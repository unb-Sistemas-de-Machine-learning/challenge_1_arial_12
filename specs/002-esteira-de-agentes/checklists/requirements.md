# Checklist de qualidade da spec: 002 - Esteira de agentes

**Objetivo**: validar a completude da especificação antes de passar ao `plan.md`
**Criado em**: 2026-09-16
**Spec**: [spec.md](../spec.md)

## Qualidade do conteúdo

- [x] Sem detalhe de implementação (biblioteca, assinatura, provedor de modelo)
- [x] Focada em valor para o usuário e no contrato entre as peças
- [x] Legível por quem não implementa
- [x] Todas as seções obrigatórias do `specs/_template/` preenchidas

## Completude dos requisitos

- [x] Nenhum `[NEEDS CLARIFICATION]` restante — dúvidas foram para a seção 9
- [x] Cada estágio tem entrada, saída e comportamento de falha declarados
- [x] Critérios de sucesso mensuráveis e independentes de tecnologia (seção 6)
- [x] Escopo delimitado (seção 4)
- [x] Premissas registradas (seção 7)
- [x] Specs derivadas mapeadas com numeração reservada (seção 8)

## Conformidade com a constituição

- [x] **II — Contrato primeiro**: é o propósito inteiro do documento
- [x] **III — Determinístico se testa, probabilístico se avalia**: seção 5 define um eval
      set por agente, com meta e erro inaceitável em cada um
- [x] **IV — Latência e custo são requisitos**: orçamento por estágio e somado
      (critérios 10, 23, 27)
- [x] **V — Rastreabilidade**: numeração, branch e mapa de specs filhas

## Revalidação após a sessão de clarificação (2026-09-16)

- [x] Privacidade dos dados persistidos definida (critério 25: duas ilhas sem chave entre si)
- [x] Taxonomia de estados fechada e rotulável pela equipe (critério 3; eval do Juiz com
      dupla rotulagem)
- [x] Estado degradado da interface definido (critério 24: nunca exibir evidência sem veredito)
- [x] Custo do portão do Triador definido (critério 8: camada determinística custa zero token)
- [x] Comportamento diante de entrada fora do português definido (critério 7)

## Pontos de atenção levantados na validação

- **Tamanho.** Esta spec é maior que o normal porque é a spec-mãe. Se a revisão travar,
  quebre-a em duas: contrato externo (critérios 1–6, 24–28) e contratos internos entre
  estágios (7–23). Não a deixe em revisão eterna.
- **Critério 3 e 22 mudam `extensao/tipos.ts`.** A extensão precisa mudar junto; o
  `verificador/README.md` afirma o contrário e deve ser corrigido na implementação.
- ~~Pergunta sobre `contradiz` vs `exagera`~~ — resolvida na clarificação: cinco estados de
  conteúdo, com `divergente` próprio, e dupla rotulagem no eval do Juiz.
- ~~Pergunta sobre anonimato do voto~~ — resolvida na clarificação: voto e alegação em
  tabelas sem chave entre si.
- Os números dos critérios 6, 12, 15, 21 e 27 são estimativas de partida. Cada um vira
  medição no `plan.md` do estágio correspondente e deve ser corrigido aqui por emenda
  quando a medição contrariar o palpite.
