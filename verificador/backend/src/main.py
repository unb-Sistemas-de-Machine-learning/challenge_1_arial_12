"""Ponto de entrada da API do Verificador Científico."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.gateway.routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="Verificador Científico")
    # Mantém a política do stub; as origens da extensão variam entre navegadores.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
