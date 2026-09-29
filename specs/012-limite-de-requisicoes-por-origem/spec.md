# 012 - Limite de requisições por origem

| Campo | Valor |
| :--- | :--- |
| **Status** | implementada |
| **Autor** | Pedro Mota |
| **Branch** | `feature/012-limite-de-requisicoes-por-origem` |
| **Depende de** | `006`, `010`, `011` |

---

## 1. Objetivo

Impedir que uma origem sem limite consuma tokens de LLM e cota da OpenAlex sem
controle, e garantir que o CORS aberto do stub não sobreviva fora do ambiente
de desenvolvimento.

## 2. Contexto

O [Gateway](../../docs/pages/arquitetura.md) já concentra CORS (`006`), as
rotas `/verificar` e `/health` (`010`) e o contrato de erro padronizado
(`011`), que já reserva `CodigoErro.LIMITE_EXCEDIDO` para HTTP `429`. Falta a
peça que efetivamente conta requisições e nega as que passam do limite — hoje
`allow_origins` pode ser `["*"]` e nada impede volume ilimitado de chamadas a
`/verificar`, cada uma com custo real de LLM e de cota da OpenAlex.

## 3. Critérios de aceite

1. Existe um limite de requisições por origem, configurável por variável de
   ambiente, com valor padrão documentado no `.env.example` e no README.
2. Uma requisição que ultrapassa o limite na janela atual responde HTTP `429`
   com o cabeçalho `Retry-After` e o corpo `{"codigo":"limite_excedido",...}`
   já definido pela `011`.
3. Com `APP_DEBUG=true` (padrão de desenvolvimento), o CORS aceita a origem
   liberada (`CORS_ORIGINS` por padrão `["*"]`); com `APP_DEBUG=false`, apenas
   as origens presentes em `CORS_ORIGINS` recebem cabeçalho
   `Access-Control-Allow-Origin` — uma origem fora da lista não recebe.
4. `GET /health` nunca é limitado, mesmo depois de esgotar o limite de outra
   rota — o healthcheck do Compose depende dele para decidir se o container
   está pronto.
5. Um teste comprova que a N-ésima requisição de uma origem dentro da janela é
   bloqueada com `429` e que a mesma origem volta a ser aceita depois que a
   janela expira; outra origem, nesse meio tempo, não é afetada pelo limite da
   primeira.

## 4. Fora de escopo

- Limitar por IP ou por usuário autenticado — a contagem é por cabeçalho
  `Origin`, que é o que o Gateway já usa para CORS e o que identifica a
  extensão instalada.
- Armazenamento compartilhado entre processos (Redis ou banco) para a
  contagem. A API roda como processo único no Compose; a contagem em memória
  fica documentada como limite conhecido em caso de múltiplos workers.
- Limites diferentes por rota — o mesmo limite vale para toda rota que não seja
  `/health`.
- Qualquer mudança no contrato de erro da `011` — `CodigoErro.LIMITE_EXCEDIDO`
  e o status `429` já existem e são reaproveitados como estão.
- Mudar o valor padrão de `CORS_ORIGINS` (`["*"]`) definido na `006`. A `006`
  já torna a lista configurável por ambiente; esta spec testa que a
  combinação com `APP_DEBUG` funciona como o time de implantação espera, sem
  alterar o default.

## 5. Perguntas em aberto

- [x] A contagem é por `Origin`, não por IP — resolvido: é o único
  identificador estável do cliente que o Gateway já usa (CORS).

## 6. Histórico

| Data | Mudança |
| :--- | :--- |
| 2026-09-24 | Criação da spec |
