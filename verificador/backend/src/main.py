"""Fábrica e ponto de entrada ASGI da API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.gateway import router
from src.core.config.settings import get_settings


def criar_app() -> FastAPI:
    settings = get_settings()
    api = FastAPI(
        title="Verificador Científico", version="0.1.0", debug=settings.app_debug
    )
    api.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    api.include_router(router)
    return api


create_app = criar_app
app = criar_app()
