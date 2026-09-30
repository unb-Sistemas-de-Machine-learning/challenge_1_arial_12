"""A camada de LLM, sem rede e sem chave real.

O `ClienteLLM` é testado com o `DubleLLM` no lugar do provedor: timeout,
repetição, validação e log rodam de verdade. O provedor real é testado com
`httpx.MockTransport`: a biblioteca `openai` monta a requisição de verdade, e
só o soquete é dublê.
"""

import json
import logging
import time
from collections.abc import Callable

import httpx
import pytest
from pydantic import BaseModel, ValidationError

from src.core.config import settings as settings_module
from src.core.config.settings import Settings
from src.services import llm
from src.services.llm import (
    ClienteLLM,
    FalhaTransitoria,
    LLMIndisponivel,
    LLMRecusouOPedido,
    LLMTempoEsgotado,
    ProvedorCompativelComOpenAI,
    RespostaInvalidaDoLLM,
    obter_cliente_llm,
)
from src.tests.dubles.llm import DubleLLM

CHAVE = "gsk-chave-super-secreta-de-teste"
VALIDA = {"buscas": ["polylaminin spinal cord", "polylaminin regeneration"]}


class Variacoes(BaseModel):
    buscas: list[str]


class Espera:
    """Registra as esperas entre tentativas sem dormir de verdade."""

    def __init__(self) -> None:
        self.pedidas: list[float] = []

    async def __call__(self, segundos: float) -> None:
        self.pedidas.append(segundos)


def cliente_com(duble: DubleLLM, **opcoes) -> tuple[ClienteLLM, Espera]:
    espera = Espera()
    return ClienteLLM(duble, dormir=espera, **opcoes), espera


# --- Critério 1: interface única ----------------------------------------------


@pytest.mark.asyncio
async def test_gerar_devolve_instancia_validada_do_schema() -> None:
    cliente, _ = cliente_com(DubleLLM(VALIDA))

    resultado = await cliente.gerar("Gere buscas", Variacoes)

    assert isinstance(resultado, Variacoes)
    assert resultado.buscas == VALIDA["buscas"]


@pytest.mark.asyncio
async def test_schema_vai_para_o_provedor_e_sistema_do_agente_e_preservado() -> None:
    duble = DubleLLM(VALIDA)
    cliente, _ = cliente_com(duble)

    await cliente.gerar("Gere buscas", Variacoes, sistema="Você é o Triador.")

    chamada = duble.chamadas[0]
    assert chamada["prompt"] == "Gere buscas"
    assert chamada["nome_schema"] == "Variacoes"
    assert chamada["schema_json"] == Variacoes.model_json_schema()
    assert chamada["sistema"].startswith("Você é o Triador.")
    assert "JSON" in chamada["sistema"]
    assert '"buscas"' in chamada["sistema"].replace("'", '"')


@pytest.mark.asyncio
async def test_json_cercado_por_bloco_de_codigo_e_aceito() -> None:
    cercado = f"```json\n{json.dumps(VALIDA)}\n```"
    cliente, _ = cliente_com(DubleLLM(cercado))

    assert (await cliente.gerar("x", Variacoes)).buscas == VALIDA["buscas"]


# --- Critério 2: resposta fora do schema --------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resposta",
    [
        "Claro! Aqui estão as buscas: polylaminin",
        '{"buscas": "polylaminin"}',
        "{}",
        '{"buscas": [1, 2]}',
        '{"buscas": ["a"',
    ],
    ids=[
        "texto_solto",
        "string_no_lugar_de_lista",
        "sem_campo",
        "tipo_errado",
        "truncado",
    ],
)
async def test_resposta_fora_do_schema_vira_erro_e_nao_e_repetida(resposta) -> None:
    duble = DubleLLM(resposta)
    cliente, _ = cliente_com(duble, max_tentativas=3)

    with pytest.raises(RespostaInvalidaDoLLM):
        await cliente.gerar("x", Variacoes)

    assert len(duble.chamadas) == 1


# --- Critério 3: timeout ------------------------------------------------------


@pytest.mark.asyncio
async def test_provedor_lento_estoura_o_timeout_dentro_do_prazo() -> None:
    cliente, _ = cliente_com(DubleLLM(VALIDA, atraso_segundos=5), timeout_segundos=0.05)

    inicio = time.perf_counter()
    with pytest.raises(LLMTempoEsgotado):
        await cliente.gerar("x", Variacoes)

    assert time.perf_counter() - inicio < 1


@pytest.mark.asyncio
async def test_timeout_pode_ser_sobrescrito_por_chamada() -> None:
    cliente, _ = cliente_com(DubleLLM(VALIDA, atraso_segundos=5), timeout_segundos=60)

    inicio = time.perf_counter()
    with pytest.raises(LLMTempoEsgotado):
        await cliente.gerar("x", Variacoes, timeout_segundos=0.05)

    assert time.perf_counter() - inicio < 1


def test_timeout_padrao_documentado() -> None:
    settings = Settings(_env_file=None, database_url="postgresql+asyncpg://db/v")
    assert settings.llm_timeout_segundos == 15.0
    assert settings.llm_max_tentativas == 2


# --- Critério 6: repetição e falha do provedor --------------------------------


@pytest.mark.asyncio
async def test_falha_transitoria_e_repetida_ate_dar_certo() -> None:
    duble = DubleLLM(FalhaTransitoria("503"), VALIDA)
    cliente, espera = cliente_com(duble, max_tentativas=2)

    resultado = await cliente.gerar("x", Variacoes)

    assert resultado.buscas == VALIDA["buscas"]
    assert len(duble.chamadas) == 2
    assert espera.pedidas == [0.5]


@pytest.mark.asyncio
async def test_falha_transitoria_persistente_vira_indisponivel() -> None:
    duble = DubleLLM(FalhaTransitoria("503"))
    cliente, espera = cliente_com(duble, max_tentativas=3)

    with pytest.raises(LLMIndisponivel, match="3 tentativa"):
        await cliente.gerar("x", Variacoes)

    assert len(duble.chamadas) == 3
    assert espera.pedidas == [0.5, 1.0]


@pytest.mark.asyncio
async def test_retry_after_e_respeitado_com_teto() -> None:
    duble = DubleLLM(
        FalhaTransitoria("429", retry_after=2),
        FalhaTransitoria("429", retry_after=600),
        VALIDA,
    )
    cliente, espera = cliente_com(duble, max_tentativas=3)

    await cliente.gerar("x", Variacoes)

    assert espera.pedidas == [2, llm.TETO_ESPERA_SEGUNDOS]


@pytest.mark.asyncio
async def test_recusa_definitiva_nao_e_repetida() -> None:
    duble = DubleLLM(LLMRecusouOPedido("401"))
    cliente, _ = cliente_com(duble, max_tentativas=3)

    with pytest.raises(LLMIndisponivel):
        await cliente.gerar("x", Variacoes)

    assert len(duble.chamadas) == 1


@pytest.mark.asyncio
async def test_repeticao_nao_passa_do_prazo_total() -> None:
    duble = DubleLLM(FalhaTransitoria("503"), atraso_segundos=0.03)
    cliente = ClienteLLM(duble, timeout_segundos=0.1, max_tentativas=5)

    inicio = time.perf_counter()
    with pytest.raises(LLMTempoEsgotado):
        await cliente.gerar("x", Variacoes)

    assert time.perf_counter() - inicio < 1


# --- Critério 4: log ----------------------------------------------------------


@pytest.mark.asyncio
async def test_log_registra_modelo_latencia_e_tokens(caplog) -> None:
    caplog.set_level(logging.INFO, logger="verificador.llm")
    duble = DubleLLM(VALIDA, modelo="modelo-x", tokens_entrada=312, tokens_saida=45)
    cliente, _ = cliente_com(duble)

    await cliente.gerar("x", Variacoes)

    [registro] = [r for r in caplog.records if r.name == "verificador.llm"]
    linha = registro.getMessage()
    assert registro.levelno == logging.INFO
    assert "provedor=duble" in linha
    assert "modelo=modelo-x" in linha
    assert "resultado=ok" in linha
    assert "latencia_ms=" in linha
    assert "tokens_entrada=312" in linha
    assert "tokens_saida=45" in linha
    assert "tentativas=1" in linha


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("passo", "erro", "resultado"),
    [
        ("nao e json", RespostaInvalidaDoLLM, "resposta_invalida"),
        (FalhaTransitoria("503"), LLMIndisponivel, "indisponivel"),
    ],
)
async def test_falha_tambem_gera_linha_de_log(caplog, passo, erro, resultado) -> None:
    caplog.set_level(logging.INFO, logger="verificador.llm")
    cliente, _ = cliente_com(DubleLLM(passo))

    with pytest.raises(erro):
        await cliente.gerar("x", Variacoes)

    [registro] = [r for r in caplog.records if r.name == "verificador.llm"]
    assert registro.levelno == logging.WARNING
    assert f"resultado={resultado}" in registro.getMessage()


# --- Provedor real, com transporte dublê --------------------------------------


def resposta_de_chat(conteudo: str | None, **extra) -> dict:
    return {
        "id": "chatcmpl-teste",
        "object": "chat.completion",
        "created": 0,
        "model": "openai/gpt-oss-20b",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": conteudo},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 312, "completion_tokens": 45, "total_tokens": 357},
        **extra,
    }


class Transporte:
    """Responde cada requisição com a ação dada e guarda o que chegou."""

    def __init__(self, acao: Callable[[httpx.Request], httpx.Response]) -> None:
        self.acao = acao
        self.requisicoes: list[httpx.Request] = []

    def __call__(self, requisicao: httpx.Request) -> httpx.Response:
        self.requisicoes.append(requisicao)
        return self.acao(requisicao)


def provedor(
    acao: Callable[[httpx.Request], httpx.Response], nome: str = "groq", **opcoes
) -> tuple[ProvedorCompativelComOpenAI, Transporte]:
    transporte = Transporte(acao)
    return (
        ProvedorCompativelComOpenAI(
            nome=nome,
            api_key=CHAVE,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(transporte)),
            **opcoes,
        ),
        transporte,
    )


def devolver(corpo: dict, status: int = 200, **cabecalhos: str):
    return lambda _r: httpx.Response(status, json=corpo, headers=cabecalhos)


async def completar(prov: ProvedorCompativelComOpenAI):
    return await prov.completar(
        sistema="sistema",
        prompt="prompt",
        nome_schema="Variacoes",
        schema_json=Variacoes.model_json_schema(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("nome", "url", "modelo"),
    [
        (
            "groq",
            "https://api.groq.com/openai/v1/chat/completions",
            "openai/gpt-oss-20b",
        ),
        (
            "gemini",
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            "gemini-3.5-flash",
        ),
    ],
)
async def test_provedor_monta_a_requisicao_de_cada_provedor(nome, url, modelo) -> None:
    prov, transporte = provedor(devolver(resposta_de_chat(json.dumps(VALIDA))), nome)

    resposta = await completar(prov)

    [requisicao] = transporte.requisicoes
    corpo = json.loads(requisicao.content)
    assert str(requisicao.url) == url
    assert requisicao.headers["Authorization"] == f"Bearer {CHAVE}"
    assert corpo["model"] == modelo
    assert corpo["messages"] == [
        {"role": "system", "content": "sistema"},
        {"role": "user", "content": "prompt"},
    ]
    assert corpo["response_format"]["type"] == "json_schema"
    assert corpo["response_format"]["json_schema"]["name"] == "Variacoes"
    assert resposta.texto == json.dumps(VALIDA)
    assert (resposta.tokens_entrada, resposta.tokens_saida) == (312, 45)


@pytest.mark.asyncio
async def test_modelo_e_formato_json_sao_configuraveis() -> None:
    prov, transporte = provedor(
        devolver(resposta_de_chat("{}")),
        modelo="llama-3.1-8b-instant",
        formato_json="json_object",
    )

    await completar(prov)

    corpo = json.loads(transporte.requisicoes[0].content)
    assert corpo["model"] == "llama-3.1-8b-instant"
    assert corpo["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_429_e_transitorio_e_traz_o_retry_after() -> None:
    prov, _ = provedor(
        devolver({"error": {"message": "limite"}}, 429, **{"Retry-After": "3"})
    )

    with pytest.raises(FalhaTransitoria) as falha:
        await completar(prov)

    assert falha.value.retry_after == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [500, 502, 503])
async def test_5xx_e_transitorio(status) -> None:
    prov, _ = provedor(devolver({"error": {"message": "fora"}}, status))

    with pytest.raises(FalhaTransitoria):
        await completar(prov)


@pytest.mark.asyncio
async def test_falha_de_conexao_e_transitoria() -> None:
    def cair(requisicao: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dublê de queda", request=requisicao)

    prov, _ = provedor(cair)

    with pytest.raises(FalhaTransitoria):
        await completar(prov)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 403, 404])
async def test_4xx_e_recusa_definitiva(status) -> None:
    prov, _ = provedor(devolver({"error": {"message": "não"}}, status))

    with pytest.raises(LLMRecusouOPedido, match=str(status)):
        await completar(prov)


@pytest.mark.asyncio
async def test_json_validate_failed_da_groq_e_resposta_invalida() -> None:
    corpo = {"error": {"message": "falhou", "code": "json_validate_failed"}}
    prov, _ = provedor(devolver(corpo, 400))

    with pytest.raises(RespostaInvalidaDoLLM):
        await completar(prov)


@pytest.mark.asyncio
async def test_conteudo_vazio_e_resposta_invalida() -> None:
    prov, _ = provedor(devolver(resposta_de_chat(None)))

    with pytest.raises(RespostaInvalidaDoLLM):
        await completar(prov)


def test_provedor_exige_chave_e_nome_conhecido() -> None:
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        ProvedorCompativelComOpenAI(nome="groq", api_key="  ")
    with pytest.raises(ValueError, match="LLM_PROVEDOR"):
        ProvedorCompativelComOpenAI(nome="openai", api_key=CHAVE)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "acao",
    [
        devolver(resposta_de_chat(json.dumps(VALIDA))),
        devolver(resposta_de_chat("nao e json")),
        devolver({"error": {"message": f"chave {CHAVE} inválida"}}, 401),
        devolver({"error": {"message": "fora"}}, 503),
    ],
    ids=["sucesso", "resposta_invalida", "recusa", "indisponivel"],
)
async def test_chave_nunca_aparece_no_log(caplog, acao) -> None:
    caplog.set_level(logging.DEBUG)
    prov, _ = provedor(acao)
    cliente = ClienteLLM(prov, dormir=Espera())

    try:
        await cliente.gerar("x", Variacoes)
    except llm.ErroLLM:
        pass

    assert any(r.name == "verificador.llm" for r in caplog.records)
    assert CHAVE not in caplog.text


# --- Configuração e dependência -----------------------------------------------


def test_provedor_fora_da_lista_impede_a_configuracao() -> None:
    with pytest.raises(ValidationError, match="llm_provedor"):
        Settings(
            _env_file=None,
            database_url="postgresql+asyncpg://db/v",
            llm_provedor="openai",
        )


@pytest.mark.asyncio
async def test_cliente_nasce_das_configuracoes(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://db/v",
        llm_provedor="gemini",
        llm_api_key=CHAVE,
        llm_timeout_segundos=7,
        llm_max_tentativas=3,
    )
    monkeypatch.setattr(settings_module, "get_settings", lambda: settings)

    cliente = ClienteLLM.a_partir_das_configuracoes()

    assert cliente.provedor.nome == "gemini"
    assert cliente.provedor.modelo == llm.PROVEDORES["gemini"].modelo_padrao
    assert cliente.timeout_segundos == 7
    assert cliente.max_tentativas == 3
    await cliente.fechar()


def test_dependencia_sem_chave_vira_indisponivel(monkeypatch) -> None:
    settings = Settings(_env_file=None, database_url="postgresql+asyncpg://db/v")
    monkeypatch.setattr(settings_module, "get_settings", lambda: settings)
    monkeypatch.setattr(llm, "_compartilhado", None)

    with pytest.raises(LLMIndisponivel):
        obter_cliente_llm()
