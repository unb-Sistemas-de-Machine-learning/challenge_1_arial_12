"""Operações de domínio sobre o banco, no vocabulário do Verificador."""

import hashlib
import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database.models import Feedback, Veredito

_ESPACOS = re.compile(r"\s+")


def normalizar_trecho(trecho: str) -> str:
    """Reduz variações de escrita do mesmo texto a uma forma única.

    Sem isto, "A polilaminina  regenera" e "a polilaminina regenera" viram
    chaves diferentes e o cache quase nunca acerta.
    """
    # NFC junta acento e letra num único caractere. Texto copiado da web vem
    # ora composto, ora decomposto: "á" pode ser um caractere ou dois, visual-
    # mente idênticos e com bytes diferentes. Sem isto, o mesmo trecho geraria
    # chaves diferentes dependendo da página de origem.
    texto = unicodedata.normalize("NFC", trecho)
    # casefold, e não lower: trata casos que lower deixa passar em outros
    # idiomas, e é idêntico a lower em português.
    return _ESPACOS.sub(" ", texto).strip().casefold()


def gerar_hash_do_trecho(trecho: str) -> str:
    """Chave de busca do cache, derivada do trecho — nunca da saída de um LLM.

    Saída de LLM não se repete entre execuções: uma chave derivada dela mudaria
    a cada chamada e o cache nunca encontraria nada. A consulta acontece antes
    da esteira de agentes, e é daí que vem a economia.
    """
    return hashlib.sha256(normalizar_trecho(trecho).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class VereditoRegistrado:
    """O que a camada de fora recebe: nunca um objeto do mapeador.

    Objeto de ORM carrega a sessão junto; ler um campo dele depois que ela
    fechou estoura apontando para a linha que leu, e não para a que fechou.
    """

    id: int
    resposta: dict


async def registrar_veredito(
    sessao: AsyncSession,
    trecho: str,
    estado_veredito: str,
    resposta: dict,
) -> VereditoRegistrado:
    """Grava uma verificação. Cada chamada cria uma linha, mesmo com trecho repetido."""
    linha = Veredito(
        hash_trecho=gerar_hash_do_trecho(trecho),
        trecho_avaliado=trecho,
        estado_veredito=estado_veredito,
        resposta=resposta,
    )
    sessao.add(linha)
    await sessao.commit()
    return VereditoRegistrado(id=linha.id, resposta=linha.resposta)


async def buscar_por_hash(
    sessao: AsyncSession, hash_trecho: str
) -> VereditoRegistrado | None:
    """A verificação mais recente com essa chave, ou nada.

    "Mais recente" importa porque a chave não é única: refazer uma verificação
    vencida cria linha nova, e o cache precisa da última, não da primeira.
    """
    linha = await sessao.scalar(
        select(Veredito)
        .where(Veredito.hash_trecho == hash_trecho)
        .order_by(Veredito.criado_em.desc(), Veredito.id.desc())
        .limit(1)
    )
    if linha is None:
        return None
    return VereditoRegistrado(id=linha.id, resposta=linha.resposta)


async def registrar_feedback(sessao: AsyncSession, veredito_id: int, util: bool) -> int:
    """Grava uma avaliação. Várias podem existir sobre o mesmo veredito."""
    linha = Feedback(veredito_id=veredito_id, util=util)
    sessao.add(linha)
    await sessao.commit()
    return linha.id
