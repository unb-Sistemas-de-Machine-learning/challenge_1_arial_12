import pytest
from src.agents.triador import AgenteTriador
from src.services.llm import (
    ClienteLLM,
    LLMIndisponivel,
    RespostaInvalidaDoLLM,
    FalhaTransitoria,
)
from src.tests.dubles.llm import DubleLLM


@pytest.fixture
def sem_espera():
    async def _dormir(segundos: float) -> None:
        pass

    return _dormir


@pytest.mark.asyncio
async def test_devolve_variacoes_sem_repeticao(sem_espera):
    duble = DubleLLM({"buscas": ["Termo 1", "termo 1", "Termo 2"]})
    cliente = ClienteLLM(duble, dormir=sem_espera)
    agente = AgenteTriador(cliente, max_variacoes=3)

    trecho = "Isso é um teste"
    # O agente devolve [trecho, "Termo 1", "Termo 2"] (sem "termo 1" repetido)
    resultado = await agente.extrair_buscas(trecho)

    assert resultado == ["Isso é um teste", "Termo 1", "Termo 2"]


@pytest.mark.asyncio
async def test_respeita_limite_configuravel_n(sem_espera):
    duble = DubleLLM({"buscas": ["A", "B", "C", "D"]})
    cliente = ClienteLLM(duble, dormir=sem_espera)
    agente = AgenteTriador(cliente, max_variacoes=2)

    trecho = "Isso é um teste"
    resultado = await agente.extrair_buscas(trecho)

    # Original + max_variacoes
    assert resultado == ["Isso é um teste", "A", "B"]


@pytest.mark.asyncio
async def test_descarta_variacoes_acima_do_tamanho(sem_espera):
    duble = DubleLLM({"buscas": ["A", "B" * 201, "C"]})
    cliente = ClienteLLM(duble, dormir=sem_espera)
    agente = AgenteTriador(cliente, max_tamanho_variacao=200)

    trecho = "Isso é um teste"
    resultado = await agente.extrair_buscas(trecho)

    assert resultado == ["Isso é um teste", "A", "C"]


@pytest.mark.asyncio
async def test_degrada_se_saida_fora_do_formato(sem_espera):
    # Passando uma string que não é o schema esperado
    duble = DubleLLM('{"chave_errada": ["A", "B"]}')
    cliente = ClienteLLM(duble, dormir=sem_espera)
    agente = AgenteTriador(cliente)

    trecho = "Isso é um teste"
    resultado = await agente.extrair_buscas(trecho)

    assert resultado == ["Isso é um teste"]


@pytest.mark.asyncio
async def test_degrada_se_llm_indisponivel(sem_espera):
    duble = DubleLLM(FalhaTransitoria("503"))
    cliente = ClienteLLM(duble, dormir=sem_espera, max_tentativas=1)
    agente = AgenteTriador(cliente)

    trecho = "Isso é um teste"
    resultado = await agente.extrair_buscas(trecho)

    assert resultado == ["Isso é um teste"]


@pytest.mark.asyncio
async def test_nao_levanta_excecao_com_trecho_valido(sem_espera):
    duble = DubleLLM(Exception("Erro catastrófico do LLM"))
    cliente = ClienteLLM(duble, dormir=sem_espera)
    agente = AgenteTriador(cliente)

    trecho = "Texto válido"
    try:
        resultado = await agente.extrair_buscas(trecho)
        assert resultado == ["Texto válido"]
    except Exception as e:
        pytest.fail(f"Levantou exceção não tratada: {e}")


@pytest.mark.asyncio
async def test_trecho_vazio_retorna_vazio():
    duble = DubleLLM({"buscas": ["A"]})
    cliente = ClienteLLM(duble)
    agente = AgenteTriador(cliente)

    assert await agente.extrair_buscas("") == []
    assert await agente.extrair_buscas("   ") == []
