# Verificador Científico — contrato de verificação (spec 010)

Prova o circuito completo **sem IA e sem OpenAlex**:
seleção de texto → botão → background → back-end → veredito mock → painel.

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
│   ├── src/main.py        # aplicação FastAPI: POST /verificar; GET /health
│   ├── docker-compose.yml # api + db; inicia src.main:app
│   ├── requirements.txt
│   └── .venv/             # criado localmente
├── extensao/
│   ├── wxt.config.ts      # manifest por navegador (Chrome MV3 / Firefox MV2)
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
  -d '{"trecho":"teste","url":"http://x"}'
```

Deve voltar o JSON mock. **Só avance quando isso funcionar.**

O healthcheck responde em `http://localhost:8000/health` com `{"ok":true}`.
O backend lê `.env` na inicialização. `DATABASE_URL` precisa estar preenchida,
mas o healthcheck não conecta ao banco; `OPENAI_API_KEY` e `OPENALEX_MAILTO` podem ficar
vazios nesta fase. `CORS_ORIGINS` aceita uma lista JSON de origens e, por padrão,
mantém `['*']`.

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
abaixo. Isso vem de `webExt.startUrls` no `wxt.config.ts`.

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
4. Em menos de um segundo o painel troca para:
   - badge laranja **EXAGERA**
   - justificativa `(mock) Resposta de teste — a IA entra na Fase 04.`
   - o estudo `(mock) Estudo de exemplo · 2019 · doi:10.0000/mock`
   - as três tags `polylaminin`, `spinal cord injury`, `regeneration`
5. **Olhe o terminal 1 (uvicorn).** Deve ter impresso exatamente o trecho que
   você selecionou:
   ```
   [verificar] url=file:///.../pagina-teste.html
   [verificar] trecho='A polilaminina vai revolucionar...'
   POST /verificar HTTP/1.1" 200 OK
   ```
   Esse é o teste que realmente importa: prova que o texto atravessou os três
   processos sem se perder.
6. **Repita em 2 sites reais** (critério de pronto da fase):
   - a segunda aba, https://pt.wikipedia.org/wiki/Medula_espinhal
   - um portal de notícias (ex.: https://g1.globo.com — abra uma matéria)
   Funcionando nos dois, o encanamento não depende da página.
7. **Repita tudo no outro navegador**, se tiver o Chrome (`npm run dev`).
8. Feche o painel no `×` e confirme que uma nova seleção reabre o fluxo.

## Checklist da Fase 01

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
| Painel mostra **ERRO: Failed to fetch** | uvicorn não está rodando, ou está em outra porta |
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
| **Failed to fetch** só no Safari | o Safari é mais rígido com `localhost`; confirme que o uvicorn está de pé e teste `http://127.0.0.1:8000/health` no próprio Safari |
| `xcrun: error: unable to find utility` | Xcode não instalado ou `xcode-select` apontando para as CLT |

## Próxima migração

As próximas etapas substituem o veredicto fixo em `backend/src/api/gateway/routes.py`
por aquisição e análise de evidências reais.
A extensão **não muda** — é a prova de que o contrato JSON está bem definido.
