"""Handlers de erro e correlação de requisições do gateway."""

import logging
import traceback
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, Response

from src.api.schemas.erro import CodigoErro, Erro
from src.core.config import settings as settings_module

logger = logging.getLogger("verificador.gateway")
HEADER_CORRELACAO = "X-Correlation-ID"

STATUS_POR_CODIGO = {
    CodigoErro.ENTRADA_INVALIDA: 422,
    CodigoErro.LIMITE_EXCEDIDO: 429,
    CodigoErro.OPENALEX_INDISPONIVEL: 503,
    CodigoErro.LLM_TIMEOUT: 504,
    CodigoErro.RECURSO_NAO_ENCONTRADO: 404,
    CodigoErro.METODO_NAO_PERMITIDO: 405,
    CodigoErro.ERRO_REQUISICAO: 400,
    CodigoErro.SERVICO_INDISPONIVEL: 503,
    CodigoErro.ERRO_INTERNO: 500,
}

MENSAGENS_PUBLICAS = {
    CodigoErro.ENTRADA_INVALIDA: "Não foi possível validar a solicitação.",
    CodigoErro.LIMITE_EXCEDIDO: "Limite de solicitações excedido.",
    CodigoErro.OPENALEX_INDISPONIVEL: "Serviço de busca indisponível.",
    CodigoErro.LLM_TIMEOUT: "Tempo de análise excedido.",
    CodigoErro.RECURSO_NAO_ENCONTRADO: "Recurso não encontrado.",
    CodigoErro.METODO_NAO_PERMITIDO: "Método não permitido.",
    CodigoErro.ERRO_REQUISICAO: "Não foi possível processar a solicitação.",
    CodigoErro.SERVICO_INDISPONIVEL: "Serviço temporariamente indisponível.",
    CodigoErro.ERRO_INTERNO: "Ocorreu um erro interno.",
}


class ErroGateway(Exception):
    """Falha prevista cuja resposta é definida pelo código, nunca pelo detalhe."""

    def __init__(self, codigo: CodigoErro) -> None:
        self.codigo = CodigoErro(codigo)
        super().__init__(self.codigo.value)


def _id_correlacao(valor: str | None) -> str:
    try:
        return str(UUID(valor)) if valor else str(uuid4())
    except (ValueError, AttributeError):
        return str(uuid4())


def _codigo_http(status_code: int) -> CodigoErro:
    if status_code == 404:
        return CodigoErro.RECURSO_NAO_ENCONTRADO
    if status_code == 405:
        return CodigoErro.METODO_NAO_PERMITIDO
    if status_code == 422:
        return CodigoErro.ENTRADA_INVALIDA
    if status_code == 429:
        return CodigoErro.LIMITE_EXCEDIDO
    if status_code == 503:
        return CodigoErro.SERVICO_INDISPONIVEL
    if 400 <= status_code < 500:
        return CodigoErro.ERRO_REQUISICAO
    return CodigoErro.ERRO_INTERNO


def _resposta_erro(
    codigo: CodigoErro,
    status_code: int,
    id_correlacao: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    corpo = Erro(codigo=codigo, mensagem=MENSAGENS_PUBLICAS[codigo])
    return JSONResponse(
        status_code=status_code,
        content=corpo.model_dump(mode="json"),
        headers={**(headers or {}), HEADER_CORRELACAO: id_correlacao},
    )


def _registrar_erro_interno(request: Request, exc: Exception) -> None:
    rastreamento = "".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__)
    )
    try:
        settings = settings_module.get_settings()
        valores_sensiveis = [
            settings.database_url.get_secret_value(),
            settings.openai_api_key.get_secret_value()
            if settings.openai_api_key
            else None,
        ]
        for valor in valores_sensiveis:
            if valor:
                rastreamento = rastreamento.replace(valor, "[REDACTED]")
    except Exception:
        # Mesmo se a configuração falhar, o handler não pode falhar junto.
        pass
    logger.error(
        "Erro inesperado. correlation_id=%s\n%s",
        request.state.id_correlacao,
        rastreamento,
    )


async def _erro_interno(request: Request, exc: Exception) -> JSONResponse:
    _registrar_erro_interno(request, exc)
    request.state.erro_padronizado = True
    return _resposta_erro(CodigoErro.ERRO_INTERNO, 500, request.state.id_correlacao)


class CorsComErroPadronizado(CORSMiddleware):
    """O preflight negado não atravessa os handlers internos do FastAPI."""

    def preflight_response(self, request_headers: Headers) -> Response:
        resposta = super().preflight_response(request_headers)
        id_correlacao = _id_correlacao(request_headers.get(HEADER_CORRELACAO))
        if resposta.status_code >= 400:
            return _resposta_erro(
                CodigoErro.ERRO_REQUISICAO,
                resposta.status_code,
                id_correlacao,
                headers={
                    chave: valor
                    for chave, valor in resposta.headers.items()
                    if chave.lower().startswith("access-control-")
                    or chave.lower() == "vary"
                },
            )
        resposta.headers[HEADER_CORRELACAO] = id_correlacao
        return resposta


def registrar_tratamento_erros(api: FastAPI) -> None:
    """Instala handlers e middleware antes do CORS externo."""

    async def validar(request: Request, _exc: RequestValidationError) -> JSONResponse:
        request.state.erro_padronizado = True
        return _resposta_erro(
            CodigoErro.ENTRADA_INVALIDA, 422, request.state.id_correlacao
        )

    async def erro_previsto(request: Request, exc: ErroGateway) -> JSONResponse:
        request.state.erro_padronizado = True
        return _resposta_erro(
            exc.codigo, STATUS_POR_CODIGO[exc.codigo], request.state.id_correlacao
        )

    async def erro_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request.state.erro_padronizado = True
        return _resposta_erro(
            _codigo_http(exc.status_code),
            exc.status_code,
            request.state.id_correlacao,
            headers=exc.headers,
        )

    api.add_exception_handler(RequestValidationError, validar)
    api.add_exception_handler(ErroGateway, erro_previsto)
    api.add_exception_handler(StarletteHTTPException, erro_http)
    api.add_exception_handler(Exception, _erro_interno)

    @api.middleware("http")
    async def correlacionar_e_padronizar(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.id_correlacao = _id_correlacao(
            request.headers.get(HEADER_CORRELACAO)
        )
        try:
            resposta = await call_next(request)
        except Exception as exc:
            resposta = await _erro_interno(request, exc)

        if resposta.status_code >= 400 and not getattr(
            request.state, "erro_padronizado", False
        ):
            headers = {
                chave: valor
                for chave, valor in resposta.headers.items()
                if chave.lower() in {"retry-after", "www-authenticate", "allow"}
            }
            resposta = _resposta_erro(
                _codigo_http(resposta.status_code),
                resposta.status_code,
                request.state.id_correlacao,
                headers=headers,
            )

        resposta.headers[HEADER_CORRELACAO] = request.state.id_correlacao
        return resposta
