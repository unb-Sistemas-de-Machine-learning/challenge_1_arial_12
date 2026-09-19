"""Testes HTTP locais do contrato publicado pela aplicação."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.core.config import settings as settings_module
from src.core.config.settings import Settings

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "veredito_fase01.json"


@pytest.fixture
def create_app(monkeypatch):
    custom = Settings(_env_file=None, database_url="url-invalida")
    monkeypatch.setattr(settings_module, "get_settings", lambda: custom)
    from src.main import criar_app

    return criar_app


def test_verificar_preserva_payload_do_stub(create_app) -> None:
    esperado = json.loads(FIXTURE.read_text(encoding="utf-8"))
    with TestClient(create_app()) as client:
        response = client.post(
            "/verificar",
            json={"trecho": "trecho selecionado", "url": "file:///pagina-teste.html"},
        )
        assert response.status_code == 200
        assert response.json() == esperado
        assert (
            client.post("/verificar", json={"trecho": "outro trecho"}).json()
            == esperado
        )


def test_entrada_estruturalmente_invalida_retorna_422(create_app) -> None:
    with TestClient(create_app()) as client:
        response = client.post("/verificar", json={"url": "file:///pagina-teste.html"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "trecho"


def test_health_nao_depende_de_database_url(create_app) -> None:
    with TestClient(create_app()) as client:
        assert client.get("/health").json() == {"ok": True}
        assert client.get("/health").status_code == 200
        assert client.get("/saude").status_code == 404


def test_docs_e_openapi_publicam_contrato_e_exemplos(create_app) -> None:
    with TestClient(create_app()) as client:
        assert client.get("/docs").status_code == 200
        schema = client.get("/openapi.json").json()

    assert "/verificar" in schema["paths"]
    assert "/health" in schema["paths"]
    operacao = schema["paths"]["/verificar"]["post"]
    assert operacao["requestBody"]["content"]["application/json"]["examples"]
    assert operacao["responses"]["200"]["content"]["application/json"]["example"]
    assert schema["components"]["schemas"]["Estado"]["enum"] == [
        "sustenta",
        "exagera",
        "nada_encontrado",
    ]
    assert "trecho" in schema["components"]["schemas"]["Pedido"]["required"]
    assert set(schema["components"]["schemas"]["Veredito"]["required"]) == {
        "estado",
        "estudo",
        "termos",
        "justificativa",
    }
    assert set(schema["components"]["schemas"]["Estudo"]["required"]) == {
        "titulo",
        "ano",
        "doi",
        "retratado",
    }


def test_cors_da_extensao_permanece_disponivel(create_app) -> None:
    with TestClient(create_app()) as client:
        response = client.options(
            "/verificar",
            headers={
                "Origin": "chrome-extension://exemplo",
                "Access-Control-Request-Method": "POST",
            },
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
