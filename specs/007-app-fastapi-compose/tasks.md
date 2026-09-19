# Tarefas — 007 Inicialização da API pelo Docker Compose

- [x] 1. Escrever testes da fábrica e do healthcheck.
- [x] 2. Escrever teste de falha antecipada sem `DATABASE_URL`.
- [x] 3. Escrever teste que confirma `/verificar` no stub legado.
- [x] 4. Implementar router do gateway com `/health`.
- [x] 5. Implementar `criar_app()` e `app` em `src/main.py`.
- [x] 6. Ajustar mensagem de configuração ausente para nomear `DATABASE_URL`.
- [x] 7. Migrar o serviço `api` do Compose para `src.main:app`.
- [x] 8. Ajustar Dockerfile para executar a nova app como usuário não-root sem instalar NLP.
- [x] 9. Atualizar README com Compose e uso alternativo do stub.
- [x] 10. Executar testes e lint do backend.
- [x] 11. Verificar `docker compose config` com e sem `.env`.
- [x] 12. Subir `api` e `db` por Compose e testar `/health`.
- [x] 13. Confirmar erro com nome `DATABASE_URL` sem `.env`.

## Antes de abrir o PR de implementação

- [x] Critérios de aceite cobertos por testes ou verificação manual
- [x] Spec atualizada para refletir a implementação
- [x] Status da spec alterado para `implementada`
- [x] Linha da spec atualizada no índice (`specs/README.md`)
