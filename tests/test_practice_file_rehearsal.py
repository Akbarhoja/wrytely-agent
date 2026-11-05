"""Operator fixture through real original drafting/checks; all model IO synthetic."""

from copy import deepcopy

import pytest
from test_artifacts import assessment
from test_drafting import permitted, structured
from test_json_draft_journey import json_provider

from runtime.artifact_rendering import render_private_artifact_docx
from runtime.drafting import generate_checked_draft
from runtime.worker import run_episode
from scripts.practice_file_rehearsal import (
    CLAIM_A,
    CLAIM_B,
    DISCLOSURE,
    claim_practice_task,
    prepare_practice,
)
from shared.config import Settings
from shared.db import Store


def draft_for(data):
    return dict(
        schema_version=2,
        title="SYNTHETIC PRACTICE comparison",
        body=f"{CLAIM_A}\n{CLAIM_B}\n{DISCLOSURE}",
        disclosure=DISCLOSURE,
        citations=[
            dict(
                claim=claim,
                evidence=dict(kind="legacy", version_id=str(data["source"]["id"]), quote=claim),
            )
            for claim in (CLAIM_A, CLAIM_B)
        ],
    )


def test_practice_json_draft_and_original_revision_retain_immutable_private_files(store, alice):
    data = prepare_practice(store, "user_alice", approved=True)
    draft = draft_for(data)
    revised = deepcopy(draft)
    revised["title"] = "Revised SYNTHETIC PRACTICE comparison"
    turns = [
        permitted(),
        structured("save_review_draft", draft),
        assessment(claim_support=["supported", "supported"]),
        permitted(),
        structured("save_review_draft", revised),
        assessment(claim_support=["supported", "supported"]),
    ]
    model, requests = json_provider(turns)
    try:
        lease = claim_practice_task(store, "user_alice", data["task_id"], data["duty"]["id"])
        result = generate_checked_draft(
            store,
            model,
            Settings(),
            lease,
            workflow_key="synthetic-practice",
            policy=data["policy"],
            rubric=data["rubric"],
            max_revisions=0,
        )
        assert result["state"] == "ready"
        first = render_private_artifact_docx(store, "user_alice", result["artifact_id"])
        store.complete(lease, "Synthetic checked practice prepared; not coursework.")
        revision = store.request_private_artifact_revision(
            "user_alice", result["artifact_id"], "Use a title beginning with Revised", "practice-r1"
        )
        restarted = Store(store._url, canvas_origins=tuple(store._canvas_origins))
        second_lease = claim_practice_task(
            restarted, "user_alice", revision["task_id"], data["duty"]["id"]
        )
        run_episode(restarted, model, Settings(), second_lease)
        with store.connection() as conn:
            child = conn.execute(
                "SELECT id,state FROM wrytely_agent.artifacts WHERE task_id=%s",
                (revision["task_id"],),
            ).fetchone()
        assert child["state"] == "ready"
        second = render_private_artifact_docx(store, "user_alice", child["id"])
        assert first.content != second.content
        assert (
            render_private_artifact_docx(store, "user_alice", first.artifact_id).content
            == first.content
        )
        assert len(requests) == 6
        with pytest.raises(ValueError):
            claim_practice_task(restarted, "user_alice", revision["task_id"], data["duty"]["id"])
    finally:
        model._client.close()


def test_practice_requires_explicit_setup_and_rejects_different_owner(store, alice):
    with pytest.raises(ValueError):
        prepare_practice(store, "user_alice")
    with store.connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.academic_sources").fetchone()["n"]
            == 0
        )
    data = prepare_practice(store, "user_alice", approved=True)
    store.provision("user_bob")
    other = store.create_responsibility("user_bob", "Unrelated queued analysis", "other")
    with pytest.raises(ValueError):
        claim_practice_task(store, "user_bob", data["task_id"], data["duty"]["id"])
    lease = claim_practice_task(store, "user_alice", data["task_id"], data["duty"]["id"])
    assert lease.task_id == data["task_id"]
    with store.connection() as conn:
        untouched = conn.execute(
            "SELECT status,attempts FROM wrytely_agent.tasks WHERE responsibility_id=%s",
            (other["id"],),
        ).fetchone()
    assert untouched == dict(status="ready", attempts=0)


def test_practice_claim_respects_pause_and_never_claims_concurrent_owner_work(store, alice):
    first = prepare_practice(store, "user_alice", approved=True)
    second = prepare_practice(store, "user_alice", approved=True)
    store.set_paused("user_alice", True)
    with pytest.raises(ValueError):
        claim_practice_task(store, "user_alice", first["task_id"], first["duty"]["id"])
    store.set_paused("user_alice", False)
    claim_practice_task(store, "user_alice", first["task_id"], first["duty"]["id"])
    with pytest.raises(ValueError):
        claim_practice_task(store, "user_alice", second["task_id"], second["duty"]["id"])
