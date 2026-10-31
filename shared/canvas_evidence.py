"""Atomic staged academic evidence on the existing Store; no provider/model/delivery IO."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from psycopg.types.json import Jsonb

from contracts.canvas_evidence import RESOURCE_TYPES, AcademicBatch
from contracts.canvas_sync import Checkpoint
from contracts.models import SourceObservation
from contracts.source_digest import source_digest
from shared.canvas_sync import CanvasSyncConflict, _hash


class CanvasEvidenceStore:
    def _stage_canvas_item(self, conn, row, scan, resource_key, batch, item, observed):
        kind = item.kind or (
            "discussion"
            if batch.resource.kind == "discussions"
            else next(iter(RESOURCE_TYPES[batch.resource.kind]))
        )
        payload = item.payload(kind)
        digest = source_digest(payload)
        reference = urlsplit(item.reference)
        path = unquote(reference.path)
        base = f"/courses/{batch.resource.course_id}"
        if (
            reference.scheme != "https"
            or "https://" + reference.netloc != row["origin"]
            or not (path == base or path.startswith(base + "/"))
            or any(p in (".", "..") for p in path.split("/"))
            or any(ord(char) < 32 for char in path)
        ):
            raise ValueError("Evidence reference outside course")
        if conn.execute(
            "SELECT 1 FROM wrytely_agent.canvas_resource_items WHERE scan_id=%s "
            "AND resource_key=%s AND kind=%s AND provider_id=%s",
            (scan["id"], resource_key, kind, item.provider_id),
        ).fetchone():
            raise CanvasSyncConflict("duplicate_resource_item")
        subject_digest = hashlib.sha256(row["provider_subject"].encode()).hexdigest()
        obj = conn.execute(
            "INSERT INTO wrytely_agent.canvas_evidence_objects "
            "(id,agent_id,connection_id,subject_digest,course_id,kind,provider_id) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT(connection_id,subject_digest,course_id,kind,provider_id) "
            "DO UPDATE SET provider_id=excluded.provider_id RETURNING *",
            (
                uuid4(),
                row["agent_id"],
                row["id"],
                subject_digest,
                batch.resource.course_id,
                kind,
                item.provider_id,
            ),
        ).fetchone()
        prior = conn.execute(
            "SELECT * FROM wrytely_agent.canvas_evidence_observations WHERE id=%s",
            (obj["latest_observation_id"],),
        ).fetchone()
        historical = prior is not None and observed < prior["observed_at"]
        if prior and observed == prior["observed_at"] and digest != prior["content_digest"]:
            raise CanvasSyncConflict("ambiguous_observation_time")
        version = None
        if payload["content"].strip() and payload["title"].strip():
            identity = [
                str(row["id"]),
                subject_digest,
                batch.resource.course_id,
                kind,
                item.provider_id,
            ]
            source_key = "canvas:" + str(row["id"]) + ":" + _hash(identity)
            observation = SourceObservation(
                source_key=source_key,
                external_revision=digest,
                title=payload["title"],
                reference=item.reference,
                coverage="api",
                content=payload["content"],
                retrieved_at=observed,
            )
            version = self._observe_source_transaction(
                conn, row["agent_id"], observation, promote=False
            )
            conn.execute(
                "INSERT INTO wrytely_agent.canvas_evidence_payloads VALUES (%s,%s,%s,%s) "
                "ON CONFLICT(version_id) DO NOTHING",
                (row["agent_id"], version["id"], digest, Jsonb(payload)),
            )
        observation_id = uuid4()
        conn.execute(
            "INSERT INTO wrytely_agent.canvas_evidence_observations "
            "(id,agent_id,object_id,scan_id,generation,resource_key,observed_at,provider_updated_at,"
            "reference,coverage,content_digest,payload,version_id,historical) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                observation_id,
                row["agent_id"],
                obj["id"],
                scan["id"],
                row["generation"],
                resource_key,
                observed,
                datetime.fromisoformat(item.provider_updated_at.replace("Z", "+00:00")).astimezone(
                    UTC
                )
                if item.provider_updated_at
                else None,
                item.reference,
                item.coverage,
                digest,
                Jsonb(payload),
                version["id"] if version else None,
                historical,
            ),
        )
        if version and obj["source_id"] is None:
            conn.execute(
                "UPDATE wrytely_agent.canvas_evidence_objects SET source_id=%s WHERE id=%s",
                (version["source_id"], obj["id"]),
            )
        if not historical:
            conn.execute(
                "UPDATE wrytely_agent.canvas_evidence_objects SET latest_observation_id=%s, "
                "last_observed_at=%s,missing_pending_confirmation=false, "
                "complete_version_id=CASE WHEN %s THEN %s ELSE complete_version_id END, "
                "last_successful_check_at=CASE WHEN %s THEN %s ELSE last_successful_check_at END "
                "WHERE id=%s",
                (
                    observation_id,
                    observed,
                    item.coverage == "complete",
                    version["id"] if version else None,
                    item.coverage == "complete",
                    observed,
                    obj["id"],
                ),
            )
            if prior is None or digest != prior["content_digest"]:
                event_kind = (
                    "source_observed"
                    if prior is None
                    else (
                        "coverage_changed"
                        if prior["coverage"] != item.coverage
                        else "source_changed"
                    )
                )
                conn.execute(
                    "INSERT INTO wrytely_agent.canvas_evidence_events "
                    "(id,agent_id,object_id,observation_id,kind) VALUES (%s,%s,%s,%s,%s)",
                    (uuid4(), row["agent_id"], obj["id"], observation_id, event_kind),
                )
                if obj["source_id"] is not None:
                    duties = conn.execute(
                        "SELECT responsibility_id FROM "
                        "wrytely_agent.responsibility_sources WHERE source_id=%s "
                        "AND agent_id=%s",
                        (obj["source_id"], row["agent_id"]),
                    ).fetchall()
                    for duty in duties:
                        self._invalidate_memory(conn, duty["responsibility_id"])
        complete = item.coverage == "complete" and not historical
        conn.execute(
            "INSERT INTO wrytely_agent.canvas_resource_items VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                scan["id"],
                resource_key,
                kind,
                item.provider_id,
                row["agent_id"],
                obj["id"],
                observation_id,
                digest,
                complete,
            ),
        )
        return {
            "provider_id": item.provider_id,
            "kind": kind,
            "observation_id": str(observation_id),
            "version_id": str(version["id"]) if version else None,
            "content_digest": digest,
            "coverage": item.coverage,
            "historical": historical,
        }

    def _commit_academic_batch(
        self, actor, scan_id, generation, lease_token, batch_key, expected_checkpoint, envelope
    ):
        if len(json.dumps(envelope, ensure_ascii=False, allow_nan=False).encode()) > 1024 * 1024:
            raise ValueError("Batch size limit")
        batch = AcademicBatch.model_validate(envelope)
        Checkpoint.model_validate(expected_checkpoint)
        if (
            batch.scan_id != str(scan_id)
            or batch.generation != generation
            or batch.batch_key != batch_key
        ):
            raise ValueError("Batch context mismatch")
        digest = _hash([expected_checkpoint, envelope])
        with self.connection() as conn:
            row, scan = self._scan(conn, actor, scan_id, generation)
            if batch.connection_id != str(row["id"]) or batch.subject != row["provider_subject"]:
                raise CanvasSyncConflict("subject_changed")
            prior = self._receipt(conn, scan, "batch", batch_key, digest)
            if prior:
                return prior
            self._live(conn, scan, lease_token)
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
            if scan["checkpoint"]["resource"] != resource_key:
                previous = conn.execute(
                    "SELECT coverage FROM wrytely_agent.canvas_resources "
                    "WHERE scan_id=%s AND resource_key=%s",
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
            observed = datetime.fromisoformat(batch.observed_at.replace("Z", "+00:00"))
            if observed < scan["started_at"] or observed > datetime.now(UTC) + timedelta(minutes=5):
                raise ValueError("Observation outside scan window")
            if batch.coverage.seen_count != resource["seen_count"] + len(batch.items):
                raise ValueError("Inconsistent cumulative count")
            observations = [
                self._stage_canvas_item(conn, row, scan, resource_key, batch, item, observed)
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
                "UPDATE wrytely_agent.canvas_resources SET seen_count=%s,page_count=page_count+1, "
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
            result = {
                "receipt_id": str(uuid4()),
                "scan_id": str(scan["id"]),
                "batch_key": batch_key,
                "batch_digest": digest,
                "checkpoint": checkpoint,
                "coverage": batch.coverage.state,
                "replayed": False,
                "observations": observations,
                "source_versions": [
                    {k: o[k] for k in ("provider_id", "version_id", "content_digest")}
                    for o in observations
                    if o["version_id"] is not None
                ],
            }
            return self._save(conn, scan, "batch", batch_key, digest, result)

    @staticmethod
    def _academic_resource_manifest(conn, row, scan, resource_key, resource):
        if (
            not resource["page_count"]
            or resource["last_page_coverage"] != "complete"
            or resource["next_cursor"] is not None
            or resource["incomplete_count"]
        ):
            raise CanvasSyncConflict("incomplete_resource")
        course, kind = resource_key.split("/", 1)
        if kind not in RESOURCE_TYPES:
            raise CanvasSyncConflict("incomplete_resource")
        items = conn.execute(
            "SELECT kind,provider_id,content_digest FROM "
            "wrytely_agent.canvas_resource_items WHERE scan_id=%s AND resource_key=%s "
            "ORDER BY kind,provider_id",
            (scan["id"], resource_key),
        ).fetchall()
        subject_digest = hashlib.sha256(row["provider_subject"].encode()).hexdigest()
        conn.execute(
            "UPDATE wrytely_agent.canvas_evidence_objects o SET missing_pending_confirmation=true "
            "WHERE connection_id=%s AND subject_digest=%s AND course_id=%s AND kind=ANY(%s) "
            "AND NOT EXISTS (SELECT 1 FROM wrytely_agent.canvas_resource_items i "
            "WHERE i.scan_id=%s AND i.resource_key=%s AND i.object_id=o.id)",
            (
                row["id"],
                subject_digest,
                course,
                list(RESOURCE_TYPES[kind]),
                scan["id"],
                resource_key,
            ),
        )
        return _hash(items)
