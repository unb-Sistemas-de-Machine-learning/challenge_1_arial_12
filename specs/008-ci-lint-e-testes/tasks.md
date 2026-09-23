# Tarefas — 008 Verificação automática de lint e testes em cada PR

- [x] 1. Declarar a configuração de `ruff` e `pytest` em `pyproject.toml`.
- [x] 2. Ligar o modo estrito do `pytest-asyncio` e o escopo do laço de eventos.
- [x] 3. Formatar o código existente em commit isolado.
- [x] 4. Criar `.github/workflows/ci.yml` com os jobs `backend` e `extensao`.
- [x] 5. Validar a sintaxe do workflow antes de publicar.
- [x] 6. Abrir o PR e confirmar os dois checks verdes e simultâneos.
- [x] 7. Quebrar um teste de propósito e registrar a execução vermelha.
- [x] 8. Restaurar a asserção e registrar a execução verde seguinte.
- [ ] 9. Ligar os dois checks como obrigatórios na proteção da `main`.
- [ ] 10. Documentar como rodar as mesmas verificações localmente.

## Antes de abrir o PR de implementação

- [x] Critérios de aceite cobertos por testes ou verificação manual
- [x] Spec atualizada para refletir a implementação
- [x] Status da spec alterado para `implementada`
- [x] Linha da spec atualizada no índice (`specs/README.md`)

> As tarefas 9 e 10 ficaram pendentes no merge do PR #24. A 9 depende de
> permissão de administrador; a 10 é a seção de comandos locais no README.
