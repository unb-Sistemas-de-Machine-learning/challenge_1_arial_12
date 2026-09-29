# Plano — 012 Limite de requisições por origem

## 1. Abordagem

Adicionar um middleware de janela fixa em memória, por `Origin`, dentro de
`api/gateway/middlewares.py`, registrado **antes** de `registrar_tratamento_erros`
e do `CorsComErroPadronizado` em `main.py`. Starlette empilha middleware na
ordem inversa de registro — o último registrado é o mais externo e vê a
requisição primeiro — então registrar o limite primeiro o deixa por dentro dos
outros dois: a correlação já definiu `request.state.id_correlacao` quando o
limite roda, e a resposta `429` ainda atravessa o CORS a caminho de volta e
recebe `Access-Control-Allow-Origin`. O middleware ignora `GET /health` por
caminho e, ao negar, monta a
mesma `Erro` da `011` com `_resposta_erro(CodigoErro.LIMITE_EXCEDIDO, 429, ...)`
e `Retry-After` calculado a partir do tempo restante da janela — nenhuma
mudança no contrato de erro é necessária. O limite e a janela viram campos de
`Settings` (`006`), lidos uma vez na criação do app. O comportamento de CORS
por ambiente (critério 3) já existe desde a `006`; esta spec só acrescenta o
teste de regressão que trava a combinação `APP_DEBUG` + `CORS_ORIGINS`.

## 2. Arquivos tocados

| Arquivo | O que muda |
| :--- | :--- |
| `verificador/backend/src/core/config/settings.py` | `rate_limit_max_requests` e `rate_limit_window_seconds` |
| `verificador/backend/src/api/gateway/middlewares.py` | `ContadorDeJanelaFixa` e `registrar_limite_de_taxa` |
| `verificador/backend/src/main.py` | Registro do middleware de limite antes da correlação e do CORS |
| `verificador/backend/.env.example` | Documentar `RATE_LIMIT_MAX_REQUESTS` e `RATE_LIMIT_WINDOW_SECONDS` |
| `verificador/README.md` | Variáveis novas e nota sobre `429`/`Retry-After` |
| `verificador/backend/src/tests/unit/test_limite_de_taxa.py` | `ContadorDeJanelaFixa` isolado, com relógio controlável |
| `verificador/backend/src/tests/integration/test_limite_de_taxa.py` | `429` + `Retry-After`, isolamento por origem, `/health` isento, CORS por ambiente |

## 3. Contratos

```python
class ContadorDeJanelaFixa:
    def __init__(
        self,
        limite: int,
        janela_segundos: int,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None: ...

    def registrar(self, chave: str) -> tuple[bool, int]:
        """True e 0 quando permitida; False e os segundos até a janela abrir
        quando negada."""
```

Resposta negada (HTTP `429`):

```json
{"codigo": "limite_excedido", "mensagem": "Limite de solicitações excedido."}
```

com cabeçalho `Retry-After: <segundos>` e `X-Correlation-ID` como qualquer
outra resposta de erro da `011`.

`Settings` ganha:

```python
rate_limit_max_requests: int = 30
rate_limit_window_seconds: int = 60
```

correspondendo a `RATE_LIMIT_MAX_REQUESTS` e `RATE_LIMIT_WINDOW_SECONDS` no
ambiente, seguindo o mesmo mapeamento implícito de `app_debug`/`APP_DEBUG`.

## 4. Decisões técnicas

| Decisão | Alternativa descartada | Por quê |
| :--- | :--- | :--- |
| Contagem por `Origin` (cai para o IP do cliente quando ausente) | Contagem por IP | O Gateway já usa `Origin` para CORS; é o identificador estável da extensão, e a task pede limite "por origem" |
| Janela fixa em memória (`dict` por chave) | Sliding window log, token bucket, Redis | Processo único no Compose; janela fixa é suficiente para o objetivo de custo e não introduz dependência nova nesta entrega |
| Middleware registrado antes da correlação e do CORS (fica mais interno, pois Starlette empilha do último registrado para o primeiro) | Registrar depois dos dois | Precisa de `request.state.id_correlacao` já definido, e a resposta `429` só recebe `Access-Control-Allow-Origin` se atravessar o `CorsComErroPadronizado` a caminho de volta |
| Reaproveitar `_resposta_erro`/`CodigoErro.LIMITE_EXCEDIDO` da `011` | Criar um novo código ou schema de erro | O contrato de erro já reserva `429` para esse código; duplicar quebraria a regra de ouro de não alterar contrato existente sem necessidade |
| Relógio injetável (`time.monotonic` por padrão) | Testar com `time.sleep` real | Mantém os testes de janela rápidos e determinísticos |
| Não alterar o default de `CORS_ORIGINS` | Trocar o default para uma lista vazia | Mudaria o contrato assinado pela `006` e quebraria o comportamento hoje testado; a spec só valida a combinação com `APP_DEBUG`, quem decide a lista real é quem sobe o ambiente |

## 5. Como testar

- **Unit:** `ContadorDeJanelaFixa` com relógio falso — primeira requisição
  permitida, N+1 dentro da janela negada com o número de segundos restante,
  chave diferente não interfere, após avançar o relógio além da janela a
  contagem reinicia.
- **Integração:** `TestClient` com `Settings(_env_file=None, ...)` de limite
  baixo (ex.: 2 por segundo) — confirmar `429` com `Retry-After` na N+1ª
  chamada da mesma origem, liberação após avançar o relógio monkeypatchado,
  isolamento entre duas origens distintas, `GET /health` respondendo mesmo
  depois de esgotar o limite de `/verificar`. CORS por ambiente: com
  `app_debug=True` e `cors_origins=["*"]` qualquer `Origin` recebe o
  cabeçalho; com `app_debug=False` e `cors_origins=["https://permitida.example"]`
  uma origem fora da lista não recebe `Access-Control-Allow-Origin`.
- **Eval:** não se aplica; não há LLM nesta feature.

## 6. Riscos

- **Múltiplos workers do Uvicorn:** a contagem em memória não é compartilhada
  entre processos; documentado como limite conhecido, fora de escopo nesta
  entrega (o Compose atual roda um único processo).
- **Vazamento de memória do dicionário de contagem:** origens antigas nunca
  são removidas. Aceitável no volume esperado da extensão (poucas origens
  distintas); se crescer, revisar com uma limpeza periódica ou TTL numa spec
  futura.
- **Cabeçalho `Origin` ausente** (chamada direta via `curl`, por exemplo): cai
  para o IP do cliente da conexão, para não ficar sem limite algum.
- **Ordem de registro de middleware no Starlette é contra-intuitiva:**
  `add_middleware`/`@api.middleware("http")` inserem no início da lista
  interna, então o **último** registrado vira o **mais externo** — o oposto
  do que pareceria natural lendo `main.py` de cima para baixo. Confirmado
  lendo `Starlette.build_middleware_stack` e reproduzindo com um app mínimo
  antes de fixar a ordem final; qualquer novo middleware de gateway deve
  repetir essa checagem antes de assumir a posição na pilha.
