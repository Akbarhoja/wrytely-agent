"""Session-bound result HTTP over published synthetic documents and real Store."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_canvas_sync import device as device
from test_private_artifact_reads import result as result
from test_source_connection_api import SessionVerifier, auth

from app.main import create_app
from app.private_artifact_api import _decode_cursor, _encode_cursor
from shared.canvas_reads import SourceRefreshRequired
from shared.config import Settings
from shared.private_artifact_projection import PrivateArtifactReadLimit


def client(device):
    return TestClient(
        create_app(Settings(_env_file=None), store=device[0], verifier=SessionVerifier())
    )


def checked(response, code=200):
    assert response.status_code == code, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def paths(result):
    artifact = result[1]
    return (
        f"/v2/responsibilities/{artifact['responsibility_id']}/artifacts",
        f"/v2/artifacts/{artifact['id']}",
        f"/v2/artifacts/{artifact['id']}/evidence/citation/0",
    )


def test_real_result_list_detail_and_original_and_old_routes_stay_separate(device, result):
    api = client(device)
    listing, detail, original = paths(result)
    rows = checked(api.get(listing, headers=auth()))
    assert rows["schema_version"] == 2 and rows["next"] is None
    assert rows["artifacts"][0]["id"] == str(result[1]["id"])
    draft = checked(api.get(detail, headers=auth()))
    assert draft["latest_check"]["report"]["passed"]
    source = checked(api.get(original, headers=auth()))
    assert source["quote_matches"]
    assert source["reference"] == draft["artifact"]["draft"]["citations"][0]["evidence"]
    checked(api.get(detail.replace("/v2/", "/v1/"), headers=auth()), 404)


@pytest.mark.parametrize("who,status", [(None, 401), ("bob", 404), ("invalid", 401)])
def test_all_reads_reject_other_users_and_non_sessions(device, result, who, status):
    device[0].provision("user_bob")
    for path in paths(result):
        checked(client(device).get(path, headers={} if who is None else auth(who)), status)


@pytest.mark.parametrize(
    "path,suffix",
    [
        (0, "?limit=0"),
        (0, "?limit=51"),
        (0, "?limit=true"),
        (0, "?limit=1&limit=2"),
        (0, "?before=wrong"),
        (0, "?before=" + "a" * 513),
        (1, "?user_id=private-owner"),
        (2, "?source_id=private-source"),
        (2, "?first_slot=-1"),
        (2, "?limit=0"),
        (2, "?limit=1&limit=2"),
        (2, "?check_id=not-a-uuid"),
    ],
)
def test_strict_query_bounds_no_echo(device, result, path, suffix):
    response = client(device).get(paths(result)[path] + suffix, headers=auth())
    checked(response, 400)
    assert "private-owner" not in response.text and "private-source" not in response.text


def test_invalid_path_and_unknown_ids_are_private(device):
    api = client(device)
    checked(api.get("/v2/artifacts/invalid", headers=auth()), 400)
    device[0].provision("user_alice")
    checked(api.get(f"/v2/artifacts/{uuid4()}", headers=auth()), 404)


@pytest.mark.parametrize(
    "failure,status",
    [
        (PrivateArtifactReadLimit("private text"), 413),
        (SourceRefreshRequired(), 409),
        (KeyError("private text"), 503),
        (RuntimeError("private text"), 503),
    ],
)
def test_controlled_failures_no_echo_or_retry(device, monkeypatch, failure, status):
    calls = []

    def fail(*args, **kwargs):
        calls.append(True)
        raise failure

    monkeypatch.setattr(device[0], "read_private_artifact_v2", fail)
    response = client(device).get(f"/v2/artifacts/{uuid4()}", headers=auth())
    checked(response, status)
    assert calls == [True] and "private text" not in response.text


def test_cursor_roundtrip_is_bounded_canonical_and_not_a_capability():
    value = {"created_at": "2026-11-01T00:00:00+00:00", "id": str(uuid4())}
    encoded = _encode_cursor(value)
    assert len(encoded) <= 512 and _decode_cursor(encoded) == value
    for invalid in [encoded + "=", "!", "", _encode_cursor(value | {"user": "alice"})]:
        with pytest.raises(ValueError):
            _decode_cursor(invalid)


def test_http_pagination_roundtrips_cursor_without_skips_or_other_account_access(device, result):
    row = result[1]
    identifiers = [str(row["id"])]
    with device[0].connection() as conn:
        for index in range(3):
            identifier = uuid4()
            identifiers.append(str(identifier))
            conn.execute(
                "INSERT INTO wrytely_agent.artifacts SELECT %s,agent_id,responsibility_id,task_id,"
                "%s,memory_revision,draft,state,created_at,document_citations,evidence_schema "
                "FROM wrytely_agent.artifacts WHERE id=%s",
                (identifier, "http-page-" + str(index), row["id"]),
            )
    api = client(device)
    device[0].provision("user_bob")
    before, seen = None, []
    for _ in range(4):
        params = {"limit": "1", **({"before": before} if before else {})}
        page = checked(api.get(paths(result)[0], params=params, headers=auth()))
        seen.extend(item["id"] for item in page["artifacts"])
        before = page["next"]
        if before is None:
            break
        assert isinstance(before, str) and len(before) <= 512
        checked(api.get(paths(result)[0], params={"before": before}, headers=auth("bob")), 404)
    assert seen == sorted(identifiers, reverse=True) and before is None


def test_saved_policy_requires_exact_check_and_invalid_reference_never_widens_scope(device, result):
    api = client(device)
    detail = checked(api.get(paths(result)[1], headers=auth()))
    path = paths(result)[2].replace("citation/0", "policy/0")
    checked(api.get(path, headers=auth()), 400)
    check_id = detail["latest_check"]["id"]
    value = checked(api.get(path, params={"check_id": check_id}, headers=auth()))
    assert value["quote_matches"]
    checked(api.get(path, params={"check_id": str(uuid4())}, headers=auth()), 404)


def test_disconnect_hides_embedded_quotes_not_just_originals(device, result):
    connection = device[1]["connection_id"]
    device[0].rotate_or_revoke("user_alice", connection)
    api = client(device)
    listing, detail, original = paths(result)
    assert checked(api.get(listing, headers=auth()))["artifacts"]
    checked(api.get(detail, headers=auth()), 409)
    checked(api.get(original, headers=auth()), 409)
