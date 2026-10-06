# Verificador Científico

Circuito completo: seleção de texto → botão → background → back-end →
Triador → Pesquisador (OpenAlex) → Juiz → painel. Desde a spec 022 o
veredito é calculado de verdade; para rodar `/verificar` localmente, preencha
`LLM_API_KEY` e `OPENALEX_MAILTO` no `.env` (ver [Como rodar](#como-rodar)).

```
content.ts  --runtime.sendMessage-->  background.ts  --fetch-->  FastAPI
     ^                                                              |
     └──────────────────── resposta pela mesma via ─────────────────┘
```

O `fetch` é feito no background porque o content script está sujeito à CSP
da página visitada — muitos sites bloqueiam requisições a `localhost`.

## Estrutura

```
verificador/
├── backend/
│   ├── src/main.py        # aplicação FastAPI: POST /verificar, /buscar, /feedback; GET /health
│   ├── docker-compose.yml # api + db; inicia src.main:app
│   ├── requirements.txt
│   └── .venv/             # criado localmente
├── extensao/
│   ├── wxt.config.ts      # manifest por navegador (Chrome MV3 / Firefox MV2)
│   ├── config.ts          # base do back-end (WXT_API_BASE_URL) e rotas
│   ├── .env.example       # modelo do .env com a base do back-end
│   ├── tipos.ts           # contrato JSON compartilhado
│   └── entrypoints/
│       ├── background.ts  # faz o fetch ao back-end
│       └── content.ts     # seleção, botão flutuante e painel (shadow DOM)
└── pagina-teste.html      # página local para o primeiro teste
```

## Pré-requisitos

- Node 20+ e npm — **ok** (Node 26.3.1)
- Python 3.12 para o venv — é a versão da imagem Docker e suporta as dependências fixadas
- **Firefox** — ✅ instalado (154.0.1, via `brew install --cask firefox`)
- **Chrome** — não instalado. Se quiser testar nele também:
  `brew install --cask google-chrome`
- `web-ext` — dependência de dev já instalada. É ela que faz o WXT **abrir o
  navegador sozinho**; sem ela o WXT só diz "carregue manualmente".

O Safari também é possível, mas exige o Xcode completo — ver
[Testar no Safari](#testar-no-safari) no fim deste arquivo.

## Como rodar

### 1A. API por Docker Compose

```bash
cd verificador/backend
cp .env.example .env                      # só na primeira vez; ajuste os valores para seu ambiente
docker compose up --build
```

O Compose sobe `api` e `db`. Em outro terminal, verifique a aplicação:

```bash
curl http://localhost:8000/health
```

A resposta esperada é `{"ok":true}`. O serviço `api` executa `src.main:app`,
que também expõe `POST /verificar`. Sem `.env` e sem `DATABASE_URL` no ambiente,
o Compose ainda inicia o `db`, mas a API encerra na inicialização com erro que
identifica `DATABASE_URL`.

### 1B. API por venv (alternativa ao Compose)

Pare o Compose antes de iniciar o Uvicorn local, pois ambos usam a porta 8000.

```bash
cd verificador/backend
cp .env.example .env                      # só na primeira vez; ajuste os valores para seu ambiente
python3 -m venv .venv                    # só na primeira vez
./.venv/bin/pip install -r requirements.txt
./.venv/bin/uvicorn src.main:app --reload --port 8000
```

Confira isolado, antes de mexer na extensão:

```bash
curl -X POST http://localhost:8000/verificar \
  -H "Content-Type: application/json" \
  -d '{"trecho":"Café reduz o risco de câncer de fígado"}'
```

Deve voltar um veredito (`sustenta`, `exagera` ou `nada_encontrado`) com a
justificativa e o estudo usado. A resposta leva alguns segundos: são duas
chamadas de LLM e as buscas na OpenAlex. **Só avance quando isso funcionar.**

O healthcheck responde em `http://localhost:8000/health` com `{"ok":true}`.
O backend lê `.env` na inicialização. `DATABASE_URL` precisa estar preenchida,
mas o healthcheck não conecta ao banco. Para `/verificar` funcionar, preencha
também:

- `LLM_API_KEY` — a chave do Groq é gratuita. Sem ela, `/verificar` responde
  `503 llm_indisponivel` sempre que encontra estudos para o Juiz analisar;
- `OPENALEX_MAILTO` — um e-mail de contato. Sem ele, toda busca falha e
  `/verificar` responde `503 openalex_indisponivel`.

Não existe modo mock: o veredito fixo da Fase 01 saiu com a spec 022. Sem banco
alcançável, a verificação funciona e o veredito volta com `id = null` — a
extensão só esconde os botões de feedback. `CORS_ORIGINS` aceita uma lista JSON de origens e, por padrão,
mantém `['*']` — use isso só em desenvolvimento (`APP_DEBUG=true`); fora dele,
configure a lista com a origem real da extensão publicada.

Toda rota, exceto `/health`, tem um limite de requisições por origem
(cabeçalho `Origin`, ou o IP da conexão quando ele falta). Passar do limite
responde `429` com `Retry-After` em segundos até a janela reiniciar.
`RATE_LIMIT_MAX_REQUESTS` (padrão `30`) e `RATE_LIMIT_WINDOW_SECONDS` (padrão
`60`) controlam o limite e a janela; a contagem é em memória, por processo.

### Erros do gateway

Erros HTTP retornam `{"codigo":"...","mensagem":"..."}`. O cabeçalho
`X-Correlation-ID` identifica a requisição no log do servidor; informe esse ID
ao investigar uma falha. A extensão escolhe o texto exibido pelo `codigo`, sem
mostrar detalhes técnicos da resposta.

| Status | Código | Mensagem sugerida na extensão |
| :--- | :--- | :--- |
| 422 | `entrada_invalida` | Revise o texto selecionado e tente novamente. |
| 429 | `limite_excedido` | Muitas solicitações. Aguarde um pouco e tente novamente. |
| 503 | `openalex_indisponivel` | A busca de estudos está indisponível. Tente novamente mais tarde. |
| 504 | `llm_timeout` | A análise demorou demais. Tente novamente. |
| 503 | `llm_indisponivel` | A análise está indisponível. Tente novamente mais tarde. |
| 404 | `recurso_nao_encontrado` | Serviço não encontrado. |
| 405 | `metodo_nao_permitido` | Esta operação não está disponível. |
| 400 e demais `4xx` | `erro_requisicao` | Não foi possível processar a solicitação. |
| 503 genérico | `servico_indisponivel` | Serviço indisponível. Tente novamente mais tarde. |
| 500 e demais `5xx` | `erro_interno` | Não foi possível concluir a verificação agora. |

Se não houver resposta HTTP, a extensão mostra uma mensagem local de falha de
conexão.

### Camada de LLM (spec 003)

Porta única dos agentes Triador e Juiz para o LLM, em
[`src/services/llm.py`](backend/src/services/llm.py). **Só camada gratuita:**
Groq ou Google Gemini, os dois pela API compatível com a OpenAI. Quem usa a
camada hoje é o Triador.

```bash
LLM_PROVEDOR=groq              # groq ou gemini
LLM_API_KEY=                   # https://console.groq.com/keys ou https://aistudio.google.com/apikey
LLM_MODELO=                    # vazio: openai/gpt-oss-20b (groq) ou gemini-3.5-flash (gemini)
LLM_TIMEOUT_SEGUNDOS=15        # prazo total da chamada, tentativas incluídas
LLM_MAX_TENTATIVAS=2           # 429, 5xx e falha de conexão são repetidos
LLM_FORMATO_JSON=json_schema   # json_object para modelos sem saída estruturada
LLM_TEMPERATURA=0              # zero por padrão: os agentes extraem e classificam
LLM_SEED=                      # semente da amostragem, para quem a respeita (Groq)
```

Um agente recebe o cliente por dependência e pede a resposta num formato:

```python
class Variacoes(BaseModel):
    buscas: list[str]

@router.post("/triar")
async def triar(cliente: ClienteLLM = Depends(obter_cliente_llm)):
    return await cliente.gerar("Gere buscas para: ...", Variacoes)
```

`gerar` devolve um `Variacoes` já validado ou levanta um erro da camada, que o
gateway traduz sozinho: prazo estourado vira `504 llm_timeout`; provedor fora
do ar, recusa ou resposta fora do schema viram `503 llm_indisponivel`. Toda
chamada deixa uma linha no log `verificador.llm` com o provedor, o modelo, a
latência, os tokens e as tentativas. A chave nunca aparece no log.

Nos testes, o `DubleLLM` (`src/tests/dubles/llm.py`) entra no lugar do
provedor, sem rede e sem chave:

```python
app.dependency_overrides[obter_cliente_llm] = lambda: ClienteLLM(
    DubleLLM({"buscas": ["a", "b"]})
)
```

### Agente Triador (spec 003)

Transforma o trecho que o leitor selecionou nas strings de busca que vão à
OpenAlex, em [`src/agents/triador.py`](backend/src/agents/triador.py). O
trabalho é partido em duas metades, e essa divisão é o desenho:

| Quem | Faz o quê |
| :--- | :--- |
| o LLM | extrai quatro termos do trecho — intervenção, desfecho, condição e população — no jargão inglês da literatura |
| o código | normaliza, aplica o glossário e monta as strings combinando os termos em **eixos fixos** |

A primeira versão pedia ao modelo as strings prontas, e o resultado era
instável: o mesmo trecho achava o estudo numa tentativa e não achava na
seguinte, porque a cada chamada o modelo escolhia outro sinônimo. Tudo o que não
precisa do modelo saiu do modelo.

As instruções dadas ao LLM são arquivos versionados, e não uma f-string:

```
backend/src/agents/orientacoes/triador/
├── ORIENTACOES.md                      # as regras do variador semântico (vai no prompt)
└── referencias/
    ├── glossario.md                    # conceito → termo canônico → variantes (lido pelo código)
    ├── exemplos.md                     # trechos resolvidos (vai no prompt)
    └── formatos-de-busca.md            # os eixos e a montagem (documentação da equipe)
```

Mudar uma regra é uma linha de diff que a equipe revisa em PR. O **glossário**
não é um pedido ao modelo: o código reescreve para o termo canônico qualquer
variante conhecida (`brain shrinkage` → `brain atrophy`), inclusive o conceito
escrito em português e a marca de medicamento (`oxycontin` → `oxycodone`).

Para medir as duas coisas que importam — achar o estudo e achar sempre o mesmo:

```bash
python scripts/eval_triador.py --repeticoes 3
```

O relatório traz a taxa de acerto (meta: ≥ 80%), a estabilidade das buscas entre
rodadas e a lista dos casos que oscilaram. Cada caso que oscila é candidato a uma
linha nova no glossário — o procedimento está no fim de `glossario.md`.

### Agente Juiz (spec 004)

[`src/agents/juiz.py`](backend/src/agents/juiz.py) compara a alegação com os
abstracts recebidos e devolve `sustenta`, `exagera` ou `nada_encontrado` no
schema da extensão. O DOI e os metadados da fonte são conferidos contra a
entrada; estudo retratado não pode sustentar a alegação. É a última etapa de
`/verificar` (ver [Agente Pesquisador e esteira](#agente-pesquisador-e-esteira-spec-022)).
Internamente, o LLM declara primeiro se a evidência é compatível, parcial ou
ausente; o código rejeita um estado incompatível com essa relação antes de
montar o veredito.

O conjunto inicial tem 40 casos **sintéticos**, identificados no JSONL. Eles
testam a classificação e o formato, mas não representam evidência científica
real. Na pasta `backend/`, execute:

```bash
python scripts/eval_juiz.py --validar-dataset  # apenas confere os rótulos, sem chave
python scripts/eval_juiz.py --caso S02 --caso S03  # diagnóstico parcial com LLM
python scripts/eval_juiz.py --caso E02 --mostrar-justificativa
python scripts/eval_juiz.py --intervalo 10       # conjunto completo, pausa entre casos
```

As execuções com LLM precisam de `DATABASE_URL` e `LLM_API_KEY` locais. O relatório
separa acerto do estado, `sustenta` sem abstract relacionado e `sustenta` com
estudo retratado. Sem rodar o conjunto inteiro, as taxas de aceite **não foram medidas**.
O diagnóstico por `--caso` mostra apenas a categoria segura da falha, sem
resposta bruta ou segredo, e **não** valida a meta de acerto do conjunto inteiro.
`--mostrar-justificativa` exibe apenas o texto do veredito já validado e exige
`--caso`; use-o somente com os exemplos sintéticos ou dados autorizados. Em
`429`, o runner mostra `Retry-After` e os contadores conhecidos do Groq, quando
presentes, e interrompe a rodada para não desperdiçar chamadas. `--intervalo`
reduz a frequência, mas não garante que uma quota diária ou de tokens não seja
atingida. O tipo exato aparece como "não identificado" quando o provedor não o
informa nos dados seguros disponíveis.

### Agente Pesquisador e esteira (spec 022)

`POST /verificar` encadeia as três etapas, e a rota só orquestra:

1. **Triador** ([`triador.py`](backend/src/agents/triador.py)) — gera as buscas e
   os conceitos do trecho. Os conceitos (intervenção, desfecho, condição,
   população) vão para o campo `termos` do veredito, que a extensão mostra como
   etiquetas. Se o LLM falhar, segue só com o trecho original e `termos` vazio.
2. **Pesquisador** ([`pesquisador.py`](backend/src/agents/pesquisador.py)) — sem
   LLM. Para cada busca, consulta o cache e, se não houver, a OpenAlex; as
   buscas externas rodam em paralelo, no máximo `PESQUISADOR_CONCORRENCIA` (padrão
   `5`) ao mesmo tempo. Junta tudo intercalando por posição, sem repetir o mesmo
   DOI, e entrega até 5 trabalhos. Busca que falha só reduz a cobertura; todas
   falhando viram `503 openalex_indisponivel`.
3. **Juiz** — descarta trabalhos sem abstract ou DOI e decide o veredito.

O veredito é gravado na tabela `veredito`, e o `id` devolvido é o que
`POST /feedback` usa. Se a gravação falhar, o leitor recebe o mesmo veredito com
`id = null`.

O cache ainda não existe: [`cache.py`](backend/src/services/cache.py) define só o
contrato `CacheDeBuscas` e o padrão `SemCache`. Quem implementar o cache entrega
a instância ao Pesquisador em `src/api/gateway/dependencias.py`.

### Busca na OpenAlex (spec 002)

`POST /buscar` recebe uma **lista** de strings de busca e devolve os trabalhos
numa lista única, sem repetição. Por baixo é
[`src/services/openalex.py`](backend/src/services/openalex.py): `httpx` sobre a
API REST da OpenAlex, sem camada de protocolo no meio.

`POST /buscar` é a busca **crua**, para testes manuais (Postman, `/docs`): não
passa pelo Triador nem pelo Juiz. A esteira de `/verificar` não chama esta rota;
quem busca por ela é o Pesquisador, por chamada de função.

Cada string vai para a OpenAlex sem alteração, então a sintaxe dela vale: aspas
para frase exata, `AND`, `OR` e `NOT` em maiúsculas, e parênteses para agrupar.
Os parênteses **agrupam de verdade** — a mesma consulta devolve 4.293 resultados
agrupada e 189 sem eles, então não os remova ao montar a busca.

Configure o e-mail do *polite pool* antes de usar; sem ele o cliente recusa a
subir:

```bash
OPENALEX_MAILTO=contato-da-equipe@exemplo.org
OPENALEX_API_KEY=                  # gratuita; veja o aviso abaixo
OPENALEX_RESULTADOS_POR_BUSCA=10   # por busca, teto de 50
OPENALEX_TIMEOUT_SEGUNDOS=10
OPENALEX_MAX_TENTATIVAS=3          # 429, 5xx e timeout são repetidos
```

> **A chave importa mais do que parece.** Sob carga, a OpenAlex responde `503`
> com *"Anonymous search is paused… use a free API key"* — e considera anônimo
> quem manda só o `mailto`. A chave é gratuita em
> <https://openalex.org/rest-api>. Sem ela a busca funciona, mas de forma
> intermitente. A chave vai no cabeçalho `Authorization`, nunca na URL.

Experimente pelo venv, sem subir a API:

```bash
cd verificador/backend
python3 - <<'FIM'
import asyncio
from src.services.openalex import ClienteOpenAlex

async def principal():
    buscas = ["polylaminin spinal cord injury", "polylaminin regeneration"]
    async with ClienteOpenAlex.a_partir_das_configuracoes() as cliente:
        resultado = await cliente.buscar_varias(buscas, quantidade=3)
    for trabalho in resultado.trabalhos:
        print(trabalho.id, trabalho.ano, trabalho.doi, trabalho.titulo)
    for busca, motivo in resultado.falhas.items():
        print("falhou:", busca, "->", motivo)

asyncio.run(principal())
FIM
```

Cada trabalho vem com `id` (`W2110406916`), `titulo`, `ano`, `doi` (forma curta,
sem `https://doi.org/`), `retratado`, `abstract`, `relevancia` e `citacoes`.
Registro incompleto devolve `None` no campo que falta, e não derruba a busca.

### Quantos trabalhos vêm, e quais

**Cinco, por padrão** — o top 5 que a OpenAlex já ordenou por relevância. Não há
reclassificação nossa, nem clusterização: ela ordena, a gente aproveita.

Isso importa por causa da conta. Uma consulta de revisão sistemática casa com
milhares de trabalhos, e mandar todos para um LLM é inviável:

| Amostra | Abstracts em tokens |
| :--- | ---: |
| top 5 | ~1,4 mil |
| todos os 4.293 de uma consulta real | ~1,19 milhão |

`total_por_busca` diz quantos casaram ao todo, antes do corte — é a diferença
entre "achei 5" e "achei 5 de 4.293".

Com **várias** buscas, a lista final intercala por **posição**: o 1º de cada,
depois o 2º de cada. Não por `relevancia`, porque o escore mede o quanto o
trabalho casa com *aquela* string, e a escala muda com a string — medido, para o
mesmo assunto: 870 na formulação curta contra 227 na longa. Ordenar por ele daria
todas as vagas à busca mais curta.

Três parâmetros:

| Parâmetro | O que faz | Padrão |
| :--- | :--- | :--- |
| `limite` | quantos saem no fim | 5 |
| `quantidade` | candidatos por busca, antes de juntar | 10 (teto 200) |
| `ordenar_por` | `relevancia`, `citacoes` ou `ano` | `relevancia` |

Fora de `relevancia`, a OpenAlex devolve o campo `relevancia` nulo — ela só o
calcula quando é o critério. Uma busca que falhar aparece em `resultado.falhas` sem
levar as outras junto — o erro só sobe como `OpenAlexIndisponivel` se nenhuma
funcionar. Nenhuma exceção do `httpx` atravessa a fronteira do módulo.

### Testar pelo Postman, Bruno ou curl

```bash
cd verificador/backend
python3 -m uvicorn src.main:app --reload --port 8000
```

```bash
curl -s -X POST http://localhost:8000/buscar -H 'Content-Type: application/json' \
  -d '{"buscas":["polylaminin spinal cord injury","polylaminin regeneration"]}'
```

Há uma coleção Bruno pronta em [`verificador/bruno/`](bruno/README.md), com as
três rotas e os casos de erro. No Bruno: **Open Collection** → aponte para a
pasta → ambiente `Local`. No Postman, importe
`http://localhost:8000/openapi.json`.

Os testes unitários não tocam a rede: usam as respostas gravadas em
`src/tests/fixtures/openalex/`. O teste que fala com a OpenAlex de verdade está
marcado `rede` e fica fora da execução padrão — rode à mão quando desconfiar de
fixture velha:

```bash
cd verificador/backend
python3 -m pytest -m rede
```

### 2. Extensão (terminal 2)

Inicie a API pelo Compose (passo 1A) ou pelo venv (passo 1B) antes de testar a
extensão. Ambos expõem `/verificar` e `/health`.

```bash
cd verificador/extensao
npm install                # só na primeira vez
npm run dev                # Chrome
npm run dev:firefox        # Firefox
```

O WXT abre um navegador novo (perfil limpo, descartável), com a extensão já
carregada e com **hot-reload**: salvou um arquivo, a extensão recarrega sozinha.

Ele já abre em duas abas — a `pagina-teste.html` local e o verbete
*Medula espinhal* da Wikipédia —, que são exatamente os dois alvos do roteiro
abaixo. Isso vem de `webExt.startUrls` no `wxt.config.ts`. O caminho da
`pagina-teste.html` é derivado da localização do próprio `wxt.config.ts`, então
funciona em qualquer clone, nos três sistemas — não edite o arquivo à mão.

## Roteiro de teste manual

1. Com os dois terminais rodando, vá para a primeira aba que o WXT abriu — a
   `pagina-teste.html`.
   - No **Firefox** funciona direto (o content script casa `file:///*`).
   - No **Chrome**, `file://` ainda exige liberar à mão: `chrome://extensions`
     → "Verificador Cientifico" → **Detalhes** → ligar *Permitir acesso a URLs
     de arquivo*. Ou pule para a aba da Wikipédia.
2. **Selecione uma frase** (10 caracteres ou mais). O botão azul **"Verificar"**
   aparece logo acima da seleção.
3. **Clique no botão.** O painel abre no canto inferior direito com o badge
   cinza "VERIFICANDO…" e o trecho selecionado entre aspas.
4. Em alguns segundos o painel troca para o veredito calculado:
   - o badge do estado (**SUSTENTA**, **EXAGERA** ou **NADA ENCONTRADO**)
   - a justificativa em português, escrita pelo Juiz
   - quando há estudo, o título, o ano e o link **Abrir publicação** para o DOI
   - as etiquetas com os conceitos que o Triador reconheceu no trecho
5. **Olhe o terminal 1 (uvicorn).** Deve aparecer a requisição respondida:
   ```
   POST /verificar HTTP/1.1" 200 OK
   ```
   Um `503` ali quase sempre é `LLM_API_KEY` ou `OPENALEX_MAILTO` vazio no
   `.env`; o motivo aparece no log logo acima.
6. **Repita em 2 sites reais** (critério de pronto da fase):
   - a segunda aba, https://pt.wikipedia.org/wiki/Medula_espinhal
   - um portal de notícias (ex.: https://g1.globo.com — abra uma matéria)
   Funcionando nos dois, o encanamento não depende da página.
7. **Repita tudo no outro navegador**, se tiver o Chrome (`npm run dev`).
8. Feche o painel no `×` e confirme que uma nova seleção reabre o fluxo.

### Painel de veredicto — roteiro da task #15

- Confira que o link do DOI abre em outra aba; o painel original permanece aberto.
- Pare o backend e verifique novamente. O painel deve exibir uma mensagem de conexão em português e o botão **Tentar novamente**, sem mostrar `localhost`, porta ou stack. Reinicie o backend e clique em **Tentar novamente** sem selecionar outro trecho; o mesmo texto deve ser enviado.
- Para testar o cancelamento, clique em **Verificar** e feche o painel enquanto ele mostra **Verificando…**. A resposta tardia não pode reabrir o painel.
- Confira os estados **Sustenta**, **Exagera** e **Nada encontrado**, além do aviso **Estudo retratado** e do erro. Com a esteira real, o estado depende do trecho: escolha alegações diferentes para ver cada um. Não trate o build como evidência de teste visual desses estados.
- Repita no Chrome e no Firefox; anexe capturas dos três estados e do erro ao PR. Os testes automatizados da apresentação ficam em `extensao/tests/` e podem ser executados com `npm test`.

## Checklist da Fase 01

> Histórico: este era o critério de pronto da Fase 01, com o veredito mock. Desde
> a spec 022, `/verificar` usa IA e OpenAlex, e não imprime mais o trecho no log:
> os itens do log do uvicorn, do veredito mock e de "nada de IA" não valem mais.

- [ ] Selecionar texto faz surgir o botão "Verificar"
- [ ] Clicar mostra o painel em estado "carregando"
- [ ] O trecho correto aparece no log do uvicorn
- [ ] O painel exibe o veredito mock
- [ ] Funciona em 2 sites diferentes
- [ ] Funciona no Chrome **e** no Firefox
- [ ] Nada de IA, nada de OpenAlex

## Se der errado

| Sintoma | Causa provável |
|---|---|
| Painel mostra **ERRO: Failed to fetch** | uvicorn não está rodando, está em outra porta, ou o build aponta para outra base — o console do background imprime a base ativa ao iniciar |
| O botão não aparece | selecione 10+ caracteres; recarregue a página (o content script só entra em páginas carregadas **depois** da extensão) |
| Nada acontece ao clicar | abra o console do background (Chrome: `chrome://extensions` → *service worker*; Firefox: `about:debugging#/runtime/this-firefox` → *Inspecionar*) e veja os logs `[verificador]` |
| Painel sem estilo / quebrado | é shadow DOM `closed`, o CSS da página não deveria vazar — reporte a URL |
| O WXT diz *"Load .output/... manually"* e não abre nada | falta o `web-ext` (`npm i -D web-ext`) ou o navegador não está instalado |
| Chrome não abre nada com `npm run dev` | Chrome não instalado (`brew install --cask google-chrome`) |

## Carregar manualmente (sem `npm run dev`)

```bash
npm run build            # gera .output/chrome-mv3
npm run build:firefox    # gera .output/firefox-mv2
```

- **Chrome:** `chrome://extensions` → *Modo do desenvolvedor* → *Carregar sem
  compactação* → selecione `.output/chrome-mv3`
- **Firefox:** `about:debugging#/runtime/this-firefox` → *Carregar extensão
  temporária* → selecione `.output/firefox-mv2/manifest.json`

## Apontar o build para outro back-end

A URL do back-end não está escrita no código: ela vem de `WXT_API_BASE_URL`,
lida **no momento do build**. Sem a variável, vale `http://localhost:8000`.

```bash
cd verificador/extensao
WXT_API_BASE_URL=https://api.exemplo.com npm run build
WXT_API_BASE_URL=https://api.exemplo.com npm run build:firefox
```

Para não repetir a variável a cada comando, copie o exemplo e edite:

```bash
cp .env.example .env      # só na primeira vez; o .env não entra no versionamento
```

A variável vale para `dev`, `build` e `zip`, nos dois navegadores. O prefixo
`WXT_` é obrigatório: é ele que faz o valor chegar ao código empacotado.

Mudar o valor muda três coisas de uma vez, sem editar arquivo nenhum:

- o `background.ts` passa a chamar `<base>/verificar`;
- as `host_permissions` do manifest passam a pedir apenas `<base>/*` — o build
  não sai com permissão para um host que não vai usar;
- o console do background imprime a base ativa ao iniciar
  (`[verificador] background pronto — https://api.exemplo.com/verificar`), que
  é a forma mais rápida de descobrir para onde um `.output/` aponta.

A base precisa ser uma URL absoluta `http` ou `https`, sem query nem fragmento.
Fora disso o build falha com a mensagem do erro, em vez de gerar um artefato
que só quebra no primeiro `fetch` do usuário.

Os caminhos das rotas (`/verificar`, `/health`) ficam em `extensao/config.ts` —
é o único arquivo a mudar quando o back-end ganhar uma rota nova. Nenhum
entrypoint monta URL por conta própria.

Trocar de back-end exige recarregar a extensão (`npm run dev` já faz isso; no
build manual, recarregue o `.output/`): a permissão de host vive no manifest,
lido só na instalação.

## Notas de compatibilidade

- **Chrome → MV3** (service worker); **Firefox → MV2** (background script), que
  é o padrão do WXT. Vale a pena: no MV3 do Firefox as `host_permissions` são
  *opcionais* e exigiriam que o usuário as concedesse à mão em `about:addons`.
  No MV2 o WXT move essas entradas para `permissions`, concedidas na instalação.
- `browser.runtime.sendMessage` devolve Promise nos dois navegadores; no
  background o listener usa `sendResponse` + `return true`, que é o único
  formato aceito pelo Chrome para resposta assíncrona.

## Testar no Safari

O Safari não carrega o `.output/` direto: cada extensão precisa virar um **app
nativo** empacotado pelo Xcode. Funciona, mas **não há hot-reload** — cada
mudança vira rebuild + ⌘R. Use Chrome/Firefox no dia a dia e o Safari só como
verificação final.

### Pré-requisito

**Xcode completo** (~10 GB, App Store). As Command Line Tools sozinhas não
bastam: é o Xcode que traz o `safari-web-extension-converter`.

```bash
sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
xcrun --find safari-web-extension-converter   # deve imprimir um caminho
```

### 1. Gerar o projeto Xcode (uma vez)

```bash
cd verificador/extensao
./scripts/safari.sh converter
```

Isso roda `npm run build` e converte o `.output/chrome-mv3` em um projeto Xcode
em `verificador/safari/`. Convertemos o build **MV3 do Chrome** de propósito: o
Safari 16.4+ roda MV3, e o alvo `safari-mv2` do WXT já nasce depreciado.

### 2. Compilar e instalar

1. Abra `verificador/safari/Verificador Cientifico/Verificador Cientifico.xcodeproj`
2. Selecione o target do app → aba **Signing & Capabilities** → em *Team*
   escolha sua conta pessoal (Apple ID grátis serve) ou deixe *None*
3. **⌘R**. Um app de container abre — pode fechá-lo, ele só instala a extensão.

### 3. Liberar no Safari

Três passos, todos obrigatórios:

1. Safari → Ajustes → **Avançado** → ligar *Mostrar recursos para
   desenvolvedores web*
2. Menu **Desenvolvedor** → *Permitir Extensões Não Assinadas*
   ⚠️ **isso volta a desligar toda vez que o Safari reinicia** — se a extensão
   sumir, é quase sempre isso
3. Safari → Ajustes → **Extensões** → marcar *Verificador Cientifico* e, no
   painel da direita, mudar o acesso a sites para **Permitir em Todos os Sites**
   (o padrão é *Perguntar*, e nesse modo o content script não roda)

### 4. Testar

Mesmo roteiro manual da seção acima, com duas diferenças:

- **Não use `file://`** — o Safari não dá acesso a arquivos locais para
  extensões. Teste direto na Wikipédia e num portal de notícias.
- Para ver os logs do background: menu **Desenvolvedor** → *Web Extension
  Background Content* → *Verificador Cientifico*.

### 5. Ciclo de mudança

```bash
./scripts/safari.sh sincronizar   # rebuild + copia pro projeto Xcode
```

Depois volte ao Xcode e dê ⌘R. Não precisa reconverter.

### Se der errado no Safari

| Sintoma | Causa |
|---|---|
| Extensão sumiu da lista | *Permitir Extensões Não Assinadas* desligou no restart |
| Botão não aparece em site nenhum | acesso a sites está em *Perguntar*; mude para *Permitir em Todos os Sites* |
| **Failed to fetch** só no Safari | o Safari é mais rígido com `localhost`; confirme que o uvicorn está de pé, teste `http://127.0.0.1:8000/health` no próprio Safari e, se for o caso, refaça o build com `WXT_API_BASE_URL=http://127.0.0.1:8000` |
| `xcrun: error: unable to find utility` | Xcode não instalado ou `xcode-select` apontando para as CLT |

## Próxima migração

As próximas etapas substituem o veredicto fixo em `backend/src/api/gateway/routes.py`
por aquisição e análise de evidências reais.
A extensão **não muda** — é a prova de que o contrato JSON está bem definido.
