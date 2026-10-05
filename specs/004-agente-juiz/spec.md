# 004 — Agente Juiz: veredicto fundamentado e categorias

| Campo | Valor |
| :--- | :--- |
| **Status** | em revisão |
| **Autor** | Equipe Arial 12 |
| **Branch** | `feature/019-agente-juiz` |
| **Issue** | [#19](https://github.com/unb-Sistemas-de-Machine-learning/challenge_1_arial_12/issues/19) |
| **Depende de** | #18 (Triador), #17 (camada LLM), #10 (schema `Veredito`) |

## 1. Objetivo

O leitor recebe uma classificação fundamentada e pode conferir qual estudo sustenta — ou limita — a alegação da matéria.

## 2. Contexto

O Triador (#18) prepara buscas e a OpenAlex devolve trabalhos; o Juiz classifica o trecho usando apenas os abstracts recebidos. Esta feature implementa o agente e sua avaliação, sem substituir ainda o veredito mock de `POST /verificar`.

## 3. Categorias

| `estado` | Definição operacional |
| :--- | :--- |
| `sustenta` | Pelo menos um abstract pertinente, não retratado e com DOI relata resultado diretamente compatível com a população, intervenção/exposição, desfecho e grau de certeza da alegação. Não converter associação em causalidade nem extrapolar de animais para humanos. |
| `exagera` | Há abstract pertinente, mas a alegação amplia a força, causalidade, população, magnitude, certeza ou alcance do resultado; também inclui afirmação positiva contrariada pelo abstract. A justificativa explica o descompasso sem afirmar mais do que a fonte permite. |
| `nada_encontrado` | Não há abstract utilizável e pertinente com DOI para fundamentar a comparação, ou a lista está vazia. Não significa que a alegação seja falsa; significa evidência insuficiente nesta busca. |

Estudo retratado **nunca** fundamenta `sustenta`. Quando só há estudos retratados, a saída é `nada_encontrado`; quando há outro estudo pertinente não retratado, a decisão deve se apoiar nele.

## 4. Critérios determinísticos

1. O agente devolve `Veredito` da B05 com `estado`, `justificativa`, `estudo` (quando o estado não é `nada_encontrado`) e `termos=[]`; `id` fica `None` até persistência posterior.
2. A saída do LLM contém enum fechado `Estado`, relação interna (`compativel`, `parcial` ou `ausente`), DOI selecionado e justificativa em português entre 20 e **600 caracteres**. O código rejeita estado incoerente com a relação declarada e tenta novamente uma vez. A relação não aparece no schema B05. O teto de 600 é provisório para esta entrega e deve ser revisto com a equipe se o painel exigir outro tamanho.
3. Formato inválido, estado fora do enum, justificativa vazia/longa demais, idioma inadequado, DOI ausente ou não presente na entrada, referência a DOI estranho no texto e seleção de retratado como `sustenta` são rejeitados. O agente refaz a chamada **uma vez**; persistindo a falha, levanta `RespostaInvalidaDoLLM`, traduzível pelo gateway para erro padronizado `llm_indisponivel`/503.
4. O campo `estudo` do `Veredito` é construído pelo código **a partir da entrada**, nunca copiado de título, ano ou retratação inventados pelo LLM. O DOI selecionado e todo DOI citado na justificativa devem constar dos abstracts recebidos.
5. Lista sem abstracts utilizáveis devolve `nada_encontrado`, `estudo=None` e justificativa fixa em português **sem chamar LLM**. Abstracts sem DOI não podem ser selecionados como fonte.
6. A justificativa não contém marcadores como “estudo 1”/“estudo 2”, nem jargão de prompt. O prompt pede português claro e cita a fonte por DOI, sem numeração de candidatos.
7. Falhas de timeout/indisponibilidade do provedor preservam o contrato da camada LLM; esta feature não altera a rota `/verificar` mock.

## 5. Critérios probabilísticos

- `verificador/backend/evals/juiz.jsonl` contém no mínimo **40 casos** rotulados, com representação equilibrada de `sustenta`, `exagera` e `nada_encontrado`, incluindo ausência de abstracts, abstracts irrelevantes, retratados e extrapolações de população/causalidade. Casos sintéticos devem estar explicitamente identificados como tal; não representam achados científicos reais.
- O runner informa acerto do estado, com meta **≥ 80%**.
- Informa separadamente falsos `sustenta` sem abstract relacionado, meta **zero**, e casos em que um retratado foi usado para sustentar, meta **zero**.
- A taxa de qualidade só é reportada após uma rodada com LLM real e o dataset revisado; teste unitário com dublê não equivale a essa medição.

## 6. Fora de escopo

- Trocar o mock de `/verificar` pela esteira completa Triador → OpenAlex → Juiz.
- Afirmar acurácia clínica ou veracidade de estudos sintéticos do eval.
- Atualizar modelos/provedores ou alterar a política de custo da camada #17.

## 7. Perguntas em aberto

- Confirmar o teto provisório de 600 caracteres para a justificativa.
- Revisar os rótulos sintéticos e acrescentar estudos reais antes de usar a taxa de acerto como medida de qualidade em produção.

## 8. Histórico

| Data | Mudança |
| :--- | :--- |
| 2026-10-05 | Spec inicial da issue #19; separa garantias de código de avaliação probabilística |
