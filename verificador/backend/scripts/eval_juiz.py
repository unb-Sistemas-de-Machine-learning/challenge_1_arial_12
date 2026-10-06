"""Avalia o Juiz em 40 casos rotulados (sintéticos, não evidência científica).

    python scripts/eval_juiz.py --validar-dataset  # sem chave, sem rede
    python scripts/eval_juiz.py --caso S02 --caso S03  # diagnóstico parcial
    python scripts/eval_juiz.py --caso E02 --mostrar-justificativa
    python scripts/eval_juiz.py --intervalo 10          # pausa entre casos
    python scripts/eval_juiz.py                    # exige LLM_API_KEY e DATABASE_URL

O modo real usa o provedor configurado no .env e faz chamadas pagas ou sujeitas
a quota. Não roda na CI. A meta não é considerada atingida sem esta rodada.
"""

import argparse
import asyncio
import json
import logging
import math
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents import orientacoes
from src.agents.juiz import ARQUIVO_DE_ORIENTACOES, AgenteJuiz, normalizar_doi
from src.api.schemas.busca import TrabalhoEncontrado
from src.api.schemas.verificacao import Estado, Veredito
from src.services.llm import (
    ClienteLLM,
    ErroLLM,
    FalhaTransitoria,
    LLMIndisponivel,
    LLMRecusouOPedido,
    LLMTempoEsgotado,
    RespostaInvalidaDoLLM,
)

logging.basicConfig(level=logging.WARNING)

CAMINHO_PADRAO = Path(__file__).resolve().parent.parent / "evals" / "juiz.jsonl"
MINIMO_CASOS = 40
META_ACERTO = 80.0
CAMPOS_DA_RESPOSTA = frozenset(
    {"relacao", "estado", "doi", "evidencia", "justificativa"}
)
MOTIVOS_DE_DOMINIO = frozenset(
    {
        "Justificativa não parece estar em português",
        "Justificativa contém referência interna",
        "Justificativa cita DOI ausente da entrada",
        "Sem estudo não pode citar fonte",
        "DOI selecionado não confere com a entrada",
        "Estudo retratado não pode sustentar",
        "Evidência não consta do abstract selecionado",
        "Estado incoerente com a relação declarada entre alegação e estudo",
    }
)


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


def selecionar_casos(casos: list[Caso], ids: list[str] | None) -> list[Caso]:
    """Seleciona IDs explícitos; um erro de digitação não chama o LLM."""
    if not ids:
        return casos
    por_id = {caso.id: caso for caso in casos}
    ausentes = sorted(set(ids) - por_id.keys())
    if ausentes:
        raise ValueError(f"caso(s) inexistente(s): {', '.join(ausentes)}")
    return [por_id[id] for id in dict.fromkeys(ids)]


def motivo_seguro(erro: ErroLLM) -> str:
    """Resume somente categorias conhecidas; nunca imprime resposta ou segredo."""
    if isinstance(erro, RespostaInvalidaDoLLM):
        atual: BaseException | None = erro
        while atual is not None:
            if isinstance(atual, ValidationError):
                detalhes = []
                for item in atual.errors(
                    include_input=False, include_context=False, include_url=False
                ):
                    campo = item["loc"][0] if item["loc"] else "JSON"
                    campo = campo if campo in CAMPOS_DA_RESPOSTA else "campo adicional"
                    tipo = item["type"]
                    detalhes.append(f"{campo}: {tipo}")
                return "schema inválido (" + ", ".join(detalhes) + ")"
            if isinstance(atual, RespostaInvalidaDoLLM):
                if str(atual) in MOTIVOS_DE_DOMINIO:
                    return str(atual)
                if "gerou JSON fora do schema" in str(atual):
                    return "provedor gerou JSON fora do schema"
                if "devolveu uma resposta vazia" in str(atual):
                    return "provedor devolveu resposta vazia"
            atual = atual.__cause__
        return "resposta fora do formato esperado"

    if isinstance(erro, LLMTempoEsgotado):
        return "tempo de resposta excedido"
    if isinstance(erro, LLMRecusouOPedido):
        return "provedor recusou a requisição"
    if isinstance(erro, LLMIndisponivel):
        causa = erro.__cause__
        if isinstance(causa, FalhaTransitoria):
            if "(429)" in str(causa):
                detalhes = ["limite de uso do provedor (429)"]
                limite = causa.diagnostico_limite
                if limite is not None:
                    tipo = limite.tipo
                    if tipo is None and limite.requisicoes_restantes_dia == 0:
                        tipo = "RPD" if limite.tokens_restantes_minuto != 0 else None
                    if tipo is None and limite.tokens_restantes_minuto == 0:
                        tipo = "TPM" if limite.requisicoes_restantes_dia != 0 else None
                    detalhes.append(f"tipo={tipo or 'não identificado'}")
                    if limite.requisicoes_restantes_dia is not None:
                        detalhes.append(
                            f"requisições restantes no dia={limite.requisicoes_restantes_dia}"
                        )
                    if limite.tokens_restantes_minuto is not None:
                        detalhes.append(
                            f"tokens restantes no minuto={limite.tokens_restantes_minuto}"
                        )
                    if (
                        limite.requisicoes_restantes_dia == 0
                        and limite.reinicio_requisicoes
                    ):
                        detalhes.append(
                            f"reinício requisições={limite.reinicio_requisicoes}"
                        )
                    if limite.tokens_restantes_minuto == 0 and limite.reinicio_tokens:
                        detalhes.append(f"reinício tokens={limite.reinicio_tokens}")
                if causa.retry_after is not None:
                    detalhes.append(f"Retry-After={causa.retry_after:g}s")
                return "; ".join(detalhes)
            if "falha de conexão" in str(causa):
                return "falha de conexão com o provedor"
            if "resposta 5" in str(causa):
                return "erro 5xx do provedor"
        return "provedor indisponível"
    return "falha na camada de LLM"


def limite_429(erro: ErroLLM) -> bool:
    causa = erro.__cause__
    return (
        isinstance(erro, LLMIndisponivel)
        and isinstance(causa, FalhaTransitoria)
        and "(429)" in str(causa)
    )


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


def relatorio(resultados: list[Resultado], *, completo: bool) -> int:
    acerto, sem_relacao, retratado, falhas = metricas(resultados)
    if completo:
        print(f"Acerto do estado: {acerto:.1f}% (meta >= {META_ACERTO:g}%)")
    else:
        print(f"Acerto parcial: {acerto:.1f}% (não mede a meta de aceite)")
    print(f"Falsos sustenta sem abstract relacionado: {sem_relacao} (meta 0)")
    print(f"Sustenta com estudo retratado: {retratado} (meta 0)")
    print(f"Falhas de chamada/validação: {falhas}")
    limite_de_acerto = META_ACERTO if completo else 100.0
    return int(
        acerto < limite_de_acerto or sem_relacao > 0 or retratado > 0 or falhas > 0
    )


async def rodar(
    casos: list[Caso],
    *,
    completo: bool = True,
    intervalo: float = 0,
    mostrar_justificativa: bool = False,
) -> int:
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
    if not completo:
        print("Diagnóstico parcial: esta execução não valida a meta de 80%.")
    resultados: list[Resultado] = []
    interrompido_por_limite = False
    try:
        for indice, caso in enumerate(casos):
            if indice and intervalo:
                await asyncio.sleep(intervalo)
            try:
                veredito = await agente.julgar(caso.trecho, caso.trabalhos)
            except ErroLLM as erro:
                resultados.append(Resultado(caso, None, type(erro).__name__))
                print(f"{caso.id}: falha {type(erro).__name__}: {motivo_seguro(erro)}")
                if limite_429(erro):
                    interrompido_por_limite = True
                    print(
                        "Eval interrompido após 429; casos seguintes não foram executados."
                    )
                    break
            else:
                resultados.append(Resultado(caso, veredito))
                acerto = "ok" if veredito.estado == caso.estado_esperado else "erro"
                print(f"{caso.id}: {veredito.estado.value} ({acerto})")
                if mostrar_justificativa:
                    print(
                        "  justificativa: "
                        + json.dumps(veredito.justificativa, ensure_ascii=False)
                    )
    finally:
        await cliente.fechar()

    resultado = relatorio(resultados, completo=completo and not interrompido_por_limite)
    return 1 if interrompido_por_limite else resultado


def main() -> int:
    # O terminal do Windows pode vir em cp1252; preserve os acentos do relatório.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--validar-dataset", action="store_true")
    parser.add_argument("--arquivo", type=Path, default=CAMINHO_PADRAO)
    parser.add_argument(
        "--caso",
        action="append",
        type=str.upper,
        metavar="ID",
        help="roda só este caso; repita a opção para selecionar mais casos",
    )
    parser.add_argument(
        "--mostrar-justificativa",
        action="store_true",
        help="mostra a justificativa validada; exige --caso",
    )
    parser.add_argument(
        "--intervalo",
        type=float,
        default=0,
        metavar="SEGUNDOS",
        help="pausa entre casos para reduzir 429; não altera limites do provedor",
    )
    argumentos = parser.parse_args()
    if not math.isfinite(argumentos.intervalo) or argumentos.intervalo < 0:
        parser.error("--intervalo precisa ser um número de segundos não negativo")
    if argumentos.mostrar_justificativa and not argumentos.caso:
        parser.error("--mostrar-justificativa exige pelo menos um --caso")
    try:
        casos = ler_casos(argumentos.arquivo)
    except (OSError, ValueError) as erro:
        print(f"Dataset inválido: {erro}")
        return 2

    contagem = Counter(caso.estado_esperado.value for caso in casos)
    print(f"Dataset válido: {len(casos)} casos; {dict(contagem)}")
    if argumentos.validar_dataset and argumentos.caso:
        print("Use --validar-dataset ou --caso; as opções não se combinam.")
        return 2
    if argumentos.validar_dataset:
        print(
            "Métricas de acerto não medidas: execute sem --validar-dataset com LLM real."
        )
        return 0
    try:
        selecionados = selecionar_casos(casos, argumentos.caso)
    except ValueError as erro:
        print(f"Seleção inválida: {erro}")
        return 2
    return asyncio.run(
        rodar(
            selecionados,
            completo=len(selecionados) == len(casos),
            intervalo=argumentos.intervalo,
            mostrar_justificativa=argumentos.mostrar_justificativa,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
