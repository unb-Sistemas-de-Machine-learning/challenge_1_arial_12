# 003 - Agente Triador

| Campo | Valor |
| :--- | :--- |
| **Status** | em revisão |
| **Autor** | Antigravity |
| **Branch** | `feature/003-agente-triador` |
| **Depende de** | `017` |

---

## 1. Objetivo

Eu, como leitor que selecionou uma frase escrita em linguagem jornalística,
Quero que o sistema busque a literatura usando também os termos técnicos equivalentes,
Para que um estudo existente não deixe de ser encontrado só porque a matéria não usou o vocabulário acadêmico.

## 2. Contexto

Primeiro agente da esteira e primeira spec com eval set, conforme a seção "Como especificar uma feature que usa LLM" do `specs/README.md`. Ele atua no início da verificação, convertendo o texto de entrada do usuário em consultas de busca adequadas.

## 3. Critérios de aceite

1. O agente devolve entre 1 e N variações, N configurável, sem repetição após normalização.
2. Saída fora do formato esperado (campo ausente, item vazio, item acima do tamanho máximo) é descartada e registrada; o fluxo segue com o trecho original.
3. Trecho de entrada válido pela #10 nunca faz o agente levantar exceção não tratada.
4. Com o LLM indisponível, a verificação continua usando só o trecho original, o produto degrada, não quebra.
5. Duas chamadas com o mesmo trecho e os mesmos termos extraídos produzem a mesma lista de buscas, na mesma ordem.
6. Nenhuma busca gerada contém vírgula, aspas, parênteses, operador booleano ou palavra de ligação solta.
7. Trecho que rende menos de dois conceitos não gera busca montada: a verificação segue só com o trecho original, e o motivo fica no log.

## 4. Fora de escopo

- A execução real da busca (isso é feito pela integração com OpenAlex).
- O julgamento das evidências retornadas.

## 5. Comportamento de IA (preencher só se a feature usa LLM)

O que o LLM decide e o que o código decide são partes separadas, e a fronteira
é o ponto desta spec: **o LLM extrai termos, o código monta as strings de
busca**. A primeira versão deixava o modelo escrever as strings inteiras, e o
resultado era instável — o mesmo trecho recuperava o estudo numa tentativa e não
recuperava na seguinte, porque a cada chamada o modelo escolhia outros
sinônimos. Tudo o que não precisa do modelo saiu do modelo.

As instruções dadas ao LLM são um artefato versionado, e não uma string no
código: `verificador/backend/src/agents/orientacoes/triador/`. Mudança de regra
é revisada em PR como qualquer outra.

**Determinístico**

- O agente devolve entre 1 e N variações, N configurável, sem repetição após normalização.
- Saída fora do formato esperado (campo ausente, item vazio, item acima do tamanho máximo) é descartada e registrada; o fluxo segue com o trecho original.
- Trecho de entrada válido pela #10 nunca faz o agente levantar exceção não tratada.
- Com o LLM indisponível, a verificação continua usando só o trecho original, o produto degrada, não quebra.
- Os mesmos termos extraídos produzem sempre a mesma lista de buscas, na mesma ordem: a montagem é código, e os eixos são fixos.
- O vocabulário recorrente é fixado por um glossário versionado, aplicado pelo código — variante conhecida e conceito em português são reescritos para o termo canônico.
- A temperatura do LLM é zero por padrão.

**Probabilístico**

- **Dataset:** `verificador/backend/evals/triador.jsonl` com no mínimo 30 casos rotulados à mão pela equipe, extraídos de matérias reais. **Hoje tem 24: faltam 6.**
- **Meta de acerto:** em ≥ 80% dos casos, ao menos uma variação gerada recupera na OpenAlex o estudo rotulado como correto.
- **Meta de estabilidade:** em ≥ 90% dos casos, três rodadas do mesmo trecho geram a mesma lista de buscas (`scripts/eval_triador.py --repeticoes 3`). Um caso que oscila é candidato a uma linha nova no glossário.
- **Erro inaceitável:** gerar variação que muda o sentido da alegação (inverter negação, trocar o sujeito, alterar a magnitude).

## 6. Perguntas em aberto

- ~~Qual deve ser o limite máximo de caracteres por variação?~~ **Resolvido:**
  200 caracteres. Com a montagem em código uma busca tem ~40 caracteres, então
  o limite deixou de ser um controle de qualidade e virou guarda contra o caso
  patológico (o modelo devolvendo uma frase inteira num campo). O controle que
  faz diferença passou a ser o teto de 5 palavras **por campo**.
- A numeração desta spec conflita com `003-camada-llm`, e a branch em uso é
  `feature/018-agente-triador`. Renumerar a pasta para `018-agente-triador`
  resolve, mas é decisão da equipe: o número aparece em branch, PR e commit.
- O eixo `sinonimo` tira a variante do glossário. Conceito fora do glossário não
  tem eixo de sinônimo — vale deixar o modelo propor uma variante nesse caso, ou
  a instabilidade que isso devolve custa mais do que a cobertura que ganha?

## 7. Histórico

| Data | Mudança |
| :--- | :--- |
| 2026-10-01 | Criação da spec |
| 2026-10-01 | Busca instável entre chamadas: o LLM passa a extrair termos e o código a montar as buscas. Critérios 5 a 7, meta de estabilidade, orientações versionadas e glossário controlado. Limite de caracteres resolvido. |
