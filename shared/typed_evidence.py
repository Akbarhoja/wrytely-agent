"""Resolve exact v2 references against a trusted, task-authorized original context.

The context must come from Store, never from a model or browser. Final persistence
always reloads authorization and originals inside its own fenced transaction.
"""

import json
from datetime import UTC, datetime

from shared.document_citations import verify_citation_page

MAX_CONTEXT_CHARACTERS = 80000


class EvidenceContextLimit(Exception):
    """More original-source investigation is needed; never truncate policy evidence."""


def source_text(source):
    if source["kind"] == "legacy":
        return source["content"]
    return "".join(s["text"] for s in source["sections"])


def check_context(sources, *, now=None):
    now = datetime.now(UTC) if now is None else now
    if not 1 <= len(sources) <= 16:
        raise ValueError("Bounded complete source context required")
    if (
        sum(len(source_text(s)) for s in sources) > MAX_CONTEXT_CHARACTERS
        or len(json.dumps(sources, ensure_ascii=False, default=str).encode()) > 512000
    ):
        raise EvidenceContextLimit()
    for source in sources:
        freshness = source["freshness"]
        expires = freshness.get("expires_at")
        if isinstance(expires, str):
            expires = datetime.fromisoformat(expires)
        authorization_expires = source.get("authorization_expires_at", expires)
        if isinstance(authorization_expires, str):
            authorization_expires = datetime.fromisoformat(authorization_expires)
        if (
            not isinstance(authorization_expires, datetime)
            or authorization_expires.tzinfo is None
            or authorization_expires < now
            or freshness["usable"] is not True
            or not isinstance(expires, datetime)
            or expires.tzinfo is None
            or expires < now
            or source.get("missing")
            or source.get("historical", False)
        ):
            raise ValueError("Original evidence is unavailable or stale")


def resolve_evidence(reference, sources):
    check_context(sources)
    ref = reference.model_dump(mode="json")
    if ref["kind"] == "legacy":
        rows = [
            s
            for s in sources
            if s["kind"] == "legacy" and str(s["version_id"]) == ref["version_id"]
        ]
        if len(rows) != 1 or ref["quote"] not in rows[0]["content"]:
            raise ValueError("Exact current scoped legacy evidence required")
        return {"evidence": ref, "quote_matches": True, "evidence_usable_for_draft": True}, rows[0]
    rows = [
        s
        for s in sources
        if s["kind"] == "canvas_document"
        and all(str(s[k]) == ref[k] for k in ("object_id", "observation_id", "document_version_id"))
    ]
    if len(rows) != 1:
        raise ValueError("Exact current scoped document required")
    source = rows[0]
    sections = [s for s in source["sections"] if s["slot"] == ref["slot"]]
    proof = verify_citation_page(
        {**source, "sections": sections}, {k: v for k, v in ref.items() if k != "kind"}
    )
    if not proof.pop("evidence_usable_for_inspection"):
        raise ValueError("Complete draft evidence required")
    proof["evidence_usable_for_draft"] = True
    proof["evidence"] = ref
    return proof, source
