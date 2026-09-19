"""Rotas públicas do contrato de verificação."""

from fastapi import APIRouter, Body

from src.api.schemas.verificacao import Estado, Estudo, Pedido, Veredito

router = APIRouter()

_VEREDITO_FIXO = Veredito(
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
        }
    },
)
def verificar(
    pedido: Pedido = Body(
        openapi_examples={
            "trecho_selecionado": {
                "summary": "Texto selecionado na extensão",
                "value": {"trecho": "A polilaminina vai revolucionar o tratamento.", "url": "file:///pagina-teste.html"},
            }
        }
    ),
) -> Veredito:
    print(f"[verificar] url={pedido.url}")
    print(f"[verificar] trecho={pedido.trecho!r}")
    return _VEREDITO_FIXO.model_copy(deep=True)
