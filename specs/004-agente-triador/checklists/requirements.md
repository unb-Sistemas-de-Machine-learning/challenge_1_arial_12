# Checklist de qualidade da spec: 004 - Agente Triador

**Objetivo**: validar a completude da especificação antes de passar ao `plan.md`
**Criado em**: 2026-09-16
**Spec**: [spec.md](../spec.md)

## Qualidade do conteúdo

- [x] Sem detalhe de implementação (modelo, biblioteca, assinatura)
- [x] Focada no valor (economia e precisão da alegação) e não no mecanismo
- [x] Legível por quem não implementa
- [x] Todas as seções obrigatórias do `specs/_template/` preenchidas

## Completude dos requisitos

- [x] Nenhum `[NEEDS CLARIFICATION]` restante — dúvidas na seção 8
- [x] Critérios de aceite testáveis e não ambíguos
- [x] Critérios de sucesso mensuráveis e independentes de tecnologia
- [x] Falhas e saída inválida cobertas (critérios 14 e 15)
- [x] Escopo delimitado, com a fronteira contra a 001 explícita (seção 4)
- [x] Premissas registradas (seção 7)

## Conformidade com a constituição

- [x] **I — Spec antes do código**: nada disto existe hoje no repositório
- [x] **II — Contrato primeiro**: entrada e saída do estágio definidas antes do consumidor
- [x] **III — Determinístico se testa, probabilístico se avalia**: seção 5 separa as duas,
      com `evals/triador.jsonl`, meta e erros inaceitáveis
- [x] **IV — Latência e custo**: tetos nos critérios 13, SC-03 e SC-04
- [x] **V — Rastreabilidade**: número, slug, branch e dependência da 002 declarados

## Conformidade com a 002 (spec-mãe)

- [x] Duas camadas, primeira sem modelo (002, critério 8)
- [x] Teto de 400 tokens e uma chamada na segunda camada (002, critério 10)
- [x] Entrada em qualquer idioma (002, critério 7)
- [x] Saída com `alegacao_pt` e `alegacao_en` (002, critério 7)
- [x] Nenhuma fronteira da 002 é alterada por esta spec

## Pontos de atenção levantados na validação

- **A pergunta em aberto nº 1 e o critério 3 se contradizem na prática.** A camada 1 barra
  trecho sem predicado, mas manchete é exatamente o que uma pessoa seleciona ao ler uma
  matéria. Do jeito que está, o portão pode descartar o caso de uso mais comum do produto.
  **Resolver antes do `plan.md`** — é o item de maior impacto desta spec.
- **Pergunta em aberto nº 2 (saída binária)** interage com o critério 5: sem um "não sei",
  toda incerteza do modelo vira `false`, que é o erro caro. Vale decidir junto com a nº 1.
- O critério 9 (preservar quantificadores) é a ponte entre esta spec e o Juiz: se o número
  se perde aqui, `exagera` vira indistinguível de `sustenta` lá na frente, e nenhum eval do
  Juiz vai detectar a causa.
- O critério 2 (cache do Triador por trecho) usa chave diferente do cache da esteira
  (002, critério 11, que usa `alegacao_en`). São dois caches com propósitos distintos —
  deixar isso explícito no `plan.md` para ninguém tentar unificá-los.
