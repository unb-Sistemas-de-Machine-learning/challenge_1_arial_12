# Tarefas — 006 Configuração centralizada do backend

> Implementação realizada no stub atual. A revisão formal da spec ainda está pendente.

- [x] 1. Escrever testes unitários para os cinco campos e a leitura isolada da configuração.
- [x] 2. Escrever teste para `CORS_ORIGINS` padrão e uma lista explícita de origens.
- [x] 3. Escrever testes para `DATABASE_URL` ausente, vazia e composta por espaços.
- [x] 4. Escrever teste que comprove que a chave OpenAI e a URL do banco não aparecem em `repr` nem em erro.
- [x] 5. Escrever teste para cache e sobrescrita entre casos de teste.
- [x] 6. Implementar `Settings` com `SettingsConfigDict` e validação de campos obrigatórios.
- [x] 7. Implementar `get_settings()` com `lru_cache`.
- [x] 8. Integrar `get_settings()` ao ponto de entrada ativo para falhar antes da primeira requisição.
- [x] 9. Configurar o middleware CORS a partir de `CORS_ORIGINS`.
- [x] 10. Confirmar que o app inicia com a configuração válida e não precisa conectar ao banco nessa etapa.
- [x] 11. Adicionar `CORS_ORIGINS` a `.env.example` como lista JSON.
- [x] 12. Atualizar o roteiro local para criar `.env` e explicar a validação de `DATABASE_URL`.
- [x] 13. Executar testes unitários e de integração sem usar `.env` pessoal ou serviços externos.

## Antes de abrir o PR de implementação

- [x] Todos os critérios de aceite da spec têm teste correspondente
- [x] `spec.md` atualizado com as decisões tomadas durante a implementação
- [ ] Status da spec alterado para `implementada`
- [x] Linha da spec atualizada no índice (`specs/README.md`)
