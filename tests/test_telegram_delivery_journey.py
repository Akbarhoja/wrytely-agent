"""Connected authenticated Telegram HTTP/Store/worker seams; all IO scripted."""

from copy import deepcopy
from email import policy
from email.parser import BytesParser
from hashlib import sha256

import httpx
import pytest
from test_artifacts import assessment
from test_canvas_sync import device as device
from test_course_supervision_api import offer
from test_drafting import permitted, structured
from test_private_artifact_reads import ready
from test_source_connection_api import auth
from test_telegram_api import SECRET, TOKEN, client, update
from test_telegram_store import BOT
from test_worker import ScriptedModel

from app.telegram_worker import run_once
from integrations.telegram import TelegramAdapter
from runtime.worker import run_once as work_once
from shared.config import Settings
from shared.db import Store


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
    data, artifact = ready(device)
    db = device[0]
    api = client(device)
    connect(api)
    original = api.get(f"/v2/artifacts/{artifact['id']}/file", headers=auth())
    assert original.status_code == 200 and original.headers["cache-control"] == "no-store"
    assert original.headers["x-artifact-sha256"] == sha256(original.content).hexdigest()
    text = f"/file {artifact['id']}"
    assert callback(api, text, 2) == {"state": "command_applied"}
    assert (
        api.get("/v1/telegram", headers=auth()).json()["latest_command"]["command_result"]["kind"]
        == "send_artifact"
    )
    calls = []

    def provider(request):
        kind = request.url.path.rsplit("/", 1)[-1]
        content = request.content
        if kind == "sendDocument":
            message = BytesParser(policy=policy.default).parsebytes(
                f"Content-Type: {request.headers['content-type']}\r\n\r\n".encode() + content
            )
            files = [part for part in message.iter_parts() if part.get_filename()]
            assert len(files) == 1
            content = files[0].get_payload(decode=True)
        calls.append((kind, content))
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
        assert calls[0][1] == original.content
        assert callback(api, text, 2) == {"state": "duplicate"}
        assert run_once(db, adapter, BOT) == "idle" and len(calls) == 2
        feedback = "PRIVATE synthetic feedback: keep the citation."
        assert callback(api, f"/revise {artifact['id']} {feedback}", 3) == {
            "state": "command_applied"
        }
        status = api.get("/v1/telegram", headers=auth()).json()
        assert status["latest_command"]["command_result"]["kind"] == "revise_artifact"
        revision = status["latest_command"]["command_result"]["result"]
        assert feedback not in str(status)
        assert run_once(db, adapter, BOT) == "accepted"
        assert feedback.encode() not in calls[-1][1]
        assert run_once(db, adapter, BOT) == "idle"

        revised = deepcopy(data[3])
        revised["title"] = "Revised synthetic comparison"
        model = ScriptedModel([permitted(), structured("save_review_draft", revised), assessment()])
        db.set_paused("user_alice", True)
        assert not work_once(db, model, Settings()) and model.histories == []
        paused = api.get(f"/v2/artifacts/{artifact['id']}/file", headers=auth())
        assert paused.status_code == 409 and not paused.content.startswith(b"PK")
        db.set_paused("user_alice", False)
        assert work_once(db, model, Settings())
        assert feedback in str(model.histories)
        with db.connection() as conn:
            versions = conn.execute(
                "SELECT * FROM wrytely_agent.artifacts ORDER BY created_at"
            ).fetchall()
        assert len(versions) == 2 and versions[0]["draft"] == artifact["draft"]
        latest = versions[1]
        assert latest["id"] != artifact["id"] and str(latest["task_id"]) == revision["task_id"]
        assert latest["state"] == "ready" and latest["draft"] == revised
        detail = db.read_private_artifact_v2("user_alice", latest["id"])
        assert detail["latest_check"]["report"]["passed"] is True
        assert detail["evidence_status"]["state"] == "current"
        updated = api.get(f"/v2/artifacts/{latest['id']}/file", headers=auth())
        assert updated.status_code == 200 and updated.headers["cache-control"] == "no-store"
        assert updated.headers["x-artifact-sha256"] == sha256(updated.content).hexdigest()
        assert updated.content != original.content
        assert (
            api.get(f"/v2/artifacts/{artifact['id']}/file", headers=auth()).content
            == original.content
        )

        revised_command = f"/revise {artifact['id']} {feedback}"
        assert callback(api, revised_command, 3) == {"state": "duplicate"}
        assert not work_once(db, model, Settings())
        text_v2 = f"/file {latest['id']}"
        assert callback(api, text_v2, 4) == {"state": "command_applied"}
        restarted = Store(db._url, canvas_origins=tuple(db._canvas_origins))
        assert run_once(restarted, adapter, BOT) == "accepted"
        assert run_once(restarted, adapter, BOT) == "accepted"
        assert run_once(restarted, adapter, BOT) == "idle"
        assert [content for kind, content in calls if kind == "sendDocument"] == [
            original.content,
            updated.content,
        ]
        assert callback(api, text_v2, 4) == {"state": "duplicate"}
        count = len(calls)
        assert run_once(restarted, adapter, BOT) == "idle" and len(calls) == count
    assert sum(kind == "sendDocument" for kind, _ in calls) == 2


@pytest.mark.parametrize("control", ["pause", "unlink", "source_revoked"])
def test_http_file_request_rechecks_controls_before_transport(device, control):
    _, artifact = ready(device)
    db = device[0]
    api = client(device)
    connect(api)
    assert callback(api, f"/file {artifact['id']}", 2) == {"state": "command_applied"}
    if control == "pause":
        db.set_paused("user_alice", True)
    elif control == "unlink":
        assert api.post("/v1/telegram/unlink", headers=auth()).status_code == 200
    else:
        db.rotate_or_revoke("user_alice", device[1]["connection_id"])
    calls = []

    def provider(request):
        calls.append(request.url.path.rsplit("/", 1)[-1])
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {
                    "message_id": 50,
                    "chat": {"id": 991, "type": "private"},
                    "from": {"id": BOT},
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(provider)) as http:
        adapter = TelegramAdapter(TOKEN, http)
        assert run_once(db, adapter, BOT) in {"cancelled", "idle"}
        assert run_once(db, adapter, BOT) in {"accepted", "cancelled", "idle"}
    # A revoked source cancels the file, but not the fixed command acknowledgment.
    assert calls == (["sendMessage"] if control == "source_revoked" else [])
