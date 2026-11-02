"""Real owned coverage: metadata survives revoke, content never leaks through it."""

import pytest
import test_canvas_evidence as evidence
import test_canvas_sync as sync
from test_canvas_sync import device as device
from test_source_connection_api import auth, client_for

ROOT = "/v1/source-connections"


def test_private_course_coverage_is_owned_and_does_not_confuse_empty_or_open_with_complete(device):
    db, linked = device
    evidence.prepare(device, kinds=["assignments"])
    client = client_for(db)
    path = f"{ROOT}/{linked['connection_id']}/canvas/coverage"
    response = client.get(path, headers=auth())
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    view = response.json()
    assert view["connection"]["state"] == "connected"
    assert view["scan"]["state"] == "active"
    assert view["courses"][0]["title"] == "Synthetic course"
    assert view["courses"][0]["selected"] is True
    assert view["courses"][0]["resources"] == [
        {
            "kind": "assignments",
            "coverage": "open",
            "reason": None,
            "items_seen": 0,
            "retained_items": 0,
            "incomplete_items": 0,
        }
    ]
    assert "ingestion_bearer" not in response.text and sync.SUBJECT not in response.text
    assert client.get(path, headers=auth("bob")).status_code == 404
    assert client.get(path).status_code == 401
    db.rotate_or_revoke("user_alice", linked["connection_id"])
    view = client.get(path, headers=auth()).json()
    assert view["connection"]["state"] == "disconnected"
    assert view["scan"]["state"] in ("aborted", "not_started")


@pytest.mark.parametrize(
    "query", ["?user_id=bob", "?limit=1&limit=2", "?limit=0", "?limit=51", "?after=../101"]
)
def test_coverage_rejects_unscoped_or_unbounded_queries(device, query):
    db, linked = device
    response = client_for(db).get(
        f"{ROOT}/{linked['connection_id']}/canvas/coverage{query}", headers=auth()
    )
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"


def test_setup_list_and_strict_pagination_are_session_owned(device):
    db, linked = device
    client = client_for(db)
    assert client.get(ROOT + "/canvas/setup", headers=auth()).json() == {
        "origins": [sync.ORIGIN],
        "configured": True,
    }
    assert (
        client.get(ROOT, headers=auth()).json()["connections"][0]["connection_id"]
        == linked["connection_id"]
    )
    assert client.get(ROOT, headers=auth("bob")).json()["connections"] == []
    assert client.get(ROOT + "?user_id=bob", headers=auth()).status_code == 400
    assert (
        client.get(ROOT + "?cursor=" + linked["connection_id"], headers=auth("bob")).status_code
        == 404
    )
