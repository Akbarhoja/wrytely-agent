from contextlib import contextmanager
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg import OperationalError
from test_academic_memory import observation
from test_api import TestVerifier, auth, make_client
from test_artifacts import assessment, prepare
from test_worker import ScriptedModel

from app.main import create_app
from runtime.verification import verify_artifact
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
    for path in (
        "/v1/sources",
        f"/v1/sources/{uuid4()}",
        "/v1/responsibilities",
        f"/v1/responsibilities/{uuid4()}/artifacts",
        f"/v1/artifacts/{uuid4()}",
    ):
        response = client.get(path, headers=auth())
        assert response.status_code == 503
        assert response.headers["cache-control"] == "no-store"
        assert "private connection" not in response.text
    assert save(client).status_code == 503


def test_private_results_preserve_review_failures_staleness_and_account_isolation(store, alice):
    lease, artifact, policy, rubric, _, draft = prepare(store, alice)
    client = make_client(store)
    store.provision("user_bob")
    duty_id, artifact_id = artifact["responsibility_id"], artifact["id"]
    index = client.get("/v1/responsibilities", headers=auth())
    assert index.status_code == 200
    assert index.json()["limit"] == 50
    row = index.json()["responsibilities"][0]
    assert set(row) == {"id", "objective", "status", "steps_created", "max_steps", "created_at"}
    assert row["id"] == str(duty_id)
    assert "request_key" not in index.text and "user_alice" not in index.text
    path = f"/v1/responsibilities/{duty_id}/artifacts"
    listed = client.get(path, headers=auth())
    assert listed.json()["limit"] == 50
    assert listed.json()["artifacts"][0]["state"] == "review"
    detail_path = f"/v1/artifacts/{artifact_id}"
    detail = client.get(detail_path, headers=auth())
    assert detail.json()["artifact"]["draft"] == draft.model_dump(mode="json")
    assert detail.json()["latest_check"] is None
    for response in (index, listed, detail):
        assert response.headers["cache-control"] == "no-store"
    for owned, absent in (
        (path, f"/v1/responsibilities/{uuid4()}/artifacts"),
        (detail_path, f"/v1/artifacts/{uuid4()}"),
    ):
        assert client.get(owned).status_code == 401
        other = client.get(owned, headers=auth("bob"))
        missing = client.get(absent, headers=auth("bob"))
        assert other.status_code == missing.status_code == 404
        assert other.json() == missing.json()
        assert other.headers["cache-control"] == "no-store"
    assert client.get("/v1/responsibilities", headers=auth("bob")).json() == {
        "responsibilities": [],
        "limit": 50,
    }
    empty = store.create_responsibility("user_alice", "Empty synthetic duty", "empty-result")
    assert client.get(f"/v1/responsibilities/{empty['id']}/artifacts", headers=auth()).json() == {
        "artifacts": [],
        "limit": 50,
    }
    failed = verify_artifact(
        store,
        ScriptedModel([assessment(claim_support=["uncertain"])]),
        Settings(),
        lease,
        artifact_id,
        policy=policy,
        rubric=rubric,
    )
    assert not failed["passed"]
    assert client.get(detail_path, headers=auth()).json()["latest_check"] == failed
    passed = verify_artifact(
        store,
        ScriptedModel([assessment()]),
        Settings(),
        lease,
        artifact_id,
        policy=policy,
        rubric=rubric,
    )
    assert passed["passed"]
    assert client.get(detail_path, headers=auth()).json()["artifact"]["state"] == "ready"
    store.observe_source("user_alice", observation("v2", key="rubric", content="Changed evidence"))
    stale = client.get(detail_path, headers=auth()).json()
    assert stale["artifact"]["stale"] is True
    assert stale["latest_check"]["passed"] is True  # historical result is retained honestly
    assert client.get(path, headers=auth()).json()["artifacts"][0]["stale"] is True


def test_result_routes_have_no_public_or_mutation_fallback(store, alice):
    client = make_client(store)
    assert client.get("/v1/responsibilities").status_code == 401
    for path in (
        "/v1/responsibilities",
        f"/v1/artifacts/{uuid4()}",
        f"/v1/responsibilities/{uuid4()}/artifacts",
    ):
        assert client.post(path, headers=auth(), json={"ready": True}).status_code == 405
