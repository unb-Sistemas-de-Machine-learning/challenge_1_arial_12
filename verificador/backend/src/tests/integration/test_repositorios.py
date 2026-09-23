"""As três operações de domínio, contra Postgres real."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.repositories import (
    VereditoRegistrado,
    buscar_por_hash,
    gerar_hash_do_trecho,
    registrar_feedback,
    registrar_veredito,
)
from src.tests.conftest import exige_banco

pytestmark = [exige_banco, pytest.mark.asyncio]

TRECHO = "A polilaminina regenera a medula espinhal"
RESPOSTA = {"estado": "exagera", "termos": ["polylaminin"], "justificativa": "..."}


async def test_uma_verificacao_gravada_e_encontrada_pelo_trecho(
    sessao: AsyncSession,
) -> None:
    """O caminho que o cache vai percorrer: do trecho até a resposta guardada."""
    gravado = await registrar_veredito(sessao, TRECHO, "exagera", RESPOSTA)

    encontrado = await buscar_por_hash(sessao, gerar_hash_do_trecho(TRECHO))

    assert encontrado is not None
    assert encontrado.id == gravado.id
    assert encontrado.resposta == RESPOSTA


async def test_trecho_nunca_verificado_nao_devolve_nada(sessao: AsyncSession) -> None:
    assert await buscar_por_hash(sessao, gerar_hash_do_trecho("nunca visto")) is None


async def test_o_mesmo_trecho_pode_ser_verificado_duas_vezes(
    sessao: AsyncSession,
) -> None:
    """Prova na prática a decisão de a chave não ser única.

    Com unicidade, a segunda gravação falharia ou sobrescreveria a primeira — e
    os feedbacks já dados passariam a apontar para uma resposta que ninguém viu.
    """
    antiga = await registrar_veredito(sessao, TRECHO, "exagera", {"v": "antiga"})
    nova = await registrar_veredito(sessao, TRECHO, "sustenta", {"v": "nova"})

    assert antiga.id != nova.id

    encontrado = await buscar_por_hash(sessao, gerar_hash_do_trecho(TRECHO))
    assert encontrado is not None
    assert encontrado.id == nova.id, "o cache precisa da mais recente"
    assert encontrado.resposta == {"v": "nova"}


async def test_duas_avaliacoes_opostas_convivem(sessao: AsyncSession) -> None:
    """Prova a decisão de separar as tabelas: o segundo voto não apaga o primeiro."""
    veredito = await registrar_veredito(sessao, TRECHO, "exagera", RESPOSTA)

    positivo = await registrar_feedback(sessao, veredito.id, util=True)
    negativo = await registrar_feedback(sessao, veredito.id, util=False)

    assert positivo != negativo


async def test_o_banco_recusa_avaliacao_sem_verificacao(sessao: AsyncSession) -> None:
    with pytest.raises(IntegrityError):
        await registrar_feedback(sessao, veredito_id=999_999, util=True)

    # Transação que falhou precisa ser revertida antes de qualquer outro uso da
    # sessão; sem isto o preparo encontra a transação já desassociada no fim.
    await sessao.rollback()


async def test_as_operacoes_nao_devolvem_objeto_do_mapeador(
    sessao: AsyncSession,
) -> None:
    gravado = await registrar_veredito(sessao, TRECHO, "exagera", RESPOSTA)
    encontrado = await buscar_por_hash(sessao, gerar_hash_do_trecho(TRECHO))

    for devolvido in (gravado, encontrado):
        assert isinstance(devolvido, VereditoRegistrado)
        assert not hasattr(devolvido, "_sa_instance_state"), (
            "objeto do mapeador vazou para fora do repositório"
        )
