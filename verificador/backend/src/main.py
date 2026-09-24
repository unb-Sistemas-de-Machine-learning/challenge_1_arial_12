"""Fábrica e ponto de entrada ASGI da API."""

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
    return api


create_app = criar_app
app = criar_app()
