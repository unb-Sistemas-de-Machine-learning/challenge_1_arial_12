"""A aplicação valida Settings antes de receber qualquer requisição."""

import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.core.config import settings as settings_module
from src.core.config.settings import Settings

MAIN_FILE = Path(__file__).resolve().parents[2] / "main.py"


def load_app():
    spec = importlib.util.spec_from_file_location("stub_settings_test", MAIN_FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


@pytest.mark.parametrize("database_url", [None, "", "   "])
def test_app_falha_na_inicializacao_sem_database_url(
    monkeypatch, database_url: str | None
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    values = {} if database_url is None else {"database_url": database_url}
    monkeypatch.setattr(
        settings_module, "get_settings", lambda: Settings(_env_file=None, **values)
    )
    with pytest.raises(ValidationError):
        load_app()


def test_app_inicia_sem_conectar_ao_banco_e_configura_cors(
    monkeypatch, capsys, caplog
) -> None:
    database_url = (
        "postgresql+asyncpg://usuario:senha-super-secreta@host-inexistente/verificador"
    )
    api_key = "sk-chave-super-secreta"
    custom = Settings(
        _env_file=None,
        database_url=database_url,
        openai_api_key=api_key,
        app_debug=True,
        cors_origins=["https://permitida.example"],
    )
    monkeypatch.setattr(settings_module, "get_settings", lambda: custom)
    app = load_app()
    assert app.debug is True

    with TestClient(app) as client:
        health = client.get("/health")
        assert health.json() == {"ok": True}
        verification = client.post(
            "/verificar", json={"trecho": "Uma alegação de teste"}
        )
        assert verification.status_code == 200
        permitted = client.options(
            "/verificar",
            headers={
                "Origin": "https://permitida.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        denied = client.options(
            "/verificar",
            headers={
                "Origin": "https://bloqueada.example",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert permitted.status_code == 200
    assert (
        permitted.headers["access-control-allow-origin"] == "https://permitida.example"
    )
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers
    output = capsys.readouterr()
    exposed = (
        output.out
        + output.err
        + caplog.text
        + health.text
        + verification.text
        + permitted.text
    )
    assert api_key not in exposed
    assert database_url not in exposed
