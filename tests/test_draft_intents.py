from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from test_artifacts import TEXT, assessment
from test_drafting import permitted, structured
from test_planner import plan
from test_worker import ScriptedModel

from contracts.artifacts import DraftArtifact
from contracts.models import SourceObservation
from runtime.worker import run_once
from shared.config import Settings
from shared.db import RequestConflict, Store


def setup(store):
    source = store.observe_source(
        "user_alice",
        SourceObservation(
            source_key="draft-policy",
            external_revision="v1",
            title="Synthetic assignment",
            reference="synthetic:assignment",
            coverage="snapshot",
            content=TEXT,
            retrieved_at=datetime.now(UTC),
        ),
    )
    return source


def create(store, source, **kwargs):
    return store.create_draft_responsibility(
        "user_alice",
        "Prepare a private comparison draft",
        "draft-intent",
        source_ids=[source["source_id"]],
        **kwargs,
    )


def extracted(source, status="disclosure_required"):
    return structured(
        "assess_draft_requirements",
        {
            "policy": {
                "status": status,
                "version_id": str(source["id"]),
                "quote": "AI drafting is permitted with disclosure.",
            },
            "rubric": [{"version_id": str(source["id"]), "quote": "Compare two sources."}],
            "reason": "Source-backed assessment, not student authority.",
        },
    )


def draft_turn(source):
    draft = DraftArtifact(
        title="Private review",
        body="Source A reports 10 participants.\nDraft prepared with AI; review required.",
        disclosure="Draft prepared with AI; review required.",
        citations=[
            {
                "version_id": source["id"],
                "quote": "Source A reports 10 participants.",
                "claim": "Source A reports 10 participants.",
            }
        ],
    )
    return structured("save_review_draft", draft.model_dump(mode="json"))


def test_explicit_intent_routes_one_checked_draft_without_manual_task_upgrade(store, alice):
    source = setup(store)
    duty = create(store, source)
    model = ScriptedModel(
        [
            extracted(source),
            plan("draft", "comparison", "Prepare private draft"),
            permitted(),
            draft_turn(source),
            assessment(),
            plan("done", "review-ready", ""),
        ]
    )
    for _ in range(3):
        assert run_once(Store(store._url), model, Settings())
    state = store.draft_responsibility_status("user_alice", duty["id"])
    assert state["requested_mode"] == "private_draft"
    assert state["assessment_state"] == "assessed"
    assert (state["status"], state["workflow_state"]) == ("done", "ready_for_review")
    assert store.artifact("user_alice", state["artifact_id"])["state"] == "ready"
    store.provision("user_bob")
    assert store.draft_responsibility_status("user_bob", duty["id"]) is None
    with store.connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.drafting_requests").fetchone()[
                "n"
            ]
            == 1
        )
        assert not conn.execute("SELECT 1 FROM wrytely_agent.whatsapp_outbound").fetchall()


def test_intent_is_atomic_idempotent_and_cannot_upgrade_analysis_key(store, alice):
    source = setup(store)
    with ThreadPoolExecutor(max_workers=3) as pool:
        duties = list(pool.map(lambda _: create(Store(store._url), source), range(3)))
    assert len({d["id"] for d in duties}) == 1
    with pytest.raises(RequestConflict):
        create(store, source, max_revisions=0)
    with pytest.raises(RequestConflict):
        store.create_bound_responsibility(
            "user_alice",
            "Prepare a private comparison draft",
            "draft-intent",
            source_ids=[source["source_id"]],
        )
    analysis = store.create_bound_responsibility(
        "user_alice", "Analyze", "analysis", source_ids=[source["source_id"]]
    )
    with pytest.raises(RequestConflict):
        store.create_draft_responsibility(
            "user_alice", "Analyze", "analysis", source_ids=[source["source_id"]]
        )
    assert (
        store.draft_responsibility_status("user_alice", analysis["id"])["requested_mode"]
        == "analysis"
    )


@pytest.mark.parametrize("status", ["unknown", "limited", "prohibited"])
def test_nonpermitting_assessment_blocks_before_draft_or_planner(store, alice, status):
    source = setup(store)
    duty = create(store, source)
    assert run_once(store, ScriptedModel([extracted(source, status)]), Settings())
    state = store.draft_responsibility_status("user_alice", duty["id"])
    assert state["assessment_state"] == "blocked"
    assert state["status"] == "blocked"
    assert state["reason"] == "draft_policy_or_rubric_blocked"
    with store.connection() as conn:
        assert not conn.execute("SELECT 1 FROM wrytely_agent.drafting_requests").fetchall()


def test_saved_assessment_survives_planner_failure_and_resume(store, alice):
    source = setup(store)
    duty = create(store, source)
    assert run_once(
        store, ScriptedModel([extracted(source), RuntimeError("interrupted")]), Settings()
    )
    with store.connection() as conn:
        conn.execute("UPDATE wrytely_agent.tasks SET available_at=now() WHERE status='ready'")
    assert run_once(
        Store(store._url), ScriptedModel([plan("draft", "comparison", "Draft")]), Settings()
    )
    assert store.draft_responsibility_status("user_alice", duty["id"])["workflow_state"] == "queued"


def test_pause_and_source_change_fence_intent_without_new_inference(store, alice):
    source = setup(store)
    duty = create(store, source)
    store.set_paused("user_alice", True)
    assert not run_once(store, ScriptedModel([]), Settings())
    store.set_paused("user_alice", False)
    store.observe_source(
        "user_alice",
        SourceObservation(
            source_key="draft-policy",
            external_revision="v2",
            title="Changed policy",
            reference="synthetic:assignment",
            coverage="snapshot",
            content="No AI drafts permitted.",
            retrieved_at=datetime.now(UTC),
        ),
    )
    assert not run_once(store, ScriptedModel([]), Settings())
    state = store.draft_responsibility_status("user_alice", duty["id"])
    assert state["reason"] == "source_changed"
    assert state["workflow_state"] == "blocked"


def test_analysis_only_model_cannot_invent_drafting_authority(store, alice):
    source = setup(store)
    store.create_bound_responsibility(
        "user_alice", "Analyze", "analysis", source_ids=[source["source_id"]]
    )
    assert run_once(
        store,
        ScriptedModel([plan("draft", "forged", "Draft without consent")]),
        Settings(max_attempts=1),
    )
    with store.connection() as conn:
        assert not conn.execute("SELECT 1 FROM wrytely_agent.drafting_requests").fetchall()


def test_draft_intent_cannot_finish_without_checked_result(store, alice):
    source = setup(store)
    duty = create(store, source)
    model = ScriptedModel([extracted(source), plan("work", "notes", "Analyze sources")])
    assert run_once(store, model, Settings())
    # Completion before an actual checked draft must be blocked.
    from test_worker import answer

    assert run_once(store, ScriptedModel([answer("Working notes")]), Settings())
    assert run_once(store, ScriptedModel([plan("done", "premature", "")]), Settings())
    assert store.draft_responsibility_status("user_alice", duty["id"])["status"] == "blocked"


def test_first_claim_has_request_and_consumed_intent_rejects_new_draft_name(store, alice):
    source = setup(store)
    duty = create(store, source)
    assert run_once(
        store,
        ScriptedModel([extracted(source), plan("draft", "first", "Private draft")]),
        Settings(),
    )
    lease = store.claim()
    request = store.drafting_request(lease)
    assert request["policy"]["status"] == "disclosure_required"
    assert request["max_revisions"] == 2
    # Release only this disposable test lease, simulating recovery before dispatch.
    with store.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.tasks SET status='ready',lease_token=NULL,"
            "lease_until=NULL,available_at=now() WHERE id=%s",
            (lease.task_id,),
        )
    assert run_once(
        store, ScriptedModel([permitted(), draft_turn(source), assessment()]), Settings()
    )
    assert run_once(store, ScriptedModel([plan("draft", "second-name", "Repeat")]), Settings())
    state = store.draft_responsibility_status("user_alice", duty["id"])
    assert state["status"] == "blocked"
    with store.connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.drafting_requests").fetchone()[
                "n"
            ]
            == 1
        )


def test_intent_and_bindings_roll_back_if_initial_plan_fails(store, alice):
    source = setup(store)

    class FailingStore(Store):
        def _responsibility_task(self, conn, *args, **kwargs):
            raise RuntimeError("Synthetic setup failure")

    with pytest.raises(RuntimeError):
        create(FailingStore(store._url), source)
    assert store.responsibilities("user_alice") == []
    with store.connection() as conn:
        assert not conn.execute("SELECT 1 FROM wrytely_agent.private_draft_intents").fetchall()
        assert not conn.execute("SELECT 1 FROM wrytely_agent.responsibility_sources").fetchall()


@pytest.mark.parametrize("control", ["pause", "source_change"])
def test_control_change_during_extraction_prevents_assessment_commit(store, alice, control):
    source = setup(store)
    duty = create(store, source)

    class ChangingModel:
        def turn(self, history, tools):
            if control == "pause":
                store.set_paused("user_alice", True)
            else:
                store.observe_source(
                    "user_alice",
                    SourceObservation(
                        source_key="draft-policy",
                        external_revision="v2",
                        title="Changed",
                        reference="synthetic:assignment",
                        coverage="snapshot",
                        content=TEXT,
                        retrieved_at=datetime.now(UTC),
                    ),
                )
            return extracted(source)

    assert run_once(store, ChangingModel(), Settings())
    state = store.draft_responsibility_status("user_alice", duty["id"])
    assert state["assessment_state"] == "pending"
    with store.connection() as conn:
        assert not conn.execute("SELECT 1 FROM wrytely_agent.drafting_requests").fetchall()
