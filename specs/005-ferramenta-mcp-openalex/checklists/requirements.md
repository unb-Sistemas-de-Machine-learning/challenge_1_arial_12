# Checklist de qualidade da spec: 005 - Ferramenta MCP de busca na OpenAlex

**Objetivo**: validar a completude da especificação antes de passar ao `plan.md`
**Criado em**: 2026-09-16
**Spec**: [spec.md](../spec.md)

## Qualidade do conteúdo

- [x] Sem detalhe de implementação (biblioteca, linguagem, nome de pacote)
- [x] Focada no contrato e no valor, não no mecanismo
- [x] Legível por quem não implementa
- [x] Todas as seções obrigatórias do `specs/_template/` preenchidas

## Completude dos requisitos

- [x] Nenhum `[NEEDS CLARIFICATION]` restante — dúvidas na seção 8
- [x] Critérios de aceite testáveis e não ambíguos
- [x] Critérios de sucesso mensuráveis e independentes de tecnologia
- [x] Modos de falha cobertos (critérios 5, 7)
- [x] Escopo delimitado, com a fronteira contra 001 e 006 explícita (seção 4)
- [x] Premissas registradas (seção 7)
- [x] A decisão adotar-ou-construir tem critérios objetivos, não é deixada ao gosto (12–15)

## Conformidade com a constituição

- [x] **I — Spec antes do código**: nada disto existe hoje
- [x] **II — Contrato primeiro**: o contrato vale independentemente da origem da
      implementação; é o ponto central do documento
- [x] **III — Determinístico se testa**: seção 5 declara ausência de LLM; sem eval set
- [x] **IV — Latência e custo**: SC-03 e o teto de 25 resultados (critério 8)
- [x] **V — Rastreabilidade**: número, slug, branch, dependências e a exigência de registrar
      a decisão na tabela do `plan.md` (critério 14)

## Conformidade com a 002 (spec-mãe)

- [x] Ferramenta única com schema declarado (002, critério 15)
- [x] Nenhum LLM dentro dela (002, critério 16)
- [x] Reconstrução do abstract invertido (002, critério 17)
- [x] Polite pool, tempo limite e uma retentativa (002, critério 18)
- [x] Nenhuma fronteira da 002 é alterada por esta spec

## Pontos de atenção levantados na validação

- **Adotar pronto é a opção recomendada pela leitura da spec, mas a escolha não foi feita
  aqui de propósito.** O levantamento dos servidores disponíveis no GitHub ainda não
  existe: a pergunta em aberto nº 1 é a primeira tarefa do `plan.md`, e o critério 12 é a
  régua para avaliá-los. Não adote sem preencher essa tabela.
- **O critério 9 (fronteira de adaptação) é o que torna a decisão reversível** e, por isso,
  barata. Se ele for ignorado na implementação — com o Pesquisador chamando o servidor
  direto — a escolha vira definitiva sem ninguém ter decidido que fosse.
- **O critério 5 (retratação desconhecida ≠ não retratada)** parece detalhe e não é: a 002
  proíbe apresentar artigo retratado como sustentação (critério 14 da 001), e tratar
  ausência de dado como ausência de retratação fura essa garantia silenciosamente.
- O teste de integração contra a API real (seção 5) fica fora da suíte padrão; sem alguém
  responsável por executá-lo, ele não protege de nada. Pergunta em aberto nº 3.
