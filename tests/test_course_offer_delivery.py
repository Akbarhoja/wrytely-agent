"""Original outbox, separate proactive consent, source/recipient/one-use fencing."""

from datetime import UTC, datetime

import pytest
from test_canvas_sync import device as device
from test_course_supervision import Model, decision, due, setup
from test_delivery_store import ACCOUNT, PHONE, state, status

from contracts.models import DeliveryResult
from contracts.templates import ApprovedOfferTemplate, ApprovedTemplate
from integrations.whatsapp import WhatsAppText
from runtime.supervisor import run_course_supervision_once
from shared.db import LeaseLost, Store


def prepared(device, *, consent=True, limit=6):
    db, monitor, obj = setup(device, limit=limit)
    run_course_supervision_once(db, Model(decision("inspect", obj)), "user_alice", monitor["id"])
    run_course_supervision_once(
        db, Model(decision("offer", obj, "Prepare a study draft?")), "user_alice", monitor["id"]
    )
    offer = db.course_supervision_status("user_alice", monitor["id"])["offers"][0]
    token = db.create_whatsapp_challenge("user_alice")["message"]
    db.ingest_whatsapp(WhatsAppText("link-one", PHONE, token))
    db.ingest_whatsapp(WhatsAppText("message-one", PHONE, "Hello"))
    db.record_whatsapp_inbound_time("message-one", PHONE, datetime.now(UTC))
    db.set_communication_preferences(
        "user_alice", consent=True, timezone="UTC", quiet_start=0, quiet_end=0
    )
    if consent:
        db.set_course_notification_consent("user_alice", monitor["id"], consent=True)
    return db, monitor, offer


def queue(db, monitor, offer):
    return db.enqueue_course_offer("user_alice", monitor["id"], offer["id"])


def template(offer=True):
    cls = ApprovedOfferTemplate if offer else ApprovedTemplate
    return cls(
        key="test_offer",
        name="test_offer",
        language="en_US",
        **ACCOUNT,
        provider_approved=True,
        body_parameters=[dict(source="offer_text" if offer else "reply_text", max_length=1024)],
    )


def test_recovery_after_saved_offer_does_not_need_due_model_or_refill_allowance(device):
    db, monitor, offer = prepared(device)
    with db.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.course_supervisions SET next_check_at=now()+interval '1 day',"
            "state='blocked',reason='inference_outcome_unknown',calls_reserved=call_limit "
            "WHERE id=%s",
            (monitor["id"],),
        )
    restarted = Store(db._url, canvas_origins=db._canvas_origins)
    expected = [dict(user_id="user_alice", supervision_id=monitor["id"], offer_id=offer["id"])]
    assert restarted.pending_course_offer_deliveries(limit=1) == expected
    assert restarted.pending_course_offer_deliveries(limit=1) == expected
    assert restarted.due_course_supervisions(limit=1) == []
    result = restarted.enqueue_course_offer(
        **{
            "verified_user": expected[0]["user_id"],
            "supervision_id": expected[0]["supervision_id"],
            "offer_id": expected[0]["offer_id"],
        }
    )
    assert result["state"] == "queued"
    assert restarted.pending_course_offer_deliveries() == []
    status = restarted.course_supervision_status("user_alice", monitor["id"])
    assert status["calls_reserved"] == status["call_limit"]
    assert status["state"] == "blocked" and status["reason"] == "inference_outcome_unknown"


@pytest.mark.parametrize(
    "control", ["consent", "pause", "agent_pause", "declined", "unlink", "expired", "scope"]
)
def test_recovery_discovery_excludes_ineligible_offers(device, control):
    db, monitor, offer = prepared(device)
    assert len(db.pending_course_offer_deliveries()) == 1
    if control == "consent":
        db.set_course_notification_consent("user_alice", monitor["id"], consent=False)
    elif control == "pause":
        db.pause_course_supervision("user_alice", monitor["id"])
    elif control == "agent_pause":
        db.set_paused("user_alice", True)
    elif control == "declined":
        db.decide_course_offer("user_alice", monitor["id"], offer["id"], accept=False)
    elif control == "unlink":
        db.unlink_whatsapp("user_alice")
    elif control == "expired":
        with db.connection() as conn:
            conn.execute("UPDATE wrytely_agent.course_offers SET created_at=now()-interval '25h'")
    else:
        db.rotate_or_revoke("user_alice", device[1]["connection_id"])
    assert db.pending_course_offer_deliveries() == []


def test_recovery_hint_does_not_bypass_consent_change_before_enqueue(device):
    db, monitor, _ = prepared(device)
    candidate = db.pending_course_offer_deliveries()[0]
    db.set_course_notification_consent("user_alice", monitor["id"], consent=False)
    with pytest.raises(ValueError, match="proactive_consent_missing"):
        db.enqueue_course_offer(
            candidate["user_id"], candidate["supervision_id"], candidate["offer_id"]
        )
    with db.connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.whatsapp_outbound").fetchone()[
                "n"
            ]
            == 0
        )


@pytest.mark.parametrize("limit", [True, 0, -1, 101, "1", None])
def test_recovery_discovery_limit_rejected_before_database_access(limit):
    with pytest.raises(ValueError, match="Invalid offer recovery limit"):
        Store("not-a-database").pending_course_offer_deliveries(limit=limit)


def test_private_offer_uses_existing_queue_and_one_use_dispatch_with_signed_receipt(device):
    db, monitor, offer = prepared(device)
    action = queue(db, monitor, offer)
    assert queue(db, monitor, offer)["id"] == action["id"]
    claim = db.claim_whatsapp_delivery("worker")
    assert claim.task_id is None and claim.offer_id == offer["id"]
    auth = db.authorize_whatsapp_send(claim, **ACCOUNT)
    assert auth.state == "permitted" and auth.text == offer["message"]
    assert state(db)["dispatch_payload"] == {"kind": "text", "text": offer["message"]}
    with pytest.raises(LeaseLost):
        db.authorize_whatsapp_send(claim, **ACCOUNT)
    db.record_whatsapp_result(
        claim,
        DeliveryResult(internal_id=claim.action_id, state="accepted", provider_ref="wamid.one"),
    )
    assert db.pending_course_offer_deliveries() == []
    assert db.record_whatsapp_status(status(), **ACCOUNT)["matched"]
    assert state(db)["state"] == "delivered"
    assert db.claim_whatsapp_delivery("another") is None


def test_reply_consent_does_not_enable_proactive_offers(device):
    db, monitor, offer = prepared(device, consent=False)
    with pytest.raises(ValueError, match="proactive_consent_missing"):
        queue(db, monitor, offer)
    db.provision("user_bob")
    with pytest.raises(LookupError):
        db.set_course_notification_consent("user_bob", monitor["id"], consent=True)


@pytest.mark.parametrize(
    "mode,reason",
    [
        ("consent", "proactive_consent_missing"),
        ("pause", "course_paused"),
        ("decision", "offer_not_pending"),
        ("unlink", "link_changed"),
        ("expired", "offer_expired"),
    ],
)
def test_current_controls_rechecked_after_queue(device, mode, reason):
    db, monitor, offer = prepared(device)
    queue(db, monitor, offer)
    claim = db.claim_whatsapp_delivery("worker")
    if mode == "consent":
        db.set_course_notification_consent("user_alice", monitor["id"], consent=False)
    elif mode == "pause":
        db.pause_course_supervision("user_alice", monitor["id"])
    elif mode == "decision":
        db.decide_course_offer("user_alice", monitor["id"], offer["id"], accept=False)
    elif mode == "unlink":
        db.unlink_whatsapp("user_alice")
    else:
        with db.connection() as conn:
            conn.execute("UPDATE wrytely_agent.course_offers SET created_at=now()-interval '25h'")
    auth = db.authorize_whatsapp_send(claim, **ACCOUNT)
    assert auth.state in ("held", "cancelled") and auth.reason == reason
    assert state(db)["dispatch_at"] is None


@pytest.mark.parametrize("config", ["missing", "reply_only", "wrong_account", "approved"])
def test_expired_window_requires_distinct_account_scoped_offer_template(device, config):
    db, monitor, offer = prepared(device)
    queue(db, monitor, offer)
    with db.connection() as conn:
        conn.execute("UPDATE wrytely_agent.channel_links SET last_event_at=now()-interval '25h'")
    templates = [] if config == "missing" else [template(offer=config != "reply_only")]
    if config == "wrong_account":
        templates = [templates[0].model_copy(update={"business_id": "different"})]
    auth = db.authorize_whatsapp_send(
        db.claim_whatsapp_delivery("worker"),
        **ACCOUNT,
        supports_templates=True,
        approved_offer_templates=templates,
        offer_template_key="test_offer",
    )
    if config == "approved":
        assert auth.state == "permitted" and auth.payload.kind == "template"
        assert auth.payload.body_parameters == (offer["message"],)
    else:
        assert auth.state == "held" and state(db)["dispatch_at"] is None


def test_unknown_dispatch_never_requeues_on_restart(device):
    db, monitor, offer = prepared(device)
    queue(db, monitor, offer)
    claim = db.claim_whatsapp_delivery("worker")
    db.authorize_whatsapp_send(claim, **ACCOUNT)
    with db.connection() as conn:
        conn.execute("UPDATE wrytely_agent.whatsapp_outbound SET lease_until=now()-interval '1s'")
    assert db.claim_whatsapp_delivery("restart") is None
    assert state(db)["state"] == "unknown"
    assert queue(db, monitor, offer)["state"] == "unknown"
    assert db.pending_course_offer_deliveries() == []


def test_changed_course_source_cancels_queued_offer(device):
    import test_canvas_evidence as evidence

    db, monitor, offer = prepared(device)
    queue(db, monitor, offer)
    claim = db.claim_whatsapp_delivery("worker")
    scan = evidence.next_scan(device, "updated-source")
    item = evidence.assignment()
    item["content"] = "New instructions and deadline."
    receipt = evidence.upload(device, scan, evidence.body(device, scan, [item]))
    evidence.close(device, scan, receipt)
    auth = db.authorize_whatsapp_send(claim, **ACCOUNT)
    assert auth.state == "cancelled" and auth.reason == "offer_source_changed"


def test_three_daily_dispatch_limit_counts_accepted_and_unknown_reservations(device):
    import test_canvas_evidence as evidence

    db, monitor, first = prepared(device, limit=20)
    queue(db, monitor, first)
    claim = db.claim_whatsapp_delivery("first")
    assert db.authorize_whatsapp_send(claim, **ACCOUNT).state == "permitted"
    db.record_whatsapp_result(claim, DeliveryResult(internal_id=claim.action_id, state="unknown"))
    scan = evidence.next_scan(device, "more-assignments")
    items = []
    for i in range(4):
        item = evidence.assignment()
        item["provider_id"] = str(17 + i)
        item["content"] = "A📚B"
        items.append(item)
    receipt = evidence.upload(device, scan, evidence.body(device, scan, items))
    evidence.close(device, scan, receipt)
    sources = db.list_canvas_evidence("user_alice", connection_id=device[1]["connection_id"])[
        "sources"
    ]
    for i, source in enumerate(s for s in sources if s["provider_id"] != "17"):
        due(db, monitor)
        obj = source["object_id"]
        run_course_supervision_once(
            db, Model(decision("inspect", obj)), "user_alice", monitor["id"]
        )
        run_course_supervision_once(
            db, Model(decision("offer", obj, "Help with this task?")), "user_alice", monitor["id"]
        )
        offer = next(
            o
            for o in db.course_supervision_status("user_alice", monitor["id"])["offers"]
            if str(o["object_id"]) == str(obj)
        )
        queue(db, monitor, offer)
        claim = db.claim_whatsapp_delivery("quota")
        auth = db.authorize_whatsapp_send(claim, **ACCOUNT)
        if i == 2:
            assert auth.state == "held" and auth.reason == "proactive_daily_limit"
        else:
            assert auth.state == "permitted"
            db.record_whatsapp_result(
                claim, DeliveryResult(internal_id=claim.action_id, state="unknown")
            )
