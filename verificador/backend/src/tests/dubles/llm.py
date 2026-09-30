"""Dublê de LLM: segue o `ProvedorLLM` e devolve respostas roteirizadas.

Entra no lugar do provedor, e não do `ClienteLLM`, para que timeout, repetição,
validação e log rodem de verdade no teste. Sem rede, sem chave, sem custo.

    duble = DubleLLM('{"buscas": ["a", "b"]}')
    cliente = ClienteLLM(duble)
    app.dependency_overrides[obter_cliente_llm] = lambda: cliente
"""

import asyncio
import json

from src.services.llm import RespostaDoProvedor

Passo = str | dict | BaseException


class DubleLLM:
    """Cada chamada consome um passo do roteiro; o último se repete.

    Um passo é o texto da resposta, um dicionário (vira JSON) ou uma exceção,
    que é levantada — `FalhaTransitoria`, `LLMRecusouOPedido` etc.
    """

    nome = "duble"

    def __init__(
        self,
        *roteiro: Passo,
        modelo: str = "duble-1",
        atraso_segundos: float = 0.0,
        tokens_entrada: int | None = 10,
        tokens_saida: int | None = 5,
    ) -> None:
        if not roteiro:
            raise ValueError("o dublê precisa de pelo menos um passo")
        self.modelo = modelo
        self.atraso_segundos = atraso_segundos
        self.tokens_entrada = tokens_entrada
        self.tokens_saida = tokens_saida
        self.chamadas: list[dict] = []
        self.fechado = False
        self._roteiro = list(roteiro)

    async def completar(
        self, *, sistema: str, prompt: str, nome_schema: str, schema_json: dict
    ) -> RespostaDoProvedor:
        self.chamadas.append(
            {
                "sistema": sistema,
                "prompt": prompt,
                "nome_schema": nome_schema,
                "schema_json": schema_json,
            }
        )
        passo = self._roteiro[min(len(self.chamadas), len(self._roteiro)) - 1]
        if self.atraso_segundos:
            await asyncio.sleep(self.atraso_segundos)
        if isinstance(passo, BaseException):
            raise passo
        texto = json.dumps(passo) if isinstance(passo, dict) else passo
        return RespostaDoProvedor(
            texto=texto,
            modelo=self.modelo,
            tokens_entrada=self.tokens_entrada,
            tokens_saida=self.tokens_saida,
        )

    async def fechar(self) -> None:
        self.fechado = True
