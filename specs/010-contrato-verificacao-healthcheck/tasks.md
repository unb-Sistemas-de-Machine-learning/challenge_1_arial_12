# Tarefas — 010 Contrato de verificação entre extensão e backend

> A implementação automatizada foi antecipada com autorização do usuário. A revisão da spec, integração com a #7 e verificação manual ainda estão pendentes. Marcar cada item somente após sua verificação.

- [ ] 1. Integrar a fábrica mínima à aplicação definitiva da #7 quando ela estiver disponível.
- [x] 2. Registrar o payload literal de `backend/main.py` como fixture da Fase 01.
- [x] 3. Criar testes unitários dos modelos de entrada, veredicto e enum.
- [x] 4. Criar testes que detectem divergências de campos com `extensao/tipos.ts`.
- [x] 5. Criar teste que detecte divergência dos valores de `Estado` com `extensao/tipos.ts`.
- [x] 6. Criar testes HTTP para `/verificar`, `/health`, `/docs` e `/openapi.json`.
- [x] 7. Criar teste de `/health` com `DATABASE_URL` inválida e sem banco disponível.
- [x] 8. Implementar os modelos Pydantic conforme o contrato da spec.
- [x] 9. Implementar `/verificar` com `response_model`, exemplo OpenAPI e payload fixo da fixture.
- [x] 10. Implementar `/health` sem dependência de banco.
- [x] 11. Registrar as rotas na fábrica mínima e preservar o CORS existente.
- [x] 12. Atualizar Dockerfile e Compose para iniciar `src.main:app`.
- [x] 13. Remover `backend/main.py` após confirmar a paridade do payload.
- [x] 14. Atualizar `verificador/README.md` para o novo ponto de entrada e `/health`.
- [x] 15. Executar os testes automatizados do backend.
- [ ] 16. Executar o roteiro manual com extensão já instalada, sem recompilação.

## Antes de abrir o PR de implementação

- [ ] Todos os critérios de aceite da spec têm teste correspondente ou verificação manual explícita
- [x] `spec.md` atualizado com o que mudou durante a implementação
- [ ] Status da spec alterado para `implementada`
- [x] Linha da spec atualizada no índice (`specs/README.md`)
