"""A document-source failure needs refreshed access/evidence, never a prose revision."""

import pytest
from test_artifact_documents import setup
from test_artifacts import assessment
from test_canvas_sync import device as device
from test_worker import ScriptedModel

from runtime.drafting import generate_checked_draft
from shared.config import Settings


def workflow(device, *, partial=False):
    prepared = setup(device, partial=partial)
    db = device[0]
    lease, _, policy, rubric, citation, draft = prepared
    artifact = db.save_draft(lease, draft, "work:0", document_citations=[citation])
    # Simulate a persisted generation checkpoint, not a new student authority.
    # This suite tests recovery of already-saved pinned artifacts; generation of
    # pinned metadata and document-only task access are separate unwired consumers.
    db.event(
        lease,
        "drafting_preflight",
        {
            "workflow_key": "work",
            "allowed": True,
            "reason": "Synthetic source policy permits draft.",
        },
    )
    return prepared, artifact


def run(device, prepared, model):
    lease, _, policy, rubric, *_ = prepared
    return generate_checked_draft(
        device[0], model, Settings(), lease, workflow_key="work", policy=policy, rubric=rubric
    )


@pytest.mark.parametrize("failure", ["age", "partial", "revoke", "expiry"])
def test_unusable_saved_document_stops_without_inference_or_new_revision(device, failure):
    prepared, artifact = workflow(device, partial=failure == "partial")
    db = device[0]
    if failure == "revoke":
        db.rotate_or_revoke("user_alice", device[1]["connection_id"])
    elif failure in {"age", "expiry"}:
        with db.connection() as conn:
            if failure == "age":
                conn.execute(
                    "UPDATE wrytely_agent.canvas_evidence_observations SET "
                    "observed_at=clock_timestamp()-interval '7 hours'"
                )
            else:
                conn.execute(
                    "UPDATE wrytely_agent.source_connections SET "
                    "credential_expires_at=clock_timestamp()-interval '1 second'"
                )
    model = ScriptedModel([])
    result = run(device, prepared, model)
    assert result["state"] == "blocked" and result["artifact_id"] == artifact["id"]
    assert "document_evidence_missing_or_stale" in result["report"]["errors"]
    assert model.histories == []
    assert db.draft_progress(prepared[0], "work:1") == (None, None)
    # Retrying the workflow cannot turn the same failure into a new model revision.
    assert run(device, prepared, model)["state"] == "blocked"
    assert model.histories == []


def test_document_control_change_during_review_stops_revision_attempts(device):
    prepared, artifact = workflow(device)

    class RevokingModel(ScriptedModel):
        def turn(self, *args, **kwargs):
            result = super().turn(*args, **kwargs)
            device[0].rotate_or_revoke("user_alice", device[1]["connection_id"])
            return result

    model = RevokingModel([assessment()])
    result = run(device, prepared, model)
    assert result["state"] == "blocked" and result["artifact_id"] == artifact["id"]
    assert "document_evidence_failed_at_commit" in result["report"]["errors"]
    assert len(model.histories) == 1
    assert device[0].draft_progress(prepared[0], "work:1") == (None, None)


@pytest.mark.parametrize("failure", ["age", "revoke"])
def test_cached_document_pass_is_invalidated_without_revision_inference(device, failure):
    prepared, artifact = workflow(device)
    assert run(device, prepared, ScriptedModel([assessment()]))["state"] == "ready"
    if failure == "revoke":
        device[0].rotate_or_revoke("user_alice", device[1]["connection_id"])
    else:
        with device[0].connection() as conn:
            conn.execute(
                "UPDATE wrytely_agent.canvas_evidence_observations SET "
                "observed_at=clock_timestamp()-interval '7 hours'"
            )
    model = ScriptedModel([])
    result = run(device, prepared, model)
    assert result["state"] == "blocked" and result["artifact_id"] == artifact["id"]
    assert "document_evidence_failed_at_commit" in result["report"]["errors"]
    assert model.histories == []
    assert device[0].draft_progress(prepared[0], "work:1") == (None, None)


def test_current_pinned_draft_still_becomes_ready_and_recovers_without_new_calls(device):
    prepared, artifact = workflow(device)
    model = ScriptedModel([assessment()])
    result = run(device, prepared, model)
    assert result["state"] == "ready" and result["artifact_id"] == artifact["id"]
    assert len(model.histories) == 1
    resumed = ScriptedModel([])
    assert run(device, prepared, resumed)["state"] == "ready"
    assert resumed.histories == []
