"""Contrato HTTP da busca de trabalhos na OpenAlex."""

from pydantic import BaseModel, Field

from src.services.openalex import (
    MAXIMO_DE_BUSCAS,
    ORDENACOES,
    QUANTIDADE_MAXIMA,
    TOP_PADRAO,
)


class PedidoDeBusca(BaseModel):
    buscas: list[str] = Field(
        min_length=1,
        description=(
            "Strings de busca, em inglês. Aceitam aspas para frase exata, "
            "AND/OR/NOT em maiúsculas e parênteses para agrupar. Acima de "
            f"{MAXIMO_DE_BUSCAS} a lista é cortada."
        ),
    )
    limite: int | None = Field(
        default=None,
        description=(
            f"Quantos trabalhos saem no fim; {TOP_PADRAO} por padrão. Com "
            "várias buscas, a lista intercala por posição."
        ),
    )
    quantidade: int | None = Field(
        default=None,
        description=(
            f"Candidatos por busca, antes de juntar; teto de {QUANTIDADE_MAXIMA}. "
            "Vêm os mais relevantes, não os primeiros de uma lista qualquer."
        ),
    )
    ordenar_por: str = Field(
        default="relevancia",
        description=(
            f"Um de {sorted(ORDENACOES)}. Fora de 'relevancia', a OpenAlex "
            "devolve a pontuação de relevância nula."
        ),
    )


class TrabalhoEncontrado(BaseModel):
    id: str | None
    titulo: str
    ano: int | None
    doi: str | None
    retratado: bool
    abstract: str | None
    relevancia: float | None
    citacoes: int | None


class RespostaDaBusca(BaseModel):
    trabalhos: list[TrabalhoEncontrado]
    buscas_com_falha: dict[str, str]
    total_por_busca: dict[str, int]
