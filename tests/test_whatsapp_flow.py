import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from test_api import TestVerifier, auth
from test_worker import ScriptedModel, answer, function_turn

from app.main import create_app
from integrations.whatsapp import WhatsAppText
from shared.config import Settings
from shared.db import Store


@pytest.mark.parametrize("lost_response", [False, True], ids=["accepted", "unknown"])
def test_offline_m1_round_trip_across_api_workers_and_callbacks(store, database_url, lost_response):
    from integrations.whatsapp import WhatsAppAdapter
    from integrations.whatsapp_delivery import run_once as deliver_once
    from runtime.worker import run_once as reason_once

    client = setup(store, whatsapp_business_number="15555550100")
    agents = {}
    phones = {"alice": "15555550123", "bob": "15555550999"}
    for who, phone in phones.items():
        agents[who] = client.post("/v1/bootstrap", headers=auth(who)).json()["id"]
        challenge = client.post("/v1/whatsapp/link", headers=auth(who)).json()
        assert challenge["expires_in_seconds"] == 600
        event = {
            "id": f"link-{who}",
            "type": "text",
            "from": phone,
            "text": {"body": challenge["message"]},
            "timestamp": str(int(datetime.now(UTC).timestamp())),
        }
        assert post_signed(client, {"messages": [event]}).status_code == 200
        assert (
            client.post(
                "/v1/whatsapp/preferences",
                headers=auth(who),
                json={
                    "consent": True,
                    "timezone": "UTC",
                    "quiet_start": 0,
                    "quiet_end": 0,
                },
            ).status_code
            == 200
        )
        state = client.get("/v1/whatsapp", headers=auth(who)).json()
        assert state["configured"] and state["phone_last4"] == phone[-4:]
        assert state["latest_delivery"] is None
    assert agents["alice"] != agents["bob"]

    inbound = {
        "id": "question-alice",
        "type": "text",
        "from": phones["alice"],
        "text": {"body": "Explain a synthetic study topic"},
        "timestamp": str(int(datetime.now(UTC).timestamp())),
    }
    assert post_signed(client, {"messages": [inbound]}).status_code == 200
    assert post_signed(client, {"messages": [inbound]}).status_code == 200
    task_id = client.get("/v1/tasks", headers=auth()).json()["tasks"][0]["id"]
    assert (
        client.post(
            "/v1/messages",
            headers=auth("bob") | {"Idempotency-Key": "private-bob"},
            json={"content": "Bob's private sentinel"},
        ).status_code
        == 202
    )
    model = ScriptedModel([function_turn(), answer("A private checked-loop response")])
    assert reason_once(Store(database_url), model, Settings())
    assert "Bob's private sentinel" not in str(model.histories)
    assert "LINK " not in str(model.histories)
    assert client.get(f"/v1/tasks/{task_id}", headers=auth()).json()["status"] == "done"
    assert client.get(f"/v1/tasks/{task_id}", headers=auth("bob")).status_code == 404

    requests = []

    def transport(request):
        requests.append(json.loads(request.content))
        if lost_response:
            raise httpx.ReadTimeout("Synthetic lost response", request=request)
        return httpx.Response(200, json={"messages": [{"id": "wamid.offline-m1"}]})

    expected = "unknown" if lost_response else "accepted"
    with httpx.Client(transport=httpx.MockTransport(transport)) as http:
        adapter = WhatsAppAdapter(
            client=http, token="synthetic-only", phone_number_id="123", api_version="v23.0"
        )
        options = {"business_id": "456", "phone_number_id": "123"}
        assert (
            deliver_once(Store(database_url), adapter, worker_id="offline-m1", **options)
            == expected
        )
        assert deliver_once(Store(database_url), adapter, worker_id="restart", **options) == "idle"
    assert len(requests) == 1
    assert requests[0]["to"] == phones["alice"]
    assert requests[0]["text"]["body"] == "A private checked-loop response"
    assert client.get("/v1/whatsapp", headers=auth()).json()["latest_delivery"]["state"] == expected
    if not lost_response:
        status = {
            "id": "wamid.offline-m1",
            "recipient_id": phones["alice"],
            "status": "delivered",
            "timestamp": str(int(datetime.now(UTC).timestamp())),
        }
        assert post_signed(client, {"statuses": [status]}).status_code == 200
        assert post_signed(client, {"statuses": [status]}).status_code == 200
        status["status"] = "sent"
        assert post_signed(client, {"statuses": [status]}).status_code == 200
        assert (
            client.get("/v1/whatsapp", headers=auth()).json()["latest_delivery"]["state"]
            == "delivered"
        )

    restored = setup(Store(database_url), whatsapp_business_number="15555550100")
    assert restored.post("/v1/bootstrap", headers=auth()).json()["id"] == agents["alice"]
    assert len(restored.get("/v1/tasks", headers=auth()).json()["tasks"]) == 1
    assert "A private checked-loop response" in restored.get("/v1/messages", headers=auth()).text
    assert (
        "A private checked-loop response"
        not in restored.get("/v1/messages", headers=auth("bob")).text
    )
    assert restored.get("/v1/whatsapp", headers=auth("bob")).json()["latest_delivery"] is None


@pytest.mark.parametrize("control", ["pause_before_reasoning", "pause_before_delivery", "unlink"])
def test_offline_m1_http_controls_preserve_work_and_gate_dispatch(store, database_url, control):
    from integrations.whatsapp import WhatsAppAdapter
    from integrations.whatsapp_delivery import run_once as deliver_once
    from runtime.worker import run_once as reason_once

    client = setup(store, whatsapp_business_number="15555550100")
    assert client.post("/v1/bootstrap", headers=auth()).status_code == 200
    phone = "15555550123"
    challenge = client.post("/v1/whatsapp/link", headers=auth()).json()
    for provider_id, text in [
        ("link-control", challenge["message"]),
        ("question-control", "Synthetic question"),
    ]:
        assert (
            post_signed(
                client,
                {
                    "messages": [
                        {
                            "id": provider_id,
                            "type": "text",
                            "from": phone,
                            "text": {"body": text},
                            "timestamp": str(int(datetime.now(UTC).timestamp())),
                        }
                    ]
                },
            ).status_code
            == 200
        )
    assert (
        client.post(
            "/v1/whatsapp/preferences",
            headers=auth(),
            json={
                "consent": True,
                "timezone": "UTC",
                "quiet_start": 0,
                "quiet_end": 0,
            },
        ).status_code
        == 200
    )
    task_id = client.get("/v1/tasks", headers=auth()).json()["tasks"][0]["id"]
    model = ScriptedModel([answer("Saved despite control changes")])
    if control == "pause_before_reasoning":
        assert (
            client.post("/v1/agent/control", headers=auth(), json={"paused": True}).status_code
            == 200
        )
        assert not reason_once(Store(database_url), model, Settings())
        assert model.histories == []
        assert client.get(f"/v1/tasks/{task_id}", headers=auth()).json()["status"] == "ready"
        assert (
            client.post("/v1/agent/control", headers=auth(), json={"paused": False}).status_code
            == 200
        )
    assert reason_once(Store(database_url), model, Settings())
    assert client.get(f"/v1/tasks/{task_id}", headers=auth()).json()["status"] == "done"
    if control == "pause_before_delivery":
        assert (
            client.post("/v1/agent/control", headers=auth(), json={"paused": True}).status_code
            == 200
        )
    elif control == "unlink":
        assert client.post("/v1/whatsapp/unlink", headers=auth()).status_code == 200

    requests = []

    def transport(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"messages": [{"id": "wamid.control"}]})

    with httpx.Client(transport=httpx.MockTransport(transport)) as http:
        adapter = WhatsAppAdapter(
            client=http, token="synthetic-only", phone_number_id="123", api_version="v23.0"
        )
        outcome = deliver_once(
            Store(database_url),
            adapter,
            worker_id="control-check",
            business_id="456",
            phone_number_id="123",
        )
    state = client.get("/v1/whatsapp", headers=auth()).json()
    if control == "pause_before_reasoning":
        assert outcome == "accepted" and len(requests) == 1
        assert requests[0]["to"] == phone
    else:
        assert requests == []
        assert outcome == ("held" if control == "pause_before_delivery" else "idle")
        assert state["latest_delivery"]["state"] == (
            "deferred" if control == "pause_before_delivery" else "cancelled"
        )
    if control == "pause_before_delivery":
        assert state["latest_delivery"]["reason"] == "paused"
    elif control == "unlink":
        assert state["linked"] is False and state["phone_last4"] is None
    restored = setup(Store(database_url))
    assert "Saved despite control changes" in restored.get("/v1/messages", headers=auth()).text


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


def test_malformed_text_sibling_does_not_block_signed_delivery_evidence(store):
    client = setup(store)
    value = {
        "messages": [None, {"type": "text", "text": None}],
        "statuses": [
            {
                "id": "wamid.mixed",
                "recipient_id": "15555550123",
                "status": "delivered",
                "timestamp": str(int(datetime.now(UTC).timestamp())),
            }
        ],
    }
    assert post_signed(client, value, valid=False).status_code == 403
    assert post_signed(client, value).status_code == 200
    assert post_signed(client, value).status_code == 200
    with store.connection() as conn:
        events = conn.execute("SELECT * FROM wrytely_agent.whatsapp_status_events").fetchall()
        assert len(events) == 1
        assert events[0]["provider_ref"] == "wamid.mixed"
        assert events[0]["action_id"] is None


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


def test_link_challenge_response_keeps_relative_expiry_contract(store, alice):
    response = setup(store).post("/v1/whatsapp/link", headers=auth())
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"message", "expires_in_seconds"}
    assert payload["message"].startswith("LINK ")
    assert payload["expires_in_seconds"] == 600


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


def setup(store, **overrides):
    settings = Settings(
        whatsapp_app_secret="test-secret",
        whatsapp_verify_token="test-verify",
        whatsapp_phone_number_id="123",
        whatsapp_business_account_id="456",
        **overrides,
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
