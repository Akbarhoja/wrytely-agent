"""Internal draft-document provenance checked within the caller's agent transaction.

No activation, provider IO or additional access grant. Document-only publications
without responsibility bindings remain unavailable to tasks.
"""

from dataclasses import asdict
from uuid import UUID

from shared.canvas_reads import SourceRefreshRequired
from shared.document_citations import _citation, verify_citation_page


def draft_document_citations(draft, citations):
    if type(citations) is not list or len(citations) > 30:
        raise ValueError("Bounded document citations required")
    if citations and len(citations) != len(draft["citations"]):
        raise ValueError("Every draft citation requires document provenance")
    result = [_citation(c) for c in citations]
    if any(c["quote"] != draft["citations"][i]["quote"] for i, c in enumerate(result)):
        raise ValueError("Document quote differs from draft citation")
    return result


def check_artifact_documents(store, conn, artifact):
    """Caller holds the owned agent fence; fresh checks never trust stored reports."""
    citations = draft_document_citations(artifact["draft"], artifact["document_citations"])
    proofs = []
    connections = {}
    for index, citation in enumerate(citations):
        connection, row, projection = store._document_observation(
            conn,
            artifact["agent_id"],
            artifact["responsibility_id"],
            citation["object_id"],
            citation["observation_id"],
            task=True,
            purpose="draft",
        )
        if row["version_id"] != UUID(artifact["draft"]["citations"][index]["version_id"]):
            raise ValueError("Document observation differs from cited source version")
        if not conn.execute(
            "SELECT 1 FROM wrytely_agent.canvas_document_bindings WHERE agent_id=%s "
            "AND object_id=%s AND observation_id=%s AND document_version_id=%s",
            (
                artifact["agent_id"],
                citation["object_id"],
                citation["observation_id"],
                citation["document_version_id"],
            ),
        ).fetchone():
            raise LookupError("Not found")
        document, stored = store._load_canvas_document(
            conn, artifact["agent_id"], citation["object_id"], citation["document_version_id"]
        )
        slot = citation["slot"]
        sections = (
            []
            if slot >= len(document.sections)
            else [{"segment_id": stored[slot]["id"], **asdict(document.sections[slot])}]
        )
        proof = verify_citation_page(
            {
                "object_id": citation["object_id"],
                "observation_id": citation["observation_id"],
                "document_version_id": citation["document_version_id"],
                "sections": sections,
                "coverage": projection["coverage"],
                "missing": row["private_payload"]["missing"],
                "historical": projection["historical"],
                "freshness": projection["freshness"],
            },
            citation,
        )
        # Inspection usability is insufficient: projection above uses server-owned
        # draft-purpose (6h) freshness, never a caller/model-selected TTL.
        proof["evidence_usable_for_draft"] = proof.pop("evidence_usable_for_inspection")
        if not proof["evidence_usable_for_draft"]:
            raise SourceRefreshRequired()
        connections[str(connection["id"])] = connection
        proofs.append(proof)
    now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
    if any(p["freshness"]["expires_at"] < now for p in proofs):
        raise SourceRefreshRequired()
    for connection in connections.values():
        store._finish_canvas_read(conn, None, {}, connection)
    return proofs
