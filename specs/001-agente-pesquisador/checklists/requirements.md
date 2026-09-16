# Checklist de qualidade da spec: 001 - Agente Pesquisador

**Objetivo**: validar a completude da especificação antes de passar ao `plan.md`
**Criado em**: 2026-09-16
**Spec**: [spec.md](../spec.md)

## Qualidade do conteúdo

- [x] Sem detalhe de implementação (linguagem, framework, assinatura de função)
- [x] Focada em valor para o usuário e na necessidade do produto
- [x] Legível por quem não implementa
- [x] Todas as seções obrigatórias do `specs/_template/` preenchidas

## Completude dos requisitos

- [x] Nenhum marcador `[NEEDS CLARIFICATION]` restante — dúvidas foram para a seção 8,
      como exige o princípio I da constituição
- [x] Critérios de aceite testáveis e não ambíguos
- [x] Critérios de sucesso mensuráveis (seção 6)
- [x] Critérios de sucesso independentes de tecnologia
- [x] Casos de borda identificados (critérios 8, 11, 14, 15, 18)
- [x] Escopo delimitado (seção 4)
- [x] Premissas e dependências registradas (seção 7)

## Conformidade com a constituição

- [x] **II — Contrato primeiro**: o dossiê (critério 13) e a fronteira com o BERTopic
      (critérios 10–12) são definidos antes do consumidor
- [x] **III — Determinístico se testa, probabilístico se avalia**: seção 5 separa as duas
      naturezas e aponta `evals/pesquisador.jsonl` com meta declarada
- [x] **IV — Latência e custo são requisitos**: orçamento explícito nos critérios 17 e 18
- [x] **V — Rastreabilidade**: número, slug e branch declarados no cabeçalho

## Pontos de atenção levantados na validação

- O critério 7 depende da definição de "relacionado", que é a pergunta em aberto nº 2.
  Se a resposta for "julgamento do próprio agente", o critério vira probabilístico e
  precisa migrar para o eval set em vez de virar teste unitário. **Resolver no
  `/speckit-clarify` antes do plano.**
- O critério 16 toca a extensão e o contrato `tipos.ts`. Se a equipe preferir separar a
  mudança de contrato numa spec própria, este critério sai daqui.
- A pergunta em aberto nº 4 (guardar a URL de origem) é decisão de privacidade e deve ser
  respondida antes da implementação do cache, não durante.
