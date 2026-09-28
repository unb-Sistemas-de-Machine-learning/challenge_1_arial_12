"""Rotas públicas do contrato de verificação."""

import logging
from fastapi import APIRouter, Body, BackgroundTasks, Request

from src.api.schemas.erro import Erro
from src.api.schemas.verificacao import Estado, Estudo, Pedido, Veredito
from src.api.schemas.feedback import FeedbackRequest, FeedbackResponse
from src.core.database.repositories import registrar_feedback

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
