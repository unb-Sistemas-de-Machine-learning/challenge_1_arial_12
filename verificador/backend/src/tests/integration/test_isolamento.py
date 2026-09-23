"""O que um caso grava não existe para o seguinte.

Sem isto, a suíte passa a depender da ordem em que os casos rodam — e quebra de
um jeito que muda a cada execução.
"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.models import Veredito
from src.tests.conftest import exige_banco

pytestmark = [exige_banco, pytest.mark.asyncio]


async def contar_vereditos(sessao: AsyncSession) -> int:
    return await sessao.scalar(select(func.count()).select_from(Veredito))


async def test_o_primeiro_caso_grava_e_enxerga(sessao: AsyncSession) -> None:
    sessao.add(
        Veredito(
            hash_trecho="a" * 64,
            trecho_avaliado="trecho do primeiro caso",
            estado_veredito="exagera",
            resposta={"estado": "exagera"},
        )
    )
    await sessao.flush()
    assert await contar_vereditos(sessao) == 1


async def test_o_segundo_caso_nao_enxerga_o_que_o_primeiro_gravou(
    sessao: AsyncSession,
) -> None:
    """Depende de rodar depois do anterior — é justamente esse o ponto."""
    assert await contar_vereditos(sessao) == 0
