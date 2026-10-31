"""Canvas sync leases, discovery and consent; academic batches share the same Store transaction."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from contracts.canvas_sync import (
    REASONS,
    RESOURCE_KINDS,
    Checkpoint,
    DiscoveryBatch,
    course_id,
    replay_key,
)
from contracts.source_digest import source_digest
from shared.source_connections import SourceCredentialRejected, _digest, _safe


class CanvasSyncConflict(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _hash(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _lease(scan):
    return {
        "scan_id": str(scan["id"]),
        "scan_sequence": scan["sequence"],
        "lease_token": str(scan["lease_token"]),
        "lease_expires_at": scan["lease_expires_at"].isoformat(),
        "checkpoint": scan["checkpoint"],
    }


class CanvasSyncStore:
    @staticmethod
    def _abort_canvas_scans(conn, connection_id, reason):
        rows = conn.execute(
            "UPDATE wrytely_agent.canvas_scans SET state='aborted',reason=%s "
            "WHERE connection_id=%s AND state='active' RETURNING id",
            (reason, connection_id),
        ).fetchall()
        for row in rows:
            conn.execute(
                "UPDATE wrytely_agent.source_connections SET discovery_coverage='partial' "
                "WHERE id=%s AND EXISTS (SELECT 1 FROM wrytely_agent.canvas_resources "
                "WHERE scan_id=%s AND resource_key='courses' AND coverage='open')",
                (connection_id, row["id"]),
            )
            conn.execute(
                "UPDATE wrytely_agent.canvas_resources SET coverage='aborted',reason=%s "
                "WHERE scan_id=%s AND coverage='open'",
                (reason, row["id"]),
            )

    def _reset_canvas_context(self, conn, connection_id):
        self._abort_canvas_scans(conn, connection_id, "connection_changed")
        conn.execute(
            "UPDATE wrytely_agent.source_connections SET scope_revision=scope_revision+1, "
            "scope_mode='explicit_set',selected_course_ids='[]',resource_kinds='[]', "
            "discovery_coverage='unknown',discovery_attempt_at=NULL,discovery_complete_at=NULL "
            "WHERE id=%s",
            (connection_id,),
        )

    @staticmethod
    def _courses(conn, row):
        if row["scope_mode"] == "explicit_set":
            return row["selected_course_ids"]
        courses = [
            c["course_id"]
            for c in conn.execute(
                "SELECT course_id FROM wrytely_agent.canvas_catalog WHERE connection_id=%s "
                "AND generation=%s AND NOT missing_pending_confirmation "
                "AND payload->'fields'->>'enrollment_state'='active' "
                "ORDER BY course_id",
                (row["id"], row["generation"]),
            ).fetchall()
        ]
        if len(courses) > 1000:
            raise CanvasSyncConflict("course_scope_limit")
        return courses

    def _context(self, conn, row):
        courses = self._courses(conn, row)
        return {
            **_safe(row),
            "scope_revision": row["scope_revision"],
            "mode": row["scope_mode"],
            "course_ids": courses,
            "resource_kinds": row["resource_kinds"],
            "discovery": {
                "coverage": row["discovery_coverage"],
                "last_attempt_at": row["discovery_attempt_at"].isoformat()
                if row["discovery_attempt_at"]
                else None,
                "last_complete_at": row["discovery_complete_at"].isoformat()
                if row["discovery_complete_at"]
                else None,
            },
        }

    def canvas_connection_context(self, credential, origin):
        with self.connection() as conn:
            row = self._lock_canvas_credential(conn, credential, origin)
            self._expire(conn, row["id"])
            row = conn.execute(
                "SELECT * FROM wrytely_agent.source_connections WHERE id=%s", (row["id"],)
            ).fetchone()
            return self._context(conn, row)

    def set_canvas_scope(
        self, verified_user, connection_id, generation, *, mode, course_ids, resource_kinds
    ):
        if mode not in ("explicit_set", "all_active") or type(generation) is not int:
            raise ValueError("Invalid scope")
        if (
            not isinstance(course_ids, list)
            or len(course_ids) > 1000
            or not isinstance(resource_kinds, list)
            or len(resource_kinds) > 9
        ):
            raise ValueError("Invalid scope")
        ids = sorted({course_id(c) for c in course_ids})
        if (
            len(ids) != len(course_ids)
            or any(not isinstance(k, str) or k not in RESOURCE_KINDS for k in resource_kinds)
            or len(set(resource_kinds)) != len(resource_kinds)
            or (mode == "all_active" and ids)
        ):
            raise ValueError("Invalid scope")
        kinds = sorted(resource_kinds)
        with self.connection() as conn:
            agent = conn.execute(
                "SELECT id FROM wrytely_agent.agents WHERE user_id=%s FOR UPDATE", (verified_user,)
            ).fetchone()
            row = conn.execute(
                "SELECT * FROM wrytely_agent.source_connections "
                "WHERE id=%s AND agent_id=%s FOR UPDATE",
                (UUID(str(connection_id)), agent["id"] if agent else None),
            ).fetchone()
            if not row:
                raise LookupError("Not found")
            if row["generation"] != generation:
                raise CanvasSyncConflict("generation_changed")
            if row["state"] != "connected" or row["credential_expires_at"] <= datetime.now(UTC):
                raise CanvasSyncConflict("reconnect_required")
            if (row["scope_mode"], row["selected_course_ids"], row["resource_kinds"]) == (
                mode,
                ids,
                kinds,
            ):
                return self._context(conn, row)
            catalog = {
                r["course_id"]
                for r in conn.execute(
                    "SELECT course_id FROM wrytely_agent.canvas_catalog WHERE connection_id=%s "
                    "AND generation=%s AND NOT missing_pending_confirmation",
                    (row["id"], generation),
                ).fetchall()
            }
            if not set(ids) <= catalog:
                raise CanvasSyncConflict("course_not_discovered")
            if (row["scope_mode"], row["selected_course_ids"], row["resource_kinds"]) != (
                mode,
                ids,
                kinds,
            ):
                self._abort_canvas_scans(conn, row["id"], "scope_changed")
                conn.execute(
                    "INSERT INTO wrytely_agent.canvas_catalog "
                    "SELECT connection_id,generation+1,course_id,payload,content_digest,"
                    "observed_at,missing_pending_confirmation FROM wrytely_agent.canvas_catalog "
                    "WHERE connection_id=%s AND generation=%s",
                    (row["id"], generation),
                )
                row = conn.execute(
                    "UPDATE wrytely_agent.source_connections SET generation=generation+1, "
                    "scope_revision=scope_revision+1,scope_mode=%s,selected_course_ids=%s, "
                    "resource_kinds=%s,updated_at=clock_timestamp() WHERE id=%s RETURNING *",
                    (mode, Jsonb(ids), Jsonb(kinds), row["id"]),
                ).fetchone()
            return self._context(conn, row)

    def _actor(self, conn, actor, connection_id, generation, scope_revision=None, subject=None):
        if not isinstance(actor, str) or len(actor) != 43:
            raise SourceCredentialRejected()
        candidate = conn.execute(
            "SELECT origin FROM wrytely_agent.source_connections "
            "WHERE id=%s AND credential_hash=%s",
            (connection_id, _digest(actor)),
        ).fetchone()
        if not candidate:
            raise SourceCredentialRejected()
        row = self._lock_canvas_credential(conn, actor, candidate["origin"])
        if row["state"] != "connected":
            raise CanvasSyncConflict("identity_required")
        if type(generation) is not int or row["generation"] != generation:
            raise CanvasSyncConflict("generation_changed")
        if scope_revision is not None and (
            type(scope_revision) is not int or row["scope_revision"] != scope_revision
        ):
            raise CanvasSyncConflict("scope_changed")
        if subject is not None and row["provider_subject"] != subject:
            raise CanvasSyncConflict("subject_changed")
        return row

    @staticmethod
    def _expire(conn, connection_id):
        rows = conn.execute(
            "UPDATE wrytely_agent.canvas_scans SET state='expired', "
            "reason='scan_expired' WHERE connection_id=%s AND state='active' "
            "AND expires_at<=clock_timestamp() RETURNING id",
            (connection_id,),
        ).fetchall()
        for row in rows:
            conn.execute(
                "UPDATE wrytely_agent.source_connections SET discovery_coverage='partial' "
                "WHERE id=%s AND EXISTS (SELECT 1 FROM wrytely_agent.canvas_resources "
                "WHERE scan_id=%s AND resource_key='courses' AND coverage='open')",
                (connection_id, row["id"]),
            )
            conn.execute(
                "UPDATE wrytely_agent.canvas_resources SET coverage='aborted', "
                "reason='scan_expired' WHERE scan_id=%s AND coverage='open'",
                (row["id"],),
            )

    def begin_sync(self, actor, connection_id, generation, subject, scope_revision, begin_key):
        replay_key(begin_key)
        connection_id = UUID(str(connection_id))
        if not isinstance(subject, str) or not subject:
            raise ValueError("Provider subject required")
        digest = _hash([str(connection_id), generation, subject, scope_revision])
        with self.connection() as conn:
            row = self._actor(conn, actor, connection_id, generation, scope_revision, subject)
            self._expire(conn, row["id"])
            scan = conn.execute(
                "SELECT * FROM wrytely_agent.canvas_scans WHERE connection_id=%s AND begin_key=%s",
                (row["id"], begin_key),
            ).fetchone()
            if scan:
                if scan["begin_digest"] != digest:
                    raise CanvasSyncConflict("replay_conflict")
                if scan["state"] in ("expired", "aborted"):
                    raise CanvasSyncConflict("scan_terminal")
                return conn.execute(
                    "SELECT response FROM wrytely_agent.canvas_sync_receipts "
                    "WHERE scan_id=%s AND operation='begin'",
                    (scan["id"],),
                ).fetchone()["response"]
            if conn.execute(
                "SELECT 1 FROM wrytely_agent.canvas_scans WHERE connection_id=%s "
                "AND state='active'",
                (row["id"],),
            ).fetchone():
                raise CanvasSyncConflict("resume_existing_scan")
            sequence = conn.execute(
                "UPDATE wrytely_agent.source_connections SET "
                "scan_sequence=scan_sequence+1 WHERE id=%s RETURNING scan_sequence",
                (row["id"],),
            ).fetchone()["scan_sequence"]
            checkpoint = {
                "resource": "courses",
                "next_cursor": None,
                "sequence": 0,
                "scope_revision": scope_revision,
            }
            scan = conn.execute(
                "INSERT INTO wrytely_agent.canvas_scans "
                "(id,connection_id,generation,scope_revision,sequence,begin_key,"
                "begin_digest,lease_token,lease_expires_at,checkpoint) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,clock_timestamp()+interval '300 seconds',%s) "
                "RETURNING *",
                (
                    uuid4(),
                    row["id"],
                    generation,
                    scope_revision,
                    sequence,
                    begin_key,
                    digest,
                    uuid4(),
                    Jsonb(checkpoint),
                ),
            ).fetchone()
            keys = ["courses"] + [
                f"{c}/{k}" for c in self._courses(conn, row) for k in row["resource_kinds"]
            ]
            for key in keys:
                conn.execute(
                    "INSERT INTO wrytely_agent.canvas_resources(scan_id,resource_key) "
                    "VALUES (%s,%s)",
                    (scan["id"], key),
                )
            conn.execute(
                "UPDATE wrytely_agent.source_connections SET "
                "discovery_attempt_at=clock_timestamp() WHERE id=%s",
                (row["id"],),
            )
            result = _lease(scan)
            self._save(conn, scan, "begin", begin_key, digest, result)
            return result

    def _scan(self, conn, actor, scan_id, generation):
        scan = conn.execute(
            "SELECT * FROM wrytely_agent.canvas_scans WHERE id=%s", (UUID(str(scan_id)),)
        ).fetchone()
        if not scan:
            raise SourceCredentialRejected()
        row = self._actor(conn, actor, scan["connection_id"], generation, scan["scope_revision"])
        if scan["generation"] != generation:
            raise CanvasSyncConflict("generation_changed")
        self._expire(conn, row["id"])
        scan = conn.execute(
            "SELECT * FROM wrytely_agent.canvas_scans WHERE id=%s FOR UPDATE", (scan["id"],)
        ).fetchone()
        if scan["state"] in ("expired", "aborted"):
            raise CanvasSyncConflict("scan_terminal")
        return row, scan

    @staticmethod
    def _receipt(conn, scan, operation, key, digest):
        replay_key(key)
        receipt = conn.execute(
            "SELECT * FROM wrytely_agent.canvas_sync_receipts WHERE "
            "scan_id=%s AND operation=%s AND replay_key=%s",
            (scan["id"], operation, key),
        ).fetchone()
        if receipt:
            if receipt["digest"] != digest:
                raise CanvasSyncConflict("replay_conflict")
            return {**receipt["response"], "replayed": True}

    @staticmethod
    def _save(conn, scan, operation, key, digest, result):
        if (
            operation in ("batch", "resource", "finish")
            and not conn.execute(
                "SELECT 1 FROM wrytely_agent.canvas_scans WHERE id=%s "
                "AND lease_expires_at>clock_timestamp()",
                (scan["id"],),
            ).fetchone()
        ):
            raise CanvasSyncConflict("lease_expired")
        conn.execute(
            "INSERT INTO wrytely_agent.canvas_sync_receipts VALUES (%s,%s,%s,%s,%s)",
            (scan["id"], operation, key, digest, Jsonb(result)),
        )
        return result

    @staticmethod
    def _live(conn, scan, token):
        if scan["state"] != "active":
            raise CanvasSyncConflict("scan_terminal")
        if str(scan["lease_token"]) != str(token):
            raise CanvasSyncConflict("lease_replaced")
        if not conn.execute(
            "SELECT 1 FROM wrytely_agent.canvas_scans WHERE id=%s "
            "AND lease_expires_at>clock_timestamp()",
            (scan["id"],),
        ).fetchone():
            raise CanvasSyncConflict("lease_expired")

    def resume_sync(self, actor, scan_id, generation, resume_key):
        with self.connection() as conn:
            _, scan = self._scan(conn, actor, scan_id, generation)
            digest = _hash([str(scan_id), generation])
            prior = self._receipt(conn, scan, "resume", resume_key, digest)
            if prior:
                return prior
            if scan["state"] != "active":
                raise CanvasSyncConflict("scan_terminal")
            scan = conn.execute(
                "UPDATE wrytely_agent.canvas_scans SET lease_token=%s, "
                "lease_expires_at=least(expires_at,clock_timestamp()+interval '300 seconds') "
                "WHERE id=%s RETURNING *",
                (uuid4(), scan["id"]),
            ).fetchone()
            return self._save(conn, scan, "resume", resume_key, digest, _lease(scan))

    def commit_sync_batch(
        self, actor, scan_id, generation, lease_token, batch_key, expected_checkpoint, envelope
    ):
        if (
            isinstance(envelope, dict)
            and isinstance(envelope.get("resource"), dict)
            and (envelope["resource"].get("kind") != "courses")
        ):
            return self._commit_academic_batch(
                actor, scan_id, generation, lease_token, batch_key, expected_checkpoint, envelope
            )
        encoded = json.dumps(envelope, ensure_ascii=False, allow_nan=False).encode()
        if len(encoded) > 1024 * 1024:
            raise ValueError("Batch size limit")
        batch = DiscoveryBatch.model_validate(envelope)
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
            resource = conn.execute(
                "SELECT * FROM wrytely_agent.canvas_resources WHERE scan_id=%s "
                "AND resource_key='courses'",
                (scan["id"],),
            ).fetchone()
            if resource["coverage"] != "open":
                raise CanvasSyncConflict("resource_terminal")
            if (
                batch.next_cursor is not None
                and batch.next_cursor == scan["checkpoint"]["next_cursor"]
            ):
                raise CanvasSyncConflict("cursor_cycle")
            if resource["page_count"] >= 100 or (
                resource["page_count"] and scan["checkpoint"]["next_cursor"] is None
            ):
                raise CanvasSyncConflict("pagination_complete_or_limit")
            observed = datetime.fromisoformat(batch.observed_at.replace("Z", "+00:00"))
            if observed > datetime.now(UTC) + timedelta(minutes=5) or observed < scan["started_at"]:
                raise ValueError("Observation outside scan window")
            if batch.coverage.seen_count != resource["seen_count"] + len(batch.items):
                raise ValueError("Inconsistent cumulative count")
            for item in batch.items:
                if item.reference != row["origin"] + "/courses/" + item.provider_id:
                    raise ValueError("Course reference mismatch")
                content_digest = source_digest(item.digest_payload())
                if conn.execute(
                    "SELECT 1 FROM wrytely_agent.canvas_scan_courses "
                    "WHERE scan_id=%s AND course_id=%s",
                    (scan["id"], item.provider_id),
                ).fetchone():
                    raise CanvasSyncConflict("duplicate_course_page")
                conn.execute(
                    "INSERT INTO wrytely_agent.canvas_scan_courses VALUES (%s,%s,%s)",
                    (scan["id"], item.provider_id, content_digest),
                )
                conn.execute(
                    "INSERT INTO wrytely_agent.canvas_catalog "
                    "(connection_id,generation,course_id,payload,content_digest,observed_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT(connection_id,generation,course_id) DO UPDATE SET "
                    "payload=excluded.payload,content_digest=excluded.content_digest, "
                    "observed_at=excluded.observed_at,missing_pending_confirmation=false "
                    "WHERE canvas_catalog.observed_at<=excluded.observed_at",
                    (
                        row["id"],
                        generation,
                        item.provider_id,
                        Jsonb(item.digest_payload()),
                        content_digest,
                        observed,
                    ),
                )
                if (
                    row["scope_mode"] == "all_active"
                    and item.fields["enrollment_state"] == "active"
                ):
                    for kind in row["resource_kinds"]:
                        conn.execute(
                            "INSERT INTO wrytely_agent.canvas_resources(scan_id,resource_key) "
                            "VALUES (%s,%s) ON CONFLICT DO NOTHING",
                            (scan["id"], f"{item.provider_id}/{kind}"),
                        )
            checkpoint = {
                "resource": "courses",
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
                "last_page_coverage=%s,next_cursor=%s WHERE scan_id=%s AND resource_key='courses'",
                (batch.coverage.seen_count, batch.coverage.state, batch.next_cursor, scan["id"]),
            )
            result = {
                "receipt_id": str(uuid4()),
                "scan_id": str(scan["id"]),
                "batch_key": batch_key,
                "batch_digest": digest,
                "source_versions": [],
                "checkpoint": checkpoint,
                "coverage": batch.coverage.state,
                "replayed": False,
            }
            return self._save(conn, scan, "batch", batch_key, digest, result)

    def finish_resource(
        self,
        actor,
        scan_id,
        generation,
        lease_token,
        resource_key,
        finish_key,
        expected_checkpoint,
        *,
        outcome,
        reason,
    ):
        Checkpoint.model_validate(expected_checkpoint)
        if outcome not in ("complete", "partial", "restricted", "unsupported") or (
            (outcome == "complete" and reason is not None)
            or (outcome != "complete" and reason not in REASONS)
        ):
            raise ValueError("Invalid resource outcome")
        digest = _hash([resource_key, expected_checkpoint, outcome, reason])
        with self.connection() as conn:
            row, scan = self._scan(conn, actor, scan_id, generation)
            prior = self._receipt(conn, scan, "resource", finish_key, digest)
            if prior:
                return prior
            self._live(conn, scan, lease_token)
            if scan["checkpoint"] != expected_checkpoint:
                raise CanvasSyncConflict("checkpoint_changed")
            resource = conn.execute(
                "SELECT * FROM wrytely_agent.canvas_resources WHERE scan_id=%s AND resource_key=%s",
                (scan["id"], resource_key),
            ).fetchone()
            if not resource:
                raise CanvasSyncConflict("resource_not_selected")
            if resource["coverage"] != "open":
                raise CanvasSyncConflict("resource_terminal")
            manifest = None
            if outcome == "complete":
                if resource_key == "courses":
                    if (
                        not resource["page_count"]
                        or resource["last_page_coverage"] != "complete"
                        or resource["next_cursor"] is not None
                    ):
                        raise CanvasSyncConflict("incomplete_resource")
                    manifest = _hash(
                        conn.execute(
                            "SELECT course_id,content_digest "
                            "FROM wrytely_agent.canvas_scan_courses "
                            "WHERE scan_id=%s ORDER BY course_id",
                            (scan["id"],),
                        ).fetchall()
                    )
                else:
                    manifest = self._academic_resource_manifest(
                        conn, row, scan, resource_key, resource
                    )
            conn.execute(
                "UPDATE wrytely_agent.canvas_resources SET coverage=%s,reason=%s "
                "WHERE scan_id=%s AND resource_key=%s",
                (outcome, reason, scan["id"], resource_key),
            )
            if resource_key == "courses":
                if outcome == "complete":
                    conn.execute(
                        "UPDATE wrytely_agent.canvas_catalog c "
                        "SET missing_pending_confirmation=true "
                        "WHERE connection_id=%s AND generation=%s AND NOT EXISTS "
                        "(SELECT 1 FROM wrytely_agent.canvas_scan_courses s "
                        "WHERE s.scan_id=%s AND s.course_id=c.course_id)",
                        (row["id"], generation, scan["id"]),
                    )
                conn.execute(
                    "UPDATE wrytely_agent.source_connections SET discovery_coverage=%s, "
                    "discovery_complete_at=CASE WHEN %s='complete' THEN clock_timestamp() "
                    "ELSE discovery_complete_at END WHERE id=%s",
                    (outcome, outcome, row["id"]),
                )
            result = {
                "receipt_id": str(uuid4()),
                "coverage": outcome,
                "reason": reason,
                "seen_count": resource["seen_count"],
                "finished_at": datetime.now(UTC).isoformat(),
                "checkpoint": scan["checkpoint"],
                "source_manifest_digest": manifest,
                "resource_key": resource_key,
                "replayed": False,
            }
            return self._save(conn, scan, "resource", finish_key, digest, result)

    def finish_sync(self, actor, scan_id, generation, lease_token, finish_key):
        digest = _hash([str(scan_id), generation])
        with self.connection() as conn:
            _, scan = self._scan(conn, actor, scan_id, generation)
            prior = self._receipt(conn, scan, "finish", finish_key, digest)
            if prior:
                return prior
            self._live(conn, scan, lease_token)
            resources = conn.execute(
                "SELECT resource_key,coverage,reason FROM "
                "wrytely_agent.canvas_resources WHERE scan_id=%s ORDER BY resource_key",
                (scan["id"],),
            ).fetchall()
            if any(r["coverage"] == "open" for r in resources):
                raise CanvasSyncConflict("resources_open")
            conn.execute(
                "UPDATE wrytely_agent.canvas_scans SET state='finished' WHERE id=%s", (scan["id"],)
            )
            result = {
                "scan_id": str(scan["id"]),
                "coverage": "complete"
                if all(r["coverage"] == "complete" for r in resources)
                else "partial",
                "resources": resources,
                "replayed": False,
            }
            return self._save(conn, scan, "finish", finish_key, digest, result)
