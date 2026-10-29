"""Atomic academic-context setup; this boundary authorizes analysis only."""

from uuid import UUID, uuid4

from psycopg.types.json import Jsonb


class BoundResponsibilityStore:
    def create_bound_responsibility(
        self, user_id, objective, key, *, source_ids, max_steps=6, pending_limit=20
    ):
        return self._create_bound_responsibility(
            user_id,
            objective,
            key,
            source_ids=source_ids,
            max_steps=max_steps,
            pending_limit=pending_limit,
            draft_revisions=None,
        )

    def create_draft_responsibility(
        self,
        user_id,
        objective,
        key,
        *,
        source_ids,
        max_steps=6,
        pending_limit=20,
        max_revisions=2,
    ):
        if type(max_revisions) is not int or not 0 <= max_revisions <= 2:
            raise ValueError("Invalid draft revision budget")
        return self._create_bound_responsibility(
            user_id,
            objective,
            key,
            source_ids=source_ids,
            max_steps=max_steps,
            pending_limit=pending_limit,
            draft_revisions=max_revisions,
        )

    def _create_bound_responsibility(
        self, user_id, objective, key, *, source_ids, max_steps, pending_limit, draft_revisions
    ):
        from shared.db import QueueFull, RequestConflict

        objective = objective.strip()
        if (
            not 1 <= len(objective) <= 12000
            or not 1 <= len(key) <= 128
            or type(max_steps) is not int
            or not 1 <= max_steps <= 12
            or type(pending_limit) is not int
            or not 1 <= pending_limit <= 1000
            or not isinstance(source_ids, (list, tuple))
            or not 1 <= len(source_ids) <= 8
        ):
            raise ValueError("Invalid bound responsibility")
        try:
            identifiers = [UUID(str(value)) for value in source_ids]
        except (ValueError, TypeError, AttributeError) as exc:
            raise LookupError("Source not found") from exc
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Duplicate sources")
        canonical = sorted(str(value) for value in identifiers)
        specification = {"source_ids": canonical, "objective": objective, "max_steps": max_steps}
        if draft_revisions is not None:
            specification.update(requested_mode="private_draft", max_revisions=draft_revisions)
        with self.connection() as conn:
            # Same lock as observe_source, bind_source and worker claiming.
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
                saved = conn.execute(
                    "SELECT e.data FROM wrytely_agent.episode_events e "
                    "JOIN wrytely_agent.tasks t ON t.id=e.task_id "
                    "WHERE t.responsibility_id=%s AND t.agent_id=%s "
                    "AND e.kind='bound_responsibility_setup' ORDER BY e.id LIMIT 1",
                    (prior["id"], agent["id"]),
                ).fetchone()
                if not saved or saved["data"] != specification:
                    raise RequestConflict("Responsibility request changed")
                return prior
            owned = conn.execute(
                "SELECT s.id FROM wrytely_agent.academic_sources s "
                "JOIN wrytely_agent.source_versions v ON v.id=s.latest_version_id "
                "AND v.agent_id=s.agent_id WHERE s.agent_id=%s AND s.id=ANY(%s)",
                (agent["id"], identifiers),
            ).fetchall()
            if len(owned) != len(identifiers):
                raise LookupError("Source not found")
            pending = conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.tasks WHERE agent_id=%s "
                "AND status IN ('ready','running')",
                (agent["id"],),
            ).fetchone()["n"]
            if pending >= pending_limit:
                raise QueueFull()
            row = conn.execute(
                "INSERT INTO wrytely_agent.responsibilities "
                "(id,agent_id,request_key,objective,max_steps,memory_revision) "
                "VALUES (%s,%s,%s,%s,%s,%s) RETURNING *",
                (uuid4(), agent["id"], key, objective, max_steps, len(identifiers)),
            ).fetchone()
            for source_id in sorted(identifiers):
                conn.execute(
                    "INSERT INTO wrytely_agent.responsibility_sources "
                    "(agent_id,responsibility_id,source_id) VALUES (%s,%s,%s)",
                    (agent["id"], row["id"], source_id),
                )
            if draft_revisions is not None:
                conn.execute(
                    "INSERT INTO wrytely_agent.private_draft_intents "
                    "(responsibility_id,agent_id,memory_revision,max_revisions) "
                    "VALUES (%s,%s,%s,%s)",
                    (row["id"], agent["id"], row["memory_revision"], draft_revisions),
                )
            task_id = self._responsibility_task(conn, agent["id"], row["id"], "plan", objective)
            conn.execute(
                "INSERT INTO wrytely_agent.episode_events(task_id,attempt,kind,data) "
                "VALUES (%s,0,'bound_responsibility_setup',%s)",
                (task_id, Jsonb(specification)),
            )
            return row
