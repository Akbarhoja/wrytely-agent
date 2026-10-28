"""Explicit trusted delegation of a queued academic step to the checked draft pipeline."""

from psycopg.types.json import Jsonb

from contracts.artifacts import CoursePolicy, RubricItem


class DraftingTaskStore:
    def configure_drafting_task(
        self, user_id, task_id, *, policy: CoursePolicy, rubric: list[RubricItem], max_revisions=2
    ):
        from shared.db import RequestConflict

        if (
            not 1 <= len(rubric) <= 30
            or type(max_revisions) is not int
            or not 0 <= max_revisions <= 2
        ):
            raise ValueError("Invalid rubric or revision budget")
        specification = {
            "policy": policy.model_dump(mode="json"),
            "rubric": [item.model_dump(mode="json") for item in rubric],
            "max_revisions": max_revisions,
        }
        with self.connection() as conn:
            agent = conn.execute(
                "SELECT id FROM wrytely_agent.agents WHERE user_id=%s FOR UPDATE", (user_id,)
            ).fetchone()
            if not agent:
                raise LookupError("Task not found")
            task = conn.execute(
                "SELECT t.*,r.status AS responsibility_status, "
                "r.memory_revision AS current_revision "
                "FROM wrytely_agent.tasks t JOIN wrytely_agent.responsibilities r "
                "ON r.id=t.responsibility_id AND r.agent_id=t.agent_id "
                "WHERE t.id=%s AND t.agent_id=%s FOR UPDATE OF t",
                (task_id, agent["id"]),
            ).fetchone()
            if not task:
                raise LookupError("Task not found")
            prior = conn.execute(
                "SELECT specification FROM wrytely_agent.drafting_requests "
                "WHERE task_id=%s AND agent_id=%s",
                (task_id, agent["id"]),
            ).fetchone()
            if prior:
                if prior["specification"] != specification:
                    raise RequestConflict("Draft delegation cannot change under the same task")
                return
            if (
                task["kind"] != "academic"
                or task["status"] != "ready"
                or task["attempts"] != 0
                or task["responsibility_status"] != "active"
                or task["memory_revision"] != task["current_revision"]
            ):
                raise ValueError("Only unstarted current academic tasks can be delegated")
            if policy.status not in ("permitted", "disclosure_required"):
                raise ValueError("Policy does not permit full drafting")
            for item in [policy, *rubric]:
                source = conn.execute(
                    "SELECT v.content FROM wrytely_agent.responsibility_sources b "
                    "JOIN wrytely_agent.academic_sources s "
                    "ON s.id=b.source_id AND s.agent_id=b.agent_id "
                    "JOIN wrytely_agent.source_versions v "
                    "ON v.id=s.latest_version_id AND v.agent_id=s.agent_id "
                    "WHERE b.responsibility_id=%s AND b.agent_id=%s AND v.id=%s",
                    (task["responsibility_id"], agent["id"], item.version_id),
                ).fetchone()
                if not source or not item.quote.strip() or item.quote not in source["content"]:
                    raise ValueError("Current bound policy/rubric evidence required")
            conn.execute(
                "INSERT INTO wrytely_agent.drafting_requests(task_id,agent_id,specification) "
                "VALUES (%s,%s,%s)",
                (task_id, agent["id"], Jsonb(specification)),
            )

    def drafting_request(self, lease):
        with self.connection() as conn:
            self._fence(conn, lease)
            row = conn.execute(
                "SELECT specification FROM wrytely_agent.drafting_requests "
                "WHERE task_id=%s AND agent_id=%s",
                (lease.task_id, lease.agent_id),
            ).fetchone()
            return row["specification"] if row else None

    def block_drafting_task(self, lease, outcome):
        with self.connection() as conn:
            self._fence(conn, lease)
            if not conn.execute(
                "SELECT 1 FROM wrytely_agent.drafting_requests WHERE task_id=%s AND agent_id=%s",
                (lease.task_id, lease.agent_id),
            ).fetchone():
                raise ValueError("Not a delegated drafting task")
            conn.execute(
                "INSERT INTO wrytely_agent.episode_events(task_id,attempt,kind,data) "
                "VALUES (%s,%s,'drafting_outcome',%s)",
                (lease.task_id, lease.attempt, Jsonb(outcome)),
            )
            conn.execute(
                "UPDATE wrytely_agent.tasks SET status='blocked',last_error=%s, "
                "lease_token=NULL,lease_until=NULL WHERE id=%s",
                ("drafting_" + outcome["state"], lease.task_id),
            )
            conn.execute(
                "UPDATE wrytely_agent.responsibilities SET status='blocked',status_reason=%s "
                "WHERE id=(SELECT responsibility_id FROM wrytely_agent.tasks WHERE id=%s) "
                "AND agent_id=%s",
                ("drafting_" + outcome["state"], lease.task_id, lease.agent_id),
            )
