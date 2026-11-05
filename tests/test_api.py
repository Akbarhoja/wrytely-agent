from fastapi.testclient import TestClient

from app.main import create_app
from contracts.models import Identity
from shared.auth import AuthenticationError
from shared.config import Settings


class TestVerifier:
    __test__ = False

    def verify(self, token):
        if token not in ["alice", "bob"]:
            raise AuthenticationError()
        return Identity(f"user_{token}", f"sess_{token}")


def make_client(store):
    return TestClient(create_app(Settings(), store=store, verifier=TestVerifier()))


def auth(who="alice"):
    return {"Authorization": f"Bearer {who}"}


def test_no_authentication_bypass(store):
    client = make_client(store)
    assert client.get("/v1/me").status_code == 401
    assert client.post("/v1/bootstrap", headers=auth("bad")).status_code == 401
    # Default app has no debug identity/header/token fallback.
    real = TestClient(create_app(Settings(), store=store))
    assert real.post("/v1/bootstrap", headers=auth()).status_code == 401


def test_onboarding_session_restore_and_ownership(store):
    client = make_client(store)
    assert client.get("/v1/me", headers=auth()).status_code == 404
    first = client.post("/v1/bootstrap", headers=auth()).json()
    assert client.post("/v1/bootstrap", headers=auth()).json()["id"] == first["id"]
    client.post("/v1/bootstrap", headers=auth("bob"))
    headers = auth() | {"Idempotency-Key": "assignment-one"}
    response = client.post("/v1/messages", headers=headers, json={"content": "Secret notes"})
    assert response.status_code == 202
    assert (
        client.post("/v1/messages", headers=headers, json={"content": "Secret notes"}).json()
        == response.json()
    )
    task_id = response.json()["task_id"]
    assert client.get(f"/v1/tasks/{task_id}", headers=auth("bob")).status_code == 404
    assert client.get("/v1/messages", headers=auth("bob")).json() == {"messages": []}
    restarted = TestClient(create_app(Settings(), store=store, verifier=TestVerifier()))
    assert restarted.get("/v1/me", headers=auth()).json()["id"] == first["id"]


def test_rejects_owner_override_and_missing_idempotency_key(store):
    client = make_client(store)
    client.post("/v1/bootstrap", headers=auth())
    for body in [{"content": "hi", "user_id": "user_bob"}, {"content": " "}]:
        assert (
            client.post(
                "/v1/messages", headers=auth() | {"Idempotency-Key": "x"}, json=body
            ).status_code
            == 422
        )
    assert client.post("/v1/messages", headers=auth(), json={"content": "hi"}).status_code == 422


def test_health_is_not_a_false_claim_of_readiness():
    client = TestClient(create_app(Settings()))
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 503
