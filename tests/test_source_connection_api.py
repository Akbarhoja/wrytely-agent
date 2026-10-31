import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from psycopg import OperationalError

from app.main import create_app
from app.source_connections import CanvasRoute
from contracts.models import Identity
from shared.auth import AuthenticationError
from shared.config import Settings
from shared.db import Store

ORIGIN = "https://canvas.example.edu"
ROOT = "/v1/source-connections"
CANVAS = ROOT + "/canvas"


class SessionVerifier:
    def verify(self, token):
        if token not in {"alice", "bob"}:
            raise AuthenticationError()
        return Identity(f"user_{token}", f"session_{token}")


def auth(who="alice"):
    return {"Authorization": f"Bearer {who}"}


@pytest.fixture
def canvas_store(store, database_url):
    result = Store(database_url, canvas_origins=(ORIGIN,))
    with result.connection() as conn:
        conn.execute("TRUNCATE wrytely_agent.source_pairing_rates")
    result.provision("user_alice")
    result.provision("user_bob")
    return result


def client_for(store, enabled=True):
    return TestClient(
        create_app(
            Settings(_env_file=None, canvas_origins=[ORIGIN] if enabled else []),
            store=store,
            verifier=SessionVerifier(),
        )
    )


def challenge(client, who="alice"):
    response = client.post(CANVAS + "/pairing", headers=auth(who), json={"origin": ORIGIN})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def redeem(client, code, device="device-1"):
    return client.post(CANVAS + "/redeem", json={"code": code, "device_public_id": device})


def bind(client, token, subject="provider-alice", origin=ORIGIN):
    return client.post(
        CANVAS + "/bind", headers=auth(token), json={"origin": origin, "provider_subject": subject}
    )


def paired(client, who="alice", device="device-1"):
    result = redeem(client, challenge(client, who)["code"], device)
    assert result.status_code == 200
    return result.json()


def test_pair_bind_read_revoke_real_store_flow(canvas_store):
    client = client_for(canvas_store)
    code = challenge(client)
    assert code["challenge"] == code["code"]
    result = redeem(client, code["code"]).json()
    token, connection = result["ingestion_bearer"], result["connection_id"]
    assert result["state"] == "pending_identity"
    response = bind(client, token)
    assert response.status_code == 200
    assert response.json()["state"] == "connected"
    assert response.headers["cache-control"] == "no-store"
    own = client.get(ROOT + "/" + connection, headers=auth())
    assert own.status_code == 200
    assert set(own.json()) == {
        "connection_id",
        "provider",
        "origin",
        "state",
        "generation",
        "credential_expires_at",
    }
    assert token not in own.text and "provider-alice" not in own.text
    revoked = client.post(ROOT + "/" + connection + "/revoke", headers=auth())
    assert revoked.status_code == 200
    assert revoked.json()["state"] == "disconnected"
    assert bind(client, token).status_code == 401


def test_private_routes_require_verified_session_and_no_store(canvas_store):
    client = client_for(canvas_store)
    for response in [
        client.post(CANVAS + "/pairing", json={"origin": ORIGIN}),
        client.get(ROOT + "/not-an-id"),
        client.post(ROOT + "/not-an-id/revoke"),
    ]:
        assert response.status_code == 401
        assert response.headers["cache-control"] == "no-store"
    real = TestClient(create_app(Settings(_env_file=None), store=canvas_store))
    assert (
        real.post(CANVAS + "/pairing", headers=auth(), json={"origin": ORIGIN}).status_code == 401
    )


def test_two_accounts_and_malformed_ids_share_private_not_found(canvas_store):
    client = client_for(canvas_store)
    result = paired(client)
    connection = result["connection_id"]
    absent = client.get(ROOT + "/not-an-id", headers=auth("bob"))
    other = client.get(ROOT + "/" + connection, headers=auth("bob"))
    assert absent.status_code == other.status_code == 404
    assert absent.json() == other.json()
    assert client.post(ROOT + "/" + connection + "/revoke", headers=auth("bob")).status_code == 404
    assert bind(client, result["ingestion_bearer"]).status_code == 200


def test_clerk_and_ingestion_bearers_cannot_swap_roles(canvas_store):
    client = client_for(canvas_store)
    result = paired(client)
    assert bind(client, "alice").status_code == 401
    assert (
        client.get(
            ROOT + "/" + result["connection_id"], headers=auth(result["ingestion_bearer"])
        ).status_code
        == 401
    )
    assert (
        client.post(CANVAS + "/bind", json={"origin": ORIGIN, "provider_subject": "x"}).status_code
        == 401
    )


def test_unknown_authority_fields_reject_without_echoing_pair_code(canvas_store):
    client = client_for(canvas_store)
    secret = challenge(client)["code"]
    bad = client.post(
        CANVAS + "/redeem",
        json={"code": secret, "device_public_id": "device-1", "user_id": "user_bob"},
    )
    assert bad.status_code == 422
    assert secret not in bad.text and "user_bob" not in bad.text
    assert bad.headers["cache-control"] == "no-store"
    assert redeem(client, secret).status_code == 200
    for field in ["user_id", "canvas_origins", "ready"]:
        response = client.post(
            CANVAS + "/pairing", headers=auth(), json={"origin": ORIGIN, field: "untrusted"}
        )
        assert response.status_code == 422
        assert "untrusted" not in response.text


def test_changed_provider_subject_commits_revocation_before_error(canvas_store):
    client = client_for(canvas_store)
    result = paired(client)
    token = result["ingestion_bearer"]
    first = bind(client, token).json()
    changed = bind(client, token, subject="other-provider-subject")
    assert changed.status_code == 401
    assert token not in changed.text and "other-provider-subject" not in changed.text
    state = client.get(ROOT + "/" + result["connection_id"], headers=auth()).json()
    assert state["state"] == "reconnect_required"
    assert state["generation"] == first["generation"] + 1
    assert bind(client, token).status_code == 401


def test_same_device_repair_keeps_id_but_fences_previous_bearer(canvas_store):
    client = client_for(canvas_store)
    first = paired(client)
    assert bind(client, first["ingestion_bearer"]).status_code == 200
    second = paired(client)
    assert second["connection_id"] == first["connection_id"]
    assert second["generation"] > first["generation"]
    assert bind(client, first["ingestion_bearer"]).status_code == 401
    assert bind(client, second["ingestion_bearer"]).status_code == 200


def test_wrong_expired_and_used_codes_have_one_public_error(canvas_store):
    client = client_for(canvas_store)
    wrong = redeem(client, "A" * 32)
    short = redeem(client, "")
    code = challenge(client)["code"]
    with canvas_store.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.source_pairings SET expires_at=now()-interval '1 second'"
        )
    expired = redeem(client, code)
    fresh = challenge(client)["code"]
    assert redeem(client, fresh).status_code == 200
    used = redeem(client, fresh)
    assert {wrong.status_code, short.status_code, expired.status_code, used.status_code} == {400}
    assert wrong.json() == short.json() == expired.json() == used.json()
    assert fresh not in used.text


def test_store_rate_limit_is_honestly_reported(canvas_store):
    client = client_for(canvas_store)
    for _ in range(5):
        challenge(client)
    limited = client.post(CANVAS + "/pairing", headers=auth(), json={"origin": ORIGIN})
    assert limited.status_code == 429
    assert limited.headers["cache-control"] == "no-store"


def test_default_disabled_credential_ops_but_private_revoke_still_available(canvas_store):
    active = client_for(canvas_store)
    result = paired(active)
    disabled = client_for(canvas_store, enabled=False)
    for response in [
        disabled.post(CANVAS + "/pairing", headers=auth(), json={"origin": ORIGIN}),
        redeem(disabled, "A" * 32),
        bind(disabled, result["ingestion_bearer"]),
    ]:
        assert response.status_code == 503
        assert response.headers["cache-control"] == "no-store"
    assert disabled.get(ROOT + "/" + result["connection_id"], headers=auth()).status_code == 200
    assert (
        disabled.post(ROOT + "/" + result["connection_id"] + "/revoke", headers=auth()).status_code
        == 200
    )


@pytest.mark.parametrize("chunked", [False, True])
def test_actual_body_limit_does_not_trust_content_length(canvas_store, chunked):
    client = client_for(canvas_store)
    body = b"x" * 17000
    response = client.post(
        CANVAS + "/redeem",
        content=iter([body[:8000], body[8000:]]) if chunked else body,
        headers={"Content-Type": "application/json", "Content-Length": "1"},
    )
    assert response.status_code == 413
    assert response.headers["cache-control"] == "no-store"


def test_invalid_json_content_type_and_validation_are_redacted(canvas_store):
    client = client_for(canvas_store)
    for content, content_type, status in [
        ('{"code":"PRIVATE_BROKEN', "application/json", 422),
        ("PRIVATE_TEXT", "text/plain", 415),
        (json.dumps({"code": "PRIVATE_CODE", "device_public_id": 1}), "application/json", 422),
    ]:
        response = client.post(
            CANVAS + "/redeem", content=content, headers={"Content-Type": content_type}
        )
        assert response.status_code == status
        assert "PRIVATE" not in response.text
        assert response.headers["cache-control"] == "no-store"


def test_storage_errors_return_controlled_503_without_secrets(canvas_store, monkeypatch, caplog):
    client = client_for(canvas_store)

    def fail(*args):
        raise OperationalError("PRIVATE_DATABASE_DETAIL")

    monkeypatch.setattr(canvas_store, "create_pairing", fail)
    response = client.post(CANVAS + "/pairing", headers=auth(), json={"origin": ORIGIN})
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert "PRIVATE_DATABASE_DETAIL" not in response.text + caplog.text


def test_no_provider_subject_secret_or_code_is_logged(canvas_store, caplog):
    client = client_for(canvas_store)
    code = challenge(client)["code"]
    result = redeem(client, code).json()
    assert bind(client, result["ingestion_bearer"]).status_code == 200
    assert all(
        value not in caplog.text for value in [code, result["ingestion_bearer"], "provider-alice"]
    )
    with canvas_store.connection() as conn:
        assert conn.execute("SELECT count(*) AS n FROM wrytely_agent.tasks").fetchone()["n"] == 0
        assert (
            conn.execute("SELECT count(*) AS n FROM wrytely_agent.whatsapp_outbound").fetchone()[
                "n"
            ]
            == 0
        )


def test_default_store_constructor_gets_operator_origins_once(store, monkeypatch):
    import app.main as main

    calls = []

    def construct(url, **kwargs):
        calls.append((url, kwargs))
        return store

    monkeypatch.setattr(main, "Store", construct)
    main.create_app(
        Settings(_env_file=None, database_url="synthetic-no-connection", canvas_origins=[ORIGIN]),
        verifier=SessionVerifier(),
    )
    assert calls == [("synthetic-no-connection", {"canvas_origins": (ORIGIN,)})]


def test_unconfigured_origin_and_expired_credential_fail_closed(canvas_store):
    client = client_for(canvas_store)
    response = client.post(
        CANVAS + "/pairing", headers=auth(), json={"origin": "https://other.example.edu"}
    )
    assert response.status_code == 422
    result = paired(client)
    assert (
        bind(client, result["ingestion_bearer"], origin="https://other.example.edu").status_code
        == 401
    )
    with canvas_store.connection() as conn:
        conn.execute(
            "UPDATE wrytely_agent.source_connections "
            "SET credential_expires_at=now()-interval '1 second'"
        )
    assert bind(client, result["ingestion_bearer"]).status_code == 401
    response = client.get(ROOT + "/" + result["connection_id"], headers=auth())
    assert response.json()["state"] == "reconnect_required"


def test_revoke_rejects_authority_fields_without_mutation(canvas_store):
    client = client_for(canvas_store)
    result = paired(client)
    response = client.post(
        ROOT + "/" + result["connection_id"] + "/revoke",
        headers=auth(),
        json={"user_id": "PRIVATE_OWNER"},
    )
    assert response.status_code == 422
    assert "PRIVATE_OWNER" not in response.text
    assert bind(client, result["ingestion_bearer"]).status_code == 200


def test_unprovisioned_session_and_absent_database_are_controlled(canvas_store):
    client = client_for(canvas_store)
    with canvas_store.connection() as conn:
        conn.execute("TRUNCATE wrytely_agent.students CASCADE")
    response = client.post(CANVAS + "/pairing", headers=auth(), json={"origin": ORIGIN})
    assert response.status_code == 409
    empty = TestClient(
        create_app(
            Settings(_env_file=None, database_url=None, canvas_origins=[ORIGIN]),
            verifier=SessionVerifier(),
        )
    )
    response = empty.post(CANVAS + "/pairing", headers=auth(), json={"origin": ORIGIN})
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("size,status", [(16384, 200), (17000, 413)])
def test_raw_asgi_chunks_stop_at_bound_without_reading_remainder(size, status):
    from fastapi import APIRouter, FastAPI, Request

    api = FastAPI()
    router = APIRouter(route_class=CanvasRoute)

    @router.post("/bounded")
    async def endpoint(request: Request):
        return {"size": len(await request.body())}

    api.include_router(router)
    delivered = []
    messages = []
    chunks = [b"x" * 8000, b"x" * (size - 8000), b"unread"]

    async def receive():
        index = len(delivered)
        delivered.append(index)
        return {
            "type": "http.request",
            "body": chunks[index],
            "more_body": index == 0 or status == 413,
        }

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/bounded",
        "root_path": "",
        "query_string": b"",
        "headers": [(b"content-type", b"application/json"), (b"content-length", b"1")],
        "server": ("test", 80),
        "client": ("test", 1234),
    }
    asyncio.run(api(scope, receive, send))
    assert delivered == [0, 1]
    assert messages[0]["status"] == status
    assert (b"cache-control", b"no-store") in messages[0]["headers"]
    if status == 200:
        assert json.loads(messages[1]["body"]) == {"size": size}
