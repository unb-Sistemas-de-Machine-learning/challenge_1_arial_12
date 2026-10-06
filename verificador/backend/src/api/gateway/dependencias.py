"""As três etapas da esteira, entregues às rotas por `Depends`.

É também a costura de teste: `app.dependency_overrides[obter_pesquisador]` troca
uma etapa inteira por um dublê, sem rede e sem chave. Para o LLM, a costura
continua sendo `obter_cliente_llm`, de que o Triador e o Juiz dependem.

**Nenhuma dependência aqui falha na montagem.** O FastAPI resolve as
dependências antes de validar o corpo: se faltar `LLM_API_KEY` e a dependência
levantar, um pedido sem `trecho` responderia 503 em vez de 422. Por isso os
clientes de LLM e da OpenAlex só são montados na primeira chamada, e a falha
de configuração aparece onde a etapa já sabe tratá-la — o Triador degrada, o
Juiz responde `llm_indisponivel` e o Pesquisador responde
`openalex_indisponivel`.
"""

import logging
from collections.abc import Callable

from fastapi import Request

from src.agents.juiz import AgenteJuiz
from src.agents.pesquisador import AgentePesquisador
from src.agents.triador import AgenteTriador
from src.core.config import settings as settings_module
from src.services.llm import ClienteLLM, obter_cliente_llm
from src.services.openalex import (
    OpenAlexIndisponivel,
    Trabalho,
    cliente_compartilhado,
)

logger = logging.getLogger("verificador.gateway")


class _LLMSobDemanda:
    """Um `ClienteLLM` que só é montado quando a etapa chama o modelo."""

    def __init__(self, obter: Callable[[], ClienteLLM]) -> None:
        self._obter = obter

    async def gerar(self, *args, **kwargs):
        # `obter_cliente_llm` traduz configuração ausente em `LLMIndisponivel`,
        # um `ErroLLM`: o Triador degrada e o Juiz sobe para o handler.
        return await self._obter().gerar(*args, **kwargs)


class _OpenAlexSobDemanda:
    """O cliente compartilhado da OpenAlex, montado na primeira busca."""

    async def buscar(self, busca: str, **opcoes) -> list[Trabalho]:
        try:
            cliente = cliente_compartilhado()
        except ValueError as erro:
            # Configuração faltando é problema do servidor, como em `/buscar`.
            # Como `ErroOpenAlex`, conta como busca falha, e todas falhando
            # viram `openalex_indisponivel`.
            logger.error("Pesquisador indisponível por configuração: %s", erro)
            raise OpenAlexIndisponivel("configuração da OpenAlex incompleta") from erro
        return await cliente.buscar(busca, **opcoes)


def _llm(request: Request) -> _LLMSobDemanda:
    # Respeita a troca feita em teste com `dependency_overrides`, que o
    # FastAPI só aplicaria se `obter_cliente_llm` fosse resolvida por ele.
    obter = request.app.dependency_overrides.get(obter_cliente_llm, obter_cliente_llm)
    return _LLMSobDemanda(obter)


def obter_triador(request: Request) -> AgenteTriador:
    return AgenteTriador(_llm(request))


def obter_juiz(request: Request) -> AgenteJuiz:
    return AgenteJuiz(_llm(request))


def obter_pesquisador() -> AgentePesquisador:
    return AgentePesquisador(
        _OpenAlexSobDemanda(),
        concorrencia=settings_module.get_settings().pesquisador_concorrencia,
    )
