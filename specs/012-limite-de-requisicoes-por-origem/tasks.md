# Tarefas — 012 Limite de requisições por origem

- [x] 1. Escolher e justificar no `plan.md` a estratégia de contagem (janela
      fixa em memória, por `Origin`).
- [x] 2. Acrescentar `rate_limit_max_requests` e `rate_limit_window_seconds`
      a `Settings`, com default documentado.
- [x] 3. Implementar `ContadorDeJanelaFixa` com relógio injetável, em
      `middlewares.py`.
- [x] 4. Implementar `registrar_limite_de_taxa` (middleware) reaproveitando
      `_resposta_erro`/`CodigoErro.LIMITE_EXCEDIDO`, ignorando `GET /health`.
- [x] 5. Registrar o middleware em `main.py`, depois do CORS.
- [x] 6. Escrever o teste unitário do contador (permite, nega, reinicia,
      isola por chave).
- [x] 7. Escrever os testes de integração: `429` + `Retry-After` na N+1ª
      chamada, liberação após a janela, isolamento entre origens, `/health`
      isento.
- [x] 8. Escrever o teste de regressão de CORS por ambiente
      (`APP_DEBUG` × `CORS_ORIGINS`).
- [x] 9. Documentar `RATE_LIMIT_MAX_REQUESTS` e `RATE_LIMIT_WINDOW_SECONDS`
      no `.env.example` e no README.

## Antes de abrir o PR de implementação

- [x] Todos os critérios de aceite da spec têm teste correspondente
- [x] `spec.md` atualizado com o que mudou durante a implementação
- [x] Status da spec alterado para `implementada`
- [x] Linha da spec atualizada no índice (`specs/README.md`)
