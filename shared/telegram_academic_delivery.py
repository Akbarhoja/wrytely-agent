"""Academic Telegram intents reuse the original outbox and checked artifact files."""

import hashlib
from datetime import timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from contracts.delivery import ArtifactDeliveryFile
from contracts.telegram import positive_id
from shared.artifact_delivery import descriptor
from shared.artifact_document import MIME
from shared.canvas_reads import SourceRefreshRequired, _uuid


def offer_text(offer):
    return (
        f"{offer['message']}\n\nTo delegate this work, reply:\n/accept {offer['id']}"
        f"\nTo decline:\n/decline {offer['id']}"
    )


def command_text(receipt):
    if receipt.get("state") != "applied":
        return "That request could not be applied. Check your current work in Wrytely."
    return {
        "accept_offer": "Accepted. Your work is queued; this does not mean a draft is complete.",
        "decline_offer": "Offer declined. No work was started by this request.",
        "revise_artifact": "Revision requested. Your previous checked version is retained.",
        "send_artifact": (
            "File request recorded. Check delivery status; this does not confirm a new send."
        ),
    }[receipt["kind"]]


class TelegramAcademicDeliveryStore:
    def _telegram_academic_link(self, conn, user, bot_id):
        positive_id(bot_id)
        agent = self._telegram_owner(conn, user)
        link = conn.execute(
            "SELECT * FROM wrytely_agent.telegram_links WHERE agent_id=%s AND bot_id=%s",
            (agent["id"], bot_id),
        ).fetchone()
        if not link or not link["consent"] or agent["paused"]:
            raise ValueError("Telegram consent required")
        return agent, link

    def _insert_telegram_academic(
        self,
        conn,
        agent,
        link,
        *,
        key,
        kind,
        content,
        supervision_id=None,
        offer_id=None,
        artifact_file_id=None,
        command_update_id=None,
    ):
        if not isinstance(content, str) or not content.strip() or len(content) > 24000:
            raise ValueError("Telegram content limit")
        conn.execute(
            "INSERT INTO wrytely_agent.telegram_outbound "
            "(id,agent_id,bot_id,chat_id,generation,intent_key,kind,content,"
            "supervision_id,offer_id,artifact_file_id,command_update_id) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT(agent_id,intent_key) DO NOTHING",
            (
                uuid4(),
                agent["id"],
                link["bot_id"],
                link["chat_id"],
                link["generation"],
                key,
                kind,
                content,
                supervision_id,
                offer_id,
                artifact_file_id,
                command_update_id,
            ),
        )
        return conn.execute(
            "SELECT id,state FROM wrytely_agent.telegram_outbound "
            "WHERE agent_id=%s AND intent_key=%s",
            (agent["id"], key),
        ).fetchone()

    def queue_telegram_offer(self, user, bot_id, supervision_id, offer_id):
        with self._atomic_connection() as conn:
            agent, link = self._telegram_academic_link(conn, user, bot_id)
            if not link["notification_consent"]:
                raise ValueError("Telegram proactive consent required")
            offer, reason, _ = self._current_course_offer(conn, user, supervision_id, offer_id)
            if reason:
                raise SourceRefreshRequired()
            prior = conn.execute(
                "SELECT id,state FROM wrytely_agent.telegram_outbound WHERE agent_id=%s "
                "AND offer_id=%s ORDER BY created_at LIMIT 1",
                (agent["id"], offer["id"]),
            ).fetchone()
            if prior:
                return prior
            return self._insert_telegram_academic(
                conn,
                agent,
                link,
                key=f"offer:{offer['id']}",
                kind="offer",
                content=offer_text(offer),
                supervision_id=_uuid(supervision_id),
                offer_id=offer["id"],
            )

    def enqueue_telegram_artifact_delivery(self, user, bot_id, artifact_id):
        with self._atomic_connection() as conn:
            agent, link = self._telegram_academic_link(conn, user, bot_id)
            artifact, check, content = self._checked_artifact_file(conn, user, artifact_id)
            conn.execute(
                "INSERT INTO wrytely_agent.artifact_delivery_files "
                "(id,agent_id,artifact_id,check_id,filename,media_type,sha256,byte_length,content) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT(agent_id,artifact_id) DO NOTHING",
                (
                    uuid4(),
                    agent["id"],
                    artifact["id"],
                    check["id"],
                    f"wrytely-{artifact['id']}.docx",
                    MIME,
                    hashlib.sha256(content).hexdigest(),
                    len(content),
                    content,
                ),
            )
            file = conn.execute(
                "SELECT id FROM wrytely_agent.artifact_delivery_files WHERE agent_id=%s "
                "AND artifact_id=%s",
                (agent["id"], artifact["id"]),
            ).fetchone()
            self._artifact_delivery_file(
                conn, {"agent_id": agent["id"], "artifact_file_id": file["id"]}
            )
            prior = conn.execute(
                "SELECT id,state FROM wrytely_agent.telegram_outbound WHERE agent_id=%s "
                "AND artifact_file_id=%s ORDER BY created_at LIMIT 1",
                (agent["id"], file["id"]),
            ).fetchone()
            if prior:
                return prior
            return self._insert_telegram_academic(
                conn,
                agent,
                link,
                key=f"artifact:{file['id']}",
                kind="artifact",
                content="Your checked Wrytely draft",
                artifact_file_id=file["id"],
            )

    def queue_telegram_academic_actions(self, bot_id, *, limit=20):
        """Bounded recovery hints; individual queue methods recheck current authority."""
        positive_id(bot_id)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Invalid recovery limit")
        with self.connection() as conn:
            offers = conn.execute(
                "SELECT a.user_id,o.supervision_id,o.id FROM wrytely_agent.course_offers o "
                "JOIN wrytely_agent.agents a ON a.id=o.agent_id "
                "JOIN wrytely_agent.telegram_links l ON l.agent_id=a.id "
                "JOIN wrytely_agent.course_supervisions s ON s.id=o.supervision_id "
                "WHERE l.bot_id=%s AND l.consent AND l.notification_consent AND NOT a.paused "
                "AND s.notification_consent AND s.state<>'paused' AND o.state='pending' "
                "AND o.created_at>clock_timestamp()-interval '24 hours' "
                "AND NOT EXISTS (SELECT 1 FROM wrytely_agent.telegram_outbound d "
                "WHERE d.agent_id=o.agent_id AND d.offer_id=o.id) "
                "ORDER BY o.created_at,o.id LIMIT %s",
                (bot_id, limit),
            ).fetchall()
            receipts = conn.execute(
                "SELECT a.user_id,i.update_id FROM wrytely_agent.telegram_inbound i "
                "JOIN wrytely_agent.agents a ON a.id=i.agent_id "
                "JOIN wrytely_agent.telegram_links l ON l.agent_id=a.id AND l.bot_id=i.bot_id "
                "AND l.generation=i.generation WHERE i.bot_id=%s AND l.consent AND NOT a.paused "
                "AND i.command_result IS NOT NULL "
                "AND i.received_at>clock_timestamp()-interval '24 hours' "
                "AND NOT EXISTS (SELECT 1 FROM wrytely_agent.telegram_outbound d "
                "WHERE d.bot_id=i.bot_id AND d.command_update_id=i.update_id) "
                "ORDER BY i.received_at,i.update_id LIMIT %s",
                (bot_id, limit),
            ).fetchall()
        queued = 0
        for offer in offers:
            try:
                self.queue_telegram_offer(
                    offer["user_id"], bot_id, offer["supervision_id"], offer["id"]
                )
                queued += 1
            except (ValueError, LookupError, SourceRefreshRequired):
                continue
        for hint in receipts:
            with self._atomic_connection() as conn:
                try:
                    agent, link = self._telegram_academic_link(conn, hint["user_id"], bot_id)
                except (ValueError, LookupError):
                    continue
                receipt = conn.execute(
                    "SELECT command_result FROM wrytely_agent.telegram_inbound "
                    "WHERE bot_id=%s AND update_id=%s AND agent_id=%s AND generation=%s "
                    "AND received_at>clock_timestamp()-interval '24 hours'",
                    (bot_id, hint["update_id"], agent["id"], link["generation"]),
                ).fetchone()
                if not receipt or not receipt["command_result"]:
                    continue
                self._insert_telegram_academic(
                    conn,
                    agent,
                    link,
                    key=f"command:{bot_id}:{hint['update_id']}",
                    kind="command",
                    content=command_text(receipt["command_result"]),
                    command_update_id=hint["update_id"],
                )
                queued += 1
        return queued

    def _telegram_academic_authority(self, conn, row, user, link):
        payload = None
        if row["kind"] == "offer":
            if not link["notification_consent"]:
                return "notification_consent_missing", None
            offer, reason, _ = self._current_course_offer(
                conn, user, row["supervision_id"], row["offer_id"]
            )
            if reason or offer_text(offer) != row["content"]:
                return "offer_changed_or_unavailable", None
        elif row["kind"] == "artifact":
            file = self._artifact_delivery_file(conn, row)
            payload = descriptor(file)
            if row["content"] != "Your checked Wrytely draft":
                return "artifact_content_changed", None
        elif row["kind"] == "command":
            receipt = conn.execute(
                "SELECT command_result FROM wrytely_agent.telegram_inbound WHERE bot_id=%s "
                "AND update_id=%s AND agent_id=%s AND generation=%s",
                (row["bot_id"], row["command_update_id"], row["agent_id"], row["generation"]),
            ).fetchone()
            if not receipt or command_text(receipt["command_result"]) != row["content"]:
                return "command_receipt_changed", None
        else:
            return "unsupported_delivery_kind", None
        return None, payload

    def read_telegram_artifact_delivery(self, claim):
        """Only after a consumed one-use permit, before IO; never a public file read."""
        from shared.db import LeaseLost

        with self._atomic_connection() as conn:
            agent, link = self._telegram_academic_link(conn, claim.user_id, claim.bot_id)
            row = conn.execute(
                "SELECT * FROM wrytely_agent.telegram_outbound WHERE agent_id=%s AND id=%s "
                "FOR UPDATE",
                (agent["id"], claim.action_id),
            ).fetchone()
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            if (
                not row
                or row["state"] != "sending"
                or row["attempt_token"] != claim.attempt_token
                or row["lease_until"] <= now
                or row["created_at"] + timedelta(hours=24) <= now
                or claim.kind != "artifact"
                or claim.kind != row["kind"]
                or claim.content != row["content"]
                or claim.artifact_file_id != row["artifact_file_id"]
                or (claim.bot_id, claim.chat_id, claim.generation)
                != (row["bot_id"], row["chat_id"], row["generation"])
                or (link["chat_id"], link["generation"]) != (row["chat_id"], row["generation"])
            ):
                raise LeaseLost("Telegram file permit unavailable")
            hour = now.astimezone(ZoneInfo(link["timezone"])).hour
            start, end = link["quiet_start"], link["quiet_end"]
            if start != end and (
                start <= hour < end if start < end else hour >= start or hour < end
            ):
                raise LeaseLost("Telegram file controls changed")
            file = self._artifact_delivery_file(conn, row)
            return ArtifactDeliveryFile(descriptor(file), bytes(file["content"]))
