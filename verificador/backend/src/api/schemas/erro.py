"""Contrato público e fechado dos erros HTTP do gateway."""

from enum import Enum

from pydantic import BaseModel, ConfigDict


class CodigoErro(str, Enum):
    ENTRADA_INVALIDA = "entrada_invalida"
    LIMITE_EXCEDIDO = "limite_excedido"
    OPENALEX_INDISPONIVEL = "openalex_indisponivel"
    LLM_TIMEOUT = "llm_timeout"
    RECURSO_NAO_ENCONTRADO = "recurso_nao_encontrado"
    METODO_NAO_PERMITIDO = "metodo_nao_permitido"
    ERRO_REQUISICAO = "erro_requisicao"
    SERVICO_INDISPONIVEL = "servico_indisponivel"
    ERRO_INTERNO = "erro_interno"


class Erro(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: CodigoErro
    mensagem: str
