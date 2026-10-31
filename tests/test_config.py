import json

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsError

from shared.config import Settings
from shared.db import Store


def test_canvas_origins_default_to_disabled_without_changing_readiness(monkeypatch):
    monkeypatch.delenv("AGENT_CANVAS_ORIGINS", raising=False)
    settings = Settings(_env_file=None)
    assert settings.canvas_origins == ()
    assert set(settings.readiness()) == {"database", "authentication", "meta_model"}


def test_canvas_origins_load_as_operator_json_list_and_work_with_store(monkeypatch):
    origins = ["https://canvas.example.edu", "https://another.example.edu"]
    monkeypatch.setenv("AGENT_CANVAS_ORIGINS", json.dumps(origins))
    settings = Settings(_env_file=None)
    assert settings.canvas_origins == tuple(origins)
    store = Store("unused-no-connection", canvas_origins=settings.canvas_origins)
    assert store._canvas_origins == frozenset(origins)


@pytest.mark.parametrize(
    "origin",
    [
        "http://canvas.example.edu",
        "https://*.example.edu",
        "https://canvas.example.edu/",
        "https://canvas.example.edu/courses",
        "https://canvas.example.edu?x=1",
        "https://canvas.example.edu#fragment",
        "https://canvas.example.edu:443",
        "https://user:pass@canvas.example.edu",
        "https://CANVAS.example.edu",
        "https://cаnvas.example.edu",
        "",
        "https://canvas.example.edu\n",
    ],
)
def test_canvas_origin_rules_match_store_validation(origin):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, canvas_origins=[origin])
    with pytest.raises(ValueError):
        Store("unused-no-connection", canvas_origins=(origin,))


@pytest.mark.parametrize(
    "value",
    [
        '"https://canvas.example.edu"',
        "https://canvas.example.edu",
        "null",
        "{}",
        "123",
        '["https://canvas.example.edu",]',
        "[null]",
        "[123]",
    ],
)
def test_nonlist_or_malformed_environment_configuration_is_rejected(monkeypatch, value):
    monkeypatch.setenv("AGENT_CANVAS_ORIGINS", value)
    with pytest.raises((SettingsError, ValidationError)):
        Settings(_env_file=None)


def test_duplicate_origins_are_rejected():
    with pytest.raises(ValidationError, match="Duplicate Canvas origin"):
        Settings(_env_file=None, canvas_origins=["https://canvas.example.edu"] * 2)


def test_operator_origin_list_is_bounded():
    origins = [f"https://canvas-{index}.example.edu" for index in range(21)]
    with pytest.raises(ValidationError):
        Settings(_env_file=None, canvas_origins=origins)


def test_empty_env_list_explicitly_disables_origins(monkeypatch):
    monkeypatch.setenv("AGENT_CANVAS_ORIGINS", "[]")
    assert Settings(_env_file=None).canvas_origins == ()
