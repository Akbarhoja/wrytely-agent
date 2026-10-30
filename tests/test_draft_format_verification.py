import pytest
import test_artifacts
from test_artifacts import assessment, prepare
from test_drafting import permitted, structured
from test_worker import ScriptedModel

from contracts.artifacts import RubricItem
from runtime.drafting import generate_checked_draft
from runtime.verification import verify_artifact
from shared.config import Settings


def setup(store, alice, monkeypatch, body="Source A reports 10 participants."):
    monkeypatch.setattr(
        test_artifacts,
        "TEXT",
        test_artifacts.TEXT + "\nWrite a 5–8 word draft.\n"
        "Include this disclosure separately from the word-counted body:\n"
        "Draft prepared with AI; student review required.",
    )
    lease, _, policy, _, source, draft = prepare(
        store, alice, policy_status="disclosure_required", body=body
    )
    draft = draft.model_copy(
        update={"disclosure": "Draft prepared with AI; student review required."}
    )
    rubric = [RubricItem(version_id=source["id"], quote="Write a 5–8 word draft.")]
    return lease, policy, rubric, draft


def test_separate_disclosure_and_numeric_check_persist_before_readiness(store, alice, monkeypatch):
    lease, policy, rubric, draft = setup(store, alice, monkeypatch)
    artifact = store.save_draft(lease, draft, "format")
    report = verify_artifact(
        store,
        ScriptedModel([assessment()]),
        Settings(),
        lease,
        artifact["id"],
        policy=policy,
        rubric=rubric,
    )
    assert report["passed"]
    assert report["deterministic_checks"]["word_count"] == 5
    assert report["deterministic_checks"]["disclosure_placement"] == "separate_field"
    review = store.artifact_review("user_alice", artifact["id"])
    assert review["latest_check"] == report
    assert review["artifact"]["state"] == "ready"


def test_out_of_range_blocks_before_semantic_call_and_drives_revision(store, alice, monkeypatch):
    lease, policy, rubric, draft = setup(store, alice, monkeypatch)
    long = draft.model_copy(update={"body": draft.body + " Extra words exceed this range limit."})
    model = ScriptedModel(
        [
            permitted(),
            structured("save_review_draft", long.model_dump(mode="json")),
            structured("save_review_draft", draft.model_dump(mode="json")),
            assessment(),
        ]
    )
    outcome = generate_checked_draft(
        store,
        model,
        Settings(),
        lease,
        workflow_key="format",
        policy=policy,
        rubric=rubric,
        max_revisions=1,
    )
    assert outcome["state"] == "ready"
    assert "word_count_out_of_range" in model.histories[2][-1]["content"]
    assert store.artifact("user_alice", outcome["artifact_id"])["draft"]["body"] == draft.body


@pytest.mark.parametrize(
    "kind,error",
    [
        ("wrong_disclosure", "disclosure_text_mismatch"),
        ("in_body", "disclosure_must_be_separate"),
        ("word_count", "word_count_out_of_range"),
    ],
)
def test_format_failures_never_mark_ready(store, alice, monkeypatch, kind, error):
    lease, policy, rubric, draft = setup(store, alice, monkeypatch)
    if kind == "wrong_disclosure":
        draft = draft.model_copy(update={"disclosure": "Incorrect disclosure"})
    elif kind == "in_body":
        draft = draft.model_copy(update={"body": draft.body + "\n" + draft.disclosure})
    else:
        draft = draft.model_copy(
            update={"body": draft.body + " Too many extra words for the limit."}
        )
    artifact = store.save_draft(lease, draft, "bad-format")
    report = verify_artifact(
        store, ScriptedModel([]), Settings(), lease, artifact["id"], policy=policy, rubric=rubric
    )
    assert error in report["errors"]
    assert not report["passed"]
    assert store.artifact("user_alice", artifact["id"])["state"] == "needs_revision"
