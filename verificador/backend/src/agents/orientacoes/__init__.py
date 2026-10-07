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

Pelo mesmo motivo existe o bloco interno, entre `<!-- interno -->` e
`<!-- /interno -->`: o arquivo é lido por duas plateias e só uma delas paga por
ele. A equipe precisa saber por que uma regra existe; o modelo precisa da regra.
O que está no bloco fica no arquivo, aparece no diff e no histórico, e não entra
no prompt — `corpo` traz o documento inteiro, `prompt` traz o que vai ao modelo.

Não é economia decorativa: no plano gratuito da Groq a janela é de 8 mil tokens
por minuto, e uma verificação chama o modelo duas vezes. Cada trecho de prosa
que viaja em toda chamada sai do orçamento da verificação seguinte.

    from src.agents import orientacoes

    orientacoes.juntar("triador/ORIENTACOES.md", "triador/referencias/exemplos.md")
"""

import re
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

# Delimitadores do que é leitura da equipe e não vai ao modelo. Comentário de
# Markdown porque ele já é invisível em qualquer renderização do arquivo: quem
# abre o documento no GitHub vê o texto, e não a marcação em volta dele.
ABERTURA_INTERNA = "<!-- interno -->"
FECHAMENTO_INTERNO = "<!-- /interno -->"


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

    @property
    def prompt(self) -> str:
        """O corpo sem os blocos internos: é isto que o modelo recebe."""
        return _sem_blocos_internos(self.corpo)


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
    """O corpo dos documentos, na ordem dada, pronto para entrar no prompt.

    Sem os blocos internos, porque o destino é o modelo.
    """
    return SEPARADOR.join(ler(caminho).prompt for caminho in caminhos)


def _sem_blocos_internos(corpo: str) -> str:
    """Tira os trechos entre `<!-- interno -->` e `<!-- /interno -->`.

    Bloco aberto e não fechado é descartado até o fim do documento: o erro de
    marcação custa um pedaço do prompt, e não um prompt com a prosa de
    manutenção dentro — que é justamente o que o bloco existe para evitar.

    Os espaços em volta são colapsados para que o corte não deixe três linhas em
    branco no meio do texto que o modelo lê.
    """
    partes: list[str] = []
    resto = corpo
    while True:
        antes, marca, depois = resto.partition(ABERTURA_INTERNA)
        partes.append(antes)
        if not marca:
            break
        _, fechou, resto = depois.partition(FECHAMENTO_INTERNO)
        if not fechou:
            break

    return re.sub(r"\n{3,}", "\n\n", "".join(partes)).strip()


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
