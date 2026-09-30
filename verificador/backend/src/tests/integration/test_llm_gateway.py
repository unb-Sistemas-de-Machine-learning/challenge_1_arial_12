"""A camada de LLM atrás do gateway: injeção do dublê e erros do contrato 011.

Nenhuma rota de produção usa o LLM ainda, então o teste pendura uma rota
própria na aplicação — do jeito que o Triador e o Juiz vão receber o cliente.
"""

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import BaseModel

from src.api.schemas.erro import CodigoErro, Erro
from src.core.config import settings as settings_module
from src.core.config.settings import Settings
from src.services import llm
from src.services.llm import (
    ClienteLLM,
    FalhaTransitoria,
    LLMRecusouOPedido,
    obter_cliente_llm,
)
from src.tests.dubles.llm import DubleLLM

CHAVE = "gsk-chave-super-secreta-de-teste"


class Variacoes(BaseModel):
    buscas: list[str]


@pytest.fixture
def api(monkeypatch):
    custom = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://usuario:segredo@host-inexistente/teste",
        llm_api_key=CHAVE,
    )
    monkeypatch.setattr(settings_module, "get_settings", lambda: custom)
    monkeypatch.setattr(llm, "_compartilhado", None)
    from src.main import criar_app

    app = criar_app()

    @app.post("/teste-llm")
    async def rota(cliente: ClienteLLM = Depends(obter_cliente_llm)) -> Variacoes:
        return await cliente.gerar("Gere buscas", Variacoes)

    return app


def injetar(app, duble: DubleLLM, **opcoes) -> None:
    cliente = ClienteLLM(duble, **opcoes)
    app.dependency_overrides[obter_cliente_llm] = lambda: cliente


def _conferir_erro(resposta, status: int, codigo: CodigoErro) -> None:
    assert resposta.status_code == status
    assert Erro.model_validate(resposta.json()).codigo == codigo
    assert "X-Correlation-ID" in resposta.headers


def test_duble_injetado_responde_pela_rota(api) -> None:
    injetar(api, DubleLLM({"buscas": ["a", "b"]}))

    with TestClient(api) as client:
        resposta = client.post("/teste-llm")

    assert resposta.status_code == 200
    assert resposta.json() == {"buscas": ["a", "b"]}


def test_timeout_vira_504_llm_timeout(api) -> None:
    injetar(api, DubleLLM({"buscas": []}, atraso_segundos=5), timeout_segundos=0.05)

    with TestClient(api) as client:
        resposta = client.post("/teste-llm")

    _conferir_erro(resposta, 504, CodigoErro.LLM_TIMEOUT)


@pytest.mark.parametrize(
    "passo",
    [
        FalhaTransitoria("503"),
        LLMRecusouOPedido("401"),
        "isto não é JSON",
    ],
    ids=["indisponivel", "recusa", "resposta_invalida"],
)
def test_falhas_do_provedor_viram_503_llm_indisponivel(api, passo) -> None:
    async def sem_espera(_segundos: float) -> None:
        return None

    injetar(api, DubleLLM(passo), dormir=sem_espera)

    with TestClient(api) as client:
        resposta = client.post("/teste-llm")

    _conferir_erro(resposta, 503, CodigoErro.LLM_INDISPONIVEL)
    assert "JSON" not in resposta.text
    assert "401" not in resposta.text


def test_configuracao_sem_chave_vira_503_e_nao_500(api, monkeypatch) -> None:
    sem_chave = Settings(_env_file=None, database_url="postgresql+asyncpg://db/v")
    monkeypatch.setattr(settings_module, "get_settings", lambda: sem_chave)

    with TestClient(api) as client:
        resposta = client.post("/teste-llm")

    _conferir_erro(resposta, 503, CodigoErro.LLM_INDISPONIVEL)
