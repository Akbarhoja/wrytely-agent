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


def test_public_destination_is_optional_and_distinct_from_internal_phone_id(monkeypatch):
    monkeypatch.delenv("AGENT_WHATSAPP_BUSINESS_NUMBER", raising=False)
    assert Settings().whatsapp_business_number is None
    configured = Settings(whatsapp_business_number="15555550123", whatsapp_phone_number_id="123")
    assert configured.whatsapp_business_number == "15555550123"
    assert configured.whatsapp_phone_number_id == "123"


@pytest.mark.parametrize(
    "number", ["", "+15555550123", "01234567", "abc", "12345", "1234567890123456"]
)
def test_public_destination_rejects_invalid_international_digits(number):
    with pytest.raises(ValidationError):
        Settings(whatsapp_business_number=number)
