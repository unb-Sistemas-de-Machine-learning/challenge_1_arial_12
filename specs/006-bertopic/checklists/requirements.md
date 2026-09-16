# Checklist de qualidade da spec: 006 - BERTopic

**Objetivo**: validar a completude da especificação antes de passar ao `plan.md`
**Criado em**: 2026-09-16
**Spec**: [spec.md](../spec.md)

## Qualidade do conteúdo

- [x] Sem detalhe de implementação (modelo de embeddings, parâmetros da biblioteca)
- [x] Focada no efeito (menos ruído ao Juiz) e não no mecanismo
- [x] Legível por quem não implementa
- [x] Todas as seções obrigatórias do `specs/_template/` preenchidas

## Completude dos requisitos

- [x] Nenhum `[NEEDS CLARIFICATION]` restante — dúvidas na seção 8
- [x] Critérios de aceite testáveis e não ambíguos
- [x] Critérios de sucesso mensuráveis e independentes de tecnologia
- [x] Degradação definida: o estágio nunca derruba a esteira (critério 11)
- [x] Escopo delimitado (seção 4)
- [x] Premissas registradas, inclusive a de que o volume é atípico para a ferramenta

## Conformidade com a constituição

- [x] **II — Contrato primeiro**: entrada e saída definidas nos critérios 1 e 2
- [x] **III — Determinístico se testa, probabilístico se avalia**: o estágio não usa LLM mas
      é probabilístico em qualidade, e a seção 5 trata as duas naturezas com
      `evals/bertopic.jsonl`
- [x] **IV — Latência e custo são requisitos**: o critério 14 obriga medir a redução de
      tokens contra a latência acrescentada e **remover o estágio** se não se pagar —
      aplicação direta de "otimização sem métrica é complexidade não justificada"
- [x] **V — Rastreabilidade**: número, slug, branch e dependências declarados

## Conformidade com a 002 (spec-mãe)

- [x] Recebe só `[{id, abstract}]`, sem alegação e sem saída de LLM (002, critério 19)
- [x] Pulado abaixo de 10 abstracts, com indicação na resposta (002, critério 20)
- [x] Roda no processo do backend, não como serviço (002, revisão da arquitetura, linha 4)

## Pontos de atenção levantados na validação

- **Esta spec corrige uma contradição entre a 001 e a 007.** A 001 (critério 12) manda levar
  adiante só o cluster mais alinhado; a 007 exige evidência dos dois lados para devolver
  `divergente`. Mantidas as duas como estavam, `divergente` nunca aconteceria — a literatura
  minoritária seria descartada antes de o Juiz vê-la. O critério 8 daqui resolve, e **a 001
  precisa de emenda no critério 12 quando esta spec for aprovada**. Sem essa emenda, as duas
  specs ficam em conflito aberto.
- **O critério 4 (semente fixa) parece detalhe técnico e é pré-requisito de duas coisas:**
  o cache guardar resultado reproduzível e o eval set medir qualidade em vez de aleatoriedade.
- **O critério 14 pode matar este estágio, e isso é um bom resultado.** Clusterizar 10 a 25
  documentos é uso atípico do BERTopic — ele foi feito para corpora grandes. Se a medição
  mostrar que uma ordenação simples entrega o mesmo, remover é a decisão certa e a spec já
  autoriza.
- A pergunta em aberto nº 1 (limiar do cluster minoritário) e a nº 1 da 007 (limiar de
  `divergente`) são a mesma decisão vista de dois lados. Responder separadamente é como as
  duas ficam incoerentes.
