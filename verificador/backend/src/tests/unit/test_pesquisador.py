"""O Pesquisador consolida as buscas do Triador: cache, concorrência e falhas.

Nada aqui toca a rede: o cliente da OpenAlex usa `httpx.MockTransport`, e cada
busca responde conforme a string que chegou.
"""

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from src.agents.pesquisador import (
    AgentePesquisador,
    ResultadoDaPesquisa,
    chave_por_doi,
)
from src.api.schemas.busca import TrabalhoEncontrado
from src.services.openalex import (
    ClienteOpenAlex,
    OpenAlexIndisponivel,
    OpenAlexRecusouABusca,
    Trabalho,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "openalex"


def registro(
    identificador: str,
    doi: str | None = ...,  # type: ignore[assignment]
    *,
    abstract: bool = True,
    retratado: bool = False,
) -> dict:
    """Registro mínimo da OpenAlex, com o abstract em índice invertido.

    Julgável por padrão -- com abstract, com DOI e não retratado --, porque é
    o caso normal e porque o Pesquisador agora descarta o que não é. Quem testa
    o descarte pede o contrário de propósito: `doi=None`, `abstract=False` ou
    `retratado=True`.
    """
    return {
        "id": f"https://openalex.org/{identificador}",
        "display_name": f"Trabalho {identificador}",
        "publication_year": 2020,
        "doi": f"10.1/{identificador.casefold()}" if doi is ... else doi,
        "is_retracted": retratado,
        "abstract_inverted_index": ({"texto": [0], "curto": [1]} if abstract else None),
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
    # Quatro, e não os cinco que a OpenAlex devolveu: esta é uma resposta real
    # capturada, e um dos cinco veio sem `abstract_inverted_index`. O número
    # mede a cobertura de abstract da OpenAlex, não o Pesquisador -- 20% da
    # primeira página de uma busca comum não é julgável.
    assert len(resultado.trabalhos) == 4
    assert resultado.nao_julgaveis == 1
    assert all(isinstance(t, TrabalhoEncontrado) for t in resultado.trabalhos)
    assert all(t.abstract and t.doi for t in resultado.trabalhos)
    assert resultado.trabalhos[0].doi == "10.1096/fj.10-157628"


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
async def test_o_mesmo_id_em_duas_buscas_sai_uma_vez_so() -> None:
    openalex = OpenAlexFalsa(
        {
            "a": corpo(registro("W1"), registro("W2")),
            "b": corpo(registro("W1"), registro("W3")),
        }
    )

    resultado = await AgentePesquisador(openalex.cliente()).pesquisar(["a", "b"])

    assert [t.id for t in resultado.trabalhos] == ["W1", "W2", "W3"]


def test_chave_por_doi_cai_no_id_quando_nao_ha_doi() -> None:
    """A queda para o id não passa mais por `pesquisar` -- todo trabalho que
    chega à intercalação tem DOI, senão `julgavel` o teria barrado. O
    comportamento fica testado aqui porque `chave_por_doi` é usada direto em
    `intercalar` e a queda ainda é o que impede id e DOI de colidirem.
    """
    sem_doi = Trabalho(
        id="W1",
        titulo="t",
        ano=2020,
        doi=None,
        retratado=False,
        abstract="a",
        relevancia=None,
        citacoes=None,
    )

    assert chave_por_doi(sem_doi) == "id:W1"


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


@pytest.mark.asyncio
async def test_todas_recusadas_nao_viram_indisponivel() -> None:
    """Recusa não é queda: dizer o contrário manda o leitor esperar por nada."""
    openalex = OpenAlexFalsa({"a": 400, "b": 422})

    with pytest.raises(OpenAlexRecusouABusca):
        await AgentePesquisador(openalex.cliente()).pesquisar(["a", "b"])


@pytest.mark.asyncio
async def test_uma_indisponivel_no_meio_das_recusas_ainda_e_indisponivel() -> None:
    """A dúvida pende para o serviço: com uma queda no meio, repetir pode valer."""
    openalex = OpenAlexFalsa({"a": 400, "b": 503})

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


# --- Critério 7: o não julgável sai antes do corte ----------------------------


@pytest.mark.asyncio
async def test_trabalho_sem_abstract_e_descartado() -> None:
    openalex = OpenAlexFalsa({"a": corpo(registro("W1", abstract=False))})

    resultado = await AgentePesquisador(openalex.cliente()).pesquisar(["a"])

    assert resultado.trabalhos == []
    assert resultado.nao_julgaveis == 1


@pytest.mark.asyncio
async def test_trabalho_sem_doi_e_descartado() -> None:
    """Sem DOI o Juiz não consegue conferir a citação contra o trabalho certo."""
    openalex = OpenAlexFalsa({"a": corpo(registro("W1", None))})

    resultado = await AgentePesquisador(openalex.cliente()).pesquisar(["a"])

    assert resultado.trabalhos == []
    assert resultado.nao_julgaveis == 1


@pytest.mark.asyncio
async def test_retratado_e_descartado() -> None:
    openalex = OpenAlexFalsa({"a": corpo(registro("W1", retratado=True))})

    resultado = await AgentePesquisador(openalex.cliente()).pesquisar(["a"])

    assert resultado.trabalhos == []
    assert resultado.nao_julgaveis == 1


@pytest.mark.asyncio
async def test_o_nao_julgavel_nao_ocupa_vaga_do_limite() -> None:
    """O ponto da mudança: as vagas vão para quem o Juiz consegue ler.

    Antes, os três primeiros sem abstract enchiam as vagas e o Juiz recebia
    lista vazia -- `nada_encontrado` com cinco artigos achados na mão.
    """
    openalex = OpenAlexFalsa(
        {
            "a": corpo(
                registro("S1", abstract=False),
                registro("S2", abstract=False),
                registro("S3", abstract=False),
                registro("C1"),
                registro("C2"),
            )
        }
    )

    resultado = await AgentePesquisador(openalex.cliente(), limite=2).pesquisar(["a"])

    assert [t.id for t in resultado.trabalhos] == ["C1", "C2"]
    assert resultado.nao_julgaveis == 3


@pytest.mark.asyncio
async def test_nada_julgavel_devolve_lista_vazia_sem_erro() -> None:
    """Lista vazia, e não exceção: quem decide o veredito é o Juiz.

    `nao_julgaveis` é o que separa isto de "a busca não achou nada" -- os dois
    chegam ao Juiz como lista vazia.
    """
    openalex = OpenAlexFalsa(
        {"a": corpo(registro("W1", abstract=False), registro("W2", None))}
    )

    resultado = await AgentePesquisador(openalex.cliente()).pesquisar(["a"])

    assert resultado.trabalhos == []
    assert resultado.falhas == {}
    assert resultado.nao_julgaveis == 2


@pytest.mark.asyncio
async def test_busca_vazia_nao_conta_como_nao_julgavel() -> None:
    openalex = OpenAlexFalsa({"a": corpo()})

    resultado = await AgentePesquisador(openalex.cliente()).pesquisar(["a"])

    assert resultado.trabalhos == []
    assert resultado.nao_julgaveis == 0


@pytest.mark.asyncio
async def test_o_mesmo_nao_julgavel_em_duas_buscas_conta_uma_vez() -> None:
    """Contagem por identidade: somar os descartes de cada lista inflaria."""
    sem_abstract = registro("W1", "10.1/repetido", abstract=False)
    openalex = OpenAlexFalsa(
        {"a": corpo(sem_abstract), "b": corpo(sem_abstract, registro("W2"))}
    )

    resultado = await AgentePesquisador(openalex.cliente()).pesquisar(["a", "b"])

    assert [t.id for t in resultado.trabalhos] == ["W2"]
    assert resultado.nao_julgaveis == 1


# --- Atalho pelo título citado -----------------------------------------------


@pytest.mark.asyncio
async def test_titulo_que_acha_responde_sozinho_e_os_eixos_nao_rodam() -> None:
    """A economia é o ponto: uma requisição no lugar de todas as dos eixos."""
    openalex = OpenAlexFalsa(
        {
            "Polylaminin promotes regeneration": corpo(registro("WTITULO")),
            "polylaminin": corpo(registro("WCONCEITO")),
        }
    )

    resultado = await AgentePesquisador(openalex.cliente()).pesquisar(
        ["polylaminin"], busca_de_titulo="Polylaminin promotes regeneration"
    )

    assert [t.id for t in resultado.trabalhos] == ["WTITULO"]
    assert resultado.veio_do_titulo is True
    assert resultado.falha_do_titulo is None
    assert openalex.recebidas == ["Polylaminin promotes regeneration"]


@pytest.mark.asyncio
async def test_titulo_sem_resultado_cai_nos_conceitos() -> None:
    openalex = OpenAlexFalsa(
        {"Titulo que nao existe": corpo(), "polylaminin": corpo(registro("WCONCEITO"))}
    )

    resultado = await AgentePesquisador(openalex.cliente()).pesquisar(
        ["polylaminin"], busca_de_titulo="Titulo que nao existe"
    )

    assert [t.id for t in resultado.trabalhos] == ["WCONCEITO"]
    assert resultado.veio_do_titulo is False
    # Não achar nada não é falha de ninguém: não há o que reportar.
    assert resultado.falha_do_titulo is None


@pytest.mark.asyncio
async def test_titulo_que_acha_so_nao_julgavel_cai_nos_conceitos() -> None:
    """Achar um artigo que o Juiz não sabe ler é o mesmo que não achar."""
    openalex = OpenAlexFalsa(
        {
            "Um titulo qualquer": corpo(registro("WSEMABS", abstract=False)),
            "polylaminin": corpo(registro("WCONCEITO")),
        }
    )

    resultado = await AgentePesquisador(openalex.cliente()).pesquisar(
        ["polylaminin"], busca_de_titulo="Um titulo qualquer"
    )

    assert [t.id for t in resultado.trabalhos] == ["WCONCEITO"]
    assert resultado.veio_do_titulo is False


@pytest.mark.asyncio
async def test_titulo_que_falha_na_openalex_nao_derruba_a_pesquisa() -> None:
    """O atalho é otimização: a falha dele vai ao log, não ao leitor."""
    openalex = OpenAlexFalsa(
        {"Um titulo qualquer": 500, "polylaminin": corpo(registro("WCONCEITO"))}
    )

    resultado = await AgentePesquisador(openalex.cliente()).pesquisar(
        ["polylaminin"], busca_de_titulo="Um titulo qualquer"
    )

    assert [t.id for t in resultado.trabalhos] == ["WCONCEITO"]
    assert resultado.veio_do_titulo is False
    assert resultado.falha_do_titulo is not None
    # Separado de `falhas`, que é o que decide se a pesquisa inteira fracassou.
    assert resultado.falhas == {}


@pytest.mark.asyncio
async def test_titulo_que_acha_responde_mesmo_sem_busca_de_conceito() -> None:
    """Trecho com menos de dois conceitos, mas que nomeia o artigo: tem resposta.

    Sem o atalho esta lista vazia era `ValueError`, e a rota respondia
    `entrada_invalida` -- para um trecho que trazia a referência exata.
    """
    openalex = OpenAlexFalsa({"Um titulo bem especifico": corpo(registro("WTITULO"))})

    resultado = await AgentePesquisador(openalex.cliente()).pesquisar(
        [], busca_de_titulo="Um titulo bem especifico"
    )

    assert [t.id for t in resultado.trabalhos] == ["WTITULO"]
    assert resultado.veio_do_titulo is True


@pytest.mark.asyncio
async def test_titulo_passa_pelo_cache_como_qualquer_busca() -> None:
    openalex = OpenAlexFalsa({"Titulo em cache": corpo(registro("WTITULO"))})
    cache = CacheEmMemoria()
    agente = AgentePesquisador(openalex.cliente(), cache=cache)

    primeiro = await agente.pesquisar([], busca_de_titulo="Titulo em cache")
    segundo = await agente.pesquisar([], busca_de_titulo="Titulo em cache")

    assert [t.id for t in primeiro.trabalhos] == ["WTITULO"]
    assert [t.id for t in segundo.trabalhos] == ["WTITULO"]
    # Uma requisição para as duas pesquisas: a segunda saiu do cache.
    assert openalex.recebidas == ["Titulo em cache"]
    assert cache.gravacoes == ["Titulo em cache"]


@pytest.mark.asyncio
async def test_sem_titulo_o_comportamento_e_o_de_antes() -> None:
    """A assinatura nova não muda quem não passa o parâmetro."""
    openalex = OpenAlexFalsa({"polylaminin": corpo(registro("WCONCEITO"))})

    resultado = await AgentePesquisador(openalex.cliente()).pesquisar(["polylaminin"])

    assert [t.id for t in resultado.trabalhos] == ["WCONCEITO"]
    assert resultado.veio_do_titulo is False
    assert resultado.falha_do_titulo is None
