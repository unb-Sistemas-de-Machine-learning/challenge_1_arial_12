# NNN - Título curto da feature

> Preencha este arquivo **antes** de escrever qualquer linha de código.
> Apague estas citações em cinza conforme for preenchendo.

| Campo | Valor |
| :--- | :--- |
| **Status** | rascunho |
| **Autor** | Nome de quem escreveu |
| **Branch** | `feature/NNN-slug-curto` |
| **Depende de** | — (ou `001`, `002`...) |

---

## 1. Objetivo

> Uma frase, no máximo duas. O que o usuário ganha com isso.
> Escreva do ponto de vista de quem usa, não de quem implementa.

## 2. Contexto

> Onde essa feature se encaixa na esteira descrita na
> [Arquitetura](../../docs/pages/arquitetura.md). Cite o container ou o agente envolvido
> e, se houver, as specs anteriores das quais esta depende.

## 3. Critérios de aceite

> Numerados, no presente do indicativo, e **testáveis**. Cada item aqui vira
> pelo menos um teste. Se você não consegue imaginar o teste, reescreva o item.
>
> Ruim: "a busca deve ser rápida".
> Bom: "uma consulta repetida em menos de 24h não gera nova chamada à OpenAlex".

1.
2.
3.

## 4. Fora de escopo

> A seção mais importante do documento. É ela que impede a feature (e a IA) de
> crescer sozinha. Liste o que **não** será feito aqui, mesmo que pareça óbvio.

-
-

## 5. Comportamento de IA (preencher só se a feature usa LLM)

> Agentes são não determinísticos: não dá para validar a saída com um `assert`
> de igualdade. Separe as duas naturezas.

**Determinístico** (vira teste unitário normal):

> Formato da resposta, tratamento de erro quando o LLM devolve algo inválido,
> limites de quantidade, validação de entrada.

-

**Probabilístico** (vira eval set):

- **Dataset:** `verificador/backend/evals/<nome>.jsonl`
- **Meta:** ex.: acerta ≥ 80% dos casos rotulados
- **Erro inaceitável:** ex.: nunca classificar como `embasado` sem nenhum
  abstract relacionado

## 6. Perguntas em aberto

> Toda dúvida não resolvida vira uma linha aqui. O que não estiver escrito será
> decidido em silêncio por quem implementar — ou pelo modelo.

- [ ]

## 7. Histórico

| Data | Mudança |
| :--- | :--- |
| AAAA-MM-DD | Criação da spec |
