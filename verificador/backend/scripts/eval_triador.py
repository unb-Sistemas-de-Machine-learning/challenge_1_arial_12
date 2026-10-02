"""Roda o eval set do Triador contra a OpenAlex de verdade.

Duas perguntas, e não uma:

1. **Acerto** — alguma das buscas geradas recupera o estudo rotulado? É a meta
   da spec 003: ≥ 80% dos casos.
2. **Estabilidade** — rodar o mesmo caso de novo gera a mesma lista de buscas?
   Essa pergunta existe porque o defeito que motivou as orientações do variador
   semântico não aparece numa rodada só: o caso acertava numa tentativa e errava
   na seguinte, e a média de uma rodada escondia isso.

    python scripts/eval_triador.py                 # uma rodada por caso
    python scripts/eval_triador.py --repeticoes 3   # mede a estabilidade

Precisa de LLM_API_KEY e OPENALEX_MAILTO no .env, e gasta uma chamada de LLM e
uma de OpenAlex por busca a cada repetição. Não roda na CI.
"""

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Adiciona o diretório backend ao sys.path para permitir import do src
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents import orientacoes
from src.agents.triador import ARQUIVO_DE_ORIENTACOES, AgenteTriador
from src.services.llm import ClienteLLM
from src.services.openalex import ClienteOpenAlex

logging.basicConfig(level=logging.WARNING)

META_DE_ACERTO = 80.0


@dataclass
class Resultado:
    """O que uma rodada de um caso produziu."""

    trecho: str
    id_esperado: str
    buscas: list[tuple[str, ...]] = field(default_factory=list)
    acertos: list[bool] = field(default_factory=list)

    @property
    def estavel(self) -> bool:
        """Todas as rodadas geraram exatamente a mesma lista de buscas."""
        return len(set(self.buscas)) <= 1

    @property
    def consistente(self) -> bool:
        """Todas as rodadas chegaram ao mesmo veredicto, acerto ou erro."""
        return len(set(self.acertos)) <= 1


def ler_casos(caminho: Path) -> list[dict]:
    casos = []
    # utf-8-sig: o arquivo foi salvo com BOM, e sem isso a primeira chave vem
    # com um caractere invisível na frente.
    with open(caminho, encoding="utf-8-sig") as arquivo:
        for linha in arquivo:
            if linha.strip():
                casos.append(json.loads(linha))
    return casos


async def rodar_caso(
    agente: AgenteTriador,
    cliente_oa: ClienteOpenAlex,
    resultado: Resultado,
    numero: int,
) -> None:
    buscas = await agente.extrair_buscas(resultado.trecho)
    resultado.buscas.append(tuple(buscas))

    try:
        encontrados = await cliente_oa.buscar_varias(buscas)
    except Exception as erro:  # a busca é a dependência externa do teste
        resultado.acertos.append(False)
        print(f"  rodada {numero}  ❌  erro na busca: {erro}")
        return

    ids = [trabalho.id for trabalho in encontrados.trabalhos if trabalho.id]
    acertou = resultado.id_esperado in ids
    resultado.acertos.append(acertou)

    marca = "✅" if acertou else "❌"
    repetidas = (
        len(resultado.buscas) > 1 and resultado.buscas[-1] == resultado.buscas[0]
    )
    detalhe = (
        "(mesmas buscas)" if repetidas else " | ".join(buscas[1:]) or "(sem variação)"
    )
    print(f"  rodada {numero}  {marca}  {detalhe}")


async def rodar_eval(repeticoes: int, limite: int | None) -> int:
    backend = Path(__file__).resolve().parent.parent
    caminho = backend / "evals" / "triador.jsonl"
    if not caminho.exists():
        print(f"Arquivo não encontrado: {caminho}")
        return 1

    casos = ler_casos(caminho)[:limite]
    if not casos:
        print("Nenhum caso encontrado no arquivo.")
        return 1

    try:
        cliente_llm = ClienteLLM.a_partir_das_configuracoes()
        cliente_oa = ClienteOpenAlex.a_partir_das_configuracoes()
    except ValueError as erro:
        print(f"Erro de configuração: {erro}")
        return 1

    agente = AgenteTriador(cliente_llm)
    versao = orientacoes.ler(ARQUIVO_DE_ORIENTACOES).versao
    print(
        f"Eval do Triador — orientações v{versao}, {len(casos)} caso(s), "
        f"{repeticoes} repetição(ões)\n"
    )

    resultados: list[Resultado] = []
    try:
        for indice, caso in enumerate(casos, start=1):
            resultado = Resultado(
                trecho=caso["trecho"], id_esperado=caso["id_esperado"]
            )
            print(f"[{indice:02d}] {resultado.trecho}")
            print(f"     esperado {resultado.id_esperado}")
            for numero in range(1, repeticoes + 1):
                await rodar_caso(agente, cliente_oa, resultado, numero)
            resultados.append(resultado)
            print()
    finally:
        await cliente_llm.fechar()
        await cliente_oa.fechar()

    return relatorio(resultados, repeticoes)


def relatorio(resultados: list[Resultado], repeticoes: int) -> int:
    total = len(resultados)
    rodadas = total * repeticoes
    acertos = sum(sum(resultado.acertos) for resultado in resultados)
    taxa = acertos / rodadas * 100 if rodadas else 0.0
    estaveis = sum(resultado.estavel for resultado in resultados)
    oscilaram = [resultado for resultado in resultados if not resultado.consistente]

    print(
        f"Acerto: {acertos}/{rodadas} rodadas ({taxa:.1f}%), meta ≥ {META_DE_ACERTO:g}%"
    )
    if repeticoes > 1:
        print(
            f"Estabilidade: {estaveis}/{total} casos geraram a mesma lista de "
            f"buscas nas {repeticoes} rodadas ({estaveis / total * 100:.1f}%)"
        )
        if oscilaram:
            # É o defeito original: o mesmo trecho achando e não achando. Cada
            # caso aqui é candidato a uma linha nova no glossário.
            print(
                f"\n{len(oscilaram)} caso(s) acertaram em uma rodada e erraram em outra:"
            )
            for resultado in oscilaram:
                print(f"  - {resultado.trecho}")
                for buscas in dict.fromkeys(resultado.buscas):
                    print(f"      {' | '.join(buscas[1:])}")

    if taxa < META_DE_ACERTO:
        print("\n⚠️  Abaixo da meta de acerto.")
        return 1
    return 0


def main() -> int:
    # No Windows a saída padrão vem em cp1252 e estoura no primeiro ✅. O script
    # é de linha de comando e não vale perder a rodada inteira por isso.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    analisador = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    analisador.add_argument(
        "--repeticoes",
        type=int,
        default=1,
        help="quantas vezes rodar cada caso; mais de uma mede a estabilidade",
    )
    analisador.add_argument(
        "--limite",
        type=int,
        default=None,
        help="roda só os N primeiros casos, para um teste rápido",
    )
    argumentos = analisador.parse_args()
    return asyncio.run(rodar_eval(max(1, argumentos.repeticoes), argumentos.limite))


if __name__ == "__main__":
    sys.exit(main())
