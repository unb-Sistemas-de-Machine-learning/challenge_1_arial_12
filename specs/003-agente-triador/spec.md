# 003 - Agente Triador

| Campo | Valor |
| :--- | :--- |
| **Status** | rascunho |
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
2. Saída fora do formato esperado (não é lista, item vazio, item acima do tamanho máximo) é descartada e registrada; o fluxo segue com o trecho original.
3. Trecho de entrada válido pela #10 nunca faz o agente levantar exceção não tratada.
4. Com o LLM indisponível, a verificação continua usando só o trecho original, o produto degrada, não quebra.

## 4. Fora de escopo

- A execução real da busca (isso é feito pela integração com OpenAlex).
- O julgamento das evidências retornadas.

## 5. Comportamento de IA (preencher só se a feature usa LLM)

**Determinístico**

- O agente devolve entre 1 e N variações, N configurável, sem repetição após normalização.
- Saída fora do formato esperado (não é lista, item vazio, item acima do tamanho máximo) é descartada e registrada; o fluxo segue com o trecho original.
- Trecho de entrada válido pela #10 nunca faz o agente levantar exceção não tratada.
- Com o LLM indisponível, a verificação continua usando só o trecho original, o produto degrada, não quebra.

**Probabilístico**

- **Dataset:** `verificador/backend/evals/triador.jsonl` com no mínimo 30 casos rotulados à mão pela equipe, extraídos de matérias reais.
- **Meta:** em ≥ 80% dos casos, ao menos uma variação gerada recupera na OpenAlex o estudo rotulado como correto.
- **Erro inaceitável:** gerar variação que muda o sentido da alegação (inverter negação, trocar o sujeito, alterar a magnitude).

## 6. Perguntas em aberto

- Qual deve ser o limite máximo de caracteres por variação (tamanho máximo)?

## 7. Histórico

| Data | Mudança |
| :--- | :--- |
| 2026-10-01 | Criação da spec |
