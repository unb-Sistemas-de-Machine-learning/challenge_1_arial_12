import asyncio
import logging
import sys
from pathlib import Path

# Adiciona o diretório backend ao sys.path para permitir import do src
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents.triador import AgenteTriador
from src.services.llm import ClienteLLM
from src.services.openalex import ClienteOpenAlex

logging.basicConfig(level=logging.WARNING)


async def testar_trecho(trecho: str):
    print(f"\nTrecho de entrada: '{trecho}'\n")
    try:
        cliente_llm = ClienteLLM.a_partir_das_configuracoes()
        cliente_oa = ClienteOpenAlex.a_partir_das_configuracoes()
    except ValueError as erro:
        print(f"Erro de configuração: {erro}")
        sys.exit(1)

    agente = AgenteTriador(cliente_llm)

    try:
        # Passo 1: Extrair variações de busca usando o LLM
        print("Gerando variações pelo LLM (Groq)...")
        buscas = await agente.extrair_buscas(trecho)
        print("Variações geradas:")
        for b in buscas:
            print(f" - {b}")

        # Passo 2: Testar a busca na OpenAlex com as variações
        print("\nBuscando na OpenAlex...")
        resultado = await cliente_oa.buscar_varias(buscas)

        print(f"\nEncontrados {len(resultado.trabalhos)} trabalhos no total.")
        for trab in resultado.trabalhos:
            print(
                f"[{trab.id}] {trab.titulo} (Ano: {trab.ano}, Citações: {trab.citacoes})"
            )
            print(f" -> DOI: {trab.doi}")

    except Exception as e:
        print(f"\n❌ Erro durante o teste: {e}")
    finally:
        await cliente_llm.fechar()
        await cliente_oa.fechar()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Uso: python testar_trecho.py "Seu trecho aqui"')
        sys.exit(1)

    texto = sys.argv[1]
    asyncio.run(testar_trecho(texto))
