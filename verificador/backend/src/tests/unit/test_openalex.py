"""O cliente da OpenAlex, sem tocar na rede.

Todas as respostas vêm de `src/tests/fixtures/openalex/`, gravadas de chamadas
reais. O transporte é um `httpx.MockTransport`: a pilha do `httpx` roda de
verdade — montagem da query, cabeçalhos, timeout — e só o soquete é dublê.
"""

import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from src.services import openalex as openalex_tool
from src.services.openalex import (
    MAXIMO_DE_BUSCAS,
    TOP_PADRAO,
    QUANTIDADE_MAXIMA,
    TOTAL_MAXIMO,
    ClienteOpenAlex,
    OpenAlexIndisponivel,
    OpenAlexRecusouABusca,
    Trabalho,
    encurtar_doi,
    encurtar_id,
    intercalar,
    normalizar_buscas,
    remontar_abstract,
    sanitizar_busca,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "openalex"
CONTATO = "contato@example.com"

Acao = Callable[[httpx.Request], httpx.Response]


def carregar(nome: str) -> dict:
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


def devolver(corpo: dict, status: int = 200, **cabecalhos: str) -> Acao:
    return lambda _requisicao: httpx.Response(status, json=corpo, headers=cabecalhos)


def devolver_texto(texto: str, status: int = 200) -> Acao:
    return lambda _requisicao: httpx.Response(status, text=texto)


def levantar(classe: type[httpx.HTTPError]) -> Acao:
    def acao(requisicao: httpx.Request) -> httpx.Response:
        raise classe("dublê de falha de rede", request=requisicao)

    return acao


class Bancada:
    """Cliente pronto para teste, com o que aconteceu registrado ao lado.

    `acoes` é consumida uma por requisição; a última se repete, para que um
    teste de "falha sempre" não precise listar a mesma resposta três vezes.
    """

    def __init__(self, *acoes: Acao, **opcoes: object) -> None:
        self.requisicoes: list[httpx.Request] = []
        self.esperas: list[float] = []
        self._acoes = list(acoes)

        async def dormir(segundos: float) -> None:
            self.esperas.append(segundos)

        self.cliente = ClienteOpenAlex(
            mailto=CONTATO,
            cliente_http=httpx.AsyncClient(
                transport=httpx.MockTransport(self._atender)
            ),
            dormir=dormir,
            **opcoes,
        )

    def _atender(self, requisicao: httpx.Request) -> httpx.Response:
        self.requisicoes.append(requisicao)
        acao = self._acoes.pop(0) if len(self._acoes) > 1 else self._acoes[0]
        return acao(requisicao)

    @property
    def ultima(self) -> httpx.Request:
        return self.requisicoes[-1]


def bancada_comum(**opcoes: object) -> Bancada:
    return Bancada(devolver(carregar("busca_polilaminina.json")), **opcoes)


# --- Critério 1: a lista de trabalhos ----------------------------------------


@pytest.mark.asyncio
async def test_a_busca_devolve_trabalhos_com_os_cinco_campos() -> None:
    bancada = bancada_comum()

    trabalhos = await bancada.cliente.buscar("polylaminin spinal cord injury")

    assert len(trabalhos) == 5
    assert all(isinstance(trabalho, Trabalho) for trabalho in trabalhos)
    primeiro = trabalhos[0]
    assert primeiro.titulo.startswith("Polylaminin, a polymeric form of laminin")
    assert primeiro.ano == 2010
    assert primeiro.doi == "10.1096/fj.10-157628"
    assert primeiro.retratado is False
    assert primeiro.abstract is not None and "laminin" in primeiro.abstract.lower()


@pytest.mark.asyncio
async def test_busca_sem_resultados_devolve_lista_vazia_e_nao_e_erro() -> None:
    bancada = Bancada(devolver(carregar("busca_sem_resultados.json")))

    assert await bancada.cliente.buscar("termo inexistente") == []


# --- Critério 2: polite pool -------------------------------------------------


@pytest.mark.asyncio
async def test_toda_requisicao_leva_o_email_de_contato() -> None:
    bancada = bancada_comum()

    await bancada.cliente.buscar("polylaminin")

    assert bancada.ultima.url.params["mailto"] == CONTATO
    assert f"mailto:{CONTATO}" in bancada.ultima.headers["User-Agent"]


@pytest.mark.parametrize("mailto", ["", "   ", None])
def test_cliente_sem_email_falha_na_criacao(mailto: str | None) -> None:
    """Falha ao criar, e não no meio de uma verificação."""
    with pytest.raises(ValueError, match="OPENALEX_MAILTO"):
        ClienteOpenAlex(mailto=mailto)


# --- API key: o mailto sozinho não basta mais ---------------------------------

CHAVE = "chave-de-teste-nao-usar"


@pytest.mark.asyncio
async def test_api_key_vai_no_cabecalho_e_nunca_na_url() -> None:
    """Chave em query string vaza para log de proxy, histórico e erro."""
    bancada = bancada_comum(api_key=CHAVE)

    await bancada.cliente.buscar("polylaminin")

    assert bancada.ultima.headers["Authorization"] == f"Bearer {CHAVE}"
    assert CHAVE not in str(bancada.ultima.url)
    assert "api_key" not in bancada.ultima.url.params


@pytest.mark.parametrize("chave", [None, "", "   "])
@pytest.mark.asyncio
async def test_sem_chave_nao_manda_authorization(chave: str | None) -> None:
    bancada = bancada_comum(api_key=chave)

    await bancada.cliente.buscar("polylaminin")

    assert "Authorization" not in bancada.ultima.headers
    assert bancada.cliente.tem_api_key is False


@pytest.mark.asyncio
async def test_503_de_busca_anonima_explica_a_causa_real() -> None:
    """Sem esta mensagem o log diria só "503" e ninguém acharia a causa."""
    corte = {
        "error": "Search temporarily unavailable",
        "message": "Anonymous search is paused while the search cluster recovers",
    }
    bancada = Bancada(devolver(corte, status=503), max_tentativas=1)

    with pytest.raises(OpenAlexIndisponivel, match="OPENALEX_API_KEY"):
        await bancada.cliente.buscar("polylaminin")


@pytest.mark.asyncio
async def test_com_chave_o_503_nao_culpa_a_falta_de_chave() -> None:
    corte = {"error": "Search temporarily unavailable", "message": "…"}
    bancada = Bancada(devolver(corte, status=503), api_key=CHAVE, max_tentativas=1)

    with pytest.raises(OpenAlexIndisponivel) as erro:
        await bancada.cliente.buscar("polylaminin")

    assert "OPENALEX_API_KEY" not in str(erro.value)
    assert "503" in str(erro.value)


# --- Critérios 3 a 6: leitura defensiva do registro --------------------------


@pytest.mark.asyncio
async def test_trabalho_sem_doi_e_sem_abstract_continua_na_lista() -> None:
    bancada = Bancada(devolver(carregar("busca_sem_doi.json")))

    trabalhos = await bancada.cliente.buscar("spinal cord injury")

    assert len(trabalhos) == 3
    assert [trabalho.doi for trabalho in trabalhos] == [None, None, None]
    sem_abstract = trabalhos[2]
    assert sem_abstract.abstract is None
    assert sem_abstract.titulo.startswith("Spinal Cord Injury")
    assert sem_abstract.ano == 1995


@pytest.mark.asyncio
async def test_registro_sem_titulo_e_sem_ano_nao_derruba_a_busca() -> None:
    """Corpo montado à mão: a OpenAlex não produz esse registro hoje.

    O contrato dela permite, e um campo nulo vindo de uma fonte agregada não
    pode custar a lista inteira — é o único caso da suíte que não é gravado.
    """
    degenerado = {
        "results": [
            {"id": "https://openalex.org/W1", "display_name": None, "title": None},
            {"id": "https://openalex.org/W2", "publication_year": "mil novecentos"},
        ]
    }
    bancada = Bancada(devolver(degenerado))

    trabalhos = await bancada.cliente.buscar("qualquer coisa")

    assert [trabalho.titulo for trabalho in trabalhos] == ["(sem título)"] * 2
    assert [trabalho.ano for trabalho in trabalhos] == [None, None]
    assert [trabalho.retratado for trabalho in trabalhos] == [False, False]


@pytest.mark.asyncio
async def test_trabalho_retratado_vem_marcado() -> None:
    bancada = Bancada(devolver(carregar("busca_retratado.json")))

    trabalhos = await bancada.cliente.buscar("spinal cord injury")

    assert [trabalho.retratado for trabalho in trabalhos] == [True, True]


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        ("https://doi.org/10.1096/fj.10-157628", "10.1096/fj.10-157628"),
        ("http://doi.org/10.1/x", "10.1/x"),
        ("doi.org/10.1/x", "10.1/x"),
        ("10.1/x", "10.1/x"),
        (None, None),
        ("", None),
        ("   ", None),
    ],
)
def test_doi_vem_na_forma_curta(bruto: str | None, esperado: str | None) -> None:
    assert encurtar_doi(bruto) == esperado


def test_abstract_e_remontado_na_ordem_das_posicoes() -> None:
    """A palavra repetida aparece uma vez no índice, com as duas posições."""
    indice = {"medula": [1, 4], "A": [0], "regenera": [2], "a": [3], "espinhal": [5]}
    assert remontar_abstract(indice) == "A medula regenera a medula espinhal"


@pytest.mark.parametrize("indice", [None, {}, {"palavra": "posição errada"}])
def test_abstract_ausente_ou_ilegivel_vira_none(indice: object) -> None:
    assert remontar_abstract(indice) is None


def test_abstract_com_buraco_no_meio_nao_inventa_palavra() -> None:
    """Fonte truncada deixa posições faltando; o texto sai sem lacuna falsa."""
    assert remontar_abstract({"inicio": [0], "fim": [40]}) == "inicio fim"


# --- Critério 7: timeout e repetição -----------------------------------------


@pytest.mark.asyncio
async def test_a_requisicao_carrega_timeout_explicito() -> None:
    bancada = bancada_comum(timeout_segundos=2.5)

    await bancada.cliente.buscar("polylaminin")

    assert bancada.ultima.extensions["timeout"] == {
        "connect": 2.5,
        "read": 2.5,
        "write": 2.5,
        "pool": 2.5,
    }


@pytest.mark.asyncio
async def test_429_seguido_de_sucesso_e_repetido() -> None:
    bancada = Bancada(
        devolver({}, status=429),
        devolver(carregar("busca_polilaminina.json")),
    )

    trabalhos = await bancada.cliente.buscar("polylaminin")

    assert len(trabalhos) == 5
    assert len(bancada.requisicoes) == 2
    assert bancada.esperas == [0.5]


@pytest.mark.asyncio
async def test_a_espera_entre_tentativas_cresce() -> None:
    bancada = Bancada(devolver({}, status=503))

    with pytest.raises(OpenAlexIndisponivel):
        await bancada.cliente.buscar("polylaminin")

    assert len(bancada.requisicoes) == 3
    assert bancada.esperas == [0.5, 1.0]


@pytest.mark.asyncio
async def test_retry_after_substitui_a_espera_calculada() -> None:
    bancada = Bancada(
        devolver({}, 429, **{"Retry-After": "3"}),
        devolver(carregar("busca_polilaminina.json")),
    )

    await bancada.cliente.buscar("polylaminin")

    assert bancada.esperas == [3.0]


@pytest.mark.asyncio
async def test_retry_after_absurdo_respeita_o_teto() -> None:
    """Dez minutos de espera segurariam a requisição do usuário presa atrás."""
    bancada = Bancada(
        devolver({}, 429, **{"Retry-After": "600"}),
        devolver(carregar("busca_polilaminina.json")),
    )

    await bancada.cliente.buscar("polylaminin")

    assert bancada.esperas == [openalex_tool.TETO_ESPERA_SEGUNDOS]


@pytest.mark.asyncio
async def test_retry_after_em_formato_de_data_e_ignorado() -> None:
    bancada = Bancada(
        devolver({}, 429, **{"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}),
        devolver(carregar("busca_polilaminina.json")),
    )

    await bancada.cliente.buscar("polylaminin")

    assert bancada.esperas == [0.5]


@pytest.mark.asyncio
async def test_numero_de_tentativas_e_configuravel() -> None:
    bancada = Bancada(devolver({}, status=502), max_tentativas=1)

    with pytest.raises(OpenAlexIndisponivel):
        await bancada.cliente.buscar("polylaminin")

    assert len(bancada.requisicoes) == 1
    assert bancada.esperas == []


# --- Critérios 8 e 9: fronteira de erro --------------------------------------


@pytest.mark.asyncio
async def test_erro_de_cliente_nao_e_repetido() -> None:
    bancada = Bancada(devolver({}, status=400))

    with pytest.raises(OpenAlexRecusouABusca):
        await bancada.cliente.buscar("polylaminin")

    assert len(bancada.requisicoes) == 1
    assert bancada.esperas == []


@pytest.mark.parametrize(
    "classe",
    [httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError, httpx.ReadError],
)
@pytest.mark.asyncio
async def test_falha_de_transporte_vira_erro_de_dominio(
    classe: type[httpx.HTTPError],
) -> None:
    """Nenhuma exceção do `httpx` atravessa a fronteira do módulo."""
    bancada = Bancada(levantar(classe))

    with pytest.raises(OpenAlexIndisponivel):
        await bancada.cliente.buscar("polylaminin")

    assert len(bancada.requisicoes) == 3


@pytest.mark.asyncio
async def test_corpo_que_nao_e_json_vira_erro_de_dominio() -> None:
    bancada = Bancada(devolver_texto("<html>gateway error</html>"))

    with pytest.raises(OpenAlexIndisponivel):
        await bancada.cliente.buscar("polylaminin")


@pytest.mark.asyncio
async def test_json_sem_a_lista_results_vira_erro_de_dominio() -> None:
    bancada = Bancada(devolver({"meta": {"count": 0}}))

    with pytest.raises(OpenAlexIndisponivel):
        await bancada.cliente.buscar("polylaminin")


# --- Critério 10: quantidade -------------------------------------------------


@pytest.mark.asyncio
async def test_quantidade_padrao_vai_na_consulta() -> None:
    bancada = bancada_comum(quantidade_padrao=7)

    await bancada.cliente.buscar("polylaminin")

    assert bancada.ultima.url.params["per-page"] == "7"


@pytest.mark.parametrize(
    ("pedido", "esperado"),
    [
        (3, "3"),
        (QUANTIDADE_MAXIMA, str(QUANTIDADE_MAXIMA)),
        (500, str(QUANTIDADE_MAXIMA)),
        (0, "1"),
    ],
)
@pytest.mark.asyncio
async def test_pedido_fora_da_faixa_e_reduzido_ao_limite(
    pedido: int, esperado: str
) -> None:
    bancada = bancada_comum()

    await bancada.cliente.buscar("polylaminin", quantidade=pedido)

    assert bancada.ultima.url.params["per-page"] == esperado


@pytest.mark.asyncio
async def test_configuracao_acima_do_teto_tambem_e_reduzida() -> None:
    bancada = bancada_comum(quantidade_padrao=999)

    await bancada.cliente.buscar("polylaminin")

    assert bancada.ultima.url.params["per-page"] == str(QUANTIDADE_MAXIMA)


@pytest.mark.asyncio
async def test_a_consulta_pede_so_os_campos_usados() -> None:
    bancada = bancada_comum()

    await bancada.cliente.buscar("  polylaminin  ")

    assert (
        bancada.ultima.url.params["filter"] == "title_and_abstract.search:polylaminin"
    )
    assert bancada.ultima.url.params["select"] == openalex_tool.CAMPOS


# --- Saneamento: o que a OpenAlex leria como sintaxe de filtro ----------------


@pytest.mark.parametrize(
    ("bruta", "esperada"),
    [
        # O caso real: a busca nº 1 do Triador é o trecho original, e prosa em
        # português tem vírgula. Sem o saneamento, a API devolve 400.
        (
            "A medula espinhal e a parte do sistema nervoso central que, junto "
            "com o encefalo, forma o eixo neural.",
            "A medula espinhal e a parte do sistema nervoso central que junto "
            "com o encefalo forma o eixo neural.",
        ),
        # `|` é o OU da OpenAlex: passaria calado, alargando a busca.
        ("medula | espinhal", "medula espinhal"),
        ("vitamina C, zinco e selenio", "vitamina C zinco e selenio"),
        # Separador colado na palavra não gruda as duas vizinhas.
        ("cafe,diabetes", "cafe diabetes"),
        # O que não é sintaxe de filtro fica: já conferido contra a API real,
        # que responde 200 para todos.
        ("efeito (observado): 48% — a/b", "efeito (observado): 48% — a/b"),
        ("  polylaminin  ", "polylaminin"),
        ("", ""),
        (",", ""),
    ],
)
def test_saneamento_tira_so_a_sintaxe_de_filtro(bruta: str, esperada: str) -> None:
    assert sanitizar_busca(bruta) == esperada


@pytest.mark.asyncio
async def test_virgula_do_trecho_nao_chega_ao_filtro() -> None:
    """Uma vírgula no filtro é 400 na borda da OpenAlex, antes de qualquer busca."""
    bancada = bancada_comum()

    await bancada.cliente.buscar("polylaminin, spinal cord")

    assert (
        bancada.ultima.url.params["filter"]
        == "title_and_abstract.search:polylaminin spinal cord"
    )


@pytest.mark.asyncio
async def test_busca_so_de_separadores_e_recusada_sem_rede() -> None:
    bancada = bancada_comum()

    with pytest.raises(ValueError, match="não pode ser vazia"):
        await bancada.cliente.buscar(" , | ")

    assert bancada.requisicoes == []


def test_duas_variacoes_que_so_diferem_na_pontuacao_valem_uma() -> None:
    """Desduplicar antes do saneamento gastaria duas requisições iguais."""
    assert normalizar_buscas(["cafe, diabetes", "cafe diabetes"]) == ["cafe diabetes"]


# --- Busca em lote: a lista de strings do Triador -----------------------------


def responder_por_busca(mapa: dict[str, dict | Exception]) -> Acao:
    """Responde conforme a string que chegou, para separar uma busca da outra."""

    def acao(requisicao: httpx.Request) -> httpx.Response:
        termo = requisicao.url.params["filter"].replace(
            "title_and_abstract.search:", ""
        )
        item = mapa[termo]
        if isinstance(item, Exception):
            raise item
        return httpx.Response(200, json=item)

    return acao


def corpo_com(*trabalhos: tuple[str, str]) -> dict:
    """Corpo mínimo da OpenAlex com os identificadores e títulos informados."""
    return {
        "results": [
            {
                "id": f"https://openalex.org/{identificador}",
                "display_name": titulo,
                "publication_year": 2020,
                "doi": None,
                "is_retracted": False,
                "abstract_inverted_index": None,
            }
            for identificador, titulo in trabalhos
        ]
    }


@pytest.mark.asyncio
async def test_varias_buscas_viram_uma_lista_so() -> None:
    bancada = Bancada(
        responder_por_busca(
            {
                "service design": corpo_com(("W1", "um"), ("W2", "dois")),
                "user experience": corpo_com(("W3", "três")),
            }
        )
    )

    resultado = await bancada.cliente.buscar_varias(
        ["service design", "user experience"]
    )

    # Intercalado por posição: 1º da primeira, 1º da segunda, 2º da primeira.
    assert [t.id for t in resultado.trabalhos] == ["W1", "W3", "W2"]
    assert resultado.falhas == {}
    assert len(bancada.requisicoes) == 2


@pytest.mark.asyncio
async def test_trabalho_achado_por_duas_buscas_aparece_uma_vez() -> None:
    """Duplicata inflaria o peso do trabalho na clusterização do BERTopic."""
    bancada = Bancada(
        responder_por_busca(
            {
                "ux": corpo_com(("W1", "um"), ("W2", "dois")),
                "itsm": corpo_com(("W2", "dois"), ("W3", "três")),
            }
        )
    )

    resultado = await bancada.cliente.buscar_varias(["ux", "itsm"])

    assert [t.id for t in resultado.trabalhos] == ["W1", "W2", "W3"]


@pytest.mark.asyncio
async def test_sem_id_a_desduplicacao_cai_para_doi_e_depois_titulo() -> None:
    registro = {"display_name": "mesmo estudo", "publication_year": 1999}
    bancada = Bancada(devolver({"results": [registro, dict(registro)]}))

    resultado = await bancada.cliente.buscar_varias(["qualquer"])

    assert len(resultado.trabalhos) == 1


@pytest.mark.asyncio
async def test_a_quantidade_vale_por_busca() -> None:
    bancada = Bancada(
        responder_por_busca({"a": corpo_com(("W1", "um")), "b": corpo_com(("W2", "d"))})
    )

    await bancada.cliente.buscar_varias(["a", "b"], quantidade=4)

    assert [r.url.params["per-page"] for r in bancada.requisicoes] == ["4", "4"]


@pytest.mark.asyncio
async def test_busca_repetida_na_lista_nao_gasta_requisicao() -> None:
    bancada = Bancada(devolver(corpo_com(("W1", "um"))))

    await bancada.cliente.buscar_varias(["ux", "  ux  ", "", "ux"])

    assert len(bancada.requisicoes) == 1


@pytest.mark.asyncio
async def test_lista_longa_demais_e_cortada_no_teto() -> None:
    bancada = Bancada(devolver(corpo_com(("W1", "um"))))

    await bancada.cliente.buscar_varias([f"busca {n}" for n in range(30)])

    assert len(bancada.requisicoes) == MAXIMO_DE_BUSCAS


@pytest.mark.asyncio
async def test_o_total_de_trabalhos_tem_teto() -> None:
    """Cada busca traz trabalhos distintos: sem teto, seriam 10 x 50 = 500."""
    buscas = [f"busca {n}" for n in range(MAXIMO_DE_BUSCAS)]
    mapa = {
        busca: corpo_com(
            *(
                (f"W{indice * QUANTIDADE_MAXIMA + n}", f"t{n}")
                for n in range(QUANTIDADE_MAXIMA)
            )
        )
        for indice, busca in enumerate(buscas)
    }
    bancada = Bancada(responder_por_busca(mapa))

    resultado = await bancada.cliente.buscar_varias(buscas, limite=TOTAL_MAXIMO)

    assert len(resultado.trabalhos) == TOTAL_MAXIMO


@pytest.mark.asyncio
async def test_uma_busca_que_falha_nao_derruba_as_outras() -> None:
    """A cobertura encolhe, mas a falha vem escrita — nunca em silêncio."""
    bancada = Bancada(
        responder_por_busca(
            {
                "boa": corpo_com(("W1", "um")),
                "ruim": httpx.ConnectError("sem rota"),
            }
        ),
        max_tentativas=1,
    )

    resultado = await bancada.cliente.buscar_varias(["boa", "ruim"])

    assert [t.id for t in resultado.trabalhos] == ["W1"]
    assert list(resultado.falhas) == ["ruim"]
    assert "conexão" in resultado.falhas["ruim"]


@pytest.mark.asyncio
async def test_se_todas_as_buscas_falham_o_erro_sobe() -> None:
    bancada = Bancada(devolver({}, status=503), max_tentativas=1)

    with pytest.raises(OpenAlexIndisponivel, match="nenhuma das 2 buscas"):
        await bancada.cliente.buscar_varias(["a", "b"])


@pytest.mark.asyncio
async def test_string_no_lugar_da_lista_e_recusada() -> None:
    """Iterar uma string daria uma busca por caractere — erro caro de achar."""
    bancada = bancada_comum()

    with pytest.raises(ValueError, match="lista de strings"):
        await bancada.cliente.buscar_varias("polylaminin")

    assert bancada.requisicoes == []


@pytest.mark.parametrize("buscas", [[], ["", "   "], ["\n"]])
@pytest.mark.asyncio
async def test_lista_sem_busca_util_e_recusada_sem_rede(buscas: list[str]) -> None:
    bancada = bancada_comum()

    with pytest.raises(ValueError, match="pelo menos uma"):
        await bancada.cliente.buscar_varias(buscas)

    assert bancada.requisicoes == []


@pytest.mark.asyncio
async def test_a_sintaxe_booleana_chega_intacta_na_openalex() -> None:
    """Parênteses agrupam de verdade na OpenAlex; escapar ou limpar quebraria."""
    consulta = '("Service Design" OR "UX") AND ("ITSM" OR "ITIL")'
    bancada = bancada_comum()

    await bancada.cliente.buscar_varias([consulta])

    assert (
        bancada.ultima.url.params["filter"] == f"title_and_abstract.search:{consulta}"
    )


def test_id_da_openalex_vem_na_forma_curta() -> None:
    assert encurtar_id("https://openalex.org/W2110406916") == "W2110406916"
    assert encurtar_id("W2110406916") == "W2110406916"
    assert encurtar_id(None) is None
    assert encurtar_id("  ") is None


# --- Ranking: quantos casaram e em que ordem vêm ------------------------------


@pytest.mark.asyncio
async def test_a_amostra_vem_com_o_tamanho_do_universo() -> None:
    """ "Achei 5" e "achei 5 de 49" são informações diferentes.

    Sem o total, quem ranqueia depois não sabe se está vendo a nata ou o acervo.
    """
    bancada = bancada_comum()

    resultado = await bancada.cliente.buscar_varias(["polylaminin"], quantidade=5)

    assert len(resultado.trabalhos) == 5
    assert resultado.total_por_busca == {"polylaminin": 49}


@pytest.mark.asyncio
async def test_relevancia_e_citacoes_chegam_ao_chamador() -> None:
    bancada = bancada_comum()

    trabalhos = await bancada.cliente.buscar("polylaminin")

    assert trabalhos[0].relevancia is not None and trabalhos[0].relevancia > 0
    assert isinstance(trabalhos[0].citacoes, int)


@pytest.mark.asyncio
async def test_a_ordem_da_openalex_e_preservada() -> None:
    """A OpenAlex já entrega por relevância decrescente; reordenar perderia isso."""
    bancada = bancada_comum()

    trabalhos = await bancada.cliente.buscar("polylaminin")

    pontuacoes = [t.relevancia for t in trabalhos if t.relevancia is not None]
    assert pontuacoes == sorted(pontuacoes, reverse=True)


@pytest.mark.asyncio
async def test_relevancia_ausente_na_resposta_vira_none() -> None:
    """Ordenando por citações, a OpenAlex devolve `relevance_score` nulo."""
    sem_escore = {
        "meta": {"count": 3},
        "results": [{"id": "https://openalex.org/W1", "display_name": "um"}],
    }
    bancada = Bancada(devolver(sem_escore))

    trabalhos = await bancada.cliente.buscar("x", quantidade=1)

    assert trabalhos[0].relevancia is None
    assert trabalhos[0].citacoes is None


@pytest.mark.parametrize(
    ("ordenar_por", "sort_esperado"),
    [
        ("relevancia", None),
        ("citacoes", "cited_by_count:desc"),
        ("ano", "publication_year:desc"),
    ],
)
@pytest.mark.asyncio
async def test_ordenacao_vira_parametro_sort(
    ordenar_por: str, sort_esperado: str | None
) -> None:
    """Relevância é o padrão da OpenAlex e não manda `sort` nenhum."""
    bancada = bancada_comum()

    await bancada.cliente.buscar("polylaminin", ordenar_por=ordenar_por)

    if sort_esperado is None:
        assert "sort" not in bancada.ultima.url.params
    else:
        assert bancada.ultima.url.params["sort"] == sort_esperado


@pytest.mark.asyncio
async def test_ordenacao_desconhecida_e_recusada_sem_rede() -> None:
    bancada = bancada_comum()

    with pytest.raises(ValueError, match="ordenar_por"):
        await bancada.cliente.buscar("polylaminin", ordenar_por="popularidade")

    assert bancada.requisicoes == []


@pytest.mark.asyncio
async def test_pedido_de_200_e_aceito_que_e_o_teto_da_openalex() -> None:
    bancada = bancada_comum()

    await bancada.cliente.buscar("polylaminin", quantidade=200)

    assert bancada.ultima.url.params["per-page"] == "200"
    assert QUANTIDADE_MAXIMA == 200, "acima de 200 a OpenAlex responde 400"


@pytest.mark.asyncio
async def test_resposta_sem_meta_nao_derruba_a_busca() -> None:
    bancada = Bancada(devolver({"results": [{"id": "https://openalex.org/W1"}]}))

    resultado = await bancada.cliente.buscar_varias(["x"])

    assert resultado.total_por_busca == {"x": 1}


# --- O top 5: quantos saem, e de onde -----------------------------------------


@pytest.mark.asyncio
async def test_o_lote_devolve_cinco_por_padrao() -> None:
    """Sem BERTopic: o top 5 é o que a OpenAlex já ordenou por relevância."""
    bancada = Bancada(devolver(corpo_com(*((f"W{n}", f"t{n}") for n in range(20)))))

    resultado = await bancada.cliente.buscar_varias(["polylaminin"])

    assert len(resultado.trabalhos) == TOP_PADRAO == 5
    assert [t.id for t in resultado.trabalhos] == ["W0", "W1", "W2", "W3", "W4"]


@pytest.mark.asyncio
async def test_com_uma_busca_o_top5_e_a_ordem_da_openalex() -> None:
    bancada = bancada_comum()

    resultado = await bancada.cliente.buscar_varias(["polylaminin"], quantidade=5)

    pontuacoes = [t.relevancia for t in resultado.trabalhos]
    assert pontuacoes == sorted(pontuacoes, reverse=True)


@pytest.mark.asyncio
async def test_com_varias_buscas_o_top5_pega_de_todas() -> None:
    """Concatenar daria os 5 da primeira busca e nada das outras.

    O ponto das variações é cobertura; intercalar é o que preserva isso.
    """
    bancada = Bancada(
        responder_por_busca(
            {
                "a": corpo_com(("A1", "a1"), ("A2", "a2"), ("A3", "a3")),
                "b": corpo_com(("B1", "b1"), ("B2", "b2"), ("B3", "b3")),
            }
        )
    )

    resultado = await bancada.cliente.buscar_varias(["a", "b"])

    assert [t.id for t in resultado.trabalhos] == ["A1", "B1", "A2", "B2", "A3"]


@pytest.mark.asyncio
async def test_a_intercalacao_nao_repete_o_que_as_duas_acharam() -> None:
    bancada = Bancada(
        responder_por_busca(
            {
                "a": corpo_com(("X", "x"), ("A2", "a2")),
                "b": corpo_com(("X", "x"), ("B2", "b2")),
            }
        )
    )

    resultado = await bancada.cliente.buscar_varias(["a", "b"])

    assert [t.id for t in resultado.trabalhos] == ["X", "A2", "B2"]


def test_intercalar_aceita_outra_chave_de_repeticao() -> None:
    """O Pesquisador desduplica por DOI: ids diferentes, mesmo artigo."""

    def trabalho(identificador: str, doi: str | None) -> Trabalho:
        return Trabalho(
            id=identificador,
            titulo=identificador,
            ano=2020,
            doi=doi,
            retratado=False,
            abstract=None,
            relevancia=None,
            citacoes=None,
        )

    listas = [
        [trabalho("W1", "10.1/x"), trabalho("W2", None)],
        [trabalho("W9", "10.1/x"), trabalho("W3", None)],
    ]

    pelo_id = intercalar(listas, 10)
    pelo_doi = intercalar(listas, 10, chave=lambda t: t.doi or t.id or "")

    assert [t.id for t in pelo_id] == ["W1", "W9", "W2", "W3"]
    assert [t.id for t in pelo_doi] == ["W1", "W2", "W3"]


@pytest.mark.asyncio
async def test_busca_curta_nao_atropela_a_longa_por_ter_escore_maior() -> None:
    """O escore mede a busca, não o artigo: medido, 870 contra 227.

    Ordenar a lista juntada por `relevancia` faria a formulação curta levar
    todas as vagas. Por isso a ordem final é por posição.
    """
    curta = {
        "meta": {"count": 9},
        "results": [
            {"id": "https://openalex.org/CURTA1", "relevance_score": 870.0},
            {"id": "https://openalex.org/CURTA2", "relevance_score": 531.0},
        ],
    }
    longa = {
        "meta": {"count": 9},
        "results": [
            {"id": "https://openalex.org/LONGA1", "relevance_score": 227.0},
            {"id": "https://openalex.org/LONGA2", "relevance_score": 206.0},
        ],
    }
    bancada = Bancada(responder_por_busca({"curta": curta, "longa": longa}))

    resultado = await bancada.cliente.buscar_varias(["curta", "longa"])

    ids = [t.id for t in resultado.trabalhos]
    assert ids == ["CURTA1", "LONGA1", "CURTA2", "LONGA2"]
    assert ids[1] == "LONGA1", "o 1º da longa não pode perder para o 2º da curta"


@pytest.mark.asyncio
async def test_limite_maior_que_o_padrao_e_respeitado() -> None:
    bancada = Bancada(devolver(corpo_com(*((f"W{n}", f"t{n}") for n in range(40)))))

    resultado = await bancada.cliente.buscar_varias(["x"], quantidade=40, limite=30)

    assert len(resultado.trabalhos) == 30


# --- Critério 11: busca em branco --------------------------------------------


@pytest.mark.parametrize("busca", ["", "   ", "\n\t"])
@pytest.mark.asyncio
async def test_busca_em_branco_e_recusada_sem_chamar_a_rede(busca: str) -> None:
    bancada = bancada_comum()

    with pytest.raises(ValueError, match="vazia"):
        await bancada.cliente.buscar(busca)

    assert bancada.requisicoes == []


# --- Configuração ------------------------------------------------------------


@pytest.mark.asyncio
async def test_cliente_montado_a_partir_das_configuracoes(monkeypatch) -> None:
    from src.core.config.settings import get_settings

    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://db/verificador")
    monkeypatch.setenv("OPENALEX_MAILTO", CONTATO)
    monkeypatch.setenv("OPENALEX_RESULTADOS_POR_BUSCA", "4")
    monkeypatch.setenv("OPENALEX_TIMEOUT_SEGUNDOS", "2")
    monkeypatch.setenv("OPENALEX_MAX_TENTATIVAS", "2")
    get_settings.cache_clear()

    cliente = ClienteOpenAlex.a_partir_das_configuracoes()
    try:
        assert cliente.mailto == CONTATO
        assert cliente.quantidade_padrao == 4
        assert cliente.timeout_segundos == 2.0
        assert cliente.max_tentativas == 2
    finally:
        await cliente.fechar()
        get_settings.cache_clear()
