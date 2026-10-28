"""Fenced delivery state. Never performs network IO or automatically retries dispatch."""

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb

from contracts.delivery import DeliveryClaim, SendAuthorization, WhatsAppStatusEvent
from contracts.models import DeliveryResult
from contracts.templates import TextPayload
from shared.template_policy import select_reply_template


class DeliveryStore:
    def set_communication_preferences(self, user_id, *, consent, timezone, quiet_start, quiet_end):
        ZoneInfo(timezone)
        if type(consent) is not bool or not 0 <= quiet_start <= 23 or not 0 <= quiet_end <= 23:
            raise ValueError("Invalid communication preferences")
        with self.connection() as conn:
            agent = conn.execute(
                "SELECT id FROM wrytely_agent.agents WHERE user_id=%s FOR UPDATE", (user_id,)
            ).fetchone()
            if not agent:
                raise LookupError("Not found")
            conn.execute(
                "INSERT INTO wrytely_agent.communication_preferences "
                "(agent_id,consent,timezone,quiet_start,quiet_end) VALUES (%s,%s,%s,%s,%s) "
                "ON CONFLICT(agent_id) DO UPDATE SET consent=excluded.consent, "
                "timezone=excluded.timezone,quiet_start=excluded.quiet_start,quiet_end=excluded.quiet_end",
                (agent["id"], consent, timezone, quiet_start, quiet_end),
            )

    def record_whatsapp_inbound_time(self, provider_id, sender, event_at):
        """Only call after signed message persistence, using the provider's timestamp.

        Newer receipt time never substitutes for a missing/old signed event time.
        """
        if event_at.tzinfo is None or event_at.utcoffset() is None:
            raise ValueError("Timezone required")
        if event_at > datetime.now(UTC) + timedelta(minutes=5):
            raise ValueError("Future event time")
        with self.connection() as conn:
            row = conn.execute(
                "SELECT i.agent_id,i.received_at FROM wrytely_agent.whatsapp_inbound i "
                "JOIN wrytely_agent.channel_links l ON l.agent_id=i.agent_id "
                "WHERE i.provider_id=%s AND l.phone=%s AND l.linked_at<=i.received_at",
                (provider_id, sender),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE wrytely_agent.channel_links "
                    "SET last_event_at=greatest(last_event_at,%s) "
                    "WHERE agent_id=%s AND phone=%s AND linked_at<=%s",
                    (
                        min(event_at, row["received_at"]),
                        row["agent_id"],
                        sender,
                        row["received_at"],
                    ),
                )

    def claim_whatsapp_delivery(self, worker_id, *, lease_seconds=60):
        if not 1 <= len(worker_id) <= 100 or not 5 <= lease_seconds <= 300:
            raise ValueError("Invalid worker/lease")
        with self.connection() as conn:
            conn.execute(
                "UPDATE wrytely_agent.whatsapp_outbound SET state='unknown', "
                "hold_reason='abandoned_attempt' WHERE state='sending' AND lease_until<=now()"
            )
            row = conn.execute(
                "SELECT * FROM wrytely_agent.whatsapp_outbound "
                "WHERE state IN ('queued','deferred') "
                "AND (retry_at IS NULL OR retry_at<=now()) ORDER BY created_at,id "
                "LIMIT 1 FOR UPDATE SKIP LOCKED"
            ).fetchone()
            if not row:
                return None
            token = uuid4()
            deadline = conn.execute(
                "UPDATE wrytely_agent.whatsapp_outbound SET state='sending',worker_id=%s, "
                "attempt_token=%s,lease_until=now()+(%s*interval '1 second'),dispatch_at=NULL "
                "WHERE id=%s RETURNING lease_until",
                (worker_id, token, lease_seconds, row["id"]),
            ).fetchone()["lease_until"]
            return DeliveryClaim(
                row["id"],
                row["agent_id"],
                row["task_id"],
                row["recipient"],
                row["content"],
                row["link_generation"],
                worker_id,
                token,
                deadline,
            )

    def _delivery_fence(self, conn, claim):
        from shared.db import LeaseLost

        # All control paths lock the agent before its outbound record.
        conn.execute(
            "SELECT id FROM wrytely_agent.agents WHERE id=%s FOR UPDATE", (claim.agent_id,)
        )
        row = conn.execute(
            "SELECT * FROM wrytely_agent.whatsapp_outbound WHERE id=%s AND agent_id=%s "
            "AND task_id=%s AND worker_id=%s AND attempt_token=%s AND lease_until>now() "
            "AND state='sending' FOR UPDATE",
            (claim.action_id, claim.agent_id, claim.task_id, claim.worker_id, claim.attempt_token),
        ).fetchone()
        if not row:
            raise LeaseLost("Delivery attempt no longer owned")
        return row

    def authorize_whatsapp_send(
        self,
        claim,
        *,
        business_id,
        phone_number_id,
        supports_templates=False,
        approved_templates=(),
        reply_template_key=None,
    ):
        if not business_id or not phone_number_id:
            raise ValueError("Configured WhatsApp account required")
        with self.connection() as conn:
            row = self._delivery_fence(conn, claim)
            if row["dispatch_at"] is not None:
                from shared.db import LeaseLost

                raise LeaseLost("Dispatch already authorized")
            agent = conn.execute(
                "SELECT paused FROM wrytely_agent.agents WHERE id=%s", (row["agent_id"],)
            ).fetchone()
            link = conn.execute(
                "SELECT * FROM wrytely_agent.channel_links WHERE agent_id=%s", (row["agent_id"],)
            ).fetchone()
            reason, cancel = None, False
            payload = None
            if (
                not link
                or row["link_generation"] != link["generation"]
                or row["recipient"] != link["phone"]
            ):
                reason, cancel = "link_changed", True
            elif agent["paused"]:
                reason = "paused"
            valid = conn.execute(
                "SELECT t.status,t.kind,r.status AS responsibility_status, "
                "coalesce(t.memory_revision,0)=r.memory_revision AS current "
                "FROM wrytely_agent.tasks t "
                "LEFT JOIN wrytely_agent.responsibilities r ON r.id=t.responsibility_id "
                "AND r.agent_id=t.agent_id WHERE t.id=%s AND t.agent_id=%s",
                (row["task_id"], row["agent_id"]),
            ).fetchone()
            if not valid or valid["status"] != "done" or valid["kind"] != "reply":
                reason, cancel = "result_not_deliverable", True
            prefs = conn.execute(
                "SELECT * FROM wrytely_agent.communication_preferences WHERE agent_id=%s",
                (row["agent_id"],),
            ).fetchone()
            now = datetime.now(UTC)
            if reason is None:
                if not prefs:
                    reason = "preferences_missing"
                elif not prefs["consent"]:
                    reason = "consent_missing"
                else:
                    hour = now.astimezone(ZoneInfo(prefs["timezone"])).hour
                    start, end = prefs["quiet_start"], prefs["quiet_end"]
                    quiet = start <= hour < end if start < end else hour >= start or hour < end
                    if start != end and quiet:
                        reason = "quiet_hours"
                    elif link["last_event_at"] is None:
                        reason = "inbound_time_unknown"
                    elif now - link["last_event_at"] >= timedelta(hours=24):
                        if supports_templates is not True:
                            reason = "approved_template_required"
                        else:
                            payload, reason = select_reply_template(
                                approved_templates,
                                reply_template_key,
                                business_id=business_id,
                                phone_number_id=phone_number_id,
                                reply_text=row["content"],
                            )
                    elif not 0 < len(row["content"].strip()) <= 4096:
                        reason = "text_payload_limit"
            if reason:
                retry = None if cancel else now + timedelta(minutes=5)
                conn.execute(
                    "UPDATE wrytely_agent.whatsapp_outbound "
                    "SET state=%s,hold_reason=%s,retry_at=%s "
                    "WHERE id=%s",
                    ("cancelled" if cancel else "deferred", reason, retry, row["id"]),
                )
                return SendAuthorization("cancelled" if cancel else "held", reason, retry)
            conn.execute(
                "UPDATE wrytely_agent.whatsapp_outbound SET dispatch_at=now(),business_id=%s, "
                "phone_number_id=%s,hold_reason=NULL,retry_at=NULL WHERE id=%s",
                (business_id, phone_number_id, row["id"]),
            )
            payload = payload or TextPayload(text=row["content"])
            conn.execute(
                "INSERT INTO wrytely_agent.episode_events(task_id,attempt,kind,data) "
                "VALUES (%s,0,'delivery_authorized',%s)",
                (
                    row["task_id"],
                    Jsonb(
                        {
                            "action_id": str(row["id"]),
                            "attempt_token": str(row["attempt_token"]),
                            "payload": payload.model_dump(mode="json"),
                        }
                    ),
                ),
            )
            return SendAuthorization(
                "permitted",
                recipient=row["recipient"],
                text=payload.text if isinstance(payload, TextPayload) else None,
                payload=payload,
            )

    def record_whatsapp_result(self, claim, result: DeliveryResult):
        if result.internal_id != claim.action_id or result.state not in (
            "accepted",
            "failed",
            "unknown",
        ):
            raise ValueError("Invalid send evidence")
        if result.state == "accepted" and not result.provider_ref:
            raise ValueError("Accepted requires provider reference")
        with self.connection() as conn:
            if result.provider_ref:
                conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s,1))", (result.provider_ref,)
                )
            row = self._delivery_fence(conn, claim)
            if row["dispatch_at"] is None:
                raise ValueError("No dispatch authorization")
            conn.execute(
                "UPDATE wrytely_agent.whatsapp_outbound SET state=%s,provider_ref=%s WHERE id=%s",
                (result.state, result.provider_ref, row["id"]),
            )
            if result.provider_ref:
                self._reconcile_delivery_events(conn, row["id"])

    def _reconcile_delivery_events(self, conn, action_id):
        row = conn.execute(
            "SELECT * FROM wrytely_agent.whatsapp_outbound WHERE id=%s FOR UPDATE", (action_id,)
        ).fetchone()
        events = conn.execute(
            "UPDATE wrytely_agent.whatsapp_status_events SET action_id=%s "
            "WHERE provider_ref=%s AND business_id=%s AND phone_number_id=%s AND recipient=%s "
            "AND received_at>=now()-interval '7 days' RETURNING status",
            (
                action_id,
                row["provider_ref"],
                row["business_id"],
                row["phone_number_id"],
                row["recipient"],
            ),
        ).fetchall()
        statuses = {e["status"] for e in events}
        state = row["state"]
        if "delivered" in statuses or "read" in statuses:
            state = "delivered"
        elif state != "delivered":
            if "failed" in statuses:
                state = "failed"
            elif "sent" in statuses and state not in ("failed", "cancelled"):
                state = "accepted"
        conn.execute(
            "UPDATE wrytely_agent.whatsapp_outbound SET state=%s WHERE id=%s", (state, action_id)
        )

    def record_whatsapp_status(self, event: WhatsAppStatusEvent, *, business_id, phone_number_id):
        if event.business_id != business_id or event.phone_number_id != phone_number_id:
            raise ValueError("Wrong configured account")
        if event.event_at > datetime.now(UTC) + timedelta(minutes=5):
            raise ValueError("Future status time")
        digest = hashlib.sha256(event.model_dump_json().encode()).hexdigest()
        with self.connection() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(20417352)")
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,1))", (event.provider_ref,)
            )
            # Bound orphan retention and storage before insertion; expired callbacks
            # cannot establish a current delivery result.
            conn.execute(
                "DELETE FROM wrytely_agent.whatsapp_status_events WHERE action_id IS NULL "
                "AND received_at<now()-interval '7 days'"
            )
            row = conn.execute(
                "SELECT id FROM wrytely_agent.whatsapp_outbound WHERE provider_ref=%s "
                "AND business_id=%s AND phone_number_id=%s AND recipient=%s FOR UPDATE",
                (event.provider_ref, business_id, phone_number_id, event.recipient),
            ).fetchone()
            count = conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.whatsapp_status_events "
                "WHERE action_id IS NULL"
            ).fetchone()["n"]
            if (
                row is None
                and count >= 10000
                and not conn.execute(
                    "SELECT 1 FROM wrytely_agent.whatsapp_status_events WHERE event_hash=%s",
                    (digest,),
                ).fetchone()
            ):
                raise ValueError("Unmatched status capacity reached")
            conn.execute(
                "INSERT INTO wrytely_agent.whatsapp_status_events "
                "(event_hash,business_id,phone_number_id,provider_ref,recipient,status,event_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (
                    digest,
                    event.business_id,
                    event.phone_number_id,
                    event.provider_ref,
                    event.recipient,
                    event.status,
                    event.event_at,
                ),
            )
            if row:
                self._reconcile_delivery_events(conn, row["id"])
            return {"matched": bool(row)}
