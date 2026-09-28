"""A única conversa de verdade com a OpenAlex.

Marcado `rede` e, por isso, **fora da execução padrão** — inclusive na CI. Um
serviço de terceiro fora do ar viraria um check vermelho que não aponta defeito
nenhum no projeto, e a equipe aprenderia a ignorar o vermelho.

Ele existe para a hora em que importa: antes de uma entrega que dependa da
busca, ou quando um teste unitário passa mas a integração não funciona — o
sintoma de fixture velha. Rode com:

    pytest -m rede
"""

import httpx
import pytest

from src.core.config.settings import Settings
from src.services.openalex import ClienteOpenAlex, OpenAlexIndisponivel, Trabalho

BUSCA = "polylaminin spinal cord injury"


def _configuracao() -> Settings | None:
    try:
        return Settings()
    except Exception:
        # Sem .env válido não há o que configurar; o skip abaixo explica.
        return None


_SETTINGS = _configuracao()
CONTATO = _SETTINGS.openalex_mailto if _SETTINGS else None
# Sem chave a OpenAlex corta a busca sob carga, mesmo com o mailto preenchido.
CHAVE = (
    _SETTINGS.openalex_api_key.get_secret_value()
    if _SETTINGS and _SETTINGS.openalex_api_key
    else None
)

pytestmark = [
    pytest.mark.rede,
    pytest.mark.skipif(
        not CONTATO,
        reason="Defina OPENALEX_MAILTO: o polite pool da OpenAlex exige contato",
    ),
]


def cliente() -> ClienteOpenAlex:
    return ClienteOpenAlex(mailto=CONTATO or "", api_key=CHAVE)


def pular_se_fora_do_ar(erro: OpenAlexIndisponivel) -> None:
    """Indisponibilidade deles não é defeito nosso: pula em vez de falhar.

    Quando a OpenAlex pausa a busca por carga, o cliente faz exatamente o que a
    spec manda — repete e levanta `OpenAlexIndisponivel`. Marcar isso como
    vermelho ensinaria a equipe a ignorar o vermelho.
    """
    pytest.skip(f"OpenAlex indisponível agora: {erro}")


@pytest.mark.asyncio
async def test_busca_real_devolve_trabalhos_dentro_do_contrato() -> None:
    async with cliente() as aberto:
        try:
            trabalhos = await aberto.buscar(BUSCA, quantidade=3)
        except OpenAlexIndisponivel as erro:
            pular_se_fora_do_ar(erro)

    assert 1 <= len(trabalhos) <= 3
    for trabalho in trabalhos:
        assert isinstance(trabalho, Trabalho)
        assert trabalho.titulo and isinstance(trabalho.titulo, str)
        assert trabalho.id and trabalho.id.startswith("W")
        assert trabalho.ano is None or isinstance(trabalho.ano, int)
        assert trabalho.doi is None or not trabalho.doi.startswith("http")
        assert isinstance(trabalho.retratado, bool)
        assert trabalho.abstract is None or isinstance(trabalho.abstract, str)

    assert any(trabalho.abstract for trabalho in trabalhos), (
        "nenhum abstract remontado: o índice invertido da OpenAlex pode ter mudado"
    )


@pytest.mark.asyncio
async def test_busca_real_sem_correspondencia_devolve_lista_vazia() -> None:
    """Confirma que "nada encontrado" chega como lista vazia, e não como erro."""
    async with cliente() as aberto:
        try:
            assert await aberto.buscar("zzzqqqxyw nonexistent term 12345") == []
        except OpenAlexIndisponivel as erro:
            pular_se_fora_do_ar(erro)


@pytest.mark.asyncio
async def test_lote_de_buscas_junta_e_desduplica_de_verdade() -> None:
    """Três variações com sobreposição garantida: o total tem que ser menor."""
    variacoes = [
        "polylaminin spinal cord injury",
        "polylaminin regeneration",
        "laminin polymer nerve repair",
    ]
    async with cliente() as aberto:
        try:
            resultado = await aberto.buscar_varias(variacoes, quantidade=10)
            isoladas = [await aberto.buscar(v, quantidade=10) for v in variacoes]
        except OpenAlexIndisponivel as erro:
            pular_se_fora_do_ar(erro)

    assert resultado.falhas == {}
    chaves = [trabalho.chave for trabalho in resultado.trabalhos]
    assert len(chaves) == len(set(chaves)), "veio trabalho repetido no lote"
    assert len(chaves) < sum(len(lista) for lista in isoladas), (
        "sem sobreposição nenhuma, o teste não prova a desduplicação"
    )


@pytest.mark.asyncio
async def test_consulta_booleana_com_parenteses_e_respeitada() -> None:
    """Parênteses agrupam na OpenAlex; o cliente não pode tocar na string.

    Sem o agrupamento a mesma consulta devolve uma ordem de grandeza a menos,
    então esta é a diferença entre buscar o que foi pedido e buscar outra coisa.
    """
    agrupada = (
        '("Service Design" OR "User Experience" OR "UX") '
        'AND ("ITSM" OR "IT Service Management" OR "ITIL") '
        'AND ("service catalog" OR "service portal" OR "self-service portal")'
    )
    async with cliente() as aberto:
        try:
            com_grupos = await aberto.buscar(agrupada, quantidade=5)
            sem_grupos = await aberto.buscar(
                agrupada.replace("(", "").replace(")", ""), quantidade=5
            )
        except OpenAlexIndisponivel as erro:
            pular_se_fora_do_ar(erro)

    assert com_grupos, "a consulta agrupada não devolveu nada"
    assert [t.chave for t in com_grupos] != [t.chave for t in sem_grupos], (
        "com e sem parênteses deu o mesmo: a OpenAlex parou de agrupar"
    )


@pytest.mark.asyncio
async def test_a_openalex_ainda_devolve_os_campos_que_as_fixtures_gravaram() -> None:
    """Guarda contra fixture velha: confere o formato cru, antes da tradução.

    Se a OpenAlex renomear um campo, os testes unitários continuam verdes com as
    respostas gravadas — e só este aqui percebe.
    """
    from src.services.openalex import CAMPOS, URL_BASE

    cabecalhos = {"Authorization": f"Bearer {CHAVE}"} if CHAVE else {}
    async with httpx.AsyncClient(timeout=30) as http:
        resposta = await http.get(
            URL_BASE,
            params={
                "search": BUSCA,
                "per-page": 1,
                "select": CAMPOS,
                "mailto": CONTATO,
            },
            headers=cabecalhos,
        )

    if resposta.status_code >= 500:
        pytest.skip(f"OpenAlex indisponível agora: {resposta.status_code}")
    resposta.raise_for_status()
    corpo = resposta.json()
    assert isinstance(corpo.get("results"), list) and corpo["results"]
    assert set(CAMPOS.split(",")) <= set(corpo["results"][0])
