"""Configuração isolada: nenhum teste depende do .env pessoal."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.core.config.settings import BACKEND_DIR, Settings, get_settings

ENV_KEYS = (
    "APP_DEBUG",
    "LLM_PROVEDOR",
    "LLM_API_KEY",
    "LLM_MODELO",
    "LLM_TIMEOUT_SEGUNDOS",
    "LLM_MAX_TENTATIVAS",
    "LLM_FORMATO_JSON",
    "DATABASE_URL",
    "OPENALEX_MAILTO",
    "OPENALEX_API_KEY",
    "OPENALEX_RESULTADOS_POR_BUSCA",
    "OPENALEX_TIMEOUT_SEGUNDOS",
    "OPENALEX_MAX_TENTATIVAS",
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
        llm_api_key="sk-exemplo",
        database_url="postgresql+asyncpg://usuario:senha@db:5432/verificador",
        openalex_mailto="contato@example.com",
        cors_origins=["https://example.com"],
    )

    assert settings.app_debug is True
    assert settings.llm_api_key.get_secret_value() == "sk-exemplo"
    assert settings.database_url.get_secret_value().endswith("/verificador")
    assert settings.openalex_mailto == "contato@example.com"
    assert settings.cors_origins == ["https://example.com"]


def test_chave_da_openalex_e_segredo_e_some_do_repr() -> None:
    chave = "oa-chave-super-secreta"
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://db/v",
        openalex_api_key=chave,
    )
    assert settings.openalex_api_key.get_secret_value() == chave
    assert chave not in repr(settings)

    vazia = Settings(
        _env_file=None, database_url="postgresql+asyncpg://db/v", openalex_api_key="  "
    )
    assert vazia.openalex_api_key is None


def test_ajustes_da_openalex_tem_padrao_e_faixa() -> None:
    padrao = Settings(_env_file=None, database_url="postgresql+asyncpg://db/v")
    assert padrao.openalex_resultados_por_busca == 10
    assert padrao.openalex_timeout_segundos == 10.0
    assert padrao.openalex_max_tentativas == 3

    ajustado = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://db/v",
        openalex_resultados_por_busca="25",
        openalex_timeout_segundos="3.5",
        openalex_max_tentativas="1",
    )
    assert ajustado.openalex_resultados_por_busca == 25
    assert ajustado.openalex_timeout_segundos == 3.5
    assert ajustado.openalex_max_tentativas == 1


@pytest.mark.parametrize(
    "invalido",
    [
        {"openalex_resultados_por_busca": 0},
        {"openalex_timeout_segundos": 0},
        {"openalex_max_tentativas": 0},
        {"openalex_max_tentativas": 6},
    ],
)
def test_ajustes_da_openalex_fora_da_faixa_falham(invalido: dict) -> None:
    """Zero tentativa ou timeout zero derrubaria toda busca, em silêncio."""
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="postgresql+asyncpg://db/v", **invalido)


@pytest.mark.parametrize("database_url", [None, "", "   "])
def test_database_url_ausente_ou_vazia_falha(database_url: str | None) -> None:
    values = {} if database_url is None else {"database_url": database_url}
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_chaves_opcionais_vazias_e_cors_padrao() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://db/verificador",
        llm_api_key="",
        openalex_mailto=" ",
    )
    assert settings.app_debug is False
    assert settings.llm_api_key is None
    assert settings.openalex_mailto is None
    assert settings.cors_origins == ["*"]


def test_segredos_nao_aparecem_em_repr_ou_erro() -> None:
    key = "sk-valor-super-secreto"
    database_url = "postgresql+asyncpg://usuario:senha-super-secreta@db/verificador"
    settings = Settings(_env_file=None, llm_api_key=key, database_url=database_url)
    assert key not in repr(settings)
    assert database_url not in repr(settings)
    assert "senha-super-secreta" not in repr(settings)

    with pytest.raises(ValidationError) as error:
        Settings(
            _env_file=None,
            llm_api_key=key,
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
