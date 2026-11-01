"""Atomic explicit Canvas object delegation. No HTTP, model inference or source promotion."""

from uuid import uuid4

from psycopg.types.json import Jsonb

from shared.canvas_reads import SourceRefreshRequired, _uuid


class CanvasObjectScopeStore:
    def _canvas_scope_objects(self, conn, agent, identifiers):
        objects = []
        for identifier in identifiers:
            connection, row, _ = self._document_observation(conn, agent, None, identifier, None)
            objects.append((connection, row))
        return objects

    def _finish_canvas_scope(self, conn, agent, objects):
        for previous, row in objects:
            connection, _, _ = self._document_observation(conn, agent, None, row["id"], None)
            if (connection["id"], connection["generation"]) != (
                previous["id"],
                previous["generation"],
            ):
                raise SourceRefreshRequired()
            self._finish_canvas_read(conn, None, {}, connection)

    def _fence_canvas_object_scope(self, conn, agent, duty):
        """Caller already holds the owning agent fence; no nested connection/lease read."""
        from shared.db import LeaseLost

        bindings = conn.execute(
            "SELECT * FROM wrytely_agent.responsibility_canvas_objects "
            "WHERE agent_id=%s AND responsibility_id=%s ORDER BY object_id",
            (agent, duty),
        ).fetchall()
        try:
            for binding in bindings:
                connection, _, _ = self._document_observation(
                    conn, agent, None, binding["object_id"], None
                )
                if (connection["id"], connection["generation"]) != (
                    binding["connection_id"],
                    binding["connection_generation"],
                ):
                    raise SourceRefreshRequired()
                self._finish_canvas_read(conn, None, {}, connection)
        except (LookupError, SourceRefreshRequired):
            raise LeaseLost("Canvas object authorization changed") from None
        return bool(bindings)

    def _invalidate_canvas_connection_duties(self, conn, connection_id):
        for duty in conn.execute(
            "SELECT DISTINCT b.responsibility_id FROM "
            "wrytely_agent.responsibility_canvas_objects b "
            "JOIN wrytely_agent.responsibilities r ON r.agent_id=b.agent_id "
            "AND r.id=b.responsibility_id WHERE b.connection_id=%s AND r.status='active'",
            (connection_id,),
        ).fetchall():
            self._invalidate_memory(conn, duty["responsibility_id"])

    def _invalidate_canvas_object_duties(self, conn, agent, object_id, source_id):
        duties = conn.execute(
            "SELECT responsibility_id FROM wrytely_agent.responsibility_canvas_objects "
            "WHERE agent_id=%s AND object_id=%s UNION "
            "SELECT responsibility_id FROM wrytely_agent.responsibility_sources "
            "WHERE agent_id=%s AND source_id=%s",
            (agent, object_id, agent, source_id),
        ).fetchall()
        for duty in duties:
            self._invalidate_memory(conn, duty["responsibility_id"])

    def create_canvas_draft_responsibility(
        self,
        verified_user,
        objective,
        request_key,
        *,
        object_ids,
        max_steps=6,
        max_revisions=2,
        pending_limit=20,
    ):
        """Trusted verified identity only; published objects do not imply unrestricted access.

        Creates scoped intent/task only. Typed document generation is not yet wired;
        the planner holds this intent without model calls until that consumer exists.
        """
        from shared.db import QueueFull, RequestConflict

        if not isinstance(objective, str) or not isinstance(request_key, str):
            raise ValueError("Invalid Canvas responsibility")
        objective = objective.strip()
        if (
            not 1 <= len(objective) <= 12000
            or not 1 <= len(request_key) <= 128
            or not isinstance(object_ids, (list, tuple))
            or not 1 <= len(object_ids) <= 8
            or type(max_steps) is not int
            or not 1 <= max_steps <= 12
            or type(max_revisions) is not int
            or not 0 <= max_revisions <= 2
            or type(pending_limit) is not int
            or not 1 <= pending_limit <= 1000
        ):
            raise ValueError("Invalid Canvas responsibility")
        identifiers = sorted(_uuid(value) for value in object_ids)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Duplicate Canvas objects")
        spec = dict(
            object_ids=[str(i) for i in identifiers],
            objective=objective,
            max_steps=max_steps,
            max_revisions=max_revisions,
            pending_limit=pending_limit,
            requested_mode="canvas_private_draft",
        )
        with self.connection() as conn:
            agent = conn.execute(
                "SELECT id FROM wrytely_agent.agents WHERE user_id=%s FOR UPDATE", (verified_user,)
            ).fetchone()
            if not agent:
                raise LookupError("Not found")
            prior = conn.execute(
                "SELECT * FROM wrytely_agent.responsibilities WHERE agent_id=%s AND request_key=%s",
                (agent["id"], request_key),
            ).fetchone()
            if prior:
                saved = conn.execute(
                    "SELECT e.data FROM wrytely_agent.episode_events e JOIN wrytely_agent.tasks t "
                    "ON t.id=e.task_id WHERE t.agent_id=%s AND t.responsibility_id=%s "
                    "AND e.kind='canvas_responsibility_setup' ORDER BY e.id LIMIT 1",
                    (agent["id"], prior["id"]),
                ).fetchone()
                if not saved or saved["data"] != spec:
                    raise RequestConflict("Canvas responsibility request changed")
            objects = self._canvas_scope_objects(conn, agent["id"], identifiers)
            if prior:
                bindings = conn.execute(
                    "SELECT object_id,connection_id,connection_generation FROM "
                    "wrytely_agent.responsibility_canvas_objects WHERE agent_id=%s "
                    "AND responsibility_id=%s ORDER BY object_id",
                    (agent["id"], prior["id"]),
                ).fetchall()
                expected = [(r["id"], c["id"], c["generation"]) for c, r in objects]
                if [
                    (b["object_id"], b["connection_id"], b["connection_generation"])
                    for b in bindings
                ] != expected:
                    raise SourceRefreshRequired()
                self._finish_canvas_scope(conn, agent["id"], objects)
                return prior
            if (
                conn.execute(
                    "SELECT count(*) AS n FROM wrytely_agent.tasks WHERE agent_id=%s "
                    "AND status IN ('ready','running')",
                    (agent["id"],),
                ).fetchone()["n"]
                >= pending_limit
            ):
                raise QueueFull()
            duty = conn.execute(
                "INSERT INTO wrytely_agent.responsibilities "
                "(id,agent_id,request_key,objective,max_steps,memory_revision) "
                "VALUES (%s,%s,%s,%s,%s,%s) RETURNING *",
                (uuid4(), agent["id"], request_key, objective, max_steps, len(identifiers)),
            ).fetchone()
            for connection, row in objects:
                conn.execute(
                    "INSERT INTO wrytely_agent.responsibility_canvas_objects "
                    "(agent_id,responsibility_id,object_id,connection_id,connection_generation) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (
                        agent["id"],
                        duty["id"],
                        row["id"],
                        connection["id"],
                        connection["generation"],
                    ),
                )
            conn.execute(
                "INSERT INTO wrytely_agent.private_draft_intents "
                "(responsibility_id,agent_id,memory_revision,max_revisions) VALUES (%s,%s,%s,%s)",
                (duty["id"], agent["id"], duty["memory_revision"], max_revisions),
            )
            task = self._responsibility_task(conn, agent["id"], duty["id"], "plan", objective)
            conn.execute(
                "INSERT INTO wrytely_agent.episode_events(task_id,attempt,kind,data) "
                "VALUES (%s,0,'canvas_responsibility_setup',%s)",
                (task, Jsonb(spec)),
            )
            self._finish_canvas_scope(conn, agent["id"], objects)
            return duty
