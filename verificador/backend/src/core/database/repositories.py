"""Operações de domínio sobre o banco.

Por enquanto só a chave de busca; as operações de leitura e escrita entram na
subtask seguinte.
"""

import hashlib
import re
import unicodedata

_ESPACOS = re.compile(r"\s+")


def normalizar_trecho(trecho: str) -> str:
    """Reduz variações de escrita do mesmo texto a uma forma única.

    Sem isto, "A polilaminina  regenera" e "a polilaminina regenera" viram
    chaves diferentes e o cache quase nunca acerta.
    """
    # NFC junta acento e letra num único caractere. Texto copiado da web vem
    # ora composto, ora decomposto: "á" pode ser um caractere ou dois, visual-
    # mente idênticos e com bytes diferentes. Sem isto, o mesmo trecho geraria
    # chaves diferentes dependendo da página de origem.
    texto = unicodedata.normalize("NFC", trecho)
    # casefold, e não lower: trata casos que lower deixa passar em outros
    # idiomas, e é idêntico a lower em português.
    return _ESPACOS.sub(" ", texto).strip().casefold()


def gerar_hash_do_trecho(trecho: str) -> str:
    """Chave de busca do cache, derivada do trecho — nunca da saída de um LLM.

    Saída de LLM não se repete entre execuções: uma chave derivada dela mudaria
    a cada chamada e o cache nunca encontraria nada. A consulta acontece antes
    da esteira de agentes, e é daí que vem a economia.
    """
    return hashlib.sha256(normalizar_trecho(trecho).encode("utf-8")).hexdigest()
