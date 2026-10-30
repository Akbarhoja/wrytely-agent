"""Bounded student projections; ownership filtering and reads share one snapshot."""

import json

SOURCE_FIELDS = (
    "s.id AS source_id,v.id AS version_id,v.title,v.reference,v.coverage,"
    "v.retrieved_at,v.external_revision"
)
SOURCE_JOIN = (
    " FROM wrytely_agent.academic_sources s "
    "JOIN wrytely_agent.agents a ON a.id=s.agent_id "
    "JOIN wrytely_agent.source_versions v ON v.id=s.latest_version_id AND v.agent_id=s.agent_id "
)


def student_json(value):
    # UUIDs and aware datetime fields are serialized consistently for app consumers.
    return json.loads(
        json.dumps(value, default=lambda x: x.isoformat() if hasattr(x, "isoformat") else str(x))
    )


class AcademicReadStore:
    def source_snapshots(self, user_id):
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT "
                + SOURCE_FIELDS
                + SOURCE_JOIN
                + "WHERE a.user_id=%s ORDER BY v.retrieved_at DESC,s.id DESC LIMIT 50",
                (user_id,),
            ).fetchall()
            return student_json(rows)

    def source_snapshot(self, user_id, source_id):
        with self.connection() as conn:
            row = conn.execute(
                "SELECT "
                + SOURCE_FIELDS
                + ",v.content"
                + SOURCE_JOIN
                + "WHERE a.user_id=%s AND s.id=%s",
                (user_id, source_id),
            ).fetchone()
            return student_json(row) if row else None

    def responsibility_artifacts(self, user_id, responsibility_id):
        with self.connection() as conn:
            # Keep ownership/existence and bounded artifact retrieval coherent.
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            owned = conn.execute(
                "SELECT r.id FROM wrytely_agent.responsibilities r "
                "JOIN wrytely_agent.agents a ON a.id=r.agent_id "
                "WHERE a.user_id=%s AND r.id=%s",
                (user_id, responsibility_id),
            ).fetchone()
            if not owned:
                return None
            rows = conn.execute(
                "SELECT f.id,f.task_id,f.draft->>'title' AS title,f.state,"
                "f.memory_revision<>r.memory_revision AS stale,f.created_at "
                "FROM wrytely_agent.artifacts f JOIN wrytely_agent.responsibilities r "
                "ON r.id=f.responsibility_id AND r.agent_id=f.agent_id "
                "WHERE r.id=%s ORDER BY f.created_at DESC,f.id DESC LIMIT 50",
                (owned["id"],),
            ).fetchall()
            return student_json(rows)

    def artifact_review(self, user_id, artifact_id):
        with self.connection() as conn:
            row = conn.execute(
                "SELECT f.id,f.responsibility_id,f.task_id,f.memory_revision,"
                "f.draft,f.state,f.created_at,f.memory_revision<>r.memory_revision AS stale,"
                "(SELECT c.report FROM wrytely_agent.artifact_checks c WHERE c.artifact_id=f.id "
                "ORDER BY c.created_at DESC,c.id DESC LIMIT 1) AS latest_check "
                "FROM wrytely_agent.artifacts f JOIN wrytely_agent.agents a ON a.id=f.agent_id "
                "JOIN wrytely_agent.responsibilities r ON r.id=f.responsibility_id "
                "AND r.agent_id=f.agent_id WHERE a.user_id=%s AND f.id=%s",
                (user_id, artifact_id),
            ).fetchone()
            if not row:
                return None
            report = row.pop("latest_check")
            return student_json({"artifact": row, "latest_check": report})
