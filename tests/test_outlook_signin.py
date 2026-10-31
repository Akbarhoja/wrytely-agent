import json
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest

from scripts import p0_outlook_signin as signin

TENANT = "11111111-1111-4111-8111-111111111111"
SUBJECT = "22222222-2222-4222-8222-222222222222"


@pytest.mark.parametrize(
    "target,host",
    [
        ("/?state=bad&code=x", "localhost:8765"),
        ("/?state=s&code=x&state=s", "localhost:8765"),
        ("/?state=s&code=x&error=denied", "localhost:8765"),
        ("/?state=s", "localhost:8765"),
        ("/favicon.ico?state=s&code=x", "localhost:8765"),
        ("/?state=s&code=x", "attacker.example"),
        ("https://localhost:8765/?state=s&code=x", "localhost:8765"),
        ("/?state=s&code=x#fragment", "localhost:8765"),
        ("/?state=s&code=" + "x" * 16384, "localhost:8765"),
        ("/?state=s&code=x&broken", "localhost:8765"),
    ],
)
def test_rejects_untrusted_callback_without_consuming_state(target, host):
    gate = signin.CallbackGate("s")
    assert not gate.accept(target, host)
    assert gate.response is None
    assert gate.accept("/?state=s&code=valid", "localhost:8765")


def test_one_use_expiry_and_clear():
    clock = [0]
    gate = signin.CallbackGate("s", now=lambda: clock[0])
    clock[0] = signin.TTL
    assert not gate.accept("/?state=s&code=x", "localhost:8765")
    gate = signin.CallbackGate("s")
    assert gate.accept("/?state=s&error=denied&error_description=private", "localhost:8765")
    assert "error_description" not in gate.response
    assert not gate.accept("/?state=s&code=x", "localhost:8765")
    gate.clear()
    assert gate.response is None and gate.state == "" and gate.deadline == 0


def valid_result():
    return {
        "access_token": "synthetic",
        "scope": "User.Read Mail.Read",
        "id_token_claims": {"oid": SUBJECT, "tid": TENANT},
    }


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ({"id_token_claims": {}}, "identity_unavailable"),
        ({"id_token_claims": {"oid": SUBJECT, "tid": SUBJECT}}, "wrong_organization"),
        ({"scope": "User.Read"}, "unexpected_grant"),
        ({"refresh_token": "synthetic"}, "unexpected_grant"),
        ({"access_token": ""}, "authorization_failed"),
    ],
)
def test_identity_and_scope_fences(mutation, reason):
    result = valid_result() | mutation
    with pytest.raises(signin.Blocked, match=reason):
        signin.validated_identity(result, TENANT)


def test_identity_returns_verified_subject():
    assert signin.validated_identity(valid_result(), TENANT) == SUBJECT


class FakeServer:
    latest = None

    def __init__(self, address, handler, bind_and_activate):
        assert address == ("127.0.0.1", 8765)
        assert bind_and_activate is False
        self.handler = handler
        self.closed = self.bound = False
        FakeServer.latest = self

    def server_bind(self):
        assert self.allow_reuse_address is False
        self.bound = True

    def server_activate(self):
        assert self.bound

    def handle_request(self):
        gate = self.handler.callback_gate
        gate.accept("/?" + urlencode({"state": gate.state, "code": "synthetic"}), "localhost:8765")

    def server_close(self):
        self.closed = True


class FakeApp:
    latest = None
    bad_url = False

    def __init__(self, client_id, **kwargs):
        assert FakeServer.latest.bound
        assert kwargs["exclude_scopes"] == ["offline_access"]
        assert kwargs["authority"] == "https://login.microsoftonline.com/organizations"
        assert kwargs["enable_pii_log"] is False
        self.result = valid_result()
        self.removed = False
        FakeApp.latest = self

    def initiate_auth_code_flow(self, scopes, **kwargs):
        assert scopes == ["User.Read", "Mail.Read"]
        query = {
            "state": kwargs["state"],
            "redirect_uri": kwargs["redirect_uri"],
            "code_challenge_method": "S256",
            "code_challenge": "synthetic",
            "scope": "User.Read Mail.Read openid profile",
        }
        host = "attacker.example" if self.bad_url else "login.microsoftonline.com"
        return {"auth_uri": "https://" + host + "/authorize?" + urlencode(query)}

    def acquire_token_by_auth_code_flow(self, flow, response):
        return self.result

    def get_accounts(self):
        return ["synthetic"]

    def remove_account(self, account):
        self.removed = True


def test_sdk_lifecycle_no_graph_no_token_output(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(signin, "LoopbackServer", FakeServer)
    args = SimpleNamespace(
        client_id=TENANT,
        expected_tenant=TENANT,
        url_file=str(tmp_path / "request.json"),
        read_inbox=False,
    )
    outcome = signin.run(args, app_factory=FakeApp)
    assert outcome == {"state": "sign_in_passed", "mail_read_attempted": False}
    assert FakeServer.latest.closed and FakeApp.latest.removed
    assert FakeApp.latest.result == {}
    assert not (tmp_path / "request.json").exists()
    assert capsys.readouterr().out == "authorization_url_ready\n"
    assert "synthetic" not in json.dumps(outcome)


def test_never_overwrites_existing_url_file(tmp_path, monkeypatch):
    monkeypatch.setattr(signin, "LoopbackServer", FakeServer)
    target = tmp_path / "request.json"
    target.write_text("preserve")
    args = SimpleNamespace(
        client_id=TENANT, expected_tenant=TENANT, url_file=str(target), read_inbox=False
    )
    with pytest.raises(FileExistsError):
        signin.run(args, app_factory=FakeApp)
    assert target.read_text() == "preserve"
    assert FakeServer.latest.closed and FakeApp.latest.removed


def test_rejects_non_microsoft_authorization_uri(tmp_path, monkeypatch):
    monkeypatch.setattr(signin, "LoopbackServer", FakeServer)
    monkeypatch.setattr(FakeApp, "bad_url", True)
    args = SimpleNamespace(
        client_id=TENANT,
        expected_tenant=TENANT,
        url_file=str(tmp_path / "request.json"),
        read_inbox=False,
    )
    with pytest.raises(signin.Blocked, match="invalid_authorization_request"):
        signin.run(args, app_factory=FakeApp)
    assert not (tmp_path / "request.json").exists()
    assert FakeServer.latest.closed
