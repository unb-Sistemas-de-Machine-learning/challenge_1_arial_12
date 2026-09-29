"""A rota pública de busca: responde, ordena e erra dentro do contrato.

Nada aqui toca a rede: o cliente compartilhado é trocado por um que usa
`httpx.MockTransport`, o mesmo arranjo dos testes unitários do cliente.
"""

import json
import logging
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from src.api.schemas.erro import CodigoErro
from src.core.config import settings as settings_module
from src.core.config.settings import Settings
from src.services import openalex as openalex_tool
from src.services.openalex import (
    ClienteOpenAlex,
    OpenAlexIndisponivel,
    OpenAlexRecusouABusca,
)

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "openalex"
    / "busca_polilaminina.json"
)


def montar_app(monkeypatch, *, app_debug: bool = False):
    custom = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://usuario:segredo@host-inexistente/teste",
        app_debug=app_debug,
        openalex_mailto="contato@example.com",
    )
    monkeypatch.setattr(settings_module, "get_settings", lambda: custom)
    from src.main import criar_app

    return criar_app()


def instalar_cliente(monkeypatch, responder) -> None:
    cliente = ClienteOpenAlex(
        mailto="contato@example.com",
        cliente_http=httpx.AsyncClient(transport=httpx.MockTransport(responder)),
        max_tentativas=1,
    )
    monkeypatch.setattr(openalex_tool, "_compartilhado", cliente)


def resposta_gravada(_requisicao: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_a_rota_existe_sem_app_debug(monkeypatch) -> None:
    """É rota pública: não depende de modo de depuração para existir."""
    instalar_cliente(monkeypatch, resposta_gravada)

    with TestClient(montar_app(monkeypatch, app_debug=False)) as client:
        resposta = client.post("/buscar", json={"buscas": ["polylaminin"]})

    assert resposta.status_code == 200


def test_a_rota_esta_documentada_no_openapi(monkeypatch) -> None:
    with TestClient(montar_app(monkeypatch)) as client:
        spec = client.get("/openapi.json").json()

    assert "/buscar" in spec["paths"]
    respostas = spec["paths"]["/buscar"]["post"]["responses"]
    assert {"200", "422", "503"} <= set(respostas)


def test_busca_devolve_os_trabalhos(monkeypatch) -> None:
    instalar_cliente(monkeypatch, resposta_gravada)

    with TestClient(montar_app(monkeypatch)) as client:
        resposta = client.post(
            "/buscar",
            json={"buscas": ["polylaminin spinal cord injury"]},
        )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["buscas_com_falha"] == {}
    assert len(corpo["trabalhos"]) == 5
    primeiro = corpo["trabalhos"][0]
    assert set(primeiro) == {
        "id",
        "titulo",
        "ano",
        "doi",
        "retratado",
        "abstract",
        "relevancia",
        "citacoes",
    }
    assert primeiro["doi"] == "10.1096/fj.10-157628"
    assert primeiro["id"] == "W2110406916"
    # 49 casaram na OpenAlex; a resposta traz os 5 mais relevantes.
    assert corpo["total_por_busca"] == {"polylaminin spinal cord injury": 49}
    pontuacoes = [t["relevancia"] for t in corpo["trabalhos"]]
    assert pontuacoes == sorted(pontuacoes, reverse=True)


def test_varias_buscas_chegam_a_openalex_intactas(monkeypatch) -> None:
    """A sintaxe booleana não pode ser tocada no caminho HTTP → cliente."""
    recebidas: list[str] = []

    def responder(requisicao: httpx.Request) -> httpx.Response:
        recebidas.append(requisicao.url.params["search"])
        return httpx.Response(200, json={"results": []})

    instalar_cliente(monkeypatch, responder)
    consulta = '("Service Design" OR "UX") AND ("ITSM" OR "ITIL")'

    with TestClient(montar_app(monkeypatch)) as client:
        resposta = client.post("/buscar", json={"buscas": [consulta, "service portal"]})

    assert resposta.status_code == 200
    assert sorted(recebidas) == sorted([consulta, "service portal"])


@pytest.mark.parametrize(
    ("erro", "status", "codigo"),
    [
        (OpenAlexIndisponivel("fora do ar"), 503, CodigoErro.OPENALEX_INDISPONIVEL),
        (OpenAlexRecusouABusca("consulta ruim"), 422, CodigoErro.ENTRADA_INVALIDA),
        (ValueError("lista sem busca útil"), 422, CodigoErro.ENTRADA_INVALIDA),
    ],
)
def test_falha_da_busca_usa_o_contrato_de_erro(
    monkeypatch, erro: Exception, status: int, codigo: CodigoErro
) -> None:
    """Nada de traceback nem de mensagem crua: o contrato da spec 011 vale aqui."""

    async def explodir(*_args: object, **_kwargs: object) -> None:
        raise erro

    instalar_cliente(monkeypatch, resposta_gravada)
    monkeypatch.setattr(openalex_tool.ClienteOpenAlex, "buscar_varias", explodir)

    with TestClient(montar_app(monkeypatch)) as client:
        resposta = client.post("/buscar", json={"buscas": ["polylaminin"]})

    assert resposta.status_code == status
    corpo = resposta.json()
    assert set(corpo) == {"codigo", "mensagem"}
    assert corpo["codigo"] == codigo.value
    assert str(erro) not in corpo["mensagem"]


def test_sem_mailto_a_culpa_nao_cai_em_quem_chamou(monkeypatch, caplog) -> None:
    """Configuração faltando é 503, e não 422.

    Com 422 a resposta manda revisar uma busca que estava certa — foi
    exatamente o que aconteceu com a primeira versão desta rota.
    """
    monkeypatch.setattr(openalex_tool, "_compartilhado", None)
    custom = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://usuario:segredo@host-inexistente/teste",
        openalex_mailto=None,
    )
    monkeypatch.setattr(settings_module, "get_settings", lambda: custom)
    from src.main import criar_app

    with caplog.at_level(logging.WARNING, logger="verificador.gateway"):
        app = criar_app()
        with TestClient(app) as client:
            resposta = client.post("/buscar", json={"buscas": ["polylaminin"]})

    assert resposta.status_code == 503
    assert resposta.json()["codigo"] == CodigoErro.OPENALEX_INDISPONIVEL.value
    registros = "\n".join(r.message for r in caplog.records)
    # Na subida e no uso: quem sobe o servidor vê antes de tentar a primeira vez.
    assert "OPENALEX_MAILTO está vazio" in registros
    assert "OPENALEX_MAILTO é obrigatório" in registros


@pytest.mark.parametrize(
    "corpo",
    [{"buscas": []}, {"quantidade": 5}, {"buscas": "uma string só"}],
)
def test_corpo_invalido_da_422(monkeypatch, corpo: dict) -> None:
    with TestClient(montar_app(monkeypatch)) as client:
        resposta = client.post("/buscar", json=corpo)

    assert resposta.status_code == 422
    assert resposta.json()["codigo"] == CodigoErro.ENTRADA_INVALIDA.value
