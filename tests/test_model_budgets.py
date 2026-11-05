"""Real serialized global/student allowances; no provider calls or real charges."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest

from contracts.models import ModelTurn
from shared.budgeted_model import BudgetedModelClient
from shared.model_budgets import ModelBudgetExceeded


def configured(store, alice):
    store.configure_model_budget("pilot", ceiling_usd="2", opening_liability_usd="1.32")
    store.grant_model_budget("pilot", "user_alice", ceiling_usd="0.50")


def test_opening_unknown_liabilities_and_student_limit_are_preserved(store, alice):
    configured(store, alice)
    one = store.reserve_model_call("user_alice", "pilot", "0.30")
    store.settle_model_call("user_alice", one)
    store.configure_model_budget("pilot", ceiling_usd="2", opening_liability_usd="1.32")
    store.grant_model_budget("pilot", "user_alice", ceiling_usd="0.50")
    with pytest.raises(ModelBudgetExceeded):
        store.reserve_model_call("user_alice", "pilot", "0.21")
    with pytest.raises(ValueError, match="cannot be reset"):
        store.configure_model_budget("pilot", ceiling_usd="2", opening_liability_usd="0")
    store.reserve_model_call("user_alice", "pilot", "0.20")


def test_parallel_students_cannot_overreserve_global_allowance(store, alice):
    configured(store, alice)
    store.provision("user_bob")
    store.grant_model_budget("pilot", "user_bob", ceiling_usd="0.50")

    def reserve(user):
        try:
            return store.reserve_model_call(user, "pilot", "0.40")
        except ModelBudgetExceeded:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(reserve, ["user_alice", "user_bob"]))
    assert sum(i is not None for i in ids) == 1


def test_known_usage_releases_only_unused_part_and_cross_account_is_denied(store, alice):
    configured(store, alice)
    one = store.reserve_model_call("user_alice", "pilot", "0.40")
    store.provision("user_bob")
    with pytest.raises(LookupError):
        store.settle_model_call("user_bob", one, actual_usd="0", input_tokens=0, output_tokens=0)
    assert (
        store.settle_model_call(
            "user_alice", one, actual_usd="0.10", input_tokens=10, output_tokens=10
        )
        == "settled"
    )
    store.reserve_model_call("user_alice", "pilot", "0.40")
    with pytest.raises(ValueError):
        store.settle_model_call("user_alice", one, actual_usd="0", input_tokens=0, output_tokens=0)


def test_overrun_disables_global_budget_and_no_default_grant_exists(store, alice):
    with pytest.raises(ModelBudgetExceeded):
        store.reserve_model_call("user_alice", "missing", "0.01")
    configured(store, alice)
    one = store.reserve_model_call("user_alice", "pilot", "0.01")
    assert (
        store.settle_model_call(
            "user_alice", one, actual_usd="0.02", input_tokens=20, output_tokens=20
        )
        == "overrun"
    )
    store.configure_model_budget("pilot", ceiling_usd="2", opening_liability_usd="1.32")
    with pytest.raises(ModelBudgetExceeded):
        store.reserve_model_call("user_alice", "pilot", "0.01")


class Provider:
    def __init__(self, *, unknown=False, fail=False):
        self.calls, self.unknown, self.fail = 0, unknown, fail

    def turn(self, history, tools):
        self.calls += 1
        if self.fail:
            raise RuntimeError("Sensitive provider detail")
        return ModelTurn(
            output=[],
            text="answer",
            input_tokens=10,
            output_tokens=10,
            usage_known=not self.unknown,
        )


def wrapper(store, provider):
    return BudgetedModelClient(
        store,
        provider,
        "user_alice",
        "pilot",
        input_usd_per_million="1",
        output_usd_per_million="2",
    )


def test_wrapper_reserves_before_provider_and_records_known_usage(store, alice):
    configured(store, alice)
    provider = Provider()
    assert (
        wrapper(store, provider).turn([{"role": "user", "content": "Hello"}], []).text == "answer"
    )
    with store.connection() as conn:
        row = conn.execute("SELECT * FROM wrytely_agent.model_call_reservations").fetchone()
    assert row["state"] == "settled" and row["liability_usd"] == Decimal("0.00003")
    store.set_paused("user_alice", True)
    with pytest.raises(ModelBudgetExceeded):
        wrapper(store, provider).turn([], [])
    assert provider.calls == 1


@pytest.mark.parametrize("mode", ["failure", "unknown"])
def test_failed_or_missing_usage_holds_entire_reservation(store, alice, mode):
    configured(store, alice)
    provider = Provider(fail=mode == "failure", unknown=mode == "unknown")
    with pytest.raises((RuntimeError, ModelBudgetExceeded)):
        wrapper(store, provider).turn([], [])
    with store.connection() as conn:
        row = conn.execute("SELECT * FROM wrytely_agent.model_call_reservations").fetchone()
    assert row["state"] == "unknown" and row["liability_usd"] == row["maximum_usd"]
    assert provider.calls == 1


def test_budget_unknown_blocks_worker_instead_of_an_automatic_retry(store, alice):
    from runtime.worker import run_once
    from shared.config import Settings

    configured(store, alice)
    store.enqueue("user_alice", "Explain fractions", "budgeted-question")
    provider = Provider(fail=True)
    assert run_once(store, wrapper(store, provider), Settings())
    assert not run_once(store, wrapper(store, provider), Settings())
    with store.connection() as conn:
        row = conn.execute("SELECT status,last_error FROM wrytely_agent.tasks").fetchone()
    assert row == {"status": "blocked", "last_error": "model_budget_or_unknown"}
    assert provider.calls == 1


def test_budgeted_provider_503_is_persisted_safely_and_does_not_retry(store, alice):
    from runtime.worker import run_once
    from shared.config import Settings
    from shared.model_client import ModelCallFailed

    configured(store, alice)
    task = store.enqueue("user_alice", "Synthetic question", "provider-503-evidence")

    class FailedProvider:
        calls = 0

        def turn(self, history, tools):
            self.calls += 1
            raise ModelCallFailed(
                status="http_error", http_status=503, code="invalid_request_error"
            )

    provider = FailedProvider()
    assert run_once(store, wrapper(store, provider), Settings())
    assert not run_once(store, wrapper(store, provider), Settings())
    assert provider.calls == 1
    with store.connection() as conn:
        rows = conn.execute(
            "SELECT kind,data FROM wrytely_agent.episode_events "
            "WHERE task_id=%s AND kind='model_failure'",
            (task["task_id"],),
        ).fetchall()
        reservation = conn.execute(
            "SELECT state,liability_usd,maximum_usd FROM wrytely_agent.model_call_reservations"
        ).fetchone()
    assert len(rows) == 1 and rows[0]["data"]["http_status"] == 503
    assert rows[0]["data"]["code"] == "invalid_request_error"
    assert rows[0]["data"]["input_tokens"] is None
    assert (
        reservation["state"] == "unknown"
        and reservation["liability_usd"] == reservation["maximum_usd"]
    )
    assert store.task("user_alice", task["task_id"])["status"] == "blocked"


def test_operator_stop_survives_setup_replay_and_keeps_unknown_liabilities(store, alice):
    configured(store, alice)
    reservation = store.reserve_model_call("user_alice", "pilot", "0.10")
    store.settle_model_call("user_alice", reservation)
    assert store.disable_model_budget("pilot")["enabled"] is False
    configured(store, alice)
    with pytest.raises(ModelBudgetExceeded):
        store.reserve_model_call("user_alice", "pilot", "0.01")
    with store.connection() as conn:
        row = conn.execute(
            "SELECT state,liability_usd FROM wrytely_agent.model_call_reservations"
        ).fetchone()
    assert row == {"state": "unknown", "liability_usd": Decimal("0.10")}
