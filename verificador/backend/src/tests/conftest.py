"""Preparo compartilhado dos testes que usam banco.

Concentra três coisas que estavam espalhadas: a URL do banco, a decisão de
pular quando ele não está disponível, e o isolamento entre casos.
"""

import asyncio
import os
from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.core.config.settings import Settings
from src.core.database.models import Base
from src.core.database.session import criar_motor

URL_PADRAO = "postgresql+asyncpg://verificador:verificador@localhost:5432/verificador"
URL_DO_BANCO = os.environ.get("DATABASE_URL", URL_PADRAO)


def banco_alcancavel() -> bool:
    async def tentar() -> bool:
        try:
            conexao = await asyncpg.connect(
                URL_DO_BANCO.replace("+asyncpg", ""), timeout=2
            )
        except Exception:
            return False
        await conexao.close()
        return True

    return asyncio.run(tentar())


# Sem banco, os testes que precisam dele são pulados na máquina de quem
# desenvolve — mas **nunca** na verificação automática, onde banco ausente é
# defeito e pular deixaria o check verde sem ter rodado nada.
exige_banco = pytest.mark.skipif(
    not os.environ.get("CI") and not banco_alcancavel(),
    reason="Postgres indisponível. Suba com: docker compose up -d db",
)


@pytest_asyncio.fixture
async def motor() -> AsyncIterator[AsyncEngine]:
    """Um motor por caso, descartado ao fim.

    Não dá para compartilhar entre casos: cada teste assíncrono roda no próprio
    laço de eventos, e conexão aberta num laço não sobrevive ao seguinte — o
    sintoma é "Event loop is closed" no segundo caso, sem relação aparente com
    o que ele testa.
    """
    criado = criar_motor(Settings(_env_file=None, database_url=URL_DO_BANCO))
    try:
        yield criado
    finally:
        await criado.dispose()


@pytest_asyncio.fixture
async def sessao(motor: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Sessão isolada: tudo o que o teste gravar é revertido ao fim.

    A sessão é amarrada a uma conexão com transação já aberta. O que o código
    sob teste chama de "gravar" fica visível dentro do teste e desaparece na
    reversão — sem apagar e recriar tabelas, que multiplicaria o tempo da suíte.
    """
    async with motor.connect() as conexao:
        # checkfirst: o teste de migrações desfaz o schema no próprio teardown,
        # então não dá para criá-lo uma vez só no início da sessão.
        await conexao.run_sync(Base.metadata.create_all, checkfirst=True)
        await conexao.commit()

        transacao = await conexao.begin()
        fabrica = async_sessionmaker(
            bind=conexao,
            expire_on_commit=False,
            # O repositório confirma a transação, como manda o desenho. Sem
            # ponto de salvamento, essa confirmação mexeria na transação
            # externa e o isolamento se perderia — e uma gravação que falha
            # derrubaria a transação do teste junto.
            join_transaction_mode="create_savepoint",
        )
        async with fabrica() as aberta:
            yield aberta
        await transacao.rollback()
