# Tarefas - 003 Camada de acesso a LLM

- [x] 1. Definir a interface e o dublê no `plan.md`.
- [x] 2. Trocar `openai_api_key` pelos campos `llm_*` no settings e no `.env.example`.
- [x] 3. Escrever os testes da camada com o `DubleLLM` (falhando).
- [x] 4. Implementar o `ClienteLLM` com timeout, repetição e validação por schema.
- [x] 5. Implementar o provedor compatível com a OpenAI para Groq e Gemini.
- [x] 6. Implementar o registro de latência e tokens, sem a chave.
- [x] 7. Traduzir `ErroLLM` para o contrato da spec 011 (`llm_indisponivel`).
- [x] 8. Mensagem de `llm_indisponivel` na extensão.
- [x] 9. Documentar a camada no `verificador/README.md`.
- [x] 10. Chamada real à Groq com chave gratuita, feita à mão: `resultado=ok`, ~7 s.
- [ ] 11. Chamada real ao Gemini com chave gratuita.
- [ ] 12. Medir a latência com `reasoning_effort` baixo ou com um modelo sem raciocínio.

## Antes de abrir o PR de implementação

- [x] Todos os critérios de aceite da spec têm teste correspondente
- [ ] `spec.md` atualizado com o que mudou durante a implementação
- [ ] Status da spec alterado para `implementada`
- [x] Linha da spec atualizada no índice (`specs/README.md`)
