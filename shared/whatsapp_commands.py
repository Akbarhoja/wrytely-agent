"""Atomic explicit command execution using the original inbound and existing Store.

No raw-phone owner resolver, generic reasoning task, external send or model call.
Caller MUST authenticate exact raw webhook bytes and provider account before parsing.
"""

import hashlib
import json
from datetime import UTC, timedelta

from psycopg.types.json import Jsonb

from contracts.whatsapp_commands import WhatsAppCommandEnvelope
from shared.academic_reads import student_json
from shared.canvas_reads import SourceRefreshRequired


class WhatsAppCommandRejected(ValueError):
    """Safe permanent envelope/replay rejection; not a provider retry instruction."""


class WhatsAppCommandStore:
    @staticmethod
    def _command_target(conn, agent, link, envelope):
        target = envelope.command.target_id
        if envelope.reply_to_provider_ref is not None:
            row = conn.execute(
                "SELECT w.course_offer_id,w.artifact_file_id,f.artifact_id "
                "FROM wrytely_agent.whatsapp_outbound w "
                "LEFT JOIN wrytely_agent.artifact_delivery_files f "
                "ON f.id=w.artifact_file_id AND f.agent_id=w.agent_id "
                "WHERE w.agent_id=%s AND w.provider_ref=%s AND w.business_id=%s "
                "AND w.phone_number_id=%s AND w.recipient=%s AND w.link_generation=%s "
                "AND w.dispatch_at IS NOT NULL AND w.dispatch_at<=%s+interval '5 minutes' "
                "AND w.state IN ('accepted','delivered','unknown')",
                (
                    agent["id"],
                    envelope.reply_to_provider_ref,
                    envelope.business_id,
                    envelope.phone_number_id,
                    envelope.sender,
                    link["generation"],
                    envelope.event_at,
                ),
            ).fetchone()
            if not row:
                raise WhatsAppCommandRejected("command_context_unavailable")
            resolved = (
                row["course_offer_id"]
                if envelope.command.kind in ("accept_offer", "decline_offer")
                else row["artifact_id"]
            )
            if (
                resolved is None
                and row["course_offer_id"] is not None
                and envelope.command.kind in ("send_artifact", "revise_artifact")
            ):
                # A student can request the first file by replying to the exact
                # accepted offer, without visiting the website to find an artifact ID.
                # Never guess the latest artifact across the student's other work.
                artifact = conn.execute(
                    "SELECT f.id FROM wrytely_agent.course_offers o "
                    "JOIN wrytely_agent.responsibilities r ON r.agent_id=o.agent_id "
                    "AND r.request_key='course-offer:'||o.id::text "
                    "JOIN wrytely_agent.artifacts f ON f.agent_id=r.agent_id "
                    "AND f.responsibility_id=r.id AND f.evidence_schema=2 "
                    "WHERE o.agent_id=%s AND o.id=%s AND o.state='accepted' "
                    "AND (%s::uuid IS NULL OR f.id=%s) "
                    "AND NOT EXISTS (SELECT 1 FROM wrytely_agent.tasks t "
                    "WHERE t.agent_id=r.agent_id AND t.responsibility_id=r.id "
                    "AND t.kind='academic' AND t.status IN ('ready','running')) "
                    "ORDER BY f.created_at DESC,f.id DESC LIMIT 1",
                    (agent["id"], row["course_offer_id"], target, target),
                ).fetchone()
                resolved = artifact["id"] if artifact else None
            if resolved is None or (target is not None and target != resolved):
                raise WhatsAppCommandRejected("command_context_unavailable")
            target = resolved
        if target is None:
            raise WhatsAppCommandRejected("command_context_unavailable")
        table = (
            "course_offers"
            if envelope.command.kind in ("accept_offer", "decline_offer")
            else "artifacts"
        )
        # Table name is chosen only from the literal discriminator above.
        if not conn.execute(
            f"SELECT 1 FROM wrytely_agent.{table} WHERE agent_id=%s AND id=%s",
            (agent["id"], target),
        ).fetchone():
            raise WhatsAppCommandRejected("command_context_unavailable")
        return target

    def _apply_whatsapp_command(self, conn, user, agent, link, envelope):
        from shared.db import QueueFull, RequestConflict

        kind = envelope.command.kind
        target = None
        try:
            # Expected business rejection must roll back partial acceptance/task/file
            # changes but retain its inbound receipt. Unexpected DB errors roll back
            # the entire outer command so signed provider replay can recover it.
            with conn.transaction():
                if agent["paused"]:
                    raise WhatsAppCommandRejected("agent_paused")
                target = self._command_target(conn, agent, link, envelope)
                if kind in ("accept_offer", "decline_offer"):
                    offer = conn.execute(
                        "SELECT supervision_id FROM wrytely_agent.course_offers "
                        "WHERE agent_id=%s AND id=%s",
                        (agent["id"], target),
                    ).fetchone()
                    result = self.decide_course_offer(
                        user, offer["supervision_id"], target, accept=kind == "accept_offer"
                    )
                    if result["draft_request"] is not None:
                        duty = self.create_canvas_draft_responsibility(
                            user, **result["draft_request"]
                        )
                        result = {"state": "accepted", "responsibility_id": str(duty["id"])}
                    else:
                        result = {"state": "declined"}
                elif kind == "revise_artifact":
                    key = "whatsapp:" + hashlib.sha256(envelope.provider_id.encode()).hexdigest()
                    result = self.request_private_artifact_revision(
                        user, target, envelope.command.instructions, key
                    )
                else:
                    result = self.enqueue_checked_artifact_delivery(user, target)
        except WhatsAppCommandRejected as exc:
            return {"state": "rejected", "kind": kind, "reason": str(exc)}
        except SourceRefreshRequired:
            return {"state": "rejected", "kind": kind, "reason": "source_refresh_required"}
        except (LookupError, ValueError, QueueFull, RequestConflict):
            return {"state": "rejected", "kind": kind, "reason": "command_unavailable"}
        return student_json(
            {"state": "applied", "kind": kind, "target_id": str(target), "result": result}
        )

    def execute_whatsapp_command(self, envelope, *, business_id, phone_number_id):
        """Trusted post-signature adapter only. Never expose this as a student RPC.

        Current linked owner is selected from stored linkage; message text cannot
        supply it. An exact repeated provider event returns a historical receipt,
        never repeats a task/offer mutation or grants another delivery attempt.
        """
        envelope = WhatsAppCommandEnvelope.model_validate(envelope)
        if (
            not business_id
            or not phone_number_id
            or envelope.business_id != business_id
            or envelope.phone_number_id != phone_number_id
        ):
            raise WhatsAppCommandRejected("command_account_mismatch")
        body = envelope.model_dump(mode="json")
        body["event_at"] = envelope.event_at.astimezone(UTC).isoformat()
        fingerprint = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        with self._atomic_connection() as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,3))", (envelope.provider_id,)
            )
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (envelope.sender,))
            agent = conn.execute(
                "SELECT a.* FROM wrytely_agent.agents a JOIN wrytely_agent.channel_links l "
                "ON l.agent_id=a.id WHERE l.phone=%s FOR UPDATE OF a",
                (envelope.sender,),
            ).fetchone()
            if not agent:
                return {"state": "ignored"}
            link = conn.execute(
                "SELECT * FROM wrytely_agent.channel_links WHERE agent_id=%s AND phone=%s",
                (agent["id"], envelope.sender),
            ).fetchone()
            if not link:
                return {"state": "ignored"}
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            if (
                envelope.event_at > now + timedelta(minutes=5)
                or envelope.event_at < now - timedelta(hours=24)
                or envelope.event_at < link["linked_at"].replace(microsecond=0)
            ):
                raise WhatsAppCommandRejected("command_event_expired")
            prior = conn.execute(
                "SELECT * FROM wrytely_agent.whatsapp_inbound WHERE provider_id=%s",
                (envelope.provider_id,),
            ).fetchone()
            if prior:
                if (
                    prior["agent_id"] != agent["id"]
                    or prior["command_digest"] != fingerprint
                    or prior["command_link_generation"] != link["generation"]
                ):
                    raise WhatsAppCommandRejected("command_replay_conflict")
                return {**prior["command_result"], "replayed": True}
            conn.execute(
                "INSERT INTO wrytely_agent.whatsapp_inbound "
                "(provider_id,agent_id,command_body,command_digest,"
                "command_link_generation,command_result) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (
                    envelope.provider_id,
                    agent["id"],
                    Jsonb(body),
                    fingerprint,
                    link["generation"],
                    Jsonb({"state": "processing"}),
                ),
            )
            result = self._apply_whatsapp_command(conn, agent["user_id"], agent, link, envelope)
            conn.execute(
                "UPDATE wrytely_agent.whatsapp_inbound SET command_result=%s WHERE provider_id=%s",
                (Jsonb(result), envelope.provider_id),
            )
            conn.execute(
                "UPDATE wrytely_agent.channel_links SET last_inbound_at=clock_timestamp(),"
                "last_event_at=greatest(last_event_at,%s) WHERE agent_id=%s AND generation=%s",
                (min(envelope.event_at, now), agent["id"], link["generation"]),
            )
            return {**result, "replayed": False}
