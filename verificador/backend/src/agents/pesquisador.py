"""Pesquisador: transforma as buscas do Triador nos trabalhos que o Juiz lê.

Não usa LLM. Decide, busca a busca, se a resposta vem do cache ou da OpenAlex,
dispara as externas em paralelo com teto configurável e junta tudo numa lista
só, sem repetir o mesmo artigo.

Tem dois caminhos, e tenta o curto primeiro. Quando o Triador reconhece um
título de artigo citado no trecho, uma busca literal por ele resolve a
pesquisa inteira com uma requisição -- e acha o artigo de que a matéria fala,
em vez do vizinho temático que os conceitos alcançam. Sem título, ou com o
atalho vazio, vale o caminho por conceito, que é o de sempre.

O granulo é a string de busca, e não o lote: é o que permite consultar o cache
antes de cada ida à OpenAlex. Por isso o Pesquisador chama `ClienteOpenAlex.buscar`
uma vez por string, em vez de `buscar_varias`, e reaproveita do cliente só a
normalização da lista e a intercalação por posição.

Descarta o que o Juiz não poderia julgar (`julgavel`) **antes** de cortar a
amostra, e não depois. O corte é de cinco; o Juiz lê três. Filtrar depois do
corte deixava as vagas serem preenchidas por relevância pura e só então
descobria quantas serviam -- com cinco sem abstract, o Juiz recebia lista vazia
e respondia `nada_encontrado`, que se lê como "não existe estudo" quando o que
houve foi "achei estudos que não sei ler". O filtro não custa requisição: a
OpenAlex já devolveu dez trabalhos por busca, e o que sobra do corte era
descartado sem ninguém olhar.
"""

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Protocol

from src.agents.juiz import julgavel, normalizar_doi
from src.api.schemas.busca import TrabalhoEncontrado
from src.services.cache import CacheDeBuscas, SemCache
from src.services.openalex import (
    TOP_PADRAO,
    ErroOpenAlex,
    OpenAlexIndisponivel,
    OpenAlexRecusouABusca,
    Trabalho,
    intercalar,
    normalizar_buscas,
)

logger = logging.getLogger("verificador.agentes.pesquisador")

CONCORRENCIA_PADRAO = 5


class BuscadorDeTrabalhos(Protocol):
    """O que o Pesquisador usa do `ClienteOpenAlex`: uma busca por string."""

    async def buscar(self, busca: str) -> list[Trabalho]: ...


@dataclass(frozen=True)
class ResultadoDaPesquisa:
    """Os trabalhos consolidados e as buscas que não deram certo.

    As falhas vêm junto, e não só no log: uma variação que não rodou encolhe a
    cobertura, e quem orquestra pode querer saber disso.
    """

    trabalhos: list[TrabalhoEncontrado]
    falhas: dict[str, str]
    # Quantos a OpenAlex devolveu e o filtro de `julgavel` barrou. Separa
    # "a busca não achou nada" de "achou e nada era julgável": os dois chegam
    # ao Juiz como lista curta, mas só o segundo é problema de cobertura de
    # abstract na OpenAlex.
    nao_julgaveis: int = 0
    # A resposta veio da busca literal pelo título citado, e os eixos de
    # conceito não rodaram. Serve ao log e ao eval: a amostra do atalho não é
    # comparável com a dos eixos, e misturar as duas numa média esconde as duas.
    veio_do_titulo: bool = False
    # Por que o atalho não valeu, quando havia título e ele falhou. Fica
    # separado de `falhas` de propósito: `falhas` conta buscas de conceito, e é
    # com ela que se decide se a pesquisa inteira fracassou.
    falha_do_titulo: str | None = None


def chave_por_doi(trabalho: Trabalho) -> str:
    """Identidade do artigo: o DOI quando existe, senão o id da OpenAlex.

    Preprint e versão publicada costumam ter ids diferentes na OpenAlex e o
    mesmo DOI. O prefixo impede que um DOI e um id coincidam por acaso.
    """
    doi = normalizar_doi(trabalho.doi)
    return f"doi:{doi}" if doi else f"id:{trabalho.chave}"


def _como_encontrados(trabalhos: Sequence[Trabalho]) -> list[TrabalhoEncontrado]:
    """Os trabalhos no formato do contrato da API."""
    return [
        TrabalhoEncontrado.model_validate(trabalho.como_dicionario())
        for trabalho in trabalhos
    ]


class AgentePesquisador:
    """Cache primeiro, OpenAlex depois, concorrência limitada, sem duplicatas."""

    def __init__(
        self,
        cliente: BuscadorDeTrabalhos,
        *,
        cache: CacheDeBuscas | None = None,
        concorrencia: int = CONCORRENCIA_PADRAO,
        limite: int = TOP_PADRAO,
    ) -> None:
        self.cliente = cliente
        self.cache: CacheDeBuscas = cache if cache is not None else SemCache()
        self.concorrencia = max(1, concorrencia)
        self.limite = max(1, limite)

    async def pesquisar(
        self, buscas: Sequence[str], *, busca_de_titulo: str | None = None
    ) -> ResultadoDaPesquisa:
        """Os trabalhos das buscas, intercalados por posição e sem repetição.

        `busca_de_titulo` é o atalho. Quando a matéria cita o título do artigo,
        uma busca literal por ele costuma trazer aquele artigo, e não um vizinho
        temático: é a melhor pista que a esteira pode receber, e desperdiçá-la
        era o preço de decompor tudo em conceitos. Se o atalho achar trabalho
        julgável, é essa a resposta e os eixos nem rodam -- seis requisições
        viram uma.

        **O atalho é otimização, nunca condição.** Se ele não achar nada, ou se
        a OpenAlex falhar justamente nele, a pesquisa por conceito acontece como
        sempre acontecia; o motivo da desistência vai em `falha_do_titulo`, para
        o log, e não para o leitor.

        Levanta `ValueError` se a lista não tiver nenhuma busca útil. Se
        **nenhuma** busca funcionar, levanta `OpenAlexRecusouABusca` quando
        todas foram recusadas (consulta malformada) e `OpenAlexIndisponivel`
        no resto dos casos. Falha parcial não é erro: entra em `falhas`.

        A validação da lista vive no caminho por conceito, e por isso um título
        que acerta responde mesmo com `buscas` vazia. É o que se quer: o trecho
        rendeu menos de dois conceitos, mas nomeou o artigo -- e o artigo é a
        resposta.
        """
        falha_do_titulo: str | None = None
        if busca_de_titulo:
            achados, falha_do_titulo = await self._pelo_titulo(busca_de_titulo)
            if achados is not None:
                return ResultadoDaPesquisa(
                    trabalhos=achados, falhas={}, veio_do_titulo=True
                )

        resultado = await self._pelos_conceitos(buscas)
        if falha_do_titulo is None:
            return resultado
        return replace(resultado, falha_do_titulo=falha_do_titulo)

    async def _pelo_titulo(
        self, busca: str
    ) -> tuple[list[TrabalhoEncontrado] | None, str | None]:
        """Os trabalhos do título citado, ou `None` quando o atalho não serviu.

        Passa pelo mesmo `_uma` das outras buscas, e portanto pelo cache: duas
        matérias sobre o mesmo estudo citam o mesmo título, e a segunda não
        precisa de requisição. O semáforo é de uma vaga porque há uma requisição.

        `None` cobre os dois casos que o chamador trata igual -- cair nos
        conceitos: a busca falhou, ou respondeu e nada do que veio é julgável.
        A mensagem só acompanha o primeiro; o segundo não é falha de ninguém.
        """
        saneada = normalizar_buscas([busca])
        if not saneada:
            return None, None

        resposta = await self._uma(saneada[0], asyncio.Semaphore(1))
        if isinstance(resposta, ErroOpenAlex):
            logger.warning(
                "Busca pelo título citado falhou; seguindo pelos conceitos: %s",
                resposta,
            )
            return None, str(resposta)

        julgaveis = [trabalho for trabalho in resposta if julgavel(trabalho)]
        if not julgaveis:
            logger.info(
                "Busca pelo título citado não achou trabalho julgável; "
                "seguindo pelos conceitos"
            )
            return None, None

        # Pela intercalação, e não por uma fatia: é uma lista só, mas é ela que
        # desduplica por DOI -- preprint e versão publicada vêm os dois.
        trabalhos = intercalar([julgaveis], self.limite, chave=chave_por_doi)
        logger.info(
            "Pesquisador respondeu pelo título citado com %d trabalho(s); "
            "os eixos de conceito não rodaram",
            len(trabalhos),
        )
        return _como_encontrados(trabalhos), None

    async def _pelos_conceitos(self, buscas: Sequence[str]) -> ResultadoDaPesquisa:
        """O caminho de sempre: as buscas dos eixos do Triador."""
        pedidas = normalizar_buscas(buscas)
        if not pedidas:
            raise ValueError("é preciso pelo menos uma string de busca não vazia")

        # Um limitador por pesquisa: o teto vale para esta verificação, e um
        # semáforo compartilhado entre requisições faria uma esperar a outra.
        limitador = asyncio.Semaphore(self.concorrencia)
        respostas = await asyncio.gather(
            *(self._uma(busca, limitador) for busca in pedidas)
        )

        falhas: dict[str, str] = {}
        recusas = 0
        listas: list[list[Trabalho]] = []
        for busca, resposta in zip(pedidas, respostas, strict=True):
            if isinstance(resposta, ErroOpenAlex):
                falhas[busca] = str(resposta)
                if isinstance(resposta, OpenAlexRecusouABusca):
                    recusas += 1
            else:
                listas.append(resposta)

        if len(falhas) == len(pedidas):
            motivo = (
                f"nenhuma das {len(pedidas)} buscas funcionou: "
                f"{next(iter(falhas.values()))}"
            )
            # Recusa e indisponibilidade levam o leitor a ações opostas: uma
            # consulta malformada não melhora esperando, e dizer "tente mais
            # tarde" manda ele repetir o que vai falhar igual. Só quando TODAS
            # as falhas são recusa a culpa é da consulta; uma indisponível no
            # meio já faz do conjunto um problema de serviço.
            if recusas == len(pedidas):
                raise OpenAlexRecusouABusca(motivo)
            raise OpenAlexIndisponivel(motivo)
        if falhas:
            logger.warning(
                "Pesquisador seguiu com %d de %d buscas; falharam: %s",
                len(pedidas) - len(falhas),
                len(pedidas),
                falhas,
            )

        # Filtrar ANTES de intercalar, não depois: as cinco vagas são para
        # trabalho que o Juiz consegue ler. A posição que a intercalação usa
        # passa a ser a posição entre os julgáveis -- "primeiro colocado com
        # abstract" --, que continua comparável entre buscas.
        julgaveis = [[t for t in lista if julgavel(t)] for lista in listas]

        # Contado por identidade, e não somando os descartes de cada lista: o
        # mesmo trabalho sem abstract aparece em várias buscas e seria contado
        # várias vezes.
        barrados = {
            chave_por_doi(t) for lista in listas for t in lista if not julgavel(t)
        }
        achados = {chave_por_doi(t) for lista in listas for t in lista}
        if barrados:
            logger.info(
                "Pesquisador descartou %d de %d trabalhos sem abstract, sem DOI "
                "ou retratados; %d julgáveis sobraram para as %d vagas",
                len(barrados),
                len(achados),
                len(achados) - len(barrados),
                self.limite,
            )

        # O DOI entra na intercalação, e não depois do corte: desduplicar
        # depois entregaria menos trabalhos ao Juiz do que o limite permite.
        trabalhos = intercalar(julgaveis, self.limite, chave=chave_por_doi)
        return ResultadoDaPesquisa(
            trabalhos=_como_encontrados(trabalhos),
            falhas=falhas,
            nao_julgaveis=len(barrados),
        )

    async def _uma(
        self, busca: str, limitador: asyncio.Semaphore
    ) -> list[Trabalho] | ErroOpenAlex:
        em_cache = await self._consultar_cache(busca)
        if em_cache is not None:
            return em_cache

        # O limite protege a OpenAlex; acerto de cache não ocupa vaga.
        async with limitador:
            try:
                trabalhos = await self.cliente.buscar(busca)
            except ErroOpenAlex as erro:
                return erro

        await self._guardar_no_cache(busca, trabalhos)
        return trabalhos

    async def _consultar_cache(self, busca: str) -> list[Trabalho] | None:
        # Cache é otimização: se quebrar, a busca segue para a OpenAlex.
        try:
            return await self.cache.obter(busca)
        except Exception:
            logger.exception("Cache indisponível na leitura; seguindo sem ele")
            return None

    async def _guardar_no_cache(self, busca: str, trabalhos: list[Trabalho]) -> None:
        try:
            await self.cache.guardar(busca, trabalhos)
        except Exception:
            logger.exception("Cache indisponível na escrita; resultado não guardado")
