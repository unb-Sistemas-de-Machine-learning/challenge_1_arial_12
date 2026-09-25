"""Fábrica e ponto de entrada ASGI da API."""

import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.gateway import router
from src.api.gateway.middlewares import (
    HEADER_CORRELACAO,
    CorsComErroPadronizado,
    registrar_limite_de_taxa,
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


def criar_app(*, relogio_limite: Callable[[], float] = time.monotonic) -> FastAPI:
    """`relogio_limite` só existe para o teste de integração do limite de taxa
    avançar o tempo sem depender de `time.sleep`; a aplicação real usa o
    padrão."""
    settings = settings_module.get_settings()
    api = FastAPI(
        title="Verificador Científico",
        version="0.1.0",
        debug=settings.app_debug,
        lifespan=ciclo_de_vida,
    )
    # Starlette empilha o middleware na ordem inversa de registro: o último
    # registrado é o mais externo, e vê a requisição primeiro. O limite
    # precisa ficar por dentro da correlação (para reaproveitar
    # `request.state.id_correlacao`) e por dentro do CORS (para que uma
    # resposta 429 ainda receba `Access-Control-Allow-Origin`) — por isso é
    # registrado antes dos outros dois, e não depois.
    registrar_limite_de_taxa(api, settings, relogio=relogio_limite)
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
