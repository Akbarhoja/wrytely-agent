import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_worker import ScriptedModel, answer

from contracts.models import ModelTurn
from runtime.worker import run_once
from shared.config import Settings
from shared.db import QueueFull, RequestConflict, Store


def plan(action="work", key="requirements", instruction="Extract the supplied rubric requirements"):
    return ModelTurn(
        [
            {
                "type": "function_call",
                "name": "record_plan",
                "call_id": "plan_one",
                "arguments": json.dumps(
                    {
                        "action": action,
                        "reason": "Advances the objective",
                        "step_key": key,
                        "instruction": instruction,
                    }
                ),
            }
        ],
        "",
        30,
        10,
    )


def test_three_self_selected_steps_across_worker_restarts_without_new_inputs(store, alice):
    responsibility = store.create_responsibility(
        "user_alice",
        "Analyze the supplied rubric: compare two sources, make a structure, identify gaps.",
        "duty",
    )
    model = ScriptedModel(
        [
            plan(),
            answer("Two sources and a comparison are required."),
            plan(
                key="structure", instruction="Develop a structure from the extracted requirements"
            ),
            answer("Use introduction, comparison and conclusion."),
            plan(key="gaps", instruction="Review the structure for missing evidence"),
            answer("We still need the two original sources before making claims."),
            plan("done", "analysis-complete", ""),
        ]
    )
    for _ in range(7):
        assert run_once(Store(store._url), model, Settings())
    assert not run_once(Store(store._url), ScriptedModel([]), Settings())
    saved = store.responsibilities("user_alice")[0]
    assert saved["id"] == responsibility["id"]
    assert saved["status"] == "done"
    assert saved["steps_created"] == 3
    assert all(isinstance(item["content"], str) for item in model.histories[0])
    assert "Two sources and a comparison" in str(model.histories[2])
    assert "Use introduction" in str(model.histories[4])
    assert store.messages("user_alice") == []  # Internal work never impersonates chat.


def test_duplicate_step_stops_instead_of_repeating(store, alice):
    store.create_responsibility("user_alice", "Analyze rubric", "duty")
    model = ScriptedModel([plan(), answer(), plan()])
    for _ in range(3):
        run_once(store, model, Settings())
    row = store.responsibilities("user_alice")[0]
    assert row["status"] == "blocked"
    assert row["steps_created"] == 1
    assert not run_once(store, ScriptedModel([]), Settings())


def test_budget_blocks_even_when_model_changes_step_name(store, alice):
    store.create_responsibility("user_alice", "Analyze rubric", "duty", max_steps=1)
    model = ScriptedModel([plan(), answer(), plan(key="another-step")])
    for _ in range(3):
        run_once(store, model, Settings())
    assert store.responsibilities("user_alice")[0]["status"] == "blocked"
    assert store.responsibilities("user_alice")[0]["steps_created"] == 1


def test_blocked_duty_does_not_stop_other_work(store, alice):
    store.create_responsibility("user_alice", "Need missing assignment", "blocked")
    run_once(store, ScriptedModel([plan("blocked", "missing", "")]), Settings())
    task = store.enqueue("user_alice", "Independent question", "other")
    assert run_once(store, ScriptedModel([answer()]), Settings())
    assert store.task("user_alice", task["task_id"])["status"] == "done"


def test_duties_are_idempotent_private_and_bounded(store, alice):
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(
            pool.map(
                lambda _: store.create_responsibility("user_alice", "Analyze", "duty"), range(4)
            )
        )
    assert len({row["id"] for row in rows}) == 1
    assert len(store.tasks("user_alice")) == 1
    with pytest.raises(RequestConflict):
        store.create_responsibility("user_alice", "Different objective", "duty")
    with pytest.raises(QueueFull):
        store.create_responsibility("user_alice", "Another", "another", pending_limit=1)
    store.provision("user_bob")
    assert store.responsibilities("user_bob") == []
    store.create_responsibility("user_bob", "Bob private data", "bob")
    model = ScriptedModel([plan("blocked", "missing", "")])
    run_once(store, model, Settings())
    assert "Bob private data" not in str(model.histories)


def test_failed_planner_marks_responsibility_blocked(store, alice):
    store.create_responsibility("user_alice", "Analyze rubric", "duty")
    run_once(store, ScriptedModel([answer("Unstructured plan")]), Settings(max_attempts=1))
    assert store.responsibilities("user_alice")[0]["status"] == "blocked"
    assert store.responsibilities("user_alice")[0]["status_reason"] == "task_execution_failed"


def test_cannot_claim_done_before_any_work(store, alice):
    store.create_responsibility("user_alice", "Analyze rubric", "duty")
    run_once(store, ScriptedModel([plan("done", "done", "")]), Settings())
    assert store.responsibilities("user_alice")[0]["status_reason"] == "no_completed_work"


def test_paused_agent_does_not_plan(store, alice):
    store.create_responsibility("user_alice", "Analyze rubric", "duty")
    store.set_paused("user_alice", True)
    assert not run_once(store, ScriptedModel([]), Settings())


def test_saved_planner_decision_survives_crash_without_replanning(store, alice, monkeypatch):
    class ProcessKilled(BaseException):
        pass

    store.create_responsibility("user_alice", "Analyze supplied assignment", "duty")
    original = store.apply_plan

    def killed(*args):
        raise ProcessKilled()

    monkeypatch.setattr(store, "apply_plan", killed)
    with pytest.raises(ProcessKilled):
        run_once(store, ScriptedModel([plan()]), Settings())
    monkeypatch.setattr(store, "apply_plan", original)
    with store.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.tasks SET lease_until=now()-interval '1 second' "
            "WHERE status='running'"
        )
    assert run_once(Store(store._url), ScriptedModel([]), Settings())
    assert store.responsibilities("user_alice")[0]["steps_created"] == 1
    assert len(store.tasks("user_alice")) == 2


def test_failed_planning_transaction_creates_no_orphan_work(store, alice, monkeypatch):
    from contracts.models import PlannerDecision

    store.create_responsibility("user_alice", "Analyze", "duty")
    lease = store.claim()
    original = store._responsibility_task

    def fail_after_insert(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("Simulated storage failure before commit")

    monkeypatch.setattr(store, "_responsibility_task", fail_after_insert)
    decision = PlannerDecision(
        action="work",
        reason="Read requirements",
        step_key="requirements",
        instruction="Read supplied requirements",
    )
    with pytest.raises(RuntimeError):
        store.apply_plan(lease, decision)
    assert len(store.tasks("user_alice")) == 1
    assert store.responsibilities("user_alice")[0]["steps_created"] == 0
    assert store.task("user_alice", lease.task_id)["status"] == "running"
