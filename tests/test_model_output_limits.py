"""Transport/allowance alignment without database or provider access."""

import json
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from contracts.models import ModelTurn
from shared.budgeted_model import BudgetedModelClient
from shared.config import Settings
from shared.model_budgets import ModelBudgetExceeded, usd


class Budget:
    def __init__(self, allowance):
        self.allowance = Decimal(allowance)
        self.maximum = None
        self.settlements = []

    def reserve_model_call(self, user, key, maximum):
        assert user == "verified-owner" and key == "approved"
        self.maximum = maximum
        if maximum > self.allowance:
            raise ModelBudgetExceeded("Limit")
        return "reservation"

    def settle_model_call(self, user, reservation, **usage):
        assert user == "verified-owner" and reservation == "reservation"
        self.settlements.append(usage)
        return "settled" if usage else "unknown"


@pytest.mark.parametrize("limit", [2048, 8192, 16384])
def test_output_reservation_matches_configured_transport_cap(limit):
    budget = Budget("1")
    calls = []
    model = SimpleNamespace(
        max_output_tokens=limit,
        turn=lambda h, t: (
            calls.append((h, t))
            or ModelTurn(output=[], text="", input_tokens=2, output_tokens=2, usage_known=True)
        ),
    )
    history, tools = [{"role": "user", "content": "Read course metadata"}], []
    wrapped = BudgetedModelClient(
        budget,
        model,
        "verified-owner",
        "approved",
        input_usd_per_million="1.25",
        output_usd_per_million="4.25",
    )
    wrapped.turn(history, tools)
    size = len(json.dumps([history, tools], ensure_ascii=False).encode())
    assert budget.maximum == usd(
        (Decimal("1.25") * (size + 4096) + Decimal("4.25") * limit) / Decimal("1000000")
    )
    assert len(calls) == 1 and len(budget.settlements) == 1


def test_larger_output_cap_cannot_use_the_old_smaller_reservation():
    budget = Budget("0.02")
    calls = []
    model = SimpleNamespace(max_output_tokens=8192, turn=lambda h, t: calls.append(1))
    wrapped = BudgetedModelClient(
        budget,
        model,
        "verified-owner",
        "approved",
        input_usd_per_million="1.25",
        output_usd_per_million="4.25",
    )
    with pytest.raises(ModelBudgetExceeded):
        wrapped.turn([], [])
    assert calls == [] and budget.settlements == []


@pytest.mark.parametrize("value", [0, 255, 16385, True, "8192"])
def test_bad_transport_limit_is_rejected_before_reservation(value):
    budget = Budget("1")
    model = SimpleNamespace(max_output_tokens=value)
    wrapped = BudgetedModelClient(
        budget,
        model,
        "verified-owner",
        "approved",
        input_usd_per_million="1.25",
        output_usd_per_million="4.25",
    )
    with pytest.raises(ValueError, match="output limit"):
        wrapped.turn([], [])
    assert budget.maximum is None


@pytest.mark.parametrize(
    "settings",
    [
        {"meta_reasoning_effort": "none"},
        {"meta_reasoning_effort": "unknown"},
        {"meta_max_output_tokens": 0},
        {"meta_max_output_tokens": 16385},
    ],
)
def test_unusable_reasoning_or_unbounded_output_configuration_is_rejected(settings):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **settings)
