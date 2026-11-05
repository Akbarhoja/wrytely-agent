"""Original Store/replay/academic machinery, with no model or provider IO."""

from dataclasses import replace
from datetime import timedelta

import pytest
from test_canvas_sync import device as device
from test_course_supervision import Model, decision, setup
from test_private_artifact_reads import ready
from test_telegram_store import BOT, CHAT, event, link

from runtime.supervisor import run_course_supervision_once
from shared.db import QueueFull, RequestConflict, Store


def offered(device):
    db, monitor, obj = setup(device)
    run_course_supervision_once(db, Model(decision("inspect", obj)), "user_alice", monitor["id"])
    run_course_supervision_once(
        db, Model(decision("offer", obj, "Prepare a study draft?")), "user_alice", monitor["id"]
    )
    offer = db.course_supervision_status("user_alice", monitor["id"])["offers"][0]
    link(db)
    return db, monitor, offer


def receipt(db):
    return db.telegram_connection("user_alice", BOT)["latest_command"]["command_result"]


def count(db, table):
    assert table in {"tasks", "responsibilities", "telegram_inbound", "drafting_requests"}
    with db.connection() as conn:
        return conn.execute(f"SELECT count(*) AS n FROM wrytely_agent.{table}").fetchone()["n"]


def test_acceptance_uses_original_draft_engine_once_across_replay_restart(device):
    db, monitor, offer = offered(device)
    message = event(f"/accept {offer['id']}", 2)
    assert db.ingest_telegram(BOT, message) == "command_applied"
    assert receipt(db)["result"]["state"] == "accepted"
    before = count(db, "tasks"), count(db, "responsibilities")
    restarted = Store(db._url, canvas_origins=tuple(db._canvas_origins))
    assert restarted.ingest_telegram(BOT, message) == "duplicate"
    assert restarted.ingest_telegram(BOT, event(message.text, 3)) == "command_applied"
    assert before == (count(db, "tasks"), count(db, "responsibilities"))
    assert (
        db.course_supervision_status("user_alice", monitor["id"])["offers"][0]["state"]
        == "accepted"
    )
    assert count(db, "responsibilities") == 1
    with db.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.tasks WHERE kind='reply'"
            ).fetchone()["n"]
            == 0
        )


def test_decline_creates_no_work(device):
    db, monitor, offer = offered(device)
    before = count(db, "tasks")
    assert db.ingest_telegram(BOT, event(f"/decline {offer['id']}", 2)) == "command_applied"
    assert receipt(db)["result"] == {"state": "declined"}
    assert count(db, "tasks") == before
    assert (
        db.course_supervision_status("user_alice", monitor["id"])["offers"][0]["state"]
        == "declined"
    )


@pytest.mark.parametrize("control", ["paused", "no_consent", "foreign_chat", "old_link"])
def test_authority_controls_block_commands_without_model_tasks(device, control):
    db, monitor, offer = offered(device)
    message = event(f"/accept {offer['id']}", 2)
    if control == "paused":
        db.set_paused("user_alice", True)
    elif control == "no_consent":
        db.set_telegram_preferences(
            "user_alice",
            BOT,
            consent=False,
            notification_consent=False,
            timezone="UTC",
            quiet_start=0,
            quiet_end=0,
        )
    elif control == "foreign_chat":
        message = replace(message, chat_id=CHAT + 1)
    else:
        message = replace(message, event_at=message.event_at - timedelta(seconds=5))
    before = count(db, "tasks")
    assert db.ingest_telegram(BOT, message) == "ignored"
    assert count(db, "tasks") == before
    assert (
        db.course_supervision_status("user_alice", monitor["id"])["offers"][0]["state"] == "pending"
    )


def test_cross_account_targets_and_malformed_commands_are_not_model_input(device):
    db, _, offer = offered(device)
    link(db, "user_bob", CHAT + 1, update_id=10)
    assert (
        db.ingest_telegram(BOT, event(f"/accept {offer['id']}", 11, CHAT + 1)) == "command_rejected"
    )
    assert db.ingest_telegram(BOT, event("/accept latest", 3)) == "command_rejected"
    assert receipt(db) == {"state": "rejected", "reason": "invalid_command"}
    assert db.ingest_telegram(BOT, event(" /help", 4)) == "ignored"
    assert count(db, "tasks") == 0
    assert db.messages("user_bob") == []


def test_expected_failure_rolls_back_partial_acceptance_but_keeps_rejection(device, monkeypatch):
    db, monitor, offer = offered(device)
    original = db.create_canvas_draft_responsibility

    def reject(*args, **kwargs):
        original(*args, **kwargs)
        raise QueueFull("synthetic capacity limit")

    monkeypatch.setattr(db, "create_canvas_draft_responsibility", reject)
    message = event(f"/accept {offer['id']}", 2)
    assert db.ingest_telegram(BOT, message) == "command_rejected"
    assert receipt(db) == {"state": "rejected", "reason": "command_unavailable"}
    assert (
        db.course_supervision_status("user_alice", monitor["id"])["offers"][0]["state"] == "pending"
    )
    assert count(db, "tasks") == 0 and count(db, "responsibilities") == 0
    assert db.ingest_telegram(BOT, message) == "duplicate"


def test_unexpected_failure_rolls_back_work_and_receipt_for_exact_provider_replay(
    device, monkeypatch
):
    db, monitor, offer = offered(device)
    original = db.create_canvas_draft_responsibility

    def crash(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("synthetic persistence crash")

    monkeypatch.setattr(db, "create_canvas_draft_responsibility", crash)
    message = event(f"/accept {offer['id']}", 2)
    before = count(db, "telegram_inbound")
    with pytest.raises(RuntimeError):
        db.ingest_telegram(BOT, message)
    assert count(db, "telegram_inbound") == before
    assert count(db, "tasks") == 0 and count(db, "responsibilities") == 0
    assert (
        db.course_supervision_status("user_alice", monitor["id"])["offers"][0]["state"] == "pending"
    )
    monkeypatch.setattr(db, "create_canvas_draft_responsibility", original)
    assert db.ingest_telegram(BOT, message) == "command_applied"
    with pytest.raises(RequestConflict):
        db.ingest_telegram(BOT, replace(message, text=f"/decline {offer['id']}"))


def test_revision_uses_existing_private_artifact_and_is_replay_safe(device):
    _, artifact = ready(device)
    db = device[0]
    link(db)
    incoming = event(f"/revise {artifact['id']} Use a clearer title", 2)
    assert db.ingest_telegram(BOT, incoming) == "command_applied"
    result = receipt(db)
    assert result["kind"] == "revise_artifact"
    assert result["result"]["parent_artifact_id"] == str(artifact["id"])
    before = count(db, "tasks"), count(db, "drafting_requests")
    assert db.ingest_telegram(BOT, incoming) == "duplicate"
    assert before == (count(db, "tasks"), count(db, "drafting_requests"))
    link(db, "user_bob", CHAT + 1, update_id=10)
    assert db.ingest_telegram(BOT, event(incoming.text, 11, CHAT + 1)) == "command_rejected"


def test_receipt_history_is_scoped_to_current_link_generation(device):
    db, _, offer = offered(device)
    assert db.ingest_telegram(BOT, event(f"/decline {offer['id']}", 2)) == "command_applied"
    assert receipt(db)["state"] == "applied"
    db.unlink_telegram("user_alice", BOT)
    assert db.telegram_connection("user_alice", BOT)["latest_command"] is None
    challenge = db.create_telegram_challenge("user_alice", BOT)
    assert db.ingest_telegram(BOT, event(challenge["message"], 5)) == "linked"
    assert db.telegram_connection("user_alice", BOT)["latest_command"] is None


def test_revoked_canvas_scope_rejects_acceptance_without_creating_work(device):
    db, _, offer = offered(device)
    db.rotate_or_revoke("user_alice", device[1]["connection_id"])
    assert db.ingest_telegram(BOT, event(f"/accept {offer['id']}", 2)) == "command_rejected"
    assert receipt(db) == {"state": "rejected", "reason": "source_refresh_required"}
    assert count(db, "responsibilities") == 0 and count(db, "tasks") == 0
