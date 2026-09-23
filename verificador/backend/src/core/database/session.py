"""Motor de conexão, fábrica de sessões e a sessão entregue a cada requisição."""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.config.settings import Settings


def criar_motor(settings: Settings) -> AsyncEngine:
    """Cria o motor. **Não abre conexão**: a primeira só acontece no primeiro uso.

    Conectar aqui quebraria `test_app_compose.py`, que instancia a aplicação com
    uma URL fictícia só para exercitar CORS e healthcheck.
    """
    return create_async_engine(
        # Único ponto do código que abre o segredo da URL. Em nenhum outro
        # lugar, e nunca em log ou mensagem de erro.
        settings.database_url.get_secret_value(),
        # Sem echo mesmo em debug: o log do SQLAlchemy imprime a URL conectada.
        echo=False,
        pool_pre_ping=True,
    )


def criar_fabrica_de_sessoes(motor: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        motor,
        # O padrão do SQLAlchemy expira os objetos depois do commit, o que faz
        # ler um campo já carregado disparar consulta nova — e estourar se a
        # sessão tiver fechado.
        expire_on_commit=False,
    )


async def get_sessao(requisicao: Request) -> AsyncIterator[AsyncSession]:
    """Entrega uma sessão por requisição.

    O `async with` é o que garante o fechamento mesmo quando a rota levanta
    exceção — não há tratamento manual de erro, e não deve haver.

    Não faz `commit`: quem grava é o repositório, explicitamente. Commit
    automático aqui gravaria também quando a rota decidiu não gravar.
    """
    fabrica = requisicao.app.state.fabrica_de_sessoes
    async with fabrica() as sessao:
        yield sessao
