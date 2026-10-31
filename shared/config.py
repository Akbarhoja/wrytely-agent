import json
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from contracts.templates import ApprovedTemplate
from shared.source_connections import canvas_origin


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENT_", extra="ignore")
    database_url: SecretStr | None = None
    clerk_issuer: str | None = None
    clerk_jwt_key: SecretStr | None = None
    authorized_parties: list[str] = Field(default_factory=list)
    canvas_origins: Annotated[tuple[str, ...], NoDecode] = Field(default=(), max_length=20)
    meta_api_key: SecretStr | None = None
    meta_model: str = "muse-spark-1.3"
    whatsapp_approved_templates: list[ApprovedTemplate] = Field(default_factory=list, max_length=20)
    whatsapp_reply_template_key: str | None = None
    whatsapp_business_number: str | None = Field(default=None, pattern=r"^[1-9][0-9]{6,14}$")
    whatsapp_access_token: SecretStr | None = None
    whatsapp_api_version: str | None = Field(default=None, pattern=r"^v[0-9]+\.0$")
    whatsapp_app_secret: SecretStr | None = None
    whatsapp_verify_token: SecretStr | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_business_account_id: str | None = None
    max_episode_turns: int = Field(default=6, ge=1, le=20)
    lease_seconds: int = Field(default=300, ge=30, le=3600)
    max_attempts: int = Field(default=3, ge=1, le=10)
    pending_task_limit: int = Field(default=20, ge=1, le=100)

    @field_validator("canvas_origins", mode="before")
    @classmethod
    def validate_canvas_origins(cls, origins):
        if isinstance(origins, str):
            try:
                origins = json.loads(origins)
            except ValueError:
                raise ValueError("Canvas origins require a JSON list") from None
        if not isinstance(origins, (list, tuple)):
            raise ValueError("Canvas origins require a list")
        if len(origins) > 20:
            raise ValueError("Canvas origin limit")
        validated = tuple(canvas_origin(origin) for origin in origins)
        if len(set(validated)) != len(validated):
            raise ValueError("Duplicate Canvas origin")
        return validated

    def readiness(self) -> dict[str, bool]:
        return {
            "database": bool(self.database_url),
            "authentication": bool(
                self.clerk_issuer and self.clerk_jwt_key and self.authorized_parties
            ),
            "meta_model": bool(self.meta_api_key),
        }
