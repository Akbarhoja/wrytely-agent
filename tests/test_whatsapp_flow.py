import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from test_api import TestVerifier, auth

from app.main import create_app
from integrations.whatsapp import WhatsAppText
from shared.config import Settings


def post_signed(client, value, *, valid=True):
    body = json.dumps(
        {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "456",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "metadata": {"phone_number_id": "123"},
                                **value,
                            },
                        }
                    ],
                }
            ],
        }
    ).encode()
    signature = "sha256=" + hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
    return client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={"x-hub-signature-256": signature if valid else "bad"},
    )


def test_private_connection_read_and_session_restore(store, alice):
    client = setup(store)
    assert client.get("/v1/whatsapp").status_code == 401
    assert client.get("/v1/whatsapp", headers=auth("bob")).status_code == 404
    phone = link(store)
    preferences = {"consent": False, "timezone": "UTC", "quiet_start": 0, "quiet_end": 0}
    client.post("/v1/whatsapp/preferences", headers=auth(), json=preferences)
    response = client.get("/v1/whatsapp?user_id=user_bob", headers=auth())
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    state = response.json()
    assert state["linked"] and state["phone_last4"] == phone[-4:]
    assert state["preferences"] == preferences
    assert state["destination"] is None and state["configured"] is False
    assert phone not in response.text and "test-secret" not in response.text
    store.provision("user_bob")
    bob = client.get("/v1/whatsapp", headers=auth("bob")).json()
    assert bob["linked"] is False and bob["preferences"] is None
    assert setup(store).get("/v1/whatsapp", headers=auth()).json() == state
    client.post("/v1/whatsapp/unlink", headers=auth())
    assert client.get("/v1/whatsapp", headers=auth()).json()["linked"] is False


def test_connection_configuration_and_storage_failure_are_distinct(store, alice, monkeypatch):
    from psycopg import OperationalError

    settings = Settings(
        whatsapp_business_number="15555550100",
        whatsapp_app_secret="test-secret",
        whatsapp_verify_token="test-verify",
        whatsapp_phone_number_id="123",
        whatsapp_business_account_id="456",
    )
    client = TestClient(create_app(settings, store=store, verifier=TestVerifier()))
    state = client.get("/v1/whatsapp", headers=auth()).json()
    assert state["configured"] is True and state["destination"] == "15555550100"

    def unavailable(*args):
        raise OperationalError("private storage error")

    monkeypatch.setattr(store, "whatsapp_connection", unavailable)
    response = client.get("/v1/whatsapp", headers=auth())
    assert response.status_code == 503
    assert "private storage error" not in response.text


def test_private_preferences_validate_input_and_derive_verified_owner(store, alice):
    client = setup(store)
    preferences = {"consent": True, "timezone": "America/Denver", "quiet_start": 22, "quiet_end": 7}
    assert client.post("/v1/whatsapp/preferences", json=preferences).status_code == 401
    assert (
        client.post("/v1/whatsapp/preferences", json=preferences, headers=auth()).status_code == 200
    )
    for patch in [
        {"user_id": "user_bob"},
        {"timezone": "Invalid/Timezone"},
        {"quiet_start": 24},
        {"quiet_start": True},
        {"consent": "true"},
    ]:
        assert (
            client.post(
                "/v1/whatsapp/preferences", json={**preferences, **patch}, headers=auth()
            ).status_code
            == 422
        )
    store.provision("user_bob")
    with store.connection() as conn:
        rows = conn.execute(
            "SELECT p.*,a.user_id FROM wrytely_agent.communication_preferences p "
            "JOIN wrytely_agent.agents a ON a.id=p.agent_id"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["user_id"] == "user_alice"
    assert rows[0]["timezone"] == "America/Denver"


def test_signed_inbound_time_is_persisted_from_event_not_receipt(store, alice):
    client = setup(store)
    phone = link(store)
    old = datetime.now(UTC) - timedelta(hours=25)
    event = {
        "type": "text",
        "from": phone,
        "id": "delayed-inbound",
        "text": {"body": "Read this"},
        "timestamp": str(int(old.timestamp())),
    }
    assert post_signed(client, {"messages": [event]}, valid=False).status_code == 403
    assert post_signed(client, {"messages": [event]}).status_code == 200
    assert post_signed(client, {"messages": [event]}).status_code == 200
    with store.connection() as conn:
        row = conn.execute("SELECT last_event_at FROM wrytely_agent.channel_links").fetchone()
    assert row["last_event_at"] == old.replace(microsecond=0)
    assert len(store.tasks("user_alice")) == 1


def test_authenticated_status_replay_before_response_reconciles_without_regression(store, alice):
    from contracts.models import DeliveryResult

    client = setup(store)
    phone = link(store)
    store.ingest_whatsapp(WhatsAppText("status-task", phone, "Help"))
    store.record_whatsapp_inbound_time("status-task", phone, datetime.now(UTC))
    store.set_communication_preferences(
        "user_alice", consent=True, timezone="UTC", quiet_start=0, quiet_end=0
    )
    store.complete(store.claim(), "Ready")
    claim = store.claim_whatsapp_delivery("test-worker")
    store.authorize_whatsapp_send(claim, business_id="456", phone_number_id="123")
    event = {
        "id": "wamid.callback",
        "recipient_id": phone,
        "status": "delivered",
        "timestamp": str(int(datetime.now(UTC).timestamp())),
    }
    assert post_signed(client, {"statuses": [event]}, valid=False).status_code == 403
    assert post_signed(client, {"statuses": [event]}).status_code == 200
    store.record_whatsapp_result(
        claim,
        DeliveryResult(
            internal_id=claim.action_id, state="accepted", provider_ref="wamid.callback"
        ),
    )
    assert post_signed(client, {"statuses": [event]}).status_code == 200
    assert post_signed(client, {"statuses": [{**event, "status": "sent"}]}).status_code == 200
    assert post_signed(client, {"statuses": [{**event, "status": "failed"}]}).status_code == 200
    with store.connection() as conn:
        row = conn.execute("SELECT state FROM wrytely_agent.whatsapp_outbound").fetchone()
        events = conn.execute("SELECT * FROM wrytely_agent.whatsapp_status_events").fetchall()
    assert row["state"] == "delivered"
    assert len(events) == 3
    assert all(item["action_id"] == claim.action_id for item in events)


def test_status_wrong_recipient_cannot_mark_another_accounts_reply_delivered(store, alice):
    from contracts.models import DeliveryResult

    client = setup(store)
    phone = link(store)
    store.ingest_whatsapp(WhatsAppText("private-status", phone, "Help"))
    store.record_whatsapp_inbound_time("private-status", phone, datetime.now(UTC))
    store.set_communication_preferences(
        "user_alice", consent=True, timezone="UTC", quiet_start=0, quiet_end=0
    )
    store.complete(store.claim(), "Private result")
    claim = store.claim_whatsapp_delivery("test-worker")
    store.authorize_whatsapp_send(claim, business_id="456", phone_number_id="123")
    store.record_whatsapp_result(
        claim,
        DeliveryResult(internal_id=claim.action_id, state="accepted", provider_ref="wamid.private"),
    )
    store.provision("user_bob")
    link(store, user="user_bob", phone="15555550999")
    event = {
        "id": "wamid.private",
        "recipient_id": "15555550999",
        "status": "delivered",
        "timestamp": str(int(datetime.now(UTC).timestamp())),
    }
    assert post_signed(client, {"statuses": [event]}).status_code == 200
    with store.connection() as conn:
        assert (
            conn.execute("SELECT state FROM wrytely_agent.whatsapp_outbound").fetchone()["state"]
            == "accepted"
        )
        assert (
            conn.execute("SELECT action_id FROM wrytely_agent.whatsapp_status_events").fetchone()[
                "action_id"
            ]
            is None
        )


def test_callback_storage_rejection_is_not_acknowledged_and_replay_can_recover(
    store, alice, monkeypatch
):
    client = setup(store)
    event = {
        "id": "wamid.orphan",
        "recipient_id": "15555550123",
        "status": "delivered",
        "timestamp": str(int(datetime.now(UTC).timestamp())),
    }
    record = store.record_whatsapp_status

    def unavailable(*args, **kwargs):
        raise ValueError("Unmatched status capacity reached")

    monkeypatch.setattr(store, "record_whatsapp_status", unavailable)
    assert post_signed(client, {"statuses": [event]}).status_code == 503
    monkeypatch.setattr(store, "record_whatsapp_status", record)
    assert post_signed(client, {"statuses": [event]}).status_code == 200
    with store.connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.whatsapp_status_events"
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute("SELECT action_id FROM wrytely_agent.whatsapp_status_events").fetchone()[
                "action_id"
            ]
            is None
        )


def setup(store):
    settings = Settings(
        whatsapp_app_secret="test-secret",
        whatsapp_verify_token="test-verify",
        whatsapp_phone_number_id="123",
        whatsapp_business_account_id="456",
    )
    return TestClient(create_app(settings, store=store, verifier=TestVerifier()))


def link(store, user="user_alice", phone="15555550123"):
    challenge = store.create_whatsapp_challenge(user)
    assert (
        store.ingest_whatsapp(WhatsAppText(str(uuid4()), phone, challenge["message"])) == "linked"
    )
    return phone


def test_link_rotation_expiry_and_single_use(store, alice):
    first = store.create_whatsapp_challenge("user_alice")
    second = store.create_whatsapp_challenge("user_alice")
    assert store.ingest_whatsapp(WhatsAppText("old", "15555550123", first["message"])) == "ignored"
    assert store.ingest_whatsapp(WhatsAppText("new", "15555550123", second["message"])) == "linked"
    assert (
        store.ingest_whatsapp(WhatsAppText("again", "15555550999", second["message"])) == "ignored"
    )
    assert store.messages("user_alice") == []
    store.unlink_whatsapp("user_alice")
    expired = store.create_whatsapp_challenge("user_alice")
    with store.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.channel_challenges SET expires_at=now()-interval '1 second'"
        )
    assert (
        store.ingest_whatsapp(WhatsAppText("expired", "15555550123", expired["message"]))
        == "ignored"
    )


def test_atomic_ingestion_deduplication_and_reply_outbox(store, alice):
    phone = link(store)
    msg = WhatsAppText("wamid.inbound", phone, "Explain this assignment")
    assert store.ingest_whatsapp(msg) == "queued"
    assert store.ingest_whatsapp(msg) == "duplicate"
    assert len(store.tasks("user_alice")) == 1
    lease = store.claim()
    store.complete(lease, "Saved reply")
    with store.connection() as conn:
        rows = conn.execute("SELECT * FROM wrytely_agent.whatsapp_outbound").fetchall()
    assert len(rows) == 1
    assert rows[0]["recipient"] == phone
    assert rows[0]["state"] == "queued"
    assert rows[0]["content"] == "Saved reply"
    store.unlink_whatsapp("user_alice")
    with store.connection() as conn:
        assert (
            conn.execute("SELECT state FROM wrytely_agent.whatsapp_outbound").fetchone()["state"]
            == "cancelled"
        )
    assert store.ingest_whatsapp(WhatsAppText("unlinked", phone, "private")) == "ignored"


def test_web_tasks_do_not_send_to_linked_phone(store, alice):
    link(store)
    store.enqueue("user_alice", "Web only", "web-key")
    store.complete(store.claim(), "Web reply")
    with store.connection() as conn:
        assert not conn.execute("SELECT * FROM wrytely_agent.whatsapp_outbound").fetchall()


def test_number_cannot_link_to_two_students(store, alice):
    phone = link(store)
    store.provision("user_bob")
    challenge = store.create_whatsapp_challenge("user_bob")
    assert store.ingest_whatsapp(WhatsAppText("steal", phone, challenge["message"])) == "ignored"
    assert store.messages("user_bob") == []


def test_webhook_signature_and_link_endpoint(store, alice):
    client = setup(store)
    assert client.post("/v1/whatsapp/link").status_code == 401
    challenge = client.post("/v1/whatsapp/link", headers=auth()).json()["message"]
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "456",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"phone_number_id": "123"},
                            "messages": [
                                {
                                    "type": "text",
                                    "from": "15555550123",
                                    "id": "link-event",
                                    "text": {"body": challenge},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    body = json.dumps(payload).encode()
    assert client.post("/webhooks/whatsapp", content=body).status_code == 403
    signature = "sha256=" + hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
    assert (
        client.post(
            "/webhooks/whatsapp", content=body, headers={"x-hub-signature-256": signature}
        ).status_code
        == 200
    )
    assert client.post("/v1/whatsapp/link", headers=auth()).status_code == 409
    assert (
        client.get(
            "/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "test-verify",
                "hub.challenge": "123456",
            },
        ).text
        == "123456"
    )
    assert (
        client.get(
            "/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong",
                "hub.challenge": "123456",
            },
        ).status_code
        == 403
    )
    assert client.post("/v1/whatsapp/unlink", headers=auth("bob")).status_code == 200
    assert client.post("/v1/whatsapp/link", headers=auth()).status_code == 409


def test_queue_full_rolls_back_then_provider_can_retry(store, alice):
    import pytest

    from shared.db import QueueFull

    phone = link(store)
    message = WhatsAppText("retry-event", phone, "Do this")
    with pytest.raises(QueueFull):
        store.ingest_whatsapp(message, limit=0)
    assert store.tasks("user_alice") == []
    assert store.ingest_whatsapp(message) == "queued"


def test_concurrent_provider_retries_create_one_task(store, alice):
    from concurrent.futures import ThreadPoolExecutor

    phone = link(store)
    message = WhatsAppText("concurrent-event", phone, "Read assignment")
    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(store.ingest_whatsapp, [message] * 4))
    assert outcomes.count("queued") == 1
    assert outcomes.count("duplicate") == 3
    assert len(store.tasks("user_alice")) == 1


def test_unlink_before_task_completion_prevents_reply_queue(store, alice):
    phone = link(store)
    store.ingest_whatsapp(WhatsAppText("pending-event", phone, "Read this"))
    lease = store.claim()
    store.unlink_whatsapp("user_alice")
    link(store, phone="15555550999")
    store.complete(lease, "Private saved result")
    with store.connection() as conn:
        assert not conn.execute("SELECT * FROM wrytely_agent.whatsapp_outbound").fetchall()
