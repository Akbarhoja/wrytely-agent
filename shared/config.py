from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENT_", extra="ignore")
    database_url: SecretStr | None = None
    clerk_issuer: str | None = None
    clerk_jwt_key: SecretStr | None = None
    authorized_parties: list[str] = Field(default_factory=list)
    meta_api_key: SecretStr | None = None
    meta_model: str = "muse-spark-1.3"
    whatsapp_app_secret: SecretStr | None = None
    whatsapp_verify_token: SecretStr | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_business_account_id: str | None = None
    max_episode_turns: int = Field(default=6, ge=1, le=20)
    lease_seconds: int = Field(default=300, ge=30, le=3600)
    max_attempts: int = Field(default=3, ge=1, le=10)
    pending_task_limit: int = Field(default=20, ge=1, le=100)

    def readiness(self) -> dict[str, bool]:
        return {
            "database": bool(self.database_url),
            "authentication": bool(
                self.clerk_issuer and self.clerk_jwt_key and self.authorized_parties
            ),
            "meta_model": bool(self.meta_api_key),
        }
