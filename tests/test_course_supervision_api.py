"""Real Store/HTTP acceptance of the session-bound one-course assembly."""

import pytest
from fastapi.testclient import TestClient
from test_canvas_sync import device as device
from test_course_supervision import Model, decision, setup
from test_source_connection_api import SessionVerifier, auth

from app.main import create_app
from runtime.supervisor import run_course_supervision_once
from shared.config import Settings

ROOT = "/v1/course-supervisions"


def client(device):
    return TestClient(
        create_app(Settings(_env_file=None), store=device[0], verifier=SessionVerifier())
    )


def checked(response, status=200):
    assert response.status_code == status, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def offer(device):
    db, monitor, obj = setup(device)
    run_course_supervision_once(db, Model(decision("inspect", obj)), "user_alice", monitor["id"])
    run_course_supervision_once(
        db, Model(decision("offer", obj, "Prepare a checked draft?")), "user_alice", monitor["id"]
    )
    status = db.course_supervision_status("user_alice", monitor["id"])
    return monitor, status["offers"][0]


def test_enable_status_replay_and_private_projection(device):
    db, monitor, _ = setup(device)
    body = {"connection_id": str(device[1]["connection_id"]), "course_id": "101"}
    api = client(device)
    first = checked(api.post(ROOT, json=body, headers=auth()))
    assert first["id"] == str(monitor["id"]) and first["call_limit"] == 6
    assert not {"lease_token", "inspections", "agent_id", "snapshot"} & first.keys()
    body["call_limit"] = 20
    again = checked(api.post(ROOT, json=body, headers=auth()))
    assert again["call_limit"] == 6
    assert checked(api.get(f"{ROOT}/{monitor['id']}", headers=auth())) == again


def test_accept_replays_exact_existing_draft_after_handoff_failure(device, monkeypatch):
    monitor, item = offer(device)
    api = client(device)
    path = f"{ROOT}/{monitor['id']}/offers/{item['id']}/decision"
    db = device[0]
    original = db.create_canvas_draft_responsibility

    def fail(*args, **kwargs):
        raise RuntimeError("private database diagnostic must not leak")

    monkeypatch.setattr(db, "create_canvas_draft_responsibility", fail)
    failed = checked(api.post(path, json={"accept": True}, headers=auth()), 503)
    assert "private database" not in str(failed)
    monkeypatch.setattr(db, "create_canvas_draft_responsibility", original)
    accepted = checked(api.post(path, json={"accept": True}, headers=auth()))
    assert accepted["state"] == "accepted" and accepted["responsibility_id"]
    assert checked(api.post(path, json={"accept": True}, headers=auth())) == accepted
    with db.connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.responsibilities").fetchone()["n"]
            == 1
        )


def test_decline_creates_no_draft_and_pause_blocks_acceptance(device):
    monitor, item = offer(device)
    api = client(device)
    path = f"{ROOT}/{monitor['id']}"
    checked(api.post(path + "/pause", headers=auth()))
    checked(
        api.post(path + f"/offers/{item['id']}/decision", json={"accept": True}, headers=auth()),
        409,
    )
    with device[0].connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.responsibilities").fetchone()["n"]
            == 0
        )


@pytest.mark.parametrize("who,code", [(None, 401), ("invalid", 401), ("bob", 404)])
def test_identity_fences_all_existing_resource_routes(device, who, code):
    monitor, item = offer(device)
    device[0].provision("user_bob")
    api = client(device)
    headers = {} if who is None else auth(who)
    path = f"{ROOT}/{monitor['id']}"
    checked(api.get(path, headers=headers), code)
    checked(api.post(path + "/pause", headers=headers), code)
    checked(
        api.post(path + f"/offers/{item['id']}/decision", json={"accept": True}, headers=headers),
        code,
    )


@pytest.mark.parametrize(
    "payload",
    [{"accept": "true"}, {"accept": 1}, {}, {"accept": True, "verified_user": "user_bob"}],
)
def test_decision_requires_explicit_boolean_and_no_caller_identity(device, payload):
    monitor, item = offer(device)
    checked(
        client(device).post(
            f"{ROOT}/{monitor['id']}/offers/{item['id']}/decision", json=payload, headers=auth()
        ),
        422,
    )


def test_pause_available_after_disconnect_and_rejects_unknown_parameters(device):
    db, monitor, _ = setup(device)
    api = client(device)
    path = f"{ROOT}/{monitor['id']}/pause"
    checked(api.post(path + "?user_id=user_bob", headers=auth()), 400)
    checked(api.post(path, json={"verified_user": "user_bob"}, headers=auth()), 400)
    db.rotate_or_revoke("user_alice", device[1]["connection_id"])
    assert checked(api.post(path, headers=auth()))["state"] == "paused"


def test_decline_and_strict_enable_inputs(device):
    monitor, item = offer(device)
    api = client(device)
    path = f"{ROOT}/{monitor['id']}/offers/{item['id']}/decision"
    result = checked(api.post(path, json={"accept": False}, headers=auth()))
    assert result == {"state": "declined", "responsibility_id": None}
    checked(api.post(path, json={"accept": True}, headers=auth()), 400)
    body = {"connection_id": str(device[1]["connection_id"]), "course_id": "101"}
    for fields in ({"call_limit": True}, {"call_limit": 21}, {"verified_user": "user_bob"}):
        checked(api.post(ROOT, json={**body, **fields}, headers=auth()), 422)
    checked(api.post(ROOT, json=body), 401)
    device[0].provision("user_bob")
    checked(api.post(ROOT, json=body, headers=auth("bob")), 404)
    with device[0].connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.responsibilities").fetchone()["n"]
            == 0
        )


def test_proactive_opt_in_and_queue_are_session_owned_and_idempotent(device):
    from test_course_offer_delivery import prepared

    db, monitor, item = prepared(device, consent=False)
    api = client(device)
    root = f"{ROOT}/{monitor['id']}"
    path = root + f"/offers/{item['id']}/delivery"
    checked(api.post(path, headers=auth()), 400)
    checked(api.post(root + "/notifications", json={"consent": "true"}, headers=auth()), 422)
    db.provision("user_bob")
    checked(api.post(root + "/notifications", json={"consent": True}, headers=auth("bob")), 404)
    checked(api.post(root + "/notifications", json={"consent": True}, headers=auth()))
    assert checked(api.get(root, headers=auth()))["notification_consent"] is True
    first = checked(api.post(path, headers=auth()))
    assert checked(api.post(path, headers=auth())) == first
    checked(api.post(path, json={"recipient": "15555550999"}, headers=auth()), 400)
    checked(api.post(path, headers=auth("bob")), 404)
    checked(api.post(root + "/notifications", json={"consent": False}, headers=auth()))
    with db.connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.whatsapp_outbound").fetchone()[
                "n"
            ]
            == 1
        )
