import json
from datetime import UTC, datetime, timedelta

import pytest
from test_planner import plan
from test_worker import ScriptedModel

from contracts.artifacts import CoursePolicy, DraftArtifact, RubricItem
from contracts.models import ModelTurn, SourceObservation
from runtime.verification import verify_artifact
from runtime.worker import run_once
from shared.config import Settings
from shared.db import LeaseLost, RequestConflict

TEXT = (
    "AI drafting is permitted with disclosure. Compare two sources. "
    "Source A reports 10 participants."
)


def prepare(store, alice, policy_status="permitted", body="Source A reports 10 participants."):
    r = store.create_responsibility("user_alice", "Compare two sources", "duty")
    source = store.observe_source(
        "user_alice",
        SourceObservation(
            source_key="rubric",
            external_revision="v1",
            title="Assignment",
            reference="synthetic:assignment",
            coverage="snapshot",
            content=TEXT,
            retrieved_at=datetime.now(UTC),
        ),
    )
    store.bind_source("user_alice", r["id"], source["source_id"])
    run_once(store, ScriptedModel([plan()]), Settings())
    lease = store.claim()
    draft = DraftArtifact(
        title="Review draft",
        body=body,
        disclosure="",
        citations=[
            {
                "version_id": source["id"],
                "claim": "Source A reports 10 participants.",
                "quote": "Source A reports 10 participants.",
            }
        ],
    )
    artifact = store.save_draft(lease, draft, "draft-one")
    policy = CoursePolicy(
        status=policy_status,
        version_id=source["id"],
        quote="AI drafting is permitted with disclosure.",
    )
    rubric = [RubricItem(version_id=source["id"], quote="Compare two sources.")]
    return lease, artifact, policy, rubric, source, draft


def assessment(**changes):
    payload = {
        "claim_support": ["supported"],
        "rubric_coverage": ["covered"],
        "uncited_claims": False,
        "policy_allows_drafting": True,
        "disclosure_satisfied": True,
        "rubric_complete": True,
        "reason": "Evidence supports the listed claim and rubric.",
    } | changes
    return ModelTurn(
        [
            {
                "type": "function_call",
                "name": "assess_draft",
                "call_id": "review-one",
                "arguments": json.dumps(payload),
            }
        ],
        "",
        40,
        20,
    )


def test_saved_draft_stays_review_until_mandatory_checks_pass(store, alice):
    lease, artifact, policy, rubric, _, draft = prepare(store, alice)
    assert artifact["state"] == "review"
    assert store.save_draft(lease, draft, "draft-one")["id"] == artifact["id"]
    model = ScriptedModel([assessment()])
    report = verify_artifact(
        store, model, Settings(), lease, artifact["id"], policy=policy, rubric=rubric
    )
    assert report["passed"]
    assert store.artifact("user_alice", artifact["id"])["state"] == "ready"
    assert "policy" in json.loads(model.histories[0][-1]["content"])
    assert report["input_tokens"] == 40
    assert isinstance(model.histories[0][0]["content"], str)


@pytest.mark.parametrize(
    "change,error",
    [
        ({"claim_support": ["unsupported"]}, "claims_not_supported"),
        ({"claim_support": ["uncertain"]}, "claims_not_supported"),
        ({"rubric_coverage": ["missing"]}, "rubric_not_covered"),
        ({"rubric_coverage": []}, "assessment_coverage_mismatch"),
        ({"uncited_claims": True}, "uncited_claims"),
        ({"policy_allows_drafting": False}, "policy_assessment_failed"),
        ({"disclosure_satisfied": False}, "disclosure_assessment_failed"),
        ({"rubric_complete": False}, "rubric_incomplete"),
    ],
)
def test_failed_or_uncertain_assessment_never_marks_ready(store, alice, change, error):
    lease, artifact, policy, rubric, _, _ = prepare(store, alice)
    report = verify_artifact(
        store,
        ScriptedModel([assessment(**change)]),
        Settings(),
        lease,
        artifact["id"],
        policy=policy,
        rubric=rubric,
    )
    assert not report["passed"]
    assert error in report["errors"]
    assert store.artifact("user_alice", artifact["id"])["state"] == "needs_revision"


@pytest.mark.parametrize("status", ["unknown", "prohibited", "limited", "disclosure_required"])
def test_policy_gate_prevents_finalization_before_model_call(store, alice, status):
    lease, artifact, policy, rubric, _, _ = prepare(store, alice, policy_status=status)
    report = verify_artifact(
        store, ScriptedModel([]), Settings(), lease, artifact["id"], policy=policy, rubric=rubric
    )
    assert not report["passed"]


def test_fabricated_quote_blocks_before_semantic_assessment(store, alice):
    lease, _, policy, rubric, source, draft = prepare(store, alice)
    forged = draft.model_copy(
        update={"citations": [draft.citations[0].model_copy(update={"quote": "Fake quote"})]}
    )
    artifact = store.save_draft(lease, forged, "draft-two")
    report = verify_artifact(
        store, ScriptedModel([]), Settings(), lease, artifact["id"], policy=policy, rubric=rubric
    )
    assert "citation_missing_or_stale" in report["errors"]


def test_draft_ownership_and_key_conflicts(store, alice):
    lease, artifact, _, _, _, draft = prepare(store, alice)
    store.provision("user_bob")
    assert store.artifact("user_bob", artifact["id"]) is None
    with pytest.raises(RequestConflict):
        store.save_draft(lease, draft.model_copy(update={"body": "Changed draft"}), "draft-one")


def test_source_change_during_assessment_fences_ready_commit(store, alice):
    lease, artifact, policy, rubric, _, _ = prepare(store, alice)

    class ChangingModel:
        def turn(self, history, tools):
            store.observe_source(
                "user_alice",
                SourceObservation(
                    source_key="rubric",
                    external_revision="v2",
                    title="Changed",
                    reference="synthetic:changed",
                    coverage="snapshot",
                    content="New rubric",
                    retrieved_at=datetime.now(UTC) + timedelta(seconds=1),
                ),
            )
            return assessment()

    with pytest.raises(LeaseLost):
        verify_artifact(
            store, ChangingModel(), Settings(), lease, artifact["id"], policy=policy, rubric=rubric
        )
    saved = store.artifact("user_alice", artifact["id"])
    assert saved["stale"]
    assert saved["state"] == "review"


def test_provider_failure_leaves_draft_unready(store, alice):
    lease, artifact, policy, rubric, _, _ = prepare(store, alice)
    with pytest.raises(RuntimeError):
        verify_artifact(
            store,
            ScriptedModel([RuntimeError("Provider unavailable")]),
            Settings(),
            lease,
            artifact["id"],
            policy=policy,
            rubric=rubric,
        )
    assert store.artifact("user_alice", artifact["id"])["state"] == "review"


def test_stale_evidence_blocks_without_model_call(store, alice):
    lease, artifact, policy, rubric, source, _ = prepare(store, alice)
    # Age the synthetic fixture to exercise freshness checks (production versions
    # are immutable through the Store interface).
    with store.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.source_versions SET retrieved_at=now()-interval '2 days' "
            "WHERE id=%s",
            (source["id"],),
        )
    report = verify_artifact(
        store, ScriptedModel([]), Settings(), lease, artifact["id"], policy=policy, rubric=rubric
    )
    assert not report["passed"]
    assert "policy_evidence_missing_or_stale" in report["errors"]


def test_malformed_assessment_cannot_mark_ready(store, alice):
    lease, artifact, policy, rubric, _, _ = prepare(store, alice)
    malformed = ModelTurn(
        [
            {
                "type": "function_call",
                "name": "assess_draft",
                "call_id": "bad",
                "arguments": '{"claim_support":[]}',
            }
        ],
        "",
    )
    report = verify_artifact(
        store,
        ScriptedModel([malformed]),
        Settings(),
        lease,
        artifact["id"],
        policy=policy,
        rubric=rubric,
    )
    assert report["errors"] == ["invalid_assessment"]
    assert store.artifact("user_alice", artifact["id"])["state"] == "needs_revision"


def test_pause_during_review_blocks_finalization(store, alice):
    lease, artifact, policy, rubric, _, _ = prepare(store, alice)

    class PauseModel:
        def turn(self, history, tools):
            store.set_paused("user_alice", True)
            return assessment()

    with pytest.raises(LeaseLost):
        verify_artifact(
            store, PauseModel(), Settings(), lease, artifact["id"], policy=policy, rubric=rubric
        )
    assert store.artifact("user_alice", artifact["id"])["state"] == "review"
