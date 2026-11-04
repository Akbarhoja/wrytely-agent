"""Source-bound preparation inside course supervision; no drafting/send authority."""

import hashlib
import json

from shared.canvas_reads import SourceRefreshRequired

NOTICE = (
    "Preparation checklist only, not a completed or checked assignment. Read the original "
    "instructions; missing material may change these steps. Perform physical work yourself "
    "and provide actual results. This checklist does not establish permission for "
    "AI-written submissions."
)


def pin(source):
    return {
        "object_id": source["object_id"],
        "observation_id": source["latest_observation_id"],
        "version_id": source["document_version_id"] or source["latest_version_id"],
    }


def preparation_record(decision, sources, inspections):
    """Only original quotes, current scoped originals and explicit student questions."""
    catalog = {s["object_id"]: s for s in sources}
    target = catalog.get(decision.object_id)
    if not target or not target["inspection_ready"]:
        raise SourceRefreshRequired()
    fields = target["fields"]
    types = fields.get("submission_types")
    ordinary = {"online_upload", "online_text_entry", "online_url", "on_paper", "none"}
    if (
        target["kind"] != "assignment"
        or not isinstance(types, list)
        or not types
        or not set(types) <= ordinary
    ):
        raise ValueError("Preparation requires an ordinary assignment")
    required = {decision.object_id, *(x.object_id for x in decision.preparation.excerpts)}
    # Policy is read as original evidence, not converted into a permission assertion.
    required.update(s["object_id"] for s in sources if s["kind"] == "syllabus")
    if len(required) > 8:
        raise ValueError("Preparation evidence scope limit")
    evidence = []
    texts = {}
    for object_id in sorted(required):
        source, inspected = catalog.get(object_id), inspections.get(object_id)
        if not source or not source["inspection_ready"] or not inspected:
            raise ValueError("Preparation requires current inspected originals")
        if str(inspected.get("observation_id")) != source["latest_observation_id"]:
            raise SourceRefreshRequired()
        if source["document_version_id"] and (
            str(inspected.get("document_version_id")) != source["document_version_id"]
        ):
            raise SourceRefreshRequired()
        if object_id != decision.object_id and source["kind"] != "syllabus":
            if source["kind"] != "file" or (
                f"assignment:{target['provider_id']}" not in source["fields"].get("linked_from", [])
            ):
                raise ValueError("Preparation evidence must belong to the target")
        sections = inspected.get("sections", [inspected.get("section", {})])
        texts[object_id] = [s.get("text", "") for s in sections]
        evidence.append(
            {
                **pin(source),
                "coverage": source["coverage"],
                "resource_coverage": source["resource_coverage"],
                "missing": source["missing"],
                "unread_continuation": inspected.get("next_slot") is not None
                or inspected.get("section", {}).get("next_offset") is not None,
            }
        )
    for item in decision.preparation.excerpts:
        if not item.quote.strip() or not any(item.quote in text for text in texts[item.object_id]):
            raise ValueError("Preparation quote must match inspected original text")
    fingerprint = hashlib.sha256(
        json.dumps([decision.object_id, evidence], sort_keys=True).encode()
    ).hexdigest()
    return {
        "key": fingerprint,
        "object_id": decision.object_id,
        "title": target["title"],
        "kind": "preparation_checklist",
        "notice": NOTICE,
        "excerpts": [x.model_dump() for x in decision.preparation.excerpts],
        "questions": decision.preparation.questions,
        "evidence": evidence,
    }


def preparation_projection(records, sources, *, active):
    catalog = {s["object_id"]: s for s in sources}
    return [
        {
            **record,
            "current": bool(
                active
                and all(
                    (source := catalog.get(p["object_id"]))
                    and source["inspection_ready"]
                    and pin(source) == {k: p[k] for k in pin(source)}
                    for p in record["evidence"]
                )
            ),
        }
        for record in records
    ]
