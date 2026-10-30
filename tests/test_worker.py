from contracts.models import ModelTurn
from runtime.worker import run_once
from shared.config import Settings
from shared.db import Store


class ScriptedModel:
    def __init__(self, turns):
        self.turns = iter(turns)
        self.histories = []

    def turn(self, history, tools):
        self.histories.append(list(history))
        value = next(self.turns)
        if isinstance(value, Exception):
            raise value
        return value


def function_turn(arguments="{}", name="get_academic_context"):
    return ModelTurn(
        [{"type": "function_call", "name": name, "call_id": "call_one", "arguments": arguments}],
        "",
        30,
        10,
    )


def answer(text="Here is your answer"):
    return ModelTurn(
        [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text}],
            }
        ],
        text,
        50,
        20,
    )


def test_tool_loop_persists_usage_and_private_result(store, alice):
    store.enqueue("user_alice", "Explain the project", "one")
    store.provision("user_bob")
    store.enqueue("user_bob", "Bob's private notes", "one")
    model = ScriptedModel([function_turn(), answer()])
    assert run_once(store, model, Settings())
    assert store.messages("user_alice")[-1]["content"] == "Here is your answer"
    assert "Bob's private notes" not in str(model.histories)
    assert len(store.messages("user_bob")) == 1


def test_unknown_or_cross_user_tool_not_executed(store, alice):
    store.enqueue("user_alice", "Read someone else's context", "one")
    model = ScriptedModel([function_turn('{"user_id":"user_bob"}'), answer()])
    run_once(store, model, Settings())
    assert "tool_not_permitted" in str(model.histories[-1])


def test_model_failure_is_bounded_and_redacts_provider_error(store, alice):
    task = store.enqueue("user_alice", "Question", "one")
    model = ScriptedModel([RuntimeError("api-key-secret should never be stored")])
    run_once(store, model, Settings(max_attempts=1))
    row = store.task("user_alice", task["task_id"])
    assert row["status"] == "blocked"
    assert row["last_error"] == "execution_failed"
    assert len(store.messages("user_alice")) == 1


def test_turn_budget_records_handoff_then_blocks_when_attempts_exhausted(store, alice):
    task = store.enqueue("user_alice", "Question", "one")
    model = ScriptedModel([function_turn()])
    run_once(store, model, Settings(max_episode_turns=1, max_attempts=1))
    assert store.task("user_alice", task["task_id"])["status"] == "blocked"
    with store.connection() as conn:
        row = conn.execute(
            "SELECT data FROM wrytely_agent.episode_events WHERE task_id=%s AND kind='handoff'",
            (task["task_id"],),
        ).fetchone()
        assert row["data"]["reason"] == "episode_turn_budget"


def test_worker_restart_processes_existing_durable_work(store, alice):
    task = store.enqueue("user_alice", "Question", "one")
    restarted = Store(store._url)
    assert run_once(restarted, ScriptedModel([answer()]), Settings())
    assert store.task("user_alice", task["task_id"])["status"] == "done"


def test_paused_student_does_not_trigger_model_call(store, alice):
    store.enqueue("user_alice", "Question", "one")
    store.set_paused("user_alice", True)
    assert not run_once(store, ScriptedModel([]), Settings())


def test_unsuccessful_model_usage_is_private_evidence_not_an_answer(store, alice):
    from types import SimpleNamespace

    from shared.model_client import ModelCallFailed

    task = store.enqueue("user_alice", "Question", "failed-model-usage")
    failure = ModelCallFailed(
        status="incomplete", usage=SimpleNamespace(input_tokens=120, output_tokens=2048)
    )
    run_once(store, ScriptedModel([failure]), Settings(max_attempts=1))
    assert store.task("user_alice", task["task_id"])["status"] == "blocked"
    assert len(store.messages("user_alice")) == 1
    with store.connection() as conn:
        rows = conn.execute(
            "SELECT kind,data FROM wrytely_agent.episode_events WHERE task_id=%s",
            (task["task_id"],),
        ).fetchall()
    assert [(r["kind"], r["data"]) for r in rows if r["kind"] == "model_failure"] == [
        (
            "model_failure",
            {
                "status": "incomplete",
                "http_status": None,
                "code": None,
                "input_tokens": 120,
                "output_tokens": 2048,
            },
        )
    ]
    assert not any(r["kind"] == "model_turn" for r in rows)
