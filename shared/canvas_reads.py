"""Agreed private inspection of staged Canvas evidence; no model/source activation."""

import hashlib
import json
import re
import secrets
from uuid import UUID

from shared.academic_reads import student_json
from shared.canvas_evidence import RESOURCE_TYPES
from shared.freshness import canvas_freshness


class SourceRefreshRequired(Exception):
    def __init__(self):
        super().__init__("source_refresh_required")


def _uuid(value):
    try:
        if not isinstance(value, (str, UUID)):
            raise ValueError()
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise LookupError("Not found") from None


def _bound(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Invalid read bounds")


def _budget(value):
    value = student_json(value)
    if len(json.dumps(value, ensure_ascii=False).encode()) > 1024 * 1024:
        raise ValueError("Read response limit")
    return value


class CanvasReadStore:
    def _finish_canvas_read(self, conn, lease, result, connection=None):
        result = _budget(result)
        now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        if connection is not None and connection["credential_expires_at"] <= now:
            raise SourceRefreshRequired()
        if lease is not None:
            from shared.db import LeaseLost

            self._fence(conn, lease)
            live = conn.execute(
                "SELECT 1 FROM wrytely_agent.tasks WHERE id=%s AND lease_until>clock_timestamp()",
                (lease.task_id,),
            ).fetchone()
            if not live:
                raise LeaseLost("Task lease expired during read")
        return result

    def _read_identity(self, conn, user, lease):
        if lease is not None:
            self._fence(conn, lease)
            task = conn.execute(
                "SELECT responsibility_id FROM wrytely_agent.tasks WHERE id=%s",
                (lease.task_id,),
            ).fetchone()
            return lease.agent_id, task["responsibility_id"]
        row = conn.execute(
            "SELECT id FROM wrytely_agent.agents WHERE user_id=%s FOR UPDATE", (user,)
        ).fetchone()
        if not row:
            raise LookupError("Not found")
        return row["id"], None

    @staticmethod
    def _read_connection(conn, agent, connection_id):
        row = conn.execute(
            "SELECT * FROM wrytely_agent.source_connections WHERE agent_id=%s AND id=%s",
            (agent, connection_id),
        ).fetchone()
        if not row:
            raise LookupError("Not found")
        return row

    @staticmethod
    def _evidence_rows(
        conn,
        agent,
        connection,
        duty,
        *,
        task=False,
        course=None,
        anchor=None,
        limit=1,
        object_id=None,
        observation_id=None,
        body=False,
    ):
        # All interpolated fragments are internal constants; public values are parameters.
        payload = "n.payload" if body else "NULL::jsonb"
        return conn.execute(
            "SELECT o.*,n.id AS observation_id,n.generation AS observation_generation,"
            "n.observed_at,n.received_at,n.provider_updated_at,n.version_id,n.reference,"
            "n.coverage AS item_coverage,n.historical,n.resource_key,"
            "(SELECT v.version_id FROM wrytely_agent.canvas_evidence_observations v "
            "WHERE v.id=o.latest_observation_id AND v.agent_id=o.agent_id) AS current_version_id,"
            "n.payload->>'title' AS title," + payload + " AS private_payload "
            "FROM wrytely_agent.canvas_evidence_objects o "
            "JOIN wrytely_agent.canvas_evidence_observations n ON "
            "n.id=coalesce(%s::uuid,o.latest_observation_id) AND n.object_id=o.id "
            "AND n.agent_id=o.agent_id WHERE o.agent_id=%s AND o.connection_id=%s "
            "AND o.subject_digest=%s AND (%s::text IS NULL OR o.course_id=%s) "
            "AND (%s::uuid IS NULL OR o.id>%s) AND (%s::uuid IS NULL OR o.id=%s) "
            "AND (NOT %s OR EXISTS (SELECT 1 FROM wrytely_agent.responsibility_sources b "
            "WHERE b.agent_id=o.agent_id AND b.responsibility_id=%s AND b.source_id=o.source_id)) "
            "ORDER BY o.id LIMIT %s",
            (
                observation_id,
                agent,
                connection["id"],
                hashlib.sha256((connection["provider_subject"] or "").encode()).hexdigest(),
                course,
                course,
                anchor,
                anchor,
                object_id,
                object_id,
                task,
                duty,
                limit,
            ),
        ).fetchall()

    def _evidence_projection(self, conn, connection, row):
        kind = next((k for k, v in RESOURCE_TYPES.items() if row["kind"] in v), None)
        selected = (
            row["course_id"] in self._courses(conn, connection)
            and kind in connection["resource_kinds"]
        )
        attempt = conn.execute(
            "SELECT r.coverage,s.expires_at,s.state FROM wrytely_agent.canvas_scans s "
            "LEFT JOIN wrytely_agent.canvas_resources r ON r.scan_id=s.id AND r.resource_key=%s "
            "WHERE s.connection_id=%s AND s.generation=%s ORDER BY s.sequence DESC LIMIT 1",
            (row["resource_key"], connection["id"], connection["generation"]),
        ).fetchone()
        now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        coverage = attempt["coverage"] if attempt else "unknown"
        if attempt and (
            attempt["state"] in ("expired", "aborted")
            or (attempt["state"] == "active" and attempt["expires_at"] <= now)
        ):
            coverage = "unknown"
        state = connection["state"]
        if (
            connection["credential_expires_at"] <= now
            or connection["origin"] not in self._canvas_origins
        ):
            state = "reconnect_required"
        historical = bool(
            row["historical"]
            or row["observation_id"] != row["latest_observation_id"]
            or row["observation_generation"] != connection["generation"]
        )
        freshness = canvas_freshness(
            observed_at=row["observed_at"],
            received_at=row["received_at"],
            connection_state=state,
            current_generation=connection["generation"],
            observation_generation=row["observation_generation"],
            selected=selected,
            item_coverage=row["item_coverage"],
            resource_coverage=coverage,
            historical=historical,
            missing_pending_confirmation=row["missing_pending_confirmation"],
            now=now,
        )
        projection = {
            "object_id": row["id"],
            "source_id": row["source_id"],
            "connection_id": connection["id"],
            "course_id": row["course_id"],
            "kind": row["kind"],
            "provider_id": row["provider_id"],
            "title": row["title"],
            "latest_version_id": row["current_version_id"],
            "latest_observation_id": row["latest_observation_id"],
            "document_version_id": None,
            "coverage": row["item_coverage"],
            "resource_coverage": coverage,
            "missing_pending_confirmation": row["missing_pending_confirmation"],
            "historical": historical,
            "freshness": {
                "usable": freshness.usable,
                "reason": freshness.reason,
                "checked_at": freshness.checked_at,
                "expires_at": freshness.expires_at,
            },
        }
        return projection, selected, state

    @staticmethod
    def _read_cursor(conn, token, agent, connection, course, task_id):
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{32}", token):
            raise ValueError("Invalid read cursor")
        row = conn.execute(
            "SELECT anchor FROM wrytely_agent.canvas_read_cursors WHERE token_hash=%s "
            "AND agent_id=%s AND connection_id=%s AND generation=%s "
            "AND course_filter IS NOT DISTINCT FROM %s AND task_id IS NOT DISTINCT FROM %s "
            "AND expires_at>clock_timestamp()",
            (
                hashlib.sha256(token.encode()).hexdigest(),
                agent,
                connection["id"],
                connection["generation"],
                course,
                task_id,
            ),
        ).fetchone()
        if not row:
            raise ValueError("Invalid read cursor")
        return row["anchor"]

    @staticmethod
    def _issue_read_cursor(conn, agent, connection, course, task_id, anchor):
        # Agent lock bounds concurrent issuance; expired handles never refresh source evidence.
        conn.execute(
            "DELETE FROM wrytely_agent.canvas_read_cursors WHERE token_hash IN "
            "(SELECT token_hash FROM wrytely_agent.canvas_read_cursors WHERE agent_id=%s "
            "AND expires_at<=clock_timestamp() LIMIT 256)",
            (agent,),
        )
        if (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.canvas_read_cursors WHERE agent_id=%s",
                (agent,),
            ).fetchone()["n"]
            >= 256
        ):
            raise ValueError("Read cursor limit")
        token = secrets.token_urlsafe(24)
        conn.execute(
            "INSERT INTO wrytely_agent.canvas_read_cursors "
            "(token_hash,agent_id,connection_id,generation,course_filter,task_id,anchor) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (
                hashlib.sha256(token.encode()).hexdigest(),
                agent,
                connection["id"],
                connection["generation"],
                course,
                task_id,
                anchor,
            ),
        )
        return token

    def _list_canvas_evidence(
        self, user, lease, *, connection_id, course_id=None, limit=20, cursor=None
    ):
        from contracts.canvas_sync import course_id as validate_course

        _bound(limit, 1, 50)
        connection_id = _uuid(connection_id)
        if course_id is not None:
            course_id = validate_course(course_id)
        with self.connection() as conn:
            agent, duty = self._read_identity(conn, user, lease)
            connection = self._read_connection(conn, agent, connection_id)
            if (
                lease is not None
                and course_id is not None
                and not self._evidence_rows(
                    conn, agent, connection, duty, task=True, course=course_id
                )
            ):
                # A task must not infer unbound course existence through filter errors.
                raise LookupError("Not found")
            if (
                course_id is not None
                and not conn.execute(
                    "SELECT 1 FROM wrytely_agent.canvas_catalog WHERE connection_id=%s "
                    "AND generation=%s AND course_id=%s",
                    (connection_id, connection["generation"], course_id),
                ).fetchone()
            ):
                raise LookupError("Not found")
            task_id = lease.task_id if lease is not None else None
            anchor = (
                self._read_cursor(conn, cursor, agent, connection, course_id, task_id)
                if cursor is not None
                else None
            )
            rows = self._evidence_rows(
                conn,
                agent,
                connection,
                duty,
                task=lease is not None,
                course=course_id,
                anchor=anchor,
                limit=limit + 1,
            )
            result = {
                "sources": [
                    self._evidence_projection(conn, connection, r)[0] for r in rows[:limit]
                ],
                "next_cursor": None,
            }
            if len(rows) > limit:
                result["next_cursor"] = self._issue_read_cursor(
                    conn, agent, connection, course_id, task_id, rows[limit - 1]["id"]
                )
            return self._finish_canvas_read(conn, lease, result)

    def list_canvas_evidence(self, verified_user, **kwargs):
        return self._list_canvas_evidence(verified_user, None, **kwargs)

    def list_canvas_evidence_for_task(self, lease, **kwargs):
        return self._list_canvas_evidence(None, lease, **kwargs)

    def _read_canvas_evidence(
        self, user, lease, object_id, *, observation_id=None, offset=0, limit=12000
    ):
        _bound(offset, 0, 24000)
        _bound(limit, 1, 12000)
        object_id = _uuid(object_id)
        observation_id = _uuid(observation_id) if observation_id is not None else None
        if offset and observation_id is None:
            raise ValueError("Pinned observation required")
        with self.connection() as conn:
            agent, duty = self._read_identity(conn, user, lease)
            owned = conn.execute(
                "SELECT connection_id FROM wrytely_agent.canvas_evidence_objects "
                "WHERE id=%s AND agent_id=%s",
                (object_id, agent),
            ).fetchone()
            if not owned:
                raise LookupError("Not found")
            connection = self._read_connection(conn, agent, owned["connection_id"])
            rows = self._evidence_rows(
                conn,
                agent,
                connection,
                duty,
                task=lease is not None,
                object_id=object_id,
                observation_id=observation_id,
                body=True,
            )
            if not rows:
                raise LookupError("Not found")
            row = rows[0]
            projection, selected, state = self._evidence_projection(conn, connection, row)
            if (
                state != "connected"
                or not selected
                or row["observation_generation"] != connection["generation"]
            ):
                raise SourceRefreshRequired()
            text = row["private_payload"]["content"]
            if offset > len(text):
                raise ValueError("Invalid read bounds")
            end = min(len(text), offset + limit)
            projection.update(
                {
                    "observation_id": row["observation_id"],
                    "version_id": row["version_id"],
                    "observed_at": row["observed_at"],
                    "received_at": row["received_at"],
                    "provider_updated_at": row["provider_updated_at"],
                    "reference": (
                        f"canvas-object:{row['course_id']}:{row['kind']}:{row['provider_id']}"
                    ),
                    "fields": row["private_payload"]["fields"],
                    "missing": row["private_payload"]["missing"],
                    "section": {
                        "text": text[offset:end],
                        "offset": offset,
                        "next_offset": end if end < len(text) else None,
                        "total_characters": len(text),
                    },
                }
            )
            return self._finish_canvas_read(conn, lease, projection, connection)

    def read_canvas_evidence(self, verified_user, object_id, **kwargs):
        return self._read_canvas_evidence(verified_user, None, object_id, **kwargs)

    def read_canvas_evidence_for_task(self, lease, object_id, **kwargs):
        return self._read_canvas_evidence(None, lease, object_id, **kwargs)
