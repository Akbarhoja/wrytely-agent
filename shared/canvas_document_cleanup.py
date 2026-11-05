"""Explicit operator-only orphan maintenance; never deletes published evidence.

No HTTP, worker, timer, provider IO or automatic migration. Application writers
hold the agent lock before touching roots; cleanup uses the same order and skips
busy agents, then rechecks every reference while holding the root row lock.
"""

_ORPHAN = """
    v.protocol_payload IS NOT NULL
    AND v.created_at<=clock_timestamp()-interval '24 hours'
    AND NOT EXISTS (SELECT 1 FROM wrytely_agent.canvas_document_bindings b
                    WHERE b.document_version_id=v.id)
    AND NOT EXISTS (SELECT 1 FROM wrytely_agent.canvas_evidence_observations n
                    WHERE n.agent_id=v.agent_id AND n.object_id=v.object_id
                    AND n.payload=v.protocol_payload)
    AND NOT EXISTS (SELECT 1 FROM wrytely_agent.canvas_document_uploads u
                    WHERE u.document_version_id=v.id)
"""


class CanvasDocumentCleanupStore:
    @staticmethod
    def _cleanup_document_upload(conn, upload_id):
        sizes = conn.execute(
            "SELECT count(*) AS parts,COALESCE(sum(octet_length(text)),0) AS bytes "
            "FROM wrytely_agent.canvas_document_upload_parts WHERE upload_id=%s",
            (upload_id,),
        ).fetchone()
        conn.execute(
            "DELETE FROM wrytely_agent.canvas_document_upload_parts WHERE upload_id=%s",
            (upload_id,),
        )
        # Retain IDs/expiry/replay receipts, but never header text or ready pointers
        # in the tombstone. Expired uploads fail closed before inspecting headers.
        conn.execute(
            "UPDATE wrytely_agent.canvas_document_uploads SET header='{}',object_id=NULL,"
            "document_version_id=NULL,cleaned_at=clock_timestamp() WHERE id=%s",
            (upload_id,),
        )
        return sizes

    def cleanup_canvas_document_staging(self, *, limit=100):
        """Trusted operator entry; bounded explicit invocation, no user/agent lookup API.

        Each class selects at most limit candidates (not limit per agent). Busy
        candidates stay for a later pass. One transaction preserves atomic rollback.
        Returned counts contain no source identifiers or text. Root age is server
        time, not an observation/check time, and cleanup never refreshes evidence.
        """
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Document cleanup limit must be1–100")
        result = {
            "uploads_cleaned": 0,
            "upload_parts_deleted": 0,
            "upload_bytes_deleted": 0,
            "roots_deleted": 0,
            "root_parts_deleted": 0,
        }
        with self.connection() as conn:
            candidates = conn.execute(
                "SELECT id,agent_id FROM wrytely_agent.canvas_document_uploads "
                "WHERE expires_at<=clock_timestamp() AND cleaned_at IS NULL "
                "ORDER BY expires_at,id LIMIT %s",
                (limit,),
            ).fetchall()
            for candidate in candidates:
                if not conn.execute(
                    "SELECT id FROM wrytely_agent.agents WHERE id=%s FOR UPDATE SKIP LOCKED",
                    (candidate["agent_id"],),
                ).fetchone():
                    continue
                upload = conn.execute(
                    "SELECT id FROM wrytely_agent.canvas_document_uploads WHERE id=%s "
                    "AND expires_at<=clock_timestamp() AND cleaned_at IS NULL "
                    "FOR UPDATE SKIP LOCKED",
                    (candidate["id"],),
                ).fetchone()
                if upload is None:
                    continue
                sizes = self._cleanup_document_upload(conn, upload["id"])
                result["uploads_cleaned"] += 1
                result["upload_parts_deleted"] += sizes["parts"]
                result["upload_bytes_deleted"] += sizes["bytes"]
            candidates = conn.execute(
                "SELECT v.id,v.agent_id FROM wrytely_agent.canvas_document_versions v WHERE "
                + _ORPHAN
                + " ORDER BY v.created_at,v.id LIMIT %s",
                (limit,),
            ).fetchall()
            for candidate in candidates:
                if not conn.execute(
                    "SELECT id FROM wrytely_agent.agents WHERE id=%s FOR UPDATE SKIP LOCKED",
                    (candidate["agent_id"],),
                ).fetchone():
                    continue
                root = conn.execute(
                    "SELECT v.id FROM wrytely_agent.canvas_document_versions v WHERE v.id=%s AND "
                    + _ORPHAN
                    + " FOR UPDATE SKIP LOCKED",
                    (candidate["id"],),
                ).fetchone()
                if root is None:
                    continue
                # Root lock + same agent serialization protects publication/finish;
                # FKs separately prevent a committed dangling binding or upload.
                deleted = conn.execute(
                    "DELETE FROM wrytely_agent.canvas_document_sections "
                    "WHERE document_version_id=%s RETURNING id",
                    (root["id"],),
                ).fetchall()
                conn.execute(
                    "DELETE FROM wrytely_agent.canvas_document_versions WHERE id=%s", (root["id"],)
                )
                result["root_parts_deleted"] += len(deleted)
                result["roots_deleted"] += 1
        return result
