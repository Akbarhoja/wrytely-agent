"""Actual existing session routes expose preparation without new action authority."""

from test_canvas_sync import device as device
from test_course_supervision import prepared_course
from test_course_supervision_api import ROOT, checked, client
from test_source_connection_api import auth


def test_preparation_status_and_lookup_are_private_read_only_projections(device):
    db, monitor, _, _ = prepared_course(device)
    api = client(device)
    path = f"{ROOT}/{monitor['id']}"
    first = checked(api.get(path, headers=auth()))
    record = first["preparations"][0]
    assert record["kind"] == "preparation_checklist" and record["current"]
    assert record["evidence"][0]["missing"] == ["linked_content_unread"]
    assert "not a completed or checked assignment" in record["notice"]
    assert not {"lease_token", "inspections", "agent_id", "snapshot"} & first.keys()
    query = {"connection_id": str(device[1]["connection_id"]), "course_id": "101"}
    found = checked(api.get(ROOT, params=query, headers=auth()))["supervision"]
    assert found["preparations"] == [record] and found["calls_reserved"] == 2
    assert checked(api.get(path, headers=auth()))["calls_reserved"] == 2
    assert first["offers"] == []
    with db.connection() as conn:
        for table in ["responsibilities", "artifacts", "whatsapp_outbound"]:
            assert (
                conn.execute(f"SELECT count(*) AS n FROM wrytely_agent.{table}").fetchone()["n"]
                == 0
            )
    db.provision("user_bob")
    checked(api.get(path, headers=auth("bob")), 404)
    checked(api.get(ROOT, params=query, headers=auth("bob")), 404)
    checked(api.get(path), 401)
    checked(api.get(path, params={"verified_user": "user_bob"}, headers=auth()), 400)
    checked(api.get(ROOT, params={**query, "verified_user": "user_bob"}, headers=auth()), 400)


def test_pause_retains_history_without_current_or_draft_authority(device):
    _, monitor, _, _ = prepared_course(device)
    api = client(device)
    path = f"{ROOT}/{monitor['id']}"
    before = checked(api.get(path, headers=auth()))["preparations"][0]
    checked(api.post(path + "/pause", headers=auth()))
    status = checked(api.get(path, headers=auth()))
    after = status["preparations"][0]
    assert status["state"] == "paused" and after["current"] is False
    assert after["id"] == before["id"] and after["excerpts"] == before["excerpts"]
    assert status["offers"] == [] and status["calls_reserved"] == 2
