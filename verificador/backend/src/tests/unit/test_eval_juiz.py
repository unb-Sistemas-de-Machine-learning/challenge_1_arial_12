"""Integridade do conjunto rotulado e das métricas, sem API de LLM."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.eval_juiz import (
    CAMINHO_PADRAO,
    Caso,
    Resultado,
    ler_casos,
    metricas,
    motivo_seguro,
    relatorio,
    rodar,
    selecionar_casos,
)
from src.agents.juiz import RespostaDoJuiz
from src.api.schemas.verificacao import Estado, Estudo, Veredito
from src.services.llm import (
    DiagnosticoDeLimite,
    FalhaTransitoria,
    LLMIndisponivel,
    RespostaInvalidaDoLLM,
)


def test_dataset_tem_quarenta_casos_equilibrados_e_identificados() -> None:
    casos = ler_casos(CAMINHO_PADRAO)
    contagens = [
        sum(caso.estado_esperado == estado for caso in casos) for estado in Estado
    ]

    assert len(casos) == 40
    assert sorted(contagens) == [13, 13, 14]
    assert any(not caso.trabalhos for caso in casos)
    assert any(caso.trabalhos and not caso.relacionados for caso in casos)
    assert any(any(estudo.retratado for estudo in caso.trabalhos) for caso in casos)


def test_dataset_rejeita_arquivo_incompleto(tmp_path: Path) -> None:
    arquivo = tmp_path / "incompleto.jsonl"
    arquivo.write_text('{"id":"A"}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="linha 1 inválida"):
        ler_casos(arquivo)


def test_seleciona_casos_sem_repetir_e_rejeita_id_desconhecido() -> None:
    casos = ler_casos(CAMINHO_PADRAO)

    assert [caso.id for caso in selecionar_casos(casos, ["S03", "S02", "S03"])] == [
        "S03",
        "S02",
    ]
    with pytest.raises(ValueError, match="S99"):
        selecionar_casos(casos, ["S99"])


def test_motivo_seguro_mostra_campo_do_schema_sem_conteudo_do_modelo() -> None:
    try:
        RespostaDoJuiz.model_validate(
            {
                "relacao": "compativel",
                "estado": "inexistente",
                "doi": None,
                "evidencia": None,
                "justificativa": "Justificativa válida e suficientemente longa.",
            }
        )
    except ValueError as validacao:
        try:
            raise RespostaInvalidaDoLLM("resposta fora do schema") from validacao
        except RespostaInvalidaDoLLM as erro:
            motivo = motivo_seguro(erro)

    assert motivo == "schema inválido (estado: enum)"


def test_motivo_seguro_nao_imprime_texto_arbitrario() -> None:
    erro = RespostaInvalidaDoLLM("segredo-do-modelo")
    assert motivo_seguro(erro) == "resposta fora do formato esperado"


def test_motivo_seguro_distingue_limite_do_provedor() -> None:
    try:
        raise LLMIndisponivel("não ecoar") from FalhaTransitoria(
            "limite de uso do groq atingido (429)",
            retry_after=7.5,
            diagnostico_limite=DiagnosticoDeLimite(
                tipo="TPM",
                requisicoes_restantes_dia=93,
                tokens_restantes_minuto=0,
                reinicio_tokens="7.66s",
            ),
        )
    except LLMIndisponivel as erro:
        motivo = motivo_seguro(erro)
        assert "tipo=TPM" in motivo
        assert "tokens restantes no minuto=0" in motivo
        assert "Retry-After=7.5s" in motivo


@pytest.mark.asyncio
async def test_runner_para_no_primeiro_429_sem_chamar_casos_seguintes(
    monkeypatch, capsys
) -> None:
    casos = ler_casos(CAMINHO_PADRAO)[:2]
    chamadas: list[str] = []

    class ClienteFalso:
        provedor = SimpleNamespace(nome="duble")

        async def fechar(self) -> None:
            pass

    class JuizFalso:
        async def julgar(self, trecho, trabalhos):
            chamadas.append(trecho)
            raise LLMIndisponivel("não ecoar") from FalhaTransitoria(
                "limite de uso do groq atingido (429)", retry_after=10
            )

    monkeypatch.setattr(
        "scripts.eval_juiz.ClienteLLM.a_partir_das_configuracoes", ClienteFalso
    )
    monkeypatch.setattr("scripts.eval_juiz.AgenteJuiz", lambda _cliente: JuizFalso())

    assert await rodar(casos, completo=True) == 1
    assert chamadas == [casos[0].trecho]
    saida = capsys.readouterr().out
    assert "Retry-After=10s" in saida
    assert "casos seguintes não foram executados" in saida
    assert "Acerto parcial" in saida


@pytest.mark.asyncio
async def test_runner_mostra_justificativa_validada_so_quando_solicitada(
    monkeypatch, capsys
) -> None:
    caso = next(caso for caso in ler_casos(CAMINHO_PADRAO) if caso.id == "E02")

    class ClienteFalso:
        provedor = SimpleNamespace(nome="duble")

        async def fechar(self) -> None:
            pass

    class JuizFalso:
        async def julgar(self, trecho, trabalhos):
            return Veredito(
                estado=Estado.EXAGERA,
                estudo=Estudo(titulo="Teste", ano=None, doi=None, retratado=False),
                termos=[],
                justificativa="A alegação amplia o alcance do resultado.",
            )

    monkeypatch.setattr(
        "scripts.eval_juiz.ClienteLLM.a_partir_das_configuracoes", ClienteFalso
    )
    monkeypatch.setattr("scripts.eval_juiz.AgenteJuiz", lambda _cliente: JuizFalso())

    assert await rodar([caso], completo=False, mostrar_justificativa=True) == 0
    saida = capsys.readouterr().out
    assert 'justificativa: "A alegação amplia o alcance do resultado."' in saida


def test_metricas_contam_erros_inaceitaveis_separadamente() -> None:
    caso = Caso(
        id="N",
        trecho="Alegação sem fonte relacionada",
        estado_esperado=Estado.NADA_ENCONTRADO,
        relacionados=frozenset(),
        trabalhos=(),
    )
    veredito = Veredito(
        estado=Estado.SUSTENTA,
        estudo=Estudo(titulo="Retratado", ano=2020, doi="10.0000/x", retratado=True),
        termos=[],
        justificativa="Justificativa de teste",
    )

    assert metricas([Resultado(caso, veredito)]) == (0.0, 1, 1, 0)
    assert metricas([Resultado(caso, None, "LLMTempoEsgotado")]) == (
        0.0,
        0,
        0,
        1,
    )


def test_relatorio_parcial_nao_apresenta_meta_como_atingida(capsys) -> None:
    caso = ler_casos(CAMINHO_PADRAO)[0]
    veredito = Veredito(
        estado=Estado.SUSTENTA,
        estudo=Estudo(titulo="Teste", ano=None, doi=None, retratado=False),
        termos=[],
        justificativa="Justificativa de teste",
    )

    assert relatorio([Resultado(caso, veredito)], completo=False) == 0
    saida = capsys.readouterr().out
    assert "Acerto parcial" in saida
    assert "não mede a meta de aceite" in saida
