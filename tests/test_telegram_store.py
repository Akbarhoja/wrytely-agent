"""Actual original Store/task journal with separate Telegram provider authority."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from test_canvas_sync import device as device
from test_course_supervision import prepared_course

from contracts.models import DeliveryResult
from contracts.telegram import TelegramText
from shared.canvas_reads import SourceRefreshRequired
from shared.db import RequestConflict, Store

BOT = 123456789
CHAT = 991


def event(text, update_id=1, chat_id=CHAT):
    return TelegramText(
        update_id, update_id, chat_id, text, datetime.now(UTC).replace(microsecond=0)
    )


def link(db, user="user_alice", chat=CHAT):
    db.provision(user)
    challenge = db.create_telegram_challenge(user, BOT)
    assert db.ingest_telegram(BOT, event(challenge["message"], chat_id=chat)) == "linked"
    db.set_telegram_preferences(
        user,
        BOT,
        consent=True,
        notification_consent=True,
        timezone="UTC",
        quiet_start=0,
        quiet_end=0,
    )
    return challenge


def queued_reply(db):
    link(db)
    assert db.ingest_telegram(BOT, event("Help me study fractions", 2)) == "queued"
    lease = db.claim()
    assert lease.user_id == "user_alice"
    db.complete(lease, "Use a small example and explain it in your own words.")
    assert db.queue_telegram_replies(BOT) == 1
    return db.claim_telegram_delivery(BOT)


def test_pairing_is_bot_namespaced_one_use_and_never_a_model_message(store):
    store.provision("user_alice")
    challenge = store.create_telegram_challenge("user_alice", BOT)
    message = event(challenge["message"])
    assert store.ingest_telegram(BOT + 1, message) == "ignored"
    assert store.ingest_telegram(BOT, message) == "linked"
    assert store.ingest_telegram(BOT, message) == "duplicate"
    connection = store.telegram_connection("user_alice", BOT)
    assert connection["linked"] and not connection["preferences"]["consent"]
    assert not connection["preferences"]["notification_consent"]
    assert "chat_id" not in str(connection) and "generation" not in str(connection)
    assert store.messages("user_alice") == [] and store.claim() is None
    with store.connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.telegram_challenges").fetchone()[
                "n"
            ]
            == 0
        )
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.channel_links").fetchone()["n"]
            == 0
        )


def test_rotation_and_bad_link_tokens_are_not_enqueued(store):
    store.provision("user_alice")
    old = store.create_telegram_challenge("user_alice", BOT)
    new = store.create_telegram_challenge("user_alice", BOT)
    assert old["message"] != new["message"]
    assert store.ingest_telegram(BOT, event(old["message"])) == "ignored"
    assert store.ingest_telegram(BOT, event("/start invalid", 2)) == "ignored"
    assert store.messages("user_alice") == []
    assert store.ingest_telegram(BOT, event(new["message"], 3)) == "linked"


def test_inbound_replay_mismatch_and_cross_bot_cannot_duplicate_tasks(store):
    link(store)
    incoming = event("A question", 2)
    assert store.ingest_telegram(BOT, incoming) == "queued"
    assert store.ingest_telegram(BOT, incoming) == "duplicate"
    with pytest.raises(RequestConflict):
        store.ingest_telegram(BOT, replace(incoming, text="Changed private text"))
    assert store.ingest_telegram(BOT + 1, incoming) == "ignored"
    assert store.ingest_telegram(BOT, event("Someone else", 3, chat_id=992)) == "ignored"
    assert len(store.tasks("user_alice")) == 1
    store.provision("user_bob")
    assert not store.telegram_connection("user_bob", BOT)["linked"]
    assert store.messages("user_bob") == []


@pytest.mark.parametrize("control", ["paused", "no_consent"])
def test_disabled_controls_prevent_inbound_model_work(store, control):
    link(store)
    if control == "paused":
        store.set_paused("user_alice", True)
    else:
        store.set_telegram_preferences(
            "user_alice",
            BOT,
            consent=False,
            notification_consent=False,
            timezone="UTC",
            quiet_start=0,
            quiet_end=0,
        )
    assert store.ingest_telegram(BOT, event("Do work", 2)) == "ignored"
    assert store.claim() is None


def test_existing_task_completion_recovery_and_dispatch_are_once_only(store):
    claim = queued_reply(store)
    assert claim.kind == "reply" and store.queue_telegram_replies(BOT) == 0
    with store.connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.whatsapp_outbound").fetchone()[
                "n"
            ]
            == 0
        )
    permit = store.authorize_telegram_dispatch(claim)
    assert permit.state == "permitted" and permit.content == claim.content
    assert store.authorize_telegram_dispatch(claim).state == "cancelled"
    receipt = DeliveryResult(state="accepted", internal_id=claim.action_id, provider_ref="777")
    assert store.finish_telegram_delivery(claim, receipt)
    assert not store.finish_telegram_delivery(claim, receipt)
    restarted = Store(store._url)
    assert restarted.claim_telegram_delivery(BOT) is None
    assert (
        restarted.telegram_connection("user_alice", BOT)["latest_delivery"]["state"] == "accepted"
    )


@pytest.mark.parametrize("control", ["pause", "unlink", "stop", "forged_content"])
def test_controls_recheck_before_any_dispatch(store, control):
    claim = queued_reply(store)
    if control == "pause":
        store.set_paused("user_alice", True)
    elif control == "unlink":
        store.unlink_telegram("user_alice", BOT)
    elif control == "stop":
        assert store.ingest_telegram(BOT, event("/stop", 3)) == "stopped"
    else:
        claim = replace(claim, content="Forged output")
    assert store.authorize_telegram_dispatch(claim).state == "cancelled"


def test_cross_account_forged_claim_does_not_cancel_the_owner_action(store):
    claim = queued_reply(store)
    store.provision("user_bob")
    assert (
        store.authorize_telegram_dispatch(replace(claim, user_id="user_bob")).state == "cancelled"
    )
    assert store.authorize_telegram_dispatch(claim).state == "permitted"


@pytest.mark.parametrize("phase", ["before_dispatch", "after_dispatch"])
def test_expired_claim_recovery_distinguishes_unsent_from_unknown(store, phase):
    claim = queued_reply(store)
    if phase == "after_dispatch":
        assert store.authorize_telegram_dispatch(claim).state == "permitted"
    with store.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.telegram_outbound SET lease_until=now()-interval '1 second'"
        )
    recovered = store.claim_telegram_delivery(BOT)
    assert (recovered is None) == (phase == "after_dispatch")
    if recovered:
        assert recovered.attempt_token != claim.attempt_token
        assert store.authorize_telegram_dispatch(claim).state == "cancelled"
    else:
        assert store.telegram_connection("user_alice", BOT)["latest_delivery"]["state"] == "unknown"


def test_quiet_hours_hold_without_dispatch_and_unknown_send_never_retries(store):
    claim = queued_reply(store)
    hour = datetime.now(UTC).hour
    store.set_telegram_preferences(
        "user_alice",
        BOT,
        consent=True,
        notification_consent=True,
        timezone="UTC",
        quiet_start=hour,
        quiet_end=(hour + 1) % 24,
    )
    assert store.authorize_telegram_dispatch(claim).state == "held"
    with store.connection() as conn:
        row = conn.execute(
            "SELECT dispatch_at,attempts FROM wrytely_agent.telegram_outbound"
        ).fetchone()
        assert row["dispatch_at"] is None and row["attempts"] == 0
        conn.execute("UPDATE wrytely_agent.telegram_outbound SET available_at=now()")
    store.set_telegram_preferences(
        "user_alice",
        BOT,
        consent=True,
        notification_consent=True,
        timezone="UTC",
        quiet_start=0,
        quiet_end=0,
    )
    claim = store.claim_telegram_delivery(BOT)
    assert store.authorize_telegram_dispatch(claim).state == "permitted"
    assert store.finish_telegram_delivery(
        claim, DeliveryResult(state="unknown", internal_id=claim.action_id)
    )
    assert store.claim_telegram_delivery(BOT) is None


def test_preparation_uses_existing_scoped_record_deduplicates_and_source_change_blocks(device):
    db, monitor, _, _ = prepared_course(device)
    link(db)
    record = db.course_supervision_status("user_alice", monitor["id"])["preparations"][0]
    hints = db.pending_telegram_preparations(BOT)
    assert hints == [
        dict(user_id="user_alice", supervision_id=monitor["id"], preparation_id=record["id"])
    ]
    queued = db.queue_telegram_preparation("user_alice", BOT, monitor["id"], record["id"])
    assert db.queue_telegram_preparation("user_alice", BOT, monitor["id"], record["id"]) == queued
    assert db.pending_telegram_preparations(BOT) == []
    claim = db.claim_telegram_delivery(BOT)
    assert "not a completed or checked assignment" in claim.content
    assert (
        record["excerpts"][0]["quote"] in claim.content and "linked_content_unread" in claim.content
    )
    with db.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_evidence_objects SET missing_pending_confirmation=true"
        )
    assert db.authorize_telegram_dispatch(claim).state == "cancelled"
    with pytest.raises(SourceRefreshRequired):
        db.queue_telegram_preparation("user_alice", BOT, monitor["id"], record["id"])


def test_preparation_requires_its_own_telegram_notification_consent(device):
    db, monitor, _, _ = prepared_course(device)
    link(db)
    record = db.course_supervision_status("user_alice", monitor["id"])["preparations"][0]
    db.set_telegram_preferences(
        "user_alice",
        BOT,
        consent=True,
        notification_consent=False,
        timezone="UTC",
        quiet_start=0,
        quiet_end=0,
    )
    with pytest.raises(ValueError, match="notification consent"):
        db.queue_telegram_preparation("user_alice", BOT, monitor["id"], record["id"])
    db.set_telegram_preferences(
        "user_alice",
        BOT,
        consent=True,
        notification_consent=True,
        timezone="UTC",
        quiet_start=0,
        quiet_end=0,
    )
    with pytest.raises(LookupError):
        db.queue_telegram_preparation("user_alice", BOT, uuid4(), record["id"])


def test_known_rate_limit_respects_wait_and_three_dispatch_ceiling(store):
    from datetime import timedelta

    claim = queued_reply(store)
    for attempt in range(3):
        assert store.authorize_telegram_dispatch(claim).state == "permitted"
        retry_at = datetime.now(UTC) + timedelta(hours=1)
        receipt = DeliveryResult(
            state="deferred", internal_id=claim.action_id, retry_at=retry_at.isoformat()
        )
        assert store.finish_telegram_delivery(claim, receipt)
        assert store.claim_telegram_delivery(BOT) is None
        with store.connection() as conn:
            row = conn.execute(
                "SELECT state,available_at,attempts FROM wrytely_agent.telegram_outbound"
            ).fetchone()
            assert row["available_at"] >= retry_at
            assert row["attempts"] == attempt + 1
            assert row["state"] == ("failed" if attempt == 2 else "queued")
            conn.execute("UPDATE wrytely_agent.telegram_outbound SET available_at=now()")
        if attempt < 2:
            claim = store.claim_telegram_delivery(BOT)
    assert store.claim_telegram_delivery(BOT) is None
