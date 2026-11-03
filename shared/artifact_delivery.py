"""Explicit checked-file delivery on the original outbox; no provider or public URL."""

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from contracts.delivery import ArtifactDeliveryFile
from contracts.document_artifacts import DraftArtifactV2
from contracts.templates import ArtifactPayload
from shared.artifact_document import MIME, render_docx
from shared.canvas_reads import SourceRefreshRequired


def descriptor(row):
    return ArtifactPayload(
        file_id=str(row["id"]),
        artifact_id=str(row["artifact_id"]),
        check_id=str(row["check_id"]),
        filename=row["filename"],
        media_type=row["media_type"],
        sha256=row["sha256"],
        byte_length=row["byte_length"],
    )


class ArtifactDeliveryStore:
    def _checked_artifact_file(self, conn, user, artifact_id):
        artifact, duty, draft = self._private_artifact(conn, user, artifact_id)
        check = self._private_check(conn, artifact)
        proofs, cache = self._private_proofs(conn, artifact, draft, check)
        content = render_docx(DraftArtifactV2.model_validate(draft))
        current = self._finish_private(conn, artifact, duty, proofs, cache, check)
        paused = conn.execute(
            "SELECT paused FROM wrytely_agent.agents WHERE id=%s", (artifact["agent_id"],)
        ).fetchone()["paused"]
        if (
            artifact["state"] != "ready"
            or not check
            or not check["report"]["passed"]
            or current["state"] != "current"
            or paused
            or duty["status"] not in ("active", "done")
        ):
            raise SourceRefreshRequired()
        # Download inspection freshness is not enough for an outward action.
        bindings = conn.execute(
            "SELECT object_id FROM wrytely_agent.responsibility_canvas_objects "
            "WHERE agent_id=%s AND responsibility_id=%s ORDER BY object_id",
            (artifact["agent_id"], duty["id"]),
        ).fetchall()
        for binding in bindings:
            _, _, projection = self._document_observation(
                conn,
                artifact["agent_id"],
                duty["id"],
                binding["object_id"],
                None,
                task=True,
                purpose="act",
            )
            if not projection["freshness"]["usable"] or projection["historical"]:
                raise SourceRefreshRequired()
        now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        for proof in cache.values():
            if proof["reference"]["kind"] == "legacy":
                checked = proof["source"]["freshness"]["checked_at"]
                if checked is None or now - checked > timedelta(hours=1):
                    raise SourceRefreshRequired()
        if not 0 < len(content) <= 10485760:
            raise ValueError("Document byte limit")
        return artifact, check, content

    def enqueue_checked_artifact_delivery(self, verified_user, artifact_id):
        """Explicit session/signed-linked student request, never automatic from drafting."""
        with self.connection() as conn:
            artifact, check, content = self._checked_artifact_file(conn, verified_user, artifact_id)
            prior = conn.execute(
                "SELECT w.id,w.state FROM wrytely_agent.artifact_delivery_files f "
                "JOIN wrytely_agent.whatsapp_outbound w ON w.artifact_file_id=f.id "
                "AND w.agent_id=f.agent_id WHERE f.agent_id=%s AND f.artifact_id=%s",
                (artifact["agent_id"], artifact["id"]),
            ).fetchone()
            if prior:
                return prior
            link = conn.execute(
                "SELECT * FROM wrytely_agent.channel_links WHERE agent_id=%s",
                (artifact["agent_id"],),
            ).fetchone()
            if not link:
                raise LookupError("WhatsApp connection required")
            file_id = uuid4()
            conn.execute(
                "INSERT INTO wrytely_agent.artifact_delivery_files "
                "(id,agent_id,artifact_id,check_id,filename,media_type,sha256,byte_length,content) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    file_id,
                    artifact["agent_id"],
                    artifact["id"],
                    check["id"],
                    f"wrytely-{artifact['id']}.docx",
                    MIME,
                    hashlib.sha256(content).hexdigest(),
                    len(content),
                    content,
                ),
            )
            return conn.execute(
                "INSERT INTO wrytely_agent.whatsapp_outbound "
                "(id,agent_id,task_id,artifact_file_id,recipient,content,link_generation) "
                "VALUES (%s,%s,NULL,%s,%s,%s,%s) RETURNING id,state",
                (
                    uuid4(),
                    artifact["agent_id"],
                    file_id,
                    link["phone"],
                    "Your checked Wrytely draft",
                    link["generation"],
                ),
            ).fetchone()

    def _artifact_delivery_file(self, conn, outbound):
        row = conn.execute(
            "SELECT f.*,a.user_id FROM wrytely_agent.artifact_delivery_files f "
            "JOIN wrytely_agent.agents a ON a.id=f.agent_id "
            "WHERE f.id=%s AND f.agent_id=%s",
            (outbound["artifact_file_id"], outbound["agent_id"]),
        ).fetchone()
        if not row:
            raise LookupError("Not found")
        artifact, check, content = self._checked_artifact_file(
            conn, row["user_id"], row["artifact_id"]
        )
        if (
            check["id"] != row["check_id"]
            or artifact["id"] != row["artifact_id"]
            or row["filename"] != f"wrytely-{artifact['id']}.docx"
            or row["media_type"] != MIME
            or bytes(row["content"]) != content
            or hashlib.sha256(content).hexdigest() != row["sha256"]
            or len(content) != row["byte_length"]
        ):
            raise SourceRefreshRequired()
        return row

    def _authorize_artifact_delivery(self, conn, outbound):
        try:
            row = self._artifact_delivery_file(conn, outbound)
        except (LookupError, SourceRefreshRequired, ValueError):
            return None, "artifact_not_current", True
        return descriptor(row), None, False

    def read_artifact_delivery_file(self, claim):
        """Internal byte read AFTER one-use authorization; recheck before provider upload/send."""
        from shared.db import LeaseLost

        with self.connection() as conn:
            outbound = self._delivery_fence(conn, claim)
            if not outbound["artifact_file_id"] or outbound["dispatch_at"] is None:
                raise LeaseLost("Document dispatch not authorized")
            row = self._artifact_delivery_file(conn, outbound)
            payload = descriptor(row)
            if outbound["dispatch_payload"] != payload.model_dump(mode="json"):
                raise LeaseLost("Document dispatch changed")
            link = conn.execute(
                "SELECT * FROM wrytely_agent.channel_links WHERE agent_id=%s",
                (outbound["agent_id"],),
            ).fetchone()
            prefs = conn.execute(
                "SELECT * FROM wrytely_agent.communication_preferences WHERE agent_id=%s",
                (outbound["agent_id"],),
            ).fetchone()
            now = datetime.now(UTC)
            if (
                not link
                or not prefs
                or not prefs["consent"]
                or link["generation"] != outbound["link_generation"]
                or link["phone"] != outbound["recipient"]
                or link["last_event_at"] is None
                or now - link["last_event_at"] >= timedelta(hours=24)
            ):
                raise SourceRefreshRequired()
            hour = now.astimezone(ZoneInfo(prefs["timezone"])).hour
            start, end = prefs["quiet_start"], prefs["quiet_end"]
            quiet = start <= hour < end if start < end else hour >= start or hour < end
            if start != end and quiet:
                raise SourceRefreshRequired()
            return ArtifactDeliveryFile(payload, bytes(row["content"]))
