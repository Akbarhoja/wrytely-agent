"""Telegram transport persistence on the original Store and task queue."""

import hashlib
import json
import re
import secrets
from datetime import timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from contracts.telegram import TelegramClaim, TelegramPermit, positive_id
from shared.canvas_reads import SourceRefreshRequired, _uuid


def preparation_text(record):
    parts = ["Wrytely preparation checklist", record["title"], record["notice"]]
    for item in record["excerpts"]:
        label = "Review original" if item["kind"] == "review" else "Your action from the original"
        parts.append(f"{label}:\n{item['quote']}")
    parts.extend("Question for you: " + q for q in record["questions"])
    parts.append("Source limits (not a claim of complete course coverage):")
    for p in record["evidence"]:
        parts.append(
            f"{p['object_id']}: {p['coverage']}; resource {p['resource_coverage']}; "
            f"missing: {', '.join(p['missing']) or 'none reported'}; "
            f"unread continuation: {p['unread_continuation']}"
        )
    content = "\n\n".join(parts)
    if len(content) > 24000:
        raise ValueError("Preparation transport limit")
    return content


class TelegramStore:
    @staticmethod
    def _telegram_owner(conn, user):
        row = conn.execute(
            "SELECT * FROM wrytely_agent.agents WHERE user_id=%s FOR UPDATE", (user,)
        ).fetchone()
        if not row:
            raise LookupError("Complete setup first")
        return row

    def create_telegram_challenge(self, verified_user, bot_id):
        positive_id(bot_id)
        token = secrets.token_urlsafe(32)
        with self.connection() as conn:
            agent = self._telegram_owner(conn, verified_user)
            if conn.execute(
                "SELECT 1 FROM wrytely_agent.telegram_links WHERE agent_id=%s", (agent["id"],)
            ).fetchone():
                raise ValueError("Unlink existing Telegram first")
            row = conn.execute(
                "INSERT INTO "
                "wrytely_agent.telegram_challenges(agent_id,bot_id,token_hash,expires_at) "
                "VALUES (%s,%s,%s,clock_timestamp()+interval '10 minutes') "
                "ON CONFLICT(agent_id) DO UPDATE SET bot_id=excluded.bot_id,"
                "token_hash=excluded.token_hash,expires_at=excluded.expires_at RETURNING "
                "expires_at",
                (agent["id"], bot_id, hashlib.sha256(token.encode()).hexdigest()),
            ).fetchone()
            return {"message": "/start " + token, "expires_at": row["expires_at"]}

    def telegram_connection(self, verified_user, bot_id):
        positive_id(bot_id)
        with self.connection() as conn:
            agent = self._telegram_owner(conn, verified_user)
            row = conn.execute(
                "SELECT consent,notification_consent,timezone,quiet_start,quiet_end,generation "
                "FROM wrytely_agent.telegram_links WHERE agent_id=%s AND bot_id=%s",
                (agent["id"], bot_id),
            ).fetchone()
            generation = row.pop("generation") if row else None
            delivery = (
                conn.execute(
                    "SELECT state,reason,created_at FROM wrytely_agent.telegram_outbound "
                    "WHERE agent_id=%s AND bot_id=%s AND generation=%s "
                    "ORDER BY created_at DESC LIMIT 1",
                    (agent["id"], bot_id, generation),
                ).fetchone()
                if row
                else None
            )
            return {"linked": row is not None, "preferences": row, "latest_delivery": delivery}

    def pending_telegram_preparations(self, bot_id, *, limit=20):
        """Internal recovery hints only. Queueing/dispatch independently recheck all authority."""
        positive_id(bot_id)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Invalid preparation recovery limit")
        with self.connection() as conn:
            return conn.execute(
                "SELECT a.user_id,s.id AS supervision_id,p->>'id' AS preparation_id "
                "FROM wrytely_agent.course_supervisions s JOIN wrytely_agent.agents a "
                "ON a.id=s.agent_id JOIN wrytely_agent.telegram_links l ON l.agent_id=a.id "
                "CROSS JOIN LATERAL jsonb_array_elements(s.preparations) p "
                "WHERE l.bot_id=%s AND l.consent AND l.notification_consent AND NOT a.paused "
                "AND s.state<>'paused' AND (p->>'created_at')::timestamptz>"
                "clock_timestamp()-interval '24 hours' AND NOT EXISTS "
                "(SELECT 1 FROM wrytely_agent.telegram_outbound o WHERE o.agent_id=a.id "
                "AND o.intent_key='preparation:'||(p->>'id')||':'||l.generation::text) "
                "ORDER BY p->>'created_at',s.id LIMIT %s",
                (bot_id, limit),
            ).fetchall()

    def set_telegram_preferences(
        self,
        verified_user,
        bot_id,
        *,
        consent,
        notification_consent,
        timezone,
        quiet_start,
        quiet_end,
    ):
        positive_id(bot_id)
        ZoneInfo(timezone)
        if (
            type(consent) is not bool
            or type(notification_consent) is not bool
            or any(type(h) is not int or not 0 <= h <= 23 for h in (quiet_start, quiet_end))
        ):
            raise ValueError("Invalid Telegram preferences")
        with self.connection() as conn:
            agent = self._telegram_owner(conn, verified_user)
            row = conn.execute(
                "UPDATE wrytely_agent.telegram_links SET consent=%s,notification_consent=%s,"
                "timezone=%s,quiet_start=%s,quiet_end=%s WHERE agent_id=%s AND bot_id=%s "
                "RETURNING consent,notification_consent,timezone,quiet_start,quiet_end",
                (
                    consent,
                    notification_consent,
                    timezone,
                    quiet_start,
                    quiet_end,
                    agent["id"],
                    bot_id,
                ),
            ).fetchone()
            if not row:
                raise LookupError("Not linked")
            return row

    def unlink_telegram(self, verified_user, bot_id):
        positive_id(bot_id)
        with self.connection() as conn:
            agent = self._telegram_owner(conn, verified_user)
            conn.execute(
                "DELETE FROM wrytely_agent.telegram_links WHERE agent_id=%s AND bot_id=%s",
                (agent["id"], bot_id),
            )
            conn.execute(
                "DELETE FROM wrytely_agent.telegram_challenges WHERE agent_id=%s AND bot_id=%s",
                (agent["id"], bot_id),
            )
            conn.execute(
                "UPDATE wrytely_agent.telegram_outbound SET state='cancelled',reason='unlinked' "
                "WHERE agent_id=%s AND bot_id=%s AND state IN ('queued','claimed')",
                (agent["id"], bot_id),
            )

    def ingest_telegram(self, bot_id, event):
        """Trusted authenticated parser only. Pairing tokens never enter model history."""
        from shared.db import RequestConflict

        positive_id(bot_id)
        positive_id(event.chat_id)
        positive_id(event.message_id)
        if (
            type(event.update_id) is not int
            or not 0 <= event.update_id < 2**63
            or not isinstance(event.text, str)
            or not event.text.strip()
            or len(event.text) > 12000
            or event.event_at.tzinfo is None
        ):
            raise ValueError("Invalid trusted Telegram envelope")
        digest = hashlib.sha256(
            json.dumps(
                [event.chat_id, event.message_id, event.event_at.isoformat(), event.text]
            ).encode()
        ).hexdigest()
        with self._atomic_connection() as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"telegram-update:{bot_id}:{event.update_id}",),
            )
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"telegram-chat:{bot_id}:{event.chat_id}",),
            )
            prior = conn.execute(
                "SELECT digest FROM wrytely_agent.telegram_inbound WHERE bot_id=%s AND "
                "update_id=%s",
                (bot_id, event.update_id),
            ).fetchone()
            if prior:
                if prior["digest"] != digest:
                    raise RequestConflict("Telegram update identity reused")
                return "duplicate"
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            if not now - timedelta(hours=24) <= event.event_at <= now + timedelta(minutes=5):
                raise ValueError("Telegram update outside accepted age")
            outcome, agent_id, generation, task_id = "ignored", None, None, None
            if event.text.startswith("/start "):
                token = event.text[7:]
                if re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
                    challenge = conn.execute(
                        "SELECT a.id FROM wrytely_agent.agents a JOIN "
                        "wrytely_agent.telegram_challenges c ON c.agent_id=a.id "
                        "WHERE c.bot_id=%s AND c.token_hash=%s AND c.expires_at>clock_timestamp() "
                        "FOR UPDATE OF a",
                        (bot_id, hashlib.sha256(token.encode()).hexdigest()),
                    ).fetchone()
                    if (
                        challenge
                        and not conn.execute(
                            "SELECT 1 FROM wrytely_agent.telegram_links "
                            "WHERE agent_id=%s OR (bot_id=%s AND chat_id=%s)",
                            (challenge["id"], bot_id, event.chat_id),
                        ).fetchone()
                    ):
                        deleted = conn.execute(
                            "DELETE FROM wrytely_agent.telegram_challenges WHERE agent_id=%s "
                            "AND bot_id=%s AND token_hash=%s AND expires_at>clock_timestamp() "
                            "RETURNING agent_id",
                            (challenge["id"], bot_id, hashlib.sha256(token.encode()).hexdigest()),
                        ).fetchone()
                        if deleted:
                            agent_id, generation, outcome = challenge["id"], uuid4(), "linked"
                            conn.execute(
                                "INSERT INTO wrytely_agent.telegram_links "
                                "(agent_id,bot_id,chat_id,generation,linking_update_id) "
                                "VALUES (%s,%s,%s,%s,%s)",
                                (agent_id, bot_id, event.chat_id, generation, event.update_id),
                            )
            else:
                owner = conn.execute(
                    "SELECT a.* FROM wrytely_agent.agents a JOIN wrytely_agent.telegram_links l "
                    "ON l.agent_id=a.id WHERE l.bot_id=%s AND l.chat_id=%s FOR UPDATE OF a",
                    (bot_id, event.chat_id),
                ).fetchone()
                link = (
                    conn.execute(
                        "SELECT * FROM wrytely_agent.telegram_links WHERE bot_id=%s AND chat_id=%s",
                        (bot_id, event.chat_id),
                    ).fetchone()
                    if owner
                    else None
                )
                if link:
                    agent_id, generation = owner["id"], link["generation"]
                    fresh_link = event.event_at >= link["linked_at"].replace(microsecond=0) and (
                        event.event_at > link["linked_at"]
                        or event.update_id > link["linking_update_id"]
                    )
                    if event.text == "/stop" and fresh_link:
                        self.set_paused(owner["user_id"], True)
                        conn.execute(
                            "UPDATE wrytely_agent.telegram_links SET consent=false,"
                            "notification_consent=false WHERE agent_id=%s",
                            (agent_id,),
                        )
                        conn.execute(
                            "UPDATE wrytely_agent.telegram_outbound SET state='cancelled',"
                            "reason='stopped' WHERE agent_id=%s AND state IN ('queued','claimed')",
                            (agent_id,),
                        )
                        outcome = "stopped"
                    elif (
                        fresh_link
                        and not owner["paused"]
                        and link["consent"]
                        and not event.text.startswith("/")
                    ):
                        task = self.enqueue(
                            owner["user_id"], event.text, f"telegram:{bot_id}:{event.update_id}"
                        )
                        task_id, outcome = task["task_id"], "queued"
            conn.execute(
                "INSERT INTO wrytely_agent.telegram_inbound "
                "(bot_id,update_id,agent_id,generation,digest,outcome,task_id) VALUES "
                "(%s,%s,%s,%s,%s,%s,%s)",
                (bot_id, event.update_id, agent_id, generation, digest, outcome, task_id),
            )
            return outcome

    def queue_telegram_replies(self, bot_id, *, limit=20):
        """Recover completed replies from the existing task journal; no second model call."""
        positive_id(bot_id)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Invalid recovery limit")
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT a.user_id,t.id FROM wrytely_agent.telegram_inbound i "
                "JOIN wrytely_agent.tasks t ON t.id=i.task_id AND t.agent_id=i.agent_id "
                "JOIN wrytely_agent.agents a ON a.id=t.agent_id "
                "JOIN wrytely_agent.telegram_links l ON l.agent_id=a.id AND l.bot_id=i.bot_id "
                "AND l.generation=i.generation "
                "WHERE i.bot_id=%s AND t.status='done' AND t.kind='reply' "
                "AND NOT EXISTS (SELECT 1 FROM wrytely_agent.telegram_outbound o "
                "WHERE o.agent_id=a.id AND o.intent_key='reply:'||t.id::text) "
                "ORDER BY i.received_at LIMIT %s",
                (bot_id, limit),
            ).fetchall()
        for row in rows:
            with self.connection() as conn:
                agent = self._telegram_owner(conn, row["user_id"])
                conn.execute(
                    "INSERT INTO wrytely_agent.telegram_outbound "
                    "(id,agent_id,bot_id,chat_id,generation,intent_key,kind,"
                    "task_id,content,state,reason) "
                    "SELECT %s,a.id,l.bot_id,l.chat_id,l.generation,'reply:'||t.id::text,"
                    "'reply',t.id,CASE WHEN length(m.content) BETWEEN 1 AND 24000 THEN m.content "
                    "ELSE '' END,CASE WHEN length(m.content) BETWEEN 1 AND 24000 THEN 'queued' "
                    "ELSE 'failed' END,CASE WHEN length(m.content) BETWEEN 1 AND 24000 THEN NULL "
                    "ELSE 'result_too_large_or_empty' END FROM wrytely_agent.agents a "
                    "JOIN wrytely_agent.telegram_links l ON l.agent_id=a.id "
                    "JOIN wrytely_agent.telegram_inbound i ON i.agent_id=a.id AND "
                    "i.bot_id=l.bot_id "
                    "AND i.generation=l.generation JOIN wrytely_agent.tasks t "
                    "ON t.id=i.task_id AND t.agent_id=a.id JOIN wrytely_agent.messages m "
                    "ON m.source_task_id=t.id AND m.agent_id=a.id AND m.role='assistant' "
                    "WHERE a.id=%s AND l.bot_id=%s AND t.id=%s AND t.kind='reply' AND "
                    "t.status='done' "
                    "ON CONFLICT(agent_id,intent_key) DO NOTHING",
                    (uuid4(), agent["id"], bot_id, row["id"]),
                )
        return len(rows)

    def queue_telegram_preparation(self, verified_user, bot_id, supervision_id, preparation_id):
        positive_id(bot_id)
        preparation_id = str(_uuid(preparation_id))
        with self._atomic_connection() as conn:
            agent = self._telegram_owner(conn, verified_user)
            link = conn.execute(
                "SELECT * FROM wrytely_agent.telegram_links WHERE agent_id=%s AND bot_id=%s",
                (agent["id"], bot_id),
            ).fetchone()
            if (
                not link
                or not link["consent"]
                or not link["notification_consent"]
                or agent["paused"]
            ):
                raise ValueError("Telegram notification consent required")
            status = self.course_supervision_status(verified_user, supervision_id)
            record = next((p for p in status["preparations"] if p["id"] == preparation_id), None)
            if not record or not record["current"]:
                raise SourceRefreshRequired()
            key = f"preparation:{preparation_id}:{link['generation']}"
            conn.execute(
                "INSERT INTO wrytely_agent.telegram_outbound "
                "(id,agent_id,bot_id,chat_id,generation,intent_key,kind,"
                "supervision_id,preparation_id,content) "
                "VALUES (%s,%s,%s,%s,%s,%s,'preparation',%s,%s,%s) "
                "ON CONFLICT(agent_id,intent_key) DO NOTHING",
                (
                    uuid4(),
                    agent["id"],
                    bot_id,
                    link["chat_id"],
                    link["generation"],
                    key,
                    _uuid(supervision_id),
                    _uuid(preparation_id),
                    preparation_text(record),
                ),
            )
            return conn.execute(
                "SELECT id,state FROM wrytely_agent.telegram_outbound WHERE agent_id=%s "
                "AND intent_key=%s",
                (agent["id"], key),
            ).fetchone()

    def claim_telegram_delivery(self, bot_id):
        positive_id(bot_id)
        with self.connection() as conn:
            conn.execute(
                "UPDATE wrytely_agent.telegram_outbound SET state=CASE WHEN state='sending' "
                "THEN 'unknown' ELSE 'queued' END,attempt_token=NULL,lease_until=NULL,"
                "reason='lease_expired' WHERE bot_id=%s AND state IN ('claimed','sending') "
                "AND lease_until<=clock_timestamp()",
                (bot_id,),
            )
            row = conn.execute(
                "SELECT o.*,a.user_id FROM wrytely_agent.telegram_outbound o "
                "JOIN wrytely_agent.agents a ON a.id=o.agent_id WHERE o.bot_id=%s "
                "AND o.state='queued' AND o.available_at<=clock_timestamp() "
                "ORDER BY o.created_at,o.id LIMIT 1 FOR UPDATE OF o SKIP LOCKED",
                (bot_id,),
            ).fetchone()
            if not row:
                return None
            token = uuid4()
            conn.execute(
                "UPDATE wrytely_agent.telegram_outbound SET state='claimed',attempt_token=%s,"
                "lease_until=clock_timestamp()+interval '60 seconds' WHERE id=%s",
                (token, row["id"]),
            )
            return TelegramClaim(
                row["id"],
                bot_id,
                row["chat_id"],
                row["generation"],
                token,
                row["user_id"],
                row["kind"],
                row["content"],
            )

    def authorize_telegram_dispatch(self, claim):
        with self._atomic_connection() as conn:
            agent = self._telegram_owner(conn, claim.user_id)
            row = conn.execute(
                "SELECT * FROM wrytely_agent.telegram_outbound WHERE id=%s AND agent_id=%s "
                "FOR UPDATE",
                (claim.action_id, agent["id"]),
            ).fetchone()
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            if (
                not row
                or row["state"] != "claimed"
                or row["attempt_token"] != claim.attempt_token
                or row["lease_until"] <= now
            ):
                return TelegramPermit("cancelled", "claim_unavailable")
            link = conn.execute(
                "SELECT * FROM wrytely_agent.telegram_links WHERE agent_id=%s AND bot_id=%s",
                (agent["id"], row["bot_id"]),
            ).fetchone()
            reason = None
            if (
                agent["paused"]
                or not link
                or not link["consent"]
                or (link["generation"], link["chat_id"]) != (row["generation"], row["chat_id"])
                or (claim.bot_id, claim.chat_id, claim.generation, claim.kind, claim.content)
                != (row["bot_id"], row["chat_id"], row["generation"], row["kind"], row["content"])
            ):
                reason = "control_changed"
            elif row["created_at"] + timedelta(hours=24) <= now or row["attempts"] >= 3:
                reason = "intent_expired_or_exhausted"
            elif row["kind"] == "preparation":
                status = self.course_supervision_status(claim.user_id, row["supervision_id"])
                record = next(
                    (p for p in status["preparations"] if p["id"] == str(row["preparation_id"])),
                    None,
                )
                if (
                    not link["notification_consent"]
                    or not record
                    or not record["current"]
                    or preparation_text(record) != row["content"]
                ):
                    reason = "preparation_changed_or_consent_missing"
                count = conn.execute(
                    "SELECT count(*) AS n FROM wrytely_agent.telegram_outbound WHERE agent_id=%s "
                    "AND kind='preparation' AND dispatch_at>clock_timestamp()-interval '24 hours'",
                    (agent["id"],),
                ).fetchone()["n"]
                if count >= 3:
                    reason = "notification_limit"
            else:
                valid = conn.execute(
                    "SELECT m.content FROM wrytely_agent.telegram_inbound i "
                    "JOIN wrytely_agent.tasks t ON t.id=i.task_id AND t.agent_id=i.agent_id "
                    "JOIN wrytely_agent.messages m ON m.source_task_id=t.id AND "
                    "m.agent_id=t.agent_id "
                    "WHERE t.id=%s AND t.agent_id=%s AND i.bot_id=%s AND i.generation=%s "
                    "AND t.status='done' AND t.kind='reply' AND m.role='assistant'",
                    (row["task_id"], agent["id"], row["bot_id"], row["generation"]),
                ).fetchone()
                if not valid or valid["content"] != row["content"]:
                    reason = "reply_changed"
            if reason:
                conn.execute(
                    "UPDATE wrytely_agent.telegram_outbound SET state='cancelled',reason=%s,"
                    "attempt_token=NULL,lease_until=NULL WHERE id=%s",
                    (reason, row["id"]),
                )
                return TelegramPermit("cancelled", reason)
            hour = now.astimezone(ZoneInfo(link["timezone"])).hour
            start, end = link["quiet_start"], link["quiet_end"]
            if start != end and (
                start <= hour < end if start < end else hour >= start or hour < end
            ):
                conn.execute(
                    "UPDATE wrytely_agent.telegram_outbound SET "
                    "state='queued',reason='quiet_hours',"
                    "available_at=clock_timestamp()+interval '5 "
                    "minutes',attempt_token=NULL,lease_until=NULL "
                    "WHERE id=%s",
                    (row["id"],),
                )
                return TelegramPermit("held", "quiet_hours")
            conn.execute(
                "UPDATE wrytely_agent.telegram_outbound SET "
                "state='sending',dispatch_at=clock_timestamp(),"
                "attempts=attempts+1,reason=NULL WHERE id=%s",
                (row["id"],),
            )
            return TelegramPermit("permitted", content=row["content"])

    def finish_telegram_delivery(self, claim, result):
        if result.internal_id != claim.action_id or result.state not in (
            "accepted",
            "failed",
            "unknown",
            "deferred",
        ):
            raise ValueError("Invalid Telegram receipt")
        if result.state == "accepted" and (
            not isinstance(result.provider_ref, str)
            or not re.fullmatch(r"[1-9][0-9]{0,15}", result.provider_ref)
        ):
            raise ValueError("Invalid Telegram provider reference")
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM wrytely_agent.telegram_outbound WHERE id=%s AND state='sending' "
                "AND attempt_token=%s FOR UPDATE",
                (claim.action_id, claim.attempt_token),
            ).fetchone()
            if not row:
                return False
            if (claim.bot_id, claim.chat_id, claim.generation, claim.kind, claim.content) != (
                row["bot_id"],
                row["chat_id"],
                row["generation"],
                row["kind"],
                row["content"],
            ) or not conn.execute(
                "SELECT 1 FROM wrytely_agent.agents WHERE id=%s AND user_id=%s",
                (row["agent_id"], claim.user_id),
            ).fetchone():
                return False
            state = result.state
            if state == "deferred":
                state = "queued" if row["attempts"] < 3 else "failed"
            conn.execute(
                "UPDATE wrytely_agent.telegram_outbound SET state=%s,provider_ref=%s,"
                "attempt_token=NULL,lease_until=NULL,"
                "available_at=clock_timestamp()+interval '60 seconds' "
                "WHERE id=%s",
                (state, result.provider_ref, row["id"]),
            )
            return True
