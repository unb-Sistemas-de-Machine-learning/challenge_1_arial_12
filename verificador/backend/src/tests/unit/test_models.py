"""A estrutura declarada das tabelas, conferida sem abrir conexão com banco.

Estes testes leem apenas os metadados em memória. Existem porque erro de schema
não aparece em teste de comportamento: ele aparece quando a tabela já tem dado,
e aí corrigir vira migração de dado.
"""

import pytest
from sqlalchemy import Boolean, DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB

from src.core.database.models import Base, Feedback, Veredito


def tabela(nome: str):
    return Base.metadata.tables[nome]


def test_as_duas_tabelas_existem_com_os_nomes_do_desenho() -> None:
    assert set(Base.metadata.tables) == {"veredito", "feedback"}
    assert Veredito.__tablename__ == "veredito"
    assert Feedback.__tablename__ == "feedback"


def test_veredito_tem_as_colunas_e_tipos_do_desenho() -> None:
    colunas = tabela("veredito").columns
    assert set(colunas.keys()) == {
        "id",
        "hash_trecho",
        "trecho_avaliado",
        "estado_veredito",
        "resposta",
        "criado_em",
    }
    assert isinstance(colunas["id"].type, Integer)
    assert colunas["id"].primary_key
    assert colunas["hash_trecho"].type.length == 64
    assert isinstance(colunas["trecho_avaliado"].type, Text)
    assert isinstance(colunas["estado_veredito"].type, Text)
    assert isinstance(colunas["resposta"].type, JSONB)
    for nome in ("hash_trecho", "trecho_avaliado", "estado_veredito", "resposta"):
        assert not colunas[nome].nullable, f"{nome} não deveria aceitar nulo"


def test_feedback_tem_as_colunas_e_tipos_do_desenho() -> None:
    colunas = tabela("feedback").columns
    assert set(colunas.keys()) == {"id", "veredito_id", "util", "criado_em"}
    assert colunas["id"].primary_key
    assert isinstance(colunas["util"].type, Boolean)
    assert not colunas["util"].nullable
    assert not colunas["veredito_id"].nullable


def test_o_hash_e_indexado_mas_nao_unico() -> None:
    """Decisão registrada na TechSpec: unicidade quebraria a atribuição do
    feedback quando o cache vencer e a verificação for refeita."""
    veredito = tabela("veredito")
    indices_do_hash = [
        indice
        for indice in veredito.indexes
        if [coluna.name for coluna in indice.columns] == ["hash_trecho"]
    ]
    assert indices_do_hash, (
        "o hash precisa de índice, senão a busca do cache varre a tabela"
    )
    assert all(not indice.unique for indice in indices_do_hash)
    assert not veredito.columns["hash_trecho"].unique


def test_feedback_aponta_para_veredito_por_chave_estrangeira() -> None:
    """Sem isso o banco aceitaria avaliação órfã, apontando para nada."""
    chaves = list(tabela("feedback").columns["veredito_id"].foreign_keys)
    assert len(chaves) == 1
    assert chaves[0].target_fullname == "veredito.id"


@pytest.mark.parametrize("nome_tabela", ["veredito", "feedback"])
def test_criado_em_guarda_fuso_e_vem_do_relogio_do_banco(nome_tabela: str) -> None:
    coluna = tabela(nome_tabela).columns["criado_em"]
    assert isinstance(coluna.type, DateTime)
    assert coluna.type.timezone, "sem fuso, o instante vira ambíguo entre máquinas"
    assert coluna.server_default is not None, (
        "o relógio é o do banco, não o da aplicação"
    )
    assert not coluna.nullable
