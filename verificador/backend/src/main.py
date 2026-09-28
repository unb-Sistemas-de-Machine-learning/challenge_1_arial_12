"""Fábrica e ponto de entrada ASGI da API."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.gateway import router
from src.api.gateway.middlewares import (
    HEADER_CORRELACAO,
    CorsComErroPadronizado,
    registrar_tratamento_erros,
)
from src.core.config import settings as settings_module
from src.core.database.session import criar_fabrica_de_sessoes, criar_motor
from src.services.openalex import encerrar_cliente_compartilhado


@asynccontextmanager
async def ciclo_de_vida(api: FastAPI) -> AsyncIterator[None]:
    """Cria o motor na subida e o descarta no encerramento.

    **Nada aqui toca o banco.** Criar o motor não abre conexão; a primeira só
    acontece no primeiro uso. Acrescentar uma checagem de conectividade faria
    `test_app_compose.py` falhar por não resolver um host fictício, num teste
    que nada tem a ver com banco.
    """
    motor = criar_motor(settings_module.get_settings())
    api.state.motor = motor
    api.state.fabrica_de_sessoes = criar_fabrica_de_sessoes(motor)
    try:
        yield
    finally:
        await motor.dispose()
        await encerrar_cliente_compartilhado()


def criar_app() -> FastAPI:
    settings = settings_module.get_settings()
    api = FastAPI(
        title="Verificador Científico",
        version="0.1.0",
        debug=settings.app_debug,
        lifespan=ciclo_de_vida,
    )
    registrar_tratamento_erros(api)
    api.add_middleware(
        CorsComErroPadronizado,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[HEADER_CORRELACAO],
    )
    api.include_router(router)
    if not settings.openalex_mailto:
        # O corpo de erro é fechado por contrato e não pode nomear a variável
        # que falta. Sem este aviso, quem sobe o servidor só descobre no
        # primeiro 503, com uma mensagem que não ajuda a achar a causa.
        logging.getLogger("verificador.gateway").warning(
            "POST /buscar está registrada, mas OPENALEX_MAILTO está vazio: "
            "toda busca vai responder 503 até o .env ser preenchido"
        )
    return api


create_app = criar_app
app = criar_app()
