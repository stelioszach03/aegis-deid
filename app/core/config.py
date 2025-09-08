from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field

# Support both Pydantic v1 (pydantic.BaseSettings) and v2 (pydantic-settings)
try:  # Pydantic v2 preferred import
    from pydantic_settings import BaseSettings, SettingsConfigDict  # type: ignore
    IS_PYDANTIC_V2 = True
except Exception:  # Fallback for Pydantic v1
    IS_PYDANTIC_V2 = False
    try:
        from pydantic import BaseSettings  # type: ignore
    except Exception as e:  # pragma: no cover
        raise ImportError(
            "pydantic-settings is required when using Pydantic v2."
        ) from e

    def SettingsConfigDict(**kwargs):  # type: ignore
        return kwargs


class Settings(BaseSettings):
    # App
    app_name: str = Field(default="DeID-MVP", env="APP_NAME")
    app_env: Literal["dev", "prod"] = Field(default="dev", env="APP_ENV")
    app_version: str = Field(default="0.1.0", env="APP_VERSION")

    # Infra
    postgres_dsn: str = Field(
        default="postgresql+psycopg://deid:deidpass@localhost:5432/deid",
        env="POSTGRES_DSN",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    # Security
    api_key: Optional[str] = Field(default=None, env="API_KEY")
    cors_allow_origins: str = Field(
        default="http://localhost:8000,http://localhost:3000", env="CORS_ALLOW_ORIGINS"
    )

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # De-ID
    deid_default_policy: Literal["mask", "hash", "redact"] = Field(
        default="mask", env="DEID_DEFAULT_POLICY"
    )
    deid_salt: str = Field(default="change-me-salt", env="DEID_SALT")
    max_text_size: int = Field(default=500_000, env="MAX_TEXT_SIZE")
    request_body_limit: int = Field(default=1_000_000, env="REQUEST_BODY_LIMIT")

    # Pydantic v2 settings model config
    if IS_PYDANTIC_V2:
        # Ignore extra/unknown keys from environment/.env (e.g., Docker-only vars)
        model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")
    else:
        # Pydantic v1 compatibility
        class Config:  # type: ignore
            env_file = ".env"
            case_sensitive = False
            extra = "ignore"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
