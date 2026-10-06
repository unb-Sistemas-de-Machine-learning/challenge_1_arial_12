"""Pesquisador: transforma as buscas do Triador nos trabalhos que o Juiz lê.

Não usa LLM. Decide, busca a busca, se a resposta vem do cache ou da OpenAlex,
dispara as externas em paralelo com teto configurável e junta tudo numa lista
só, sem repetir o mesmo artigo.

O granulo é a string de busca, e não o lote: é o que permite consultar o cache
antes de cada ida à OpenAlex. Por isso o Pesquisador chama `ClienteOpenAlex.buscar`
uma vez por string, em vez de `buscar_varias`, e reaproveita do cliente só a
normalização da lista e a intercalação por posição.

Não descarta trabalho sem abstract ou sem DOI: esse filtro é do Juiz, que já o
aplica antes de gastar uma chamada de LLM.
"""

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from src.agents.juiz import normalizar_doi
from src.api.schemas.busca import TrabalhoEncontrado
from src.services.cache import CacheDeBuscas, SemCache
from src.services.openalex import (
    TOP_PADRAO,
    ErroOpenAlex,
    OpenAlexIndisponivel,
    Trabalho,
    intercalar,
    normalizar_buscas,
)

logger = logging.getLogger("verificador.agentes.pesquisador")

CONCORRENCIA_PADRAO = 5


class BuscadorDeTrabalhos(Protocol):
    """O que o Pesquisador usa do `ClienteOpenAlex`: uma busca por string."""

    async def buscar(self, busca: str) -> list[Trabalho]: ...


@dataclass(frozen=True)
class ResultadoDaPesquisa:
    """Os trabalhos consolidados e as buscas que não deram certo.

    As falhas vêm junto, e não só no log: uma variação que não rodou encolhe a
    cobertura, e quem orquestra pode querer saber disso.
    """

    trabalhos: list[TrabalhoEncontrado]
    falhas: dict[str, str]


def chave_por_doi(trabalho: Trabalho) -> str:
    """Identidade do artigo: o DOI quando existe, senão o id da OpenAlex.

    Preprint e versão publicada costumam ter ids diferentes na OpenAlex e o
    mesmo DOI. O prefixo impede que um DOI e um id coincidam por acaso.
    """
    doi = normalizar_doi(trabalho.doi)
    return f"doi:{doi}" if doi else f"id:{trabalho.chave}"


class AgentePesquisador:
    """Cache primeiro, OpenAlex depois, concorrência limitada, sem duplicatas."""

    def __init__(
        self,
        cliente: BuscadorDeTrabalhos,
        *,
        cache: CacheDeBuscas | None = None,
        concorrencia: int = CONCORRENCIA_PADRAO,
        limite: int = TOP_PADRAO,
    ) -> None:
        self.cliente = cliente
        self.cache: CacheDeBuscas = cache if cache is not None else SemCache()
        self.concorrencia = max(1, concorrencia)
        self.limite = max(1, limite)

    async def pesquisar(self, buscas: Sequence[str]) -> ResultadoDaPesquisa:
        """Os trabalhos das buscas, intercalados por posição e sem repetição.

        Levanta `ValueError` se a lista não tiver nenhuma busca útil, e
        `OpenAlexIndisponivel` se **nenhuma** busca funcionar. Falha parcial
        não é erro: entra em `falhas`.
        """
        pedidas = normalizar_buscas(buscas)
        if not pedidas:
            raise ValueError("é preciso pelo menos uma string de busca não vazia")

        # Um limitador por pesquisa: o teto vale para esta verificação, e um
        # semáforo compartilhado entre requisições faria uma esperar a outra.
        limitador = asyncio.Semaphore(self.concorrencia)
        respostas = await asyncio.gather(
            *(self._uma(busca, limitador) for busca in pedidas)
        )

        falhas: dict[str, str] = {}
        listas: list[list[Trabalho]] = []
        for busca, resposta in zip(pedidas, respostas, strict=True):
            if isinstance(resposta, ErroOpenAlex):
                falhas[busca] = str(resposta)
            else:
                listas.append(resposta)

        if len(falhas) == len(pedidas):
            raise OpenAlexIndisponivel(
                f"nenhuma das {len(pedidas)} buscas funcionou: "
                f"{next(iter(falhas.values()))}"
            )
        if falhas:
            logger.warning(
                "Pesquisador seguiu com %d de %d buscas; falharam: %s",
                len(pedidas) - len(falhas),
                len(pedidas),
                falhas,
            )

        # O DOI entra na intercalação, e não depois do corte: desduplicar
        # depois entregaria menos trabalhos ao Juiz do que o limite permite.
        trabalhos = intercalar(listas, self.limite, chave=chave_por_doi)
        return ResultadoDaPesquisa(
            trabalhos=[
                TrabalhoEncontrado.model_validate(trabalho.como_dicionario())
                for trabalho in trabalhos
            ],
            falhas=falhas,
        )

    async def _uma(
        self, busca: str, limitador: asyncio.Semaphore
    ) -> list[Trabalho] | ErroOpenAlex:
        em_cache = await self._consultar_cache(busca)
        if em_cache is not None:
            return em_cache

        # O limite protege a OpenAlex; acerto de cache não ocupa vaga.
        async with limitador:
            try:
                trabalhos = await self.cliente.buscar(busca)
            except ErroOpenAlex as erro:
                return erro

        await self._guardar_no_cache(busca, trabalhos)
        return trabalhos

    async def _consultar_cache(self, busca: str) -> list[Trabalho] | None:
        # Cache é otimização: se quebrar, a busca segue para a OpenAlex.
        try:
            return await self.cache.obter(busca)
        except Exception:
            logger.exception("Cache indisponível na leitura; seguindo sem ele")
            return None

    async def _guardar_no_cache(self, busca: str, trabalhos: list[Trabalho]) -> None:
        try:
            await self.cache.guardar(busca, trabalhos)
        except Exception:
            logger.exception("Cache indisponível na escrita; resultado não guardado")
