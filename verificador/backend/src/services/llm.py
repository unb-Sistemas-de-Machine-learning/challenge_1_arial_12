"""Camada única de acesso a LLM, usada pelos agentes Triador e Juiz.

Recebe um prompt e o formato esperado da resposta (um modelo Pydantic) e
devolve uma instância desse modelo, já validada, ou um erro de domínio. Não
contém regra de agente: não sabe o que é gerar variação nem julgar evidência.

Duas peças, com responsabilidades separadas:

- o **provedor** faz uma requisição e classifica a falha (vale repetir ou não);
- o **`ClienteLLM`** cuida do resto: prazo total, repetição, validação e log.

A separação existe para o dublê de teste entrar no lugar do provedor, e não
do cliente: assim timeout, repetição e validação rodam de verdade na suíte.

Só camada gratuita (spec 003): Groq e Gemini, ambos pela API compatível com a
OpenAI. Por isso a biblioteca `openai` é o cliente HTTP dos dois, e o que muda
entre eles é o endereço, a chave e o modelo.
"""

import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol, TypeVar

import httpx
import openai
from pydantic import BaseModel, ValidationError

from src.core.config import settings as settings_module

logger = logging.getLogger("verificador.llm")

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class PerfilDeProvedor:
    base_url: str
    modelo_padrao: str


# Os modelos gratuitos mudam com frequência: confira antes de trocar o padrão.
# Groq: https://console.groq.com/docs/rate-limits
# Gemini: https://ai.google.dev/gemini-api/docs/pricing
PROVEDORES: dict[str, PerfilDeProvedor] = {
    "groq": PerfilDeProvedor(
        base_url="https://api.groq.com/openai/v1",
        # Aceita saída estruturada (`json_schema`) e é rápido.
        modelo_padrao="openai/gpt-oss-20b",
    ),
    "gemini": PerfilDeProvedor(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        modelo_padrao="gemini-3.5-flash",
    ),
}

# Um Retry-After longo seguraria a requisição do leitor; o prazo total da
# chamada já corta antes, mas o teto evita dormir à toa.
TETO_ESPERA_SEGUNDOS = 5.0

INSTRUCAO_JSON = (
    "Responda somente com um objeto JSON que obedeça a este JSON Schema, "
    "sem nenhum texto antes ou depois:\n{schema}"
)

# Alguns modelos cercam o JSON com bloco de código mesmo em modo JSON.
_BLOCO_DE_CODIGO = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


# --- Erros --------------------------------------------------------------------


class ErroLLM(RuntimeError):
    """Base dos erros da camada. O gateway traduz todos para o contrato 011."""


class LLMTempoEsgotado(ErroLLM):
    """A chamada passou do prazo total, tentativas incluídas."""


class LLMIndisponivel(ErroLLM):
    """O provedor não respondeu de forma utilizável dentro das tentativas."""


class LLMRecusouOPedido(LLMIndisponivel):
    """4xx do provedor: chave inválida, modelo inexistente. Repetir não adianta."""


class RespostaInvalidaDoLLM(ErroLLM):
    """A resposta não é JSON ou não obedece ao schema pedido."""


class FalhaTransitoria(Exception):
    """Sinal do provedor para a camada: esta falha vale uma nova tentativa."""

    def __init__(self, motivo: str, *, retry_after: float | None = None) -> None:
        super().__init__(motivo)
        self.retry_after = retry_after


# --- Provedor -----------------------------------------------------------------


@dataclass(frozen=True)
class RespostaDoProvedor:
    texto: str
    modelo: str
    tokens_entrada: int | None
    tokens_saida: int | None


class ProvedorLLM(Protocol):
    """O que a camada precisa de um provedor. O `DubleLLM` segue o mesmo."""

    nome: str
    modelo: str

    async def completar(
        self, *, sistema: str, prompt: str, nome_schema: str, schema_json: dict
    ) -> RespostaDoProvedor:
        """Uma requisição. Levanta `FalhaTransitoria` quando vale repetir."""
        ...

    async def fechar(self) -> None: ...


def _segundos_do_retry_after(resposta: httpx.Response | None) -> float | None:
    if resposta is None:
        return None
    try:
        return float(resposta.headers.get("retry-after", ""))
    except ValueError:
        return None


class ProvedorCompativelComOpenAI:
    """Groq ou Gemini, pelo endpoint que imita a API da OpenAI."""

    def __init__(
        self,
        *,
        nome: str,
        api_key: str,
        modelo: str | None = None,
        formato_json: str = "json_schema",
        timeout_segundos: float = 15.0,
        temperatura: float = 0.0,
        seed: int | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if nome not in PROVEDORES:
            raise ValueError(
                f"LLM_PROVEDOR inválido: {nome!r}. Use {', '.join(PROVEDORES)}"
            )
        if not api_key or not api_key.strip():
            raise ValueError("LLM_API_KEY é obrigatória para usar a camada de LLM")

        perfil = PROVEDORES[nome]
        self.nome = nome
        self.modelo = modelo or perfil.modelo_padrao
        self.formato_json = formato_json
        # Zero por decisão, e não por acaso: os dois agentes fazem extração e
        # classificação, trabalho em que criatividade é defeito. Com a
        # temperatura padrão do provedor, o mesmo trecho rendia termos
        # diferentes a cada chamada e a verificação achava o estudo numa
        # tentativa e não achava na seguinte.
        self.temperatura = temperatura
        # Semente é a outra metade: com ela, o provedor que a respeita (a Groq
        # documenta; a do Gemini ignora em silêncio) devolve a mesma amostragem
        # para o mesmo pedido. Não é garantia contratual em nenhum dos dois —
        # a determinação de verdade está no desenho do agente.
        self.seed = seed
        self._cliente = openai.AsyncOpenAI(
            api_key=api_key.strip(),
            base_url=perfil.base_url,
            # Quem repete é a camada: ela precisa contar as tentativas para o
            # log e respeitar o prazo total da chamada.
            max_retries=0,
            timeout=timeout_segundos,
            http_client=http_client,
        )

    def _formato_de_resposta(self, nome_schema: str, schema_json: dict) -> dict:
        if self.formato_json == "json_object":
            return {"type": "json_object"}
        return {
            "type": "json_schema",
            # Sem `strict`: o modo estrito exige um schema reescrito
            # (`additionalProperties: false` em todo objeto), e a validação
            # que vale é a do Pydantic, na camada.
            "json_schema": {"name": nome_schema, "schema": schema_json},
        }

    async def completar(
        self, *, sistema: str, prompt: str, nome_schema: str, schema_json: dict
    ) -> RespostaDoProvedor:
        # A semente só vai quando configurada: mandar `seed: null` faz provedor
        # que não conhece o parâmetro recusar o pedido inteiro com 400.
        opcionais: dict[str, object] = {} if self.seed is None else {"seed": self.seed}
        try:
            resposta = await self._cliente.chat.completions.create(
                model=self.modelo,
                messages=[
                    {"role": "system", "content": sistema},
                    {"role": "user", "content": prompt},
                ],
                response_format=self._formato_de_resposta(nome_schema, schema_json),
                temperature=self.temperatura,
                **opcionais,
            )
        except openai.APIConnectionError as erro:
            # Inclui o timeout da requisição (`APITimeoutError`).
            raise FalhaTransitoria(f"falha de conexão com {self.nome}") from erro
        except openai.RateLimitError as erro:
            raise FalhaTransitoria(
                f"limite de uso do {self.nome} atingido (429)",
                retry_after=_segundos_do_retry_after(erro.response),
            ) from erro
        except openai.InternalServerError as erro:
            raise FalhaTransitoria(
                f"resposta {erro.status_code} do {self.nome}"
            ) from erro
        except openai.APIStatusError as erro:
            if erro.code == "json_validate_failed":
                # A Groq confere o JSON do modelo e devolve 400 quando ele
                # não bate com o schema: o defeito é da resposta, não do pedido.
                raise RespostaInvalidaDoLLM(
                    f"{self.nome} gerou JSON fora do schema"
                ) from erro
            # Só o status: o corpo de erro é do provedor e não precisa ir
            # para o log da aplicação.
            raise LLMRecusouOPedido(
                f"{self.nome} recusou o pedido com {erro.status_code}"
            ) from erro

        escolha = resposta.choices[0] if resposta.choices else None
        texto = escolha.message.content if escolha else None
        if not texto:
            raise RespostaInvalidaDoLLM(f"{self.nome} devolveu uma resposta vazia")

        uso = resposta.usage
        return RespostaDoProvedor(
            texto=texto,
            modelo=resposta.model or self.modelo,
            tokens_entrada=uso.prompt_tokens if uso else None,
            tokens_saida=uso.completion_tokens if uso else None,
        )

    async def fechar(self) -> None:
        await self._cliente.close()


# --- Cliente ------------------------------------------------------------------


@dataclass
class _Andamento:
    """O que a chamada acumulou até aqui, para a linha de log."""

    tentativas: int = 0
    tokens_entrada: int | None = None
    tokens_saida: int | None = None


def _validar(texto: str, schema: type[T]) -> T:
    limpo = texto.strip()
    cercado = _BLOCO_DE_CODIGO.match(limpo)
    if cercado:
        limpo = cercado.group(1)
    try:
        return schema.model_validate_json(limpo)
    except ValidationError as erro:
        # Sem ecoar a resposta: ela pode ser longa e não ajuda o leitor.
        raise RespostaInvalidaDoLLM(
            f"resposta fora do schema {schema.__name__}: {erro.error_count()} erro(s)"
        ) from erro


class ClienteLLM:
    """A porta única dos agentes para o LLM."""

    def __init__(
        self,
        provedor: ProvedorLLM,
        *,
        timeout_segundos: float = 15.0,
        max_tentativas: int = 2,
        espera_base_segundos: float = 0.5,
        dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
        relogio: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.provedor = provedor
        self.timeout_segundos = timeout_segundos
        self.max_tentativas = max(1, max_tentativas)
        self.espera_base_segundos = espera_base_segundos
        self._dormir = dormir
        self._relogio = relogio

    @classmethod
    def a_partir_das_configuracoes(cls) -> "ClienteLLM":
        # Pelo módulo, e não pela função importada: é o que permite trocar a
        # configuração em teste.
        settings = settings_module.get_settings()
        chave = settings.llm_api_key
        provedor = ProvedorCompativelComOpenAI(
            nome=settings.llm_provedor,
            api_key=chave.get_secret_value() if chave else "",
            modelo=settings.llm_modelo,
            formato_json=settings.llm_formato_json,
            timeout_segundos=settings.llm_timeout_segundos,
            temperatura=settings.llm_temperatura,
            seed=settings.llm_seed,
        )
        return cls(
            provedor,
            timeout_segundos=settings.llm_timeout_segundos,
            max_tentativas=settings.llm_max_tentativas,
        )

    async def gerar(
        self,
        prompt: str,
        schema: type[T],
        *,
        sistema: str | None = None,
        timeout_segundos: float | None = None,
    ) -> T:
        """Devolve a resposta do LLM como instância de `schema`, já validada.

        Levanta `LLMTempoEsgotado`, `LLMIndisponivel` ou `RespostaInvalidaDoLLM`.
        """
        prazo = (
            timeout_segundos if timeout_segundos is not None else self.timeout_segundos
        )
        schema_json = schema.model_json_schema()
        instrucao = INSTRUCAO_JSON.format(schema=schema_json)
        sistema_final = f"{sistema}\n\n{instrucao}" if sistema else instrucao

        andamento = _Andamento()
        inicio = self._relogio()
        resultado = "ok"
        try:
            try:
                async with asyncio.timeout(prazo):
                    resposta = await self._com_repeticao(
                        andamento,
                        sistema=sistema_final,
                        prompt=prompt,
                        nome_schema=schema.__name__,
                        schema_json=schema_json,
                    )
            except TimeoutError as erro:
                raise LLMTempoEsgotado(
                    f"{self.provedor.nome} não respondeu em {prazo:g}s"
                ) from erro
            andamento.tokens_entrada = resposta.tokens_entrada
            andamento.tokens_saida = resposta.tokens_saida
            return _validar(resposta.texto, schema)
        except LLMTempoEsgotado:
            resultado = "tempo_esgotado"
            raise
        except RespostaInvalidaDoLLM:
            resultado = "resposta_invalida"
            raise
        except LLMIndisponivel:
            resultado = "indisponivel"
            raise
        finally:
            self._registrar(andamento, resultado, inicio)

    async def _com_repeticao(
        self, andamento: _Andamento, **pedido: object
    ) -> RespostaDoProvedor:
        ultima: FalhaTransitoria | None = None
        for tentativa in range(1, self.max_tentativas + 1):
            andamento.tentativas = tentativa
            try:
                return await self.provedor.completar(**pedido)
            except FalhaTransitoria as falha:
                ultima = falha
                if tentativa == self.max_tentativas:
                    break
                await self._dormir(self._espera(tentativa, falha.retry_after))

        raise LLMIndisponivel(
            f"{self.provedor.nome} indisponível após "
            f"{self.max_tentativas} tentativa(s): {ultima}"
        ) from ultima

    def _espera(self, tentativa: int, retry_after: float | None) -> float:
        if retry_after is not None:
            return min(retry_after, TETO_ESPERA_SEGUNDOS)
        return self.espera_base_segundos * (2 ** (tentativa - 1))

    def _registrar(self, andamento: _Andamento, resultado: str, inicio: float) -> None:
        # Só campos escolhidos aqui: nem a chave, nem o prompt, nem a resposta.
        nivel = logging.INFO if resultado == "ok" else logging.WARNING
        logger.log(
            nivel,
            "llm provedor=%s modelo=%s resultado=%s latencia_ms=%d "
            "tokens_entrada=%s tokens_saida=%s tentativas=%d",
            self.provedor.nome,
            self.provedor.modelo,
            resultado,
            round((self._relogio() - inicio) * 1000),
            andamento.tokens_entrada,
            andamento.tokens_saida,
            andamento.tentativas,
        )

    async def fechar(self) -> None:
        await self.provedor.fechar()


# --- Cliente compartilhado e dependência --------------------------------------

_compartilhado: ClienteLLM | None = None


def cliente_compartilhado() -> ClienteLLM:
    """Um cliente por processo: cada instância abre um pool de conexões novo."""
    global _compartilhado
    if _compartilhado is None:
        _compartilhado = ClienteLLM.a_partir_das_configuracoes()
    return _compartilhado


def obter_cliente_llm() -> ClienteLLM:
    """Dependência do FastAPI: `Depends(obter_cliente_llm)` nas rotas.

    É a costura de teste: `app.dependency_overrides[obter_cliente_llm]` põe um
    `ClienteLLM` com o `DubleLLM` no lugar, sem rede e sem chave.
    """
    try:
        return cliente_compartilhado()
    except ValueError as erro:
        # Configuração faltando é problema do servidor, não de quem chamou.
        logger.error("Camada de LLM indisponível por configuração: %s", erro)
        raise LLMIndisponivel("configuração da camada de LLM incompleta") from erro


async def encerrar_cliente_compartilhado() -> None:
    """Fecha o pool no encerramento da aplicação."""
    global _compartilhado
    if _compartilhado is not None:
        await _compartilhado.fechar()
        _compartilhado = None
