"""Trusted private-draft intent, fenced assessment and atomic task attachment."""

from datetime import UTC, datetime, timedelta

from psycopg.types.json import Jsonb

from contracts.artifacts import CoursePolicy, RubricItem


class DraftIntentStore:
    def _intent(self, conn, lease):
        return conn.execute(
            "SELECT i.* FROM wrytely_agent.private_draft_intents i "
            "JOIN wrytely_agent.tasks t ON t.responsibility_id=i.responsibility_id "
            "AND t.agent_id=i.agent_id WHERE t.id=%s AND i.agent_id=%s",
            (lease.task_id, lease.agent_id),
        ).fetchone()

    def draft_intent(self, lease):
        with self.connection() as conn:
            self._fence(conn, lease)
            row = self._intent(conn, lease)
            if row:
                current = conn.execute(
                    "SELECT memory_revision FROM wrytely_agent.responsibilities WHERE id=%s",
                    (row["responsibility_id"],),
                ).fetchone()
                if row["memory_revision"] != current["memory_revision"]:
                    raise ValueError("Draft intent source revision changed")
            return row

    def draft_intent_sources(self, lease):
        with self.connection() as conn:
            self._fence(conn, lease)
            intent = self._intent(conn, lease)
            if not intent:
                raise ValueError("Explicit private-draft intent required")
            return self._intent_sources(conn, intent)

    def _intent_sources(self, conn, intent):
        return conn.execute(
            "SELECT v.id,v.content,v.coverage,v.retrieved_at FROM "
            "wrytely_agent.responsibility_sources b JOIN wrytely_agent.academic_sources s "
            "ON s.id=b.source_id AND s.agent_id=b.agent_id "
            "JOIN wrytely_agent.source_versions v ON v.id=s.latest_version_id "
            "AND v.agent_id=s.agent_id "
            "WHERE b.responsibility_id=%s AND b.agent_id=%s ORDER BY v.id",
            (intent["responsibility_id"], intent["agent_id"]),
        ).fetchall()

    def _validate_draft_assessment(self, conn, intent, result):
        policy = CoursePolicy.model_validate(result["policy"]) if result.get("policy") else None
        rubric = [RubricItem.model_validate(r) for r in result["rubric"]]
        sources = self._intent_sources(conn, intent)
        indexed = {str(s["id"]): s for s in sources}
        now = datetime.now(UTC)
        if not 1 <= len(sources) <= 8 or len(rubric) > 30:
            raise ValueError("Invalid assessment evidence bounds")
        if any(
            s["retrieved_at"] < now - timedelta(hours=24)
            or s["retrieved_at"] > now + timedelta(minutes=5)
            for s in sources
        ):
            raise ValueError("Assessment evidence is stale")
        for item in ([policy] if policy else []) + rubric:
            source = indexed.get(str(item.version_id))
            if not source or not item.quote.strip() or item.quote not in source["content"]:
                raise ValueError("Assessment evidence unavailable")
        return bool(policy and policy.status in ("permitted", "disclosure_required") and rubric)

    def commit_draft_assessment(self, lease, result):
        """Internal runtime boundary, never an app endpoint or model tool."""
        with self.connection() as conn:
            self._fence(conn, lease)
            intent = self._intent(conn, lease)
            if not intent:
                raise ValueError("Explicit private-draft intent required")
            revision = conn.execute(
                "SELECT memory_revision FROM wrytely_agent.responsibilities WHERE id=%s",
                (intent["responsibility_id"],),
            ).fetchone()["memory_revision"]
            if revision != intent["memory_revision"]:
                raise ValueError("Draft intent source revision changed")
            if intent["assessment"] is not None:
                from shared.db import RequestConflict

                if intent["assessment"] != result:
                    raise RequestConflict("Assessment already persisted")
                return result["state"] == "assessed"
            allowed = self._validate_draft_assessment(conn, intent, result)
            if result["state"] != ("assessed" if allowed else "blocked"):
                raise ValueError("Invalid assessment state")
            conn.execute(
                "UPDATE wrytely_agent.private_draft_intents SET assessment=%s "
                "WHERE responsibility_id=%s",
                (Jsonb(result), intent["responsibility_id"]),
            )
            if not allowed:
                conn.execute(
                    "UPDATE wrytely_agent.responsibilities SET status='blocked',"
                    "status_reason='draft_policy_or_rubric_blocked' WHERE id=%s",
                    (intent["responsibility_id"],),
                )
                conn.execute(
                    "UPDATE wrytely_agent.tasks SET status='blocked',"
                    "last_error='draft_policy_or_rubric_blocked',lease_token=NULL,lease_until=NULL "
                    "WHERE id=%s",
                    (lease.task_id,),
                )
            return allowed

    def _queue_private_draft(self, conn, lease, decision, context):
        intent = self._intent(conn, lease)
        duty = context["responsibility"]
        if (
            not intent
            or intent["memory_revision"] != duty["memory_revision"]
            or intent["drafting_task_id"] is not None
            or not intent["assessment"]
            or intent["assessment"]["state"] != "assessed"
        ):
            return "draft_intent_unavailable_or_consumed"
        if (
            duty["steps_created"] >= duty["max_steps"]
            or not decision.instruction.strip()
            or any(s["step_key"] == decision.step_key for s in context["previous_steps"])
        ):
            return "step_budget_or_duplicate_or_empty_instruction"
        result = intent["assessment"]
        if not self._validate_draft_assessment(conn, intent, result):
            return "draft_policy_or_rubric_blocked"
        task_id = self._responsibility_task(
            conn,
            lease.agent_id,
            duty["id"],
            "academic",
            decision.instruction.strip(),
            decision.step_key,
        )
        conn.execute(
            "INSERT INTO "
            "wrytely_agent.drafting_requests(task_id,agent_id,specification) VALUES (%s,%s,%s)",
            (
                task_id,
                lease.agent_id,
                Jsonb(
                    {
                        "policy": result["policy"],
                        "rubric": result["rubric"],
                        "max_revisions": intent["max_revisions"],
                    }
                ),
            ),
        )
        conn.execute(
            "UPDATE wrytely_agent.private_draft_intents SET "
            "drafting_task_id=%s WHERE responsibility_id=%s",
            (task_id, duty["id"]),
        )
        conn.execute(
            "UPDATE wrytely_agent.responsibilities SET steps_created=steps_created+1 WHERE id=%s",
            (duty["id"],),
        )
        return None

    def _private_draft_ready(self, conn, lease):
        intent = self._intent(conn, lease)
        if not intent:
            return True
        return bool(
            conn.execute(
                "SELECT 1 FROM wrytely_agent.artifacts f JOIN wrytely_agent.tasks "
                "t ON t.id=f.task_id "
                "WHERE f.task_id=%s AND f.agent_id=%s AND f.state='ready' AND t.status='done' "
                "AND f.memory_revision=%s",
                (intent["drafting_task_id"], lease.agent_id, intent["memory_revision"]),
            ).fetchone()
        )

    def draft_responsibility_status(self, user_id, responsibility_id):
        with self.connection() as conn:
            row = conn.execute(
                "SELECT "
                "r.id,r.status,r.status_reason,r.memory_revision,"
                "i.memory_revision AS intent_revision,"
                "i.assessment,i.drafting_task_id,t.status AS task_status,f.id AS "
                "artifact_id,f.state AS artifact_state "
                "FROM wrytely_agent.responsibilities r JOIN wrytely_agent.agents "
                "a ON a.id=r.agent_id "
                "LEFT JOIN wrytely_agent.private_draft_intents i ON "
                "i.responsibility_id=r.id AND i.agent_id=r.agent_id "
                "LEFT JOIN wrytely_agent.tasks t ON t.id=i.drafting_task_id "
                "LEFT JOIN LATERAL (SELECT id,state FROM wrytely_agent.artifacts "
                "WHERE task_id=i.drafting_task_id "
                "AND agent_id=r.agent_id ORDER BY created_at DESC,id DESC LIMIT 1) f ON true "
                "WHERE a.user_id=%s AND r.id=%s",
                (user_id, responsibility_id),
            ).fetchone()
        if not row:
            return None
        draft = row["intent_revision"] is not None
        stale = draft and row["intent_revision"] != row["memory_revision"]
        assessment = row["assessment"]
        workflow = "not_requested" if not draft else "pending"
        if row["drafting_task_id"]:
            workflow = {
                "ready": "queued",
                "running": "running",
                "blocked": "blocked",
                "done": "ready_for_review",
            }.get(row["task_status"], "blocked")
            if workflow == "ready_for_review" and row["artifact_state"] != "ready":
                workflow = "blocked"
        if draft and (stale or row["status"] == "blocked"):
            workflow = "blocked"
        reason = (
            "source_changed"
            if stale
            else (
                "draft_policy_or_rubric_blocked"
                if assessment and assessment["state"] == "blocked"
                else "draft_work_blocked"
                if row["status"] == "blocked"
                else None
            )
        )
        return {
            "responsibility_id": str(row["id"]),
            "requested_mode": "private_draft" if draft else "analysis",
            "status": "blocked" if stale else row["status"],
            "reason": reason,
            "assessment_state": "not_requested"
            if not draft
            else assessment["state"]
            if assessment
            else "pending",
            "workflow_state": workflow,
            "artifact_id": str(row["artifact_id"]) if row["artifact_id"] else None,
        }
