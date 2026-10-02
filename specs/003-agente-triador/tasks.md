# Tarefas - 003 Agente Triador

A primeira leva (1 a 4) é o agente como ele nasceu: o LLM escrevendo as strings
de busca. A segunda (5 a 12) é a correção da instabilidade medida depois —
mesma frase, estudo encontrado numa tentativa e não na seguinte.

- [x] 1. Schema da resposta do LLM e chamada pela camada `ClienteLLM`
- [x] 2. Descarte de variação vazia, repetida ou acima do tamanho máximo
- [x] 3. Degradação para o trecho original quando o LLM falha
- [x] 4. Eval set inicial em `evals/triador.jsonl` e runner

## Estabilidade das buscas

- [x] 5. Carregador de orientações em Markdown (`src/agents/orientacoes/`), com
      cabeçalho de metadados separado do corpo
- [x] 6. Escrever as orientações do variador semântico: regras de extração,
      forma dos termos, erro inaceitável e checklist
- [x] 7. Escrever o glossário controlado e ler a tabela no código (variante e
      conceito em português reescritos para o termo canônico)
- [x] 8. Escrever os exemplos resolvidos e a referência dos formatos de busca
- [x] 9. Trocar o schema de `Variacoes` (lista de strings) por `TermosDeBusca`
      (quatro campos) e montar as buscas pelos eixos fixos
- [x] 10. Forma canônica dos termos: minúsculas, sem pontuação, sem vírgula, sem
      operador booleano, sem conectivo, teto de palavras por campo
- [x] 11. `LLM_TEMPERATURA` (padrão 0) e `LLM_SEED` na camada de LLM
- [x] 12. `--repeticoes` no runner de eval, com relatório de estabilidade

## Antes de abrir o PR de implementação

- [x] Todos os critérios de aceite da spec têm teste correspondente
- [x] `spec.md` atualizado com o que mudou durante a implementação
- [ ] Rodar `scripts/eval_triador.py --repeticoes 3` e registrar as duas taxas
      (acerto e estabilidade) na descrição do PR
- [ ] Completar o eval set: 24 casos rotulados, a spec pede no mínimo 30
- [ ] Resolver a numeração da spec (`003` conflita com `003-camada-llm`; a
      branch é `feature/018-agente-triador`)
- [ ] Status da spec alterado para `implementada`
- [ ] Linha da spec acrescentada no índice (`specs/README.md`)
