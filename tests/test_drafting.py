import json

import pytest
from test_artifacts import assessment, prepare
from test_worker import ScriptedModel

from contracts.models import ModelTurn
from runtime.drafting import generate_checked_draft
from shared.config import Settings
from shared.db import RequestConflict, Store


def structured(name, payload):
    return ModelTurn(
        [
            {
                "type": "function_call",
                "name": name,
                "call_id": "one",
                "arguments": json.dumps(payload),
            }
        ],
        "",
        15,
        10,
    )


def permitted():
    return structured(
        "assess_drafting_permission", {"allowed": True, "reason": "Policy permits drafting."}
    )


def test_generation_saves_checks_and_recovers_without_repeating_calls(store, alice):
    lease, _, policy, rubric, _, draft = prepare(store, alice)
    model = ScriptedModel(
        [permitted(), structured("save_review_draft", draft.model_dump(mode="json")), assessment()]
    )
    result = generate_checked_draft(
        store, model, Settings(), lease, workflow_key="work", policy=policy, rubric=rubric
    )
    assert result["state"] == "ready"
    assert store.artifact("user_alice", result["artifact_id"])["state"] == "ready"
    # Same live task and workflow: already saved draft/checks are reused.
    recovered = generate_checked_draft(
        Store(store._url),
        ScriptedModel([]),
        Settings(),
        lease,
        workflow_key="work",
        policy=policy,
        rubric=rubric,
    )
    assert recovered["artifact_id"] == result["artifact_id"]
    assert len(model.histories) == 3


def test_review_feedback_drives_a_bounded_revision(store, alice):
    lease, _, policy, rubric, _, draft = prepare(store, alice)
    revised = draft.model_copy(update={"title": "Revised draft"})
    model = ScriptedModel(
        [
            permitted(),
            structured("save_review_draft", draft.model_dump(mode="json")),
            assessment(rubric_coverage=["missing"]),
            structured("save_review_draft", revised.model_dump(mode="json")),
            assessment(),
        ]
    )
    result = generate_checked_draft(
        store, model, Settings(), lease, workflow_key="work", policy=policy, rubric=rubric
    )
    assert result["state"] == "ready"
    assert "rubric_not_covered" in model.histories[3][-1]["content"]
    assert "previous_draft" in model.histories[3][-1]["content"]
    assert store.artifact("user_alice", result["artifact_id"])["draft"]["title"] == "Revised draft"


def test_no_draft_is_generated_when_preflight_denies_policy(store, alice):
    lease, _, policy, rubric, _, _ = prepare(store, alice)
    model = ScriptedModel(
        [
            structured(
                "assess_drafting_permission", {"allowed": False, "reason": "Conflicting policy."}
            )
        ]
    )
    result = generate_checked_draft(
        store, model, Settings(), lease, workflow_key="work", policy=policy, rubric=rubric
    )
    assert result["state"] == "blocked"
    assert result["artifact_id"] is None
    assert store.draft_progress(lease, "work:0") == (None, None)
    assert len(model.histories) == 1


def test_unknown_policy_blocks_before_inference(store, alice):
    lease, _, policy, rubric, _, _ = prepare(store, alice, policy_status="unknown")
    with pytest.raises(ValueError):
        generate_checked_draft(
            store,
            ScriptedModel([]),
            Settings(),
            lease,
            workflow_key="work",
            policy=policy,
            rubric=rubric,
        )


def test_revision_budget_cannot_be_increased_under_same_workflow_key(store, alice):
    lease, _, policy, rubric, _, draft = prepare(store, alice)
    model = ScriptedModel(
        [
            permitted(),
            structured("save_review_draft", draft.model_dump(mode="json")),
            assessment(claim_support=["uncertain"]),
        ]
    )
    result = generate_checked_draft(
        store,
        model,
        Settings(),
        lease,
        workflow_key="work",
        policy=policy,
        rubric=rubric,
        max_revisions=0,
    )
    assert result["state"] == "needs_revision"
    with pytest.raises(RequestConflict):
        generate_checked_draft(
            store,
            ScriptedModel([]),
            Settings(),
            lease,
            workflow_key="work",
            policy=policy,
            rubric=rubric,
            max_revisions=2,
        )


def test_saved_draft_recovers_after_assessor_failure(store, alice):
    lease, _, policy, rubric, _, draft = prepare(store, alice)
    model = ScriptedModel(
        [
            permitted(),
            structured("save_review_draft", draft.model_dump(mode="json")),
            RuntimeError("provider unavailable"),
        ]
    )
    with pytest.raises(RuntimeError):
        generate_checked_draft(
            store, model, Settings(), lease, workflow_key="work", policy=policy, rubric=rubric
        )
    artifact, _ = store.draft_progress(lease, "work:0")
    assert artifact["state"] == "review"
    resumed = ScriptedModel([assessment()])
    result = generate_checked_draft(
        Store(store._url),
        resumed,
        Settings(),
        lease,
        workflow_key="work",
        policy=policy,
        rubric=rubric,
    )
    assert result["artifact_id"] == artifact["id"]
    assert len(resumed.histories) == 1


def test_new_worker_attempt_recovers_saved_generation_after_interruption(store, alice):
    lease, _, policy, rubric, _, draft = prepare(store, alice)
    model = ScriptedModel(
        [
            permitted(),
            structured("save_review_draft", draft.model_dump(mode="json")),
            RuntimeError("Interrupted review"),
        ]
    )
    with pytest.raises(RuntimeError):
        generate_checked_draft(
            store, model, Settings(), lease, workflow_key="work", policy=policy, rubric=rubric
        )
    with store.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.tasks SET lease_until=now()-interval '1 second' WHERE id=%s",
            (lease.task_id,),
        )
    restarted = Store(store._url)
    new_lease = restarted.claim()
    assert new_lease.task_id == lease.task_id
    resumed = ScriptedModel([assessment()])
    result = generate_checked_draft(
        restarted, resumed, Settings(), new_lease, workflow_key="work", policy=policy, rubric=rubric
    )
    assert result["state"] == "ready"
    assert len(resumed.histories) == 1


def test_policy_failure_after_generation_stops_revision_loop(store, alice):
    lease, _, policy, rubric, _, draft = prepare(store, alice)
    model = ScriptedModel(
        [
            permitted(),
            structured("save_review_draft", draft.model_dump(mode="json")),
            assessment(policy_allows_drafting=False),
        ]
    )
    result = generate_checked_draft(
        store, model, Settings(), lease, workflow_key="work", policy=policy, rubric=rubric
    )
    assert result["state"] == "blocked"
    assert len(model.histories) == 3
