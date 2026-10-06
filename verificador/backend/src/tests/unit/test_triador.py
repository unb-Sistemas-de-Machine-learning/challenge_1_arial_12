"""O Triador, com o LLM dublado.

A suíte é dividida como o agente: primeiro a parte determinística (forma
canônica, glossário, eixos), depois o agente inteiro com o dublê no lugar do
provedor. O que se cobra aqui não é a qualidade dos termos — isso é eval, em
`evals/triador.jsonl` — e sim que os mesmos termos produzam sempre as mesmas
buscas.

Os casos de comportamento montam o próprio `Glossario`, em vez de usar o
arquivo: assim a equipe pode editar `orientacoes/triador/referencias/`
glossario.md sem derrubar teste nenhum. O que o arquivo de verdade precisa
cumprir está na última seção.
"""

import pytest

from src.agents import orientacoes
from src.agents.orientacoes import ABERTURA_INTERNA
from src.agents.triador import (
    EIXOS,
    AgenteTriador,
    Glossario,
    TermosDeBusca,
    canonizar_termos,
    forma_canonica,
    glossario_padrao,
    ler_glossario,
    montar_buscas,
)
from src.services.llm import ClienteLLM, FalhaTransitoria
from src.tests.dubles.llm import DubleLLM

TRECHO = "Consumo de álcool está ligado ao encolhimento do cérebro"

GLOSSARIO_DE_TESTE = """
| Conceito (PT) | Termo canônico (EN) | Variantes |
| :--- | :--- | :--- |
| consumo de álcool | alcohol consumption | alcohol intake; drinking |
| encolhimento do cérebro | brain atrophy | brain shrinkage |
| linha sem variante | lonely term | |
"""


@pytest.fixture
def glossario() -> Glossario:
    return ler_glossario(GLOSSARIO_DE_TESTE)


@pytest.fixture
def sem_espera():
    async def _dormir(segundos: float) -> None:
        pass

    return _dormir


def agente(*roteiro, glossario: Glossario, sem_espera, **opcoes) -> AgenteTriador:
    cliente = ClienteLLM(DubleLLM(*roteiro), dormir=sem_espera)
    return AgenteTriador(cliente, glossario=glossario, **opcoes)


def termos(**campos: str) -> TermosDeBusca:
    return TermosDeBusca(
        **{
            "intervencao": "",
            "desfecho": "",
            "condicao": "",
            "populacao": "",
            **campos,
        }
    )


# --- Forma canônica -----------------------------------------------------------


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("Alcohol Consumption", "alcohol consumption"),
        ("  alcohol   consumption  ", "alcohol consumption"),
        # A vírgula é o caso que importa: na OpenAlex ela separa filtros.
        ("melanoma, mrna vaccine", "melanoma mrna vaccine"),
        ('"spinal cord" (injury)', "spinal cord injury"),
        ("exercise AND depression", "exercise depression"),
        ("effect of exercise on depression", "effect exercise depression"),
        ("Parkinson's disease", "parkinsons disease"),
        # Uma letra nunca é descartada: há nome de substância que é uma letra.
        ("bisphenol a", "bisphenol a"),
        ("vitamin d supplementation", "vitamin d supplementation"),
        # "in" fica, porque "in vitro" e "in vivo" são termos.
        ("in vitro fertilization", "in vitro fertilization"),
        ("non-small cell lung cancer", "non-small cell lung cancer"),
        ("", ""),
        ("   ", ""),
    ],
    ids=[
        "minusculas",
        "espacos",
        "virgula",
        "aspas_e_parenteses",
        "operador_booleano",
        "conectivos",
        "apostrofo",
        "letra_sozinha",
        "vitamina",
        "in_vitro",
        "hifen",
        "vazio",
        "espaco",
    ],
)
def test_forma_canonica(entrada: str, esperado: str) -> None:
    assert forma_canonica(entrada) == esperado


def test_forma_canonica_corta_campo_que_veio_como_frase() -> None:
    """Teto de cinco palavras: acima disso veio texto no lugar de termo."""
    frase = "alcohol consumption is linked to brain atrophy in older adults"

    assert forma_canonica(frase) == "alcohol consumption linked brain atrophy"


def test_forma_canonica_e_estavel() -> None:
    uma_vez = forma_canonica("Alcohol Intake,")
    assert forma_canonica(uma_vez) == uma_vez


# --- Glossário ----------------------------------------------------------------


def test_glossario_reescreve_variante_para_o_termo_canonico(
    glossario: Glossario,
) -> None:
    assert glossario.aplicar("brain shrinkage") == "brain atrophy"
    assert glossario.aplicar("alcohol intake") == "alcohol consumption"


def test_glossario_reescreve_o_conceito_em_portugues(glossario: Glossario) -> None:
    """Rede de segurança: se o modelo não traduzir, o código traduz."""
    assert glossario.aplicar(forma_canonica("Consumo de Álcool")) == (
        "alcohol consumption"
    )


def test_glossario_reescreve_variante_dentro_de_um_termo_maior(
    glossario: Glossario,
) -> None:
    assert glossario.aplicar("chronic alcohol intake") == "chronic alcohol consumption"


def test_glossario_deixa_passar_o_que_nao_conhece(glossario: Glossario) -> None:
    assert glossario.aplicar("polylaminin") == "polylaminin"


def test_glossario_nao_reescreve_o_proprio_termo_canonico(
    glossario: Glossario,
) -> None:
    assert glossario.aplicar("alcohol consumption") == "alcohol consumption"


def test_primeira_variante_e_a_que_o_eixo_de_sinonimo_usa(
    glossario: Glossario,
) -> None:
    assert glossario.primeira_variante("alcohol consumption") == "alcohol intake"
    assert glossario.primeira_variante("lonely term") == ""
    assert glossario.primeira_variante("polylaminin") == ""


def test_glossario_le_so_a_tabela_da_secao_dele() -> None:
    """Outra tabela no arquivo é prosa, e não vocabulário."""
    arquivo = (
        "| Eixo | Para que serve |\n"
        "| :--- | :--- |\n"
        "| nucleo | a alegação nua |\n"
        "\n## Tabela\n\n"
        "| Conceito | Canônico | Variantes |\n"
        "| :--- | :--- | :--- |\n"
        "| cárie | dental caries | tooth decay |\n"
        "\n## Como acrescentar uma linha\n\n"
        "| exemplo | de | tabela |\n"
    )

    lido = ler_glossario(arquivo)

    assert lido.conceitos == {"cárie": "dental caries"}


def test_glossario_ignora_linha_incompleta() -> None:
    """Arquivo editado à mão não derruba a verificação por uma linha torta."""
    lido = ler_glossario("| só uma coluna |\n| a | b |\n| | canônico | x |\n")

    assert lido.conceitos == {}


# --- Eixos --------------------------------------------------------------------


def test_eixos_na_ordem_documentada(glossario: Glossario) -> None:
    extraidos = canonizar_termos(
        termos(
            condicao="depression",
            intervencao="alcohol consumption",
            desfecho="brain atrophy",
            populacao="older adults",
        ),
        glossario,
    )

    assert montar_buscas(extraidos, glossario) == [
        ("completo", "depression alcohol consumption brain atrophy"),
        ("nucleo", "alcohol consumption brain atrophy"),
        ("sinonimo", "alcohol intake brain atrophy"),
        ("condicao_intervencao", "depression alcohol consumption"),
        ("condicao_desfecho", "depression brain atrophy"),
        ("populacao", "alcohol consumption brain atrophy older adults"),
    ]


def test_dois_campos_entre_os_tres_ja_produzem_busca(glossario: Glossario) -> None:
    """Os eixos de par esgotam as três combinações; é o piso da cobertura."""
    pares = (
        ("intervencao", "desfecho"),
        ("condicao", "intervencao"),
        ("condicao", "desfecho"),
    )

    for primeiro, segundo in pares:
        extraidos = canonizar_termos(
            termos(**{primeiro: "polylaminin", segundo: "spinal cord"}), glossario
        )
        assert montar_buscas(extraidos, glossario), (primeiro, segundo)


def test_um_campo_sozinho_nao_produz_busca(glossario: Glossario) -> None:
    extraidos = canonizar_termos(termos(condicao="breast cancer"), glossario)

    assert montar_buscas(extraidos, glossario) == []


def test_eixo_de_sinonimo_sai_de_cena_sem_variante_no_glossario(
    glossario: Glossario,
) -> None:
    extraidos = canonizar_termos(
        termos(intervencao="polylaminin", desfecho="spinal cord"), glossario
    )

    assert [eixo for eixo, _busca in montar_buscas(extraidos, glossario)] == ["nucleo"]


def test_eixo_de_sinonimo_cai_no_desfecho_quando_a_intervencao_nao_tem_variante(
    glossario: Glossario,
) -> None:
    extraidos = canonizar_termos(
        termos(intervencao="polylaminin", desfecho="brain shrinkage"), glossario
    )

    assert montar_buscas(extraidos, glossario) == [
        ("nucleo", "polylaminin brain atrophy"),
        ("sinonimo", "polylaminin brain shrinkage"),
    ]


def test_palavra_repetida_entre_campos_entra_uma_vez(glossario: Glossario) -> None:
    extraidos = canonizar_termos(
        termos(condicao="malaria", intervencao="malaria vaccine", desfecho="mortality"),
        glossario,
    )
    montadas = dict(montar_buscas(extraidos, glossario))

    assert montadas["completo"] == "malaria vaccine mortality"


def test_eixos_com_o_mesmo_conjunto_de_palavras_valem_como_um(
    glossario: Glossario,
) -> None:
    """`completo` e `nucleo` dão o mesmo conjunto quando falta a condição."""
    extraidos = canonizar_termos(
        termos(intervencao="alcohol consumption", desfecho="brain atrophy"), glossario
    )

    assert [eixo for eixo, _ in montar_buscas(extraidos, glossario)] == [
        "nucleo",
        "sinonimo",
    ]


def test_busca_de_uma_palavra_e_descartada(glossario: Glossario) -> None:
    """Condição e desfecho no mesmo termo canônico dariam "depression" sozinho."""
    extraidos = canonizar_termos(
        termos(condicao="depression", desfecho="depression"), glossario
    )

    assert montar_buscas(extraidos, glossario) == []


# --- O agente -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_o_mesmo_trecho_e_os_mesmos_termos_dao_sempre_a_mesma_lista(
    glossario, sem_espera
) -> None:
    """O caso que motivou o desenho: duas chamadas iguais, listas iguais.

    O dublê devolve as mesmas duas respostas com os campos em outra ordem e com
    outra grafia — é o tipo de diferença que o modelo produz entre chamadas, e
    que não deve mais chegar à OpenAlex.
    """
    primeira = {
        "intervencao": "Alcohol consumption",
        "desfecho": "brain atrophy",
        "condicao": "",
        "populacao": "",
    }
    segunda = {
        "desfecho": "Brain Shrinkage,",
        "intervencao": "alcohol intake",
        "populacao": "",
        "condicao": "",
    }
    triador = agente(primeira, segunda, glossario=glossario, sem_espera=sem_espera)

    assert await triador.extrair_buscas(TRECHO) == await triador.extrair_buscas(TRECHO)


@pytest.mark.asyncio
async def test_o_trecho_original_vem_sempre_na_frente(glossario, sem_espera) -> None:
    triador = agente(
        {
            "intervencao": "alcohol consumption",
            "desfecho": "brain atrophy",
            "condicao": "",
            "populacao": "",
        },
        glossario=glossario,
        sem_espera=sem_espera,
    )

    assert await triador.extrair_buscas(TRECHO) == [
        TRECHO,
        "alcohol consumption brain atrophy",
        "alcohol intake brain atrophy",
    ]


@pytest.mark.asyncio
async def test_respeita_o_limite_configuravel_de_variacoes(
    glossario, sem_espera
) -> None:
    resposta = {
        "condicao": "depression",
        "intervencao": "alcohol consumption",
        "desfecho": "brain atrophy",
        "populacao": "older adults",
    }
    triador = agente(
        resposta, glossario=glossario, sem_espera=sem_espera, max_variacoes=2
    )

    buscas = await triador.extrair_buscas(TRECHO)

    assert buscas == [
        TRECHO,
        "depression alcohol consumption brain atrophy",
        "alcohol consumption brain atrophy",
    ]


@pytest.mark.asyncio
async def test_descarta_busca_acima_do_tamanho_maximo(glossario, sem_espera) -> None:
    resposta = {
        "intervencao": "a" * 150,
        "desfecho": "b" * 150,
        "condicao": "",
        "populacao": "",
    }
    triador = agente(
        resposta,
        glossario=glossario,
        sem_espera=sem_espera,
        max_tamanho_variacao=200,
    )

    assert await triador.extrair_buscas(TRECHO) == [TRECHO]


@pytest.mark.asyncio
async def test_degrada_se_a_saida_esta_fora_do_formato(glossario, sem_espera) -> None:
    triador = agente(
        '{"chave_errada": ["A", "B"]}', glossario=glossario, sem_espera=sem_espera
    )

    assert await triador.extrair_buscas(TRECHO) == [TRECHO]


@pytest.mark.asyncio
async def test_degrada_se_o_llm_esta_indisponivel(glossario, sem_espera) -> None:
    cliente = ClienteLLM(
        DubleLLM(FalhaTransitoria("503")), dormir=sem_espera, max_tentativas=1
    )
    triador = AgenteTriador(cliente, glossario=glossario)

    assert await triador.extrair_buscas(TRECHO) == [TRECHO]


@pytest.mark.asyncio
async def test_degrada_se_o_trecho_nao_rende_dois_termos(glossario, sem_espera) -> None:
    resposta = {
        "condicao": "breast cancer",
        "intervencao": "",
        "desfecho": "",
        "populacao": "",
    }
    triador = agente(resposta, glossario=glossario, sem_espera=sem_espera)

    assert await triador.extrair_buscas(TRECHO) == [TRECHO]


@pytest.mark.asyncio
async def test_nao_levanta_excecao_com_trecho_valido(glossario, sem_espera) -> None:
    triador = agente(
        Exception("erro catastrófico do LLM"),
        glossario=glossario,
        sem_espera=sem_espera,
    )

    try:
        assert await triador.extrair_buscas(TRECHO) == [TRECHO]
    except Exception as erro:  # pragma: no cover - é o que o teste proíbe
        pytest.fail(f"levantou exceção não tratada: {erro}")


@pytest.mark.asyncio
async def test_trecho_vazio_nao_gasta_chamada(glossario, sem_espera) -> None:
    duble = DubleLLM(
        {"intervencao": "x", "desfecho": "y", "condicao": "", "populacao": ""}
    )
    triador = AgenteTriador(ClienteLLM(duble, dormir=sem_espera), glossario=glossario)

    assert await triador.extrair_buscas("") == []
    assert await triador.extrair_buscas("   ") == []
    assert duble.chamadas == []


# --- Conceitos para o campo `termos` do veredito --------------------------------


@pytest.mark.asyncio
async def test_extrair_devolve_buscas_e_conceitos_na_ordem_de_leitura(
    glossario, sem_espera
) -> None:
    triador = agente(
        {
            "condicao": "Depression",
            "intervencao": "alcohol intake",
            "desfecho": "brain shrinkage",
            "populacao": "older adults",
        },
        glossario=glossario,
        sem_espera=sem_espera,
    )

    extracao = await triador.extrair(TRECHO)

    # Glossário aplicado: as variantes viram o termo canônico.
    assert extracao.conceitos == [
        "alcohol consumption",
        "brain atrophy",
        "depression",
        "older adults",
    ]
    assert extracao.buscas[0] == TRECHO


@pytest.mark.asyncio
async def test_conceitos_sem_vazios_e_sem_repeticao(glossario, sem_espera) -> None:
    triador = agente(
        {
            "intervencao": "malaria",
            "desfecho": "",
            "condicao": "malaria",
            "populacao": "children",
        },
        glossario=glossario,
        sem_espera=sem_espera,
    )

    assert (await triador.extrair(TRECHO)).conceitos == ["malaria", "children"]


@pytest.mark.asyncio
async def test_extrair_buscas_e_as_buscas_de_extrair(glossario, sem_espera) -> None:
    resposta = {
        "intervencao": "alcohol consumption",
        "desfecho": "brain atrophy",
        "condicao": "",
        "populacao": "",
    }
    um = agente(resposta, glossario=glossario, sem_espera=sem_espera)
    outro = agente(resposta, glossario=glossario, sem_espera=sem_espera)

    assert (await um.extrair(TRECHO)).buscas == await outro.extrair_buscas(TRECHO)


@pytest.mark.asyncio
async def test_llm_falhando_devolve_trecho_e_nenhum_conceito(
    glossario, sem_espera
) -> None:
    cliente = ClienteLLM(
        DubleLLM(FalhaTransitoria("503")), dormir=sem_espera, max_tentativas=1
    )
    triador = AgenteTriador(cliente, glossario=glossario)

    extracao = await triador.extrair(TRECHO)

    assert extracao.buscas == [TRECHO]
    assert extracao.conceitos == []


# --- O prompt -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_o_prompt_leva_as_orientacoes_o_glossario_e_o_trecho(
    glossario, sem_espera
) -> None:
    """As instruções vêm do arquivo versionado, e não de uma f-string."""
    duble = DubleLLM(
        {"intervencao": "a", "desfecho": "b", "condicao": "", "populacao": ""}
    )
    triador = AgenteTriador(ClienteLLM(duble, dormir=sem_espera), glossario=glossario)

    await triador.extrair_buscas(TRECHO)

    prompt = duble.chamadas[0]["prompt"]
    assert "# Variador semântico do Triador" in prompt
    assert "## Regras de extração" in prompt
    assert "consumo de álcool → alcohol consumption" in prompt
    assert prompt.rstrip().endswith(TRECHO)
    # A coluna de variantes e o procedimento de manutenção não vão ao modelo.
    assert "Como acrescentar uma linha" not in prompt


def test_o_prompt_nao_leva_o_cabecalho_de_metadados() -> None:
    documento = orientacoes.ler("triador/ORIENTACOES.md")

    assert documento.versao == documento.metadados["versao"]
    assert not documento.corpo.startswith("---")
    assert "description:" not in documento.corpo.splitlines()[0]


def test_o_prompt_nao_leva_os_blocos_internos() -> None:
    """A prosa de manutenção fica no arquivo e fora da chamada.

    No plano gratuito a janela é de 8 mil tokens por minuto para as duas
    chamadas da verificação: o que viaja em toda chamada sem mudar a resposta
    sai do orçamento da verificação seguinte.
    """
    documento = orientacoes.ler("triador/ORIENTACOES.md")

    assert "Por que o trabalho é partido assim" in documento.corpo
    assert "Por que o trabalho é partido assim" not in documento.prompt
    assert "## Referências" in documento.corpo
    assert "## Referências" not in documento.prompt
    # As regras continuam todas lá.
    assert "## Regras de extração" in documento.prompt
    assert "## O erro inaceitável" in documento.prompt
    assert ABERTURA_INTERNA not in documento.prompt
    assert len(documento.prompt) < len(documento.corpo)


def test_os_exemplos_fora_do_prompt_ficam_no_arquivo() -> None:
    """Decisão reversível: o exemplo retirado fica documentado com o motivo."""
    documento = orientacoes.ler("triador/referencias/exemplos.md")

    assert "Oxycontin" in documento.corpo
    assert "Oxycontin" not in documento.prompt
    assert "O par que sustenta a busca" in documento.prompt


# --- O arquivo de verdade -----------------------------------------------------


def test_o_glossario_versionado_tem_conteudo_e_esta_em_forma_canonica() -> None:
    real = glossario_padrao()

    assert len(real.conceitos) >= 20
    for conceito, canonico in real.conceitos.items():
        assert conceito == forma_canonica(conceito)
        assert canonico == forma_canonica(canonico)
    for canonico, variantes in real.variantes.items():
        assert canonico not in variantes, "variante igual ao canônico não varia nada"


def test_os_eixos_documentados_sao_os_eixos_do_codigo() -> None:
    """Documento e código não divergem em silêncio: a tabela lista os `id`."""
    documentados = orientacoes.ler("triador/referencias/formatos-de-busca.md").corpo

    for eixo in EIXOS:
        assert f"`{eixo.id}`" in documentados, f"eixo {eixo.id} não documentado"
    assert documentados.count("| :-- | :--- | :--- | :--- |") == 1
