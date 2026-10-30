from datetime import UTC, datetime

import pytest

from integrations.whatsapp import WhatsAppText

PHONE = "15555550123"


def link(store):
    code = store.create_whatsapp_challenge("user_alice")["message"]
    store.ingest_whatsapp(WhatsAppText("link", PHONE, code))


def test_unprovisioned_and_disconnected_are_distinct(store, alice):
    assert store.whatsapp_connection("user_missing") is None
    assert store.whatsapp_connection("user_alice") == {
        "linked": False,
        "phone_last4": None,
        "preferences": None,
        "latest_delivery": None,
    }


def test_linked_read_exposes_no_challenge_or_private_identifiers(store, alice):
    link(store)
    result = store.whatsapp_connection("user_alice")
    assert result["linked"]
    assert result["phone_last4"] == "0123"
    assert PHONE not in str(result)
    assert set(result) == {"linked", "phone_last4", "preferences", "latest_delivery"}
    assert result["preferences"] is None
    assert result["latest_delivery"] is None


def test_explicit_false_preferences_are_not_unknown(store, alice):
    store.set_communication_preferences(
        "user_alice", consent=False, timezone="America/Denver", quiet_start=22, quiet_end=7
    )
    assert store.whatsapp_connection("user_alice")["preferences"] == {
        "consent": False,
        "timezone": "America/Denver",
        "quiet_start": 22,
        "quiet_end": 7,
    }


def test_delivery_status_is_private_and_does_not_include_content(store, alice):
    link(store)
    store.ingest_whatsapp(WhatsAppText("incoming", PHONE, "Private assignment"))
    store.complete(store.claim(), "Private reply")
    store.provision("user_bob")
    with store.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.whatsapp_outbound SET state='deferred', "
            "hold_reason='preferences_missing',retry_at=now()+interval '5 minutes'"
        )
    alice_status = store.whatsapp_connection("user_alice")
    assert alice_status["latest_delivery"]["state"] == "deferred"
    assert alice_status["latest_delivery"]["reason"] == "preferences_missing"
    assert alice_status["latest_delivery"]["retry_at"] > datetime.now(UTC)
    assert "Private" not in str(alice_status)
    bob_status = store.whatsapp_connection("user_bob")
    assert bob_status["latest_delivery"] is None
    assert bob_status["phone_last4"] is None


def test_unlink_is_reflected_without_erasing_explicit_preferences(store, alice):
    link(store)
    store.set_communication_preferences(
        "user_alice", consent=True, timezone="UTC", quiet_start=0, quiet_end=0
    )
    store.unlink_whatsapp("user_alice")
    status = store.whatsapp_connection("user_alice")
    assert not status["linked"]
    assert status["phone_last4"] is None
    assert status["preferences"]["consent"] is True


def test_storage_error_is_not_reported_as_disconnected(store, alice, monkeypatch):
    def unavailable():
        raise RuntimeError("Simulated storage failure")

    monkeypatch.setattr(store, "connection", unavailable)
    with pytest.raises(RuntimeError):
        store.whatsapp_connection("user_alice")
