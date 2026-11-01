"""Internal bounded exact-quote discovery over the existing authorized section reader.

Inspection only: no model tool, source activation, task capability or drafting
permission. Matches never span sections; exhausting a range cannot establish
absence of policy. Every invocation requires pinned IDs and reauthorizes access.
"""

from copy import deepcopy

from contracts.source_digest import _text
from shared.canvas_reads import _bound, _uuid
from shared.document_citations import verify_citation_page
from shared.document_sections import DocumentSection


def _search(
    reader,
    object_id,
    observation_id,
    document_version_id,
    quote,
    first_slot,
    offset,
    max_pages,
    max_matches,
):
    object_id, observation_id, document_version_id = map(
        lambda value: str(_uuid(value)), (object_id, observation_id, document_version_id)
    )
    _bound(first_slot, 0, 512)
    _bound(offset, 0, 24000)
    _bound(max_pages, 1, 8)
    _bound(max_matches, 1, 30)
    if not isinstance(quote, str) or not 1 <= len(quote) <= 4000 or not quote.strip():
        raise ValueError("Bounded nonblank quote required")
    try:
        if _text(quote) != quote:
            raise ValueError("Quote must match original normalized text")
    except UnicodeError:
        raise ValueError("Invalid quote Unicode") from None
    pinned = dict(
        object_id=object_id, observation_id=observation_id, document_version_id=document_version_id
    )
    total_slots = None

    def read(slot, limit=20):
        nonlocal total_slots
        page = reader(
            object_id,
            observation_id=observation_id,
            document_version_id=document_version_id,
            first_slot=slot,
            limit=limit,
        )
        if any(str(page[k]) != value for k, value in pinned.items()):
            raise ValueError("Pinned search identity changed")
        _bound(page["total_slots"], 0, 512)
        if total_slots is not None and total_slots != page["total_slots"]:
            raise ValueError("Pinned document size changed")
        total_slots = page["total_slots"]
        return page

    matches, sections_scanned = [], 0
    cursor, local_offset = first_slot, offset
    continuation = None
    last_slot = first_slot
    for page_number in range(max_pages):
        page = read(cursor)
        sections = page["sections"]
        if not sections:
            if cursor != total_slots or local_offset or page["next_slot"] is not None:
                raise ValueError("Invalid empty section page")
            break
        if not 1 <= len(sections) <= 20:
            raise ValueError("Invalid section page size")
        for index, section in enumerate(sections):
            if section["slot"] != cursor + index:
                raise ValueError("Section search did not advance contiguously")
            validated = DocumentSection(
                **{k: section[k] for k in ("slot", "start", "end", "page", "text", "text_sha256")}
            )
            _bound(local_offset, 0, len(validated.text))
            sections_scanned += 1
            last_slot = section["slot"]
            position = validated.text.find(quote, local_offset)
            while position >= 0:
                citation = {
                    **pinned,
                    "segment_id": section["segment_id"],
                    "slot": section["slot"],
                    "page": section["page"],
                    "start": section["start"] + position,
                    "end": section["start"] + position + len(quote),
                    "quote": quote,
                }
                proof = verify_citation_page({**page, "sections": [section]}, citation)
                matches.append(proof)
                # Code-point +1 preserves overlapping matches, including repeated
                # single-character quotes. A plain slot continuation would skip them.
                position += 1
                if len(matches) == max_matches:
                    continuation = {"first_slot": section["slot"], "offset": position}
                    break
                position = validated.text.find(quote, position)
            local_offset = 0
            if continuation:
                break
        if continuation:
            break
        next_slot = page["next_slot"]
        if next_slot is None:
            if cursor + len(sections) != total_slots:
                raise ValueError("Incomplete section page without continuation")
            break
        if type(next_slot) is not int or next_slot != cursor + len(sections):
            raise ValueError("Invalid section continuation")
        cursor = next_slot
        continuation = {"first_slot": cursor, "offset": 0}
        # Continue within this invocation while its page budget remains.
        if page_number + 1 < max_pages:
            continuation = None

    # Reads are separate transactions: reauthorize after paging and propagate the
    # current coverage/freshness of this exact observation to every earlier match.
    final = read(last_slot, limit=1)
    metadata = {k: deepcopy(final[k]) for k in ("coverage", "missing", "historical", "freshness")}
    for proof in matches:
        proof.update(deepcopy(metadata))
        proof["evidence_usable_for_inspection"] = bool(
            metadata["freshness"]["usable"]
            and metadata["coverage"] == "complete"
            and not metadata["missing"]
            and not metadata["historical"]
        )
    return {
        **pinned,
        **metadata,
        "matches": matches,
        "next": continuation,
        "range_start": {"first_slot": first_slot, "offset": offset},
        "range_complete": continuation is None,
        "total_slots": total_slots,
        "sections_scanned": sections_scanned,
        "match_scope": "single_section_exact_quotes",
    }


def find_document_quotes(
    store,
    verified_user,
    object_id,
    *,
    observation_id,
    document_version_id,
    quote,
    first_slot=0,
    offset=0,
    max_pages=2,
    max_matches=10,
):
    """Server-verified user identity only; never accept a model-selected account."""
    return _search(
        lambda *args, **kwargs: store.read_canvas_document_sections(verified_user, *args, **kwargs),
        object_id,
        observation_id,
        document_version_id,
        quote,
        first_slot,
        offset,
        max_pages,
        max_matches,
    )


def find_document_quotes_for_task(
    store,
    lease,
    object_id,
    *,
    observation_id,
    document_version_id,
    quote,
    first_slot=0,
    offset=0,
    max_pages=2,
    max_matches=10,
):
    """Existing leased, responsibility-bound scope; no same-account blanket access."""
    return _search(
        lambda *args, **kwargs: store.read_canvas_document_sections_for_task(
            lease, *args, **kwargs
        ),
        object_id,
        observation_id,
        document_version_id,
        quote,
        first_slot,
        offset,
        max_pages,
        max_matches,
    )
