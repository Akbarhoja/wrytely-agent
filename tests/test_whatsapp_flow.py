import hashlib
import hmac
import json
from uuid import uuid4

from fastapi.testclient import TestClient
from test_api import TestVerifier, auth

from app.main import create_app
from integrations.whatsapp import WhatsAppText
from shared.config import Settings


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
