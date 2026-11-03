"""Actual checked document download/revision over session HTTP and real Store."""

import hashlib
import io
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from test_canvas_sync import device as device
from test_private_artifact_reads import ready
from test_source_connection_api import SessionVerifier, auth

from app.main import create_app
from shared.config import Settings


def client(device):
    return TestClient(
        create_app(Settings(_env_file=None), store=device[0], verifier=SessionVerifier())
    )


def test_checked_file_download_is_private_immutable_docx(device):
    _, saved = ready(device)
    api = client(device)
    path = f"/v2/artifacts/{saved['id']}/file"
    response = api.get(path, headers=auth())
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-artifact-sha256"] == hashlib.sha256(response.content).hexdigest()
    assert response.headers["content-disposition"].endswith('.docx"')
    assert api.get(path, headers=auth()).content == response.content
    with ZipFile(io.BytesIO(response.content)) as archive:
        assert b"w:document" in archive.read("word/document.xml")
    device[0].provision("user_bob")
    for headers, code in [({}, 401), (auth("invalid"), 401), (auth("bob"), 404)]:
        rejected = api.get(path, headers=headers)
        assert rejected.status_code == code
        assert rejected.headers["cache-control"] == "no-store"
        assert not rejected.content.startswith(b"PK")
    device[0].set_paused("user_alice", True)
    assert api.get(path, headers=auth()).status_code == 409


def test_revision_is_explicit_private_and_replays_existing_task(device):
    _, saved = ready(device)
    api = client(device)
    path = f"/v2/artifacts/{saved['id']}/revisions"
    body = {"instructions": "Clarify the title", "request_key": "revision-one"}
    first = api.post(path, json=body, headers=auth())
    assert first.status_code == 200, first.text
    assert first.headers["cache-control"] == "no-store"
    assert api.post(path, json=body, headers=auth()).json() == first.json()
    assert (
        api.post(
            path, json={**body, "instructions": "Different change"}, headers=auth()
        ).status_code
        == 409
    )
    device[0].provision("user_bob")
    assert api.post(path, json=body, headers=auth("bob")).status_code == 404
    assert (
        api.post(path, json={**body, "verified_user": "user_bob"}, headers=auth()).status_code
        == 422
    )
    assert (
        api.post(path, json={**body, "instructions": "x" * 4001}, headers=auth()).status_code == 422
    )
    assert api.post(path, json=body).status_code == 401


def test_file_delivery_requires_explicit_owner_request_without_caller_payload(device):
    from test_artifact_delivery import prepared_file

    db, saved = prepared_file(device)
    api = client(device)
    path = f"/v2/artifacts/{saved['id']}/delivery"
    first = api.post(path, headers=auth())
    assert first.status_code == 200, first.text
    assert first.headers["cache-control"] == "no-store"
    assert api.post(path, headers=auth()).json() == first.json()
    db.provision("user_bob")
    assert api.post(path, headers=auth("bob")).status_code == 404
    assert api.post(path, json={"recipient": "15555550999"}, headers=auth()).status_code == 400
    assert api.post(path).status_code == 401
    with db.connection() as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.whatsapp_outbound").fetchone()[
                "n"
            ]
            == 1
        )


@pytest.mark.parametrize("suffix", ["file", "revisions"])
def test_result_database_errors_are_private(device, monkeypatch, suffix):
    def fail(*args, **kwargs):
        raise RuntimeError("private diagnostic")

    db = device[0]
    monkeypatch.setattr(
        db,
        "read_private_artifact_v2" if suffix == "file" else "request_private_artifact_revision",
        fail,
    )
    path = "/v2/artifacts/00000000-0000-4000-8000-000000000001/" + suffix
    api = client(device)
    response = (
        api.get(path, headers=auth())
        if suffix == "file"
        else api.post(path, json={"instructions": "Clarify", "request_key": "one"}, headers=auth())
    )
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert "private diagnostic" not in response.text
