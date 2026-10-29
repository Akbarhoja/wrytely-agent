from contextlib import contextmanager
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg import OperationalError
from test_api import TestVerifier, auth, make_client

from app.main import create_app
from shared.config import Settings
from shared.db import Store


def save(client, *, who="alice", key=None, **body):
    return client.post(
        "/v1/sources",
        headers=auth(who) | {"Idempotency-Key": str(key or uuid4())},
        json={"title": "Fictional assignment", "content": "Private synthetic text"} | body,
    )


def test_snapshot_intake_is_private_idempotent_server_scoped_and_does_not_queue(store, alice):
    client = make_client(store)
    store.provision("user_bob")
    key = uuid4()
    first = save(client, key=key)
    assert first.status_code == 201
    result = first.json()
    assert set(result) == {
        "source_id",
        "version_id",
        "title",
        "reference",
        "coverage",
        "retrieved_at",
        "external_revision",
        "content",
    }
    assert result["coverage"] == "snapshot"
    assert result["reference"] == f"snapshot:{key}"
    assert datetime.fromisoformat(result["retrieved_at"]).tzinfo is not None
    assert save(client, key=key).json() == result
    assert save(client, key=key, content="Changed text").status_code == 409
    assert store.tasks("user_alice") == []
    assert store.responsibilities("user_alice") == []
    index = client.get("/v1/sources", headers=auth())
    assert index.status_code == 200
    assert index.json() == {
        "sources": [{k: v for k, v in result.items() if k != "content"}],
        "limit": 50,
    }
    detail = client.get(f"/v1/sources/{result['source_id']}", headers=auth())
    assert detail.json() == result
    for response in (first, index, detail):
        assert response.headers["cache-control"] == "no-store"
    assert client.get("/v1/sources", headers=auth("bob")).json() == {"sources": [], "limit": 50}
    absent = client.get(f"/v1/sources/{uuid4()}", headers=auth("bob"))
    other = client.get(f"/v1/sources/{result['source_id']}", headers=auth("bob"))
    assert absent.status_code == other.status_code == 404
    assert absent.json() == other.json()
    # Same client request key is isolated by the verified account.
    assert save(client, who="bob", key=key).json()["source_id"] != result["source_id"]


@pytest.mark.parametrize(
    "extra",
    [
        {"user_id": "user_bob"},
        {"coverage": "group"},
        {"retrieved_at": "2026-10-29T00:00:00Z"},
        {"source_id": str(uuid4())},
        {"policy": "permitted"},
        {"reference": "https://example.test"},
    ],
)
def test_snapshot_rejects_browser_identity_provenance_and_authority(store, alice, extra):
    assert save(make_client(store), **extra).status_code == 422
    assert store.source_snapshots("user_alice") == []


@pytest.mark.parametrize(
    "body",
    [
        {"title": " "},
        {"content": " "},
        {"title": "x" * 301},
        {"content": "x" * 24001},
        {"title": 12},
        {"content": ["text"]},
    ],
)
def test_snapshot_input_bounds(store, alice, body):
    assert save(make_client(store), **body).status_code == 422


def test_snapshot_body_byte_limit_and_setup_auth_requirements(store):
    client = make_client(store)
    assert client.get("/v1/sources").status_code == 401
    assert client.get(f"/v1/sources/{uuid4()}").status_code == 401
    assert client.post("/v1/sources", json={"title": "x", "content": "x"}).status_code == 401
    assert save(client).status_code == 409
    client.post("/v1/bootstrap", headers=auth())
    assert save(client, content="字" * 23000).status_code == 413
    assert (
        client.post("/v1/sources", headers=auth(), json={"title": "x", "content": "x"}).status_code
        == 422
    )
    assert (
        client.post(
            "/v1/sources",
            headers=auth() | {"Idempotency-Key": "not-a-uuid"},
            json={"title": "x", "content": "x"},
        ).status_code
        == 422
    )


def test_snapshot_storage_failure_is_not_a_successful_empty_list():
    class BrokenStore(Store):
        @contextmanager
        def connection(self):
            raise OperationalError("private connection details")
            yield

    client = TestClient(
        create_app(Settings(), store=BrokenStore("unused"), verifier=TestVerifier())
    )
    for path in ("/v1/sources", f"/v1/sources/{uuid4()}"):
        response = client.get(path, headers=auth())
        assert response.status_code == 503
        assert "private connection" not in response.text
    assert save(client).status_code == 503
