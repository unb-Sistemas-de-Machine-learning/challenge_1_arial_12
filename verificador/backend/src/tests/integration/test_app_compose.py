"""Comportamento HTTP da nova API e preservação do stub legado."""

import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.core.config import settings as settings_module
from src.core.config.settings import Settings

BACKEND_DIR = Path(__file__).resolve().parents[3]


def load_app(relative_path: str):
    filename = BACKEND_DIR / relative_path
    module_name = relative_path.replace("/", "_").replace(".", "_")
    spec = importlib.util.spec_from_file_location(module_name, filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


def test_nova_api_responde_health_e_aplica_cors(monkeypatch) -> None:
    custom = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://db/teste",
        cors_origins=["https://permitida.example"],
    )
    monkeypatch.setattr(settings_module, "get_settings", lambda: custom)
    with TestClient(load_app("src/main.py")) as client:
        health = client.get("/health")
        preflight = client.options(
            "/health",
            headers={
                "Origin": "https://permitida.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert client.get("/verificar").status_code == 404
        assert client.get("/saude").status_code == 404

    assert health.status_code == 200
    assert health.json() == {"ok": True}
    assert (
        preflight.headers["access-control-allow-origin"] == "https://permitida.example"
    )


def test_erro_de_inicializacao_nomeia_database_url(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(
        settings_module, "get_settings", lambda: Settings(_env_file=None)
    )

    with pytest.raises(ValidationError) as error:
        load_app("src/main.py")
    assert "DATABASE_URL" in str(error.value)


def test_stub_legado_continua_respondendo_verificar(monkeypatch) -> None:
    custom = Settings(_env_file=None, database_url="postgresql+asyncpg://db/teste")
    monkeypatch.setattr(settings_module, "get_settings", lambda: custom)
    with TestClient(load_app("main.py")) as client:
        assert client.get("/health").json() == {"ok": True}
        assert client.get("/saude").status_code == 404
        response = client.post("/verificar", json={"trecho": "Uma alegação de teste"})

    assert response.status_code == 200
    assert response.json()["estado"] == "exagera"
    assert response.json()["estudo"]["titulo"] == "(mock) Estudo de exemplo"
