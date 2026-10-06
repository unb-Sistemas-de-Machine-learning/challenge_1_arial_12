"""Cliente HTTP da OpenAlex.

Recebe strings de busca e devolve os trabalhos publicados que elas encontram,
numa lista só e sem repetição. É a única parte do backend que fala com um
serviço de terceiro, e por isso carrega sozinha o custo disso — timeout,
repetição de falha transitória e leitura defensiva de um registro incompleto.

A OpenAlex expõe uma API REST e nada além disso: aqui é `httpx` sobre HTTPS,
sem camada de protocolo no meio. Quem chama é o gateway, por chamada de função.

`buscar` faz uma requisição para uma string; `buscar_varias` orquestra o lote.
A separação existe para que a política de repetição valha por requisição, e não
por lote: uma variação que tomou 429 não deve arrastar as outras.

A leitura é defensiva por decisão: a OpenAlex agrega milhares de fontes e um
registro chega sem DOI, sem abstract ou com o título nulo. Campo ausente vira
`None`; nunca uma exceção que derrube a lista inteira.
"""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import asdict, dataclass

import httpx

from src.core.config import settings as settings_module

URL_BASE = "https://api.openalex.org/works"

# Pedir só o que é usado: a resposta completa de cinco trabalhos passa de 50 kB,
# e o que não vem não precisa ser tratado.
CAMPOS = ",".join(
    (
        "id",
        "display_name",
        "title",
        "publication_year",
        "doi",
        "is_retracted",
        "abstract_inverted_index",
        # Sinais para quem for ranquear depois. A OpenAlex já ordena por
        # relevância; devolver o número deixa o agente discordar com base.
        "relevance_score",
        "cited_by_count",
    )
)

# 200 é o teto da própria OpenAlex para `per-page`; acima disso ela dá 400.
QUANTIDADE_MAXIMA = 200
# Tetos da busca em lote. O Triador gera variações da mesma pergunta, não uma
# revisão sistemática inteira: dez strings já cobrem bem, e o total existe para
# o BERTopic e o Juiz não receberem um monte que ninguém orçou em token.
MAXIMO_DE_BUSCAS = 10
# Quantos trabalhos saem do lote, já intercalados. Cinco é o veredito: a
# OpenAlex ordena por relevância e a gente aproveita essa ordem — sem BERTopic,
# sem reclassificar.
TOP_PADRAO = 5
# Teto absoluto, para quem pedir uma amostra maior de propósito. 500 abstracts
# são ~100 mil tokens.
TOTAL_MAXIMO = 500
# Cinco requisições ao mesmo tempo. O polite pool permite dez por segundo, e
# metade disso deixa folga para o resto do sistema sem serializar a espera.
CONCORRENCIA = 5

TETO_ESPERA_SEGUNDOS = 10.0
PREFIXOS_DE_DOI = ("https://doi.org/", "http://doi.org/", "doi.org/")
PREFIXO_DE_ID = "https://openalex.org/"

# `relevancia` é o padrão da OpenAlex quando há `search`, e por isso não manda
# parâmetro nenhum. Ordenar por outra coisa faz ela devolver `relevance_score`
# nulo — o sinal só existe quando é ele que ordena.
ORDENACOES: dict[str, str | None] = {
    "relevancia": None,
    "citacoes": "cited_by_count:desc",
    "ano": "publication_year:desc",
}
SEM_TITULO = "(sem título)"

VERSAO_AGENTE = "verificador-cientifico/0.1"


class ErroOpenAlex(RuntimeError):
    """Tudo o que este módulo deixa escapar. Nunca uma exceção do `httpx`.

    Quem chama trata a busca como uma dependência que pode faltar, sem precisar
    conhecer transporte, status HTTP ou formato de resposta.
    """


class OpenAlexIndisponivel(ErroOpenAlex):
    """A OpenAlex não respondeu de forma utilizável dentro das tentativas."""


class OpenAlexRecusouABusca(ErroOpenAlex):
    """A OpenAlex respondeu `4xx`: a consulta está errada, repetir não resolve."""


class _FalhaTransitoria(Exception):
    """Interna: marca a tentativa que vale a pena repetir."""

    def __init__(self, motivo: str, *, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        super().__init__(motivo)


@dataclass(frozen=True)
class Trabalho:
    """Um trabalho publicado, no vocabulário do Verificador.

    Os nomes são os do schema `Estudo` do contrato HTTP, e não os da OpenAlex:
    o formato dela é detalhe desta ponte e não deve vazar para o resto.
    """

    # O identificador da OpenAlex ("W2110406916") é o que permite reconhecer o
    # mesmo trabalho achado por duas buscas diferentes. O DOI não serve para
    # isso: boa parte dos registros não tem.
    id: str | None
    titulo: str
    ano: int | None
    doi: str | None
    retratado: bool
    abstract: str | None
    # Pontuação da OpenAlex para esta busca. Vem `None` quando a ordenação não
    # é por relevância — ela só calcula o escore quando ele é o critério.
    relevancia: float | None
    citacoes: int | None

    def como_dicionario(self) -> dict[str, object]:
        return asdict(self)

    @property
    def chave(self) -> str:
        """Identidade para desduplicar, com queda para o que existir."""
        return self.id or self.doi or f"{self.titulo}|{self.ano}"


@dataclass(frozen=True)
class ResultadoDaBusca:
    """O que uma busca em lote devolve: o que achou e o que não deu certo.

    As falhas vêm junto, e não em log: o Juiz decide com base na literatura
    encontrada, e uma variação que não rodou encolhe a cobertura em silêncio se
    ninguém for avisado.
    """

    trabalhos: list[Trabalho]
    falhas: dict[str, str]
    # Quantos trabalhos casaram com cada busca na OpenAlex, antes do corte. É a
    # diferença entre "achei 5" e "achei 5 de 4.293" — sem isso, quem ranqueia
    # depois não sabe se está vendo a nata ou o acervo inteiro.
    total_por_busca: dict[str, int]

    def como_dicionario(self) -> dict[str, object]:
        return {
            "trabalhos": [trabalho.como_dicionario() for trabalho in self.trabalhos],
            "buscas_com_falha": self.falhas,
            "total_por_busca": self.total_por_busca,
        }


def remontar_abstract(indice: dict[str, list[int]] | None) -> str | None:
    """Desfaz o índice invertido em que a OpenAlex guarda o abstract.

    Ela não devolve o texto: devolve `{"palavra": [posições]}`. Uma palavra
    repetida aparece uma vez com várias posições, e o dicionário não tem ordem
    nenhuma — a ordem está nos números.

    Devolve `None` quando não há abstract, que é o caso de boa parte dos
    registros antigos.
    """
    if not isinstance(indice, dict) or not indice:
        return None

    posicionadas: list[tuple[int, str]] = []
    for palavra, posicoes in indice.items():
        if not isinstance(posicoes, list):
            continue
        posicionadas.extend(
            (posicao, palavra) for posicao in posicoes if isinstance(posicao, int)
        )

    if not posicionadas:
        return None

    posicionadas.sort()
    # Ordenar pela posição, e não confiar no tamanho: o índice pode ter buracos
    # quando a fonte truncou o abstract, e um `[""] * max(posicoes)` deixaria
    # lacunas no meio do texto.
    return " ".join(palavra for _, palavra in posicionadas)


def encurtar_doi(doi: str | None) -> str | None:
    """`https://doi.org/10.1/x` vira `10.1/x`.

    O schema `Estudo` da spec 010 já usa a forma curta. Converter aqui, num
    lugar só, evita as duas formas circulando pelo resto do sistema.
    """
    if not isinstance(doi, str) or not doi.strip():
        return None
    curto = doi.strip()
    for prefixo in PREFIXOS_DE_DOI:
        if curto.lower().startswith(prefixo):
            curto = curto[len(prefixo) :]
            break
    return curto or None


def encurtar_id(identificador: str | None) -> str | None:
    """`https://openalex.org/W123` vira `W123`, pelo mesmo motivo do DOI."""
    if not isinstance(identificador, str) or not identificador.strip():
        return None
    curto = identificador.strip()
    if curto.lower().startswith(PREFIXO_DE_ID):
        curto = curto[len(PREFIXO_DE_ID) :]
    return curto or None


def _ler_trabalho(registro: dict) -> Trabalho:
    titulo = registro.get("display_name") or registro.get("title")
    ano = registro.get("publication_year")
    return Trabalho(
        id=encurtar_id(registro.get("id")),
        titulo=titulo if isinstance(titulo, str) and titulo.strip() else SEM_TITULO,
        ano=ano if isinstance(ano, int) else None,
        doi=encurtar_doi(registro.get("doi")),
        # Campo ausente vale como "não retratado": a OpenAlex marca o que sabe,
        # e o silêncio dela não é acusação.
        retratado=bool(registro.get("is_retracted")),
        abstract=remontar_abstract(registro.get("abstract_inverted_index")),
        relevancia=_numero(registro.get("relevance_score")),
        citacoes=(
            registro.get("cited_by_count")
            if isinstance(registro.get("cited_by_count"), int)
            else None
        ),
    )


def _numero(valor: object) -> float | None:
    return float(valor) if isinstance(valor, (int, float)) else None


def _segundos_do_retry_after(resposta: httpx.Response) -> float | None:
    """Lê `Retry-After` só na forma de segundos.

    A forma de data HTTP também é válida no protocolo, mas depende do relógio
    do cliente estar certo; sem ela, a espera calculada vale.
    """
    bruto = resposta.headers.get("Retry-After")
    try:
        segundos = float(bruto) if bruto is not None else None
    except ValueError:
        return None
    return segundos if segundos is not None and segundos >= 0 else None


class ClienteOpenAlex:
    """Cliente HTTP da OpenAlex, com timeout e repetição de falha transitória."""

    def __init__(
        self,
        *,
        mailto: str,
        api_key: str | None = None,
        quantidade_padrao: int = 10,
        timeout_segundos: float = 10.0,
        max_tentativas: int = 3,
        espera_base_segundos: float = 0.5,
        cliente_http: httpx.AsyncClient | None = None,
        dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if not mailto or not mailto.strip():
            # Sem e-mail, a OpenAlex joga o tráfego no pool comum e pode
            # bloquear sem avisar ninguém. Falhar aqui é mais barato do que
            # descobrir isso no meio de uma verificação.
            raise ValueError(
                "OPENALEX_MAILTO é obrigatório: o polite pool da OpenAlex exige "
                "um e-mail de contato"
            )

        self.mailto = mailto.strip()
        self.quantidade_padrao = limitar_quantidade(quantidade_padrao)
        self.timeout_segundos = timeout_segundos
        self.max_tentativas = max(1, max_tentativas)
        self.espera_base_segundos = espera_base_segundos

        self._dormir = dormir
        self._proprio = cliente_http is None
        self._http = cliente_http or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_segundos)
        )
        self._cabecalhos = {"User-Agent": f"{VERSAO_AGENTE} (mailto:{self.mailto})"}
        if api_key and api_key.strip():
            # No cabeçalho, e nunca na query: chave em URL vaza para log de
            # proxy, histórico e mensagem de erro. A OpenAlex aceita as duas
            # formas, então a escolha é nossa.
            self._cabecalhos["Authorization"] = f"Bearer {api_key.strip()}"
        self.tem_api_key = "Authorization" in self._cabecalhos

    @classmethod
    def a_partir_das_configuracoes(cls) -> "ClienteOpenAlex":
        # Pelo módulo, e não pela função importada: é como o resto do projeto
        # faz, e é o que permite trocar a configuração em teste.
        settings = settings_module.get_settings()
        chave = settings.openalex_api_key
        return cls(
            mailto=settings.openalex_mailto or "",
            api_key=chave.get_secret_value() if chave else None,
            quantidade_padrao=settings.openalex_resultados_por_busca,
            timeout_segundos=settings.openalex_timeout_segundos,
            max_tentativas=settings.openalex_max_tentativas,
        )

    async def buscar(
        self,
        busca: str,
        *,
        quantidade: int | None = None,
        ordenar_por: str = "relevancia",
    ) -> list[Trabalho]:
        """Devolve os trabalhos que a OpenAlex associa à string de busca.

        São os **mais relevantes**, e não os primeiros de uma lista arbitrária:
        a OpenAlex ordena por `relevance_score` quando há busca textual.

        Levanta `ValueError` se a busca é vazia — é defeito de quem chama, e não
        motivo para gastar uma requisição.
        """
        trabalhos, _total = await self._buscar_uma(busca, quantidade, ordenar_por)
        return trabalhos

    async def _buscar_uma(
        self, busca: str, quantidade: int | None, ordenar_por: str
    ) -> tuple[list[Trabalho], int]:
        """Uma requisição: devolve os trabalhos e quantos casaram ao todo."""
        termo = busca.strip() if isinstance(busca, str) else ""
        if not termo:
            raise ValueError("a string de busca não pode ser vazia")
        if ordenar_por not in ORDENACOES:
            raise ValueError(
                f"ordenar_por deve ser um de {sorted(ORDENACOES)}; veio {ordenar_por!r}"
            )

        quantos = limitar_quantidade(
            self.quantidade_padrao if quantidade is None else quantidade
        )
        parametros: dict[str, object] = {
            "filter": f"title_and_abstract.search:{termo}",
            "per-page": quantos,
            "select": CAMPOS,
            # O mailto vai na query **e** no User-Agent: a OpenAlex documenta as
            # duas formas e usa a que encontrar primeiro.
            "mailto": self.mailto,
        }
        if ORDENACOES[ordenar_por]:
            parametros["sort"] = ORDENACOES[ordenar_por]

        registros, total = await self._obter(parametros)
        return [_ler_trabalho(registro) for registro in registros], total

    async def buscar_varias(
        self,
        buscas: Sequence[str],
        *,
        quantidade: int | None = None,
        limite: int | None = None,
        ordenar_por: str = "relevancia",
    ) -> ResultadoDaBusca:
        """Roda várias strings de busca e junta os trabalhos numa lista só.

        É o formato que o Triador produz: variações da mesma pergunta, feitas
        para ampliar a cobertura. `quantidade` vale **por busca**; `limite`
        corta a lista final. O mesmo trabalho achado por duas variações aparece
        uma vez só.

        Só levanta `OpenAlexIndisponivel` se **nenhuma** busca funcionar. Uma
        variação que falhou entra em `falhas`, para que quem decide saiba que a
        cobertura ficou menor do que foi pedido.
        """
        pedidas = normalizar_buscas(buscas)
        if not pedidas:
            raise ValueError("é preciso pelo menos uma string de busca não vazia")

        limitador = asyncio.Semaphore(CONCORRENCIA)

        async def uma(termo: str) -> tuple[list[Trabalho], int] | ErroOpenAlex:
            async with limitador:
                try:
                    return await self._buscar_uma(termo, quantidade, ordenar_por)
                except ErroOpenAlex as erro:
                    return erro

        respostas = await asyncio.gather(*(uma(termo) for termo in pedidas))

        falhas: dict[str, str] = {}
        totais: dict[str, int] = {}
        listas: list[list[Trabalho]] = []
        for termo, resposta in zip(pedidas, respostas, strict=True):
            if isinstance(resposta, ErroOpenAlex):
                falhas[termo] = str(resposta)
                continue
            encontrados, total = resposta
            totais[termo] = total
            listas.append(encontrados)

        quantos = max(
            1, min(limite if limite is not None else TOP_PADRAO, TOTAL_MAXIMO)
        )
        trabalhos = intercalar(listas, quantos)

        if len(falhas) == len(pedidas):
            raise OpenAlexIndisponivel(
                f"nenhuma das {len(pedidas)} buscas funcionou: "
                f"{next(iter(falhas.values()))}"
            )

        return ResultadoDaBusca(
            trabalhos=trabalhos, falhas=falhas, total_por_busca=totais
        )

    async def fechar(self) -> None:
        """Fecha o cliente HTTP, se este objeto foi quem o criou."""
        if self._proprio:
            await self._http.aclose()

    async def __aenter__(self) -> "ClienteOpenAlex":
        return self

    async def __aexit__(self, *_excecao: object) -> None:
        await self.fechar()

    async def _obter(self, parametros: dict[str, object]) -> tuple[list[dict], int]:
        ultima: _FalhaTransitoria | None = None
        for tentativa in range(1, self.max_tentativas + 1):
            try:
                return await self._uma_tentativa(parametros)
            except _FalhaTransitoria as falha:
                ultima = falha
                if tentativa == self.max_tentativas:
                    break
                await self._dormir(self._espera(tentativa, falha.retry_after))

        raise OpenAlexIndisponivel(
            f"OpenAlex indisponível após {self.max_tentativas} tentativa(s): {ultima}"
        ) from ultima

    async def _uma_tentativa(
        self, parametros: dict[str, object]
    ) -> tuple[list[dict], int]:
        try:
            resposta = await self._http.get(
                URL_BASE,
                params=parametros,
                headers=self._cabecalhos,
                # Explícito na chamada, e não só no cliente: um `AsyncClient`
                # injetado de fora pode ter sido criado sem timeout nenhum.
                timeout=self.timeout_segundos,
            )
        except httpx.TimeoutException as erro:
            raise _FalhaTransitoria(f"tempo de resposta esgotado ({erro})") from erro
        except httpx.TransportError as erro:
            raise _FalhaTransitoria(f"falha de conexão ({erro})") from erro

        if resposta.status_code == httpx.codes.TOO_MANY_REQUESTS:
            raise _FalhaTransitoria(
                "limite de tráfego atingido (429)",
                retry_after=_segundos_do_retry_after(resposta),
            )
        if resposta.status_code >= 500:
            raise _FalhaTransitoria(self._motivo_do_5xx(resposta))
        if resposta.status_code >= 400:
            # Consulta malformada, parâmetro inválido: repetir devolve o mesmo
            # erro e só gasta tempo de quem está esperando o veredicto.
            raise OpenAlexRecusouABusca(
                f"a OpenAlex recusou a busca com {resposta.status_code}"
            )

        try:
            corpo = resposta.json()
        except ValueError as erro:
            raise _FalhaTransitoria("corpo da resposta não é JSON") from erro

        resultados = corpo.get("results") if isinstance(corpo, dict) else None
        if not isinstance(resultados, list):
            # Página de erro de proxy, resposta truncada: o status disse 200 mas
            # não veio o que o contrato promete.
            raise _FalhaTransitoria("resposta sem a lista 'results'")

        meta = corpo.get("meta") if isinstance(corpo.get("meta"), dict) else {}
        total = meta.get("count")
        return (
            [registro for registro in resultados if isinstance(registro, dict)],
            total if isinstance(total, int) else len(resultados),
        )

    def _motivo_do_5xx(self, resposta: httpx.Response) -> str:
        """Distingue "fora do ar" de "cortou o tráfego não identificado".

        Sob carga, a OpenAlex responde 503 a quem não manda API key — e chama
        isso de busca anônima mesmo com o `mailto` preenchido. Sem esta
        distinção, o log diria só "503" e a equipe procuraria defeito no lugar
        errado por um bom tempo.
        """
        if resposta.status_code == 503 and not self.tem_api_key:
            try:
                erro = resposta.json().get("error", "")
            except ValueError:
                erro = ""
            if "unavailable" in str(erro).lower():
                return (
                    "503: a OpenAlex pausou a busca não identificada por carga. "
                    "Configure OPENALEX_API_KEY (a chave é gratuita)"
                )
        return f"resposta {resposta.status_code} da OpenAlex"

    def _espera(self, tentativa: int, retry_after: float | None) -> float:
        if retry_after is not None:
            # Respeitado, mas com teto: um Retry-After de dez minutos seguraria
            # a requisição HTTP do usuário presa atrás dele.
            return min(retry_after, TETO_ESPERA_SEGUNDOS)
        return self.espera_base_segundos * (2 ** (tentativa - 1))


def intercalar(
    listas: list[list[Trabalho]],
    quantos: int,
    chave: Callable[[Trabalho], str] = lambda trabalho: trabalho.chave,
) -> list[Trabalho]:
    """Junta os resultados pegando o 1º de cada busca, depois o 2º, e assim vai.

    Por posição, e **não** por `relevancia`: o escore da OpenAlex mede o quanto
    o trabalho casa com *aquela* string, e a escala muda com a string. Medido na
    prática, para o mesmo assunto: a formulação curta pontua 870 no primeiro
    colocado e a longa pontua 227. Ordenar a lista juntada por esse número faria
    a busca mais curta vencer sempre, o que não diz nada sobre o artigo.

    A posição, essa sim, é comparável: "primeiro colocado" quer dizer a mesma
    coisa em qualquer busca.

    `chave` decide o que conta como repetido. O padrão é o id da OpenAlex; o
    Pesquisador passa o DOI, porque preprint e versão publicada têm ids
    diferentes e o mesmo DOI.
    """
    juntos: list[Trabalho] = []
    vistos: set[str] = set()
    for posicao in range(max((len(lista) for lista in listas), default=0)):
        for lista in listas:
            if posicao >= len(lista) or len(juntos) >= quantos:
                continue
            trabalho = lista[posicao]
            identidade = chave(trabalho)
            if identidade in vistos:
                continue
            vistos.add(identidade)
            juntos.append(trabalho)
        if len(juntos) >= quantos:
            break
    return juntos


def normalizar_buscas(buscas: Sequence[str]) -> list[str]:
    """Limpa a lista antes de gastar requisição: apara, descarta vazia e repetida.

    Repetida acontece de verdade: o Triador pode gerar duas variações que, depois
    de aparadas, são a mesma string — e seria uma ida à OpenAlex para nada.
    """
    if isinstance(buscas, str):
        # Engano fácil de cometer e caro de descobrir: iterar uma string daria
        # uma busca por caractere.
        raise ValueError("passe uma lista de strings, não uma string")

    limpas: list[str] = []
    for busca in buscas:
        termo = busca.strip() if isinstance(busca, str) else ""
        if termo and termo not in limpas:
            limpas.append(termo)
    return limpas[:MAXIMO_DE_BUSCAS]


def limitar_quantidade(quantidade: int) -> int:
    """Encaixa o pedido em `[1, QUANTIDADE_MAXIMA]`.

    Quem chama é um agente: se o modelo pedir 500 trabalhos, devolver 50 é
    melhor do que derrubar a verificação inteira por causa do pedido.
    """
    try:
        pedido = int(quantidade)
    except (TypeError, ValueError):
        return 1
    return max(1, min(pedido, QUANTIDADE_MAXIMA))


# --- Cliente compartilhado ----------------------------------------------------

_compartilhado: ClienteOpenAlex | None = None


def cliente_compartilhado() -> ClienteOpenAlex:
    """Um cliente por processo: cada instância abre um pool de conexões novo.

    É também a costura de teste: trocar `_compartilhado` por um cliente com
    transporte dublê evita que qualquer teste toque a rede.
    """
    global _compartilhado
    if _compartilhado is None:
        _compartilhado = ClienteOpenAlex.a_partir_das_configuracoes()
    return _compartilhado


async def encerrar_cliente_compartilhado() -> None:
    """Fecha o pool no encerramento da aplicação."""
    global _compartilhado
    if _compartilhado is not None:
        await _compartilhado.fechar()
        _compartilhado = None
