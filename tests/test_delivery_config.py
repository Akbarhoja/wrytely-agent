import pytest
from pydantic import ValidationError

from shared.config import Settings


def test_delivery_config_defaults_closed_and_token_is_redacted(monkeypatch):
    monkeypatch.delenv("AGENT_WHATSAPP_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("AGENT_WHATSAPP_API_VERSION", raising=False)
    settings = Settings()
    assert settings.whatsapp_access_token is None
    assert settings.whatsapp_api_version is None
    configured = Settings(
        whatsapp_access_token="placeholder-private-token", whatsapp_api_version="v23.0"
    )
    assert "placeholder-private-token" not in str(configured)
    assert configured.whatsapp_api_version == "v23.0"


@pytest.mark.parametrize("version", ["", "23", "latest", "v23.1", "https://example.test"])
def test_delivery_config_rejects_implicit_or_invalid_api_version(version):
    with pytest.raises(ValidationError):
        Settings(whatsapp_api_version=version)
