import asyncio
import json
import logging
import sys
from pathlib import Path

# Adiciona o diretório backend ao sys.path para permitir import do src
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents.triador import AgenteTriador
from src.services.llm import ClienteLLM
from src.services.openalex import ClienteOpenAlex

logging.basicConfig(level=logging.WARNING)


async def rodar_eval():
    backend_dir = Path(__file__).resolve().parent.parent
    caminho_eval = backend_dir / "evals" / "triador.jsonl"
    if not caminho_eval.exists():
        print(f"Arquivo não encontrado: {caminho_eval}")
        sys.exit(1)

    casos = []
    with open(caminho_eval, "r", encoding="utf-8-sig") as f:
        for linha in f:
            linha = linha.strip()
            if not linha:
                continue
            casos.append(json.loads(linha))

    if not casos:
        print("Nenhum caso encontrado no arquivo.")
        sys.exit(1)

    print(f"Rodando eval para {len(casos)} casos...")

    try:
        cliente_llm = ClienteLLM.a_partir_das_configuracoes()
        cliente_oa = ClienteOpenAlex.a_partir_das_configuracoes()
    except ValueError as erro:
        print(f"Erro de configuração: {erro}")
        sys.exit(1)

    agente = AgenteTriador(cliente_llm)

    acertos = 0
    total = 0

    for caso in casos:
        trecho = caso["trecho"]
        id_esperado = caso["id_esperado"]

        print(f"\nCaso: {trecho}")
        print(f"Esperado: {id_esperado}")

        try:
            buscas = await agente.extrair_buscas(trecho)
            print(f"Variações geradas: {buscas}")

            # Buscando na openalex
            resultado = await cliente_oa.buscar_varias(buscas)
            ids_retornados = [trab.id for trab in resultado.trabalhos if trab.id]

            if id_esperado in ids_retornados:
                print("✅ ACERTO")
                acertos += 1
            else:
                print("❌ ERRO")

        except Exception as e:
            print(f"❌ ERRO na execução: {e}")

        total += 1

    taxa = (acertos / total) * 100 if total > 0 else 0
    print(f"\nResultado Final: {acertos}/{total} acertos ({taxa:.1f}%)")

    await cliente_llm.fechar()
    await cliente_oa.fechar()

    if taxa < 80.0:
        print("⚠️  Atenção: A taxa de acerto está abaixo da meta de 80%.")


if __name__ == "__main__":
    asyncio.run(rodar_eval())
