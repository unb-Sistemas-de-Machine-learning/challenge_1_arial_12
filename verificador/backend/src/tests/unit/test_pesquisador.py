"""O Pesquisador consolida as buscas do Triador: cache, concorrência e falhas.

Nada aqui toca a rede: o cliente da OpenAlex usa `httpx.MockTransport`, e cada
busca responde conforme a string que chegou.
"""

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from src.agents.pesquisador import AgentePesquisador, ResultadoDaPesquisa
from src.api.schemas.busca import TrabalhoEncontrado
from src.services.openalex import ClienteOpenAlex, OpenAlexIndisponivel, Trabalho

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "openalex"


def registro(identificador: str, doi: str | None = None) -> dict:
    """Registro mínimo da OpenAlex, com o abstract em índice invertido."""
    return {
        "id": f"https://openalex.org/{identificador}",
        "display_name": f"Trabalho {identificador}",
        "publication_year": 2020,
        "doi": doi,
        "is_retracted": False,
        "abstract_inverted_index": {"texto": [0], "curto": [1]},
    }


def corpo(*registros: dict) -> dict:
    return {"results": list(registros), "meta": {"count": len(registros)}}


def termo_da(requisicao: httpx.Request) -> str:
    return requisicao.url.params["filter"].replace("title_and_abstract.search:", "")


class OpenAlexFalsa:
    """Responde por busca e registra o que chegou e quantas estavam abertas."""

    def __init__(self, mapa: dict[str, dict | int], *, atraso: float = 0.0) -> None:
        self.mapa = mapa
        self.atraso = atraso
        self.recebidas: list[str] = []
        self.abertas = 0
        self.pico = 0

    async def atender(self, requisicao: httpx.Request) -> httpx.Response:
        termo = termo_da(requisicao)
        self.recebidas.append(termo)
        self.abertas += 1
        self.pico = max(self.pico, self.abertas)
        try:
            await asyncio.sleep(self.atraso)
            item = self.mapa[termo]
            if isinstance(item, int):
                return httpx.Response(item, json={"error": "dublê"})
            return httpx.Response(200, json=item)
        finally:
            self.abertas -= 1

    def cliente(self) -> ClienteOpenAlex:
        async def sem_espera(_segundos: float) -> None:
            return None

        return ClienteOpenAlex(
            mailto="contato@example.com",
            cliente_http=httpx.AsyncClient(transport=httpx.MockTransport(self.atender)),
            max_tentativas=1,
            dormir=sem_espera,
        )


class CacheEmMemoria:
    def __init__(self, guardados: dict[str, list[Trabalho]] | None = None) -> None:
        self.guardados = dict(guardados or {})
        self.gravacoes: list[str] = []

    async def obter(self, busca: str) -> list[Trabalho] | None:
        return self.guardados.get(busca)

    async def guardar(self, busca: str, trabalhos: list[Trabalho]) -> None:
        self.gravacoes.append(busca)
        self.guardados[busca] = trabalhos


class CacheQuebrado:
    async def obter(self, busca: str) -> list[Trabalho] | None:
        raise RuntimeError("cache fora do ar")

    async def guardar(self, busca: str, trabalhos: list[Trabalho]) -> None:
        raise RuntimeError("cache fora do ar")


# --- Caminho feliz -----------------------------------------------------------


@pytest.mark.asyncio
async def test_devolve_os_trabalhos_no_tipo_que_o_juiz_recebe() -> None:
    fixture = json.loads((FIXTURES / "busca_polilaminina.json").read_text("utf-8"))
    openalex = OpenAlexFalsa({"polylaminin": fixture})

    resultado = await AgentePesquisador(openalex.cliente()).pesquisar(["polylaminin"])

    assert isinstance(resultado, ResultadoDaPesquisa)
    assert resultado.falhas == {}
    assert len(resultado.trabalhos) == 5
    assert all(isinstance(t, TrabalhoEncontrado) for t in resultado.trabalhos)
    assert resultado.trabalhos[0].doi == "10.1096/fj.10-157628"
    assert resultado.trabalhos[0].abstract


@pytest.mark.asyncio
async def test_lista_sem_busca_util_e_recusada_sem_chamar_a_openalex() -> None:
    openalex = OpenAlexFalsa({})

    with pytest.raises(ValueError):
        await AgentePesquisador(openalex.cliente()).pesquisar(["  ", ""])

    assert openalex.recebidas == []


# --- Critério 1: sem duplicatas por DOI ---------------------------------------


@pytest.mark.asyncio
async def test_mesmo_doi_em_formatos_diferentes_sai_uma_vez_so() -> None:
    """Ids diferentes (preprint e publicado), mesmo DOI: é o mesmo artigo."""
    openalex = OpenAlexFalsa(
        {
            "a": corpo(registro("W1", "https://doi.org/10.1/ABC"), registro("W2")),
            "b": corpo(registro("W9", "https://doi.org/10.1/abc"), registro("W3")),
        }
    )

    resultado = await AgentePesquisador(openalex.cliente()).pesquisar(["a", "b"])

    assert [t.id for t in resultado.trabalhos] == ["W1", "W2", "W3"]


@pytest.mark.asyncio
async def test_sem_doi_a_repeticao_e_reconhecida_pelo_id() -> None:
    openalex = OpenAlexFalsa(
        {
            "a": corpo(registro("W1"), registro("W2")),
            "b": corpo(registro("W1"), registro("W3")),
        }
    )

    resultado = await AgentePesquisador(openalex.cliente()).pesquisar(["a", "b"])

    assert [t.id for t in resultado.trabalhos] == ["W1", "W2", "W3"]


@pytest.mark.asyncio
async def test_repetido_nao_ocupa_vaga_do_limite() -> None:
    """Desduplicar antes do corte: o Juiz recebe o limite inteiro de artigos."""
    openalex = OpenAlexFalsa(
        {
            "a": corpo(*(registro(f"A{n}", f"10.1/{n}") for n in range(3))),
            "b": corpo(*(registro(f"B{n}", f"10.1/{n}") for n in range(3))),
            "c": corpo(registro("C0", "10.2/c")),
        }
    )

    resultado = await AgentePesquisador(openalex.cliente(), limite=4).pesquisar(
        ["a", "b", "c"]
    )

    assert [t.id for t in resultado.trabalhos] == ["A0", "C0", "A1", "A2"]


# --- Critério 2: concorrência limitada ----------------------------------------


@pytest.mark.asyncio
async def test_concorrencia_nunca_passa_do_limite() -> None:
    buscas = [f"busca {n}" for n in range(5)]
    openalex = OpenAlexFalsa(
        {busca: corpo(registro(f"W{n}")) for n, busca in enumerate(buscas)},
        atraso=0.02,
    )

    await AgentePesquisador(openalex.cliente(), concorrencia=2).pesquisar(buscas)

    assert sorted(openalex.recebidas) == sorted(buscas)
    assert openalex.pico == 2


@pytest.mark.asyncio
async def test_as_buscas_rodam_em_paralelo() -> None:
    """Sem isto, um Pesquisador sequencial passaria no teste do limite."""
    buscas = [f"busca {n}" for n in range(4)]
    openalex = OpenAlexFalsa(
        {busca: corpo(registro(f"W{n}")) for n, busca in enumerate(buscas)},
        atraso=0.02,
    )

    await AgentePesquisador(openalex.cliente(), concorrencia=4).pesquisar(buscas)

    assert openalex.pico == 4


# --- Critérios 3 e 4: falha parcial e falha total ------------------------------


@pytest.mark.asyncio
async def test_falha_parcial_consolida_as_que_funcionaram(caplog) -> None:
    openalex = OpenAlexFalsa({"quebra": 500, "funciona": corpo(registro("W1"))})

    with caplog.at_level("WARNING", logger="verificador.agentes.pesquisador"):
        resultado = await AgentePesquisador(openalex.cliente()).pesquisar(
            ["quebra", "funciona"]
        )

    assert [t.id for t in resultado.trabalhos] == ["W1"]
    assert list(resultado.falhas) == ["quebra"]
    assert "quebra" in caplog.text


@pytest.mark.asyncio
async def test_busca_recusada_tambem_conta_como_falha_parcial() -> None:
    openalex = OpenAlexFalsa({"recusada": 400, "funciona": corpo(registro("W1"))})

    resultado = await AgentePesquisador(openalex.cliente()).pesquisar(
        ["recusada", "funciona"]
    )

    assert [t.id for t in resultado.trabalhos] == ["W1"]
    assert list(resultado.falhas) == ["recusada"]


@pytest.mark.asyncio
async def test_todas_falhando_levanta_openalex_indisponivel() -> None:
    openalex = OpenAlexFalsa({"a": 500, "b": 503})

    with pytest.raises(OpenAlexIndisponivel):
        await AgentePesquisador(openalex.cliente()).pesquisar(["a", "b"])


# --- Critério 5: ponto de extensão do cache -----------------------------------


@pytest.mark.asyncio
async def test_acerto_de_cache_nao_chama_a_openalex() -> None:
    guardado = Trabalho(
        id="W7",
        titulo="do cache",
        ano=2021,
        doi="10.9/cache",
        retratado=False,
        abstract="texto",
        relevancia=None,
        citacoes=None,
    )
    cache = CacheEmMemoria({"guardada": [guardado]})
    openalex = OpenAlexFalsa({"nova": corpo(registro("W1"))})

    resultado = await AgentePesquisador(openalex.cliente(), cache=cache).pesquisar(
        ["guardada", "nova"]
    )

    assert openalex.recebidas == ["nova"]
    assert cache.gravacoes == ["nova"]
    assert [t.id for t in resultado.trabalhos] == ["W7", "W1"]


@pytest.mark.asyncio
async def test_lista_vazia_no_cache_tambem_e_acerto() -> None:
    cache = CacheEmMemoria({"sem resultado": []})
    openalex = OpenAlexFalsa({})

    resultado = await AgentePesquisador(openalex.cliente(), cache=cache).pesquisar(
        ["sem resultado"]
    )

    assert openalex.recebidas == []
    assert resultado.trabalhos == []


@pytest.mark.asyncio
async def test_sem_cache_configurado_toda_busca_vai_a_openalex() -> None:
    openalex = OpenAlexFalsa({"a": corpo(registro("W1")), "b": corpo(registro("W2"))})

    await AgentePesquisador(openalex.cliente()).pesquisar(["a", "b"])

    assert sorted(openalex.recebidas) == ["a", "b"]


@pytest.mark.asyncio
async def test_cache_quebrado_nao_derruba_a_pesquisa() -> None:
    openalex = OpenAlexFalsa({"a": corpo(registro("W1"))})

    resultado = await AgentePesquisador(
        openalex.cliente(), cache=CacheQuebrado()
    ).pesquisar(["a"])

    assert openalex.recebidas == ["a"]
    assert [t.id for t in resultado.trabalhos] == ["W1"]


# --- Critério 7: o filtro é do Juiz -------------------------------------------


@pytest.mark.asyncio
async def test_trabalho_sem_abstract_e_sem_doi_nao_e_descartado() -> None:
    sem_nada = registro("W1") | {"abstract_inverted_index": None}
    openalex = OpenAlexFalsa({"a": corpo(sem_nada)})

    resultado = await AgentePesquisador(openalex.cliente()).pesquisar(["a"])

    assert [(t.id, t.doi, t.abstract) for t in resultado.trabalhos] == [
        ("W1", None, None)
    ]
