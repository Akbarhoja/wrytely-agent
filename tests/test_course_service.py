"""Offline entrypoint/control tests; real Store restart rules live in supervisor tests."""

import json

import pytest
from test_canvas_sync import device as device
from test_course_supervision import Model, decision, setup

from app.course_service import health, main, tick
from shared.config import Settings
from shared.db import Store as RealStore


class Store:
    def __init__(self):
        self.queued = []

    def due_course_supervisions(self, *, limit):
        assert limit == 2
        return [{"id": "one", "user_id": "stored_owner"}, {"id": "two", "user_id": "other"}]

    def course_supervision_status(self, user, monitor):
        return {"notification_consent": True, "offers": [{"id": "offer", "state": "pending"}]}

    def enqueue_course_offer(self, user, monitor, offer):
        self.queued.append((user, monitor, offer))

    def pending_course_offer_deliveries(self, *, limit):
        return (
            []
            if self.queued
            else [{"user_id": "stored_owner", "supervision_id": "one", "offer_id": "offer"}]
        )


def test_ticks_use_stored_identities_and_do_not_send_by_default(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.course_service.run_course_supervision_once",
        lambda s, m, u, i: calls.append((u, i)) or {"state": "ready"},
    )
    store = Store()
    assert tick(store, object(), limit=2) == {"checked": 2, "queued": 0, "errors": 0}
    assert calls == [("stored_owner", "one"), ("other", "two")]
    assert store.queued == []


def test_failure_is_not_retried_and_error_content_stays_private(monkeypatch, caplog):
    calls = []

    def failed(s, m, user, monitor):
        calls.append(monitor)
        raise RuntimeError("private course and credential")

    monkeypatch.setattr("app.course_service.run_course_supervision_once", failed)
    assert tick(Store(), object(), limit=2)["errors"] == 2
    assert calls == ["one", "two"] and "private course" not in caplog.text


def test_stop_check_fences_second_item_and_queue(monkeypatch):
    stopped = []
    monkeypatch.setattr(
        "app.course_service.run_course_supervision_once",
        lambda *args: stopped.append(True) or {"state": "ready"},
    )
    store = Store()
    result = tick(store, object(), limit=2, queue_offers=True, stopped=lambda: bool(stopped))
    assert result == {"checked": 1, "queued": 0, "errors": 0}
    assert store.queued == []


def test_health_contains_counts_only_and_replaces_atomically(tmp_path):
    target = tmp_path / "health.json"
    health(target, "running", {"checked": 1, "queued": 0, "errors": 0})
    health(target, "stopped", {"checked": 1, "queued": 0, "errors": 0})
    assert json.loads(target.read_text())["state"] == "stopped"
    assert not target.with_name("health.json.tmp").exists()


def test_cli_requires_explicit_mode_and_configured_budget(monkeypatch):
    monkeypatch.setattr("app.course_service.Settings", lambda: Settings(_env_file=None))
    with pytest.raises(SystemExit) as missing_mode:
        main([])
    assert missing_mode.value.code == 2
    with pytest.raises(SystemExit) as missing_budget:
        main(["--once"])
    assert missing_budget.value.code == 2


@pytest.mark.parametrize("unknown", [False, True])
def test_real_store_restart_keeps_due_time_or_unknown_hold(device, unknown):
    db, monitor, _ = setup(device)
    model = Model(decision("wait"))
    if unknown:

        def failed(*args):
            model.calls += 1
            raise RuntimeError("unknown inference")

        model.turn = failed
    result = tick(db, model, limit=1)
    assert result["errors"] == int(unknown)
    assert model.calls == 1
    restarted = RealStore(db._url, canvas_origins=db._canvas_origins)
    assert tick(restarted, model, limit=1) == {"checked": 0, "queued": 0, "errors": 0}
    assert model.calls == 1
    status = db.course_supervision_status("user_alice", monitor["id"])
    assert status["state"] == ("blocked" if unknown else "ready")


def test_saved_offer_recovery_needs_no_model_call_and_never_requeues_unknown(device):
    from test_course_offer_delivery import ACCOUNT, prepared

    from contracts.models import DeliveryResult

    db, monitor, _ = prepared(device)
    with db.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.course_supervisions "
            "SET next_check_at=now()+interval '1 day' WHERE id=%s",
            (monitor["id"],),
        )
    model = Model(decision("wait"))
    assert tick(db, model, limit=1, queue_offers=True) == {"checked": 0, "queued": 1, "errors": 0}
    assert model.calls == 0
    restarted = RealStore(db._url, canvas_origins=db._canvas_origins)
    claim = restarted.claim_whatsapp_delivery("one")
    assert restarted.authorize_whatsapp_send(claim, **ACCOUNT).state == "permitted"
    restarted.record_whatsapp_result(
        claim, DeliveryResult(internal_id=claim.action_id, state="unknown")
    )
    assert tick(restarted, model, limit=1, queue_offers=True) == {
        "checked": 0,
        "queued": 0,
        "errors": 0,
    }
    assert model.calls == 0
