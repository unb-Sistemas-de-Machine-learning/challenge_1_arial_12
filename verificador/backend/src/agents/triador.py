"""Agente Triador: transforma o trecho do leitor nas buscas que vão à OpenAlex.

O trabalho é partido em duas metades, e a divisão é a razão de ser deste módulo:

- o **LLM extrai termos** — a condição, a intervenção, o desfecho e a população
  de que o trecho fala, já no jargão inglês da literatura;
- o **código monta as strings** — combinando esses termos nos eixos fixos de
  `EIXOS`, normalizando a forma e aplicando o glossário.

Antes, o modelo escrevia as strings inteiras, e era isso que fazia a verificação
achar o estudo numa tentativa e não achar na seguinte: a cada chamada ele
escolhia outros sinônimos, outra quantidade de palavras, outra ordem. O que muda
não é o assunto, é a amostragem — e amostragem não se conserta pedindo coerência
ao modelo, se conserta tirando dele a decisão que varia.

Sobrou para o modelo a parte que só ele faz (reconhecer o conceito e traduzi-lo)
e, mesmo nela, com as escolhas recorrentes fixadas num glossário versionado. Do
glossário para dentro a montagem é determinística: os mesmos termos extraídos
produzem byte a byte a mesma lista de buscas, na mesma ordem.

As instruções que o modelo recebe **não** moram aqui: elas estão em
`src/agents/orientacoes/triador/`, em Markdown, para que mudar uma regra seja
uma linha de diff que a equipe revisa em PR. Este módulo as carrega e garante o
que elas prometem.
"""

import logging
import re
import unicodedata
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from functools import lru_cache

from pydantic import BaseModel, Field

from src.agents import orientacoes
from src.services.llm import ClienteLLM, ErroLLM

logger = logging.getLogger("verificador.agentes.triador")

ARQUIVO_DE_ORIENTACOES = "triador/ORIENTACOES.md"
ARQUIVO_DE_EXEMPLOS = "triador/referencias/exemplos.md"
ARQUIVO_DO_GLOSSARIO = "triador/referencias/glossario.md"
# O glossário é a tabela que está sob este título, e não qualquer tabela do
# arquivo: o resto do documento é prosa para quem o edita, e pode ganhar uma
# tabela de exemplo sem que ela entre no vocabulário.
SECAO_DO_GLOSSARIO = "## Tabela"

SISTEMA = (
    "Você é o variador semântico do Verificador Científico. Siga as orientações "
    "do pedido à risca, inclusive quando outro termo parecer melhor: elas "
    "existem para que o mesmo trecho produza sempre os mesmos termos."
)

MOLDE_DO_PROMPT = (
    "{orientacoes}\n\n"
    "## Glossário controlado (conceito em português → termo canônico)\n\n"
    "{glossario}\n\n"
    "{exemplos}\n\n"
    "## Trecho a analisar\n\n"
    "{trecho}\n"
)

# Quantas buscas o código monta, sem contar o trecho original. Seis é o número
# de eixos documentados: o teto existe para quem quiser gastar menos requisição,
# e não para cortar eixo no meio.
MAX_VARIACOES = 6
# Uma busca montada tem umas 40 letras. O teto é para o caso patológico — o
# modelo devolvendo uma frase inteira num campo — e 200 é folgado o bastante
# para nunca cortar termo legítimo.
MAX_TAMANHO_VARIACAO = 200
# Um campo é um conceito, não uma frase. Cinco palavras cabem
# "non small cell lung cancer"; acima disso veio texto no lugar de termo.
MAX_PALAVRAS_POR_CAMPO = 5
# Busca de uma palavra só devolve a literatura inteira da área, e isso não
# verifica alegação nenhuma. Acontece quando dois campos de um eixo caem no
# mesmo termo canônico — "depression" como condição e como desfecho.
MIN_PALAVRAS_POR_BUSCA = 2

CAMPOS = ("condicao", "intervencao", "desfecho", "populacao")

# Palavra de ligação não acrescenta sentido, e a busca da OpenAlex exige todas
# as palavras da string: ela só estreita o resultado. Ficam fora desta lista, de
# propósito, as palavras de uma letra, porque "bisphenol a" e "vitamin a" são
# nomes de substância, e "in", porque "in vitro" e "in vivo" são termos.
CONECTIVOS = frozenset(
    {
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "into",
        "is",
        "its",
        "not",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "versus",
        "vs",
        "with",
    }
)

# Apóstrofo desaparece em vez de virar espaço: "Parkinson's" é "parkinsons", e
# não "parkinson s".
SEM_APOSTROFO = str.maketrans("", "", "'’ʼ´")
# Tudo o que não é letra, número, hífen ou espaço vira espaço. A vírgula é o
# caso que importa: na OpenAlex ela separa filtros, e uma busca com vírgula
# deixa de ser uma busca.
NAO_TERMO = re.compile(r"[^\w\s-]|_", re.UNICODE)


class TermosDeBusca(BaseModel):
    """O que o LLM devolve: um conceito por campo, vazio quando o trecho não diz.

    Os quatro campos são obrigatórios na resposta. Campo vazio diz "o trecho não
    traz isso"; campo ausente diz "o modelo não seguiu o formato", que é outra
    coisa e precisa aparecer no log.
    """

    intervencao: str = Field(
        description="O que age: tratamento, substância, hábito, exposição ou "
        "fenômeno, em inglês técnico. Vazio se o trecho não nomear."
    )
    desfecho: str = Field(
        description="O que é afetado: doença, sintoma, medida ou evento, em "
        "inglês técnico. Vazio se o trecho não nomear."
    )
    condicao: str = Field(
        description="A doença ou o contexto clínico em que isso acontece, em "
        "inglês técnico. Vazio se o trecho não nomear."
    )
    populacao: str = Field(
        description="Em quem ou em quê (children, older adults, mice). Vazio se "
        "o trecho não disser."
    )


# --- Forma canônica -----------------------------------------------------------


def forma_canonica(termo: object) -> str:
    """Põe um termo na única forma que o resto do módulo manipula.

    Minúsculas, acento composto (NFC), sem apóstrofo, sem pontuação, sem palavra
    de ligação, espaços colapsados e no máximo `MAX_PALAVRAS_POR_CAMPO`
    palavras. É o que faz `"Alcohol Intake,"` e `"alcohol intake"` serem o mesmo
    termo na hora de consultar o glossário e de descartar busca repetida.
    """
    if not isinstance(termo, str):
        return ""

    texto = unicodedata.normalize("NFC", termo).lower().translate(SEM_APOSTROFO)
    palavras = [
        palavra
        for palavra in NAO_TERMO.sub(" ", texto).split()
        if len(palavra) == 1 or palavra not in CONECTIVOS
    ]

    if len(palavras) > MAX_PALAVRAS_POR_CAMPO:
        logger.warning(
            "Campo com %d palavras cortado em %d: %r",
            len(palavras),
            MAX_PALAVRAS_POR_CAMPO,
            termo,
        )
        palavras = palavras[:MAX_PALAVRAS_POR_CAMPO]

    return " ".join(palavras)


# --- Glossário ----------------------------------------------------------------


@dataclass(frozen=True)
class Glossario:
    """O vocabulário fixado pela equipe, já em forma canônica.

    `canonico_por_forma` mapeia o que pode chegar do modelo — o conceito em
    português, ou uma das variantes em inglês — para o termo que vale.
    `variantes` guarda o caminho inverso, porque a primeira variante de cada
    termo é o que o eixo `sinonimo` usa: a diversidade de vocabulário da busca é
    editada à mão numa tabela, e não sorteada a cada chamada. `conceitos` é só a
    coluna em português, que é a parte do glossário que vai no prompt.
    """

    canonico_por_forma: Mapping[str, str]
    variantes: Mapping[str, tuple[str, ...]]
    conceitos: Mapping[str, str]
    _formas_por_tamanho: tuple[str, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Da forma mais longa para a mais curta, para que "bpa exposure" seja
        # tentada antes de "bpa". Calculado uma vez: `aplicar` roda quatro vezes
        # por verificação e a ordem não muda.
        object.__setattr__(
            self,
            "_formas_por_tamanho",
            tuple(sorted(self.canonico_por_forma, key=lambda f: (-len(f), f))),
        )

    def aplicar(self, termo: str) -> str:
        """Devolve o termo canônico equivalente, ou o próprio termo."""
        if not termo:
            return ""
        canonico = self.canonico_por_forma.get(termo)
        if canonico:
            return canonico

        # Nenhuma linha casou com o campo inteiro: tenta as formas conhecidas
        # dentro dele ("chronic alcohol intake" → "chronic alcohol consumption"),
        # sempre com fronteira de palavra.
        texto = termo
        for forma in self._formas_por_tamanho:
            texto = re.sub(
                rf"(?<!\w){re.escape(forma)}(?!\w)",
                self.canonico_por_forma[forma],
                texto,
            )
        return forma_canonica(texto) if texto != termo else termo

    def primeira_variante(self, termo: str) -> str:
        """A variante que o eixo `sinonimo` usa, ou vazio quando não há."""
        variantes = self.variantes.get(termo, ())
        return variantes[0] if variantes else ""


def ler_glossario(texto: str) -> Glossario:
    """Lê a tabela Markdown do glossário.

    Formato esperado, uma linha por conceito:

        | conceito em português | termo canônico | variante; variante |

    Linha incompleta é ignorada em silêncio, que é a escolha certa para um
    arquivo editado à mão: uma linha mal fechada não deve derrubar a verificação
    inteira. Quem cobra que o arquivo tenha conteúdo é a suíte de testes.
    """
    canonico_por_forma: dict[str, str] = {}
    variantes: dict[str, tuple[str, ...]] = {}
    conceitos: dict[str, str] = {}

    for celulas in _linhas_de_tabela(_secao_do_glossario(texto)):
        if len(celulas) < 3:
            continue
        portugues = forma_canonica(celulas[0])
        canonico = forma_canonica(celulas[1])
        if not portugues or not canonico:
            continue

        formas = tuple(
            dict.fromkeys(forma for forma in _variantes(celulas[2]) if forma)
        )
        if formas:
            variantes[canonico] = formas
        for forma in formas:
            # `setdefault` porque o termo canônico de uma linha pode aparecer na
            # coluna de variantes de outra: o canônico nunca é reescrito.
            canonico_por_forma.setdefault(forma, canonico)
        canonico_por_forma[portugues] = canonico
        canonico_por_forma[canonico] = canonico
        conceitos[portugues] = canonico

    return Glossario(
        canonico_por_forma=canonico_por_forma,
        variantes=variantes,
        conceitos=conceitos,
    )


def _secao_do_glossario(texto: str) -> str:
    """O trecho sob `SECAO_DO_GLOSSARIO`, até o próximo título de seção.

    Texto sem esse título vale inteiro: é como os testes passam uma tabela solta,
    e renomear o título no arquivo não deve apagar o vocabulário em silêncio.
    """
    linhas = texto.splitlines()
    try:
        inicio = next(
            numero
            for numero, linha in enumerate(linhas)
            if linha.strip() == SECAO_DO_GLOSSARIO
        )
    except StopIteration:
        return texto

    fim = next(
        (
            numero
            for numero, linha in enumerate(linhas[inicio + 1 :], start=inicio + 1)
            if linha.startswith("## ")
        ),
        len(linhas),
    )
    return "\n".join(linhas[inicio + 1 : fim])


def _variantes(celula: str) -> Iterator[str]:
    for pedaco in celula.split(";"):
        yield forma_canonica(pedaco)


def _linhas_de_tabela(texto: str) -> Iterator[list[str]]:
    """As linhas de dado das tabelas Markdown do texto, sem o cabeçalho.

    O cabeçalho é reconhecido pela posição que o Markdown lhe dá — a linha
    imediatamente antes da linha de traços —, e não pelo conteúdo. Sem isso,
    "Conceito (PT) | Termo canônico (EN)" entraria no glossário como se fosse
    um conceito, e apareceria no prompt como tal.
    """
    pendente: list[str] | None = None
    for linha in texto.splitlines():
        crua = linha.strip()
        if not crua.startswith("|"):
            if pendente is not None:
                yield pendente
                pendente = None
            continue

        celulas = [celula.strip() for celula in crua.strip("|").split("|")]
        if all(set(celula) <= set(":- ") for celula in celulas):
            # Linha de traços: o que estava pendente era o cabeçalho.
            pendente = None
            continue
        if pendente is not None:
            yield pendente
        pendente = celulas

    if pendente is not None:
        yield pendente


@lru_cache(maxsize=1)
def glossario_padrao() -> Glossario:
    """O glossário do arquivo versionado, lido uma vez por processo."""
    return ler_glossario(orientacoes.ler(ARQUIVO_DO_GLOSSARIO).corpo)


# --- Eixos --------------------------------------------------------------------


@dataclass(frozen=True)
class Eixo:
    """Uma combinação fixa de campos, e portanto uma busca.

    `campos` é também a ordem das palavras na string. `sinonimo_de` lista os
    campos em que o eixo tenta trocar o termo pela primeira variante do
    glossário, na ordem: o primeiro que tiver variante é o trocado.
    """

    id: str
    campos: tuple[str, ...]
    sinonimo_de: tuple[str, ...] = ()


# A ordem é contrato, e não gosto: `buscar_varias` intercala os resultados por
# posição, então o primeiro colocado do primeiro eixo é o primeiro trabalho que
# chega ao Juiz. Por isso o eixo mais preciso vem primeiro.
#
# `nucleo`, `condicao_intervencao` e `condicao_desfecho` esgotam os três pares
# possíveis entre condição, intervenção e desfecho: é o que garante que dois
# campos preenchidos entre os três já produzam busca.
#
# Mexer aqui é mexer em recall; o procedimento está em
# `orientacoes/triador/referencias/formatos-de-busca.md`.
EIXOS: tuple[Eixo, ...] = (
    Eixo("completo", ("condicao", "intervencao", "desfecho")),
    Eixo("nucleo", ("intervencao", "desfecho")),
    Eixo(
        "sinonimo",
        ("intervencao", "desfecho"),
        sinonimo_de=("intervencao", "desfecho"),
    ),
    Eixo("condicao_intervencao", ("condicao", "intervencao")),
    Eixo("condicao_desfecho", ("condicao", "desfecho")),
    Eixo("populacao", ("intervencao", "desfecho", "populacao")),
)


# A ordem em que o leitor entende a alegação: o que age, o que muda, em que
# contexto, em quem. Não é a de `CAMPOS`, que é a ordem das palavras na busca.
ORDEM_DOS_CONCEITOS = ("intervencao", "desfecho", "condicao", "populacao")


@dataclass(frozen=True)
class ExtracaoDoTriador:
    """O que o Triador entrega à esteira.

    `buscas` vai para o Pesquisador; `conceitos` vai para o campo `termos` do
    veredito, que a extensão mostra como etiquetas.
    """

    buscas: list[str]
    conceitos: list[str]


def conceitos_de(canonicos: Mapping[str, str]) -> list[str]:
    """Os termos canônicos na ordem de leitura, sem vazios e sem repetição.

    Repetição acontece de verdade: em "vacina contra a malária", `malaria`
    aparece como condição e dentro da intervenção, e cada campo é um conceito.
    Só o termo idêntico é descartado.
    """
    conceitos: list[str] = []
    for campo in ORDEM_DOS_CONCEITOS:
        termo = canonicos.get(campo, "")
        if termo and termo not in conceitos:
            conceitos.append(termo)
    return conceitos


def canonizar_termos(termos: TermosDeBusca, glossario: Glossario) -> dict[str, str]:
    """Normaliza os quatro campos e aplica o glossário em cada um."""
    return {
        campo: glossario.aplicar(forma_canonica(getattr(termos, campo)))
        for campo in CAMPOS
    }


def montar_buscas(
    termos: Mapping[str, str],
    glossario: Glossario,
    eixos: Sequence[Eixo] = EIXOS,
) -> list[tuple[str, str]]:
    """Monta as buscas dos eixos aplicáveis, na ordem de `EIXOS`, sem repetição.

    Devolve pares `(id do eixo, busca)`: o id não vai para a OpenAlex, mas é o
    que permite ao log dizer qual eixo produziu qual string.
    """
    montadas: list[tuple[str, str]] = []
    vistas: set[frozenset[str]] = set()

    for eixo in eixos:
        palavras = _palavras_do_eixo(eixo, termos, glossario)
        if palavras is None or len(palavras) < MIN_PALAVRAS_POR_BUSCA:
            continue
        # Pelo conjunto de palavras, e não pela string: a busca da OpenAlex é a
        # conjunção dos termos, então duas ordens das mesmas palavras gastam
        # duas requisições para trazer o mesmo resultado. Dois eixos caem no
        # mesmo conjunto com frequência — sem desfecho, `completo` e
        # `condicao_intervencao` são a mesma busca.
        if frozenset(palavras) in vistas:
            continue
        vistas.add(frozenset(palavras))
        montadas.append((eixo.id, " ".join(palavras)))

    return montadas


def _palavras_do_eixo(
    eixo: Eixo, termos: Mapping[str, str], glossario: Glossario
) -> list[str] | None:
    """As palavras da busca do eixo, ou `None` quando ele não se aplica.

    Palavra repetida entre dois campos entra uma vez só: a condição `malaria`
    com a intervenção `malaria vaccine` daria "malaria malaria vaccine", e a
    busca da OpenAlex exige cada palavra uma vez — repetir só desperdiça
    requisição.
    """
    valores = {campo: termos.get(campo, "") for campo in eixo.campos}
    if not all(valores.values()):
        return None

    if eixo.sinonimo_de:
        trocado = False
        for campo in eixo.sinonimo_de:
            variante = glossario.primeira_variante(valores.get(campo, ""))
            if variante:
                valores[campo] = variante
                trocado = True
                break
        if not trocado:
            # Nenhum dos termos está no glossário: o eixo repetiria outro.
            return None

    return list(
        dict.fromkeys(
            palavra for campo in eixo.campos for palavra in valores[campo].split()
        )
    )


# --- Agente -------------------------------------------------------------------


class AgenteTriador:
    """Devolve as buscas de um trecho: o trecho original e as variações.

    O trecho original vem sempre na primeira posição. Ele é o chão
    determinístico da busca — é o que sobra quando o LLM não responde — e por
    isso não passa por normalização nenhuma.
    """

    def __init__(
        self,
        cliente_llm: ClienteLLM,
        max_variacoes: int = MAX_VARIACOES,
        max_tamanho_variacao: int = MAX_TAMANHO_VARIACAO,
        *,
        glossario: Glossario | None = None,
    ):
        self.cliente_llm = cliente_llm
        self.max_variacoes = max_variacoes
        self.max_tamanho_variacao = max_tamanho_variacao
        self.glossario = glossario if glossario is not None else glossario_padrao()

    async def extrair(self, trecho: str) -> ExtracaoDoTriador:
        """As buscas do trecho e os conceitos que o LLM reconheceu nele.

        Nunca levanta. Se o LLM falhar, segue só com o trecho original e sem
        conceitos: a verificação continua, só com cobertura menor.
        """
        if not trecho or not trecho.strip():
            return ExtracaoDoTriador(buscas=[], conceitos=[])

        try:
            termos = await self.cliente_llm.gerar(
                prompt=self.montar_prompt(trecho),
                schema=TermosDeBusca,
                sistema=SISTEMA,
            )
        except ErroLLM as erro:
            logger.warning(
                "Falha ao extrair termos, seguindo só com o trecho original: %s", erro
            )
            return ExtracaoDoTriador(buscas=[trecho], conceitos=[])
        except Exception as erro:
            logger.exception("Erro inesperado no LLM ao extrair termos: %s", erro)
            return ExtracaoDoTriador(buscas=[trecho], conceitos=[])

        return ExtracaoDoTriador(
            buscas=self.montar_lista(trecho, termos),
            conceitos=conceitos_de(canonizar_termos(termos, self.glossario)),
        )

    async def extrair_buscas(self, trecho: str) -> list[str]:
        """As strings de busca do trecho, prontas para `buscar_varias`.

        Mantido para o eval do Triador, que mede só as buscas.
        """
        return (await self.extrair(trecho)).buscas

    def montar_prompt(self, trecho: str) -> str:
        """O pedido que vai ao modelo: as orientações do arquivo, mais o trecho.

        O glossário entra reduzido às duas colunas que interessam ao modelo
        (conceito e termo canônico): a coluna de variantes e o procedimento de
        manutenção são para quem edita o arquivo, e mandá-los dobraria o tamanho
        do prompt sem mudar a resposta.
        """
        return MOLDE_DO_PROMPT.format(
            orientacoes=orientacoes.ler(ARQUIVO_DE_ORIENTACOES).corpo,
            glossario=self._glossario_para_o_prompt(),
            exemplos=orientacoes.ler(ARQUIVO_DE_EXEMPLOS).corpo,
            trecho=trecho.strip(),
        )

    def montar_lista(self, trecho: str, termos: TermosDeBusca) -> list[str]:
        """Aplica glossário e eixos: daqui para baixo não há nada probabilístico."""
        canonicos = canonizar_termos(termos, self.glossario)
        buscas = [trecho]
        vistas = {trecho.strip().lower()}
        eixos_usados: list[str] = []

        for id_do_eixo, busca in montar_buscas(canonicos, self.glossario):
            if len(buscas) > self.max_variacoes:
                break
            if len(busca) > self.max_tamanho_variacao:
                logger.warning(
                    "Busca do eixo %s descartada por exceder %d caracteres",
                    id_do_eixo,
                    self.max_tamanho_variacao,
                )
                continue
            if busca in vistas:
                continue
            vistas.add(busca)
            buscas.append(busca)
            eixos_usados.append(id_do_eixo)

        if not eixos_usados:
            logger.warning(
                "Nenhum eixo aplicável: o trecho rendeu menos de dois termos "
                "(%s). Seguindo só com o trecho original.",
                ", ".join(f"{campo}={canonicos[campo]!r}" for campo in CAMPOS),
            )
        logger.info(
            "triador orientacoes_v=%s variacoes=%d eixos=%s",
            orientacoes.ler(ARQUIVO_DE_ORIENTACOES).versao,
            len(eixos_usados),
            ",".join(eixos_usados) or "-",
        )
        logger.debug(
            "triador termos=%s",
            {campo: valor for campo, valor in canonicos.items() if valor},
        )
        return buscas

    def _glossario_para_o_prompt(self) -> str:
        """As duas primeiras colunas do glossário, uma linha por conceito."""
        return "\n".join(
            f"- {conceito} → {canonico}"
            for conceito, canonico in self.glossario.conceitos.items()
        )
