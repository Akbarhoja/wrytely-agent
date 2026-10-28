"""Transactional WhatsApp linkage and ingestion on the application's existing store."""

import hashlib
import secrets
from uuid import uuid4


class WhatsAppStore:
    def create_whatsapp_challenge(self, user_id: str):
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.connection() as conn:
            agent = conn.execute(
                "SELECT id FROM wrytely_agent.agents WHERE user_id=%s FOR UPDATE", (user_id,)
            ).fetchone()
            if not agent:
                raise LookupError("Complete setup first")
            if conn.execute(
                "SELECT 1 FROM wrytely_agent.channel_links WHERE agent_id=%s", (agent["id"],)
            ).fetchone():
                raise ValueError("Unlink existing WhatsApp first")
            conn.execute(
                "INSERT INTO wrytely_agent.channel_challenges(agent_id,token_hash,expires_at) "
                "VALUES (%s,%s,now()+interval '10 minutes') ON CONFLICT(agent_id) DO UPDATE "
                "SET token_hash=excluded.token_hash,expires_at=excluded.expires_at",
                (agent["id"], digest),
            )
        return {"message": f"LINK {token}", "expires_in_seconds": 600}

    def unlink_whatsapp(self, user_id: str):
        with self.connection() as conn:
            agent = conn.execute(
                "SELECT id FROM wrytely_agent.agents WHERE user_id=%s FOR UPDATE", (user_id,)
            ).fetchone()
            if agent:
                conn.execute(
                    "DELETE FROM wrytely_agent.channel_links WHERE agent_id=%s", (agent["id"],)
                )
                conn.execute(
                    "DELETE FROM wrytely_agent.channel_challenges WHERE agent_id=%s", (agent["id"],)
                )
                conn.execute(
                    "UPDATE wrytely_agent.whatsapp_outbound SET state='cancelled' "
                    "WHERE agent_id=%s AND state IN ('queued','deferred')",
                    (agent["id"],),
                )

    def ingest_whatsapp(self, message, *, limit: int = 20):
        """Accept only authenticated adapter data. Link, record and enqueue atomically.

        Unknown senders are ignored without retaining their text. A linking secret
        is never stored as a conversation or sent to the model. No message is sent.
        """
        from shared.db import QueueFull

        with self.connection() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (message.sender,))
            if conn.execute(
                "SELECT 1 FROM wrytely_agent.whatsapp_inbound WHERE provider_id=%s",
                (message.provider_id,),
            ).fetchone():
                return "duplicate"
            if message.text.startswith("LINK "):
                digest = hashlib.sha256(message.text[5:].encode()).hexdigest()
                # Serialize with challenge issuance/unlink and agent execution.
                challenge = conn.execute(
                    "SELECT a.id FROM wrytely_agent.agents a JOIN "
                    "wrytely_agent.channel_challenges c ON c.agent_id=a.id "
                    "WHERE c.token_hash=%s AND c.expires_at>now() FOR UPDATE OF a",
                    (digest,),
                ).fetchone()
                if not challenge:
                    return "ignored"
                if conn.execute(
                    "SELECT 1 FROM wrytely_agent.channel_links WHERE phone=%s OR agent_id=%s",
                    (message.sender, challenge["id"]),
                ).fetchone():
                    return "ignored"
                # Recheck after taking the agent lock in case a challenge was rotated.
                deleted = conn.execute(
                    "DELETE FROM wrytely_agent.channel_challenges WHERE agent_id=%s "
                    "AND token_hash=%s AND expires_at>now() RETURNING agent_id",
                    (challenge["id"], digest),
                ).fetchone()
                if not deleted:
                    return "ignored"
                conn.execute(
                    "INSERT INTO wrytely_agent.channel_links(agent_id,phone) VALUES (%s,%s)",
                    (challenge["id"], message.sender),
                )
                conn.execute(
                    "INSERT INTO wrytely_agent.whatsapp_inbound(provider_id,agent_id) "
                    "VALUES (%s,%s)",
                    (message.provider_id, challenge["id"]),
                )
                return "linked"
            agent = conn.execute(
                "SELECT a.id FROM wrytely_agent.agents a JOIN wrytely_agent.channel_links l "
                "ON l.agent_id=a.id WHERE l.phone=%s FOR UPDATE OF a",
                (message.sender,),
            ).fetchone()
            if not agent:
                return "ignored"
            # Unlink may have completed while waiting for the agent lock.
            if not conn.execute(
                "SELECT 1 FROM wrytely_agent.channel_links WHERE agent_id=%s AND phone=%s",
                (agent["id"], message.sender),
            ).fetchone():
                return "ignored"
            count = conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.tasks WHERE agent_id=%s "
                "AND status IN ('ready','running')",
                (agent["id"],),
            ).fetchone()["n"]
            if count >= limit:
                raise QueueFull()
            message_id, task_id = uuid4(), uuid4()
            conn.execute(
                "INSERT INTO wrytely_agent.messages(id,agent_id,role,content) "
                "VALUES (%s,%s,'user',%s)",
                (message_id, agent["id"], message.text),
            )
            conn.execute(
                "INSERT INTO wrytely_agent.tasks(id,agent_id,message_id) VALUES (%s,%s,%s)",
                (task_id, agent["id"], message_id),
            )
            conn.execute(
                "INSERT INTO wrytely_agent.whatsapp_inbound(provider_id,agent_id,task_id) "
                "VALUES (%s,%s,%s)",
                (message.provider_id, agent["id"], task_id),
            )
            conn.execute(
                "UPDATE wrytely_agent.channel_links SET last_inbound_at=now() WHERE agent_id=%s",
                (agent["id"],),
            )
            return "queued"
