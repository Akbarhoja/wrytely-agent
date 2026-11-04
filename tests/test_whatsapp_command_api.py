"""Exact signed webhook -> bounded command -> real existing Store actions."""

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_artifact_delivery import prepared_file
from test_canvas_sync import device as device
from test_course_offer_delivery import ACCOUNT, PHONE, prepared
from test_source_connection_api import SessionVerifier
from test_whatsapp_commands import counts

from app.main import create_app
from contracts.models import DeliveryResult
from integrations.whatsapp import WhatsAppText
from integrations.whatsapp_commands import InvalidWhatsAppCommand, parse_command
from shared.config import Settings

SECRET = b"synthetic-command-webhook-secret"


def client(db):
    return TestClient(
        create_app(
            Settings(
                _env_file=None,
                whatsapp_app_secret=SECRET.decode(),
                whatsapp_verify_token="synthetic",
                whatsapp_business_account_id=ACCOUNT["business_id"],
                whatsapp_phone_number_id=ACCOUNT["phone_number_id"],
            ),
            store=db,
            verifier=SessionVerifier(),
        )
    )


def event(text, *, provider_id="command-api-one", **changes):
    return {
        "id": provider_id,
        "type": "text",
        "from": PHONE,
        "timestamp": str(int(datetime.now(UTC).timestamp())),
        "text": {"body": text},
        **changes,
    }


def post(api, message, *, valid=True, business=None, number=None, statuses=None):
    value = {
        "metadata": {"phone_number_id": number or ACCOUNT["phone_number_id"]},
        "messages": [message],
    }
    if statuses is not None:
        value["statuses"] = statuses
    body = json.dumps(
        {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": business or ACCOUNT["business_id"],
                    "changes": [{"field": "messages", "value": value}],
                }
            ],
        }
    ).encode()
    signature = "sha256=" + hmac.new(SECRET, body, hashlib.sha256).hexdigest()
    return api.post(
        "/webhooks/whatsapp",
        content=body,
        headers={"x-hub-signature-256": signature if valid else "sha256=wrong"},
    )


def dispatched_offer(device):
    db, monitor, offer = prepared(device)
    db.enqueue_course_offer("user_alice", monitor["id"], offer["id"])
    claim = db.claim_whatsapp_delivery("command-context")
    assert db.authorize_whatsapp_send(claim, **ACCOUNT).state == "permitted"
    db.record_whatsapp_result(
        claim,
        DeliveryResult(
            internal_id=claim.action_id, state="accepted", provider_ref="wamid.command-offer"
        ),
    )
    return db, monitor, offer


@pytest.mark.parametrize(
    "verb,kind",
    [("accept", "accept_offer"), ("decline", "decline_offer"), ("file", "send_artifact")],
)
def test_parser_accepts_only_explicit_command_and_signed_context(verb, kind):
    parsed = parse_command(
        WhatsAppText("one", PHONE, "/" + verb, datetime.now(UTC), "wamid.original"), **ACCOUNT
    )
    assert parsed.command.kind == kind and parsed.command.target_id is None
    assert parsed.reply_to_provider_ref == "wamid.original"
    assert (
        parse_command(WhatsAppText("one", PHONE, "yes, accept that", datetime.now(UTC)), **ACCOUNT)
        is None
    )


@pytest.mark.parametrize(
    "text",
    [
        "/accept",
        "/accept wrong-id",
        "/decline extra text",
        "/file",
        "/revise",
        "/revise " + "x" * 4001,
        "/unknown",
        "/accept " + "x" * 4096,
    ],
)
def test_invalid_commands_never_become_generic_messages(text):
    with pytest.raises(InvalidWhatsAppCommand):
        parse_command(WhatsAppText("one", PHONE, text, datetime.now(UTC)), **ACCOUNT)


def test_revision_parser_pins_explicit_target_and_complete_feedback():
    target = uuid4()
    parsed = parse_command(
        WhatsAppText(
            "one",
            PHONE,
            f"/revise {target} Clarify the comparison.\nRetain citations.",
            datetime.now(UTC),
        ),
        **ACCOUNT,
    )
    assert parsed.command.target_id == target
    assert parsed.command.instructions == "Clarify the comparison.\nRetain citations."


def test_signed_reply_acceptance_replay_and_changed_replay_never_create_generic_work(device):
    db, monitor, _ = dispatched_offer(device)
    api = client(db)
    message = event("/accept", context={"id": "wamid.command-offer"})
    before = counts(db)
    assert post(api, message).status_code == 200
    after = counts(db)
    assert after["responsibilities"] == before["responsibilities"] + 1
    assert after["user_messages"] == before["user_messages"]
    assert after["reply_tasks"] == before["reply_tasks"]
    assert post(api, message).status_code == 200 and counts(db) == after
    changed = {**message, "text": {"body": "/decline"}}
    assert post(api, changed).status_code == 200 and counts(db) == after
    assert (
        db.course_supervision_status("user_alice", monitor["id"])["offers"][0]["state"]
        == "accepted"
    )


@pytest.mark.parametrize(
    "mode",
    [
        "signature",
        "account",
        "number",
        "sender",
        "linked_sender",
        "context",
        "timestamp",
        "expired",
        "malformed_context",
    ],
)
def test_signed_identity_context_and_event_gates_cannot_accept_or_enqueue_chat(device, mode):
    db, _, _ = dispatched_offer(device)
    api = client(db)
    message = event("/accept", context={"id": "wamid.command-offer"})
    args = {}
    if mode == "signature":
        args["valid"] = False
    if mode == "account":
        args["business"] = "other"
    if mode == "number":
        args["number"] = "other"
    if mode == "sender":
        message["from"] = "15555550999"
    if mode == "linked_sender":
        other = "15555550999"
        db.provision("user_bob")
        challenge = db.create_whatsapp_challenge("user_bob")["message"]
        db.ingest_whatsapp(WhatsAppText("link-command-bob", other, challenge))
        message["from"] = other
    if mode == "context":
        message["context"] = {"id": "wamid.unrelated"}
    if mode == "malformed_context":
        message["context"] = {"id": 123}
    if mode == "timestamp":
        message.pop("timestamp")
    if mode == "expired":
        message["timestamp"] = str(int((datetime.now(UTC) - timedelta(days=2)).timestamp()))
    before = counts(db)
    response = post(api, message, **args)
    assert response.status_code == (403 if mode == "signature" else 200), response.text
    after = counts(db)
    for name in ("responsibilities", "tasks", "user_messages", "reply_tasks"):
        assert after[name] == before[name]


def test_invalid_command_does_not_drop_signed_delivery_status_sibling(device):
    db, _, _ = dispatched_offer(device)
    response = post(
        client(db),
        event("/accept wrong-target"),
        statuses=[
            {
                "id": "wamid.command-offer",
                "recipient_id": PHONE,
                "status": "delivered",
                "timestamp": str(int(datetime.now(UTC).timestamp())),
            }
        ],
    )
    assert response.status_code == 200
    with db.connection() as conn:
        assert (
            conn.execute(
                "SELECT state FROM wrytely_agent.whatsapp_outbound "
                "WHERE provider_ref='wamid.command-offer'"
            ).fetchone()["state"]
            == "delivered"
        )


@pytest.mark.parametrize("after_commit", [False, True])
def test_unexpected_command_failure_is_not_acknowledged_and_replay_is_safe(
    device, monkeypatch, after_commit
):
    db, _, offer = prepared(device)
    api = client(db)
    message = event(f"/accept {offer['id']}")
    execute = db.execute_whatsapp_command

    def fail(*args, **kwargs):
        if after_commit:
            execute(*args, **kwargs)
        raise RuntimeError("private persistence diagnostic")

    monkeypatch.setattr(db, "execute_whatsapp_command", fail)
    response = post(api, message)
    assert response.status_code == 503 and "private persistence" not in response.text
    monkeypatch.setattr(db, "execute_whatsapp_command", execute)
    assert post(api, message).status_code == 200
    with db.connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.responsibilities").fetchone()["n"]
            == 1
        )


def test_signed_file_and_revision_use_existing_owned_actions(device):
    db, artifact = prepared_file(device)
    api = client(db)
    first = event(f"/file {artifact['id']}", provider_id="file-command")
    assert post(api, first).status_code == 200
    assert post(api, first).status_code == 200
    before = counts(db)
    revise = event(f"/revise {artifact['id']} Clarify the title", provider_id="revision-command")
    assert post(api, revise).status_code == 200
    after = counts(db)
    assert after["tasks"] == before["tasks"] + 1
    assert after["reply_tasks"] == before["reply_tasks"]
    assert post(api, revise).status_code == 200 and counts(db) == after
    with db.connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.whatsapp_outbound").fetchone()[
                "n"
            ]
            == 1
        )
