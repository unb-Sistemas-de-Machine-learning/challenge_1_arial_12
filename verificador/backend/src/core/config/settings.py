"""Configuração única do backend, carregada e validada na inicialização."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
        populate_by_name=True,
    )

    app_debug: bool = False
    openai_api_key: SecretStr | None = None
    database_url: SecretStr = Field(validation_alias="DATABASE_URL")
    openalex_mailto: str | None = None
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    rate_limit_max_requests: int = 30
    rate_limit_window_seconds: int = 60

    @field_validator("database_url", mode="before")
    @classmethod
    def require_database_url(cls, value: str | SecretStr) -> str | SecretStr:
        raw_value = value.get_secret_value() if isinstance(value, SecretStr) else value
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise ValueError("DATABASE_URL não pode estar vazia")
        return value

    @field_validator("openai_api_key", "openalex_mailto", mode="before")
    @classmethod
    def optional_blank_as_none(
        cls, value: str | SecretStr | None
    ) -> str | SecretStr | None:
        raw_value = value.get_secret_value() if isinstance(value, SecretStr) else value
        if isinstance(raw_value, str) and not raw_value.strip():
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    """Retorna a configuração validada; testes podem chamar cache_clear()."""
    return Settings()
