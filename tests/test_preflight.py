import json

import psycopg
import pytest

from runtime import preflight
from shared.config import Settings


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    import os

    for key in os.environ:
        if key.startswith("AGENT_"):
            monkeypatch.delenv(key)


def configured(**overrides):
    fields = {
        "database_url": "postgresql://private:private@localhost/private",
        "clerk_issuer": "https://clerk.example.test",
        "clerk_jwt_key": "private-public-key-placeholder",
        "authorized_parties": ["http://localhost:3000"],
        "canvas_origins": ["https://canvas.example.test"],
        "canvas_document_extractors": ["canvas.html.v2"],
        "meta_provider": "fireworks",
        "fireworks_api_key": "private-fireworks-key",
        "meta_budget_key": "private-budget-key",
        "meta_input_usd_per_million": "1",
        "meta_output_usd_per_million": "4",
        "telegram_bot_token": "123456789:" + "z" * 35,
        "telegram_bot_username": "example_test_bot",
        "telegram_webhook_secret": "private_" + "w" * 35,
    }
    return Settings(_env_file=None, **(fields | overrides))


def test_default_check_has_no_network_or_database_side_effects(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("Default preflight must not connect")

    monkeypatch.setattr(psycopg, "connect", forbidden)
    assert preflight.main([]) == 1
    report = json.loads(capsys.readouterr().out)
    assert not report["configuration_complete"]
    assert not report["live_agent_verified"]
    assert report["database"]["state"] == "not_checked"
    assert {check["name"] for check in report["checks"]} == {
        "database",
        "authentication",
        "canvas",
        "model_credential",
        "model_options",
        "model_budget_configuration",
        "telegram_bot",
        "telegram_webhook",
    }


def test_complete_configuration_does_not_certify_live_agent_or_print_values(monkeypatch, capsys):
    settings = configured()
    monkeypatch.setattr(preflight, "Settings", lambda: settings)
    assert preflight.main([]) == 0
    output = capsys.readouterr().out
    report = json.loads(output)
    assert report["configuration_complete"]
    assert report["live_agent_verified"] is False
    for private_value in [
        "private-fireworks-key",
        "private-budget-key",
        "postgresql://",
        "123456789:",
        "clerk.example.test",
    ]:
        assert private_value not in output


@pytest.mark.parametrize("profile", preflight.PROFILES)
def test_profiles_only_require_their_own_configuration(profile):
    checks = preflight.configuration_checks(configured(), profile)
    names = {check["name"] for check in checks}
    assert all(check["state"] == "configured" for check in checks)
    assert ("authentication" in names) == (profile in {"api", "all"})
    assert ("model_credential" in names) == (profile in {"supervisor", "all"})
    assert ("telegram_bot" in names) == (profile in {"telegram", "all"})


def test_other_provider_key_cannot_satisfy_selected_provider():
    checks = preflight.configuration_checks(
        configured(fireworks_api_key=None, meta_api_key="not-selected"), "supervisor"
    )
    assert (
        next(check for check in checks if check["name"] == "model_credential")["state"]
        == "missing_or_invalid"
    )


@pytest.mark.parametrize(
    "changes,name",
    [
        ({"meta_reasoning_effort": "xhigh"}, "model_options"),
        ({"meta_input_usd_per_million": None}, "model_budget_configuration"),
        ({"telegram_bot_token": "bad-secret-value"}, "telegram_bot"),
        ({"telegram_webhook_secret": "short"}, "telegram_webhook"),
    ],
)
def test_actionable_incompatible_configuration(changes, name):
    checks = preflight.configuration_checks(configured(**changes), "all")
    assert next(check for check in checks if check["name"] == name)["state"] == "missing_or_invalid"


@pytest.mark.parametrize(
    "changes,name",
    [
        ({"database_url": " "}, "database"),
        ({"fireworks_api_key": ""}, "model_credential"),
        ({"clerk_jwt_key": " "}, "authentication"),
    ],
)
def test_empty_secrets_are_not_configured(changes, name):
    checks = preflight.configuration_checks(configured(**changes), "all")
    assert next(check for check in checks if check["name"] == name)["state"] == "missing_or_invalid"


@pytest.mark.parametrize("key", ["AGENT_META_PROVIDER", "AGENT_AUTHORIZED_PARTIES"])
def test_invalid_environment_never_dumps_validation_input(monkeypatch, capsys, key):
    monkeypatch.setenv(key, "private-malformed-value")
    assert preflight.main([]) == 1
    output = capsys.readouterr().out
    assert "private-malformed-value" not in output
    assert json.loads(output)["configuration_error"] == "invalid_environment_configuration"


class LedgerConnection:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query):
        self.queries.append(query)
        return self

    def fetchall(self):
        return self.rows


@pytest.mark.parametrize(
    "rows,reason,state",
    [
        ([("001", "a"), ("002", "b")], "migration_ledger_matches", "verified"),
        ([("001", "a")], "migrations_pending", "blocked"),
        ([("001", "altered")], "migration_checksum_mismatch", "blocked"),
        ([("999", "future")], "database_newer_than_checkout", "blocked"),
    ],
)
def test_ledger_check_is_read_only_and_checks_exact_checkout(monkeypatch, rows, reason, state):
    connection = LedgerConnection(rows)
    monkeypatch.setattr(psycopg, "connect", lambda *args, **kwargs: connection)
    monkeypatch.setattr(preflight, "expected_migrations", lambda: {"001": "a", "002": "b"})
    assert preflight.database_check("private-dsn") == {"state": state, "reason": reason}
    assert connection.queries == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '5s'",
        "SELECT version, checksum FROM wrytely_agent.migrations",
    ]


def test_database_failures_are_sanitized_and_no_configuration_is_not_a_connection(monkeypatch):
    def failure(*args, **kwargs):
        raise RuntimeError("secret-password from database")

    monkeypatch.setattr(psycopg, "connect", failure)
    assert preflight.database_check(None)["state"] == "not_checked"
    assert preflight.database_check("private-dsn") == {
        "state": "blocked",
        "reason": "database_unreachable_or_access_denied",
    }


def test_opt_in_database_failure_is_nonzero_even_with_complete_settings(monkeypatch, capsys):
    monkeypatch.setattr(preflight, "Settings", configured)
    monkeypatch.setattr(
        preflight,
        "database_check",
        lambda _: {"state": "blocked", "reason": "migrations_pending"},
    )
    assert preflight.main(["--database-check"]) == 1
    assert json.loads(capsys.readouterr().out)["configuration_complete"] is True
