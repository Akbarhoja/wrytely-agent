import pytest
from test_academic_memory import observation
from test_planner import plan
from test_worker import ScriptedModel, answer

from runtime.worker import run_once
from shared.config import Settings
from shared.db import LeaseLost


def duty(store, alice, max_steps=6):
    r = store.create_responsibility(
        "user_alice", "Track rubric requirements", "duty", max_steps=max_steps
    )
    first = store.observe_source("user_alice", observation(age=1))
    store.bind_source("user_alice", r["id"], first["source_id"])
    store.set_source_reassessment("user_alice", r["id"], True)
    return r, first


def update(store, revision="v2"):
    return store.observe_source(
        "user_alice", observation(revision, content="Updated rubric requires five sources.")
    )


def test_changed_source_queues_one_new_plan_and_fences_old_attempt(store, alice):
    r, _ = duty(store, alice)
    old = store.claim()
    v = update(store)
    assert update(store)["id"] == v["id"]
    with pytest.raises(LeaseLost):
        store.complete(old, "Stale result")
    tasks = store.tasks("user_alice")
    assert sum(t["status"] == "ready" for t in tasks) == 1
    assert sum(t["status"] == "blocked" for t in tasks) == 1
    model = ScriptedModel([plan()])
    assert run_once(store, model, Settings())
    assert "five sources" in model.histories[0][-1]["content"]
    assert store.responsibilities("user_alice")[0]["status"] == "active"


def test_same_step_can_be_revised_under_new_memory_version(store, alice):
    r, _ = duty(store, alice)
    run_once(store, ScriptedModel([plan()]), Settings())
    run_once(store, ScriptedModel([answer("Three sources required.")]), Settings())
    update(store)
    model = ScriptedModel(
        [plan(), answer("Five sources now required."), plan("done", "reviewed", "")]
    )
    for _ in range(3):
        assert run_once(store, model, Settings())
    assert store.responsibilities("user_alice")[0]["status"] == "done"
    assert store.responsibilities("user_alice")[0]["steps_created"] == 2
    assert '"stale": true' in model.histories[0][-1]["content"]
    assert not run_once(store, ScriptedModel([]), Settings())


def test_finished_duty_reopens_only_with_remaining_original_budget(store, alice):
    r, _ = duty(store, alice, max_steps=1)
    for turn in [plan(), answer(), plan("done", "done", "")]:
        run_once(store, ScriptedModel([turn]), Settings())
    update(store)
    saved = store.responsibilities("user_alice")[0]
    assert saved["status"] == "blocked"
    assert saved["steps_created"] == 1
    assert not run_once(store, ScriptedModel([]), Settings())


def test_pause_preserves_reassessment_without_model_calls(store, alice):
    duty(store, alice)
    store.set_paused("user_alice", True)
    update(store)
    assert not run_once(store, ScriptedModel([]), Settings())
    store.set_paused("user_alice", False)
    assert run_once(store, ScriptedModel([plan("blocked", "missing", "")]), Settings())


def test_blocked_policy_duty_is_not_automatically_reopened(store, alice):
    r, _ = duty(store, alice)
    run_once(store, ScriptedModel([plan("blocked", "policy-conflict", "")]), Settings())
    update(store)
    assert store.responsibilities("user_alice")[0]["status"] == "blocked"
    assert not run_once(store, ScriptedModel([]), Settings())


def test_late_version_does_not_create_reassessment(store, alice):
    duty(store, alice)
    before = len(store.tasks("user_alice"))
    store.observe_source("user_alice", observation("older", age=48))
    assert len(store.tasks("user_alice")) == before


def test_only_owner_can_enable_and_setting_requires_boolean(store, alice):
    r, _ = duty(store, alice)
    store.provision("user_bob")
    with pytest.raises(LookupError):
        store.set_source_reassessment("user_bob", r["id"], True)
    with pytest.raises(ValueError):
        store.set_source_reassessment("user_alice", r["id"], "yes")
    store.set_source_reassessment("user_alice", r["id"], False)
    update(store)
    assert store.responsibilities("user_alice")[0]["status"] == "blocked"
    assert not run_once(store, ScriptedModel([]), Settings())


def test_done_cannot_reuse_only_stale_results(store, alice):
    duty(store, alice)
    run_once(store, ScriptedModel([plan()]), Settings())
    run_once(store, ScriptedModel([answer("Old requirements")]), Settings())
    update(store)
    run_once(store, ScriptedModel([plan("done", "done", "")]), Settings())
    saved = store.responsibilities("user_alice")[0]
    assert saved["status"] == "blocked"
    assert saved["status_reason"] == "no_completed_work"


def test_completed_duty_with_budget_reassesses_new_requirements(store, alice):
    duty(store, alice)
    for turn in [plan(), answer("Old analysis"), plan("done", "done", "")]:
        run_once(store, ScriptedModel([turn]), Settings())
    assert store.responsibilities("user_alice")[0]["status"] == "done"
    update(store)
    assert store.responsibilities("user_alice")[0]["status"] == "active"
    assert run_once(store, ScriptedModel([plan()]), Settings())


def test_reassessment_queue_failure_rolls_back_source_promotion(store, alice, monkeypatch):
    _, first = duty(store, alice)
    old = store.claim()

    def fail(*args, **kwargs):
        raise RuntimeError("Simulated queue write failure")

    monkeypatch.setattr(store, "_responsibility_task", fail)
    with pytest.raises(RuntimeError):
        update(store)
    with store.connection() as conn:
        latest = conn.execute(
            "SELECT latest_version_id FROM wrytely_agent.academic_sources WHERE id=%s",
            (first["source_id"],),
        ).fetchone()["latest_version_id"]
    assert latest == first["id"]
    assert store.context(old)["responsibility"]["status"] == "active"


def test_multiple_changes_leave_only_latest_planning_task_ready(store, alice):
    duty(store, alice)
    update(store)
    update(store, revision="v3")
    assert sum(t["status"] == "ready" for t in store.tasks("user_alice")) == 1
    assert run_once(store, ScriptedModel([plan()]), Settings())
