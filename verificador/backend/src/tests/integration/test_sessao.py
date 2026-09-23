"""A sessão devolve a conexão ao fim da requisição, inclusive quando ela falha.

Conexão vazada não aparece com poucos casos: a aplicação funciona nos testes e
esgota o conjunto de conexões em produção. Por isso o teste mede o número de
conexões em uso, e não apenas se a resposta veio.
"""

import os

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config.settings import Settings
from src.core.database.session import criar_fabrica_de_sessoes, criar_motor, get_sessao

URL_PADRAO = "postgresql+asyncpg://verificador:verificador@localhost:5432/verificador"
URL_DO_BANCO = os.environ.get("DATABASE_URL", URL_PADRAO)


def banco_alcancavel() -> bool:
    import asyncio

    import asyncpg

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


# Sem banco de pé, estes testes são pulados na máquina de quem desenvolve — mas
# **nunca** na verificação automática, onde banco ausente é defeito e pular
# deixaria o check verde sem ter rodado nada.
pytestmark = pytest.mark.skipif(
    not os.environ.get("CI") and not banco_alcancavel(),
    reason="Postgres indisponível. Suba com: docker compose up -d db",
)


@pytest.fixture
def api() -> FastAPI:
    """Aplicação mínima com duas rotas: uma que falha e uma que funciona.

    Não usa a aplicação real de propósito — rota que levanta exceção não existe
    lá, e não deve passar a existir só por causa de teste.
    """
    aplicacao = FastAPI()
    motor = criar_motor(Settings(_env_file=None, database_url=URL_DO_BANCO))
    aplicacao.state.motor = motor
    aplicacao.state.fabrica_de_sessoes = criar_fabrica_de_sessoes(motor)

    @aplicacao.get("/explode")
    async def explode(sessao: AsyncSession = Depends(get_sessao)) -> dict:
        # Consulta antes de falhar: sem ela nenhuma conexão sai do conjunto, e
        # o teste passaria mesmo com a sessão vazando.
        await sessao.execute(text("select 1"))
        raise RuntimeError("falha proposital para exercitar o fechamento")

    @aplicacao.get("/ok")
    async def ok(sessao: AsyncSession = Depends(get_sessao)) -> dict:
        return {"resultado": (await sessao.execute(text("select 1"))).scalar()}

    return aplicacao


def conexoes_em_uso(aplicacao: FastAPI) -> int:
    return aplicacao.state.motor.sync_engine.pool.checkedout()


def conexoes_devolvidas(aplicacao: FastAPI) -> int:
    return aplicacao.state.motor.sync_engine.pool.checkedin()


def exigir_conexao_devolvida(aplicacao: FastAPI) -> None:
    """Zero conexões em uso, e ao menos uma devolvida ao conjunto.

    A segunda metade não é redundante: sem banco nenhum, "zero em uso" é
    trivialmente verdade porque conexão alguma chegou a existir, e o teste
    passaria verde sem ter exercitado nada.
    """
    assert conexoes_devolvidas(aplicacao) >= 1, (
        "nenhuma conexão foi aberta — o teste não exercitou o banco"
    )
    assert conexoes_em_uso(aplicacao) == 0, "a conexão ficou presa"


def test_a_sessao_e_devolvida_quando_a_rota_falha(api: FastAPI) -> None:
    with TestClient(api, raise_server_exceptions=False) as cliente:
        resposta = cliente.get("/explode")
        assert resposta.status_code == 500
        exigir_conexao_devolvida(api)


def test_a_sessao_e_devolvida_quando_a_rota_funciona(api: FastAPI) -> None:
    with TestClient(api) as cliente:
        assert cliente.get("/ok").json() == {"resultado": 1}
        exigir_conexao_devolvida(api)


def test_requisicoes_seguidas_nao_acumulam_conexoes(api: FastAPI) -> None:
    """Vazamento de uma conexão por requisição só aparece na repetição."""
    with TestClient(api, raise_server_exceptions=False) as cliente:
        for _ in range(5):
            cliente.get("/explode")
        exigir_conexao_devolvida(api)
