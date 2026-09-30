"""Configuração única do backend, carregada e validada na inicialização."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

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
    # Só camada gratuita: Groq ou Gemini, ambos pela API compatível com a
    # OpenAI. Endereço e modelo padrão de cada um ficam em src/services/llm.py.
    llm_provedor: Literal["groq", "gemini"] = "groq"
    llm_api_key: SecretStr | None = None
    # Vazio usa o modelo padrão do provedor.
    llm_modelo: str | None = None
    # Tempo total da chamada, tentativas incluídas: é quanto o leitor espera.
    llm_timeout_segundos: float = Field(default=15.0, gt=0)
    llm_max_tentativas: int = Field(default=2, ge=1, le=5)
    # `json_object` para modelos que não aceitam saída estruturada.
    llm_formato_json: Literal["json_schema", "json_object"] = "json_schema"
    database_url: SecretStr = Field(validation_alias="DATABASE_URL")
    openalex_mailto: str | None = None
    # Chave gratuita da OpenAlex. Opcional, mas sob carga ela derruba busca
    # "anônima" com 503 — e tráfego só com mailto conta como anônimo.
    openalex_api_key: SecretStr | None = None
    # O teto de resultados por busca não mora aqui: quem aplica é
    # `limitar_quantidade`, em src/services/openalex.py, para que a mesma regra
    # valha para a configuração e para o parâmetro que o agente passa.
    openalex_resultados_por_busca: int = Field(default=10, ge=1)
    openalex_timeout_segundos: float = Field(default=10.0, gt=0)
    openalex_max_tentativas: int = Field(default=3, ge=1, le=5)
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

    @field_validator(
        "llm_api_key",
        "llm_modelo",
        "openalex_api_key",
        "openalex_mailto",
        mode="before",
    )
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
