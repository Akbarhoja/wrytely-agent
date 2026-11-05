import pytest
from test_worker import ScriptedModel, answer, function_turn

from runtime.worker import run_episode, run_once
from shared.config import Settings
from shared.db import LeaseLost, Store


class ProcessKilled(BaseException):
    """Simulates abrupt termination without running the worker's retry handler."""


def expire(store, task_id):
    with store.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.tasks SET lease_until=now()-interval '1 second' WHERE id=%s",
            (task_id,),
        )


def test_new_worker_resumes_saved_tool_result_without_rereading(store, alice, monkeypatch):
    task = store.enqueue("user_alice", "Understand this assignment", "resume-one")
    model = ScriptedModel([function_turn(), ProcessKilled()])
    # ScriptedModel only raises Exception; force a process kill at its second turn.
    original = model.turn

    def turn(history, tools):
        if model.histories:
            raise ProcessKilled()
        return original(history, tools)

    monkeypatch.setattr(model, "turn", turn)
    lease = store.claim()
    with pytest.raises(ProcessKilled):
        run_episode(store, model, Settings(), lease)
    expire(store, task["task_id"])
    restarted = Store(store._url)
    resumed = ScriptedModel([answer("Continued from saved evidence")])
    assert run_once(restarted, resumed, Settings())
    assert any(item.get("type") == "function_call_output" for item in resumed.histories[0])
    with store.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.episode_events "
                "WHERE task_id=%s AND kind='tool_result'",
                (task["task_id"],),
            ).fetchone()["n"]
            == 1
        )
    assert store.messages("user_alice")[-1]["content"] == "Continued from saved evidence"


def test_saved_model_call_executes_missing_read_before_next_model_turn(store, alice):
    task = store.enqueue("user_alice", "Read rubric", "resume-two")
    lease = store.claim()
    call = function_turn()
    store.event(lease, "model_turn", {"output": call.output, "text": ""})
    expire(store, task["task_id"])
    model = ScriptedModel([answer()])
    run_once(Store(store._url), model, Settings())
    assert model.histories[0][-1]["type"] == "function_call_output"
    assert "Read rubric" in model.histories[0][-1]["output"]


def test_saved_final_result_completes_without_another_model_call(store, alice, monkeypatch):
    task = store.enqueue("user_alice", "Question", "resume-three")
    lease = store.claim()
    original = store.complete

    def killed(*args):
        raise ProcessKilled()

    monkeypatch.setattr(store, "complete", killed)
    with pytest.raises(ProcessKilled):
        run_episode(store, ScriptedModel([answer("Saved final answer")]), Settings(), lease)
    monkeypatch.setattr(store, "complete", original)
    expire(store, task["task_id"])
    assert run_once(Store(store._url), ScriptedModel([]), Settings())
    assert store.messages("user_alice")[-1]["content"] == "Saved final answer"


def test_resume_preserves_encrypted_reasoning_and_isolation(store, alice):
    task = store.enqueue("user_alice", "Own question", "resume-four")
    lease = store.claim()
    output = [{"type": "reasoning", "id": "r_one", "encrypted_content": "opaque", "summary": []}]
    output += function_turn().output
    store.event(lease, "model_turn", {"output": output, "text": ""})
    store.provision("user_bob")
    store.enqueue("user_bob", "Private Bob material", "bob")
    expire(store, task["task_id"])
    with pytest.raises(LeaseLost):
        store.episode_history(lease)
    model = ScriptedModel([answer()])
    run_once(Store(store._url), model, Settings())
    assert output[0] in model.histories[0]
    assert "Private Bob material" not in str(model.histories)


def test_episode_budget_continues_with_saved_progress_on_next_attempt(store, alice):
    task = store.enqueue("user_alice", "Question", "budget-resume")
    run_once(store, ScriptedModel([function_turn()]), Settings(max_episode_turns=1))
    with store.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.tasks SET available_at=now() WHERE id=%s", (task["task_id"],)
        )
    model = ScriptedModel([answer("Next episode")])
    assert run_once(Store(store._url), model, Settings())
    assert model.histories[0][-1]["type"] == "function_call_output"
    assert store.task("user_alice", task["task_id"])["status"] == "done"
