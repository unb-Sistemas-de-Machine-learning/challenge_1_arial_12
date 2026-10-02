"""Orientações dos agentes: o prompt mora em Markdown, não em f-string.

Cada agente que fala com o LLM tem uma pasta aqui com o que ele deve seguir.
Este módulo só lê esses arquivos; a regra de cada agente fica com o agente.

A razão de o texto sair do código é a mesma que fez surgir a pasta `specs/`:
quem revisa a instrução dada ao modelo não é necessariamente quem mexe em
Python, e instrução dentro de uma f-string não é revisável em PR — aparece como
mudança de código, com o diff embaralhado pela indentação. Em Markdown, a
mudança de uma regra é uma linha de diff, e o histórico do arquivo conta quando
cada regra entrou.

O cabeçalho de metadados (`---` no topo, `chave: valor` dentro) não vai para o
modelo: ele é o registro de versão, e é o que permite ligar uma rodada de
avaliação à versão das orientações que a produziu.

    from src.agents import orientacoes

    orientacoes.juntar("triador/ORIENTACOES.md", "triador/referencias/exemplos.md")
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

PASTA = Path(__file__).resolve().parent

# Entre dois documentos, uma linha em branco: eles já começam com um título de
# nível 1, que é o que separa as seções aos olhos do modelo.
SEPARADOR = "\n\n"

ABERTURA_DE_METADADOS = "---"


class OrientacaoAusente(RuntimeError):
    """O arquivo pedido não existe.

    É defeito de programação, e não condição de operação: os caminhos são
    constantes do módulo do agente. Falhar aqui é melhor do que mandar para o
    modelo um prompt sem as orientações e descobrir pelo resultado.
    """


@dataclass(frozen=True)
class Documento:
    caminho: str
    metadados: Mapping[str, str]
    corpo: str

    @property
    def versao(self) -> str:
        """A versão declarada no cabeçalho, ou `?` quando não há."""
        return self.metadados.get("versao", "?")


@lru_cache
def ler(caminho: str) -> Documento:
    """Lê um documento da pasta de orientações, separando cabeçalho e corpo.

    Em cache: o arquivo não muda enquanto o processo roda, e a alternativa é
    reler o disco a cada verificação.
    """
    arquivo = PASTA / caminho
    try:
        texto = arquivo.read_text(encoding="utf-8")
    except OSError as erro:
        raise OrientacaoAusente(f"orientação não encontrada: {caminho}") from erro

    metadados, corpo = _separar_metadados(texto)
    return Documento(
        caminho=caminho, metadados=MappingProxyType(metadados), corpo=corpo
    )


@lru_cache
def juntar(*caminhos: str) -> str:
    """O corpo dos documentos, na ordem dada, pronto para entrar no prompt."""
    return SEPARADOR.join(ler(caminho).corpo for caminho in caminhos)


def _separar_metadados(texto: str) -> tuple[dict[str, str], str]:
    """Tira o cabeçalho `---` do topo, se houver, e devolve as duas partes.

    Sem biblioteca de YAML de propósito: o cabeçalho é um punhado de
    `chave: valor` em uma linha cada, e aceitar mais do que isso convidaria a
    pôr no cabeçalho o que deveria estar no corpo.
    """
    linhas = texto.strip().splitlines()
    if not linhas or linhas[0].strip() != ABERTURA_DE_METADADOS:
        return {}, texto.strip()

    metadados: dict[str, str] = {}
    for fim, linha in enumerate(linhas[1:], start=1):
        if linha.strip() == ABERTURA_DE_METADADOS:
            return metadados, "\n".join(linhas[fim + 1 :]).strip()
        chave, separador, valor = linha.partition(":")
        if separador:
            metadados[chave.strip()] = valor.strip()

    # Cabeçalho aberto e não fechado: trata tudo como corpo, em vez de devolver
    # um documento vazio e um prompt sem instrução.
    return {}, texto.strip()
