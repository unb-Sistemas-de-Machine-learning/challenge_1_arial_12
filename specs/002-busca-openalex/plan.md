# Plano — 002 Busca de trabalhos na OpenAlex

## 1. Abordagem

Duas camadas, em arquivos separados. Embaixo, `src/services/openalex.py`: um
cliente `httpx.AsyncClient` que fala com `GET /works`, repete falha transitória
com espera crescente e traduz todo defeito de transporte em erro de domínio. Em
cima, `POST /buscar` no gateway, que só valida a entrada e traduz os erros do
cliente para o contrato HTTP da spec `011`.

A separação existe porque as duas partes falham por motivos diferentes: o
cliente é testável com transporte dublê e fixtures gravadas; a rota só precisa
provar que devolve o que o cliente produziu e que erra dentro do contrato.

A leitura da resposta é defensiva por decisão, não por descuido: a OpenAlex é um
acervo agregado de milhares de fontes e um registro pode chegar sem DOI, sem
abstract ou sem título. Um campo ausente vira `null`; nunca uma exceção.

## 2. Arquivos tocados

| Arquivo | O que muda |
| :--- | :--- |
| `verificador/backend/src/services/openalex.py` | Cliente HTTP, `Trabalho`, `ResultadoDaBusca` e os erros de domínio |
| `verificador/backend/src/api/schemas/busca.py` | Contrato HTTP de `POST /buscar` |
| `verificador/backend/src/api/gateway/routes.py` | A rota `POST /buscar` |
| `verificador/backend/src/main.py` | Encerramento do cliente e aviso de configuração na subida |
| `verificador/backend/src/core/config/settings.py` | `OPENALEX_API_KEY`, `OPENALEX_RESULTADOS_POR_BUSCA`, `OPENALEX_TIMEOUT_SEGUNDOS`, `OPENALEX_MAX_TENTATIVAS` |
| `verificador/backend/src/api/gateway/middlewares.py` | A chave da OpenAlex entra na lista de segredos redigidos do traceback |
| `verificador/backend/requirements.txt` | Sai `mcp==1.2.0` |
| `verificador/backend/.env.example` | As chaves novas, comentadas |
| `verificador/backend/pyproject.toml` | Marca `rede` registrada e excluída da execução padrão |
| `verificador/backend/src/tests/fixtures/openalex/` | Respostas gravadas + README com a URL de cada uma |
| `verificador/backend/src/tests/unit/conftest.py` | Bloqueio de soquete nos testes unitários |
| `verificador/backend/src/tests/unit/test_openalex.py` | Cliente, com transporte dublê |
| `verificador/backend/src/tests/integration/test_rota_busca.py` | A rota e o contrato de erro |
| `verificador/backend/src/tests/integration/test_openalex_rede.py` | Teste marcado `rede`, fora da CI |
| `verificador/bruno/` | Coleção Bruno das rotas |
| `verificador/README.md` | Como usar a busca e rodar o teste marcado |

## 3. Contratos

```python
QUANTIDADE_MAXIMA = 200         # teto da própria OpenAlex para `per-page`
MAXIMO_DE_BUSCAS = 10           # strings por lote
TOP_PADRAO = 5                  # quantos saem do lote por padrão
TOTAL_MAXIMO = 500              # teto absoluto para quem pedir amostra maior
CONCORRENCIA = 5                # requisições simultâneas
ORDENACOES = {"relevancia": None, "citacoes": "cited_by_count:desc",
              "ano": "publication_year:desc"}

class ErroOpenAlex(RuntimeError): ...
class OpenAlexIndisponivel(ErroOpenAlex): ...      # 429, 5xx, timeout, conexão, corpo ilegível
class OpenAlexRecusouABusca(ErroOpenAlex): ...     # 4xx que não é 429: a consulta está errada

@dataclass(frozen=True)
class Trabalho:
    id: str | None             # curto: "W2110406916"
    titulo: str
    ano: int | None
    doi: str | None            # curto: "10.1096/fj.10-157628"
    retratado: bool
    abstract: str | None
    relevancia: float | None   # None fora da ordenação por relevância
    citacoes: int | None
    @property
    def chave(self) -> str: ...          # id → doi → "titulo|ano"

@dataclass(frozen=True)
class ResultadoDaBusca:
    trabalhos: list[Trabalho]
    falhas: dict[str, str]               # string de busca → motivo
    total_por_busca: dict[str, int]      # quantos casaram, antes do corte

class ClienteOpenAlex:
    def __init__(self, *, mailto: str, api_key: str | None = None,
                 quantidade_padrao: int = 10, timeout_segundos: float = 10.0,
                 max_tentativas: int = 3, espera_base_segundos: float = 0.5,
                 cliente_http: httpx.AsyncClient | None = None,
                 dormir: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None: ...

    @classmethod
    def a_partir_das_configuracoes(cls) -> "ClienteOpenAlex": ...

    # uma string, uma requisição
    async def buscar(self, busca: str, *, quantidade: int | None = None,
                     ordenar_por: str = "relevancia") -> list[Trabalho]: ...
    # o lote: `quantidade` por busca, `limite` no fim
    async def buscar_varias(self, buscas: Sequence[str], *, quantidade: int | None = None,
                            limite: int | None = None,
                            ordenar_por: str = "relevancia") -> ResultadoDaBusca: ...
    async def fechar(self) -> None: ...
```

`ValueError` fica reservado para defeito de quem chama — lista vazia, `mailto`
ausente, ordenação desconhecida — e `ErroOpenAlex` para falha da integração.
Quem consome sabe, pelo tipo, se o problema é dele ou do serviço.

Requisição emitida:

```text
GET https://api.openalex.org/works
    ?search=<busca>&per-page=<quantidade>&select=<CAMPOS>&mailto=<e-mail>
    [&sort=<ordenação>]
User-Agent: verificador-cientifico/0.1 (mailto:<e-mail>)
[Authorization: Bearer <chave>]
```

Contrato HTTP:

```json
POST /buscar
{"buscas": ["polylaminin spinal cord injury"], "limite": 5}

200 →
{"trabalhos": [
   {"id": "W2110406916",
    "titulo": "Polylaminin, a polymeric form of laminin…",
    "ano": 2010, "doi": "10.1096/fj.10-157628",
    "retratado": false, "abstract": "Laminin is…",
    "relevancia": 863.9, "citacoes": 48}
 ],
 "buscas_com_falha": {},
 "total_por_busca": {"polylaminin spinal cord injury": 49}}
```

## 4. Decisões técnicas

| Decisão | Alternativa descartada | Por quê |
| :--- | :--- | :--- |
| HTTP puro, sem camada MCP | Servidor `FastMCP` com a ferramenta `buscar_trabalhos` | MCP expõe ferramentas a um cliente **externo**, por subprocesso e JSON-RPC; aqui tudo mora no mesmo processo, e a OpenAlex é REST de qualquer forma — era adaptador de HTTP para HTTP |
| Módulo em `src/services/` | Manter em `src/mcp/` | O nome da pasta é documentação; `mcp/` passaria a mentir |
| Top 5 da relevância da OpenAlex | Clusterizar com BERTopic e amostrar | Resolve o mesmo problema com zero token, zero `torch` e zero latência; perde diversidade temática, e é aí que se volta atrás |
| Lote intercala por posição | Ordenar a lista juntada por `relevancia` | O escore mede a busca, não o artigo: medido, 870 na formulação curta contra 227 na longa, para o mesmo assunto. Ordenar por ele daria todas as vagas à busca mais curta |
| Deixar a OpenAlex ordenar e cortar | Paginar os 4.293 e mandar tudo adiante | 4.293 abstracts são ~1,19 milhão de tokens; 5 são ~1,4 mil |
| Devolver `total_por_busca` | Só a lista | "Achei 5 de 49" e "achei 5 de 4.293" levam a decisões diferentes |
| Expor `relevancia` e `citacoes` | Guardar só para ordenar | São o sinal com que o Juiz vai discordar da ordem da OpenAlex, se quiser |
| Erro de domínio próprio no módulo | Levantar `ErroGateway` da spec `011` | `src/api` pode depender de `src/services`; o contrário inverteria a dependência e amarraria a integração ao HTTP |
| Dois erros: indisponível e busca recusada | Um só | `503` deles e `400` nosso viram o mesmo `503` para o usuário, mas não a mesma linha de log |
| Config faltando dá `503`, não `422` | Um `except ValueError` só | `422` manda quem chamou revisar uma busca que estava certa — foi o que aconteceu na primeira versão |
| Chave de API no cabeçalho `Authorization` | Parâmetro `api_key` na query | A OpenAlex aceita os dois; segredo em URL vaza para log de proxy, histórico e mensagem de erro |
| Chave opcional, e não obrigatória | Exigir como o `mailto` | O projeto ainda não tem uma; exigir travaria a busca hoje |
| `503` de busca anônima com mensagem própria | Tratar como qualquer `5xx` | O log diria "503" e a equipe procuraria defeito no código |
| `httpx.AsyncClient` injetável | `respx` ou `unittest.mock` | `MockTransport` exercita a pilha real do `httpx` — parâmetros, cabeçalhos, timeout — em vez de dublar o método que o teste queria verificar |
| Função de espera injetável | `time.sleep` real com valores minúsculos | O teste de repetição afirma **quais** esperas aconteceram, e a suíte não perde segundos |
| Pedido acima do teto é reduzido | Recusar com `ValueError` | Devolver 200 é melhor do que derrubar a verificação inteira porque pediram 500 |
| String no lugar da lista levanta `ValueError` | Aceitar os dois | Iterar uma string daria uma busca por caractere: 359 requisições para a consulta real de exemplo |
| Consulta repassada byte a byte | Escapar ou normalizar os operadores | Parênteses agrupam de verdade: a mesma consulta devolve 4.293 resultados agrupada e 189 sem eles |
| `select` na consulta | Trazer o registro inteiro | A resposta completa de 5 trabalhos passa de 50 kB; com `select`, de 30 kB |
| DOI e `id` curtos | Guardar as URLs | O schema `Estudo` da spec `010` já usa a forma curta |
| Soquete bloqueado em `src/tests/unit/` | Confiar na convenção | Um teste passou a chamar a rede de verdade e continuou verde, porque o `.env` local fazia a chamada falhar antes de sair |
| Marca `rede` excluída por padrão no `pyproject` | Variável de ambiente no workflow | A exclusão fica junto do resto da configuração de teste, e vale igual na CI e na máquina de quem desenvolve |
| Teste de rede **pula** quando a OpenAlex está fora | Falhar | O cliente fez o certo ao reportar indisponibilidade; vermelho aqui ensina a ignorar vermelho |

### Repetição

| Tentativa | Espera antes da próxima |
| :-- | :--- |
| 1 | 0,5 s |
| 2 | 1,0 s |
| 3 | — levanta `OpenAlexIndisponivel` |

`Retry-After` recebido em `429` substitui a espera calculada, limitado a 10 s
para não segurar uma requisição HTTP presa atrás dela.

## 5. Como testar

- **Unit** (`test_openalex.py`): `httpx.MockTransport` devolve as fixtures
  gravadas; `dormir` é um dublê que registra as esperas. Reais: o `httpx`, a
  montagem da query, a leitura da resposta, o laço de repetição e a
  intercalação. Abrir soquete estoura o teste.
- **Integração** (`test_rota_busca.py`): `TestClient` sobre a app real, com o
  cliente compartilhado trocado por um de transporte dublê. Cobre a resposta,
  o OpenAPI e os três caminhos de erro.
- **Rede** (`test_openalex_rede.py`): marcado `rede`, fora da execução padrão.
  Busca de verdade, confere os tipos do contrato, a desduplicação do lote e que
  os parênteses ainda agrupam. Pula — não falha — se a OpenAlex estiver fora.
- **Regravar fixtures:** as URLs estão em `src/tests/fixtures/openalex/README.md`.
- **Eval:** não se aplica.

## 6. Riscos

- A OpenAlex muda o formato da resposta e as fixtures envelhecem sem ninguém
  perceber, porque a CI não fala com ela. Mitigação: o teste `rede` existe
  justamente para ser rodado à mão antes de uma entrega que dependa da busca.
- Sem `OPENALEX_API_KEY`, a busca é intermitente sob carga da OpenAlex. Não é
  hipótese: aconteceu durante a implementação.
- `POST /buscar` é pública e sem limite próprio. Ver seção 6a da spec.
- O teto de 5 resultados é palpite até existir o Juiz. É parâmetro, não
  constante enterrada, justamente para a próxima spec poder mexer.
