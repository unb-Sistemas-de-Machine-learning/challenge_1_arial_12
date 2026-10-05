"""Avalia o Juiz em 40 casos rotulados (sintéticos, não evidência científica).

    python scripts/eval_juiz.py --validar-dataset  # sem chave, sem rede
    python scripts/eval_juiz.py                    # exige LLM_API_KEY e DATABASE_URL

O modo real usa o provedor configurado no .env e faz chamadas pagas ou sujeitas
a quota. Não roda na CI. A meta não é considerada atingida sem esta rodada.
"""

import argparse
import asyncio
import json
import logging
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents import orientacoes
from src.agents.juiz import ARQUIVO_DE_ORIENTACOES, AgenteJuiz, normalizar_doi
from src.api.schemas.busca import TrabalhoEncontrado
from src.api.schemas.verificacao import Estado, Veredito
from src.services.llm import ClienteLLM, ErroLLM

logging.basicConfig(level=logging.WARNING)

CAMINHO_PADRAO = Path(__file__).resolve().parent.parent / "evals" / "juiz.jsonl"
MINIMO_CASOS = 40
META_ACERTO = 80.0


@dataclass(frozen=True)
class Caso:
    id: str
    trecho: str
    estado_esperado: Estado
    relacionados: frozenset[str]
    trabalhos: tuple[TrabalhoEncontrado, ...]


@dataclass(frozen=True)
class Resultado:
    caso: Caso
    veredito: Veredito | None
    erro: str | None = None


def ler_casos(caminho: Path) -> list[Caso]:
    """Falha antes de chamar o LLM se o dataset for incompleto ou malformado."""
    casos: list[Caso] = []
    ids: set[str] = set()
    for numero, linha in enumerate(caminho.read_text(encoding="utf-8").splitlines(), 1):
        if not linha.strip():
            continue
        try:
            bruto = json.loads(linha)
            if bruto["origem"] != "sintetico":
                raise ValueError("origem deve declarar 'sintetico'")
            if not bruto["id"] or bruto["id"] in ids:
                raise ValueError("id vazio ou repetido")
            if not bruto["trecho"].strip():
                raise ValueError("trecho vazio")
            estado = Estado(bruto["estado_esperado"])
            trabalhos = tuple(
                TrabalhoEncontrado.model_validate(
                    {
                        "id": item.get("id"),
                        "titulo": item["titulo"],
                        "ano": item.get("ano"),
                        "doi": item.get("doi"),
                        "retratado": item.get("retratado", False),
                        "abstract": item.get("abstract"),
                        "relevancia": None,
                        "citacoes": None,
                    }
                )
                for item in bruto["trabalhos"]
            )
            disponiveis = {normalizar_doi(item.doi) for item in trabalhos}
            relacionados = frozenset(map(normalizar_doi, bruto["relacionados"]))
            if not relacionados <= disponiveis:
                raise ValueError("DOI relacionado ausente dos trabalhos")
            if estado != Estado.NADA_ENCONTRADO and not relacionados:
                raise ValueError("estado com fonte precisa de DOI relacionado")
            if not all(item.doi and item.abstract for item in trabalhos):
                raise ValueError("trabalho sem DOI ou abstract")
        except (KeyError, TypeError, ValueError) as erro:
            raise ValueError(f"linha {numero} inválida: {erro}") from erro

        ids.add(bruto["id"])
        casos.append(
            Caso(
                id=bruto["id"],
                trecho=bruto["trecho"],
                estado_esperado=estado,
                relacionados=relacionados,
                trabalhos=trabalhos,
            )
        )

    contagem = Counter(caso.estado_esperado for caso in casos)
    if len(casos) < MINIMO_CASOS:
        raise ValueError(f"dataset precisa de pelo menos {MINIMO_CASOS} casos")
    if (
        set(contagem) != set(Estado)
        or max(contagem.values()) - min(contagem.values()) > 1
    ):
        raise ValueError("os três estados precisam estar equilibrados")
    return casos


def metricas(resultados: list[Resultado]) -> tuple[float, int, int, int]:
    """Acerto, falso sustenta sem relacionado, sustenta retratado, falhas."""
    total = len(resultados)
    acertos = sum(
        resultado.veredito is not None
        and resultado.veredito.estado == resultado.caso.estado_esperado
        for resultado in resultados
    )
    sem_relacao = sum(
        resultado.veredito is not None
        and resultado.veredito.estado == Estado.SUSTENTA
        and not resultado.caso.relacionados
        for resultado in resultados
    )
    retratados = sum(
        resultado.veredito is not None
        and resultado.veredito.estado == Estado.SUSTENTA
        and resultado.veredito.estudo is not None
        and resultado.veredito.estudo.retratado
        for resultado in resultados
    )
    falhas = sum(resultado.erro is not None for resultado in resultados)
    return (100.0 * acertos / total if total else 0.0, sem_relacao, retratados, falhas)


async def rodar(casos: list[Caso]) -> int:
    try:
        cliente = ClienteLLM.a_partir_das_configuracoes()
    except ValueError as erro:
        print(f"Configuração incompleta para avaliação real: {erro}")
        return 2

    agente = AgenteJuiz(cliente)
    versao = orientacoes.ler(ARQUIVO_DE_ORIENTACOES).versao
    print(
        f"Juiz v{versao}: {len(casos)} casos sintéticos; provedor={cliente.provedor.nome}"
    )
    resultados: list[Resultado] = []
    try:
        for caso in casos:
            try:
                veredito = await agente.julgar(caso.trecho, caso.trabalhos)
            except ErroLLM as erro:
                resultados.append(Resultado(caso, None, type(erro).__name__))
                print(f"{caso.id}: falha {type(erro).__name__}")
            else:
                resultados.append(Resultado(caso, veredito))
                acerto = "ok" if veredito.estado == caso.estado_esperado else "erro"
                print(f"{caso.id}: {veredito.estado.value} ({acerto})")
    finally:
        await cliente.fechar()

    acerto, sem_relacao, retratado, falhas = metricas(resultados)
    print(f"Acerto do estado: {acerto:.1f}% (meta >= {META_ACERTO:g}%)")
    print(f"Falsos sustenta sem abstract relacionado: {sem_relacao} (meta 0)")
    print(f"Sustenta com estudo retratado: {retratado} (meta 0)")
    print(f"Falhas de chamada/validação: {falhas}")
    return int(acerto < META_ACERTO or sem_relacao > 0 or retratado > 0 or falhas > 0)


def main() -> int:
    # O terminal do Windows pode vir em cp1252; preserve os acentos do relatório.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validar-dataset", action="store_true")
    parser.add_argument("--arquivo", type=Path, default=CAMINHO_PADRAO)
    argumentos = parser.parse_args()
    try:
        casos = ler_casos(argumentos.arquivo)
    except (OSError, ValueError) as erro:
        print(f"Dataset inválido: {erro}")
        return 2

    contagem = Counter(caso.estado_esperado.value for caso in casos)
    print(f"Dataset válido: {len(casos)} casos; {dict(contagem)}")
    if argumentos.validar_dataset:
        print(
            "Métricas de acerto não medidas: execute sem --validar-dataset com LLM real."
        )
        return 0
    return asyncio.run(rodar(casos))


if __name__ == "__main__":
    sys.exit(main())
