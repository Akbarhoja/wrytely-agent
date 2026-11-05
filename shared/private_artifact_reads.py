"""Owned v2 student reads, reusing original evidence and current connection authority.

No lease, inference, delivery or mutation. Public v1 projections remain unchanged.
"""

from dataclasses import asdict
from datetime import UTC

from contracts.document_artifacts import DraftArtifactV2
from shared.canvas_reads import SourceRefreshRequired, _bound, _uuid
from shared.document_citations import verify_citation_page
from shared.document_sections import page_document_sections
from shared.freshness import legacy_freshness
from shared.private_artifact_projection import LIMITS, bounded, cursor, project_check, status


class PrivateArtifactReadStore:
    def _private_duty(self, conn, user, duty_id):
        agent, _ = self._read_identity(conn, user, None)
        duty = conn.execute(
            "SELECT * FROM wrytely_agent.responsibilities WHERE agent_id=%s AND id=%s FOR UPDATE",
            (agent, _uuid(duty_id)),
        ).fetchone()
        if not duty:
            raise LookupError("Not found")
        return agent, duty

    def _private_artifact(self, conn, user, artifact_id):
        agent, _ = self._read_identity(conn, user, None)
        row = conn.execute(
            "SELECT * FROM wrytely_agent.artifacts "
            "WHERE agent_id=%s AND id=%s AND evidence_schema=2",
            (agent, _uuid(artifact_id)),
        ).fetchone()
        if not row:
            raise LookupError("Not found")
        _, duty = self._private_duty(conn, user, row["responsibility_id"])
        draft = DraftArtifactV2.model_validate(row["draft"]).model_dump(mode="json")
        return row, duty, draft

    def list_private_artifacts_v2(self, verified_user, responsibility_id, *, limit=20, before=None):
        _bound(limit, 1, 50)
        anchor = cursor(before)
        with self.connection() as conn:
            agent, duty = self._private_duty(conn, verified_user, responsibility_id)
            clause = "AND (f.created_at,f.id)<(%s,%s) " if anchor else ""
            rows = conn.execute(
                "SELECT f.id,f.task_id,f.created_at,f.state AS saved_state,"
                "f.memory_revision<>%s AS memory_stale FROM wrytely_agent.artifacts f "
                "WHERE f.agent_id=%s AND f.responsibility_id=%s AND f.evidence_schema=2 "
                + clause
                + "ORDER BY f.created_at DESC,f.id DESC LIMIT %s",
                (duty["memory_revision"], agent, duty["id"], *(anchor or ()), limit + 1),
            ).fetchall()
            following = None
            if len(rows) > limit:
                following = {
                    "created_at": rows[limit - 1]["created_at"].astimezone(UTC),
                    "id": rows[limit - 1]["id"],
                }
            return bounded(
                dict(schema_version=2, artifacts=rows[:limit], limit=limit, next=following)
            )

    def _private_scope(self, conn, artifact):
        """Check even uncited explicit bindings, without requiring an active duty."""
        bindings = conn.execute(
            "SELECT * FROM wrytely_agent.responsibility_canvas_objects "
            "WHERE agent_id=%s AND responsibility_id=%s ORDER BY object_id",
            (artifact["agent_id"], artifact["responsibility_id"]),
        ).fetchall()
        connections = []
        for binding in bindings:
            connection, _, _ = self._document_observation(
                conn, artifact["agent_id"], None, binding["object_id"], None
            )
            if (connection["id"], connection["generation"]) != (
                binding["connection_id"],
                binding["connection_generation"],
            ):
                raise SourceRefreshRequired()
            self._finish_canvas_read(conn, None, {}, connection)
            connections.append(connection)
        return connections

    def _private_document_source(self, conn, artifact, reference):
        agent, duty = artifact["agent_id"], artifact["responsibility_id"]
        connection, row, projection = self._document_observation(
            conn, agent, duty, reference["object_id"], reference["observation_id"], task=True
        )
        if not conn.execute(
            "SELECT 1 FROM wrytely_agent.canvas_document_bindings WHERE agent_id=%s "
            "AND object_id=%s AND observation_id=%s AND document_version_id=%s",
            (
                agent,
                reference["object_id"],
                reference["observation_id"],
                reference["document_version_id"],
            ),
        ).fetchone():
            raise SourceRefreshRequired()
        document, stored = self._load_canvas_document(
            conn, agent, reference["object_id"], reference["document_version_id"]
        )
        source = dict(
            kind="canvas_document",
            object_id=reference["object_id"],
            observation_id=reference["observation_id"],
            document_version_id=reference["document_version_id"],
            coverage=projection["coverage"],
            missing=list(row["private_payload"]["missing"]),
            historical=projection["historical"],
            freshness=projection["freshness"],
        )
        return source, connection, document, stored

    def _private_legacy_source(self, conn, artifact, reference):
        agent, duty = artifact["agent_id"], artifact["responsibility_id"]
        version = conn.execute(
            "SELECT v.*,s.latest_version_id FROM wrytely_agent.source_versions v "
            "JOIN wrytely_agent.academic_sources s ON s.agent_id=v.agent_id AND s.id=v.source_id "
            "WHERE v.agent_id=%s AND v.id=%s",
            (agent, reference["version_id"]),
        ).fetchone()
        if not version:
            raise SourceRefreshRequired()
        bound = conn.execute(
            "SELECT 1 FROM wrytely_agent.responsibility_sources "
            "WHERE agent_id=%s AND responsibility_id=%s AND source_id=%s",
            (agent, duty, version["source_id"]),
        ).fetchone()
        mapped = conn.execute(
            "SELECT id FROM wrytely_agent.canvas_evidence_objects "
            "WHERE agent_id=%s AND source_id=%s ORDER BY id",
            (agent, version["source_id"]),
        ).fetchall()
        now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        source = dict(
            kind="legacy",
            version_id=reference["version_id"],
            title=version["title"],
            content=version["content"],
            historical=version["id"] != version["latest_version_id"],
            freshness=asdict(legacy_freshness(version["retrieved_at"], now=now)),
        )
        connections = []
        if not bound and not mapped:
            raise SourceRefreshRequired()
        for obj in mapped:
            observed = conn.execute(
                "SELECT id FROM wrytely_agent.canvas_evidence_observations WHERE agent_id=%s "
                "AND object_id=%s AND version_id=%s ORDER BY received_at DESC,id DESC LIMIT 1",
                (agent, obj["id"], version["id"]),
            ).fetchone()
            if not observed:
                raise SourceRefreshRequired()
            connection, row, projection = self._document_observation(
                conn, agent, duty, obj["id"], observed["id"], task=True
            )
            if row["private_payload"]["content"] != version["content"]:
                raise SourceRefreshRequired()
            source.update(
                coverage=projection["coverage"],
                missing=list(row["private_payload"]["missing"]),
                historical=projection["historical"],
                freshness=projection["freshness"],
            )
            connections.append(connection)
        return source, connections

    def _private_proof(self, conn, artifact, reference, cache):
        if reference["kind"] == "legacy":
            key = ("legacy", reference["version_id"])
            if key not in cache:
                source, connections = self._private_legacy_source(conn, artifact, reference)
                cache[key] = dict(source=source, connections=connections, reference=reference)
            result = cache[key]
            return dict(
                source=result["source"],
                quote_matches=reference["quote"] in result["source"]["content"],
            )
        key = tuple(reference[k] for k in ("object_id", "observation_id", "document_version_id"))
        if key not in cache:
            source, connection, document, stored = self._private_document_source(
                conn, artifact, reference
            )
            cache[key] = dict(
                source=source,
                connections=[connection],
                document=document,
                stored=stored,
                reference=reference,
            )
        result = cache[key]
        source, document, stored = result["source"], result["document"], result["stored"]
        slot = reference["slot"]
        section = (
            []
            if slot >= len(document.sections)
            else [dict(segment_id=stored[slot]["id"], **asdict(document.sections[slot]))]
        )
        try:
            verify_citation_page(
                {**source, "sections": section}, {k: v for k, v in reference.items() if k != "kind"}
            )
            matches = True
        except ValueError:
            matches = False
        return dict(source=source, quote_matches=matches)

    @staticmethod
    def _private_check(conn, artifact, check_id=None):
        extra = "AND id=%s " if check_id is not None else ""
        row = conn.execute(
            "SELECT * FROM wrytely_agent.artifact_checks WHERE artifact_id=%s "
            + extra
            + "ORDER BY created_at DESC,id DESC LIMIT 1",
            (artifact["id"], *([_uuid(check_id)] if check_id is not None else [])),
        ).fetchone()
        return project_check(row, artifact["memory_revision"], len(artifact["draft"]["citations"]))

    def _private_proofs(self, conn, artifact, draft, check):
        cache = {}
        refs = [c["evidence"] for c in draft["citations"]]
        if check:
            report = check["report"]
            refs += [report["policy"]["evidence"], *(r["evidence"] for r in report["rubric"])]
        try:
            self._private_scope(conn, artifact)
            proofs = [self._private_proof(conn, artifact, ref, cache) for ref in refs]
        except LookupError:
            raise SourceRefreshRequired() from None
        return proofs, cache

    def _finish_private(self, conn, artifact, duty, proofs, cache, check):
        try:
            live_connections = self._private_scope(conn, artifact)
            for result in cache.values():
                ref = result["reference"]
                if ref["kind"] == "legacy":
                    current, connections = self._private_legacy_source(conn, artifact, ref)
                    if current["content"] != result["source"]["content"]:
                        raise SourceRefreshRequired()
                    result["source"].update(current)
                else:
                    connection, row, projection = self._document_observation(
                        conn,
                        artifact["agent_id"],
                        artifact["responsibility_id"],
                        ref["object_id"],
                        ref["observation_id"],
                        task=True,
                    )
                    if str(row["document_version_id"]) != ref["document_version_id"]:
                        raise SourceRefreshRequired()
                    result["source"].update(
                        coverage=projection["coverage"],
                        missing=list(row["private_payload"]["missing"]),
                        historical=projection["historical"],
                        freshness=projection["freshness"],
                    )
                    connections = [connection]
                for connection in connections:
                    self._finish_canvas_read(conn, None, {}, connection)
                    live_connections.append(connection)
        except LookupError:
            raise SourceRefreshRequired() from None
        duty.update(
            conn.execute(
                "SELECT memory_revision,status FROM wrytely_agent.responsibilities WHERE id=%s",
                (duty["id"],),
            ).fetchone()
        )
        now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        if any(c["credential_expires_at"] <= now for c in live_connections):
            raise SourceRefreshRequired()
        return status(
            proofs,
            now=now,
            memory_stale=artifact["memory_revision"] != duty["memory_revision"],
            check_available=check is not None,
        )

    def read_private_artifact_v2(self, verified_user, artifact_id):
        with self.connection() as conn:
            artifact, duty, draft = self._private_artifact(conn, verified_user, artifact_id)
            check = self._private_check(conn, artifact)
            proofs, cache = self._private_proofs(conn, artifact, draft, check)
            # Bound serialization before the final clock/authority checks too.
            bounded(dict(draft=draft, check=check))
            evidence = self._finish_private(conn, artifact, duty, proofs, cache, check)
            agent = conn.execute(
                "SELECT paused FROM wrytely_agent.agents WHERE id=%s", (artifact["agent_id"],)
            ).fetchone()
            return bounded(
                dict(
                    schema_version=2,
                    artifact=dict(
                        id=artifact["id"],
                        responsibility_id=duty["id"],
                        task_id=artifact["task_id"],
                        created_at=artifact["created_at"],
                        memory_revision=artifact["memory_revision"],
                        saved_state=artifact["state"],
                        memory_stale=artifact["memory_revision"] != duty["memory_revision"],
                        draft=draft,
                    ),
                    controls=dict(
                        agent_paused=agent["paused"], responsibility_status=duty["status"]
                    ),
                    latest_check=check,
                    evidence_status=evidence,
                    limits=LIMITS,
                )
            )

    def read_private_artifact_evidence_v2(
        self, verified_user, artifact_id, *, group, index, check_id=None, first_slot=0, limit=1
    ):
        if group not in ("citation", "policy", "rubric"):
            raise ValueError("Invalid evidence group")
        _bound(index, 0, 29)
        _bound(first_slot, 0, 512)
        _bound(limit, 1, 20)
        if (group == "citation" and check_id is not None) or (
            group != "citation" and check_id is None
        ):
            raise ValueError("Exact check selection required")
        with self.connection() as conn:
            artifact, duty, draft = self._private_artifact(conn, verified_user, artifact_id)
            check = self._private_check(conn, artifact, check_id)
            if group != "citation" and check is None:
                raise LookupError("Not found")
            items = (
                draft["citations"]
                if group == "citation"
                else (
                    [check["report"]["policy"]] if group == "policy" else check["report"]["rubric"]
                )
            )
            if index >= len(items):
                raise LookupError("Not found")
            reference = items[index]["evidence"]
            proofs, cache = self._private_proofs(conn, artifact, draft, check)
            proof = self._private_proof(conn, artifact, reference, cache)
            source = dict(proof["source"])
            if reference["kind"] == "legacy":
                if first_slot != 0 or limit != 1:
                    raise ValueError("Legacy evidence is not section-paged")
            else:
                result = cache[
                    tuple(
                        reference[k] for k in ("object_id", "observation_id", "document_version_id")
                    )
                ]
                page = page_document_sections(
                    result["document"], first_slot=first_slot, limit=limit
                )
                source.update(
                    sections=[
                        dict(segment_id=result["stored"][s.slot]["id"], **asdict(s))
                        for s in page.sections
                    ],
                    next_slot=page.next_slot,
                    total_slots=page.total_slots,
                )
            bounded(dict(source=source, reference=reference))
            evidence = self._finish_private(conn, artifact, duty, proofs, cache, check)
            source.update(proof["source"])
            return bounded(
                dict(
                    schema_version=2,
                    artifact_id=artifact["id"],
                    group=group,
                    index=index,
                    check_id=check["id"] if group != "citation" else None,
                    reference=reference,
                    quote_matches=proof["quote_matches"],
                    source=source,
                    evidence_status=evidence,
                )
            )
