"""Rotas públicas: verificação, busca de trabalhos e saúde."""

import logging
from fastapi import APIRouter, Body, BackgroundTasks, Depends, Request

from src.agents.juiz import AgenteJuiz
from src.agents.pesquisador import AgentePesquisador
from src.agents.triador import AgenteTriador
from src.api.gateway.dependencias import obter_juiz, obter_pesquisador, obter_triador
from src.api.gateway.middlewares import ErroGateway
from src.api.schemas.busca import PedidoDeBusca, RespostaDaBusca
from src.api.schemas.erro import CodigoErro, Erro
from src.api.schemas.feedback import FeedbackRequest, FeedbackResponse
from src.core.database.repositories import registrar_feedback, registrar_veredito
from src.api.schemas.verificacao import Estado, Estudo, Pedido, Veredito
from src.services.openalex import (
    ErroOpenAlex,
    OpenAlexIndisponivel,
    OpenAlexRecusouABusca,
    cliente_compartilhado,
)

logger = logging.getLogger("verificador.gateway")


router = APIRouter()

# Só documentação: é o exemplo de resposta publicado no OpenAPI. A resposta de
# verdade vem da esteira.
_EXEMPLO_DE_VEREDITO = Veredito(
    id=1,
    estado=Estado.EXAGERA,
    estudo=Estudo(
        titulo="Polylaminin promotes regeneration after spinal cord injury",
        ano=2019,
        doi="10.0000/exemplo",
        retratado=False,
    ),
    termos=["polylaminin", "regeneration", "spinal cord injury"],
    justificativa=(
        "O estudo observou regeneração em ratos, mas a matéria promete um "
        "tratamento revolucionário para pessoas."
    ),
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
            "description": "Veredicto da esteira Triador → Pesquisador → Juiz",
            "content": {
                "application/json": {
                    "example": _EXEMPLO_DE_VEREDITO.model_dump(mode="json"),
                }
            },
        },
        422: {"model": Erro, "description": "Entrada inválida"},
        429: {"model": Erro, "description": "Limite de solicitações excedido"},
        502: {"model": Erro, "description": "A OpenAlex recusou todas as buscas"},
        503: {"model": Erro, "description": "Busca de estudos ou análise indisponível"},
        504: {"model": Erro, "description": "Tempo de análise excedido"},
        500: {"model": Erro, "description": "Erro interno"},
    },
)
async def verificar(
    request: Request,
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
    triador: AgenteTriador = Depends(obter_triador),
    pesquisador: AgentePesquisador = Depends(obter_pesquisador),
    juiz: AgenteJuiz = Depends(obter_juiz),
) -> Veredito:
    """Triador → Pesquisador → Juiz. A rota só orquestra e grava o resultado.

    Falha do LLM no Triador não aparece aqui: ele segue com o trecho original.
    Falha do LLM no Juiz sobe como `ErroLLM` e vira `llm_timeout` ou
    `llm_indisponivel` no handler do gateway.
    """
    if not pedido.trecho.strip():
        # Trecho em branco não tem o que verificar, e não vale uma chamada de LLM.
        raise ErroGateway(CodigoErro.ENTRADA_INVALIDA)

    extracao = await triador.extrair(pedido.trecho)
    try:
        pesquisa = await pesquisador.pesquisar(extracao.buscas)
    except OpenAlexRecusouABusca as erro:
        # Todas as buscas recusadas: a OpenAlex respondeu, e o problema é a
        # consulta. Dizer `openalex_indisponivel` aqui culparia um serviço que
        # está no ar e mandaria o leitor tentar mais tarde sem motivo.
        logger.error("Todas as buscas do Pesquisador foram recusadas: %s", erro)
        raise ErroGateway(CodigoErro.BUSCA_RECUSADA) from erro
    except OpenAlexIndisponivel as erro:
        logger.warning("Nenhuma busca do Pesquisador funcionou: %s", erro)
        raise ErroGateway(CodigoErro.OPENALEX_INDISPONIVEL) from erro
    except ValueError as erro:
        raise ErroGateway(CodigoErro.ENTRADA_INVALIDA) from erro

    veredito = await juiz.julgar(pedido.trecho, pesquisa.trabalhos)
    veredito = veredito.model_copy(update={"termos": extracao.conceitos})
    return veredito.model_copy(
        update={"id": await gravar_veredito(request, pedido.trecho, veredito)}
    )


async def gravar_veredito(
    request: Request, trecho: str, veredito: Veredito
) -> int | None:
    """O `id` da linha gravada, ou `None` se o banco falhar.

    Falha aqui não vira erro para o leitor: a análise já custou duas chamadas
    de LLM, e sem `id` a extensão só esconde os botões de feedback.
    """
    try:
        async with request.app.state.fabrica_de_sessoes() as sessao:
            registrado = await registrar_veredito(
                sessao,
                trecho,
                veredito.estado.value,
                veredito.model_dump(mode="json", exclude={"id"}),
            )
    except Exception as erro:
        # Banco fora do ar é previsto: uma linha basta. A pilha só aparece em
        # modo de depuração, quando alguém está de fato investigando.
        logger.error(
            "Falha ao gravar o veredito; respondendo sem id: %s: %s",
            type(erro).__name__,
            erro,
            exc_info=logger.isEnabledFor(logging.DEBUG),
        )
        return None
    return registrado.id


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
