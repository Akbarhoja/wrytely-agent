import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from contracts.models import TaskLease
from shared.responsibilities import ResponsibilityStore
from shared.whatsapp_store import WhatsAppStore


class LeaseLost(Exception):
    pass


class RequestConflict(Exception):
    pass


class QueueFull(Exception):
    pass


class Store(WhatsAppStore, ResponsibilityStore):
    def __init__(self, url: str):
        self._url = url

    @contextmanager
    def connection(self):
        with psycopg.connect(self._url, row_factory=dict_row, connect_timeout=10) as conn:
            yield conn

    def migrate(self):
        """Explicit command only. Never run automatically on app startup."""
        paths = sorted((Path(__file__).parents[1] / "contracts").glob("[0-9]*_*.sql"))
        with self.connection() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(20417351)")
            conn.execute("CREATE SCHEMA IF NOT EXISTS wrytely_agent")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS wrytely_agent.migrations "
                "(version text PRIMARY KEY, checksum text NOT NULL, "
                "applied_at timestamptz NOT NULL DEFAULT now())"
            )
            for path in paths:
                version = path.name.split("_", 1)[0]
                sql = path.read_text()
                checksum = hashlib.sha256(sql.encode()).hexdigest()
                row = conn.execute(
                    "SELECT checksum FROM wrytely_agent.migrations WHERE version=%s", (version,)
                ).fetchone()
                if row:
                    if row["checksum"] != checksum:
                        raise RuntimeError(
                            "Applied migration checksum changed; add a new migration"
                        )
                    continue
                conn.execute(sql, prepare=False)
                conn.execute(
                    "INSERT INTO wrytely_agent.migrations(version,checksum) VALUES (%s,%s)",
                    (version, checksum),
                )

    def provision(self, user_id: str):
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO wrytely_agent.students(user_id) VALUES (%s) ON CONFLICT DO NOTHING",
                (user_id,),
            )
            return conn.execute(
                "INSERT INTO wrytely_agent.agents(id,user_id) VALUES (%s,%s) "
                "ON CONFLICT(user_id) DO UPDATE SET user_id=excluded.user_id RETURNING *",
                (uuid4(), user_id),
            ).fetchone()

    def agent(self, user_id: str):
        with self.connection() as conn:
            return conn.execute(
                "SELECT * FROM wrytely_agent.agents WHERE user_id=%s", (user_id,)
            ).fetchone()

    def set_paused(self, user_id: str, paused: bool):
        with self.connection() as conn:
            return conn.execute(
                "UPDATE wrytely_agent.agents SET paused=%s WHERE user_id=%s RETURNING *",
                (paused, user_id),
            ).fetchone()

    def enqueue(self, user_id: str, content: str, key: str, limit: int = 20):
        with self.connection() as conn:
            agent = conn.execute(
                "SELECT * FROM wrytely_agent.agents WHERE user_id=%s FOR UPDATE", (user_id,)
            ).fetchone()
            if not agent:
                raise LookupError("Complete agent setup first")
            prior = conn.execute(
                "SELECT m.content,t.id,t.status FROM wrytely_agent.messages m "
                "JOIN wrytely_agent.tasks t ON t.message_id=m.id AND t.agent_id=m.agent_id "
                "WHERE m.agent_id=%s AND m.request_key=%s",
                (agent["id"], key),
            ).fetchone()
            if prior:
                if prior["content"] != content:
                    raise RequestConflict("Idempotency key was already used for another message")
                return {"task_id": prior["id"], "status": prior["status"]}
            count = conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.tasks "
                "WHERE agent_id=%s AND status IN ('ready','running')",
                (agent["id"],),
            ).fetchone()["n"]
            if count >= limit:
                raise QueueFull("Too many pending messages")
            message_id, task_id = uuid4(), uuid4()
            conn.execute(
                "INSERT INTO wrytely_agent.messages(id,agent_id,role,content,request_key) "
                "VALUES (%s,%s,'user',%s,%s)",
                (message_id, agent["id"], content, key),
            )
            conn.execute(
                "INSERT INTO wrytely_agent.tasks(id,agent_id,message_id) VALUES (%s,%s,%s)",
                (task_id, agent["id"], message_id),
            )
            return {"task_id": task_id, "status": "ready"}

    def messages(self, user_id: str):
        with self.connection() as conn:
            return conn.execute(
                "SELECT m.id,m.role,m.content,m.created_at FROM wrytely_agent.messages m "
                "JOIN wrytely_agent.agents a ON a.id=m.agent_id WHERE a.user_id=%s "
                "AND m.role IN ('user','assistant') "
                "AND NOT EXISTS (SELECT 1 FROM wrytely_agent.tasks t "
                "WHERE t.id=m.source_task_id AND t.kind='academic') "
                "ORDER BY m.created_at DESC,m.id DESC LIMIT 100",
                (user_id,),
            ).fetchall()[::-1]

    def task(self, user_id: str, task_id: UUID):
        with self.connection() as conn:
            return conn.execute(
                "SELECT t.id,t.status,t.attempts,t.last_error,t.created_at "
                "FROM wrytely_agent.tasks t JOIN wrytely_agent.agents a ON a.id=t.agent_id "
                "WHERE a.user_id=%s AND t.id=%s",
                (user_id, task_id),
            ).fetchone()

    def tasks(self, user_id: str):
        with self.connection() as conn:
            return conn.execute(
                "SELECT t.id,t.status,t.attempts,t.last_error,t.created_at, "
                "left(m.content,180) AS title FROM wrytely_agent.tasks t "
                "JOIN wrytely_agent.agents a ON a.id=t.agent_id "
                "JOIN wrytely_agent.messages m ON m.id=t.message_id AND m.agent_id=t.agent_id "
                "WHERE a.user_id=%s ORDER BY t.created_at DESC,t.id DESC LIMIT 50",
                (user_id,),
            ).fetchall()

    def claim(self, lease_seconds: int = 300, max_attempts: int = 3):
        with self.connection() as conn:
            # Serialize task selection per agent across worker processes, skip busy agents.
            agent = conn.execute(
                "SELECT a.id,a.user_id FROM wrytely_agent.agents a WHERE NOT a.paused "
                "AND EXISTS(SELECT 1 FROM wrytely_agent.tasks t WHERE t.agent_id=a.id "
                "AND ((t.status='ready' AND t.available_at<=now()) "
                "OR (t.status='running' AND t.lease_until<=now()))) "
                "AND NOT EXISTS(SELECT 1 FROM wrytely_agent.tasks t WHERE t.agent_id=a.id "
                "AND t.status='running' AND t.lease_until>now()) "
                "ORDER BY (SELECT min(t.available_at) FROM wrytely_agent.tasks t "
                "WHERE t.agent_id=a.id AND t.status IN ('ready','running')),a.id "
                "LIMIT 1 FOR UPDATE OF a SKIP LOCKED"
            ).fetchone()
            if not agent:
                return None
            # Recheck with a fresh statement snapshot after acquiring the agent
            # lock: selection may have started before another worker committed.
            if conn.execute(
                "SELECT 1 FROM wrytely_agent.tasks WHERE agent_id=%s "
                "AND status='running' AND lease_until>now()",
                (agent["id"],),
            ).fetchone():
                return None
            conn.execute(
                "UPDATE wrytely_agent.tasks SET status='blocked',last_error='attempt_limit', "
                "lease_token=NULL,lease_until=NULL WHERE agent_id=%s AND attempts>=%s "
                "AND (status='ready' OR (status='running' AND lease_until<=now()))",
                (agent["id"], max_attempts),
            )
            self._block_failed_responsibilities(conn, agent["id"])
            token = uuid4()
            row = conn.execute(
                "UPDATE wrytely_agent.tasks SET status='running',attempts=attempts+1, "
                "lease_token=%s,lease_until=now()+(%s * interval '1 second') "
                "WHERE id=(SELECT id FROM wrytely_agent.tasks WHERE agent_id=%s "
                "AND attempts<%s AND ((status='ready' AND available_at<=now()) "
                "OR (status='running' AND lease_until<=now())) ORDER BY created_at,id LIMIT 1) "
                "RETURNING *",
                (token, lease_seconds, agent["id"], max_attempts),
            ).fetchone()
            if not row:
                return None
            return TaskLease(
                row["id"], agent["id"], agent["user_id"], token, row["attempts"], row["message_id"]
            )

    def _fence(self, conn, lease: TaskLease):
        row = conn.execute(
            "SELECT t.id,a.paused FROM wrytely_agent.tasks t "
            "JOIN wrytely_agent.agents a ON a.id=t.agent_id "
            "WHERE t.id=%s AND t.agent_id=%s AND a.user_id=%s AND t.status='running' "
            "AND t.lease_token=%s AND t.lease_until>now() FOR UPDATE OF a,t",
            (lease.task_id, lease.agent_id, lease.user_id, lease.lease_token),
        ).fetchone()
        if not row or row["paused"]:
            raise LeaseLost("Task lease expired, was superseded, or agent was paused")

    def heartbeat(self, lease: TaskLease, seconds: int = 300):
        with self.connection() as conn:
            self._fence(conn, lease)
            conn.execute(
                "UPDATE wrytely_agent.tasks SET lease_until=now()+(%s * interval '1 second') "
                "WHERE id=%s",
                (seconds, lease.task_id),
            )

    def event(self, lease: TaskLease, kind: str, data: dict):
        with self.connection() as conn:
            self._fence(conn, lease)
            conn.execute(
                "INSERT INTO wrytely_agent.episode_events(task_id,attempt,kind,data) "
                "VALUES (%s,%s,%s,%s)",
                (lease.task_id, lease.attempt, kind, Jsonb(data)),
            )

    def complete(self, lease: TaskLease, text: str):
        with self.connection() as conn:
            self._fence(conn, lease)
            conn.execute(
                "INSERT INTO wrytely_agent.messages(id,agent_id,role,content,source_task_id) "
                "VALUES (%s,%s,'assistant',%s,%s)",
                (uuid4(), lease.agent_id, text, lease.task_id),
            )
            conn.execute(
                "INSERT INTO wrytely_agent.whatsapp_outbound "
                "(id,agent_id,task_id,recipient,content) "
                "SELECT %s,%s,%s,l.phone,%s FROM wrytely_agent.channel_links l "
                "JOIN wrytely_agent.whatsapp_inbound i ON i.agent_id=l.agent_id "
                "WHERE i.task_id=%s AND l.agent_id=%s AND l.linked_at<=i.received_at "
                "ON CONFLICT(task_id) DO NOTHING",
                (uuid4(), lease.agent_id, lease.task_id, text, lease.task_id, lease.agent_id),
            )
            conn.execute(
                "UPDATE wrytely_agent.tasks SET status='done',lease_token=NULL,lease_until=NULL "
                "WHERE id=%s",
                (lease.task_id,),
            )
            self._continue_responsibility(conn, lease)

    def retry(self, lease: TaskLease, code: str, max_attempts: int = 3):
        with self.connection() as conn:
            self._fence(conn, lease)
            # Store controlled error codes only, never provider exception bodies/credentials.
            conn.execute(
                "UPDATE wrytely_agent.tasks SET status=%s,last_error=%s,lease_token=NULL, "
                "lease_until=NULL,available_at=now()+(%s * interval '1 second') WHERE id=%s",
                (
                    "blocked" if lease.attempt >= max_attempts else "ready",
                    code,
                    min(2**lease.attempt, 60),
                    lease.task_id,
                ),
            )

            if lease.attempt >= max_attempts:
                self._block_failed_responsibilities(conn, lease.agent_id)

    def context(self, lease: TaskLease):
        with self.connection() as conn:
            self._fence(conn, lease)
            # Never expose a later queued user's message as the current task input.
            source = conn.execute(
                "SELECT content,created_at FROM wrytely_agent.messages WHERE id=%s AND agent_id=%s",
                (lease.message_id, lease.agent_id),
            ).fetchone()
            return {
                "current_message": source["content"],
                "agent_id": str(lease.agent_id),
                "context_status": "stored_context_only_no_course_connectors",
                **self._responsibility_context(conn, lease),
            }

    def episode_history(self, lease: TaskLease):
        """Private replay records across attempts, fenced to the current owner."""
        with self.connection() as conn:
            self._fence(conn, lease)
            return conn.execute(
                "SELECT kind,data FROM wrytely_agent.episode_events WHERE task_id=%s "
                "AND kind IN ('model_turn','tool_result') ORDER BY id",
                (lease.task_id,),
            ).fetchall()

    def events(self, lease: TaskLease):
        with self.connection() as conn:
            return conn.execute(
                "SELECT kind,data FROM wrytely_agent.episode_events WHERE task_id=%s "
                "AND attempt=%s ORDER BY id",
                (lease.task_id, lease.attempt),
            ).fetchall()


def json_text(value) -> str:
    return json.dumps(value, default=str, ensure_ascii=False)
