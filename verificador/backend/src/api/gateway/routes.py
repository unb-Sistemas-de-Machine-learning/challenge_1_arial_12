"""Rotas públicas: verificação, busca de trabalhos e saúde."""

import logging

import logging
from fastapi import APIRouter, Body, BackgroundTasks, Request

from src.api.gateway.middlewares import ErroGateway
from src.api.schemas.busca import PedidoDeBusca, RespostaDaBusca
from src.api.schemas.erro import CodigoErro, Erro
from src.api.schemas.feedback import FeedbackRequest, FeedbackResponse
from src.core.database.repositories import registrar_feedback
from src.api.schemas.verificacao import Estado, Estudo, Pedido, Veredito
from src.services.openalex import (
    ErroOpenAlex,
    OpenAlexRecusouABusca,
    cliente_compartilhado,
)

logger = logging.getLogger("verificador.gateway")


router = APIRouter()

_VEREDITO_FIXO = Veredito(
    id=1,
    estado=Estado.EXAGERA,
    estudo=Estudo(
        titulo="(mock) Estudo de exemplo",
        ano=2019,
        doi="10.0000/mock",
        retratado=False,
    ),
    termos=["polylaminin", "spinal cord injury", "regeneration"],
    justificativa="(mock) Resposta de teste — a IA entra na Fase 04.",
)


@router.get("/health", tags=["health"])
def health() -> dict[str, bool]:
    return {"ok": True}


@router.post(
    "/verificar",
    response_model=Veredito,
    tags=["verificação"],
    responses={
        200: {
            "description": "Veredicto fixo da Fase 01",
            "content": {
                "application/json": {
                    "example": _VEREDITO_FIXO.model_dump(mode="json"),
                }
            },
        },
        422: {"model": Erro, "description": "Entrada inválida"},
        429: {"model": Erro, "description": "Limite de solicitações excedido"},
        503: {"model": Erro, "description": "Busca de estudos indisponível"},
        504: {"model": Erro, "description": "Tempo de análise excedido"},
        500: {"model": Erro, "description": "Erro interno"},
    },
)
def verificar(
    pedido: Pedido = Body(
        openapi_examples={
            "trecho_selecionado": {
                "summary": "Texto selecionado na extensão",
                "value": {
                    "trecho": "A polilaminina vai revolucionar o tratamento.",
                    "url": "https://pagina-teste.html",
                },
            }
        }
    ),
) -> Veredito:
    print(f"[verificar] url={pedido.url}")
    print(f"[verificar] trecho={pedido.trecho!r}")
    return _VEREDITO_FIXO.model_copy(deep=True)


@router.post(
    "/buscar",
    response_model=RespostaDaBusca,
    tags=["busca"],
    summary="Busca trabalhos científicos na OpenAlex",
    responses={
        422: {"model": Erro, "description": "Lista inválida ou recusada pela OpenAlex"},
        503: {"model": Erro, "description": "OpenAlex indisponível"},
    },
)
async def buscar(
    pedido: PedidoDeBusca = Body(
        openapi_examples={
            "variacoes": {
                "summary": "Variações da mesma pergunta",
                "value": {
                    "buscas": [
                        "polylaminin spinal cord injury",
                        "polylaminin regeneration",
                    ]
                },
            },
            "booleana": {
                "summary": "Consulta booleana com parênteses",
                "value": {
                    "buscas": ['("Service Design" OR "UX") AND ("ITSM" OR "ITIL")'],
                    "limite": 5,
                },
            },
            "mais_citados": {
                "summary": "Os mais citados, em vez dos mais relevantes",
                "value": {
                    "buscas": ["polylaminin spinal cord injury"],
                    "ordenar_por": "citacoes",
                },
            },
        }
    ),
) -> RespostaDaBusca:
    """Devolve os trabalhos mais relevantes que a OpenAlex associa às buscas."""
    # Montar o cliente e usá-lo falham por motivos diferentes, e a resposta
    # precisa dizer de quem é a culpa. Config faltando é problema do servidor:
    # responder 422 mandaria quem chamou revisar uma busca que estava certa.
    try:
        cliente = cliente_compartilhado()
    except ValueError as erro:
        logger.error("Busca indisponível por configuração: %s", erro)
        raise ErroGateway(CodigoErro.OPENALEX_INDISPONIVEL) from erro

    try:
        resultado = await cliente.buscar_varias(
            pedido.buscas,
            quantidade=pedido.quantidade,
            limite=pedido.limite,
            ordenar_por=pedido.ordenar_por,
        )
    except OpenAlexRecusouABusca as erro:
        # A consulta é que está errada, e quem a escreveu foi quem chamou.
        logger.warning("OpenAlex recusou a busca: %s", erro)
        raise ErroGateway(CodigoErro.ENTRADA_INVALIDA) from erro
    except ValueError as erro:
        # Lista sem nenhuma busca útil: aí sim a culpa é da entrada.
        logger.warning("Lista de buscas recusada: %s", erro)
        raise ErroGateway(CodigoErro.ENTRADA_INVALIDA) from erro
    except ErroOpenAlex as erro:
        logger.warning("OpenAlex indisponível: %s", erro)
        raise ErroGateway(CodigoErro.OPENALEX_INDISPONIVEL) from erro

    return RespostaDaBusca.model_validate(resultado.como_dicionario())

async def persistir_feedback(fabrica_de_sessoes, veredicto_id: int, util: bool):
    try:
        async with fabrica_de_sessoes() as sessao:
            await registrar_feedback(sessao, veredicto_id, util)
    except Exception as e:
        logging.error(f"Erro ao persistir feedback: {e}")


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    tags=["feedback"],
    responses={
        200: {"description": "Feedback recebido"},
        422: {"model": Erro, "description": "Entrada inválida"},
        429: {"model": Erro, "description": "Limite de solicitações excedido"},
        500: {"model": Erro, "description": "Erro interno"},
    },
)
async def receber_feedback(
    request: Request,
    background_tasks: BackgroundTasks,
    pedido: FeedbackRequest = Body(...),
) -> FeedbackResponse:
    fabrica = request.app.state.fabrica_de_sessoes
    background_tasks.add_task(
        persistir_feedback, fabrica, pedido.veredicto_id, pedido.util
    )
    return FeedbackResponse(status="recebido")

