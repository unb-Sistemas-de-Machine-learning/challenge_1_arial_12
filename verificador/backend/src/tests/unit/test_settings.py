"""Configuração isolada: nenhum teste depende do .env pessoal."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.core.config.settings import BACKEND_DIR, Settings, get_settings

ENV_KEYS = (
    "APP_DEBUG",
    "OPENAI_API_KEY",
    "DATABASE_URL",
    "OPENALEX_MAILTO",
    "CORS_ORIGINS",
)


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_configuracao_valida_sem_arquivo_env() -> None:
    settings = Settings(
        _env_file=None,
        app_debug="true",
        openai_api_key="sk-exemplo",
        database_url="postgresql+asyncpg://usuario:senha@db:5432/verificador",
        openalex_mailto="contato@example.com",
        cors_origins=["https://example.com"],
    )

    assert settings.app_debug is True
    assert settings.openai_api_key.get_secret_value() == "sk-exemplo"
    assert settings.database_url.get_secret_value().endswith("/verificador")
    assert settings.openalex_mailto == "contato@example.com"
    assert settings.cors_origins == ["https://example.com"]


@pytest.mark.parametrize("database_url", [None, "", "   "])
def test_database_url_ausente_ou_vazia_falha(database_url: str | None) -> None:
    values = {} if database_url is None else {"database_url": database_url}
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_chaves_opcionais_vazias_e_cors_padrao() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://db/verificador",
        openai_api_key="",
        openalex_mailto=" ",
    )
    assert settings.app_debug is False
    assert settings.openai_api_key is None
    assert settings.openalex_mailto is None
    assert settings.cors_origins == ["*"]


def test_segredos_nao_aparecem_em_repr_ou_erro() -> None:
    key = "sk-valor-super-secreto"
    database_url = "postgresql+asyncpg://usuario:senha-super-secreta@db/verificador"
    settings = Settings(_env_file=None, openai_api_key=key, database_url=database_url)
    assert key not in repr(settings)
    assert database_url not in repr(settings)
    assert "senha-super-secreta" not in repr(settings)

    with pytest.raises(ValidationError) as error:
        Settings(
            _env_file=None,
            openai_api_key=key,
            database_url=database_url,
            app_debug="invalido",
        )
    assert key not in str(error.value)
    assert database_url not in str(error.value)


def test_env_file_e_sobrescrita_por_ambiente(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "APP_DEBUG=true\nDATABASE_URL=postgresql+asyncpg://db/original\n"
        'CORS_ORIGINS=["https://arquivo.example"]\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://db/sobrescrito")
    settings = Settings(_env_file=env_file)
    assert settings.app_debug is True
    assert settings.database_url.get_secret_value().endswith("/sobrescrito")
    assert settings.cors_origins == ["https://arquivo.example"]


def test_caminho_padrao_do_env_nao_depende_do_diretorio_atual() -> None:
    assert Settings.model_config["env_file"] == BACKEND_DIR / ".env"


def test_get_settings_usa_cache_e_permite_sobrescrita_em_teste(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://db/primeiro")
    first = get_settings()
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://db/segundo")
    assert get_settings() is first

    get_settings.cache_clear()
    second = get_settings()
    assert second is not first
    assert second.database_url.get_secret_value().endswith("/segundo")
