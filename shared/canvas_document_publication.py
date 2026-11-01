"""Atomic document-only evidence publication on the existing sync transaction."""

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from contracts.canvas_document_publication import DocumentBatch
from contracts.canvas_sync import Checkpoint
from contracts.source_digest import _text, source_digest
from shared.canvas_evidence import _change_details, _validate_canvas_reference
from shared.canvas_sync import CanvasSyncConflict, _hash


def _document_change_payload(payload):
    if payload["kind"] != "document":
        return payload
    return {
        **payload,
        "fields": payload["fields"]["object_fields"],
        "content": {k: payload["fields"][k] for k in ("format", "extractor_version", "slots")},
    }


class CanvasDocumentPublicationStore:
    def _publish_document_item(
        self, conn, actor, row, scan, resource_key, batch, item, observed, lease_token
    ):
        _validate_canvas_reference(row["origin"], batch.resource.course_id, item.reference)
        upload = self._document_upload(conn, row, scan, UUID(item.upload_id))
        header = upload["header"]
        if (
            header["resource"] != batch.resource.model_dump()
            or header["owner_object"] != {"kind": item.kind, "provider_id": item.provider_id}
            or header["metadata"]["title"] != _text(item.title)
            or header["metadata"]["provider_updated_at"] != item.provider_updated_at
        ):
            raise CanvasSyncConflict("document_conflict")
        if upload["document_version_id"] is None:
            raise CanvasSyncConflict("document_not_ready")
        self._load_canvas_document(
            conn, row["agent_id"], upload["object_id"], upload["document_version_id"]
        )
        root = conn.execute(
            "SELECT protocol_payload FROM wrytely_agent.canvas_document_versions WHERE id=%s "
            "AND agent_id=%s AND object_id=%s",
            (upload["document_version_id"], row["agent_id"], upload["object_id"]),
        ).fetchone()
        if root is None or root["protocol_payload"] is None:
            raise CanvasSyncConflict("document_not_ready")
        payload = root["protocol_payload"]
        digest = source_digest(payload)
        obj = conn.execute(
            "SELECT * FROM wrytely_agent.canvas_evidence_objects WHERE id=%s AND "
            "agent_id=%s FOR UPDATE",
            (upload["object_id"], row["agent_id"]),
        ).fetchone()
        if conn.execute(
            "SELECT 1 FROM wrytely_agent.canvas_resource_items WHERE scan_id=%s "
            "AND resource_key=%s AND kind=%s AND provider_id=%s",
            (scan["id"], resource_key, item.kind, item.provider_id),
        ).fetchone():
            raise CanvasSyncConflict("duplicate_resource_item")
        prior = conn.execute(
            "SELECT * FROM wrytely_agent.canvas_evidence_observations WHERE id=%s",
            (obj["latest_observation_id"],),
        ).fetchone()
        prior_at = prior["observed_at"].astimezone(UTC) if prior else None
        if prior and prior_at == observed and prior["content_digest"] != digest:
            raise CanvasSyncConflict("ambiguous_observation_time")
        historical = prior_at is not None and observed < prior_at
        observation_id = uuid4()
        conn.execute(
            "INSERT INTO wrytely_agent.canvas_evidence_observations "
            "(id,agent_id,object_id,scan_id,generation,resource_key,observed_at,provider_updated_at,"
            "reference,coverage,content_digest,payload,version_id,historical) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,%s)",
            (
                observation_id,
                row["agent_id"],
                obj["id"],
                scan["id"],
                row["generation"],
                resource_key,
                observed,
                item.provider_updated_at,
                item.reference,
                payload["coverage"],
                digest,
                Jsonb(payload),
                historical,
            ),
        )
        if not historical:
            conn.execute(
                "UPDATE wrytely_agent.canvas_evidence_objects SET latest_observation_id=%s,"
                "last_observed_at=%s,missing_pending_confirmation=false,"
                "last_successful_check_at=CASE WHEN %s THEN %s ELSE "
                "last_successful_check_at END WHERE id=%s",
                (observation_id, observed, payload["coverage"] == "complete", observed, obj["id"]),
            )
        self._bind_canvas_document_sections(
            conn, row["agent_id"], obj["id"], observation_id, upload["document_version_id"]
        )
        if not historical and (prior is None or prior["content_digest"] != digest):
            changes = _change_details(
                {**prior, "payload": _document_change_payload(prior["payload"])} if prior else None,
                _document_change_payload(payload),
            )
            event_kind = (
                "source_observed"
                if prior is None
                else "coverage_changed"
                if prior["coverage"] != payload["coverage"]
                else "source_changed"
            )
            conn.execute(
                "INSERT INTO wrytely_agent.canvas_evidence_events "
                "(id,agent_id,object_id,observation_id,kind,previous_observation_id,changes) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (
                    uuid4(),
                    row["agent_id"],
                    obj["id"],
                    observation_id,
                    event_kind,
                    prior["id"] if prior else None,
                    Jsonb(changes),
                ),
            )
            self._invalidate_canvas_object_duties(
                conn, row["agent_id"], obj["id"], obj["source_id"]
            )
        conn.execute(
            "INSERT INTO wrytely_agent.canvas_resource_items VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                scan["id"],
                resource_key,
                item.kind,
                item.provider_id,
                row["agent_id"],
                obj["id"],
                observation_id,
                digest,
                payload["coverage"] == "complete" and not historical,
            ),
        )
        conn.execute(
            "UPDATE wrytely_agent.canvas_document_uploads SET "
            "published_at=clock_timestamp() WHERE id=%s",
            (upload["id"],),
        )
        return {
            "provider_id": item.provider_id,
            "kind": item.kind,
            "object_id": str(obj["id"]),
            "observation_id": str(observation_id),
            "document_version_id": str(upload["document_version_id"]),
            "document_digest": digest,
            "coverage": payload["coverage"],
            "historical": historical,
        }

    def _commit_document_batch(
        self, actor, scan_id, generation, lease_token, batch_key, expected_checkpoint, envelope
    ):
        try:
            if (
                len(json.dumps(envelope, ensure_ascii=False, allow_nan=False).encode())
                > 1024 * 1024
            ):
                raise ValueError("Document batch size limit")
        except (UnicodeError, TypeError):
            raise ValueError("Invalid document batch") from None
        batch = DocumentBatch.model_validate(envelope)
        Checkpoint.model_validate(expected_checkpoint)
        if (
            batch.scan_id != str(scan_id)
            or batch.generation != generation
            or batch.batch_key != batch_key
        ):
            raise ValueError("Document batch context mismatch")
        digest = _hash([expected_checkpoint, envelope])
        with self.connection() as conn:
            row, scan = self._scan(conn, actor, scan_id, generation)
            if batch.connection_id != str(row["id"]) or batch.subject != row["provider_subject"]:
                raise CanvasSyncConflict("subject_changed")
            self._live(conn, scan, lease_token)
            prior = self._receipt(conn, scan, "batch", batch_key, digest)
            if prior:
                # Replays retain current authority and upload expiry, not fresh evidence.
                for item in batch.items:
                    self._document_upload(conn, row, scan, UUID(item.upload_id))
                self._scan(conn, actor, scan_id, generation)
                self._live(conn, scan, lease_token)
                return prior
            if scan["checkpoint"] != expected_checkpoint:
                raise CanvasSyncConflict("checkpoint_changed")
            resource_key = batch.resource.course_id + "/" + batch.resource.kind
            resource = conn.execute(
                "SELECT * FROM wrytely_agent.canvas_resources WHERE scan_id=%s AND resource_key=%s",
                (scan["id"], resource_key),
            ).fetchone()
            if not resource:
                raise CanvasSyncConflict("resource_not_selected")
            if resource["coverage"] != "open":
                raise CanvasSyncConflict("resource_terminal")
            if resource["content_mode"] == "inline" or (
                resource["content_mode"] is None and resource["page_count"]
            ):
                raise CanvasSyncConflict("resource_format_conflict")
            if scan["checkpoint"]["resource"] != resource_key:
                previous = conn.execute(
                    "SELECT coverage FROM wrytely_agent.canvas_resources WHERE scan_id=%s "
                    "AND resource_key=%s",
                    (scan["id"], scan["checkpoint"]["resource"]),
                ).fetchone()
                if not previous or previous["coverage"] == "open":
                    raise CanvasSyncConflict("finish_previous_resource")
                if resource["page_count"]:
                    raise CanvasSyncConflict("resource_rewind")
            if (
                resource["page_count"] >= 100
                or expected_checkpoint["sequence"] >= 10000
                or (resource["page_count"] and resource["next_cursor"] is None)
            ):
                raise CanvasSyncConflict("pagination_complete_or_limit")
            if batch.next_cursor is not None and batch.next_cursor == resource["next_cursor"]:
                raise CanvasSyncConflict("cursor_cycle")
            observed = datetime.fromisoformat(batch.observed_at.replace("Z", "+00:00")).astimezone(
                UTC
            )
            if observed < scan["started_at"] or observed > datetime.now(UTC) + timedelta(minutes=5):
                raise ValueError("Observation outside scan window")
            if batch.coverage.seen_count != resource["seen_count"] + len(batch.items):
                raise ValueError("Inconsistent cumulative count")
            observations = [
                self._publish_document_item(
                    conn, actor, row, scan, resource_key, batch, item, observed, lease_token
                )
                for item in batch.items
            ]
            checkpoint = {
                "resource": resource_key,
                "sequence": expected_checkpoint["sequence"] + 1,
                "next_cursor": batch.next_cursor,
                "scope_revision": scan["scope_revision"],
            }
            conn.execute(
                "UPDATE wrytely_agent.canvas_scans SET checkpoint=%s WHERE id=%s",
                (Jsonb(checkpoint), scan["id"]),
            )
            conn.execute(
                "UPDATE wrytely_agent.canvas_resources SET "
                "content_mode='documents',seen_count=%s,page_count=page_count+1,"
                "last_page_coverage=%s,next_cursor=%s,incomplete_count=incomplete_count+%s "
                "WHERE scan_id=%s AND resource_key=%s",
                (
                    batch.coverage.seen_count,
                    batch.coverage.state,
                    batch.next_cursor,
                    sum(o["coverage"] != "complete" or o["historical"] for o in observations),
                    scan["id"],
                    resource_key,
                ),
            )
            self._scan(conn, actor, scan_id, generation)
            self._live(conn, scan, lease_token)
            for item in batch.items:
                self._document_upload(conn, row, scan, UUID(item.upload_id))
            result = {
                "schema_version": 2,
                "batch_type": "canvas_documents",
                "receipt_id": str(uuid4()),
                "scan_id": str(scan["id"]),
                "batch_key": batch_key,
                "batch_digest": digest,
                "checkpoint": checkpoint,
                "coverage": batch.coverage.state,
                "replayed": False,
                "observations": observations,
            }
            return self._save(conn, scan, "batch", batch_key, digest, result)
