"""Explicit student revisions reuse original scoped tasks/drafting/checks/artifacts."""

import hashlib

from psycopg.types.json import Jsonb

from shared.canvas_reads import SourceRefreshRequired


class ArtifactRevisionStore:
    def request_private_artifact_revision(
        self, verified_user, artifact_id, instructions, request_key
    ):
        from shared.db import QueueFull, RequestConflict

        if (
            not isinstance(instructions, str)
            or not instructions.strip()
            or len(instructions) > 4000
            or not isinstance(request_key, str)
            or not 1 <= len(request_key) <= 100
        ):
            raise ValueError("Invalid revision request")
        instructions = instructions.strip()
        with self.connection() as conn:
            artifact, duty, draft = self._private_artifact(conn, verified_user, artifact_id)
            check = self._private_check(conn, artifact)
            proofs, cache = self._private_proofs(conn, artifact, draft, check)
            current = self._finish_private(conn, artifact, duty, proofs, cache, check)
            agent = conn.execute(
                "SELECT paused FROM wrytely_agent.agents WHERE id=%s", (artifact["agent_id"],)
            ).fetchone()
            if (
                artifact["state"] != "ready"
                or not check
                or not check["report"]["passed"]
                or current["state"] != "current"
                or agent["paused"]
                or duty["status"] not in ("active", "done")
            ):
                raise SourceRefreshRequired()
            step = (
                "revision-"
                + hashlib.sha256((str(artifact["id"]) + ":" + request_key).encode()).hexdigest()
            )
            revision = {
                "artifact_id": str(artifact["id"]),
                "check_id": str(check["id"]),
                "instructions": instructions,
                "draft": draft,
            }
            prior = conn.execute(
                "SELECT t.id,t.status,d.specification FROM wrytely_agent.tasks t "
                "JOIN wrytely_agent.drafting_requests d "
                "ON d.task_id=t.id AND d.agent_id=t.agent_id "
                "WHERE t.agent_id=%s AND t.responsibility_id=%s AND t.step_key=%s",
                (artifact["agent_id"], duty["id"], step),
            ).fetchone()
            if prior:
                if prior["specification"].get("revision") != revision:
                    raise RequestConflict("Revision request key changed")
                return {
                    "task_id": prior["id"],
                    "state": prior["status"],
                    "parent_artifact_id": artifact["id"],
                }
            active = conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.tasks WHERE agent_id=%s "
                "AND status IN ('ready','running')",
                (artifact["agent_id"],),
            ).fetchone()["n"]
            academic = conn.execute(
                "SELECT 1 FROM wrytely_agent.tasks WHERE agent_id=%s AND responsibility_id=%s "
                "AND kind='academic' AND status IN ('ready','running')",
                (artifact["agent_id"], duty["id"]),
            ).fetchone()
            if duty["steps_created"] >= duty["max_steps"] or active >= 20 or academic:
                raise QueueFull("Work/revision limit or existing work in progress")
            # A student revision replaces obsolete planner continuation, not prior results.
            conn.execute(
                "UPDATE wrytely_agent.tasks SET status='blocked',"
                "last_error='superseded_by_revision',lease_token=NULL,lease_until=NULL "
                "WHERE agent_id=%s AND responsibility_id=%s AND kind='plan' "
                "AND status IN ('ready','running')",
                (artifact["agent_id"], duty["id"]),
            )
            conn.execute(
                "UPDATE wrytely_agent.responsibilities SET status='active',status_reason=NULL,"
                "steps_created=steps_created+1 WHERE id=%s",
                (duty["id"],),
            )
            task = self._responsibility_task(
                conn, artifact["agent_id"], duty["id"], "academic", instructions, step
            )
            spec = {
                "policy": check["report"]["policy"],
                "rubric": check["report"]["rubric"],
                "max_revisions": 1,
                "evidence_schema": 2,
                "revision": revision,
            }
            conn.execute(
                "INSERT INTO wrytely_agent.drafting_requests(task_id,agent_id,specification) "
                "VALUES (%s,%s,%s)",
                (task, artifact["agent_id"], Jsonb(spec)),
            )
            return {"task_id": task, "state": "ready", "parent_artifact_id": artifact["id"]}
