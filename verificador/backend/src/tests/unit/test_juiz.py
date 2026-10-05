"""Garantias determinísticas do Juiz com o LLM dublado, sem rede."""

import pytest

from src.agents.juiz import (
    ARQUIVO_DE_ORIENTACOES,
    JUSTIFICATIVA_SEM_EVIDENCIA,
    MAX_JUSTIFICATIVA,
    AgenteJuiz,
    normalizar_doi,
)
from src.agents import orientacoes
from src.api.schemas.busca import TrabalhoEncontrado
from src.api.schemas.verificacao import Estado, Veredito
from src.services.llm import ClienteLLM, LLMTempoEsgotado, RespostaInvalidaDoLLM
from src.tests.dubles.llm import DubleLLM

DOI = "10.0000/eval-1"
ABSTRACT = "Em adultos, a intervenção mostrou melhora moderada no desfecho medido."
JUSTIFICATIVA = (
    f"O estudo com DOI {DOI} mostra melhora moderada no desfecho, "
    "o que sustenta a alegação limitada a adultos."
)


def trabalho(
    *, doi: str | None = DOI, abstract: str | None = ABSTRACT, retratado: bool = False
) -> TrabalhoEncontrado:
    return TrabalhoEncontrado(
        id="W1",
        titulo="Estudo de teste",
        ano=2024,
        doi=doi,
        retratado=retratado,
        abstract=abstract,
        relevancia=1.0,
        citacoes=4,
    )


def resposta(
    *,
    estado: str = "sustenta",
    relacao: str | None = None,
    doi: str | None = DOI,
    evidencia: str | None = "melhora moderada no desfecho",
    justificativa: str = JUSTIFICATIVA,
) -> dict:
    return {
        "relacao": relacao
        or {
            "sustenta": "compativel",
            "exagera": "parcial",
            "nada_encontrado": "ausente",
        }.get(estado, "compativel"),
        "estado": estado,
        "doi": doi,
        "evidencia": evidencia,
        "justificativa": justificativa,
    }


def juiz(*passos) -> tuple[AgenteJuiz, DubleLLM]:
    duble = DubleLLM(*passos)
    return AgenteJuiz(ClienteLLM(duble)), duble


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "trabalhos", [[], [trabalho(abstract=None)], [trabalho(doi=None)]]
)
async def test_sem_abstract_utilizavel_devolve_nada_sem_llm(trabalhos) -> None:
    agente, duble = juiz(resposta())

    veredito = await agente.julgar("Alegação", trabalhos)

    assert isinstance(veredito, Veredito)
    assert veredito.estado == Estado.NADA_ENCONTRADO
    assert veredito.estudo is None
    assert veredito.justificativa == JUSTIFICATIVA_SEM_EVIDENCIA
    assert duble.chamadas == []


@pytest.mark.asyncio
async def test_apenas_retratado_nao_chama_llm_nem_sustenta() -> None:
    agente, duble = juiz(resposta())
    veredito = await agente.julgar("Alegação", [trabalho(retratado=True)])
    assert veredito.estado == Estado.NADA_ENCONTRADO
    assert veredito.estudo is None
    assert duble.chamadas == []


@pytest.mark.asyncio
async def test_veredito_usa_metadados_da_entrada_e_schema_b05() -> None:
    agente, duble = juiz(resposta())

    veredito = await agente.julgar("Alegação limitada a adultos", [trabalho()])

    assert veredito.estado == Estado.SUSTENTA
    assert veredito.estudo is not None
    assert veredito.estudo.titulo == "Estudo de teste"
    assert veredito.estudo.ano == 2024
    assert veredito.estudo.doi == DOI
    assert veredito.termos == []
    assert veredito.id is None
    assert len(duble.chamadas) == 1
    assert duble.chamadas[0]["nome_schema"] == "RespostaDoJuiz"
    assert "Alegação limitada a adultos" in duble.chamadas[0]["prompt"]
    assert ABSTRACT in duble.chamadas[0]["prompt"]


@pytest.mark.asyncio
async def test_exagera_cita_o_estudo_recebido() -> None:
    mensagem = (
        f"O estudo com DOI {DOI} mostra melhora moderada, "
        "mas a alegação promete uma cura que o abstract não demonstra."
    )
    agente, _ = juiz(resposta(estado="exagera", justificativa=mensagem))
    veredito = await agente.julgar("A intervenção cura a doença", [trabalho()])
    assert veredito.estado == Estado.EXAGERA
    assert veredito.estudo is not None
    assert veredito.estudo.doi == DOI


@pytest.mark.asyncio
async def test_doi_valido_na_resposta_dispensa_repeticao_na_justificativa() -> None:
    mensagem = (
        "O estudo recebido observou melhora moderada apenas em adultos, "
        "enquanto a alegação promete uma cura para todas as pessoas."
    )
    agente, duble = juiz(resposta(estado="exagera", justificativa=mensagem))

    veredito = await agente.julgar("A intervenção cura todas as pessoas", [trabalho()])

    assert veredito.estado == Estado.EXAGERA
    assert veredito.estudo is not None
    assert veredito.estudo.doi == DOI
    assert len(duble.chamadas) == 1


@pytest.mark.asyncio
async def test_estudo_relacionado_nao_pode_virar_nada_encontrado() -> None:
    mensagem = (
        "O estudo disponível trata da mesma intervenção e do mesmo desfecho, "
        "mas relata um efeito menor do que a alegação promete."
    )
    agente, duble = juiz(
        resposta(
            estado="nada_encontrado",
            relacao="parcial",
            doi=None,
            evidencia=None,
            justificativa=mensagem,
        ),
        resposta(estado="exagera", justificativa=JUSTIFICATIVA),
    )

    veredito = await agente.julgar("A alegação amplia o efeito", [trabalho()])

    assert veredito.estado == Estado.EXAGERA
    assert len(duble.chamadas) == 2


@pytest.mark.asyncio
async def test_doi_apos_palavra_estudo_nao_e_numero_interno() -> None:
    mensagem = (
        f"O estudo {DOI} relata melhora moderada no desfecho medido "
        "em adultos, apoiando esta alegação limitada."
    )
    agente, duble = juiz(resposta(justificativa=mensagem))

    veredito = await agente.julgar("Alegação limitada a adultos", [trabalho()])

    assert veredito.estado == Estado.SUSTENTA
    assert len(duble.chamadas) == 1


@pytest.mark.asyncio
async def test_frase_em_portugues_sem_vocabulario_especifico_e_aceita() -> None:
    abstract = "No ensaio, o filtro A reteve mais partículas do que o filtro B."
    mensagem = (
        f"O filtro A reteve mais partículas do que o filtro B no ensaio "
        f"descrito em {DOI}."
    )
    agente, duble = juiz(
        resposta(
            evidencia="o filtro A reteve mais partículas do que o filtro B",
            justificativa=mensagem,
        )
    )

    veredito = await agente.julgar(
        "O filtro A reteve mais partículas", [trabalho(abstract=abstract)]
    )

    assert veredito.estado == Estado.SUSTENTA
    assert len(duble.chamadas) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "primeira",
    [
        resposta(estado="fora_do_enum"),
        resposta(justificativa=""),
        resposta(justificativa="a" * (MAX_JUSTIFICATIVA + 1)),
        resposta(doi="10.0000/nao-recebido"),
        resposta(evidencia="trecho que não consta do abstract"),
        resposta(justificativa=f"The study with DOI {DOI} shows a clear benefit."),
        resposta(justificativa=f"O estudo 1 com DOI {DOI} mostra um resultado melhor."),
        resposta(
            justificativa=f"O prompt diz que o estudo com DOI {DOI} mostra melhora."
        ),
        resposta(
            justificativa=(
                f"O estudo com DOI {DOI} mostra melhora, mas o DOI "
                "10.0000/nao-recebido não veio da entrada."
            )
        ),
    ],
    ids=[
        "estado",
        "vazia",
        "longa",
        "doi_estranho",
        "citacao_inventada",
        "ingles",
        "numero_de_estudo",
        "jargao_prompt",
        "doi_no_texto",
    ],
)
async def test_resposta_invalida_e_reprocessada_uma_vez(primeira: dict) -> None:
    agente, duble = juiz(primeira, resposta())

    veredito = await agente.julgar("Alegação", [trabalho()])

    assert veredito.estado == Estado.SUSTENTA
    assert len(duble.chamadas) == 2
    assert duble.chamadas[0]["prompt"] != duble.chamadas[1]["prompt"]


@pytest.mark.asyncio
async def test_falha_persistente_levanta_erro_padronizavel() -> None:
    agente, duble = juiz(resposta(estado="inexistente"))

    with pytest.raises(RespostaInvalidaDoLLM):
        await agente.julgar("Alegação", [trabalho()])

    assert len(duble.chamadas) == 2


@pytest.mark.asyncio
async def test_fonte_retratada_nao_pode_sustentar_mesmo_com_outra_fonte() -> None:
    outro = trabalho(doi="10.0000/eval-2", retratado=False)
    agente, duble = juiz(
        resposta(),
        resposta(
            estado="nada_encontrado",
            doi=None,
            evidencia=None,
            justificativa="Os estudos disponíveis não mostram evidência pertinente para a alegação.",
        ),
    )

    veredito = await agente.julgar("Alegação", [trabalho(retratado=True), outro])

    assert veredito.estado == Estado.NADA_ENCONTRADO
    assert len(duble.chamadas) == 2


@pytest.mark.asyncio
async def test_timeout_do_provedor_nao_gera_retry_extra_do_juiz() -> None:
    agente, duble = juiz(LLMTempoEsgotado("tempo esgotado"))

    with pytest.raises(LLMTempoEsgotado):
        await agente.julgar("Alegação", [trabalho()])

    assert len(duble.chamadas) == 1


def test_normalizacao_de_doi_aceita_url_do_resolvedor() -> None:
    assert normalizar_doi("https://doi.org/10.0000/EVAL-1") == DOI


def test_prompt_distingue_exagero_de_ausencia_de_estudo() -> None:
    documento = orientacoes.ler(ARQUIVO_DE_ORIENTACOES)
    corpo = " ".join(documento.corpo.split())

    assert documento.versao == "4"
    assert "`parcial` → `exagera`" in corpo
    assert "Não comprova a promessa inteira" in corpo
    assert "estudo pertinente `ausente`" in corpo
    assert "em animais, mas a alegação promete o efeito em humanos" in corpo
    assert "medida indireta" in corpo
