"""Internal literal-term discovery; originals remain the authority, not search hits.

Uses the existing exact-quote pager and its final scoped authorization check.
No public/model tool, automatic inference, source activation or permission grant.
"""

import re

from contracts.source_digest import _text
from runtime.document_quote_search import _search


def _terms(terms, case_sensitive):
    if type(case_sensitive) is not bool or type(terms) not in (list, tuple):
        raise ValueError("Literal terms and exact boolean required")
    if not 1 <= len(terms) <= 8:
        raise ValueError("One to eight literal terms required")
    result = []
    for term in terms:
        if type(term) is not str or not 1 <= len(term) <= 128 or not term.strip():
            raise ValueError("Bounded nonblank literal term required")
        try:
            if _text(term) != term:
                raise ValueError("Normalized literal term required")
        except UnicodeError:
            raise ValueError("Invalid term Unicode") from None
        if term in result:
            raise ValueError("Duplicate literal term")
        result.append(term)
    # Longest wins at the same offset, independent of caller order. Escaping means
    # user terms are never regex programs. Python regex spans remain code points;
    # no case-folded copy can shift original offsets (e.g. ß versus ss).
    pattern = re.compile(
        "|".join(re.escape(t) for t in sorted(result, key=lambda t: (-len(t), t))),
        0 if case_sensitive else re.IGNORECASE,
    )
    return tuple(result), pattern


def _find(reader, object_id, observation_id, document_version_id, terms, case_sensitive, bounds):
    terms, pattern = _terms(terms, case_sensitive)

    def match(text, start):
        result = pattern.search(text, start)
        return None if result is None else result.span()

    result = _search(
        reader,
        object_id,
        observation_id,
        document_version_id,
        terms[0],
        bounds["first_slot"],
        bounds["offset"],
        bounds["max_pages"],
        bounds["max_matches"],
        matcher=match,
    )
    result.update(
        match_scope="single_section_literal_terms",
        terms=list(terms),
        case_sensitive=case_sensitive,
        limits=(
            "Literal discovery only; no-match cannot establish absence of policy or requirements."
        ),
    )
    return result


def find_document_terms(
    store,
    verified_user,
    object_id,
    *,
    observation_id,
    document_version_id,
    terms,
    case_sensitive=False,
    first_slot=0,
    offset=0,
    max_pages=2,
    max_matches=10,
):
    """Session-derived identity. Open a hit's original section before interpretation."""
    return _find(
        lambda *a, **k: store.read_canvas_document_sections(verified_user, *a, **k),
        object_id,
        observation_id,
        document_version_id,
        terms,
        case_sensitive,
        dict(first_slot=first_slot, offset=offset, max_pages=max_pages, max_matches=max_matches),
    )


def find_document_terms_for_task(
    store,
    lease,
    object_id,
    *,
    observation_id,
    document_version_id,
    terms,
    case_sensitive=False,
    first_slot=0,
    offset=0,
    max_pages=2,
    max_matches=10,
):
    """Existing leased task bindings only; no same-account blanket course access."""
    return _find(
        lambda *a, **k: store.read_canvas_document_sections_for_task(lease, *a, **k),
        object_id,
        observation_id,
        document_version_id,
        terms,
        case_sensitive,
        dict(first_slot=first_slot, offset=offset, max_pages=max_pages, max_matches=max_matches),
    )
