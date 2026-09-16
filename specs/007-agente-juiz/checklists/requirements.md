# Checklist de qualidade da spec: 007 - Agente Juiz

**Objetivo**: validar a completude da especificação antes de passar ao `plan.md`
**Criado em**: 2026-09-16
**Spec**: [spec.md](../spec.md)

## Qualidade do conteúdo

- [x] Sem detalhe de implementação (modelo, provedor, formato de prompt)
- [x] Focada no que o leitor recebe e no dano a evitar
- [x] Legível por quem não implementa
- [x] Todas as seções obrigatórias do `specs/_template/` preenchidas

## Completude dos requisitos

- [x] Nenhum `[NEEDS CLARIFICATION]` restante — dúvidas na seção 8
- [x] Critérios de aceite testáveis e não ambíguos
- [x] Critérios de sucesso mensuráveis e independentes de tecnologia
- [x] Regras de combinação estado/evidência exaustivas (critérios 6 a 11)
- [x] Falhas e saída inválida cobertas (critérios 17 a 21)
- [x] Escopo delimitado (seção 4)
- [x] Premissas registradas (seção 7)

## Conformidade com a constituição

- [x] **I — Spec antes do código**: nada disto existe hoje
- [x] **II — Contrato primeiro**: entrada e saída do estágio definidas antes do consumidor
- [x] **III — Determinístico se testa, probabilístico se avalia**: a validação da saída é
      teste unitário; a qualidade do rótulo é eval, com meta e erros inaceitáveis
- [x] **IV — Latência e custo**: teto de 1.500 tokens, uma chamada, sem retentativa
      automática (critério 20) e SC-03
- [x] **V — Rastreabilidade**: número, slug, branch e dependências declarados

## Conformidade com a 002 (spec-mãe)

- [x] Cinco estados de conteúdo, `divergente` inclusive (002, critério 3)
- [x] `divergente` exige evidência dos dois lados (002, critério 21)
- [x] Justificativa ≤ 280 caracteres em português (002, critério 21)
- [x] Nenhuma citação fora da lista recebida, validada no código (002, critério 22)
- [x] Zero evidências nunca vira `sustenta` (002, critério 23)
- [x] Falha nunca exibe evidência sem veredito (002, critério 24)
- [x] Nenhuma fronteira da 002 é alterada por esta spec

## Pontos de atenção levantados na validação

- **O critério 5 é o coração da spec e o mais difícil de garantir.** Um modelo grande
  "sabe" que muita alegação é falsa, e o caminho fácil é ele responder pelo que sabe, não
  pelo que recebeu. O eval tem 3 casos desenhados só para flagrar isso; se a equipe cortar
  casos por tempo, não corte esses.
- **A pergunta em aberto nº 1 (limiar de `divergente`) muda os critérios 6 e 8.** Como está,
  uma única evidência contrária entre seis já impede `sustenta` — provavelmente apertado
  demais. Resolver antes do `plan.md`.
- **A pergunta nº 5 aponta um ponto cego real:** `indisponivel` por saída inválida é
  invisível ao usuário e, do jeito que está, também à equipe. Sem um contador dessas
  ocorrências, o Juiz pode estar falhando em 20% das verificações sem ninguém perceber.
  Candidato a virar critério em vez de pergunta.
- O link para a spec 006 (BERTopic) aponta para uma spec **ainda não escrita**; o número
  está reservado no mapa da 002. Corrigir o link não é necessário — escrever a 006 é.
