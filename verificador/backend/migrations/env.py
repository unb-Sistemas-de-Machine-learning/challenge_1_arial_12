"""Ponto de entrada das migrações.

A URL vem de `get_settings()`, e não do `alembic.ini`: duas fontes de verdade
para a mesma coisa divergem na primeira vez que alguém muda uma delas.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from src.core.config.settings import get_settings
from src.core.database.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# É o que a geração automática compara com o banco para descobrir o que mudou.
target_metadata = Base.metadata

config.set_main_option("sqlalchemy.url", get_settings().database_url.get_secret_value())


def run_migrations_offline() -> None:
    """Gera o SQL sem conectar, para quem precisa aplicar à mão."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # Sem isto, mudança de tipo e de valor padrão de coluna passa
        # despercebida pela geração automática.
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    conectavel = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with conectavel.connect() as conexao:
        await conexao.run_sync(do_run_migrations)
    await conectavel.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
