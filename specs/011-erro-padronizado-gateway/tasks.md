# Tarefas — 011 Tratamento de erro padronizado no Gateway

- [x] 1. Definir o enum fechado de códigos e o schema `Erro`.
- [x] 2. Implementar a exceção de falha prevista e o mapeamento HTTP.
- [x] 3. Registrar handlers para validação, exceções HTTP e erro inesperado.
- [x] 4. Gerar e propagar o ID de correlação no cabeçalho.
- [x] 5. Padronizar erros retornados pelo CORS e por respostas HTTP genéricas.
- [x] 6. Documentar respostas de erro de `/verificar` no OpenAPI.
- [x] 7. Traduzir os códigos de erro em mensagens amigáveis na extensão.
- [x] 8. Documentar a tabela de códigos no README.
- [x] 9. Escrever testes de `422`, `429`, `503`, `504`, `500` e casos genéricos.
- [x] 10. Executar testes, lint, formatação e checagem de tipos. 13 testes de banco ficam pendentes de PostgreSQL local/CI.

## Antes de abrir o PR de implementação

- [x] Critérios de aceite cobertos por testes
- [x] Spec atualizada para refletir a implementação
- [x] Status da spec alterado para `implementada`
- [x] Linha da spec atualizada no índice (`specs/README.md`)
