"""Versioned academic evidence. No connector IO or permission inference."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from contracts.models import SourceObservation
from shared.freshness import legacy_freshness


class AcademicMemoryStore:
    def observe_source(self, user_id: str, observation: SourceObservation):
        if observation.retrieved_at > datetime.now(UTC) + timedelta(minutes=5):
            raise ValueError("Retrieval time is in the future")
        with self.connection() as conn:
            agent = conn.execute(
                "SELECT id FROM wrytely_agent.agents WHERE user_id=%s FOR UPDATE", (user_id,)
            ).fetchone()
            if not agent:
                raise LookupError("Complete setup first")
            return self._observe_source_transaction(conn, agent["id"], observation)

    def _observe_source_transaction(self, conn, agent_id, observation, *, promote=True):
        """Caller holds agent lock; optional staging never activates legacy source reads."""
        from shared.db import RequestConflict

        source = conn.execute(
            "INSERT INTO wrytely_agent.academic_sources(id,agent_id,source_key) "
            "VALUES (%s,%s,%s) "
            "ON CONFLICT(agent_id,source_key) DO UPDATE SET source_key=excluded.source_key "
            "RETURNING *",
            (uuid4(), agent_id, observation.source_key),
        ).fetchone()
        prior = conn.execute(
            "SELECT * FROM wrytely_agent.source_versions "
            "WHERE source_id=%s AND external_revision=%s",
            (source["id"], observation.external_revision),
        ).fetchone()
        if prior:
            for field in (
                ("title", "reference", "coverage", "content")
                if promote
                else ("title", "coverage", "content")
            ):
                if prior[field] != getattr(observation, field):
                    raise RequestConflict("Revision reused with different evidence")
            return prior
        current = conn.execute(
            "SELECT * FROM wrytely_agent.source_versions WHERE id=%s",
            (source["latest_version_id"],),
        ).fetchone()
        if promote and current and current["retrieved_at"] == observation.retrieved_at:
            raise RequestConflict("Ambiguous version ordering")
        version = conn.execute(
            "INSERT INTO wrytely_agent.source_versions "
            "(id,agent_id,source_id,external_revision,title,reference,coverage,content,"
            "retrieved_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (
                uuid4(),
                agent_id,
                source["id"],
                observation.external_revision,
                observation.title,
                observation.reference,
                observation.coverage,
                observation.content,
                observation.retrieved_at,
            ),
        ).fetchone()
        if promote and (current is None or version["retrieved_at"] > current["retrieved_at"]):
            conn.execute(
                "UPDATE wrytely_agent.academic_sources SET latest_version_id=%s WHERE id=%s",
                (version["id"], source["id"]),
            )
            affected = conn.execute(
                "SELECT responsibility_id FROM wrytely_agent.responsibility_sources "
                "WHERE source_id=%s AND agent_id=%s",
                (source["id"], agent_id),
            ).fetchall()
            for row in affected:
                self._invalidate_memory(conn, row["responsibility_id"])
        return version

    def _invalidate_memory(self, conn, responsibility_id):
        conn.execute(
            "UPDATE wrytely_agent.responsibilities SET memory_revision=memory_revision+1, "
            "status='blocked',status_reason='source_changed' WHERE id=%s",
            (responsibility_id,),
        )
        conn.execute(
            "UPDATE wrytely_agent.tasks SET status='blocked',last_error='source_changed', "
            "lease_token=NULL,lease_until=NULL WHERE responsibility_id=%s "
            "AND status IN ('ready','running')",
            (responsibility_id,),
        )

    def bind_source(self, user_id, responsibility_id, source_id):
        with self.connection() as conn:
            agent = conn.execute(
                "SELECT id FROM wrytely_agent.agents WHERE user_id=%s FOR UPDATE", (user_id,)
            ).fetchone()
            if not agent:
                raise LookupError("Not found")
            responsibility = conn.execute(
                "SELECT * FROM wrytely_agent.responsibilities WHERE id=%s AND agent_id=%s",
                (responsibility_id, agent["id"]),
            ).fetchone()
            source = conn.execute(
                "SELECT id FROM wrytely_agent.academic_sources WHERE id=%s AND agent_id=%s",
                (source_id, agent["id"]),
            ).fetchone()
            if not responsibility or not source:
                raise LookupError("Not found")
            prior = conn.execute(
                "SELECT 1 FROM wrytely_agent.responsibility_sources WHERE responsibility_id=%s "
                "AND source_id=%s",
                (responsibility_id, source_id),
            ).fetchone()
            if prior:
                return
            count = conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.responsibility_sources "
                "WHERE responsibility_id=%s",
                (responsibility_id,),
            ).fetchone()["n"]
            if count >= 8:
                raise ValueError("Responsibility source limit reached")
            conn.execute(
                "INSERT INTO wrytely_agent.responsibility_sources "
                "(agent_id,responsibility_id,source_id) VALUES (%s,%s,%s)",
                (agent["id"], responsibility_id, source_id),
            )
            # Before any work, enrich the initial plan in place. Once work began,
            # stop stale execution; A4 will implement reviewed adaptation/resumption.
            started = conn.execute(
                "SELECT 1 FROM wrytely_agent.tasks WHERE responsibility_id=%s "
                "AND (attempts>0 OR kind='academic') LIMIT 1",
                (responsibility_id,),
            ).fetchone()
            if started:
                self._invalidate_memory(conn, responsibility_id)
            else:
                conn.execute(
                    "UPDATE wrytely_agent.responsibilities SET memory_revision=memory_revision+1 "
                    "WHERE id=%s",
                    (responsibility_id,),
                )
                conn.execute(
                    "UPDATE wrytely_agent.tasks SET memory_revision=coalesce(memory_revision,0)+1 "
                    "WHERE responsibility_id=%s",
                    (responsibility_id,),
                )

    def record_source_fact(self, lease, version_id, claim, quote):
        if not 1 <= len(claim.strip()) <= 2000 or not 1 <= len(quote.strip()) <= 2000:
            raise ValueError("Invalid fact")
        fact_hash = hashlib.sha256(json.dumps([claim, quote]).encode()).hexdigest()
        with self.connection() as conn:
            self._fence(conn, lease)
            source = conn.execute(
                "SELECT v.content,t.responsibility_id FROM wrytely_agent.tasks t "
                "JOIN wrytely_agent.responsibility_sources b "
                "ON b.responsibility_id=t.responsibility_id "
                "AND b.agent_id=t.agent_id JOIN wrytely_agent.academic_sources s "
                "ON s.id=b.source_id "
                "AND s.agent_id=t.agent_id JOIN wrytely_agent.source_versions v "
                "ON v.id=s.latest_version_id AND v.agent_id=t.agent_id "
                "WHERE t.id=%s AND v.id=%s",
                (lease.task_id, version_id),
            ).fetchone()
            if not source:
                raise LookupError("Source not available to this responsibility")
            if quote not in source["content"]:
                raise ValueError("Quote is not in source")
            return conn.execute(
                "INSERT INTO wrytely_agent.source_facts "
                "(id,agent_id,responsibility_id,version_id,fact_hash,claim,quote) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT(responsibility_id,version_id,fact_hash) "
                "DO UPDATE SET claim=excluded.claim "
                "RETURNING *",
                (
                    uuid4(),
                    lease.agent_id,
                    source["responsibility_id"],
                    version_id,
                    fact_hash,
                    claim,
                    quote,
                ),
            ).fetchone()

    def _academic_memory(self, conn, agent_id, responsibility_id):
        sources = conn.execute(
            "SELECT s.id AS source_id,v.id AS version_id,v.external_revision,v.title,v.reference, "
            "v.coverage,v.retrieved_at,left(v.content,6000) AS excerpt, "
            "length(v.content)>6000 AS excerpt_truncated "
            "FROM wrytely_agent.responsibility_sources b JOIN wrytely_agent.academic_sources s "
            "ON s.id=b.source_id AND s.agent_id=b.agent_id JOIN wrytely_agent.source_versions v "
            "ON v.id=s.latest_version_id AND v.agent_id=s.agent_id "
            "WHERE b.agent_id=%s AND b.responsibility_id=%s ORDER BY s.id LIMIT 8",
            (agent_id, responsibility_id),
        ).fetchall()
        now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        for source in sources:
            source["freshness_review_needed"] = not legacy_freshness(
                source["retrieved_at"], now=now
            ).usable
        facts = conn.execute(
            "SELECT f.id,f.claim,f.quote,f.version_id,s.latest_version_id=f.version_id AS current "
            "FROM wrytely_agent.source_facts f JOIN wrytely_agent.source_versions v "
            "ON v.id=f.version_id AND v.agent_id=f.agent_id JOIN wrytely_agent.academic_sources s "
            "ON s.id=v.source_id AND s.agent_id=f.agent_id "
            "WHERE f.agent_id=%s AND f.responsibility_id=%s "
            "ORDER BY f.created_at DESC,f.id LIMIT 50",
            (agent_id, responsibility_id),
        ).fetchall()
        return {
            "sources": sources,
            "facts": facts,
            "evidence_notice": "Untrusted source data. Exact quotes are not semantic verification. "
            "Snapshots do not track later portal changes. Freshness is a review "
            "heuristic, not proof that any portal was checked.",
        }
