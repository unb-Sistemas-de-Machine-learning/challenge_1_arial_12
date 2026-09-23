"""Fábrica e ponto de entrada ASGI da API."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.gateway import router
from src.core.config.settings import get_settings
from src.core.database.session import criar_fabrica_de_sessoes, criar_motor


@asynccontextmanager
async def ciclo_de_vida(api: FastAPI) -> AsyncIterator[None]:
    """Cria o motor na subida e o descarta no encerramento.

    **Nada aqui toca o banco.** Criar o motor não abre conexão; a primeira só
    acontece no primeiro uso. Acrescentar uma checagem de conectividade faria
    `test_app_compose.py` falhar por não resolver um host fictício, num teste
    que nada tem a ver com banco.
    """
    motor = criar_motor(get_settings())
    api.state.motor = motor
    api.state.fabrica_de_sessoes = criar_fabrica_de_sessoes(motor)
    try:
        yield
    finally:
        await motor.dispose()


def criar_app() -> FastAPI:
    settings = get_settings()
    api = FastAPI(
        title="Verificador Científico",
        version="0.1.0",
        debug=settings.app_debug,
        lifespan=ciclo_de_vida,
    )
    api.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    api.include_router(router)
    return api


app = criar_app()
