"""Internal exact document-quote checks over existing authorized pinned reads.

No model tool, API, persistence, source activation or drafting permission. Caller
supplies a server-verified user or current task lease; models never choose identity.
Results are inspection-time evidence, not authority for a later draft/send commit.
"""

from shared.document_citations import _citation, verify_citation_page


def _verify(store, user, lease, citation):
    citation = _citation(citation)
    args = dict(
        observation_id=citation["observation_id"],
        document_version_id=citation["document_version_id"],
        first_slot=citation["slot"],
        limit=1,
    )
    if lease is None:
        page = store.read_canvas_document_sections(user, citation["object_id"], **args)
    else:
        page = store.read_canvas_document_sections_for_task(lease, citation["object_id"], **args)
    return verify_citation_page(page, citation)


def verify_document_citation(store, verified_user, citation):
    """Internal session-derived identity; exact quote can match incomplete evidence."""
    return _verify(store, verified_user, None, citation)


def verify_document_citation_for_task(store, lease, citation):
    """Current leased, task-bound scope only; no semester-wide capability inferred."""
    return _verify(store, None, lease, citation)
