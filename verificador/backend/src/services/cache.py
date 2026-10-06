"""Ponto de extensão do cache de buscas, consultado pelo Pesquisador.

O cache é por **string de busca**, e não por trecho: duas alegações diferentes
geram variações em comum com frequência ("coffee cancer"), e é aí que está a
economia de chamadas à OpenAlex.

Esta entrega só define o contrato e o "sem cache". A implementação de verdade,
com prazo de validade e meta de acerto, tem issue própria: quem a fizer
implementa `CacheDeBuscas` e entrega a instância ao Pesquisador, sem tocar na
rota nem no agente.
"""

from typing import Protocol

from src.services.openalex import Trabalho


class CacheDeBuscas(Protocol):
    """O que o Pesquisador espera de um cache.

    Erro aqui nunca derruba a verificação: o Pesquisador trata qualquer exceção
    como "não estava no cache" e segue para a OpenAlex.
    """

    async def obter(self, busca: str) -> list[Trabalho] | None:
        """Os trabalhos guardados para a busca, ou `None` se não houver.

        Lista vazia é resposta válida: a busca rodou e não achou nada, e isso
        também vale guardar.
        """
        ...

    async def guardar(self, busca: str, trabalhos: list[Trabalho]) -> None:
        """Guarda o resultado de uma busca que foi à OpenAlex."""
        ...


class SemCache:
    """O padrão: nunca encontra nada e não guarda nada."""

    async def obter(self, busca: str) -> list[Trabalho] | None:
        return None

    async def guardar(self, busca: str, trabalhos: list[Trabalho]) -> None:
        return None
