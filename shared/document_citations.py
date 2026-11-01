"""Pure exact-reference validation shared by inspection and draft commit gates."""

import hashlib
from copy import deepcopy
from uuid import UUID

from contracts.source_digest import _text

_KEYS = {
    "object_id",
    "observation_id",
    "document_version_id",
    "segment_id",
    "slot",
    "page",
    "start",
    "end",
    "quote",
}


def _citation(value):
    if type(value) is not dict or value.keys() != _KEYS:
        raise ValueError("Exact document citation required")
    result = dict(value)
    for key in ("object_id", "observation_id", "document_version_id", "segment_id"):
        if not isinstance(result[key], (str, UUID)):
            raise ValueError("Invalid citation ID")
        try:
            result[key] = str(UUID(str(result[key])))
        except (ValueError, AttributeError):
            raise ValueError("Invalid citation ID") from None
    for key, low, high in (("slot", 0, 511), ("start", 0, 200000), ("end", 1, 200000)):
        if type(result[key]) is not int or not low <= result[key] <= high:
            raise ValueError("Invalid citation offset")
    page = result["page"]
    if page is not None and (type(page) is not int or not 1 <= page <= 200):
        raise ValueError("Invalid citation page")
    quote = result["quote"]
    if not isinstance(quote, str) or not 1 <= len(quote) <= 4000 or not quote.strip():
        raise ValueError("Bounded nonblank citation quote required")
    try:
        if _text(quote) != quote:
            raise ValueError("Citation must match original normalized text")
    except UnicodeError:
        raise ValueError("Invalid citation Unicode") from None
    if result["end"] - result["start"] != len(quote):
        raise ValueError("Citation offsets must span the exact quote")
    return result


def verify_citation_page(page, citation):
    citation = _citation(citation)
    # This output must come from the trusted Store read, not a model-supplied
    # excerpt or summary. Reject inconsistent identity; never fall back to latest.
    if any(
        str(page[k]) != citation[k] for k in ("object_id", "observation_id", "document_version_id")
    ):
        raise ValueError("Citation source mismatch")
    if len(page["sections"]) != 1:
        raise ValueError("Citation section unavailable")
    section = page["sections"][0]
    if (
        str(section["segment_id"]) != citation["segment_id"]
        or section["slot"] != citation["slot"]
        or section["page"] != citation["page"]
    ):
        raise ValueError("Citation section mismatch")
    text = section["text"]
    if hashlib.sha256(text.encode()).hexdigest() != section["text_sha256"]:
        raise ValueError("Citation section integrity mismatch")
    start, end = citation["start"] - section["start"], citation["end"] - section["start"]
    if not 0 <= start < end <= len(text) or text[start:end] != citation["quote"]:
        raise ValueError("Quote does not match original document section")
    return {
        "citation": citation,
        "quote_matches": True,
        "section_text_sha256": section["text_sha256"],
        "coverage": page["coverage"],
        "missing": list(page["missing"]),
        "historical": page["historical"],
        "freshness": deepcopy(page["freshness"]),
        "evidence_usable_for_inspection": bool(
            page["freshness"]["usable"]
            and page["coverage"] == "complete"
            and not page["missing"]
            and not page["historical"]
        ),
    }
