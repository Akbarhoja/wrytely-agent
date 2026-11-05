from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from contracts.delivery import WhatsAppStatusEvent
from contracts.models import DeliveryResult
from shared.db import LeaseLost

PHONE = "15555550123"
ACCOUNT = {"business_id": "business-test", "phone_number_id": "phone-test"}


def queued(store, alice, *, preferences=True, event_time=True):
    from integrations.whatsapp import WhatsAppText

    token = store.create_whatsapp_challenge("user_alice")["message"]
    store.ingest_whatsapp(WhatsAppText("link-one", PHONE, token))
    store.ingest_whatsapp(WhatsAppText("message-one", PHONE, "Explain assignment"))
    if event_time:
        store.record_whatsapp_inbound_time("message-one", PHONE, datetime.now(UTC))
    if preferences:
        store.set_communication_preferences(
            "user_alice", consent=True, timezone="UTC", quiet_start=0, quiet_end=0
        )
    store.complete(store.claim(), "Saved answer")


def state(store):
    with store.connection() as conn:
        return conn.execute("SELECT * FROM wrytely_agent.whatsapp_outbound").fetchone()


def status(provider_ref="wamid.one", kind="delivered", recipient=PHONE):
    return WhatsAppStatusEvent(
        **ACCOUNT,
        provider_ref=provider_ref,
        recipient=recipient,
        status=kind,
        event_at=datetime.now(UTC),
    )


def test_concurrent_claim_authorization_and_result(store, alice):
    queued(store, alice)
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = list(pool.map(store.claim_whatsapp_delivery, ["a", "b", "c", "d"]))
    claims = [claim for claim in claims if claim]
    assert len(claims) == 1
    claim = claims[0]
    auth = store.authorize_whatsapp_send(claim, **ACCOUNT)
    assert auth.state == "permitted"
    assert auth.text == "Saved answer"
    with pytest.raises(LeaseLost):
        store.authorize_whatsapp_send(claim, **ACCOUNT)
    store.record_whatsapp_result(
        claim,
        DeliveryResult(internal_id=claim.action_id, state="accepted", provider_ref="wamid.one"),
    )
    assert state(store)["state"] == "accepted"
    assert store.claim_whatsapp_delivery("next") is None


@pytest.mark.parametrize(
    "mode,reason",
    [
        ("missing", "preferences_missing"),
        ("consent", "consent_missing"),
        ("paused", "paused"),
        ("time", "inbound_time_unknown"),
        ("expired", "approved_template_required"),
        ("quiet", "quiet_hours"),
    ],
)
def test_required_controls_hold_sending(store, alice, mode, reason):
    queued(store, alice, preferences=mode != "missing", event_time=mode != "time")
    if mode == "consent":
        store.set_communication_preferences(
            "user_alice", consent=False, timezone="UTC", quiet_start=0, quiet_end=0
        )
    if mode == "paused":
        store.set_paused("user_alice", True)
    if mode == "expired":
        with store.connection() as conn:
            conn.execute(
                "UPDATE wrytely_agent.channel_links SET last_event_at=now()-interval '25 hours'"
            )
    if mode == "quiet":
        hour = datetime.now(UTC).hour
        store.set_communication_preferences(
            "user_alice", consent=True, timezone="UTC", quiet_start=hour, quiet_end=(hour + 1) % 24
        )
    auth = store.authorize_whatsapp_send(store.claim_whatsapp_delivery("worker"), **ACCOUNT)
    assert auth.state == "held"
    assert auth.reason == reason
    assert state(store)["dispatch_at"] is None
    assert state(store)["state"] == "deferred"


def test_expired_attempt_never_becomes_sendable_again(store, alice):
    queued(store, alice)
    claim = store.claim_whatsapp_delivery("first")
    store.authorize_whatsapp_send(claim, **ACCOUNT)
    with store.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.whatsapp_outbound SET lease_until=now()-interval '1 second'"
        )
    assert store.claim_whatsapp_delivery("second") is None
    assert state(store)["state"] == "unknown"
    with pytest.raises(LeaseLost):
        store.record_whatsapp_result(
            claim,
            DeliveryResult(internal_id=claim.action_id, state="accepted", provider_ref="late"),
        )


def test_unlink_and_relink_cannot_reuse_claim(store, alice):
    from integrations.whatsapp import WhatsAppText

    queued(store, alice)
    claim = store.claim_whatsapp_delivery("worker")
    store.unlink_whatsapp("user_alice")
    token = store.create_whatsapp_challenge("user_alice")["message"]
    store.ingest_whatsapp(WhatsAppText("new-link", PHONE, token))
    assert store.authorize_whatsapp_send(claim, **ACCOUNT).state == "cancelled"
    assert state(store)["dispatch_at"] is None


def test_early_callbacks_reconcile_and_never_regress_delivery(store, alice):
    queued(store, alice)
    claim = store.claim_whatsapp_delivery("worker")
    store.authorize_whatsapp_send(claim, **ACCOUNT)
    event = status()
    assert store.record_whatsapp_status(event, **ACCOUNT) == {"matched": False}
    store.record_whatsapp_result(
        claim,
        DeliveryResult(internal_id=claim.action_id, state="accepted", provider_ref="wamid.one"),
    )
    assert state(store)["state"] == "delivered"
    assert store.record_whatsapp_status(event, **ACCOUNT) == {"matched": True}
    store.record_whatsapp_status(status(kind="failed"), **ACCOUNT)
    store.record_whatsapp_status(status(kind="sent"), **ACCOUNT)
    assert state(store)["state"] == "delivered"
    with store.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.whatsapp_status_events"
            ).fetchone()["n"]
            == 3
        )


def test_wrong_account_or_recipient_does_not_update_action(store, alice):
    queued(store, alice)
    claim = store.claim_whatsapp_delivery("worker")
    store.authorize_whatsapp_send(claim, **ACCOUNT)
    store.record_whatsapp_result(
        claim,
        DeliveryResult(internal_id=claim.action_id, state="unknown", provider_ref="wamid.one"),
    )
    assert not store.record_whatsapp_status(status(recipient="15555550999"), **ACCOUNT)["matched"]
    assert state(store)["state"] == "unknown"
    with pytest.raises(ValueError):
        store.record_whatsapp_status(status(), business_id="wrong", phone_number_id="phone-test")


def test_receipt_time_cannot_reopen_old_window(store, alice):
    queued(store, alice, event_time=False)
    store.record_whatsapp_inbound_time(
        "message-one", PHONE, datetime.now(UTC) - timedelta(hours=26)
    )
    auth = store.authorize_whatsapp_send(store.claim_whatsapp_delivery("worker"), **ACCOUNT)
    assert auth.reason == "approved_template_required"
    with pytest.raises(ValueError):
        store.record_whatsapp_inbound_time(
            "message-one", PHONE, datetime.now(UTC) + timedelta(hours=1)
        )


def test_result_requires_real_authorized_attempt(store, alice):
    queued(store, alice)
    claim = store.claim_whatsapp_delivery("worker")
    with pytest.raises(ValueError):
        store.record_whatsapp_result(
            claim,
            DeliveryResult(internal_id=claim.action_id, state="accepted", provider_ref="wamid.one"),
        )
    with pytest.raises(ValueError):
        store.record_whatsapp_result(claim, DeliveryResult(internal_id=uuid4(), state="unknown"))


def test_callback_and_result_can_race_without_losing_evidence(store, alice):
    queued(store, alice)
    claim = store.claim_whatsapp_delivery("worker")
    store.authorize_whatsapp_send(claim, **ACCOUNT)
    result = DeliveryResult(internal_id=claim.action_id, state="accepted", provider_ref="wamid.one")
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(store.record_whatsapp_result, claim, result),
            pool.submit(store.record_whatsapp_status, status(), **ACCOUNT),
        ]
        for future in futures:
            future.result(timeout=10)
    assert state(store)["state"] == "delivered"


def test_stale_backfill_without_generation_cannot_send(store, alice):
    queued(store, alice)
    with store.connection() as conn:
        conn.execute("UPDATE wrytely_agent.whatsapp_outbound SET link_generation=NULL")
    auth = store.authorize_whatsapp_send(store.claim_whatsapp_delivery("worker"), **ACCOUNT)
    assert auth.state == "cancelled"
    assert auth.reason == "link_changed"


def test_untrusted_timestamp_must_match_persisted_sender_and_link(store, alice):
    queued(store, alice, event_time=False)
    store.record_whatsapp_inbound_time("not-persisted", PHONE, datetime.now(UTC))
    store.record_whatsapp_inbound_time("message-one", "15555550999", datetime.now(UTC))
    auth = store.authorize_whatsapp_send(store.claim_whatsapp_delivery("worker"), **ACCOUNT)
    assert auth.reason == "inbound_time_unknown"


def test_consent_preferences_are_private(store, alice):
    queued(store, alice)
    store.provision("user_bob")
    store.set_communication_preferences(
        "user_bob", consent=False, timezone="UTC", quiet_start=0, quiet_end=0
    )
    assert (
        store.authorize_whatsapp_send(store.claim_whatsapp_delivery("worker"), **ACCOUNT).state
        == "permitted"
    )


def fill_orphan_capacity(store):
    with store.connection() as conn:
        conn.execute(
            "INSERT INTO wrytely_agent.whatsapp_status_events "
            "(event_hash,business_id,phone_number_id,provider_ref,recipient,status,event_at) "
            "SELECT 'orphan-'||n,%s,%s,'unknown-'||n,%s,'sent',now() "
            "FROM generate_series(1,10000) AS n",
            (ACCOUNT["business_id"], ACCOUNT["phone_number_id"], PHONE),
        )


def test_matched_delivery_callback_bypasses_orphan_capacity(store, alice):
    queued(store, alice)
    claim = store.claim_whatsapp_delivery("worker")
    store.authorize_whatsapp_send(claim, **ACCOUNT)
    store.record_whatsapp_result(
        claim,
        DeliveryResult(internal_id=claim.action_id, state="accepted", provider_ref="wamid.one"),
    )
    fill_orphan_capacity(store)
    event = status()
    assert store.record_whatsapp_status(event, **ACCOUNT) == {"matched": True}
    assert state(store)["state"] == "delivered"
    assert store.record_whatsapp_status(event, **ACCOUNT) == {"matched": True}
    with store.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.whatsapp_status_events "
                "WHERE action_id IS NULL"
            ).fetchone()["n"]
            == 10000
        )


def test_new_orphan_still_rejected_at_capacity_even_with_known_reference(store, alice):
    queued(store, alice)
    claim = store.claim_whatsapp_delivery("worker")
    store.authorize_whatsapp_send(claim, **ACCOUNT)
    store.record_whatsapp_result(
        claim,
        DeliveryResult(internal_id=claim.action_id, state="accepted", provider_ref="wamid.one"),
    )
    fill_orphan_capacity(store)
    with pytest.raises(ValueError, match="capacity"):
        store.record_whatsapp_status(status(recipient="15555550999"), **ACCOUNT)
    with pytest.raises(ValueError, match="capacity"):
        store.record_whatsapp_status(status(provider_ref="wamid.unmatched"), **ACCOUNT)
    assert state(store)["state"] == "accepted"


def test_existing_orphan_replay_is_accepted_at_capacity(store, alice):
    event = status(provider_ref="wamid.early")
    assert store.record_whatsapp_status(event, **ACCOUNT) == {"matched": False}
    fill_orphan_capacity(store)
    assert store.record_whatsapp_status(event, **ACCOUNT) == {"matched": False}
