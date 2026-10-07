"""Testes HTTP do `/verificar`: a esteira Triador → Pesquisador → Juiz.

Nada aqui toca a rede. O LLM é o `DubleLLM` atrás de `obter_cliente_llm`, com
um roteiro em ordem (primeiro o Triador, depois o Juiz), e a OpenAlex é um
`httpx.MockTransport`. Sem banco, a gravação falha e o veredito volta com
`id = null`; o caminho com banco tem teste próprio, marcado com `exige_banco`.
"""

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from src.api.schemas.erro import CodigoErro, Erro
from src.core.config import settings as settings_module
from src.core.config.settings import Settings
from src.core.database.models import Base, Feedback, Veredito
from src.core.database.session import criar_motor
from src.services import llm
from src.services import openalex as openalex_tool
from src.services.llm import (
    ClienteLLM,
    FalhaTransitoria,
    LLMTempoEsgotado,
    obter_cliente_llm,
)
from src.services.openalex import ClienteOpenAlex
from src.tests.conftest import URL_DO_BANCO, exige_banco
from src.tests.dubles.esteira import banco_indisponivel
from src.tests.dubles.llm import DubleLLM

TRECHO = "A polilaminina regenera a medula espinhal de pessoas."
DOI = "10.1234/polilaminina"
ABSTRACT = "Polylaminin promoted axon regeneration in rats"

TERMOS_DO_TRIADOR = {
    "intervencao": "polylaminin",
    "desfecho": "axon regeneration",
    "condicao": "",
    "populacao": "",
}
RESPOSTA_DO_JUIZ = {
    "relacao": "parcial",
    "estado": "exagera",
    "doi": DOI,
    "evidencia": "promoted axon regeneration in rats",
    "justificativa": (
        "O estudo observou regeneração de axônios em ratos, mas a matéria "
        "promete o mesmo efeito em pessoas."
    ),
}


def corpo_openalex(*, com_trabalho: bool = True) -> dict:
    registros = []
    if com_trabalho:
        registros.append(
            {
                "id": "https://openalex.org/W1",
                "display_name": "Polylaminin and axon regeneration",
                "publication_year": 2019,
                "doi": f"https://doi.org/{DOI}",
                "is_retracted": False,
                "abstract_inverted_index": {
                    palavra: [posicao]
                    for posicao, palavra in enumerate(ABSTRACT.split())
                },
            }
        )
    return {"results": registros, "meta": {"count": len(registros)}}


@pytest.fixture
def montar(monkeypatch):
    """Monta a aplicação; `llm_api_key` e o banco variam por cenário."""

    def _montar(
        *, llm_api_key: str | None = None, database_url: str | None = None
    ) -> object:
        custom = Settings(
            _env_file=None,
            database_url=database_url
            or "postgresql+asyncpg://usuario:senha@host-inexistente/verificador",
            openalex_mailto="contato@example.com",
            llm_api_key=llm_api_key,
        )
        monkeypatch.setattr(settings_module, "get_settings", lambda: custom)
        monkeypatch.setattr(llm, "_compartilhado", None)
        monkeypatch.setattr(openalex_tool, "_compartilhado", None)
        if database_url is None:
            banco_indisponivel(monkeypatch)
        from src.main import criar_app

        return criar_app()

    return _montar


class OpenAlexFalsa:
    def __init__(self, status: int = 200, corpo: dict | None = None) -> None:
        self.status = status
        self.corpo = corpo if corpo is not None else corpo_openalex()
        self.buscas: list[str] = []

    def atender(self, requisicao: httpx.Request) -> httpx.Response:
        self.buscas.append(
            requisicao.url.params["filter"].replace("title_and_abstract.search:", "")
        )
        if self.status != 200:
            return httpx.Response(self.status, json={"error": "dublê"})
        return httpx.Response(200, json=self.corpo)


def instalar_openalex(monkeypatch, falsa: OpenAlexFalsa) -> None:
    cliente = ClienteOpenAlex(
        mailto="contato@example.com",
        cliente_http=httpx.AsyncClient(transport=httpx.MockTransport(falsa.atender)),
        max_tentativas=1,
    )
    monkeypatch.setattr(openalex_tool, "_compartilhado", cliente)


def instalar_llm(app, *roteiro, **opcoes) -> DubleLLM:
    async def sem_espera(_segundos: float) -> None:
        return None

    duble = DubleLLM(*roteiro)
    cliente = ClienteLLM(duble, dormir=sem_espera, **opcoes)
    app.dependency_overrides[obter_cliente_llm] = lambda: cliente
    return duble


def conferir_erro(resposta, status: int, codigo: CodigoErro) -> None:
    assert resposta.status_code == status
    assert Erro.model_validate(resposta.json()).codigo == codigo


# --- Caminho feliz ------------------------------------------------------------


def test_verificar_devolve_o_veredito_do_juiz(montar, monkeypatch) -> None:
    app = montar()
    openalex = OpenAlexFalsa()
    instalar_openalex(monkeypatch, openalex)
    duble = instalar_llm(app, TERMOS_DO_TRIADOR, RESPOSTA_DO_JUIZ)

    with TestClient(app) as client:
        resposta = client.post("/verificar", json={"trecho": TRECHO, "url": None})

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["estado"] == "exagera"
    assert corpo["estudo"] == {
        "titulo": "Polylaminin and axon regeneration",
        "ano": 2019,
        "doi": DOI,
        "retratado": False,
    }
    assert corpo["justificativa"] == RESPOSTA_DO_JUIZ["justificativa"]
    # Os conceitos do Triador, e não o `termos=[]` que o Juiz devolve.
    assert corpo["termos"] == ["polylaminin", "axon regeneration"]
    # Sem banco no teste: a gravação falha e o leitor recebe o veredito sem id.
    assert corpo["id"] is None
    # Triador e Juiz, nessa ordem; e a busca começa pelo trecho original.
    assert [c["nome_schema"] for c in duble.chamadas] == [
        "TermosDeBusca",
        "RespostaDoJuiz",
    ]
    assert openalex.buscas[0] == TRECHO


def test_sem_trabalhos_responde_nada_encontrado_sem_chamar_o_juiz(
    montar, monkeypatch
) -> None:
    app = montar()
    instalar_openalex(
        monkeypatch, OpenAlexFalsa(corpo=corpo_openalex(com_trabalho=False))
    )
    duble = instalar_llm(app, TERMOS_DO_TRIADOR, RESPOSTA_DO_JUIZ)

    with TestClient(app) as client:
        resposta = client.post("/verificar", json={"trecho": TRECHO})

    assert resposta.status_code == 200
    assert resposta.json()["estado"] == "nada_encontrado"
    assert resposta.json()["estudo"] is None
    assert len(duble.chamadas) == 1  # só o Triador


def test_triador_falhando_vira_triagem_indisponivel(montar, monkeypatch) -> None:
    """Sem tradução não há busca, e sem busca não há veredito a dar.

    O trecho cru em português casa com quase nada na OpenAlex, então seguir
    daqui terminaria em `nada_encontrado` — que o leitor lê como "não existe
    estudo" quando o que houve foi "não consegui procurar".
    """
    app = montar()
    openalex = OpenAlexFalsa()
    instalar_openalex(monkeypatch, openalex)
    duble = instalar_llm(
        app, FalhaTransitoria("503"), RESPOSTA_DO_JUIZ, max_tentativas=1
    )

    with TestClient(app) as client:
        resposta = client.post("/verificar", json={"trecho": TRECHO})

    conferir_erro(resposta, 503, CodigoErro.TRIAGEM_INDISPONIVEL)
    # Nada depois do Triador roda: a recusa vem antes de gastar requisição de
    # busca e a chamada de LLM do Juiz.
    assert openalex.buscas == []
    assert len(duble.chamadas) == 1


# --- Erros padronizados -------------------------------------------------------


def test_todas_as_buscas_falhando_vira_openalex_indisponivel(
    montar, monkeypatch
) -> None:
    app = montar()
    instalar_openalex(monkeypatch, OpenAlexFalsa(status=500))
    duble = instalar_llm(app, TERMOS_DO_TRIADOR, RESPOSTA_DO_JUIZ)

    with TestClient(app) as client:
        resposta = client.post("/verificar", json={"trecho": TRECHO})

    conferir_erro(resposta, 503, CodigoErro.OPENALEX_INDISPONIVEL)
    assert len(duble.chamadas) == 1  # o Juiz nem foi chamado


def test_todas_as_buscas_recusadas_viram_busca_recusada(montar, monkeypatch) -> None:
    """4xx é consulta errada, não serviço fora do ar — e o leitor lê a diferença."""
    app = montar()
    instalar_openalex(monkeypatch, OpenAlexFalsa(status=400))
    duble = instalar_llm(app, TERMOS_DO_TRIADOR, RESPOSTA_DO_JUIZ)

    with TestClient(app) as client:
        resposta = client.post("/verificar", json={"trecho": TRECHO})

    conferir_erro(resposta, 502, CodigoErro.BUSCA_RECUSADA)
    assert len(duble.chamadas) == 1  # o Juiz nem foi chamado


def test_juiz_estourando_o_tempo_vira_llm_timeout(montar, monkeypatch) -> None:
    app = montar()
    instalar_openalex(monkeypatch, OpenAlexFalsa())
    instalar_llm(app, TERMOS_DO_TRIADOR, LLMTempoEsgotado("prazo"))

    with TestClient(app) as client:
        resposta = client.post("/verificar", json={"trecho": TRECHO})

    conferir_erro(resposta, 504, CodigoErro.LLM_TIMEOUT)


def test_juiz_respondendo_invalido_vira_llm_indisponivel(montar, monkeypatch) -> None:
    app = montar()
    instalar_openalex(monkeypatch, OpenAlexFalsa())
    invalida = RESPOSTA_DO_JUIZ | {"doi": "10.9999/nao-recebido"}
    duble = instalar_llm(app, TERMOS_DO_TRIADOR, invalida)

    with TestClient(app) as client:
        resposta = client.post("/verificar", json={"trecho": TRECHO})

    conferir_erro(resposta, 503, CodigoErro.LLM_INDISPONIVEL)
    assert len(duble.chamadas) == 3  # Triador + Juiz com uma nova tentativa


def test_sem_llm_api_key_vira_triagem_indisponivel(montar, monkeypatch) -> None:
    """Sem chave o Triador é a primeira etapa a faltar, e a esteira para nele.

    O erro é da triagem, e não da análise: o Juiz nunca chegou a ser chamado.
    """
    app = montar(llm_api_key=None)
    openalex = OpenAlexFalsa()
    instalar_openalex(monkeypatch, openalex)

    with TestClient(app) as client:
        resposta = client.post("/verificar", json={"trecho": TRECHO})

    conferir_erro(resposta, 503, CodigoErro.TRIAGEM_INDISPONIVEL)
    assert openalex.buscas == []


def test_entrada_invalida_e_422_mesmo_sem_chaves(montar, monkeypatch) -> None:
    """O corpo é validado antes de qualquer cliente ser montado."""
    app = montar(llm_api_key=None)
    custom = settings_module.get_settings().model_copy(update={"openalex_mailto": None})
    monkeypatch.setattr(settings_module, "get_settings", lambda: custom)
    with TestClient(app) as client:
        resposta = client.post("/verificar", json={"url": "file:///x"})

    conferir_erro(resposta, 422, CodigoErro.ENTRADA_INVALIDA)


def test_sem_openalex_mailto_responde_openalex_indisponivel(
    montar, monkeypatch
) -> None:
    app = montar()
    custom = settings_module.get_settings().model_copy(update={"openalex_mailto": None})
    monkeypatch.setattr(settings_module, "get_settings", lambda: custom)
    instalar_llm(app, TERMOS_DO_TRIADOR, RESPOSTA_DO_JUIZ)

    with TestClient(app) as client:
        resposta = client.post("/verificar", json={"trecho": TRECHO})

    conferir_erro(resposta, 503, CodigoErro.OPENALEX_INDISPONIVEL)


@pytest.mark.parametrize("trecho", ["", "   "])
def test_trecho_em_branco_e_recusado_sem_gastar_llm(
    montar, monkeypatch, trecho: str
) -> None:
    app = montar()
    instalar_openalex(monkeypatch, OpenAlexFalsa())
    duble = instalar_llm(app, TERMOS_DO_TRIADOR, RESPOSTA_DO_JUIZ)

    with TestClient(app) as client:
        resposta = client.post("/verificar", json={"trecho": trecho})

    conferir_erro(resposta, 422, CodigoErro.ENTRADA_INVALIDA)
    assert duble.chamadas == []


def test_entrada_estruturalmente_invalida_retorna_422(montar) -> None:
    with TestClient(montar()) as client:
        response = client.post("/verificar", json={"url": "file:///pagina-teste.html"})
    assert response.status_code == 422
    assert response.json() == {
        "codigo": "entrada_invalida",
        "mensagem": "Não foi possível validar a solicitação.",
    }


# --- Gravação no banco --------------------------------------------------------


def test_falha_ao_gravar_devolve_veredito_sem_id_e_registra(
    montar, monkeypatch, caplog
) -> None:
    app = montar()
    instalar_openalex(monkeypatch, OpenAlexFalsa())
    instalar_llm(app, TERMOS_DO_TRIADOR, RESPOSTA_DO_JUIZ)

    with caplog.at_level("ERROR", logger="verificador.gateway"):
        with TestClient(app) as client:
            resposta = client.post("/verificar", json={"trecho": TRECHO})

    assert resposta.status_code == 200
    assert resposta.json()["id"] is None
    assert "Falha ao gravar o veredito" in caplog.text


@exige_banco
def test_veredito_gravado_tem_id_aceito_pelo_feedback(montar, monkeypatch) -> None:
    async def no_banco(operacao):
        motor = criar_motor(Settings(_env_file=None, database_url=URL_DO_BANCO))
        try:
            async with motor.begin() as conexao:
                return await operacao(conexao)
        finally:
            await motor.dispose()

    async def criar_tabelas(conexao):
        await conexao.run_sync(Base.metadata.create_all, checkfirst=True)

    asyncio.run(no_banco(criar_tabelas))

    app = montar(database_url=URL_DO_BANCO)
    instalar_openalex(monkeypatch, OpenAlexFalsa())
    instalar_llm(app, TERMOS_DO_TRIADOR, RESPOSTA_DO_JUIZ)

    with TestClient(app) as client:
        resposta = client.post("/verificar", json={"trecho": TRECHO})
        identificador = resposta.json()["id"]
        feedback = client.post(
            "/feedback",
            json={
                "veredicto_id": identificador,
                "util": True,
                "data_hora": "2026-10-05T12:00:00Z",
            },
        )

    async def conferir_e_limpar(conexao):
        estado = await conexao.scalar(
            select(Veredito.estado_veredito).where(Veredito.id == identificador)
        )
        avaliacoes = await conexao.scalar(
            select(func.count())
            .select_from(Feedback)
            .where(Feedback.veredito_id == identificador)
        )
        await conexao.execute(
            delete(Feedback).where(Feedback.veredito_id == identificador)
        )
        await conexao.execute(delete(Veredito).where(Veredito.id == identificador))
        return estado, avaliacoes

    assert resposta.status_code == 200
    assert isinstance(identificador, int)
    assert feedback.status_code == 200
    assert asyncio.run(no_banco(conferir_e_limpar)) == ("exagera", 1)


# --- Contrato publicado -------------------------------------------------------


def test_health_nao_depende_de_database_url(montar) -> None:
    with TestClient(montar()) as client:
        assert client.get("/health").json() == {"ok": True}
        assert client.get("/health").status_code == 200
        assert client.get("/saude").status_code == 404


def test_docs_e_openapi_publicam_contrato_e_exemplos(montar) -> None:
    with TestClient(montar()) as client:
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


def test_cors_da_extensao_permanece_disponivel(montar) -> None:
    with TestClient(montar()) as client:
        response = client.options(
            "/verificar",
            headers={
                "Origin": "chrome-extension://exemplo",
                "Access-Control-Request-Method": "POST",
            },
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
