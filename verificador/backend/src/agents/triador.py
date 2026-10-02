import logging

from pydantic import BaseModel, Field

from src.services.llm import ClienteLLM, ErroLLM

logger = logging.getLogger("verificador.agentes.triador")


class Variacoes(BaseModel):
    buscas: list[str] = Field(
        description="Lista de buscas em inglês com termos técnicos equivalentes"
    )


class AgenteTriador:
    def __init__(
        self,
        cliente_llm: ClienteLLM,
        max_variacoes: int = 5,
        max_tamanho_variacao: int = 200,
    ):
        self.cliente_llm = cliente_llm
        self.max_variacoes = max_variacoes
        self.max_tamanho_variacao = max_tamanho_variacao

    async def extrair_buscas(self, trecho: str) -> list[str]:
        if not trecho or not trecho.strip():
            return []

        prompt = (
            f"Extract the essential keywords from the journalistic excerpt below, "
            f"focusing strictly on Condition, Intervention, and Outcome (PICO methodology).\n\n"
            f'Original excerpt (Portuguese): "{trecho}"\n\n'
            f"Search query rules:\n"
            f"1. Translate concepts to their proper English scientific jargon.\n"
            f"2. Remove company names (e.g. Merck, Moderna), dates, or sensationalist words.\n"
            f"3. Generate up to {self.max_variacoes} concise search queries combining the keywords "
            f"(e.g. 'melanoma mrna vaccine recurrence' or 'spinal cord injury stem cells')."
        )
        sistema = "You are an expert in scientific literature search strategies."

        try:
            resposta = await self.cliente_llm.gerar(
                prompt=prompt, schema=Variacoes, sistema=sistema
            )
        except ErroLLM as erro:
            logger.warning(
                "Falha ao gerar variações, usando trecho original. Erro: %s", erro
            )
            return [trecho]
        except Exception as erro:
            logger.exception(
                "Erro inesperado no LLM ao gerar variações. Erro: %s", erro
            )
            return [trecho]

        buscas_validas = []
        vistas = set()

        # Sempre adiciona o trecho original para garantir degradação/verificação
        buscas_validas.append(trecho)
        vistas.add(trecho.lower())

        for b in resposta.buscas:
            if not b or not b.strip():
                continue
            if len(b) > self.max_tamanho_variacao:
                logger.warning(
                    "Variação descartada por exceder %d caracteres: %s",
                    self.max_tamanho_variacao,
                    b,
                )
                continue

            normalizada = b.strip().lower()
            if normalizada not in vistas:
                vistas.add(normalizada)
                buscas_validas.append(b.strip())

            if len(buscas_validas) >= self.max_variacoes + 1:  # +1 do original
                break

        return buscas_validas[: self.max_variacoes + 1]
