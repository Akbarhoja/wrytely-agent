"""Internal complete, bounded original context for explicitly scoped v2 drafting."""

from dataclasses import asdict

from shared.academic_reads import student_json
from shared.canvas_reads import SourceRefreshRequired
from shared.freshness import legacy_freshness
from shared.typed_evidence import EvidenceContextLimit, check_context, source_text


class TypedEvidenceStore:
    def _typed_drafting_context(self, conn, agent, duty):
        from shared.typed_evidence import MAX_CONTEXT_CHARACTERS

        sources, legacy_ids = [], set()
        now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        for row in conn.execute(
            "SELECT v.* FROM wrytely_agent.responsibility_sources b "
            "JOIN wrytely_agent.academic_sources s ON s.id=b.source_id AND s.agent_id=b.agent_id "
            "JOIN wrytely_agent.source_versions v ON v.id=s.latest_version_id "
            "AND v.agent_id=s.agent_id "
            "WHERE b.agent_id=%s AND b.responsibility_id=%s ORDER BY v.id",
            (agent, duty),
        ).fetchall():
            freshness = legacy_freshness(row["retrieved_at"], now=now)
            metadata = dict(freshness=asdict(freshness))
            mapped = conn.execute(
                "SELECT id FROM wrytely_agent.canvas_evidence_objects "
                "WHERE agent_id=%s AND source_id=%s",
                (agent, row["source_id"]),
            ).fetchall()
            for obj in mapped:
                connection, observed, projection = self._document_observation(
                    conn, agent, duty, obj["id"], None, task=True, purpose="draft"
                )
                if observed["version_id"] != row["id"]:
                    raise SourceRefreshRequired()
                metadata = dict(
                    freshness=projection["freshness"],
                    coverage=projection["coverage"],
                    historical=projection["historical"],
                    missing=observed["private_payload"]["missing"],
                    fields=observed["private_payload"]["fields"],
                    authorization_expires_at=connection["credential_expires_at"],
                )
                self._finish_canvas_read(conn, None, {}, connection)
            sources.append(
                dict(
                    kind="legacy",
                    version_id=row["id"],
                    content=row["content"],
                    title=row["title"],
                    **metadata,
                )
            )
            legacy_ids.add(row["id"])
        bindings = conn.execute(
            "SELECT object_id,connection_generation FROM "
            "wrytely_agent.responsibility_canvas_objects "
            "WHERE agent_id=%s AND responsibility_id=%s ORDER BY object_id",
            (agent, duty),
        ).fetchall()
        connections = {}
        for binding in bindings:
            connection, row, projection = self._document_observation(
                conn, agent, duty, binding["object_id"], None, task=True, purpose="draft"
            )
            if connection["generation"] != binding["connection_generation"]:
                raise SourceRefreshRequired()
            metadata = dict(
                coverage=projection["coverage"],
                missing=row["private_payload"]["missing"],
                historical=projection["historical"],
                freshness=projection["freshness"],
                authorization_expires_at=connection["credential_expires_at"],
            )
            if row["private_payload"]["kind"] == "document":
                root = row["document_version_id"]
                if root is None:
                    raise SourceRefreshRequired()
                document, stored = self._load_canvas_document(conn, agent, row["id"], root)
                sources.append(
                    dict(
                        kind="canvas_document",
                        fields=row["private_payload"]["fields"]["object_fields"],
                        object_id=row["id"],
                        observation_id=row["observation_id"],
                        document_version_id=root,
                        title=row["title"],
                        sections=[
                            {"segment_id": stored[s.slot]["id"], **asdict(s)}
                            for s in document.sections
                        ],
                        **metadata,
                    )
                )
            else:
                version = conn.execute(
                    "SELECT * FROM wrytely_agent.source_versions WHERE agent_id=%s AND id=%s",
                    (agent, row["version_id"]),
                ).fetchone()
                if not version or version["content"] != row["private_payload"]["content"]:
                    raise SourceRefreshRequired()
                # A real observed text version is readable by explicit object scope;
                # never advance its legacy source pointer or manufacture a version.
                if version["id"] in legacy_ids:
                    sources = [s for s in sources if s.get("version_id") != version["id"]]
                sources.append(
                    dict(
                        kind="legacy",
                        fields=row["private_payload"]["fields"],
                        version_id=version["id"],
                        content=version["content"],
                        title=version["title"],
                        **metadata,
                    )
                )
                legacy_ids.add(version["id"])
            connections[str(connection["id"])] = connection
            if sum(len(source_text(s)) for s in sources) > MAX_CONTEXT_CHARACTERS:
                raise EvidenceContextLimit()
        for connection in connections.values():
            self._finish_canvas_read(conn, None, {}, connection)
        try:
            check_context(
                sources, now=conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            )
        except ValueError:
            raise SourceRefreshRequired() from None
        return student_json(sources)
