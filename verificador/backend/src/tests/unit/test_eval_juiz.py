"""Integridade do conjunto rotulado e das métricas, sem API de LLM."""

from pathlib import Path

import pytest

from scripts.eval_juiz import CAMINHO_PADRAO, Caso, Resultado, ler_casos, metricas
from src.api.schemas.verificacao import Estado, Estudo, Veredito


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
