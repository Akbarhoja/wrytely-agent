"""Real Store and immutable bytes, scripted transport only; no live sends."""

from dataclasses import replace

import pytest
from test_canvas_sync import device as device
from test_private_artifact_reads import ready
from test_telegram_command_store import offered
from test_telegram_store import BOT, event, link

from contracts.models import DeliveryResult
from shared.db import LeaseLost, Store


def test_offer_is_recovered_once_and_acceptance_queues_original_work(device):
    db, monitor, offer = offered(device)
    db.set_course_notification_consent("user_alice", monitor["id"], consent=True)
    assert db.queue_telegram_academic_actions(BOT) == 1
    assert db.queue_telegram_academic_actions(BOT) == 0
    claim = db.claim_telegram_delivery(BOT)
    assert claim.kind == "offer"
    assert f"/accept {offer['id']}" in claim.content
    permit = db.authorize_telegram_dispatch(claim)
    assert permit.state == "permitted" and permit.payload is None
    assert db.finish_telegram_delivery(
        claim, DeliveryResult(state="accepted", internal_id=claim.action_id, provider_ref="77")
    )
    assert db.ingest_telegram(BOT, event(f"/accept {offer['id']}", 2)) == "command_applied"
    assert db.queue_telegram_academic_actions(BOT) == 1
    ack = db.claim_telegram_delivery(BOT)
    assert ack.kind == "command" and "queued" in ack.content
    assert db.authorize_telegram_dispatch(ack).state == "permitted"
    assert db.queue_telegram_academic_actions(BOT) == 0


@pytest.mark.parametrize("control", ["pause", "revoke", "consent", "decline"])
def test_proactive_offer_checks_current_scope_and_controls(device, control):
    db, monitor, offer = offered(device)
    db.set_course_notification_consent("user_alice", monitor["id"], consent=True)
    db.queue_telegram_offer("user_alice", BOT, monitor["id"], offer["id"])
    claim = db.claim_telegram_delivery(BOT)
    if control == "pause":
        db.pause_course_supervision("user_alice", monitor["id"])
    elif control == "revoke":
        db.rotate_or_revoke("user_alice", device[1]["connection_id"])
    elif control == "consent":
        db.set_course_notification_consent("user_alice", monitor["id"], consent=False)
    else:
        db.decide_course_offer("user_alice", monitor["id"], offer["id"], accept=False)
    assert db.authorize_telegram_dispatch(claim).state == "cancelled"


def file_claim(device):
    _, artifact = ready(device)
    db = device[0]
    link(db)
    incoming = event(f"/file {artifact['id']}", 2)
    assert db.ingest_telegram(BOT, incoming) == "command_applied"
    return db, artifact, db.claim_telegram_delivery(BOT)


def test_checked_file_requires_document_worker_and_one_use_authority(device):
    db, artifact, claim = file_claim(device)
    assert claim.kind == "artifact" and claim.artifact_file_id
    with pytest.raises(LeaseLost):
        db.read_telegram_artifact_delivery(claim)
    assert db.authorize_telegram_dispatch(claim).state == "held"
    with db.connection() as conn:
        conn.execute("UPDATE wrytely_agent.telegram_outbound SET available_at=now()")
    claim = db.claim_telegram_delivery(BOT)
    permit = db.authorize_telegram_dispatch(claim, supports_documents=True)
    assert permit.state == "permitted"
    assert permit.payload.artifact_id == str(artifact["id"])
    file = db.read_telegram_artifact_delivery(claim)
    assert file.descriptor == permit.payload and file.content.startswith(b"PK")
    assert db.authorize_telegram_dispatch(claim, supports_documents=True).state == "cancelled"
    assert db.finish_telegram_delivery(
        claim, DeliveryResult(state="unknown", internal_id=claim.action_id)
    )
    restarted = Store(db._url, canvas_origins=tuple(db._canvas_origins))
    assert restarted.claim_telegram_delivery(BOT) is None
    prior = db.enqueue_telegram_artifact_delivery("user_alice", BOT, artifact["id"])
    assert prior["state"] == "unknown" and prior["id"] == claim.action_id
    with pytest.raises(LeaseLost):
        db.read_telegram_artifact_delivery(claim)
    with db.connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.whatsapp_outbound").fetchone()[
                "n"
            ]
            == 0
        )


@pytest.mark.parametrize("control", ["pause", "unlink", "forged_file", "revoke", "tamper"])
def test_file_authority_cannot_survive_changed_controls_or_bytes(device, control):
    db, _, claim = file_claim(device)
    if control == "pause":
        db.set_paused("user_alice", True)
    elif control == "unlink":
        db.unlink_telegram("user_alice", BOT)
    elif control == "forged_file":
        from uuid import uuid4

        claim = replace(claim, artifact_file_id=uuid4())
    elif control == "revoke":
        db.rotate_or_revoke("user_alice", device[1]["connection_id"])
    else:
        with db.connection() as conn:
            conn.execute("UPDATE wrytely_agent.artifact_delivery_files SET sha256=%s", ("0" * 64,))
    assert db.authorize_telegram_dispatch(claim, supports_documents=True).state == "cancelled"


def test_file_read_rechecks_control_after_dispatch_permission(device):
    db, _, claim = file_claim(device)
    assert db.authorize_telegram_dispatch(claim, supports_documents=True).state == "permitted"
    db.set_paused("user_alice", True)
    with pytest.raises((ValueError, LeaseLost)):
        db.read_telegram_artifact_delivery(claim)


def test_command_receipt_is_literal_and_old_generation_cannot_send(device):
    db, _, offer = offered(device)
    assert db.ingest_telegram(BOT, event(f"/decline {offer['id']}", 2)) == "command_applied"
    db.queue_telegram_academic_actions(BOT)
    claim = db.claim_telegram_delivery(BOT)
    assert claim.kind == "command"
    assert "declined" in claim.content and str(offer["id"]) not in claim.content
    db.unlink_telegram("user_alice", BOT)
    assert db.authorize_telegram_dispatch(claim).state == "cancelled"


def test_file_request_is_private_and_a_new_link_cannot_repeat_unknown_send(device):
    db, artifact, claim = file_claim(device)
    db.provision("user_bob")
    with pytest.raises((ValueError, LookupError)):
        db.enqueue_telegram_artifact_delivery("user_bob", BOT, artifact["id"])
    assert db.authorize_telegram_dispatch(claim, supports_documents=True).state == "permitted"
    assert db.finish_telegram_delivery(
        claim, DeliveryResult(state="unknown", internal_id=claim.action_id)
    )
    db.unlink_telegram("user_alice", BOT)
    challenge = db.create_telegram_challenge("user_alice", BOT)
    assert db.ingest_telegram(BOT, event(challenge["message"], 5)) == "linked"
    db.set_telegram_preferences(
        "user_alice",
        BOT,
        consent=True,
        notification_consent=True,
        timezone="UTC",
        quiet_start=0,
        quiet_end=0,
    )
    assert (
        db.enqueue_telegram_artifact_delivery("user_alice", BOT, artifact["id"])["state"]
        == "unknown"
    )
    assert db.claim_telegram_delivery(BOT) is None


def test_offer_and_preparation_share_the_daily_dispatch_cap(device):
    db, monitor, offer = offered(device)
    db.set_course_notification_consent("user_alice", monitor["id"], consent=True)
    db.queue_telegram_offer("user_alice", BOT, monitor["id"], offer["id"])
    claim = db.claim_telegram_delivery(BOT)
    with db.connection() as conn:
        for number in range(3):
            conn.execute(
                "INSERT INTO wrytely_agent.telegram_outbound "
                "(id,agent_id,bot_id,chat_id,generation,intent_key,kind,content,"
                "supervision_id,offer_id,state,dispatch_at) SELECT gen_random_uuid(),agent_id,"
                "bot_id,chat_id,generation,%s,kind,content,supervision_id,offer_id,'unknown',"
                "clock_timestamp() FROM wrytely_agent.telegram_outbound WHERE id=%s",
                (f"prior-notification:{number}", claim.action_id),
            )
    permit = db.authorize_telegram_dispatch(claim)
    assert permit.state == "cancelled" and permit.reason == "notification_limit"
