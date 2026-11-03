"""Proactive offers are distinct intents in the original WhatsApp dispatch queue."""

from datetime import timedelta
from uuid import uuid4

from shared.canvas_reads import SourceRefreshRequired, _uuid


class CourseOfferDeliveryStore:
    def set_course_notification_consent(self, verified_user, supervision_id, *, consent):
        if type(consent) is not bool:
            raise ValueError("Explicit notification consent required")
        with self.connection() as conn:
            agent, _ = self._read_identity(conn, verified_user, None)
            row = conn.execute(
                "UPDATE wrytely_agent.course_supervisions SET notification_consent=%s "
                "WHERE agent_id=%s AND id=%s RETURNING id,notification_consent",
                (consent, agent, _uuid(supervision_id)),
            ).fetchone()
            if not row:
                raise LookupError("Not found")
            return row

    def _current_course_offer(self, conn, user, supervision_id, offer_id):
        agent, connection, monitor = self._supervision_scope(conn, user, supervision_id)
        offer = conn.execute(
            "SELECT * FROM wrytely_agent.course_offers WHERE agent_id=%s "
            "AND supervision_id=%s AND id=%s FOR UPDATE",
            (agent["id"], monitor["id"], _uuid(offer_id)),
        ).fetchone()
        if not offer:
            raise LookupError("Not found")
        if monitor["state"] == "paused":
            return offer, "course_paused", False
        if not monitor["notification_consent"]:
            return offer, "proactive_consent_missing", False
        if offer["state"] != "pending":
            return offer, "offer_not_pending", True
        now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        if now >= offer["created_at"] + timedelta(hours=24):
            return offer, "offer_expired", True
        if not offer["evidence"] or len(offer["evidence"]) > 8:
            return offer, "offer_evidence_invalid", True
        for pin in offer["evidence"]:
            rows = self._evidence_rows(
                conn,
                agent["id"],
                connection,
                None,
                course=monitor["course_id"],
                object_id=_uuid(pin["object_id"]),
                limit=1,
            )
            if not rows:
                return offer, "offer_source_changed", True
            projection = self._evidence_projection(conn, connection, rows[0], purpose="act")[0]
            if (
                not projection["freshness"]["usable"]
                or projection["historical"]
                or str(projection["document_version_id"] or projection["latest_version_id"])
                != pin["version_id"]
            ):
                return offer, "offer_source_changed", True
        return offer, None, False

    def enqueue_course_offer(self, verified_user, supervision_id, offer_id):
        """Trusted assembly queues one evidenced offer, never arbitrary model text/recipient."""
        with self.connection() as conn:
            offer, reason, _ = self._current_course_offer(
                conn, verified_user, supervision_id, offer_id
            )
            if reason:
                raise ValueError(reason)
            link = conn.execute(
                "SELECT * FROM wrytely_agent.channel_links WHERE agent_id=%s", (offer["agent_id"],)
            ).fetchone()
            if not link:
                raise LookupError("WhatsApp connection required")
            prior = conn.execute(
                "SELECT id,state FROM wrytely_agent.whatsapp_outbound WHERE agent_id=%s "
                "AND course_offer_id=%s",
                (offer["agent_id"], offer["id"]),
            ).fetchone()
            if prior:
                return prior
            return conn.execute(
                "INSERT INTO wrytely_agent.whatsapp_outbound "
                "(id,agent_id,task_id,course_offer_id,recipient,content,link_generation) "
                "VALUES (%s,%s,NULL,%s,%s,%s,%s) RETURNING id,state",
                (
                    uuid4(),
                    offer["agent_id"],
                    offer["id"],
                    link["phone"],
                    offer["message"],
                    link["generation"],
                ),
            ).fetchone()

    def _authorize_course_offer(self, conn, outbound):
        user = conn.execute(
            "SELECT user_id FROM wrytely_agent.agents WHERE id=%s", (outbound["agent_id"],)
        ).fetchone()["user_id"]
        saved = conn.execute(
            "SELECT supervision_id FROM wrytely_agent.course_offers WHERE agent_id=%s AND id=%s",
            (outbound["agent_id"], outbound["course_offer_id"]),
        ).fetchone()
        if not saved:
            return "offer_not_found", True
        try:
            offer, reason, cancel = self._current_course_offer(
                conn, user, saved["supervision_id"], outbound["course_offer_id"]
            )
        except (LookupError, SourceRefreshRequired):
            return "offer_scope_changed", True
        if reason:
            return reason, cancel
        if offer["message"] != outbound["content"]:
            return "offer_content_changed", True
        if (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.whatsapp_outbound WHERE agent_id=%s "
                "AND course_offer_id IS NOT NULL "
                "AND dispatch_at>clock_timestamp()-interval '24 hours'",
                (outbound["agent_id"],),
            ).fetchone()["n"]
            >= 3
        ):
            return "proactive_daily_limit", False
        return None, False
