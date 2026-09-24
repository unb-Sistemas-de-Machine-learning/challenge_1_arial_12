# Plano — 011 Tratamento de erro padronizado no Gateway

## 1. Abordagem

Criar um enum e um schema Pydantic para as respostas de erro. Registrar handlers para validação, exceções HTTP e falhas previstas; um middleware atribui o ID de correlação, normaliza respostas de erro restantes e captura falhas inesperadas antes que o modo debug devolva traceback. O CORS envolve esse middleware para manter os cabeçalhos também nos erros; uma resposta de preflight negado usa o mesmo contrato.

## 2. Arquivos tocados

| Arquivo | O que muda |
| :--- | :--- |
| `verificador/backend/src/api/schemas/erro.py` | `CodigoErro` e `Erro` |
| `verificador/backend/src/api/gateway/middlewares.py` | Exceção prevista, handlers, correlação e CORS padronizado |
| `verificador/backend/src/main.py` | Registro dos handlers e middleware |
| `verificador/backend/src/api/gateway/routes.py` | Respostas de erro no OpenAPI |
| `verificador/backend/src/tests/integration/test_erros_gateway.py` | Testes HTTP e de log |
| `verificador/backend/src/tests/integration/test_rotas_verificacao.py` | Atualização do contrato de `422` |
| `verificador/extensao/tipos.ts` | União fechada de códigos de erro |
| `verificador/extensao/entrypoints/background.ts` | Tradução de códigos para mensagens amigáveis |
| `verificador/README.md` | Tabela de códigos e mensagens sugeridas |

## 3. Contratos

```json
{"codigo":"entrada_invalida","mensagem":"Não foi possível validar a solicitação."}
```

O cabeçalho `X-Correlation-ID` contém um UUID. `ErroGateway(CodigoErro.OPENALEX_INDISPONIVEL)` devolve `503`; `ErroGateway(CodigoErro.LLM_TIMEOUT)` devolve `504`. O corpo não contém o ID para manter os dois campos exigidos pela task.

## 4. Decisões técnicas

| Decisão | Motivo |
| :--- | :--- |
| Mensagens públicas constantes por código | Impede vazamento de `detail`, traceback ou entrada inválida |
| UUID validado no cabeçalho de entrada | Permite correlação sem injetar texto arbitrário nos logs |
| Captura de exceções antes do tratamento de debug | Impede resposta HTML ou traceback quando `APP_DEBUG=true` |
| CORS externo aos handlers | Mantém acesso da extensão ao JSON de erro |
| Exceção tipada para OpenAlex e LLM | Mapeia a origem real da falha sem adivinhar pelo status `503` |

## 5. Como testar

- **Integração:** `TestClient` com requisições inválidas, exceções previstas e inesperadas; inspecionar corpo, cabeçalho, CORS, OpenAPI e log capturado.
- **Extensão:** `npm run compile`; verificar que o mapa contém todos os valores da união TypeScript e que não exibe a mensagem crua.
- **Regressão:** suíte completa de backend e extensão; testes de banco podem usar a CI com PostgreSQL.

## 6. Riscos

- Middleware de CORS pode responder ao preflight antes de chegar aos handlers; a resposta negada precisa ser padronizada no próprio middleware.
- Exceções durante envio de respostas em streaming não podem trocar um status já enviado; o gateway não usa streaming nesta entrega.
