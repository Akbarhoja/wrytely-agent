"""Actual session/callback Telegram assembly, no provider calls."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from test_canvas_sync import device as device
from test_source_connection_api import SessionVerifier, auth

from app.main import create_app
from shared.config import Settings

TOKEN = "123456789:" + "a" * 35
SECRET = "s" * 40


def client(device):
    device[0].provision("user_alice")
    return TestClient(
        create_app(
            Settings(
                _env_file=None,
                telegram_bot_token=TOKEN,
                telegram_webhook_secret=SECRET,
                telegram_bot_username="wrytely_agent_bot",
            ),
            store=device[0],
            verifier=SessionVerifier(),
        )
    )


def update(text):
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "date": int(datetime.now(UTC).timestamp()),
            "chat": {"id": 991, "type": "private"},
            "from": {"id": 991, "is_bot": False},
            "text": text,
        },
    }


def test_private_pair_callback_and_preferences(device):
    api = client(device)
    assert api.get("/v1/telegram").status_code == 401
    challenge = api.post("/v1/telegram/link", headers=auth())
    assert challenge.status_code == 200 and challenge.headers["cache-control"] == "no-store"
    headers = {"X-Telegram-Bot-Api-Secret-Token": SECRET}
    event = update(challenge.json()["message"])
    assert api.post("/webhooks/telegram", json=event, headers=headers).json() == {"state": "linked"}
    assert api.post("/webhooks/telegram", json=event, headers=headers).json() == {
        "state": "duplicate"
    }
    state = api.get("/v1/telegram", headers=auth()).json()
    assert state["linked"] and state["preferences"]["consent"] is False
    assert state["preferences"]["notification_consent"] is False
    assert not {"chat_id", "generation", "token"} & state.keys()
    prefs = dict(
        consent=True, notification_consent=False, timezone="UTC", quiet_start=0, quiet_end=0
    )
    assert api.post("/v1/telegram/preferences", json=prefs, headers=auth()).status_code == 200
    assert (
        api.post("/v1/telegram/link", json={"user_id": "user_bob"}, headers=auth()).status_code
        == 400
    )
    assert api.get("/v1/telegram?bot_id=1", headers=auth()).status_code == 400
    assert api.post("/v1/telegram/unlink", headers=auth()).json() == {"linked": False}
    assert api.get("/v1/telegram", headers=auth()).json()["linked"] is False
    assert device[0].messages("user_alice") == []


def test_callback_authentication_precedes_body_and_duplicates_rejected(device):
    api = client(device)
    bad = api.post("/webhooks/telegram", content=b"not json" * 20000)
    assert bad.status_code == 401 and bad.headers["cache-control"] == "no-store"
    dup = [("X-Telegram-Bot-Api-Secret-Token", SECRET)] * 2
    assert api.post("/webhooks/telegram", json={}, headers=dup).status_code == 401
    assert (
        api.post(
            "/webhooks/telegram",
            content=b"x" * 65537,
            headers={"X-Telegram-Bot-Api-Secret-Token": SECRET, "Content-Type": "application/json"},
        ).status_code
        == 413
    )
    assert (
        api.post(
            "/webhooks/telegram",
            content=b"{bad",
            headers={"X-Telegram-Bot-Api-Secret-Token": SECRET, "Content-Type": "application/json"},
        ).status_code
        == 400
    )


@pytest.mark.parametrize(
    "field,value",
    [("consent", "true"), ("timezone", "not/a-zone"), ("quiet_start", 24), ("user_id", "user_bob")],
)
def test_preferences_strict_and_no_owner_input(device, field, value):
    api = client(device)
    body = dict(
        consent=False, notification_consent=False, timezone="UTC", quiet_start=0, quiet_end=0
    )
    body[field] = value
    assert api.post("/v1/telegram/preferences", json=body, headers=auth()).status_code == 422
