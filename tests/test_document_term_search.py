"""Literal discovery preserves original identity and current scoped authority."""

from uuid import uuid4

import pytest
from test_canvas_sync import device as device
from test_document_citations import source
from test_document_quote_search import HookReader, sectioned
from test_planner import plan
from test_worker import ScriptedModel

from runtime.document_citations import verify_document_citation
from runtime.document_term_search import find_document_terms, find_document_terms_for_task
from runtime.worker import run_once
from shared.canvas_reads import SourceRefreshRequired
from shared.config import Settings
from shared.db import LeaseLost


def search(device, obj, root, *, terms=("policy", "rubric"), store=None, user="user_alice", **kw):
    return find_document_terms(
        store or device[0],
        user,
        obj["id"],
        observation_id=obj["latest_observation_id"],
        document_version_id=root,
        terms=terms,
        **kw,
    )


def test_case_insensitive_discovery_keeps_exact_original_unicode_proofs(device):
    text = "📚 POLICY. Café rubric. policy."
    obj, root = source(device, text)
    result = search(device, obj, root)
    assert result["range_complete"]
    assert [m["citation"]["quote"] for m in result["matches"]] == ["POLICY", "rubric", "policy"]
    for proof in result["matches"]:
        assert verify_document_citation(device[0], "user_alice", proof["citation"]) == proof
        ref = proof["citation"]
        assert text[ref["start"] : ref["end"]] == ref["quote"]
    assert result["match_scope"] == "single_section_literal_terms"
    assert "cannot establish absence" in result["limits"]
    assert "📚" not in str(result)


def test_literal_not_regex_and_explicit_case_mode(device):
    obj, root = source(device, "Policy policy .* [a] aaaa")
    assert [
        m["citation"]["quote"] for m in search(device, obj, root, terms=[".*", "[a]"])["matches"]
    ] == [".*", "[a]"]
    assert len(search(device, obj, root, terms=["policy"], case_sensitive=True)["matches"]) == 1
    assert len(search(device, obj, root, terms=["policy"])["matches"]) == 2


def test_longest_term_at_each_offset_and_overlapping_continuation(device):
    obj, root = source(device, "aaaaa")
    cursor, hits = {}, []
    for _ in range(8):
        result = search(device, obj, root, terms=["aa", "aaa"], max_matches=1, **cursor)
        hits.extend((m["citation"]["start"], m["citation"]["quote"]) for m in result["matches"])
        if result["next"] is None:
            break
        cursor = result["next"]
    assert result["range_complete"]
    assert hits == [(0, "aaa"), (1, "aaa"), (2, "aaa"), (3, "aa")]


def test_regex_case_matching_never_uses_expanding_fold_offsets(device):
    obj, root = source(device, "📚 ß SS İ i")
    result = search(device, obj, root, terms=["ss", "i"])
    assert [(m["citation"]["start"], m["citation"]["quote"]) for m in result["matches"]] == [
        (4, "SS"),
        (7, "İ"),
        (9, "i"),
    ]


def test_page_budget_later_sections_and_no_cross_section_inference(device):
    obj, root = sectioned(device, "x" * 320 + "rubric", 8)
    result = search(device, obj, root, max_pages=1)
    assert result["matches"] == [] and not result["range_complete"]
    while result["next"] is not None:
        result = search(device, obj, root, max_pages=1, **result["next"])
    assert result["matches"][0]["citation"]["start"] == 320


def test_terms_are_not_spliced_across_section_boundaries(device):
    obj, root = sectioned(device, "policy", 3)
    assert search(device, obj, root)["matches"] == []


@pytest.mark.parametrize(
    "terms",
    [
        [],
        ["x"] * 9,
        "policy",
        {"policy"},
        [""],
        [" "],
        ["x" * 129],
        ["Cafe\u0301"],
        ["\ud800"],
        [1],
        ["x", "x"],
    ],
)
def test_invalid_terms_reject_before_io(terms):
    class NoIO:
        def read_canvas_document_sections(self, *a, **kw):
            pytest.fail("Invalid request reached IO")

    with pytest.raises(ValueError):
        find_document_terms(
            NoIO(),
            "alice",
            uuid4(),
            observation_id=uuid4(),
            document_version_id=uuid4(),
            terms=terms,
        )


@pytest.mark.parametrize(
    "kwargs", [{"case_sensitive": 1}, {"offset": True}, {"max_pages": 9}, {"max_matches": 0}]
)
def test_invalid_modes_and_bounds_reject_before_io(kwargs):
    class NoIO:
        def read_canvas_document_sections(self, *a, **kw):
            pytest.fail("Invalid request reached IO")

    with pytest.raises(ValueError):
        find_document_terms(
            NoIO(),
            "alice",
            uuid4(),
            observation_id=uuid4(),
            document_version_id=uuid4(),
            terms=["policy"],
            **kwargs,
        )


def test_wrong_account_and_explicit_wrong_root_never_fall_back(device):
    obj, root = source(device, "policy")
    device[0].provision("user_bob")
    with pytest.raises(LookupError):
        search(device, obj, root, user="user_bob")
    with pytest.raises(LookupError):
        search(device, obj, uuid4())


def test_final_reauthorization_rejects_revocation_after_hits(device):
    obj, root = source(device, "policy")
    proxy = HookReader(
        device[0], lambda: device[0].rotate_or_revoke("user_alice", device[1]["connection_id"])
    )
    with pytest.raises(SourceRefreshRequired):
        search(device, obj, root, store=proxy)
    assert proxy.calls == 2


def test_unbound_task_cannot_search_same_account_document(device):
    obj, root = source(device, "policy")
    db = device[0]
    db.create_responsibility("user_alice", "Unbound", "unbound-terms")
    run_once(db, ScriptedModel([plan()]), Settings())
    lease = db.claim()
    with pytest.raises(LookupError):
        find_document_terms_for_task(
            db,
            lease,
            obj["id"],
            observation_id=obj["latest_observation_id"],
            document_version_id=root,
            terms=["policy"],
        )


def test_bound_task_search_and_final_pause_are_enforced(device):
    obj, root = source(device, "policy")
    db = device[0]
    duty = db.create_responsibility("user_alice", "Investigate", "terms")
    db.bind_source("user_alice", duty["id"], obj["source_id"])
    run_once(db, ScriptedModel([plan()]), Settings())
    lease = db.claim()
    args = dict(
        observation_id=obj["latest_observation_id"], document_version_id=root, terms=["policy"]
    )
    assert find_document_terms_for_task(db, lease, obj["id"], **args)["matches"]
    proxy = HookReader(db, lambda: db.set_paused("user_alice", True), task=True)
    with pytest.raises(LeaseLost):
        find_document_terms_for_task(proxy, lease, obj["id"], **args)


def test_source_change_after_hits_marks_every_result_historical(device):
    import test_canvas_evidence as evidence

    obj, root = source(device, "policy")

    def change():
        scan = evidence.next_scan(device, "term-change")
        item = evidence.assignment()
        item["content"] = "Changed requirements"
        receipt = evidence.upload(device, scan, evidence.body(device, scan, [item]))
        evidence.close(device, scan, receipt)

    result = search(device, obj, root, store=HookReader(device[0], change))
    assert result["historical"]
    assert all(not m["evidence_usable_for_inspection"] for m in result["matches"])


def test_document_only_publication_search_requires_no_fake_legacy_version(device):
    import test_canvas_evidence as evidence
    from test_canvas_document_publication import page, ready

    scan = evidence.prepare(device)
    body, upload, root = ready(device, scan)
    receipt = evidence.upload(device, scan, page(device, scan, body, upload))
    evidence.close(device, scan, receipt)
    observed = receipt["observations"][0]
    obj = {"id": observed["object_id"], "latest_observation_id": observed["observation_id"]}
    result = search(device, obj, root["document_version_id"], terms=["café"])
    assert result["matches"][0]["citation"]["quote"] == "Café"
    assert evidence.rows(device, "source_versions") == []
