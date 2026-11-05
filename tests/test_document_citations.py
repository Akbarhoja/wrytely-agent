"""Internal citation checks with real scoped reads and synthetic source text only."""

import hashlib
from copy import deepcopy
from uuid import uuid4

import pytest
import test_canvas_evidence as evidence
import test_canvas_reads as reads
import test_canvas_sync as sync
from test_canvas_documents import read, save
from test_canvas_sync import device as device
from test_planner import plan
from test_worker import ScriptedModel

from runtime.document_citations import verify_document_citation, verify_document_citation_for_task
from runtime.worker import run_once
from shared.canvas_reads import SourceRefreshRequired
from shared.config import Settings
from shared.db import LeaseLost
from shared.document_sections import DocumentSection, DocumentSections, split_document_text

TEXT = "Alpha Café 📚 evidence.\nSecond line. Café."


def source(device, text=TEXT):
    obj = reads.collected(device)[0]
    version = save(device, obj, split_document_text(text))
    return obj, version


def cite(device, obj, version, *, quote="Café 📚", slot=0, offset=None):
    page = read(device, obj, version, first_slot=slot, limit=1)
    section = page["sections"][0]
    local = section["text"].index(quote) if offset is None else offset
    return {
        "object_id": str(obj["id"]),
        "observation_id": str(obj["latest_observation_id"]),
        "document_version_id": str(version),
        "segment_id": section["segment_id"],
        "slot": slot,
        "page": section["page"],
        "start": section["start"] + local,
        "end": section["start"] + local + len(quote),
        "quote": quote,
    }


def verify(device, citation, user="user_alice"):
    return verify_document_citation(device[0], user, citation)


def test_exact_unicode_quote_retains_original_reference_and_returns_no_unquoted_body(device):
    obj, version = source(device)
    citation = cite(device, obj, version)
    result = verify(device, citation)
    assert result["quote_matches"] and result["evidence_usable_for_inspection"]
    assert result["citation"] == citation
    assert result["citation"]["end"] - result["citation"]["start"] == 6
    assert result["section_text_sha256"] == hashlib.sha256(TEXT.encode()).hexdigest()
    assert "Second line" not in str(result)
    assert all(
        secret not in str(result)
        for secret in ("ingestion_bearer", "subject", "checkpoint", "lease_token")
    )
    citation["quote"] = "mutated caller"
    assert result["citation"]["quote"] == "Café 📚"


def test_repeated_quote_is_pinned_to_explicit_occurrence(device):
    obj, version = source(device)
    first = cite(device, obj, version, quote="Café")
    second = cite(device, obj, version, quote="Café", offset=TEXT.rindex("Café"))
    assert verify(device, first)["quote_matches"] and verify(device, second)["quote_matches"]
    assert first["start"] != second["start"]


def test_quote_in_later_long_section_uses_original_global_codepoint_offsets(device):
    text = "x" * 24000 + "target📚" + "y" * 30000
    obj, version = source(device, text)
    citation = cite(device, obj, version, quote="target📚", slot=1)
    assert citation["start"] == 24000
    assert verify(device, citation)["quote_matches"]
    wrong = deepcopy(citation)
    wrong.update(start=0, end=len(wrong["quote"]))
    with pytest.raises(ValueError, match="original document"):
        verify(device, wrong)


def test_pdf_page_provenance_is_exact(device):
    obj = reads.collected(device)[0]
    sections = (
        DocumentSection(0, 0, 1, 1, "A", hashlib.sha256(b"A").hexdigest()),
        DocumentSection(1, 1, 4, 2, "\n📚B", hashlib.sha256("\n📚B".encode()).hexdigest()),
    )
    version = save(device, obj, DocumentSections(sections, 4, 2), format="pdf_text")
    citation = cite(device, obj, version, quote="📚", slot=1)
    assert citation["page"] == 2 and citation["start"] == 2
    assert verify(device, citation)["quote_matches"]
    with pytest.raises(ValueError, match="section mismatch"):
        verify(device, citation | {"page": 1})


@pytest.mark.parametrize(
    "field,value",
    [
        ("slot", True),
        ("slot", -1),
        ("slot", 512),
        ("start", True),
        ("start", -1),
        ("end", 200001),
        ("end", "10"),
        ("page", True),
        ("page", 0),
        ("page", 201),
        ("quote", ""),
        ("quote", " "),
        ("quote", "x" * 4001),
        ("quote", "Cafe\u0301"),
        ("quote", "\ud800"),
        ("object_id", True),
        ("segment_id", "invalid"),
    ],
)
def test_malformed_citation_rejected_before_source_read(device, field, value):
    obj, version = source(device)
    citation = cite(device, obj, version)
    citation[field] = value
    with pytest.raises(ValueError):
        verify(device, citation)


@pytest.mark.parametrize(
    "change",
    ["extra", "missing", "quote", "offset", "segment", "slot", "root", "observation", "object"],
)
def test_tampered_citation_never_falls_back_to_another_section_or_version(device, change):
    obj, version = source(device)
    citation = cite(device, obj, version)
    if change == "extra":
        citation["permission"] = "draft"
    if change == "missing":
        del citation["document_version_id"]
    if change == "quote":
        citation["quote"] = "Fake 📚"
    if change == "offset":
        citation["start"] += 1
        citation["end"] += 1
    if change in {"segment", "root", "observation", "object"}:
        field = {
            "segment": "segment_id",
            "root": "document_version_id",
            "observation": "observation_id",
            "object": "object_id",
        }[change]
        citation[field] = str(uuid4())
    if change == "slot":
        citation["slot"] = 1
    with pytest.raises((ValueError, LookupError)):
        verify(device, citation)


def test_cross_account_quote_verification_is_denied(device):
    obj, version = source(device)
    citation = cite(device, obj, version)
    device[0].provision("user_bob")
    with pytest.raises(LookupError):
        verify(device, citation, user="user_bob")


@pytest.mark.parametrize("control", ["revoke", "scope", "expiry"])
def test_current_connection_controls_fence_even_a_previously_matching_quote(device, control):
    obj, version = source(device)
    citation = cite(device, obj, version)
    assert verify(device, citation)["quote_matches"]
    if control == "revoke":
        device[0].rotate_or_revoke("user_alice", device[1]["connection_id"])
    if control == "scope":
        sync.set_scope(device, [], kinds=[])
    if control == "expiry":
        with device[0].connection() as conn:
            conn.execute(
                "UPDATE wrytely_agent.source_connections SET "
                "credential_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
                (device[1]["connection_id"],),
            )
    with pytest.raises(SourceRefreshRequired):
        verify(device, citation)


def test_partial_text_can_match_without_becoming_complete_or_usable(device):
    scan = evidence.prepare(device)
    item = evidence.assignment()
    item.update(coverage="partial", missing=["linked_content_unread"])
    receipt = evidence.upload(device, scan, evidence.body(device, scan, [item]))
    evidence.close(device, scan, receipt, partial=True)
    obj = evidence.rows(device, "canvas_evidence_objects")[0]
    version = save(device, obj, split_document_text(TEXT))
    citation = cite(device, obj, version)
    result = verify(device, citation)
    assert result["quote_matches"] and not result["evidence_usable_for_inspection"]
    assert result["coverage"] == "partial" and result["missing"] == ["linked_content_unread"]


def test_old_observation_quote_stays_historical_after_source_changes(device):
    obj, version = source(device)
    citation = cite(device, obj, version)
    scan = evidence.next_scan(device, "citation-changed")
    item = evidence.assignment()
    item["content"] = "Changed requirements"
    receipt = evidence.upload(device, scan, evidence.body(device, scan, [item]))
    evidence.close(device, scan, receipt)
    result = verify(device, citation)
    assert (
        result["quote_matches"]
        and result["historical"]
        and not result["evidence_usable_for_inspection"]
    )


def test_stale_quote_and_latest_failed_scan_remain_inspectable_but_unusable(device):
    obj, version = source(device)
    citation = cite(device, obj, version)
    with device[0].connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_evidence_observations SET "
            "observed_at=clock_timestamp()-interval '25 hours' WHERE id=%s",
            (obj["latest_observation_id"],),
        )
    result = verify(device, citation)
    assert result["quote_matches"] and result["freshness"]["reason"] == "too_old"
    scan = evidence.next_scan(device, "citation-failed-check")
    sync.finish_resource(
        device,
        scan,
        key="101/assignments",
        finish_key="failed",
        outcome="partial",
        reason="provider_unavailable",
    )
    result = verify(device, citation)
    assert (
        not result["evidence_usable_for_inspection"]
        and result["freshness"]["reason"] == "resource_incomplete"
    )


def test_task_verification_is_bound_to_current_responsibility_and_lease(device):
    objs = reads.collected(device, 2)
    versions = [save(device, obj, split_document_text(TEXT)) for obj in objs]
    citations = [cite(device, obj, version) for obj, version in zip(objs, versions, strict=True)]
    db = device[0]
    duty = db.create_responsibility("user_alice", "Verify one document", "citation-task")
    db.bind_source("user_alice", duty["id"], objs[0]["source_id"])
    run_once(db, ScriptedModel([plan()]), Settings())
    lease = db.claim()
    assert lease
    assert verify_document_citation_for_task(db, lease, citations[0])["quote_matches"]
    with pytest.raises(LookupError):
        verify_document_citation_for_task(db, lease, citations[1])
    db.set_paused("user_alice", True)
    with pytest.raises(LeaseLost):
        verify_document_citation_for_task(db, lease, citations[0])


def test_quote_verification_works_on_published_root_without_fabricated_legacy_source(device):
    from test_canvas_document_publication import page, ready

    scan = evidence.prepare(device)
    body, upload, root = ready(device, scan)
    receipt = evidence.upload(device, scan, page(device, scan, body, upload))
    evidence.close(device, scan, receipt)
    observed = receipt["observations"][0]
    obj = {"id": observed["object_id"], "latest_observation_id": observed["observation_id"]}
    citation = cite(device, obj, root["document_version_id"], quote="Café")
    result = verify(device, citation)
    assert result["quote_matches"] and result["evidence_usable_for_inspection"]
    assert evidence.rows(device, "source_versions") == []
    # A task does not acquire this source merely because the same account owns it.
    db = device[0]
    db.create_responsibility("user_alice", "Unbound analysis", "no-document-scope")
    run_once(db, ScriptedModel([plan()]), Settings())
    lease = db.claim()
    assert lease
    with pytest.raises(LookupError):
        verify_document_citation_for_task(db, lease, citation)


def test_stored_section_corruption_cannot_be_certified_by_matching_quote(device):
    obj, version = source(device)
    citation = cite(device, obj, version)
    with device[0].connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_document_sections SET text=%s WHERE "
            "document_version_id=%s",
            ("Z" + TEXT[1:], version),
        )
    with pytest.raises(ValueError):
        verify(device, citation)
