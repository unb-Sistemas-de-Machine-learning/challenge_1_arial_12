# 011 — Tratamento de erro padronizado no Gateway

| Campo | Valor |
| :--- | :--- |
| **Status** | implementada |
| **Autor** | Equipe Arial 12 |
| **Branch** | `feature/011-erro-padronizado-gateway` |
| **Depende de** | `010` — contrato de `/verificar` e `/health` |
| **Origem** | [Task #11](https://github.com/unb-Sistemas-de-Machine-learning/challenge_1_arial_12/issues/11) |

---

## 1. Objetivo

Permitir que a extensão mostre mensagens compreensíveis e estáveis quando a API falha, sem expor detalhes internos ao usuário.

## 2. Contexto

O gateway já expõe `POST /verificar` e `GET /health`. Hoje uma entrada inválida usa o corpo padrão do FastAPI e uma exceção inesperada pode produzir HTML ou traceback, especialmente com `APP_DEBUG=true`. A extensão exibe o status ou a mensagem crua da falha. A task #11 padroniza esse limite HTTP antes da integração real com OpenAlex e LLM.

## 3. Critérios de aceite

1. Toda resposta HTTP com status `4xx` ou `5xx` produz JSON com exatamente `codigo` e `mensagem`; `codigo` pertence ao enum fechado `CodigoErro`.
2. O ID de correlação é um UUID no cabeçalho `X-Correlation-ID` de toda resposta. Um UUID recebido nesse cabeçalho é propagado; um valor ausente ou inválido é substituído por um novo UUID.
3. O corpo de um erro `500` inesperado contém `{"codigo":"erro_interno","mensagem":"Ocorreu um erro interno."}` mesmo com `APP_DEBUG=true`. Não contém traceback, caminhos, nomes de variáveis nem valores de configuração.
4. O servidor registra o traceback completo do erro `500` com o mesmo ID de correlação devolvido na resposta.
5. Falhas de validação do corpo da requisição, inclusive JSON malformado, retornam `422` com `codigo: "entrada_invalida"` e mensagem estável, sem ecoar o valor recebido.
6. Uma falha prevista de limite retorna `429` com `codigo: "limite_excedido"`; uma falha prevista da OpenAlex retorna `503` com `codigo: "openalex_indisponivel"`; um timeout previsto do LLM retorna `504` com `codigo: "llm_timeout"`.
7. Respostas HTTP de erro não previstas, como `404`, `405` ou uma resposta `400` de CORS, também usam o mesmo contrato. Detalhes arbitrários de `HTTPException` não aparecem no corpo.
8. A extensão usa `codigo` para escolher o texto exibido. Se não há resposta HTTP ou o código é desconhecido, usa uma mensagem local genérica; não mostra o texto cru do servidor.
9. O OpenAPI documenta o schema `Erro` e as respostas `422`, `429`, `503`, `504` e `500` de `/verificar`.
10. Testes automatizados cobrem `422`, `429`, `503`, `504`, `500`, correlação, ausência de vazamento e formatos genéricos de erro.

### Códigos e mensagens sugeridas para a extensão

| Status | `codigo` | Mensagem sugerida |
| :--- | :--- | :--- |
| 422 | `entrada_invalida` | Revise o texto selecionado e tente novamente. |
| 429 | `limite_excedido` | Muitas solicitações. Aguarde um pouco e tente novamente. |
| 503 | `openalex_indisponivel` | A busca de estudos está indisponível. Tente novamente mais tarde. |
| 504 | `llm_timeout` | A análise demorou demais. Tente novamente. |
| 404 | `recurso_nao_encontrado` | Serviço não encontrado. |
| 405 | `metodo_nao_permitido` | Esta operação não está disponível. |
| 400 e outros `4xx` | `erro_requisicao` | Não foi possível processar a solicitação. |
| 503 genérico | `servico_indisponivel` | Serviço indisponível. Tente novamente mais tarde. |
| 500 e outros `5xx` | `erro_interno` | Não foi possível concluir a verificação agora. |

Falha de conexão sem resposta HTTP é tratada somente na extensão como indisponibilidade de conexão; não é um código devolvido pelo servidor.

## 4. Fora de escopo

- Implementar limite de requisições ou chamadas reais à OpenAlex e ao LLM; esta entrega define os erros que essas integrações deverão lançar.
- Mudar o formato das respostas de sucesso ou o veredito mock de `/verificar`.
- Expor traceback ou detalhes de validação na resposta pública.
- Padronizar erros de configuração que impedem a aplicação de iniciar; eles não são respostas HTTP.

## 5. Comportamento de IA

Não se aplica. O mapeamento de erros é determinístico.

## 6. Perguntas em aberto

Nenhuma para o escopo desta entrega.

## 7. Histórico

| Data | Mudança |
| :--- | :--- |
| 2026-09-23 | Criação da spec a partir da task #11; define `X-Correlation-ID` para preservar o corpo JSON com dois campos |
| 2026-09-23 | Implementação do contrato no gateway e na extensão, com testes HTTP e documentação |
