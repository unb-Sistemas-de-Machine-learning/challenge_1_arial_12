# Plano - 022 Agente Pesquisador e esteira real do `/verificar`

## 1. Abordagem

O Pesquisador é uma classe sem LLM em `src/agents/pesquisador.py`. Ela recebe as buscas do Triador e, **por string de busca**, consulta primeiro o cache e só depois o `ClienteOpenAlex.buscar`, com um semáforo configurável em volta da chamada externa. Depois junta tudo com a mesma intercalação por posição que o cliente já usa, desduplicando por DOI normalizado.

O granulo é a string, e não o lote, por causa do cache: `buscar_varias` faz o lote inteiro de uma vez e não deixa consultar o cache busca a busca. Por isso o Pesquisador orquestra as chamadas unitárias e reaproveita as funções de lote do cliente (normalização e intercalação), que deixam de ser privadas.

O `/verificar` passa a receber Triador, Pesquisador e Juiz por `Depends`, encadear as três etapas, trocar `termos` pelos conceitos do Triador, gravar o veredito e responder. Não há módulo de esteira à parte: a rota **é** o orquestrador, como pede a issue.

## 2. Arquivos tocados

| Arquivo | O que muda |
| :--- | :--- |
| `verificador/backend/src/agents/pesquisador.py` | **novo** — `AgentePesquisador`, `ResultadoDaPesquisa`, desduplicação por DOI |
| `verificador/backend/src/services/cache.py` | **novo conteúdo** — protocolo `CacheDeBuscas` e implementação `SemCache` |
| `verificador/backend/src/services/openalex.py` | `_intercalar` vira `intercalar` (público, com parâmetro `chave`); `_normalizar_buscas` vira `normalizar_buscas`. Comportamento de `buscar_varias` inalterado |
| `verificador/backend/src/agents/triador.py` | novo `ExtracaoDoTriador` e método `extrair`; `extrair_buscas` passa a delegar a ele, sem mudar o retorno |
| `verificador/backend/src/agents/juiz.py` | `normalizar_doi` passa a ser importado pelo Pesquisador (sem mudança de código) |
| `verificador/backend/src/api/gateway/dependencias.py` | **novo** — `obter_triador`, `obter_pesquisador`, `obter_juiz`, com os clientes de LLM e OpenAlex montados só na primeira chamada |
| `verificador/backend/src/api/gateway/routes.py` | `/verificar` orquestra a esteira e grava o veredito; saem os `print`. `_VEREDITO_FIXO` deixa de ser resposta e fica só como exemplo do OpenAPI (renomeado para `_EXEMPLO_DE_VEREDITO`). `/buscar` inalterada |
| `verificador/backend/src/core/config/settings.py` | `pesquisador_concorrencia` (`PESQUISADOR_CONCORRENCIA`, padrão 5, de 1 a 10) |
| `verificador/backend/.env.example` | a variável nova, comentada |
| `verificador/README.md` | roteiro local exige `LLM_API_KEY` e `OPENALEX_MAILTO`; seção nova do Pesquisador |
| `verificador/backend/src/tests/unit/test_pesquisador.py` | **novo** — dedup, concorrência, falha parcial/total, cache |
| `verificador/backend/src/tests/unit/test_triador.py` | casos de `extrair` (conceitos e degradação) |
| `verificador/backend/src/tests/unit/test_openalex.py` | caso de `intercalar` com `chave` personalizada |
| `verificador/backend/src/tests/integration/test_rotas_verificacao.py` | troca o teste do stub pelos cenários da esteira com dublês |
| `verificador/backend/src/tests/fixtures/veredito_fase01.json` | removido: só o teste do stub usa |
| `verificador/backend/src/tests/dubles/esteira.py` | **novo** — esteira sem rede e banco que falha na hora, para os testes que só usam `/verificar` como rota que responde 200 |
| `verificador/backend/src/tests/integration/test_limite_de_taxa.py`, `test_app_compose.py`, `test_startup_settings.py` | instalam o dublê da esteira |

## 3. Contratos

```python
# src/services/cache.py
class CacheDeBuscas(Protocol):
    """Ponto único de extensão consultado antes da OpenAlex, por string de busca."""

    async def obter(self, busca: str) -> list[Trabalho] | None:
        """Os trabalhos guardados para a busca, ou None se não houver."""

    async def guardar(self, busca: str, trabalhos: list[Trabalho]) -> None: ...


class SemCache:
    """Padrão desta entrega: nunca encontra nada e não guarda nada."""
```

```python
# src/agents/pesquisador.py
@dataclass(frozen=True)
class ResultadoDaPesquisa:
    trabalhos: list[TrabalhoEncontrado]  # o tipo que o Juiz recebe
    falhas: dict[str, str]               # busca -> motivo, só das que falharam


class AgentePesquisador:
    def __init__(
        self,
        cliente: ClienteOpenAlex,
        *,
        cache: CacheDeBuscas | None = None,   # None = SemCache()
        concorrencia: int = 5,
        limite: int = TOP_PADRAO,             # 5, decidido na spec
    ) -> None: ...

    async def pesquisar(self, buscas: Sequence[str]) -> ResultadoDaPesquisa:
        """Levanta OpenAlexIndisponivel se nenhuma busca funcionar.
        Levanta ValueError se a lista não tiver nenhuma busca útil."""
```

```python
# src/agents/triador.py
@dataclass(frozen=True)
class ExtracaoDoTriador:
    buscas: list[str]     # idêntico ao que extrair_buscas devolve hoje
    conceitos: list[str]  # intervenção, desfecho, condição, população,
                          # canônicos, sem vazios e sem repetição

class AgenteTriador:
    async def extrair(self, trecho: str) -> ExtracaoDoTriador:
        """Nunca levanta. Se o LLM falhar: buscas=[trecho], conceitos=[]."""

    async def extrair_buscas(self, trecho: str) -> list[str]:
        """Mantido para o eval do Triador: devolve extrair(trecho).buscas."""
```

```python
# src/api/gateway/routes.py — forma da rota, não o código final
@router.post("/verificar", response_model=Veredito, ...)
async def verificar(
    request: Request,
    pedido: Pedido = Body(...),
    triador: AgenteTriador = Depends(obter_triador),
    pesquisador: AgentePesquisador = Depends(obter_pesquisador),
    juiz: AgenteJuiz = Depends(obter_juiz),
) -> Veredito:
    extracao = await triador.extrair(pedido.trecho)
    try:
        pesquisa = await pesquisador.pesquisar(extracao.buscas)
    except OpenAlexIndisponivel as erro:
        raise ErroGateway(CodigoErro.OPENALEX_INDISPONIVEL) from erro
    except ValueError as erro:
        raise ErroGateway(CodigoErro.ENTRADA_INVALIDA) from erro
    veredito = await juiz.julgar(pedido.trecho, pesquisa.trabalhos)  # ErroLLM -> handler
    veredito = veredito.model_copy(update={"termos": extracao.conceitos})
    return veredito.model_copy(update={"id": await gravar(request, pedido.trecho, veredito)})
```

`gravar` chama `registrar_veredito` com `resposta = veredito.model_dump(mode="json")` e devolve o `id`, ou `None` se qualquer exceção acontecer, registrando-a com `logger.exception`.

O contrato HTTP de `/verificar`, `/buscar` e `/feedback` **não muda**.

## 4. Decisões técnicas

| Decisão | Alternativa descartada | Por quê |
| :--- | :--- | :--- |
| Pesquisador chama `ClienteOpenAlex.buscar` por string | Chamar `buscar_varias` e desduplicar depois | O cache precisa ser consultado por string, antes da busca externa (critério 5) |
| Semáforo só em volta da chamada externa | Semáforo em volta de cache + OpenAlex | Acerto de cache não ocupa vaga de concorrência; o limite protege a OpenAlex |
| Desduplicar por DOI **dentro** da intercalação, antes do corte em 5 | Cortar em 5 e desduplicar depois | Desduplicar depois do corte entregaria menos de 5 trabalhos ao Juiz sem necessidade |
| Chave de desduplicação: DOI normalizado (`normalizar_doi` do Juiz) ou, sem DOI, id da OpenAlex | Só o id da OpenAlex, como hoje | Preprint e versão publicada podem ter ids diferentes e o mesmo DOI (critério 1); reusar `normalizar_doi` mantém uma regra só no projeto |
| Tornar `intercalar` e `normalizar_buscas` públicas | Copiar a lógica para o Pesquisador | Uma regra de intercalação só, já documentada e testada |
| Erro no cache (`obter` ou `guardar`) vira "sem cache" para aquela busca, com log | Propagar o erro | Cache é otimização: nunca pode derrubar uma verificação |
| Falha de configuração da OpenAlex (`OPENALEX_MAILTO` vazio) vira `openalex_indisponivel` | 500 | Mesmo tratamento que `/buscar` já dá |
| Clientes de LLM e OpenAlex montados na primeira chamada (`_LLMSobDemanda`, `_OpenAlexSobDemanda`), respeitando `dependency_overrides[obter_cliente_llm]` | `Depends(obter_cliente_llm)` direto, como previsto | O FastAPI resolve dependências antes de validar o corpo: com a dependência levantando, pedido sem `trecho` respondia 503 em vez de 422 quando faltava chave. A costura de teste com `DubleLLM` continua a mesma |
| Trecho em branco responde 422 antes de qualquer etapa | Deixar o Triador devolver lista vazia e o Pesquisador recusar | Não gasta LLM com pedido sem conteúdo |
| Triador, Pesquisador e Juiz por `Depends` em `dependencias.py` | Instanciar na rota | Teste de integração troca cada etapa com `app.dependency_overrides` |
| `extrair` novo no Triador, `extrair_buscas` mantido | Mudar o retorno de `extrair_buscas` | `scripts/eval_triador.py` e os testes atuais continuam valendo sem mudança |
| Ordem dos conceitos: intervenção, desfecho, condição, população | A ordem de `CAMPOS` (condição primeiro) | É a ordem em que o leitor entende a alegação: o que age, o que muda, onde, em quem |
| Gravação síncrona antes de responder | `BackgroundTasks`, como o feedback | O `id` precisa voltar na resposta para o feedback funcionar |
| Saem os `print` de `/verificar` | Manter o log de `trecho` e `url` | Era depuração da Fase 01; a URL não tem uso (ver discussão da spec 021) |

## 5. Como testar

- **Unit (`test_pesquisador.py`)** — cliente OpenAlex com `httpx.MockTransport` e as fixtures de `src/tests/fixtures/openalex/`; nenhum teste abre rede (o `conftest.py` de unit já barra):
  - dois trabalhos com o mesmo DOI em formatos diferentes (`10.1/ABC`, `https://doi.org/10.1/abc`) saem uma vez só;
  - trabalhos sem DOI são desduplicados pelo id;
  - com `concorrencia=2` e 5 buscas, o transporte nunca vê mais de 2 requisições simultâneas (contador com `asyncio.Event` para segurar as respostas);
  - uma busca com 500 e outra com 200: o resultado traz os trabalhos da segunda e `falhas` com a primeira;
  - todas com 500: `OpenAlexIndisponivel`;
  - cache dublê com a resposta de uma busca: o transporte não recebe aquela busca; `guardar` é chamado para as que foram à OpenAlex;
  - cache que levanta exceção: a busca vai à OpenAlex e a verificação segue.
- **Unit (`test_triador.py`)** — `extrair` com `DubleLLM`: conceitos na ordem certa, sem vazios e repetidos; LLM falhando devolve `buscas=[trecho]` e `conceitos=[]`; `extrair_buscas` continua igual.
- **Integração (`test_rotas_verificacao.py`)** — `criar_app` com `dependency_overrides` para as três etapas (LLM com `DubleLLM`, OpenAlex com `MockTransport`):
  - caminho feliz: 200, `estado` vindo do Juiz, `termos` = conceitos do Triador, `id = null` (sem banco no teste, a gravação falha e vira log);
  - todas as buscas falham: 503 `openalex_indisponivel`;
  - Juiz estoura o tempo: 504 `llm_timeout`; Juiz responde inválido duas vezes: 503 `llm_indisponivel`;
  - Triador falha e Juiz responde: 200 com `termos = []`;
  - sem `LLM_API_KEY`: 503 `llm_indisponivel`;
  - `/buscar` continua respondendo como antes (os testes de `test_rota_busca.py` não mudam).
- **Integração com banco (`exige_banco`)** — caminho feliz grava uma linha em `veredito`, e o `id` devolvido aceita `POST /feedback`.
- **Eval:** não há eval novo (spec, seção 5).
- **Manual:** `/verificar` pelo Postman e pela extensão com `LLM_API_KEY` e `OPENALEX_MAILTO` reais.

## 6. Riscos

- **Banco fora do ar deixa a resposta lenta.** A gravação espera o timeout de conexão do driver antes de desistir e devolver `id = null` (nos testes, uns 5 s com host inexistente). Se incomodar, a correção é um timeout de conexão curto em `criar_motor`, fora desta spec.
- **Tempo de resposta alto.** Sem teto (decisão da spec), uma verificação pode passar de 30 s com repetições da OpenAlex e do Juiz. Se a equipe sentir na extensão, a próxima spec define um orçamento total.
- **Quota do Groq.** Cada verificação faz duas chamadas de LLM, contra uma por caso nos evals. Testes manuais repetidos podem bater no 429; o erro chega como `llm_indisponivel`.
- **Poucos abstracts nos 5 trabalhos.** O Juiz pode responder `nada_encontrado` mais do que deveria. A decisão de manter 5 foi consciente; o número é um parâmetro do Pesquisador e pode subir sem mudar código da rota.
- **Mudança de nome em funções do cliente OpenAlex.** `intercalar` e `normalizar_buscas` deixam de ter `_`. Hoje só o próprio `openalex.py` as usa, então o risco é baixo; a suíte do cliente precisa continuar verde sem ajuste.
