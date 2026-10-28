"""Internal-only responsibilities; trusted callers supply verified student identity."""

from uuid import uuid4

from contracts.models import PlannerDecision


class ResponsibilityStore:
    def _responsibility_task(self, conn, agent_id, responsibility_id, kind, text, step_key=None):
        message_id, task_id = uuid4(), uuid4()
        conn.execute(
            "INSERT INTO wrytely_agent.messages(id,agent_id,role,content) "
            "VALUES (%s,%s,'internal',%s)",
            (message_id, agent_id, text),
        )
        conn.execute(
            "INSERT INTO wrytely_agent.tasks "
            "(id,agent_id,message_id,responsibility_id,kind,step_key) VALUES (%s,%s,%s,%s,%s,%s)",
            (task_id, agent_id, message_id, responsibility_id, kind, step_key),
        )
        return task_id

    def create_responsibility(self, user_id, objective, key, *, max_steps=6, pending_limit=20):
        from shared.db import QueueFull, RequestConflict

        objective = objective.strip()
        if not 1 <= len(objective) <= 12000 or not 1 <= len(key) <= 128 or not 1 <= max_steps <= 12:
            raise ValueError("Invalid responsibility")
        with self.connection() as conn:
            agent = conn.execute(
                "SELECT id FROM wrytely_agent.agents WHERE user_id=%s FOR UPDATE", (user_id,)
            ).fetchone()
            if not agent:
                raise LookupError("Complete setup first")
            prior = conn.execute(
                "SELECT * FROM wrytely_agent.responsibilities WHERE agent_id=%s AND request_key=%s",
                (agent["id"], key),
            ).fetchone()
            if prior:
                if prior["objective"] != objective or prior["max_steps"] != max_steps:
                    raise RequestConflict()
                return prior
            pending = conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.tasks WHERE agent_id=%s "
                "AND status IN ('ready','running')",
                (agent["id"],),
            ).fetchone()["n"]
            if pending >= pending_limit:
                raise QueueFull()
            row = conn.execute(
                "INSERT INTO wrytely_agent.responsibilities "
                "(id,agent_id,request_key,objective,max_steps) "
                "VALUES (%s,%s,%s,%s,%s) RETURNING *",
                (uuid4(), agent["id"], key, objective, max_steps),
            ).fetchone()
            self._responsibility_task(conn, agent["id"], row["id"], "plan", objective)
            return row

    def responsibilities(self, user_id):
        with self.connection() as conn:
            return conn.execute(
                "SELECT r.* FROM wrytely_agent.responsibilities r JOIN wrytely_agent.agents a "
                "ON a.id=r.agent_id WHERE a.user_id=%s ORDER BY r.created_at DESC LIMIT 50",
                (user_id,),
            ).fetchall()

    def _responsibility_context(self, conn, lease):
        task = conn.execute(
            "SELECT kind,responsibility_id FROM wrytely_agent.tasks WHERE id=%s", (lease.task_id,)
        ).fetchone()
        if not task["responsibility_id"]:
            return {"task_kind": "reply"}
        row = conn.execute(
            "SELECT id,objective,status,status_reason,steps_created,max_steps "
            "FROM wrytely_agent.responsibilities WHERE id=%s AND agent_id=%s",
            (task["responsibility_id"], lease.agent_id),
        ).fetchone()
        outcomes = conn.execute(
            "SELECT t.step_key,t.status,left(m.content,4000) AS result FROM wrytely_agent.tasks t "
            "LEFT JOIN wrytely_agent.messages m ON m.source_task_id=t.id AND m.agent_id=t.agent_id "
            "WHERE t.responsibility_id=%s AND t.kind='academic' ORDER BY t.created_at,t.id",
            (row["id"],),
        ).fetchall()
        return {
            "task_kind": task["kind"],
            "responsibility": row,
            "previous_steps": outcomes,
            "scope": "internal_analysis_only_no_external_actions_or_verified_artifacts",
        }

    def _continue_responsibility(self, conn, lease):
        task = conn.execute(
            "SELECT responsibility_id,kind FROM wrytely_agent.tasks WHERE id=%s", (lease.task_id,)
        ).fetchone()
        if task["kind"] != "academic":
            return
        row = conn.execute(
            "SELECT * FROM wrytely_agent.responsibilities WHERE id=%s AND agent_id=%s FOR UPDATE",
            (task["responsibility_id"], lease.agent_id),
        ).fetchone()
        if row["status"] == "active":
            self._responsibility_task(conn, lease.agent_id, row["id"], "plan", row["objective"])

    def saved_plan(self, lease):
        with self.connection() as conn:
            self._fence(conn, lease)
            row = conn.execute(
                "SELECT data FROM wrytely_agent.episode_events WHERE task_id=%s "
                "AND kind='planner_decision' ORDER BY id DESC LIMIT 1",
                (lease.task_id,),
            ).fetchone()
            return row["data"]["decision"] if row else None

    def _block_failed_responsibilities(self, conn, agent_id):
        conn.execute(
            "UPDATE wrytely_agent.responsibilities r SET status='blocked', "
            "status_reason='task_execution_failed' WHERE r.agent_id=%s AND r.status='active' "
            "AND EXISTS (SELECT 1 FROM wrytely_agent.tasks t "
            "WHERE t.responsibility_id=r.id AND t.status='blocked')",
            (agent_id,),
        )

    def apply_plan(self, lease, decision: PlannerDecision):
        """Fenced transaction: finalize planning and create its next work atomically."""
        with self.connection() as conn:
            self._fence(conn, lease)
            context = self._responsibility_context(conn, lease)
            if context["task_kind"] != "plan":
                raise ValueError("Not a planning task")
            row = context["responsibility"]
            status, reason = decision.action, decision.reason
            if row["status"] != "active":
                raise ValueError("Responsibility is not active")
            if decision.action == "work":
                duplicate = any(
                    s["step_key"] == decision.step_key for s in context["previous_steps"]
                )
                if (
                    row["steps_created"] >= row["max_steps"]
                    or duplicate
                    or not decision.instruction.strip()
                ):
                    status, reason = "blocked", "step_budget_or_duplicate_or_empty_instruction"
                else:
                    self._responsibility_task(
                        conn,
                        lease.agent_id,
                        row["id"],
                        "academic",
                        decision.instruction.strip(),
                        decision.step_key,
                    )
                    conn.execute(
                        "UPDATE wrytely_agent.responsibilities SET steps_created=steps_created+1 "
                        "WHERE id=%s",
                        (row["id"],),
                    )
                    status = "active"
            if status == "done" and not context["previous_steps"]:
                status, reason = "blocked", "no_completed_work"
            conn.execute(
                "UPDATE wrytely_agent.responsibilities SET status=%s,status_reason=%s WHERE id=%s",
                (status, reason, row["id"]),
            )
            conn.execute(
                "UPDATE wrytely_agent.tasks SET status='done',lease_token=NULL,lease_until=NULL "
                "WHERE id=%s",
                (lease.task_id,),
            )
