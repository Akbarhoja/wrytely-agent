"""Exact bounded search with real original sections and scoped reads."""

import hashlib
from uuid import uuid4

import pytest
import test_canvas_evidence as evidence
import test_canvas_reads as reads
from test_canvas_documents import save
from test_canvas_sync import device as device
from test_document_citations import TEXT, source
from test_planner import plan
from test_worker import ScriptedModel

from runtime.document_citations import verify_document_citation
from runtime.document_quote_search import find_document_quotes, find_document_quotes_for_task
from runtime.worker import run_once
from shared.canvas_reads import SourceRefreshRequired
from shared.config import Settings
from shared.db import LeaseLost
from shared.document_sections import DocumentSection, DocumentSections, split_document_text


def search(device, obj, root, quote="Café", *, user="user_alice", store=None, **kwargs):
    return find_document_quotes(
        store or device[0],
        user,
        obj["id"],
        observation_id=obj["latest_observation_id"],
        document_version_id=root,
        quote=quote,
        **kwargs,
    )


def sectioned(device, text, size=8):
    obj = reads.collected(device)[0]
    root = save(device, obj, split_document_text(text, section_characters=size))
    return obj, root


def test_exact_unicode_results_verify_against_original_and_omit_other_content(device):
    obj, root = source(device)
    result = search(device, obj, root)
    assert result["range_complete"] and result["next"] is None
    assert [m["citation"]["start"] for m in result["matches"]] == [
        TEXT.index("Café"),
        TEXT.rindex("Café"),
    ]
    for match in result["matches"]:
        assert match["evidence_usable_for_inspection"]
        assert verify_document_citation(device[0], "user_alice", match["citation"]) == match
    assert "Second line" not in str(result)
    for private in ("ingestion_bearer", "provider_subject", "lease_token", "private_payload"):
        assert private not in str(result)


def test_overlapping_matches_continue_within_section_without_skips_or_duplicates(device):
    obj, root = source(device, "aaaaa")
    cursor, offsets = {}, []
    for _ in range(4):
        result = search(device, obj, root, "aaa", max_matches=1, **cursor)
        offsets.extend(m["citation"]["start"] for m in result["matches"])
        if result["next"] is None:
            break
        assert not result["range_complete"]
        cursor = result["next"]
    assert result["range_complete"] and offsets == [0, 1, 2]


def test_page_budget_returns_continuation_and_finds_later_section(device):
    text = "x" * 320 + "target📚"
    obj, root = sectioned(device, text)
    first = search(device, obj, root, "target📚", max_pages=1)
    assert first["matches"] == [] and not first["range_complete"]
    assert first["next"] == {"first_slot": 20, "offset": 0}
    second = search(device, obj, root, "target📚", max_pages=1, **first["next"])
    assert second["next"] == {"first_slot": 40, "offset": 0}
    last = search(device, obj, root, "target📚", **second["next"])
    assert last["range_complete"]
    assert last["matches"][0]["citation"]["start"] == 320
    assert last["range_start"] == second["next"]


def test_search_handles_actual_long_section_page_byte_budget(device):
    obj, root = source(device, "x" * 72000 + "Café 📚")
    first = search(device, obj, root, "Café 📚", max_pages=1)
    assert first["next"] == {"first_slot": 1, "offset": 0}
    rest = search(device, obj, root, "Café 📚", max_pages=8, **first["next"])
    assert rest["range_complete"] and rest["matches"][0]["citation"]["start"] == 72000


def test_quotes_are_never_spliced_across_sections_or_used_as_policy_absence(device):
    obj, root = sectioned(device, "ABCD", 2)
    result = search(device, obj, root, "BC")
    assert result["range_complete"] and result["matches"] == []
    assert result["match_scope"] == "single_section_exact_quotes"
    assert "policy" not in result


def test_pdf_quotes_preserve_page_and_global_offsets(device):
    obj = reads.collected(device)[0]
    parts = ["A📚", "\nCafé"]
    sections, end = [], 0
    for slot, text in enumerate(parts):
        sections.append(
            DocumentSection(
                slot,
                end,
                end + len(text),
                slot + 1,
                text,
                hashlib.sha256(text.encode()).hexdigest(),
            )
        )
        end += len(text)
    root = save(device, obj, DocumentSections(tuple(sections), end, 2), format="pdf_text")
    result = search(device, obj, root)
    citation = result["matches"][0]["citation"]
    assert (citation["page"], citation["slot"], citation["start"], citation["end"]) == (2, 1, 3, 7)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"quote": ""},
        {"quote": " "},
        {"quote": "x" * 4001},
        {"quote": "Cafe\u0301"},
        {"quote": "\ud800"},
        {"first_slot": True},
        {"first_slot": -1},
        {"first_slot": 513},
        {"offset": True},
        {"offset": -1},
        {"offset": 24001},
        {"max_pages": 0},
        {"max_pages": 9},
        {"max_pages": True},
        {"max_matches": 0},
        {"max_matches": 31},
        {"max_matches": True},
    ],
)
def test_invalid_search_bounds_are_rejected_before_io(kwargs):
    class NoIO:
        def read_canvas_document_sections(self, *args, **kwargs):
            pytest.fail("Invalid arguments must not reach the reader")

    args = {"quote": "a"} | kwargs
    with pytest.raises(ValueError):
        find_document_quotes(
            NoIO(),
            "user_alice",
            uuid4(),
            observation_id=uuid4(),
            document_version_id=uuid4(),
            **args,
        )


def test_bad_offsets_and_explicit_wrong_roots_never_fall_back_to_latest(device):
    obj, root = source(device)
    with pytest.raises(ValueError):
        search(device, obj, root, offset=len(TEXT) + 1)
    with pytest.raises(LookupError):
        search(device, obj, uuid4())
    with pytest.raises(LookupError):
        search(device, obj | {"latest_observation_id": uuid4()}, root)
    end = search(device, obj, root, first_slot=1)
    assert end["matches"] == [] and end["range_complete"] and end["sections_scanned"] == 0


def test_partial_and_stale_matches_never_become_usable_evidence(device):
    scan = evidence.prepare(device)
    item = evidence.assignment()
    item.update(content=TEXT, coverage="partial", missing=["linked_content_unread"])
    receipt = evidence.upload(device, scan, evidence.body(device, scan, [item]))
    evidence.close(device, scan, receipt, partial=True)
    obj = evidence.rows(device, "canvas_evidence_objects")[0]
    root = save(device, obj, split_document_text(TEXT))
    result = search(device, obj, root)
    assert result["matches"] and result["coverage"] == "partial"
    assert all(not m["evidence_usable_for_inspection"] for m in result["matches"])
    with device[0].connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_evidence_observations SET "
            "observed_at=clock_timestamp()-interval '2 days'"
        )
    assert not search(device, obj, root)["freshness"]["usable"]


class HookReader:
    def __init__(self, db, hook, *, task=False):
        self.db, self.hook, self.task, self.calls = db, hook, task, 0

    def invoke(self, *args, **kwargs):
        self.calls += 1
        if self.calls == 2:
            self.hook()
        read = (
            self.db.read_canvas_document_sections_for_task
            if self.task
            else self.db.read_canvas_document_sections
        )
        return read(*args, **kwargs)

    read_canvas_document_sections = invoke
    read_canvas_document_sections_for_task = invoke


def test_final_read_rejects_revocation_after_search_before_results_return(device):
    obj, root = source(device)
    proxy = HookReader(
        device[0], lambda: device[0].rotate_or_revoke("user_alice", device[1]["connection_id"])
    )
    with pytest.raises(SourceRefreshRequired):
        search(device, obj, root, store=proxy)
    assert proxy.calls == 2


def test_updated_observation_downgrades_all_prior_matches_to_historical(device):
    obj, root = source(device)

    def change():
        scan = evidence.next_scan(device, "changed-during-search")
        item = evidence.assignment()
        item["content"] = "Changed requirements"
        receipt = evidence.upload(device, scan, evidence.body(device, scan, [item]))
        evidence.close(device, scan, receipt)

    result = search(device, obj, root, store=HookReader(device[0], change))
    assert result["historical"] and not result["freshness"]["usable"]
    assert all(
        m["historical"] and not m["evidence_usable_for_inspection"] for m in result["matches"]
    )


def test_other_accounts_and_unbound_tasks_cannot_search_documents(device):
    obj, root = source(device)
    db = device[0]
    db.provision("user_bob")
    with pytest.raises(LookupError):
        search(device, obj, root, user="user_bob")
    db.create_responsibility("user_alice", "One document", "search")
    run_once(db, ScriptedModel([plan()]), Settings())
    lease = db.claim()
    args = dict(observation_id=obj["latest_observation_id"], document_version_id=root, quote="Café")
    with pytest.raises(LookupError):
        find_document_quotes_for_task(db, lease, obj["id"], **args)


def test_bound_task_search_rechecks_pause_before_return(device):
    obj, root = source(device)
    db = device[0]
    duty = db.create_responsibility("user_alice", "One bound document", "bound-search")
    db.bind_source("user_alice", duty["id"], obj["source_id"])
    run_once(db, ScriptedModel([plan()]), Settings())
    lease = db.claim()
    args = dict(observation_id=obj["latest_observation_id"], document_version_id=root, quote="Café")
    assert find_document_quotes_for_task(db, lease, obj["id"], **args)["matches"]
    proxy = HookReader(db, lambda: db.set_paused("user_alice", True), task=True)
    with pytest.raises(LeaseLost):
        find_document_quotes_for_task(proxy, lease, obj["id"], **args)


def test_published_document_only_root_search_does_not_grant_task_access(device):
    from test_canvas_document_publication import page, ready

    scan = evidence.prepare(device)
    body, upload, root = ready(device, scan)
    receipt = evidence.upload(device, scan, page(device, scan, body, upload))
    evidence.close(device, scan, receipt)
    observed = receipt["observations"][0]
    obj = {"id": observed["object_id"], "latest_observation_id": observed["observation_id"]}
    result = search(device, obj, root["document_version_id"])
    assert result["matches"][0]["citation"]["quote"] == "Café"
    assert evidence.rows(device, "source_versions") == []
    db = device[0]
    db.create_responsibility("user_alice", "No document scope", "not-bound")
    run_once(db, ScriptedModel([plan()]), Settings())
    lease = db.claim()
    with pytest.raises(LookupError):
        find_document_quotes_for_task(
            db,
            lease,
            obj["id"],
            observation_id=obj["latest_observation_id"],
            document_version_id=root["document_version_id"],
            quote="Café",
        )


@pytest.mark.parametrize("poison", ["identity", "continuation", "final_size"])
def test_inconsistent_reader_results_cannot_certify_search_progress(device, poison):
    obj, root = sectioned(device, "x" * 168)

    class PoisonReader:
        def __init__(self):
            self.calls = 0

        def read_canvas_document_sections(self, *args, **kwargs):
            result = device[0].read_canvas_document_sections(*args, **kwargs)
            self.calls += 1
            if poison == "identity":
                result["document_version_id"] = str(uuid4())
            elif poison == "continuation":
                result["next_slot"] = kwargs["first_slot"]
            elif self.calls == 2:
                result["total_slots"] += 1
            return result

    with pytest.raises(ValueError):
        search(device, obj, root, max_pages=1, store=PoisonReader())


def test_stored_corruption_is_not_hidden_by_a_matching_substring(device):
    obj, root = source(device)
    with device[0].connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_document_sections SET text=%s "
            "WHERE document_version_id=%s",
            ("Z" + TEXT[1:], root),
        )
    with pytest.raises(ValueError):
        search(device, obj, root)
