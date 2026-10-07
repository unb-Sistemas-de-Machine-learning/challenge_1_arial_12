"""Dublê da esteira inteira, para testes que não são sobre ela.

Limite de taxa, CORS e inicialização usam `/verificar` só como uma rota que
responde 200. Com a esteira real, isso exigiria LLM e OpenAlex; este dublê
troca as três etapas por versões sem rede e sem chave:

    app = criar_app()
    instalar_esteira_sem_rede(app, monkeypatch)

O Triador devolve só o trecho, o Pesquisador não acha nada e o Juiz é o de
verdade: com lista vazia ele responde `nada_encontrado` sem chamar o LLM. A
gravação falha na hora, em vez de esperar o banco fictício não responder.
"""

from collections.abc import Sequence

import pytest
from fastapi import FastAPI

from src.agents.juiz import AgenteJuiz
from src.agents.pesquisador import ResultadoDaPesquisa
from src.agents.triador import ExtracaoDoTriador
from src.api.gateway import routes
from src.api.gateway.dependencias import obter_juiz, obter_pesquisador, obter_triador


class TriadorSemLLM:
    async def extrair(self, trecho: str) -> ExtracaoDoTriador:
        return ExtracaoDoTriador(buscas=[trecho], conceitos=[])


class PesquisadorSemRede:
    # `busca_de_titulo` entra na assinatura mesmo sem ser usada: a rota a passa
    # sempre, e um dublê que a recuse viraria 500 em testes que nada têm a ver
    # com o atalho de título.
    async def pesquisar(
        self, buscas: Sequence[str], *, busca_de_titulo: str | None = None
    ) -> ResultadoDaPesquisa:
        return ResultadoDaPesquisa(trabalhos=[], falhas={})


def banco_indisponivel(monkeypatch: pytest.MonkeyPatch) -> None:
    """A gravação do veredito falha na hora, como um banco fora do ar.

    Sem isto, cada `/verificar` esperaria alguns segundos tentando resolver o
    host fictício dos testes antes de desistir.
    """

    async def falhar(*_args, **_kwargs):
        raise ConnectionError("banco indisponível (dublê)")

    monkeypatch.setattr(routes, "registrar_veredito", falhar)


def instalar_esteira_sem_rede(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    banco_indisponivel(monkeypatch)
    app.dependency_overrides[obter_triador] = TriadorSemLLM
    app.dependency_overrides[obter_pesquisador] = PesquisadorSemRede
    # Sem trabalhos o Juiz não chega a usar o cliente: `None` basta.
    app.dependency_overrides[obter_juiz] = lambda: AgenteJuiz(None)
