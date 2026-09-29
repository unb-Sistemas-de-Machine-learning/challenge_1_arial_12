"""Testes HTTP da rota de feedback."""

import pytest
from fastapi.testclient import TestClient

from src.api.gateway import routes
from src.core.config import settings as settings_module
from src.core.config.settings import Settings


@pytest.fixture
def create_app(monkeypatch):
    custom = Settings(
        _env_file=None,
        database_url=(
            "postgresql+asyncpg://usuario:senha@host-inexistente/verificador"
        ),
    )
    monkeypatch.setattr(settings_module, "get_settings", lambda: custom)
    from src.main import criar_app

    return criar_app


def test_feedback_sucesso(create_app, monkeypatch) -> None:
    calls = []

    async def mock_persistir(fabrica, veredicto_id, util):
        calls.append((veredicto_id, util))

    monkeypatch.setattr(routes, "persistir_feedback", mock_persistir)

    with TestClient(create_app()) as client:
        response = client.post(
            "/feedback",
            json={
                "veredicto_id": 123,
                "util": True,
                "data_hora": "2023-10-15T12:00:00Z",
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "recebido"}
    assert calls == [(123, True)]


def test_feedback_payload_invalido(create_app) -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/feedback",
            json={
                "veredicto_id": "nao-eh-int",
                "util": "talvez",
            },
        )
    assert response.status_code == 422


def test_feedback_falha_banco_nao_quebra_resposta(
    create_app, monkeypatch, caplog
) -> None:
    async def mock_registrar_feedback(*args, **kwargs):
        raise Exception("Banco caiu")

    monkeypatch.setattr(routes, "registrar_feedback", mock_registrar_feedback)

    # Need a mock async session context manager
    class MockSessao:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    def mock_fabrica():
        return MockSessao()

    with TestClient(create_app()) as client:
        # Patching inside the background task means we have to make sure it doesn't fail getting the session
        client.app.state.fabrica_de_sessoes = mock_fabrica

        response = client.post(
            "/feedback",
            json={
                "veredicto_id": 456,
                "util": False,
                "data_hora": "2023-10-15T12:00:00Z",
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "recebido"}
    assert "Erro ao persistir feedback" in caplog.text
