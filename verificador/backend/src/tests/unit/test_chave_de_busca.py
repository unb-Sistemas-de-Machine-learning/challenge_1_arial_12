"""A chave de busca reconhece o mesmo trecho escrito de formas diferentes.

Nenhum destes casos toca banco: são funções puras, e rodam com o Postgres
desligado.
"""

import unicodedata

import pytest

from src.core.database.models import TAMANHO_HASH
from src.core.database.repositories import gerar_hash_do_trecho, normalizar_trecho

TRECHO = "A polilaminina regenera a medula espinhal"

EQUIVALENTES = [
    pytest.param("a polilaminina regenera a medula espinhal", id="minusculas"),
    pytest.param("A POLILAMININA REGENERA A MEDULA ESPINHAL", id="maiusculas"),
    pytest.param("A polilaminina  regenera a  medula espinhal", id="espaco_duplo"),
    pytest.param("  A polilaminina regenera a medula espinhal  ", id="bordas"),
    pytest.param("A polilaminina\nregenera a medula espinhal", id="quebra_de_linha"),
    pytest.param("A polilaminina\tregenera a medula espinhal", id="tabulacao"),
]

DIFERENTES = [
    pytest.param("A polilaminina regenera o nervo óptico", id="outro_objeto"),
    pytest.param("A polilaminina nao regenera a medula espinhal", id="negacao"),
    pytest.param("A polilaminina regenera a medula", id="trecho_menor"),
    pytest.param("", id="vazio"),
]


@pytest.mark.parametrize("variacao", EQUIVALENTES)
def test_mesma_pergunta_escrita_diferente_gera_a_mesma_chave(variacao: str) -> None:
    assert gerar_hash_do_trecho(variacao) == gerar_hash_do_trecho(TRECHO)


@pytest.mark.parametrize("outro", DIFERENTES)
def test_perguntas_diferentes_geram_chaves_diferentes(outro: str) -> None:
    """Sem este caso, uma função que ignora a entrada passaria em tudo acima."""
    assert gerar_hash_do_trecho(outro) != gerar_hash_do_trecho(TRECHO)


def test_acento_composto_e_decomposto_geram_a_mesma_chave() -> None:
    """Decisão registrada: acento **conta** para a chave, mas a forma como ele
    é codificado não.

    "médula" com o acento num caractere só e com acento separado são visualmente
    idênticos e têm bytes diferentes. Texto copiado da web vem das duas formas.
    """
    composto = unicodedata.normalize("NFC", "A polilaminina regenera a médula")
    decomposto = unicodedata.normalize("NFD", "A polilaminina regenera a médula")

    assert composto != decomposto, "as duas formas precisam diferir em bytes"
    assert gerar_hash_do_trecho(composto) == gerar_hash_do_trecho(decomposto)


def test_trecho_sem_acento_e_pergunta_diferente() -> None:
    """A outra metade da decisão: não removemos acento.

    "médula" e "medula" são palavras distintas; tratá-las como iguais faria o
    cache devolver a resposta de uma pergunta que não foi feita.
    """
    assert gerar_hash_do_trecho("a médula") != gerar_hash_do_trecho("a medula")


def test_a_chave_cabe_na_coluna_declarada() -> None:
    chave = gerar_hash_do_trecho(TRECHO)
    assert len(chave) == TAMANHO_HASH
    assert chave == chave.lower(), "hexadecimal minúsculo, como a coluna espera"


def test_a_normalizacao_e_estavel() -> None:
    """Normalizar duas vezes dá no mesmo que normalizar uma."""
    uma_vez = normalizar_trecho(TRECHO)
    assert normalizar_trecho(uma_vez) == uma_vez
