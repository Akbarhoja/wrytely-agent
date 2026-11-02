"""Real task failure diagnostics without exposing content or changing recovery."""

import pytest
from test_canvas_sync import device as device
from test_planner import plan
from test_typed_document_drafting import prepared, requirements
from test_worker import ScriptedModel, answer

from runtime.worker import run_once
from shared.config import Settings
from shared.db import LeaseLost
from shared.model_client import ModelCallFailed


def failures(db):
    with db.connection() as conn:
        return [
            r["data"]
            for r in conn.execute(
                "SELECT data FROM wrytely_agent.episode_events "
                "WHERE kind='planner_failure' ORDER BY id"
            ).fetchall()
        ]


@pytest.mark.parametrize(
    "method,stage",
    [
        ("draft_intent", "intent_load"),
        ("draft_intent_sources", "source_load"),
        ("commit_draft_assessment", "assessment_commit"),
        ("saved_plan", "plan_recovery"),
        ("apply_plan", "plan_apply"),
    ],
)
def test_real_planner_records_only_controlled_failure_stage(device, monkeypatch, method, stage):
    data = prepared(device)

    def fail(*a, **kw):
        raise ValueError("PRIVATE_SOURCE_AND_TOKEN")

    monkeypatch.setattr(device[0], method, fail)
    model = ScriptedModel([requirements(data[1], data[2]), plan("draft", "comparison", "Draft")])
    assert run_once(device[0], model, Settings(max_attempts=1))
    assert failures(device[0]) == [{"stage": stage, "category": "invalid_result"}]
    with device[0].connection() as conn:
        task = conn.execute("SELECT status,last_error FROM wrytely_agent.tasks").fetchone()
        assert task == {"status": "blocked", "last_error": "execution_failed"}
        data = conn.execute("SELECT data FROM wrytely_agent.episode_events").fetchall()
    assert "PRIVATE_SOURCE_AND_TOKEN" not in str(data)


def test_model_failure_keeps_existing_usage_evidence_and_retry_semantics(store, alice):
    duty = store.create_responsibility("user_alice", "Analyze", "failure")
    model = ScriptedModel(
        [ModelCallFailed(status="http_error", http_status=429, code="rate_limit_exceeded")]
    )
    assert run_once(store, model, Settings(max_attempts=1))
    assert failures(store) == [{"stage": "plan_model", "category": "model_call_failed"}]
    with store.connection() as conn:
        event = conn.execute(
            "SELECT data FROM wrytely_agent.episode_events WHERE kind='model_failure'"
        ).fetchone()
        assert event["data"]["code"] == "rate_limit_exceeded"
        assert (
            conn.execute(
                "SELECT status FROM wrytely_agent.responsibilities WHERE id=%s", (duty["id"],)
            ).fetchone()["status"]
            == "blocked"
        )


def test_invalid_model_plan_is_diagnosed_without_echoing_raw_output(store, alice):
    store.create_responsibility("user_alice", "Analyze", "decode")
    model = ScriptedModel([answer("PRIVATE_BAD_OUTPUT")])
    assert run_once(store, model, Settings(max_attempts=1))
    assert failures(store) == [{"stage": "plan_decode", "category": "invalid_result"}]


def test_failed_diagnostic_write_does_not_replace_original_model_failure(store, alice, monkeypatch):
    store.create_responsibility("user_alice", "Analyze", "diagnostic-loss")
    original = store.event

    def event(lease, kind, value):
        if kind == "planner_failure":
            raise RuntimeError("PRIVATE_DIAGNOSTIC_FAILURE")
        return original(lease, kind, value)

    monkeypatch.setattr(store, "event", event)
    model = ScriptedModel([ModelCallFailed(status="failed", code="server_error")])
    assert run_once(store, model, Settings(max_attempts=1))
    assert failures(store) == []
    with store.connection() as conn:
        assert (
            conn.execute(
                "SELECT data FROM wrytely_agent.episode_events WHERE kind='model_failure'"
            ).fetchone()["data"]["code"]
            == "server_error"
        )


def test_revoked_lease_is_not_misclassified_as_planner_failure(store, alice, monkeypatch):
    store.create_responsibility("user_alice", "Analyze", "lost")

    def lose(*a, **kw):
        raise LeaseLost("PRIVATE_CONTROL_CHANGE")

    monkeypatch.setattr(store, "draft_intent", lose)
    assert run_once(store, ScriptedModel([]), Settings())
    assert failures(store) == []


def test_saved_plan_recovery_creates_one_child_without_new_model_call(store, alice, monkeypatch):
    store.create_responsibility("user_alice", "Analyze", "recover")
    original = store.apply_plan

    def fail(*a, **kw):
        raise RuntimeError("PRIVATE_TRANSIENT_FAILURE")

    monkeypatch.setattr(store, "apply_plan", fail)
    model = ScriptedModel([plan()])
    assert run_once(store, model, Settings())
    assert failures(store) == [{"stage": "plan_apply", "category": "unexpected_failure"}]
    monkeypatch.setattr(store, "apply_plan", original)
    with store.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.tasks SET available_at=clock_timestamp()-interval '1 second'"
        )
    recovered = ScriptedModel([])
    assert run_once(store, recovered, Settings()) and recovered.histories == []
    with store.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.tasks WHERE kind='academic'"
            ).fetchone()["n"]
            == 1
        )


def test_successful_handoff_has_no_failure_diagnostic_writes(device):
    data = prepared(device)
    model = ScriptedModel([requirements(data[1], data[2]), plan("draft", "comparison", "Draft")])
    assert run_once(device[0], model, Settings())
    assert device[0].claim() is not None
    assert failures(device[0]) == []


def test_normal_source_refresh_block_is_not_a_planner_failure(device):
    prepared(device, partial=True)
    model = ScriptedModel([])
    assert run_once(device[0], model, Settings()) and model.histories == []
    assert failures(device[0]) == []


def test_checkpoint_error_reports_stage_without_replacing_event_semantics(
    store, alice, monkeypatch
):
    store.create_responsibility("user_alice", "Analyze", "checkpoint")
    original = store.event

    def event(lease, kind, value):
        if kind == "planner_decision":
            raise KeyError("PRIVATE_CHECKPOINT_VALUE")
        return original(lease, kind, value)

    monkeypatch.setattr(store, "event", event)
    assert run_once(store, ScriptedModel([plan()]), Settings(max_attempts=1))
    assert failures(store) == [{"stage": "plan_checkpoint", "category": "missing_reference"}]
