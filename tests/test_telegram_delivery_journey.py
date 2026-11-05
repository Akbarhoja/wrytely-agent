"""Connected authenticated Telegram HTTP/Store/worker seams; all IO scripted."""

import httpx
from test_canvas_sync import device as device
from test_course_supervision_api import offer
from test_private_artifact_reads import ready
from test_source_connection_api import auth
from test_telegram_api import SECRET, TOKEN, client, update
from test_telegram_store import BOT

from app.telegram_worker import run_once
from integrations.telegram import TelegramAdapter


def connect(api):
    challenge = api.post("/v1/telegram/link", headers=auth()).json()
    assert callback(api, challenge["message"], 1)["state"] == "linked"
    prefs = dict(
        consent=True, notification_consent=False, timezone="UTC", quiet_start=0, quiet_end=0
    )
    assert api.post("/v1/telegram/preferences", json=prefs, headers=auth()).status_code == 200


def callback(api, text, number):
    # Exact replay includes the original event timestamp, not a new update body.
    if not hasattr(api, "synthetic_updates"):
        api.synthetic_updates = {}
    key = (text, number)
    if key not in api.synthetic_updates:
        event = update(text)
        event["update_id"] = number
        event["message"]["message_id"] = number
        api.synthetic_updates[key] = event
    event = api.synthetic_updates[key]
    reply = api.post(
        "/webhooks/telegram", json=event, headers={"X-Telegram-Bot-Api-Secret-Token": SECRET}
    )
    assert reply.status_code == 200 and reply.headers["cache-control"] == "no-store"
    return reply.json()


def test_http_acceptance_replay_uses_original_stable_work_intent(device):
    _, offer_row = offer(device)
    api = client(device)
    connect(api)
    text = f"/accept {offer_row['id']}"
    assert callback(api, text, 2) == {"state": "command_applied"}
    first = api.get("/v1/telegram", headers=auth()).json()["latest_command"]
    assert first["command_result"]["kind"] == "accept_offer"
    duty = first["command_result"]["result"]["responsibility_id"]
    assert callback(api, text, 2) == {"state": "duplicate"}
    assert callback(api, text, 3) == {"state": "command_applied"}
    second = api.get("/v1/telegram", headers=auth()).json()["latest_command"]
    assert second["command_result"]["result"]["responsibility_id"] == duty
    with device[0].connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.responsibilities").fetchone()["n"]
            == 1
        )


def test_http_file_and_revision_commands_recover_checked_transport_without_resend(device):
    _, artifact = ready(device)
    db = device[0]
    api = client(device)
    connect(api)
    text = f"/file {artifact['id']}"
    assert callback(api, text, 2) == {"state": "command_applied"}
    assert (
        api.get("/v1/telegram", headers=auth()).json()["latest_command"]["command_result"]["kind"]
        == "send_artifact"
    )
    calls = []

    def provider(request):
        calls.append((request.url.path.rsplit("/", 1)[-1], request.content))
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {
                    "message_id": len(calls) + 40,
                    "chat": {"id": 991, "type": "private"},
                    "from": {"id": BOT},
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(provider)) as http:
        adapter = TelegramAdapter(TOKEN, http)
        assert run_once(db, adapter, BOT) == "accepted"
        assert run_once(db, adapter, BOT) == "accepted"
        assert run_once(db, adapter, BOT) == "idle"
        assert [kind for kind, _ in calls] == ["sendDocument", "sendMessage"]
        assert b"PK" in calls[0][1]
        assert callback(api, text, 2) == {"state": "duplicate"}
        assert run_once(db, adapter, BOT) == "idle" and len(calls) == 2
        feedback = "PRIVATE synthetic feedback: keep the citation."
        assert callback(api, f"/revise {artifact['id']} {feedback}", 3) == {
            "state": "command_applied"
        }
        status = api.get("/v1/telegram", headers=auth()).json()
        assert status["latest_command"]["command_result"]["kind"] == "revise_artifact"
        assert feedback not in str(status)
        assert run_once(db, adapter, BOT) == "accepted"
        assert feedback.encode() not in calls[-1][1]
        assert run_once(db, adapter, BOT) == "idle"
    assert sum(kind == "sendDocument" for kind, _ in calls) == 1
