"""One-use worker seams against the actual original Store and scripted provider."""

from types import SimpleNamespace

import pytest
from test_telegram_store import BOT, queued_reply

from app.telegram_worker import main, run_once
from contracts.models import DeliveryResult


class Adapter:
    bot_id = BOT
    calls = 0
    fail = False

    def send(self, *, recipient, text, action_id):
        self.calls += 1
        assert recipient == "991" and text
        if self.fail:
            raise TimeoutError("PRIVATE credential-bearing exception")
        return DeliveryResult(state="accepted", internal_id=action_id, provider_ref="42")


@pytest.mark.parametrize("fail,state", [(False, "accepted"), (True, "unknown")])
def test_worker_restart_never_resends_actual_authorized_intent(store, fail, state):
    claim = queued_reply(store)

    # Return the untouched claimed lease to the normal selector for this assembly test.
    class Recovery:
        def __getattr__(self, key):
            return getattr(store, key)

        def claim_telegram_delivery(self, bot):
            return claim

    adapter = Adapter()
    adapter.fail = fail
    assert run_once(Recovery(), adapter, BOT) == state
    assert run_once(Recovery(), adapter, BOT) == "cancelled"
    assert adapter.calls == 1


def test_wrong_bot_stops_before_any_store_call():
    with pytest.raises(ValueError, match="bot mismatch"):
        run_once(object(), SimpleNamespace(bot_id=BOT + 1), BOT)


def test_cli_requires_explicit_mode_before_configuration():
    with pytest.raises(SystemExit):
        main([])


@pytest.mark.parametrize("provider_state", ["accepted", "deferred", "failed"])
def test_expired_receipt_fence_reports_unknown_and_restart_never_resends(store, provider_state):
    claim = queued_reply(store)

    class Recovery:
        def __getattr__(self, key):
            return getattr(store, key)

        def claim_telegram_delivery(self, bot):
            return claim

    class ExpiringAdapter(Adapter):
        def send(self, *, recipient, text, action_id):
            self.calls += 1
            with store.connection() as conn:
                conn.execute(
                    "UPDATE wrytely_agent.telegram_outbound SET lease_until="
                    "clock_timestamp()-interval '1 second' WHERE id=%s",
                    (action_id,),
                )
            # Another worker reconciles an expired in-flight attempt to unknown,
            # invalidating the original fence before its provider receipt returns.
            assert store.claim_telegram_delivery(BOT) is None
            return DeliveryResult(
                state=provider_state,
                internal_id=action_id,
                provider_ref="42" if provider_state == "accepted" else None,
            )

    adapter = ExpiringAdapter()
    assert run_once(Recovery(), adapter, BOT) == "unknown"
    assert run_once(store, adapter, BOT) == "idle"
    assert adapter.calls == 1
    with store.connection() as conn:
        row = conn.execute(
            "SELECT state,provider_ref FROM wrytely_agent.telegram_outbound WHERE id=%s",
            (claim.action_id,),
        ).fetchone()
    assert row == {"state": "unknown", "provider_ref": None}
