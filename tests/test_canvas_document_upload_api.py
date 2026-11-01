"""Private staging HTTP against real disposable Store; no source/provider IO."""

import asyncio
from copy import deepcopy
from uuid import uuid4

import pytest
import test_canvas_evidence as evidence
import test_canvas_sync as sync
from fastapi.testclient import TestClient
from test_canvas_document_uploads import begin_body, count, finish_body, put_body
from test_canvas_sync import device as device
from test_source_connection_api import SessionVerifier

from app.main import create_app
from shared.canvas_document_uploads import CanvasDocumentUploadLimited
from shared.canvas_sync import CanvasSyncConflict
from shared.config import Settings
from shared.db import Store

ROOT = "/v1/source-connections/canvas/documents"


def client_for(device, *, versions=("fixture.v1",), origins=(sync.ORIGIN,)):
    return TestClient(
        create_app(
            Settings(_env_file=None, canvas_origins=list(origins)),
            store=device[0],
            verifier=SessionVerifier(),
            canvas_document_extractors=versions,
        )
    )


def post(client, device, path, body, **kwargs):
    return client.post(
        ROOT + path,
        json=body,
        headers={"Authorization": "Bearer " + device[1]["ingestion_bearer"]},
        **kwargs,
    )


def checked(response, status=200):
    assert response.status_code == status, response.text
    assert response.headers["Cache-Control"] == "no-store"
    return response.json() if response.content else None


def test_real_staging_and_recreated_app_replays_original_receipts(device):
    client = client_for(device)
    body = begin_body(device, evidence.prepare(device))
    started = checked(post(client, device, "/begin", body))
    parts = put_body(body, started["upload_id"])
    saved = checked(post(client, device, "/parts", parts))
    finish = finish_body(body, started["upload_id"])
    ready = checked(post(client, device, "/finish", finish))
    assert started["received_slots"] == [] and saved["received_slots"] == [0]
    assert ready["ready"] and not ready["replayed"]
    restarted = (Store(device[0]._url, canvas_origins=(sync.ORIGIN,)), device[1])
    for path, request, receipt in (
        ("/begin", body, started),
        ("/parts", parts, saved),
        ("/finish", finish, ready),
    ):
        assert checked(post(client_for(restarted), restarted, path, request)) == {
            **receipt,
            "replayed": True,
        }
    assert count(device, "canvas_document_upload_receipts") == 3
    assert count(device, "source_versions") == count(device, "canvas_evidence_observations") == 0
    changed = deepcopy(body)
    changed["metadata"]["title"] = "Changed synthetic title"
    assert checked(post(client, device, "/begin", changed), 409) == {
        "detail": {"code": "document_conflict"}
    }


@pytest.mark.parametrize("versions,origins", [((), (sync.ORIGIN,)), (("fixture.v1",), ())])
def test_disabled_without_trusted_configuration(device, versions, origins):
    body = begin_body(device, evidence.prepare(device))
    checked(
        post(client_for(device, versions=versions, origins=origins), device, "/begin", body), 503
    )
    assert count(device, "canvas_document_uploads") == 0


def test_factory_default_is_off(device):
    client = TestClient(
        create_app(
            Settings(_env_file=None, canvas_origins=[sync.ORIGIN]),
            store=device[0],
            verifier=SessionVerifier(),
        )
    )
    checked(post(client, device, "/begin", begin_body(device, evidence.prepare(device))), 503)


@pytest.mark.parametrize(
    "versions",
    [
        ["fixture.v1"],
        "fixture.v1",
        ("",),
        ("x\r\ny",),
        ("e\u0301",),
        ("x" * 65,),
        (1,),
        ("\ud800",),
    ],
)
def test_invalid_server_configuration_is_rejected_without_echo(versions):
    with pytest.raises(ValueError, match="^Invalid Canvas document extractor configuration$"):
        client_for((None, None), versions=versions)


@pytest.mark.parametrize(
    "credential", [None, "Basic alice", "Bearer alice", "Bearer bob", "Bearer invalid"]
)
def test_ingestion_only_credentials(device, credential):
    client = client_for(device)
    response = client.post(
        ROOT + "/begin",
        json=begin_body(device, evidence.prepare(device)),
        headers={} if credential is None else {"Authorization": credential},
    )
    checked(response, 401)
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert count(device, "canvas_document_uploads") == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("operation", "finish_document"),
        ("schema_version", True),
        ("schema_version", "2"),
        ("user_id", "private-owner"),
        ("canvas_document_extractors", ["fixture.v1"]),
        ("subject", "other-subject"),
        ("generation", 999),
    ],
)
def test_exact_body_and_current_identity(device, field, value):
    body = begin_body(device, evidence.prepare(device)) | {field: value}
    status = 409 if field in {"subject", "generation"} else 400
    response = post(client_for(device), device, "/begin", body)
    checked(response, status)
    assert "private-owner" not in response.text
    assert count(device, "canvas_document_uploads") == 0


@pytest.mark.parametrize(
    "content,media,status",
    [
        (b"{", "application/json", 400),
        (b"[]", "application/json", 400),
        (b"null", "application/json", 400),
        (b"{}", "text/plain", 415),
        (b" " * (1024 * 1024 + 1), "application/json", 413),
    ],
)
def test_raw_boundary_is_bounded_and_redacted(device, content, media, status):
    response = client_for(device).post(
        ROOT + "/begin",
        content=content,
        headers={
            "Authorization": "Bearer " + device[1]["ingestion_bearer"],
            "Content-Type": media,
        },
    )
    checked(response, status)


def test_chunked_limit_and_query_rejected(device):
    client = client_for(device)
    response = client.post(
        ROOT + "/begin",
        content=iter([b" " * 600000, b" " * 600000]),
        headers={"Content-Type": "application/json"},
    )
    checked(response, 413)
    checked(
        post(client, device, "/begin?owner=private", begin_body(device, evidence.prepare(device))),
        400,
    )


def test_raw_asgi_limit_ignores_false_length_and_does_not_read_remainder():
    api = create_app(Settings(_env_file=None), verifier=SessionVerifier())
    delivered = []
    messages = []
    chunks = [b" " * 600000, b" " * 600000, b"unread-private-remainder"]

    async def receive():
        index = len(delivered)
        delivered.append(index)
        return {"type": "http.request", "body": chunks[index], "more_body": True}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": ROOT + "/begin",
        "root_path": "",
        "query_string": b"",
        "server": ("test", 80),
        "client": ("test", 1234),
        "headers": [(b"content-type", b"application/json"), (b"content-length", b"1")],
    }
    asyncio.run(api(scope, receive, send))
    assert delivered == [0, 1]
    assert messages[0]["status"] == 413
    assert (b"cache-control", b"no-store") in messages[0]["headers"]
    assert b"private" not in messages[1]["body"]


@pytest.mark.parametrize("path,builder", [("/parts", put_body), ("/finish", finish_body)])
def test_unknown_upload_is_empty_404(device, path, builder):
    body = begin_body(device, evidence.prepare(device))
    response = post(client_for(device), device, path, builder(body, str(uuid4())))
    checked(response, 404)
    assert response.content == b""


def test_replay_rechecks_current_lease(device):
    client = client_for(device)
    body = begin_body(device, evidence.prepare(device))
    checked(post(client, device, "/begin", body))
    with device[0].connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.canvas_scans SET "
            "lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
            (body["scan_id"],),
        )
    assert checked(post(client, device, "/begin", body), 409) == {
        "detail": {"code": "lease_expired"}
    }


@pytest.mark.parametrize(
    "error,status,code",
    [
        (CanvasSyncConflict("private source text"), 409, "state_changed"),
        (CanvasDocumentUploadLimited("document_upload_limit"), 429, "document_upload_limit"),
        (CanvasDocumentUploadLimited("private source text"), 429, "state_changed"),
        (RuntimeError("private source text"), 500, "document_operation_failed"),
        (KeyError("private source text"), 500, "document_operation_failed"),
    ],
)
def test_controlled_errors_do_not_echo_private_data_or_retry(
    device, monkeypatch, error, status, code
):
    calls = []

    def fail(*args, **kwargs):
        calls.append(True)
        raise error

    monkeypatch.setattr(device[0], "begin_document_upload", fail)
    response = post(
        client_for(device), device, "/begin", begin_body(device, evidence.prepare(device))
    )
    assert checked(response, status) == {"detail": {"code": code}}
    assert calls == [True] and "private source text" not in response.text
    if status == 429:
        assert response.headers["Retry-After"] == "30"


@pytest.mark.parametrize(
    "path,method",
    [
        ("/begin", "begin_document_upload"),
        ("/parts", "put_document_parts"),
        ("/finish", "finish_document_upload"),
    ],
)
def test_committed_response_loss_replays_without_duplicate_upload(
    device, monkeypatch, path, method
):
    body = begin_body(device, evidence.prepare(device))
    client = client_for(device)
    if path != "/begin":
        started = checked(post(client, device, "/begin", body))
        if path == "/finish":
            checked(post(client, device, "/parts", put_body(body, started["upload_id"])))
        body = (finish_body if path == "/finish" else put_body)(body, started["upload_id"])
    original = getattr(device[0], method)
    committed = []

    def lost(*args, **kwargs):
        committed.append(original(*args, **kwargs))
        raise RuntimeError("lost synthetic response")

    monkeypatch.setattr(device[0], method, lost)
    checked(post(client, device, path, body), 500)
    monkeypatch.setattr(device[0], method, original)
    assert checked(post(client_for(device), device, path, body)) == {
        **committed[0],
        "replayed": True,
    }
    assert count(device, "canvas_document_uploads") == 1


def test_real_upload_quota_returns_minimum_pause_without_capacity_promise(device):
    client = client_for(device)
    body = begin_body(device, evidence.prepare(device))
    for index in range(4):
        checked(post(client, device, "/begin", body | {"request_key": f"quota-{index}"}))
    response = post(client, device, "/begin", body | {"request_key": "over-quota"})
    assert checked(response, 429) == {"detail": {"code": "document_upload_limit"}}
    assert response.headers["Retry-After"] == "30"
    assert (
        count(device, "canvas_document_uploads")
        == count(device, "canvas_document_upload_receipts")
        == 4
    )


@pytest.mark.parametrize(
    "control,status",
    [
        ("revoke", 401),
        ("scope", 409),
        ("subject", 409),
        ("generation", 409),
        ("scan", 401),
        ("connection", 409),
        ("upload_expiry", 409),
    ],
)
def test_current_authority_blocks_parts_replay_and_new_request(device, control, status):
    client = client_for(device)
    body = begin_body(device, evidence.prepare(device))
    upload = checked(post(client, device, "/begin", body))
    request = put_body(body, upload["upload_id"])
    checked(post(client, device, "/parts", request))
    if control == "revoke":
        device[0].rotate_or_revoke("user_alice", body["connection_id"])
    elif control == "scope":
        sync.set_scope(device, [], kinds=[])
    elif control == "upload_expiry":
        with device[0].connection() as conn:
            conn.execute(
                "UPDATE wrytely_agent.canvas_document_uploads SET "
                "expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
                (upload["upload_id"],),
            )
    else:
        field = {"scan": "scan_id", "connection": "connection_id"}.get(control, control)
        request[field] = (
            "other"
            if control == "subject"
            else request[field] + 1
            if control == "generation"
            else str(uuid4())
        )
    for key in (request["request_key"], "new-put"):
        checked(post(client, device, "/parts", request | {"request_key": key}), status)
    assert count(device, "canvas_document_upload_receipts") == 2


def test_wrong_account_ingestion_cannot_replay_private_receipt(device):
    body = begin_body(device, evidence.prepare(device))
    client = client_for(device)
    checked(post(client, device, "/begin", body))
    db = device[0]
    db.provision("user_bob")
    code = db.create_pairing("user_bob", sync.ORIGIN)["code"]
    bob = db.redeem_pairing(code, "other-browser")
    db.bind_canvas_identity(bob["ingestion_bearer"], sync.ORIGIN, "bob")
    checked(post(client, (db, bob), "/begin", body), 401)


@pytest.mark.parametrize("path", ["/begin", "/parts", "/finish"])
def test_final_lease_fence_rolls_back_real_store(device, monkeypatch, path):
    body = begin_body(device, evidence.prepare(device))
    client = client_for(device)
    prior_receipts = 0
    if path != "/begin":
        upload = checked(post(client, device, "/begin", body))
        prior_receipts = 1
        if path == "/finish":
            checked(post(client, device, "/parts", put_body(body, upload["upload_id"])))
            prior_receipts = 2
        body = (finish_body if path == "/finish" else put_body)(body, upload["upload_id"])
    original = device[0]._save_document_receipt

    def late(conn, actor, row, scan, request, digest, upload_id):
        conn.execute(
            "UPDATE wrytely_agent.canvas_scans SET "
            "lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
            (scan["id"],),
        )
        return original(conn, actor, row, scan, request, digest, upload_id)

    monkeypatch.setattr(device[0], "_save_document_receipt", late)
    assert checked(post(client, device, path, body), 409) == {"detail": {"code": "lease_expired"}}
    assert count(device, "canvas_document_upload_receipts") == prior_receipts
    assert count(device, "canvas_document_uploads") == (path != "/begin")
    assert count(device, "canvas_document_upload_parts") == (path == "/finish")
    with device[0].connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM wrytely_agent.canvas_document_versions"
            ).fetchone()["n"]
            == 0
        )
