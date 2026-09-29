# Tarefas — 002 Busca de trabalhos na OpenAlex

- [x] 1. Gravar as fixtures de resposta da OpenAlex e documentar a URL de cada uma.
- [x] 2. Definir `Trabalho`, os erros de domínio e a remontagem do abstract.
- [x] 3. Implementar a requisição: `select`, `per-page`, `mailto` e `User-Agent`.
- [x] 4. Implementar timeout, repetição com espera crescente e `Retry-After`.
- [x] 5. Acrescentar as chaves de configuração e os tetos.
- [x] 6. Aceitar uma lista de buscas, com desduplicação e falha parcial.
- [x] 7. Expor o `id` da OpenAlex e desduplicar por ele.
- [x] 8. Suportar `OPENALEX_API_KEY` no cabeçalho e redigi-la no traceback.
- [x] 9. Expor `total_por_busca`, `relevancia` e `citacoes`.
- [x] 10. Permitir ordenar por relevância, citações ou ano.
- [x] 11. Devolver top 5 por padrão, intercalando as buscas por posição.
- [x] 12. Remover a camada MCP e mover o módulo para `src/services/openalex.py`.
- [x] 13. Expor `POST /buscar` com o contrato de erro da spec 011.
- [x] 14. Bloquear soquete nos testes unitários.
- [x] 15. Escrever os testes do cliente, da rota e o de rede marcado.
- [x] 16. Publicar a coleção Bruno das rotas.
- [x] 17. Documentar a busca no README do verificador.
- [x] 18. Rodar lint, formatação e a suíte completa. 13 testes de banco ficam
       pendentes de PostgreSQL local/CI.

## Antes de abrir o PR de implementação

- [x] Todos os critérios de aceite da spec têm teste correspondente
- [x] `spec.md` atualizado com o que mudou durante a implementação
- [x] Status da spec alterado para `implementada`
- [x] Linha da spec atualizada no índice (`specs/README.md`)

## Pendente para a equipe decidir

- [ ] Atualizar a `arquitetura.md`: o contêiner 6 não é mais MCP Server e o
      contêiner 7 (BERTopic) saiu da esteira. Ver seções 6b e 6c da spec.
- [ ] Registrar a chave gratuita da OpenAlex e pôr em `.env`.
- [ ] Decidir o controle de acesso de `POST /buscar`. Ver seção 6a da spec.
