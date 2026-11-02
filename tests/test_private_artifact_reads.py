"""Owned real-Store v2 student reads; no HTTP or provider activation."""

from copy import deepcopy
from uuid import uuid4

import pytest
import test_canvas_evidence as evidence
import test_canvas_sync as sync
from psycopg.types.json import Jsonb
from test_artifacts import assessment, prepare
from test_canvas_sync import device as device
from test_drafting import permitted, structured
from test_typed_document_drafting import TEXT, planner_stage, prepared, publish, ref
from test_worker import ScriptedModel

from contracts.document_artifacts import DraftArtifactV2
from runtime.worker import run_once
from shared.canvas_reads import SourceRefreshRequired
from shared.config import Settings
from shared.private_artifact_projection import PrivateArtifactReadLimit


def ready(device, **kwargs):
    data = prepared(device, **kwargs)
    planner_stage(device, data)
    model = ScriptedModel(
        [
            permitted(),
            structured("save_review_draft", data[3]),
            assessment(
                **({"claim_support": ["supported", "supported"]} if kwargs.get("mixed") else {})
            ),
        ]
    )
    assert run_once(device[0], model, Settings())
    with device[0].connection() as conn:
        row = conn.execute("SELECT * FROM wrytely_agent.artifacts").fetchone()
    assert row["state"] == "ready"
    return data, row


@pytest.fixture
def result(device):
    return ready(device)


def detail(device, result):
    return device[0].read_private_artifact_v2("user_alice", result[1]["id"])


def cited(device, result, **kwargs):
    return device[0].read_private_artifact_evidence_v2(
        "user_alice", result[1]["id"], group="citation", index=0, **kwargs
    )


def test_owned_detail_and_original_citation_preserve_typed_identity(device, result):
    value = detail(device, result)
    assert value["schema_version"] == 2
    assert value["latest_check"]["report"]["passed"] is True
    assert value["evidence_status"]["state"] == "current"
    assert value["controls"] == {"agent_paused": False, "responsibility_status": "active"}
    original = cited(device, result)
    assert original["quote_matches"]
    assert original["reference"] == value["artifact"]["draft"]["citations"][0]["evidence"]
    assert original["source"]["sections"][0]["text"] == TEXT
    for forbidden in (
        "typed_evidence",
        "input_tokens",
        "ingestion_bearer",
        "provider_subject",
        "lease_token",
        "https://",
    ):
        assert forbidden not in str(value) + str(original)
    assert device[0].artifact_review("user_alice", result[1]["id"]) is None
    assert device[0].responsibility_artifacts("user_alice", result[0][0]["id"]) == []


def test_metadata_list_has_no_content_even_after_disconnect(device, result):
    db = device[0]
    db.rotate_or_revoke("user_alice", device[1]["connection_id"])
    value = db.list_private_artifacts_v2("user_alice", result[0][0]["id"])
    assert len(value["artifacts"]) == 1 and value["next"] is None
    assert set(value["artifacts"][0]) == {
        "id",
        "task_id",
        "created_at",
        "saved_state",
        "memory_stale",
    }
    with pytest.raises(SourceRefreshRequired):
        detail(device, result)


def test_keyset_ties_do_not_duplicate_or_skip_artifacts(device, result):
    row = result[1]
    identifiers = [row["id"]]
    with device[0].connection() as conn:
        for i in range(4):
            identifier = uuid4()
            identifiers.append(identifier)
            conn.execute(
                "INSERT INTO wrytely_agent.artifacts SELECT %s,agent_id,responsibility_id,task_id,"
                "%s,memory_revision,draft,state,created_at,document_citations,evidence_schema "
                "FROM wrytely_agent.artifacts WHERE id=%s",
                (identifier, "clone-" + str(i), row["id"]),
            )
    before, seen = None, []
    while True:
        page = device[0].list_private_artifacts_v2(
            "user_alice", row["responsibility_id"], limit=2, before=before
        )
        seen.extend(r["id"] for r in page["artifacts"])
        before = page["next"]
        if before is None:
            break
    assert seen == sorted(map(str, identifiers), reverse=True)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"limit": True},
        {"limit": 0},
        {"limit": 51},
        {"before": {}},
        {"before": {"id": "x", "created_at": "2026-01-01T00:00:00Z"}},
        {"before": {"id": str(uuid4()), "created_at": "2026-01-01T00:00:00"}},
        {"before": {"id": str(uuid4()), "created_at": "2026-01-01T00:00:00+01:00"}},
    ],
)
def test_list_rejects_invalid_bounds_and_cursor_before_io(kwargs):
    from shared.db import Store

    with pytest.raises(ValueError):
        Store("not-a-database").list_private_artifacts_v2("alice", uuid4(), **kwargs)


def test_other_accounts_cannot_read_metadata_draft_or_reference(device, result):
    db = device[0]
    db.provision("user_bob")
    for call in [
        lambda: db.list_private_artifacts_v2("user_bob", result[1]["responsibility_id"]),
        lambda: db.read_private_artifact_v2("user_bob", result[1]["id"]),
        lambda: db.read_private_artifact_evidence_v2(
            "user_bob", result[1]["id"], group="citation", index=0
        ),
    ]:
        with pytest.raises(LookupError, match="Not found"):
            call()


@pytest.mark.parametrize(
    "control", ["scope", "revoke", "expire", "generation", "subject", "binding"]
)
def test_authority_change_denies_draft_and_embedded_quotes(device, result, control):
    db = device[0]
    if control == "scope":
        sync.set_scope(device, [], kinds=[])
    elif control == "revoke":
        db.rotate_or_revoke("user_alice", device[1]["connection_id"])
    else:
        with db.connection() as conn:
            if control == "binding":
                conn.execute("DELETE FROM wrytely_agent.responsibility_canvas_objects")
            else:
                assignment = {
                    "expire": "credential_expires_at=clock_timestamp()-interval '1 second'",
                    "generation": "generation=generation+1",
                    "subject": "provider_subject='other'",
                }[control]
                conn.execute("UPDATE wrytely_agent.source_connections SET " + assignment)
    with pytest.raises(SourceRefreshRequired):
        detail(device, result)
    with pytest.raises(SourceRefreshRequired):
        cited(device, result)


def test_pause_does_not_resume_or_hide_saved_student_work(device, result):
    db = device[0]
    db.set_paused("user_alice", True)
    with db.connection() as conn:
        before = conn.execute("SELECT count(*) AS n FROM wrytely_agent.tasks").fetchone()["n"]
    assert detail(device, result)["controls"]["agent_paused"] is True
    assert cited(device, result)["quote_matches"]
    with db.connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.tasks").fetchone()["n"] == before
        )
        assert conn.execute("SELECT paused FROM wrytely_agent.agents").fetchone()["paused"]


def test_inspection_uses_24h_not_the_drafting_6h_window(device, result):
    with device[0].connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_evidence_observations "
            "SET observed_at=clock_timestamp()-interval '7 hours'"
        )
    assert detail(device, result)["evidence_status"]["state"] == "current"
    with device[0].connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_evidence_observations "
            "SET observed_at=clock_timestamp()-interval '25 hours'"
        )
    value = detail(device, result)
    assert value["latest_check"]["report"]["passed"]
    assert value["evidence_status"]["state"] == "stale"


def test_unchanged_refresh_keeps_old_observation_historical(device, result):
    old = result[0][4]
    scan = evidence.next_scan(device, "read-refresh")
    publish(device, scan=scan)
    value = detail(device, result)
    assert value["evidence_status"]["state"] == "historical"
    original = cited(device, result)
    assert original["reference"]["observation_id"] == old["observation_id"]
    assert original["source"]["historical"]


def test_policy_read_pins_check_instead_of_following_latest(device, result):
    db = device[0]
    old = detail(device, result)["latest_check"]
    with db.connection() as conn:
        row = conn.execute("SELECT * FROM wrytely_agent.artifact_checks").fetchone()
        changed = deepcopy(row["report"])
        changed["policy"]["evidence"] = result[0][3]["citations"][0]["evidence"]
        new_id = uuid4()
        conn.execute(
            "INSERT INTO wrytely_agent.artifact_checks VALUES (%s,%s,%s,%s,%s,clock_timestamp())",
            (new_id, row["artifact_id"], row["memory_revision"], row["passed"], Jsonb(changed)),
        )
    assert detail(device, result)["latest_check"]["id"] == str(new_id)
    original = db.read_private_artifact_evidence_v2(
        "user_alice", result[1]["id"], group="policy", index=0, check_id=old["id"]
    )
    assert original["reference"] == old["report"]["policy"]["evidence"]
    with pytest.raises(LookupError):
        db.read_private_artifact_evidence_v2(
            "user_alice", result[1]["id"], group="policy", index=0, check_id=uuid4()
        )


@pytest.mark.parametrize(
    "mutation", ["missing", "unknown_code", "bool", "assessment", "legacy", "count", "schema"]
)
def test_bad_or_missing_saved_check_is_unverified_not_passed(device, result, mutation):
    with device[0].connection() as conn:
        if mutation == "missing":
            conn.execute("DELETE FROM wrytely_agent.artifact_checks")
        else:
            raw = conn.execute("SELECT report FROM wrytely_agent.artifact_checks").fetchone()[
                "report"
            ]
            if mutation == "unknown_code":
                raw["errors"] = ["PRIVATE_ERROR_TEXT"]
            if mutation == "bool":
                raw["passed"] = "true"
            if mutation == "assessment":
                raw["assessment"]["uncited_claims"] = True
            if mutation == "legacy":
                raw["policy"]["evidence"] = {"version_id": str(uuid4()), "quote": "PRIVATE"}
            if mutation == "count":
                raw["assessment"]["claim_support"] = []
            if mutation == "schema":
                raw["evidence_schema"] = 2.0
            conn.execute("UPDATE wrytely_agent.artifact_checks SET report=%s", (Jsonb(raw),))
    value = detail(device, result)
    assert value["latest_check"] is None and value["evidence_status"]["state"] == "unverified"
    assert "PRIVATE" not in str(value)


def test_original_quote_mismatch_is_unverified(device, result):
    draft = deepcopy(result[1]["draft"])
    draft["citations"][0]["evidence"]["start"] += 1
    draft["citations"][0]["evidence"]["end"] += 1
    with device[0].connection() as conn:
        conn.execute("UPDATE wrytely_agent.artifacts SET draft=%s", (Jsonb(draft),))
    assert detail(device, result)["evidence_status"]["state"] == "unverified"
    assert not cited(device, result)["quote_matches"]


def test_mixed_originals_keep_real_legacy_kind_and_current_scope(device):
    result = ready(device, mixed=True)
    value = detail(device, result)
    assert value["evidence_status"]["state"] == "current"
    legacy = device[0].read_private_artifact_evidence_v2(
        "user_alice", result[1]["id"], group="citation", index=1
    )
    assert legacy["source"]["kind"] == "legacy" and legacy["quote_matches"]
    assert "sections" not in legacy["source"]
    with pytest.raises(ValueError):
        device[0].read_private_artifact_evidence_v2(
            "user_alice", result[1]["id"], group="citation", index=1, limit=2
        )


def test_direct_legacy_v2_inspection_and_v1_compatibility(store, alice):
    lease, v1, _, _, version, draft = prepare(store, alice)
    typed = DraftArtifactV2(
        schema_version=2,
        title=draft.title,
        body=draft.body,
        disclosure="",
        citations=[
            {
                "claim": draft.citations[0].claim,
                "evidence": {
                    "kind": "legacy",
                    "version_id": version["id"],
                    "quote": draft.citations[0].quote,
                },
            }
        ],
    )
    row = store.save_draft(lease, typed, "v2-direct")
    value = store.read_private_artifact_v2("user_alice", row["id"])
    assert value["latest_check"] is None and value["evidence_status"]["state"] == "unverified"
    assert store.read_private_artifact_evidence_v2(
        "user_alice", row["id"], group="citation", index=0
    )["quote_matches"]
    assert store.artifact_review("user_alice", v1["id"]) is not None
    with pytest.raises(LookupError):
        store.read_private_artifact_v2("user_alice", v1["id"])


@pytest.mark.parametrize(
    "kwargs",
    [
        {"index": True},
        {"index": 30},
        {"group": "other"},
        {"first_slot": True},
        {"limit": 21},
        {"group": "policy"},
        {"check_id": str(uuid4())},
    ],
)
def test_evidence_bounds_and_check_selection_reject_before_io(kwargs):
    from shared.db import Store

    with pytest.raises(ValueError):
        Store("no-database").read_private_artifact_evidence_v2(
            "alice", uuid4(), **({"group": "citation", "index": 0} | kwargs)
        )


def test_owned_empty_list_and_missing_responsibility_are_distinct(store, alice):
    duty = store.create_responsibility("user_alice", "Empty work", "empty-list")
    assert store.list_private_artifacts_v2("user_alice", duty["id"])["artifacts"] == []
    with pytest.raises(LookupError):
        store.list_private_artifacts_v2("user_alice", uuid4())


def test_paged_original_uses_exact_root_and_explicit_continuation(device):
    result = ready(device, text=TEXT + "x" * 64000)
    first = cited(device, result, first_slot=1, limit=20)
    assert first["reference"]["slot"] == 0 and first["quote_matches"]
    assert len(first["source"]["sections"]) == 1
    assert first["source"]["sections"][0]["slot"] == 1
    assert first["source"]["next_slot"] == 2
    last = cited(device, result, first_slot=2, limit=20)
    assert last["source"]["next_slot"] is None
    assert first["source"]["document_version_id"] == last["source"]["document_version_id"]


def test_partial_resource_is_inspectable_but_never_current(device, result):
    with device[0].connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_resources SET coverage='partial' "
            "WHERE resource_key='101/assignments'"
        )
    value = detail(device, result)
    assert value["latest_check"]["report"]["passed"]
    assert value["evidence_status"]["state"] == "incomplete"


def test_memory_revision_and_real_responsibility_status_are_visible(device, result):
    with device[0].connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.responsibilities "
            "SET memory_revision=memory_revision+1,status='blocked'"
        )
    value = detail(device, result)
    assert value["artifact"]["memory_stale"]
    assert value["controls"]["responsibility_status"] == "blocked"
    assert value["evidence_status"]["state"] == "historical"


@pytest.mark.parametrize("operation", [detail, cited])
def test_final_authority_expiry_denies_already_loaded_content(
    device, result, monkeypatch, operation
):
    db = device[0]
    original = db._load_canvas_document

    def expire(conn, *a, **kw):
        loaded = original(conn, *a, **kw)
        conn.execute(
            "UPDATE wrytely_agent.source_connections "
            "SET credential_expires_at=clock_timestamp()-interval '1 second'"
        )
        return loaded

    monkeypatch.setattr(db, "_load_canvas_document", expire)
    with pytest.raises(SourceRefreshRequired):
        operation(device, result)


def test_final_original_age_recheck_downgrades_earlier_projection(device, result, monkeypatch):
    db = device[0]
    original = db._load_canvas_document

    def age(conn, *a, **kw):
        loaded = original(conn, *a, **kw)
        conn.execute(
            "UPDATE wrytely_agent.canvas_evidence_observations "
            "SET observed_at=clock_timestamp()-interval '25 hours'"
        )
        return loaded

    monkeypatch.setattr(db, "_load_canvas_document", age)
    value = cited(device, result)
    assert value["evidence_status"]["state"] == "stale"
    assert not value["source"]["freshness"]["usable"]


def test_oversized_valid_mixed_projection_fails_without_truncation(device):
    result = ready(device, text=TEXT + "📚" * 16000)
    large = ref(device, result[0][4], "📚" * 4000)
    draft = deepcopy(result[1]["draft"])
    draft["body"] = "📚" * 23900 + draft["citations"][0]["claim"]
    draft["citations"] = [
        dict(claim=draft["citations"][0]["claim"], evidence=large) for _ in range(30)
    ]
    with device[0].connection() as conn:
        report = conn.execute("SELECT report FROM wrytely_agent.artifact_checks").fetchone()[
            "report"
        ]
        report["policy"]["evidence"] = large
        report["rubric"] = [dict(evidence=large) for _ in range(30)]
        report["assessment"].update(
            claim_support=["supported"] * 30, rubric_coverage=["covered"] * 30
        )
        conn.execute("UPDATE wrytely_agent.artifacts SET draft=%s", (Jsonb(draft),))
        conn.execute("UPDATE wrytely_agent.artifact_checks SET report=%s", (Jsonb(report),))
    with pytest.raises(PrivateArtifactReadLimit):
        detail(device, result)
