from datetime import UTC, datetime

import pytest
from test_artifacts import TEXT, assessment
from test_drafting import permitted, structured
from test_planner import plan
from test_worker import ScriptedModel, answer

from contracts.artifacts import CoursePolicy, DraftArtifact, RubricItem
from contracts.models import SourceObservation
from runtime.worker import run_once
from shared.config import Settings
from shared.db import RequestConflict, Store


def setup_duty(store, alice):
    duty = store.create_responsibility("user_alice", "Compare sources", "duty")
    source = store.observe_source(
        "user_alice",
        SourceObservation(
            source_key="assignment",
            external_revision="v1",
            title="Assignment",
            reference="synthetic:assignment",
            coverage="snapshot",
            content=TEXT,
            retrieved_at=datetime.now(UTC),
        ),
    )
    store.bind_source("user_alice", duty["id"], source["source_id"])
    run_once(store, ScriptedModel([plan()]), Settings())
    task = next(t for t in store.tasks("user_alice") if t["status"] == "ready")
    policy = CoursePolicy(
        status="permitted",
        version_id=source["id"],
        quote="AI drafting is permitted with disclosure.",
    )
    rubric = [RubricItem(version_id=source["id"], quote="Compare two sources.")]
    draft = DraftArtifact(
        title="Review",
        body="Source A reports 10 participants.",
        disclosure="",
        citations=[
            {
                "version_id": source["id"],
                "claim": "Source A reports 10 participants.",
                "quote": "Source A reports 10 participants.",
            }
        ],
    )
    return task, policy, rubric, draft


def configure(store, task, policy, rubric, **kwargs):
    store.configure_drafting_task("user_alice", task["id"], policy=policy, rubric=rubric, **kwargs)


def test_worker_dispatches_checked_draft_then_continues_planning(store, alice):
    task, policy, rubric, draft = setup_duty(store, alice)
    configure(store, task, policy, rubric)
    model = ScriptedModel(
        [permitted(), structured("save_review_draft", draft.model_dump(mode="json")), assessment()]
    )
    assert run_once(store, model, Settings())
    assert store.task("user_alice", task["id"])["status"] == "done"
    assert any(t["status"] == "ready" for t in store.tasks("user_alice"))
    with store.connection() as conn:
        artifact = conn.execute("SELECT * FROM wrytely_agent.artifacts").fetchone()
        assert artifact["state"] == "ready"
        assert not conn.execute("SELECT * FROM wrytely_agent.whatsapp_outbound").fetchall()
    assert store.messages("user_alice") == []


def test_ordinary_academic_task_does_not_enable_assignment_drafting(store, alice):
    task, _, _, _ = setup_duty(store, alice)
    model = ScriptedModel([answer("Internal analysis only")])
    run_once(store, model, Settings())
    assert store.task("user_alice", task["id"])["status"] == "done"
    with store.connection() as conn:
        assert not conn.execute("SELECT * FROM wrytely_agent.artifacts").fetchall()


def test_configuration_is_private_idempotent_and_immutable(store, alice):
    task, policy, rubric, _ = setup_duty(store, alice)
    configure(store, task, policy, rubric)
    configure(store, task, policy, rubric)
    with pytest.raises(RequestConflict):
        configure(store, task, policy, rubric, max_revisions=0)
    store.provision("user_bob")
    with pytest.raises(LookupError):
        store.configure_drafting_task("user_bob", task["id"], policy=policy, rubric=rubric)


def test_started_task_cannot_be_upgraded_to_drafting(store, alice):
    task, policy, rubric, _ = setup_duty(store, alice)
    store.claim()
    with pytest.raises(ValueError):
        configure(store, task, policy, rubric)


def test_preflight_block_releases_slot_and_blocks_duty(store, alice):
    task, policy, rubric, _ = setup_duty(store, alice)
    configure(store, task, policy, rubric)
    model = ScriptedModel(
        [structured("assess_drafting_permission", {"allowed": False, "reason": "Policy conflict"})]
    )
    run_once(store, model, Settings())
    assert store.task("user_alice", task["id"])["status"] == "blocked"
    assert store.responsibilities("user_alice")[0]["status"] == "blocked"
    other = store.enqueue("user_alice", "Independent question", "other")
    assert run_once(store, ScriptedModel([answer()]), Settings())
    assert store.task("user_alice", other["task_id"])["status"] == "done"


def test_worker_recovers_saved_draft_after_assessor_failure(store, alice):
    task, policy, rubric, draft = setup_duty(store, alice)
    configure(store, task, policy, rubric)
    run_once(
        store,
        ScriptedModel(
            [
                permitted(),
                structured("save_review_draft", draft.model_dump(mode="json")),
                RuntimeError("Review interrupted"),
            ]
        ),
        Settings(),
    )
    with store.connection() as conn:
        conn.execute("UPDATE wrytely_agent.tasks SET available_at=now() WHERE id=%s", (task["id"],))
    resumed = ScriptedModel([assessment()])
    assert run_once(Store(store._url), resumed, Settings())
    assert len(resumed.histories) == 1
    assert store.task("user_alice", task["id"])["status"] == "done"
    with store.connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.artifacts").fetchone()["n"] == 1
        )


def test_revision_exhaustion_is_not_reported_as_task_success(store, alice):
    task, policy, rubric, draft = setup_duty(store, alice)
    configure(store, task, policy, rubric, max_revisions=0)
    run_once(
        store,
        ScriptedModel(
            [
                permitted(),
                structured("save_review_draft", draft.model_dump(mode="json")),
                assessment(claim_support=["uncertain"]),
            ]
        ),
        Settings(),
    )
    row = store.task("user_alice", task["id"])
    assert row["status"] == "blocked"
    assert row["last_error"] == "drafting_needs_revision"


def test_pause_prevents_any_generation(store, alice):
    task, policy, rubric, _ = setup_duty(store, alice)
    configure(store, task, policy, rubric)
    store.set_paused("user_alice", True)
    assert not run_once(store, ScriptedModel([]), Settings())


def test_unbound_policy_cannot_configure_draft_dispatch(store, alice):
    from uuid import uuid4

    task, policy, rubric, _ = setup_duty(store, alice)
    with pytest.raises(ValueError, match="evidence"):
        configure(store, task, policy.model_copy(update={"version_id": uuid4()}), rubric)


def test_changed_source_stops_configured_work_before_generation(store, alice):
    from datetime import timedelta

    task, policy, rubric, _ = setup_duty(store, alice)
    configure(store, task, policy, rubric)
    store.observe_source(
        "user_alice",
        SourceObservation(
            source_key="assignment",
            external_revision="v2",
            title="Updated",
            reference="synthetic:updated",
            coverage="snapshot",
            content="Changed requirements",
            retrieved_at=datetime.now(UTC) + timedelta(seconds=1),
        ),
    )
    assert not run_once(store, ScriptedModel([]), Settings())
    assert store.task("user_alice", task["id"])["last_error"] == "source_changed"
