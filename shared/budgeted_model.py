"""Reserve configured worst-case cost BEFORE inference; never retry unknown calls."""

import json
from decimal import Decimal

from shared.model_budgets import ModelBudgetExceeded, usd


class BudgetedModelClient:
    def __init__(
        self,
        store,
        model,
        verified_user,
        budget_key,
        *,
        input_usd_per_million,
        output_usd_per_million,
    ):
        self.store, self.model, self.user, self.key = store, model, verified_user, budget_key
        self.input_rate, self.output_rate = map(
            usd, (input_usd_per_million, output_usd_per_million)
        )
        if not self.input_rate or not self.output_rate:
            raise ValueError("Configure verified nonzero model prices")

    def turn(self, history, tools):
        size = len(json.dumps([history, tools], ensure_ascii=False).encode())
        if size > 250000:
            raise ValueError("Model input byte limit")
        # UTF8 bytes conservatively bound text tokens; add framing/tool overhead.
        maximum = usd(
            (self.input_rate * (size + 4096) + self.output_rate * 2048) / Decimal(1000000)
        )
        reservation = self.store.reserve_model_call(self.user, self.key, maximum)
        try:
            result = self.model.turn(history, tools)
        except Exception:
            self.store.settle_model_call(self.user, reservation)
            raise
        if not result.usage_known:
            self.store.settle_model_call(self.user, reservation)
            raise ModelBudgetExceeded("Model usage unknown; reservation held")
        actual = usd(
            (self.input_rate * result.input_tokens + self.output_rate * result.output_tokens)
            / Decimal(1000000)
        )
        state = self.store.settle_model_call(
            self.user,
            reservation,
            actual_usd=actual,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )
        if state == "overrun":
            raise ModelBudgetExceeded("Model price bound exceeded; budget disabled")
        return result


class BudgetedMetaRouter:
    """Service factory: app never chooses an unguarded paid model from student input."""

    def __init__(self, store, settings):
        from shared.model_client import MetaModelClient

        if not (
            settings.meta_budget_key
            and settings.meta_input_usd_per_million
            and settings.meta_output_usd_per_million
        ):
            raise ValueError("Configure model budget key and verified prices before activation")
        self.store, self.settings, self.model = store, settings, MetaModelClient(settings)

    def for_user(self, verified_user):
        return BudgetedModelClient(
            self.store,
            self.model,
            verified_user,
            self.settings.meta_budget_key,
            input_usd_per_million=str(self.settings.meta_input_usd_per_million),
            output_usd_per_million=str(self.settings.meta_output_usd_per_million),
        )
