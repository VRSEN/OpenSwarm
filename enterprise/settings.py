from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnterpriseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "OpenSwarm Enterprise"
    environment: str = Field(default="development", alias="ENVIRONMENT")
    database_url: str = Field(default="sqlite:///./openswarm_enterprise.db", alias="DATABASE_URL")
    redis_url: str | None = Field(default=None, alias="REDIS_URL")
    secret_key: str = Field(default="change-me-in-production", alias="ENTERPRISE_SECRET_KEY")
    encryption_key: str = Field(default="", alias="ENTERPRISE_ENCRYPTION_KEY")
    access_token_minutes: int = Field(default=480, alias="ACCESS_TOKEN_MINUTES")
    cors_origins: str = Field(default="http://localhost:8080,http://localhost:5173", alias="CORS_ORIGINS")
    rate_limit_per_minute: int = Field(default=120, alias="RATE_LIMIT_PER_MINUTE")
    max_request_bytes: int = Field(default=10_000_000, alias="MAX_REQUEST_BYTES")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> EnterpriseSettings:
    return EnterpriseSettings()

