<!--
SYNC IMPACT REPORT (scratch — remover antes do commit final)
Versão: TEMPLATE (não versionado) → 1.0.0
Tipo de bump: MAJOR inicial — primeira ratificação; todos os placeholders
              do scaffold foram substituídos por conteúdo concreto.

Princípios definidos (antes → depois):
  [PRINCIPLE_1_NAME] → I. Especificação Antes do Código (NÃO-NEGOCIÁVEL)
  [PRINCIPLE_2_NAME] → II. Contrato Primeiro, Fatia Vertical
  [PRINCIPLE_3_NAME] → III. Determinístico se Testa, Probabilístico se Avalia
  [PRINCIPLE_4_NAME] → IV. Latência e Custo São Requisitos, Não Otimizações
  [PRINCIPLE_5_NAME] → V. Rastreabilidade de Ponta a Ponta

Seções adicionadas:
  [SECTION_2_NAME] → Restrições Técnicas e de Arquitetura
  [SECTION_3_NAME] → Fluxo de Desenvolvimento e Portões de Qualidade
  Governança preenchida (emenda, versionamento, conformidade)

Seções removidas: nenhuma

Itens diferidos / TODO:
  - TODO(RATIFICATION_DATE): adotada a data desta primeira redação
    (2026-09-16). Se a equipe considerar que a governança já valia desde o
    início do projeto, ajuste para a data real de acordo e emita um PATCH.

Consistência com artefatos dependentes (lidos em runtime, não alterados aqui):
  ✅ specs/README.md — princípios I, II, III e V derivam diretamente dele
  ✅ docs/pages/politicas_repositorio.md — princípio V e seção de fluxo
  ✅ docs/pages/arquitetura.md — seção de restrições técnicas
-->

# Verificador Científico — Constituição da Equipe Arial 12

## Core Principles

### I. Especificação Antes do Código (NÃO-NEGOCIÁVEL)

Nenhuma funcionalidade entra no código sem uma spec aprovada em `specs/NNN-slug/`.
A ordem é obrigatória: `spec.md` (o quê e por quê) é escrito e aprovado em PR próprio
**antes** de `plan.md` (o como) e `tasks.md` (a ordem). Um PR de implementação sem spec
correspondente MUST ser recusado na revisão.

Toda spec MUST conter critérios de aceite verificáveis e uma seção de fora de escopo
preenchida. "Deve funcionar bem" não é critério; "uma consulta repetida em menos de 24h
não gera nova chamada à OpenAlex" é. Dúvidas não resolvidas MUST ser registradas em
**Perguntas em aberto** em vez de decididas no impulso durante a implementação.

Quando a implementação revelar que a spec estava errada, a spec MUST ser corrigida antes
de o código divergir. Spec desatualizada é pior que spec inexistente, porque é seguida com
confiança — pela equipe e pela IA que implementa a partir dela.

*Racional:* boa parte da implementação é assistida por IA. O que não estiver escrito na
spec será inventado, e o erro terá aparência de acerto.

### II. Contrato Primeiro, Fatia Vertical

Toda entrega MUST terminar em algo demonstrável ponta a ponta. Prefira "a rota
`/verificar` devolve um veredicto fixo, do texto selecionado até o painel" a "todos os
schemas do projeto".

O contrato de dados entre processos (JSON da extensão ↔ Gateway, schemas Pydantic, saída
dos agentes) MUST ser definido e escrito antes da implementação que o consome, e MUST ser
compartilhado por um único artefato de tipo — não duplicado de cada lado. Uma mudança
interna que não altera o contrato NÃO PODE exigir mudança no consumidor; se exigir, o
contrato estava mal definido.

*Racional:* a Fase 02 troca o mock pela busca real na OpenAlex sem tocar na extensão. Essa
propriedade é a prova de que a arquitetura de contêineres desacoplados funciona na prática.

### III. Determinístico se Testa, Probabilístico se Avalia

Toda spec que envolva LLM MUST separar explicitamente as duas naturezas:

- **Determinístico** — formato da resposta, comportamento diante de saída inválida do
  modelo, limites de quantidade, validação de entrada. MUST ter teste automatizado, com
  dublê no lugar do LLM. Nenhuma chamada real a LLM ou à OpenAlex em teste unitário.
- **Probabilístico** — a qualidade do resultado. MUST ter um eval set em
  `verificador/backend/evals/<agente>.jsonl`, rotulado à mão pela equipe, com meta de
  acerto declarada e lista explícita de erros inaceitáveis.

Mudança de prompt sem execução do eval set correspondente MUST ser bloqueada na revisão.
O eval set pode nascer pequeno, mas MUST existir antes do agente ser considerado pronto.

*Racional:* sem eval set não há como afirmar que uma mudança melhorou alguma coisa. A taxa
de aceitação da extensão só dá esse sinal depois que o produto já está na mão do usuário —
tarde demais para orientar decisões de engenharia.

### IV. Latência e Custo São Requisitos, Não Otimizações

O veredicto aparece na tela durante a leitura do usuário; latência alta destrói o produto
mesmo com resposta correta. Toda spec que toque o caminho de inferência MUST declarar um
orçamento de latência e, quando houver chamada a LLM, um orçamento de tokens por
requisição.

Decisões que gastam latência ou tokens MUST ser justificadas por número, não por intuição:
o cache se justifica por taxa de hit medida, a clusterização com BERTopic por redução de
tokens medida. Uma otimização sem métrica antes/depois MUST ser tratada como complexidade
não justificada e removida.

*Racional:* a proposta central do projeto é veredicto em tempo real. Tratar desempenho como
ajuste posterior o transforma em reescrita posterior.

### V. Rastreabilidade de Ponta a Ponta

De qualquer linha de código MUST ser possível chegar à decisão que a originou. Isso exige,
sem exceção:

- **Uma feature, uma spec, um número, uma branch.** Números de spec são de três dígitos,
  nunca reaproveitados nem renumerados, e aparecem na branch (`feature/004-cache-de-buscas`),
  no título do PR (`[004] Cache de buscas`) e no commit.
- **Conventional Commits em português**, conforme a política do repositório: título de até
  72 caracteres, descrição imperativa, sem ponto final. Commits genéricos (`update`,
  `ajustes`, `mudanças`) MUST ser recusados.
- **Sem push direto** em `main` ou `develop`. Todo PR vai para `develop`, exige aprovação de
  ao menos um integrante, entra por **Squash and Merge** e tem a branch removida em seguida.
- **Decisões técnicas registradas** na tabela de decisões do `plan.md`, cada uma com sua
  linha de justificativa.

*Racional:* é a tabela de decisões e a numeração que respondem, três semanas depois, "por
que isso foi feito assim?" — sem depender da memória de quem implementou.

## Restrições Técnicas e de Arquitetura

O sistema segue a arquitetura de contêineres descrita em `docs/pages/arquitetura.md`
(C4 Nível 2). As restrições abaixo são vinculantes:

- **Fronteiras de contêiner.** Extensão, API Gateway, agentes (Triador, Pesquisador, Juiz),
  cache, servidor MCP, BERTopic e Postgres são responsabilidades separadas. Código novo MUST
  respeitar o layout de `verificador/backend/src/` (`api/`, `agents/`, `core/`, `services/`,
  `mcp/`, `tests/`). Lógica de negócio dentro de rota do FastAPI MUST ser recusada na revisão.
- **Pilha fixa.** FastAPI (Python) no Gateway, PostgreSQL para feedback e histórico de cache,
  protocolo MCP para a busca na OpenAlex, BERTopic para clusterização de abstracts, WXT +
  TypeScript na extensão. Trocar qualquer um desses itens MUST passar por emenda desta
  constituição, não por decisão de PR.
- **Compatibilidade de navegador.** A extensão MUST funcionar em Chrome (MV3) e Firefox
  (MV2). O `fetch` ao backend MUST ser feito no background script — o content script está
  sujeito à CSP da página visitada. A interface injetada MUST usar shadow DOM fechado para
  não vazar nem absorver CSS da página.
- **Segredos.** Chaves de LLM e credenciais MUST vir de variáveis de ambiente
  (`core/config/`), nunca do código nem de artefato versionado. `.env.example` MUST
  permanecer atualizado com toda variável nova.
- **Validação de entrada.** Todo dado que cruza a fronteira do Gateway MUST ser validado por
  schema Pydantic em `api/schemas/`. A rota `/verificar` MUST aplicar rate limiting.
- **Dados de avaliação.** Eval sets vivem em `verificador/backend/evals/`, versionados junto
  do código, nunca dentro de `specs/`. A spec aponta para o arquivo e define a meta.

## Fluxo de Desenvolvimento e Portões de Qualidade

O ciclo de uma feature é o de `specs/README.md` e MUST ser seguido na ordem:

1. Próximo número livre + slug curto e descritivo; cópia de `specs/_template/`.
2. Branch a partir de `develop`, carregando o número da spec.
3. `spec.md` preenchido e submetido em PR **isolado**, com status `em revisão`.
4. Spec aprovada (status `aprovada`) → só então `plan.md` e `tasks.md`.
5. Implementação tarefa a tarefa, com `spec.md` e `plan.md` no contexto da sessão de IA e
   uma tarefa por vez. Checkbox só é marcado quando o passo está testado.
6. PR de implementação referenciando a spec.

**Portões de qualidade.** Um PR de implementação NÃO PODE ser aprovado sem que todos os
itens abaixo sejam verdadeiros:

- [ ] Existe spec aprovada correspondente, e ela reflete o que foi realmente construído.
- [ ] Todo critério de aceite determinístico tem teste automatizado correspondente, passando.
- [ ] Todo agente com LLM tocado teve seu eval set executado, com o resultado registrado no PR.
- [ ] O orçamento de latência/tokens declarado na spec foi medido e respeitado.
- [ ] Nenhuma decisão técnica nova ficou fora da tabela de decisões do `plan.md`.
- [ ] Status da spec atualizado para `implementada` e a linha correspondente atualizada na
      tabela de índice de `specs/README.md`.
- [ ] Ao menos uma aprovação de revisão de outro integrante.

Uma spec que morreu no caminho vira `abandonada` e **permanece** na tabela de índice; seu
número nunca é reaproveitado.

## Governance

Esta constituição prevalece sobre qualquer outra prática, convenção ou preferência
individual. Em conflito entre este documento e um `plan.md`, uma decisão de PR ou um hábito
estabelecido, esta constituição vence — até ser emendada.

**Procedimento de emenda.** Uma emenda MUST ser proposta em PR que altere apenas
`.specify/memory/constitution.md`, contendo: a mudança, o racional, o impacto sobre specs e
código existentes e, quando houver quebra, o plano de migração. A emenda exige aprovação de
**maioria simples dos integrantes ativos** da equipe. Emenda aprovada com impacto retroativo
MUST gerar as issues de adequação no mesmo momento do merge.

**Política de versionamento.** Versionamento semântico sobre a governança:

- **MAJOR** — remoção ou redefinição incompatível de princípio ou regra de governança.
- **MINOR** — novo princípio ou seção, ou expansão material de orientação existente.
- **PATCH** — esclarecimento, redação, correção tipográfica, refinamento não semântico.

O campo **Last Amended** MUST ser atualizado em toda emenda que altere conteúdo normativo.

**Revisão de conformidade.** Todo PR é uma verificação de conformidade: o revisor MUST
percorrer os portões de qualidade acima antes de aprovar. Complexidade não prevista na spec
MUST ser justificada explicitamente no PR ou removida. A equipe MUST revisar esta
constituição ao fim de cada fase do projeto, emendando o que a prática mostrou estar errado
em vez de conviver com uma regra que ninguém segue.

Para orientação de desenvolvimento em tempo de execução, consulte `specs/README.md`
(processo SDD), `docs/pages/politicas_repositorio.md` (branches e commits) e
`docs/pages/arquitetura.md` (contêineres e fluxo).

**Version**: 1.0.0 | **Ratified**: 2026-09-16 | **Last Amended**: 2026-09-16
