"""Limite de requisições por origem e sua interação com CORS por ambiente."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from src.core.config import settings as settings_module
from src.core.config.settings import Settings
from src.main import criar_app

DATABASE_URL_FALSA = "postgresql+asyncpg://usuario:segredo@host-inexistente/teste"


class RelogioFalso:
    """Avança sob controle do teste, sem depender de `time.sleep`."""

    def __init__(self, agora: float = 0.0) -> None:
        self._agora = agora

    def avancar(self, segundos: float) -> None:
        self._agora += segundos

    def __call__(self) -> float:
        return self._agora


@pytest.fixture
def preparar_app(monkeypatch) -> Callable[..., tuple[TestClient, RelogioFalso]]:
    def _preparar(
        rate_limit_max_requests: int = 2,
        rate_limit_window_seconds: int = 10,
        **outros,
    ) -> tuple[TestClient, RelogioFalso]:
        custom = Settings(
            _env_file=None,
            database_url=DATABASE_URL_FALSA,
            rate_limit_max_requests=rate_limit_max_requests,
            rate_limit_window_seconds=rate_limit_window_seconds,
            **outros,
        )
        monkeypatch.setattr(settings_module, "get_settings", lambda: custom)
        relogio = RelogioFalso()
        api = criar_app(relogio_limite=relogio)
        return TestClient(api), relogio

    return _preparar


def _verificar(client: TestClient, headers: dict[str, str], trecho: str = "trecho"):
    return client.post("/verificar", json={"trecho": trecho}, headers=headers)


def test_429_com_retry_after_apos_o_limite(preparar_app) -> None:
    client, _relogio = preparar_app()
    headers = {"Origin": "https://permitida.example"}

    with client:
        primeira = _verificar(client, headers)
        segunda = _verificar(client, headers)
        terceira = _verificar(client, headers)

    assert primeira.status_code == 200
    assert segunda.status_code == 200
    assert terceira.status_code == 429
    assert terceira.headers["Retry-After"] == "10"
    corpo = terceira.json()
    assert corpo == {
        "codigo": "limite_excedido",
        "mensagem": "Limite de solicitações excedido.",
    }
    assert "X-Correlation-ID" in terceira.headers


def test_janela_expira_e_a_mesma_origem_volta_a_passar(preparar_app) -> None:
    client, relogio = preparar_app()
    headers = {"Origin": "https://permitida.example"}

    with client:
        _verificar(client, headers)
        _verificar(client, headers)
        bloqueada = _verificar(client, headers)
        relogio.avancar(10)
        liberada = _verificar(client, headers)

    assert bloqueada.status_code == 429
    assert liberada.status_code == 200


def test_origens_diferentes_tem_contagem_isolada(preparar_app) -> None:
    client, _relogio = preparar_app()
    origem_a = {"Origin": "https://a.example"}
    origem_b = {"Origin": "https://b.example"}

    with client:
        _verificar(client, origem_a)
        _verificar(client, origem_a)
        bloqueada_a = _verificar(client, origem_a)
        livre_b = _verificar(client, origem_b)

    assert bloqueada_a.status_code == 429
    assert livre_b.status_code == 200


def test_health_nunca_e_limitado(preparar_app) -> None:
    client, _relogio = preparar_app()
    headers = {"Origin": "https://permitida.example"}

    with client:
        _verificar(client, headers)
        _verificar(client, headers)
        _verificar(client, headers)  # já esgota o limite dessa origem
        respostas = [client.get("/health", headers=headers) for _ in range(5)]

    assert all(resposta.status_code == 200 for resposta in respostas)


def test_cors_em_debug_aceita_a_origem_liberada(monkeypatch) -> None:
    custom = Settings(
        _env_file=None,
        database_url=DATABASE_URL_FALSA,
        app_debug=True,
        cors_origins=["*"],
    )
    monkeypatch.setattr(settings_module, "get_settings", lambda: custom)

    with TestClient(criar_app()) as client:
        resposta = client.get("/health", headers={"Origin": "https://qualquer.example"})

    assert resposta.headers["access-control-allow-origin"] == "*"


def test_cors_fora_do_debug_so_aceita_a_lista_configurada(monkeypatch) -> None:
    custom = Settings(
        _env_file=None,
        database_url=DATABASE_URL_FALSA,
        app_debug=False,
        cors_origins=["https://permitida.example"],
    )
    monkeypatch.setattr(settings_module, "get_settings", lambda: custom)

    with TestClient(criar_app()) as client:
        permitida = client.get(
            "/health", headers={"Origin": "https://permitida.example"}
        )
        bloqueada = client.get("/health", headers={"Origin": "https://outra.example"})

    assert (
        permitida.headers["access-control-allow-origin"] == "https://permitida.example"
    )
    assert "access-control-allow-origin" not in bloqueada.headers
