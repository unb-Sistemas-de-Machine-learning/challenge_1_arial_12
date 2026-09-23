# Tarefas — 009 Camada de persistência do Verificador

- [x] 1. Acrescentar verificação de saúde ao `db` do Compose e condição no `api`.
- [x] 2. Acrescentar serviço de Postgres ao job `backend` da verificação de PR.
- [x] 3. Declarar `Base`, `Veredito` e `Feedback` em `models.py`.
- [x] 4. Escrever teste de estrutura das tabelas, sem tocar em banco.
- [x] 5. Implementar motor, fábrica de sessões e dependência em `session.py`.
- [x] 6. Acrescentar `lifespan` à fábrica da aplicação, sem conectar na subida.
- [x] 7. Escrever teste que prova o fechamento da sessão quando a rota falha.
- [x] 8. Adicionar Alembic na variante assíncrona e gerar a migração inicial.
- [x] 9. Ler a migração gerada e conferir o schema resultante no banco.
- [x] 10. Escrever teste de divergência entre modelos e migrações.
- [x] 11. Criar as fixtures de banco em `conftest.py`, isoladas por transação.
- [x] 12. Escrever teste que prova o isolamento entre casos.
- [x] 13. Implementar normalização e geração da chave de busca.
- [x] 14. Escrever testes de equivalência e de distinção da chave.
- [x] 15. Implementar as três operações de domínio em `repositories.py`.
- [x] 16. Escrever testes das operações contra Postgres real.
- [x] 17. Executar lint, formatação e a suíte com e sem banco.

## Antes de abrir o PR de implementação

- [x] Critérios de aceite cobertos por testes ou verificação manual
- [x] Spec atualizada para refletir a implementação
- [ ] Status da spec alterado para `implementada` — ao mesclar
- [x] Linha da spec atualizada no índice (`specs/README.md`)
- [ ] Divergência do nome `veredito` × `historico_busca` confirmada com o autor da task
