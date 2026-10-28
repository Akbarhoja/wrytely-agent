"""Private saved drafts; readiness is committed only through mandatory verification."""

from uuid import uuid4

from psycopg.types.json import Jsonb

from contracts.artifacts import DraftArtifact


class ArtifactStore:
    def save_draft(self, lease, draft: DraftArtifact, request_key):
        from shared.db import RequestConflict

        if not 1 <= len(request_key) <= 128:
            raise ValueError("Invalid draft key")
        payload = draft.model_dump(mode="json")
        with self.connection() as conn:
            self._fence(conn, lease)
            task = conn.execute(
                "SELECT t.kind,t.responsibility_id,r.memory_revision FROM wrytely_agent.tasks t "
                "JOIN wrytely_agent.responsibilities r ON r.id=t.responsibility_id "
                "AND r.agent_id=t.agent_id WHERE t.id=%s",
                (lease.task_id,),
            ).fetchone()
            if not task or task["kind"] != "academic":
                raise ValueError("Draft requires an academic responsibility task")
            prior = conn.execute(
                "SELECT * FROM wrytely_agent.artifacts WHERE task_id=%s AND request_key=%s",
                (lease.task_id, request_key),
            ).fetchone()
            if prior:
                if prior["draft"] != payload:
                    raise RequestConflict("Draft key reused")
                return prior
            return conn.execute(
                "INSERT INTO wrytely_agent.artifacts "
                "(id,agent_id,responsibility_id,task_id,request_key,memory_revision,draft) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (
                    uuid4(),
                    lease.agent_id,
                    task["responsibility_id"],
                    lease.task_id,
                    request_key,
                    task["memory_revision"],
                    Jsonb(payload),
                ),
            ).fetchone()

    def artifact(self, user_id, artifact_id):
        with self.connection() as conn:
            return conn.execute(
                "SELECT f.*,f.memory_revision<>r.memory_revision AS stale FROM "
                "wrytely_agent.artifacts f "
                "JOIN wrytely_agent.agents a ON a.id=f.agent_id "
                "JOIN wrytely_agent.responsibilities r ON r.id=f.responsibility_id AND "
                "r.agent_id=f.agent_id "
                "WHERE a.user_id=%s AND f.id=%s",
                (user_id, artifact_id),
            ).fetchone()

    def artifact_verification_input(self, lease, artifact_id):
        with self.connection() as conn:
            self._fence(conn, lease)
            row = conn.execute(
                "SELECT * FROM wrytely_agent.artifacts WHERE id=%s AND agent_id=%s AND task_id=%s",
                (artifact_id, lease.agent_id, lease.task_id),
            ).fetchone()
            if not row:
                raise LookupError("Artifact not found")
            sources = conn.execute(
                "SELECT v.id,v.content,v.coverage,v.retrieved_at FROM "
                "wrytely_agent.responsibility_sources b "
                "JOIN wrytely_agent.academic_sources s ON s.id=b.source_id AND "
                "s.agent_id=b.agent_id "
                "JOIN wrytely_agent.source_versions v ON v.id=s.latest_version_id AND "
                "v.agent_id=s.agent_id "
                "WHERE b.responsibility_id=%s AND b.agent_id=%s",
                (row["responsibility_id"], lease.agent_id),
            ).fetchall()
            return row, sources

    def _commit_artifact_check(self, lease, artifact_id, memory_revision, report):
        """Internal verifier commit only. Not an API or model tool."""
        with self.connection() as conn:
            self._fence(conn, lease)
            row = conn.execute(
                "SELECT f.id FROM wrytely_agent.artifacts f JOIN wrytely_agent.responsibilities r "
                "ON r.id=f.responsibility_id AND r.agent_id=f.agent_id "
                "WHERE f.id=%s AND f.agent_id=%s AND f.task_id=%s "
                "AND f.memory_revision=%s AND r.memory_revision=f.memory_revision FOR UPDATE OF f",
                (artifact_id, lease.agent_id, lease.task_id, memory_revision),
            ).fetchone()
            if not row:
                raise LookupError("Artifact changed or not owned")
            conn.execute(
                "INSERT INTO wrytely_agent.artifact_checks "
                "(id,artifact_id,memory_revision,passed,report) VALUES (%s,%s,%s,%s,%s)",
                (uuid4(), artifact_id, memory_revision, report["passed"], Jsonb(report)),
            )
            conn.execute(
                "UPDATE wrytely_agent.artifacts SET state=%s WHERE id=%s",
                ("ready" if report["passed"] else "needs_revision", artifact_id),
            )

    def drafting_checkpoint(self, lease, kind, workflow_key):
        """Fenced recovery of this task's private drafting workflow state."""
        if kind not in ("drafting_spec", "drafting_preflight"):
            raise ValueError("Invalid checkpoint type")
        with self.connection() as conn:
            self._fence(conn, lease)
            row = conn.execute(
                "SELECT data FROM wrytely_agent.episode_events WHERE task_id=%s AND kind=%s "
                "AND data->>'workflow_key'=%s ORDER BY id DESC LIMIT 1",
                (lease.task_id, kind, workflow_key),
            ).fetchone()
            return row["data"] if row else None

    def draft_progress(self, lease, request_key):
        with self.connection() as conn:
            self._fence(conn, lease)
            artifact = conn.execute(
                "SELECT * FROM wrytely_agent.artifacts WHERE task_id=%s AND agent_id=%s "
                "AND request_key=%s",
                (lease.task_id, lease.agent_id, request_key),
            ).fetchone()
            if not artifact:
                return None, None
            report = conn.execute(
                "SELECT report FROM wrytely_agent.artifact_checks WHERE artifact_id=%s "
                "ORDER BY created_at DESC,id DESC LIMIT 1",
                (artifact["id"],),
            ).fetchone()
            return artifact, report["report"] if report else None

    def drafting_sources(self, lease):
        """Full current bound evidence for policy preflight and generation."""
        with self.connection() as conn:
            self._fence(conn, lease)
            row = conn.execute(
                "SELECT responsibility_id,kind FROM wrytely_agent.tasks WHERE id=%s",
                (lease.task_id,),
            ).fetchone()
            if row["kind"] != "academic":
                raise ValueError("Drafting requires an academic responsibility task")
            return conn.execute(
                "SELECT v.id,v.content,v.coverage,v.retrieved_at FROM "
                "wrytely_agent.responsibility_sources b JOIN wrytely_agent.academic_sources s "
                "ON s.id=b.source_id AND s.agent_id=b.agent_id JOIN "
                "wrytely_agent.source_versions v "
                "ON v.id=s.latest_version_id AND v.agent_id=s.agent_id "
                "WHERE b.responsibility_id=%s AND b.agent_id=%s",
                (row["responsibility_id"], lease.agent_id),
            ).fetchall()
