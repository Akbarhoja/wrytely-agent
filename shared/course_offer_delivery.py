"""Proactive offers are distinct intents in the original WhatsApp dispatch queue."""

from datetime import timedelta
from uuid import uuid4

from shared.canvas_reads import SourceRefreshRequired, _uuid


class CourseOfferDeliveryStore:
    def pending_course_offer_deliveries(self, *, limit=20):
        """Internal recovery hints, independent of model due time; not send permits.

        Every candidate must still pass enqueue_course_offer and the original
        dispatch authorization. Any existing outbox outcome excludes recovery.
        """
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Invalid offer recovery limit")
        with self.connection() as conn:
            return conn.execute(
                "SELECT a.user_id,s.id AS supervision_id,o.id AS offer_id "
                "FROM wrytely_agent.course_offers o "
                "JOIN wrytely_agent.course_supervisions s "
                "ON s.id=o.supervision_id AND s.agent_id=o.agent_id "
                "JOIN wrytely_agent.agents a ON a.id=o.agent_id "
                "JOIN wrytely_agent.source_connections c "
                "ON c.id=s.connection_id AND c.agent_id=s.agent_id "
                "JOIN wrytely_agent.channel_links l ON l.agent_id=a.id "
                "WHERE NOT a.paused AND s.state<>'paused' AND s.notification_consent "
                "AND o.state='pending' AND o.created_at>clock_timestamp()-interval '24 hours' "
                "AND c.provider='canvas_extension' AND c.state='connected' "
                "AND c.credential_expires_at>clock_timestamp() AND c.origin=ANY(%s) "
                "AND c.generation=s.generation AND c.scope_revision=s.scope_revision "
                "AND NOT EXISTS (SELECT 1 FROM wrytely_agent.whatsapp_outbound w "
                "WHERE w.course_offer_id=o.id) "
                "ORDER BY o.created_at,o.id LIMIT %s",
                (list(self._canvas_origins), limit),
            ).fetchall()

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
