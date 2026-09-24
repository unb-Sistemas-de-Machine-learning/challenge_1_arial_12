"""Contrato HTTP compartilhado com a extensão do navegador."""

from enum import Enum

from pydantic import BaseModel


class Estado(str, Enum):
    SUSTENTA = "sustenta"
    EXAGERA = "exagera"
    NADA_ENCONTRADO = "nada_encontrado"


class Pedido(BaseModel):
    trecho: str
    url: str | None = None


class Estudo(BaseModel):
    titulo: str
    ano: int | None
    doi: str | None
    retratado: bool


class Veredito(BaseModel):
    estado: Estado
    estudo: Estudo | None
    termos: list[str]
    justificativa: str
