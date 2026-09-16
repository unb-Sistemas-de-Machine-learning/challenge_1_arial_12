# 006 - BERTopic: redução de ruído e seleção da amostra

| Campo | Valor |
| :--- | :--- |
| **Status** | rascunho |
| **Autor** | Carlos Eduardo Mota |
| **Branch** | `feature/006-bertopic` |
| **Depende de** | [002](../002-esteira-de-agentes/spec.md) (estágio 5) · consome [001](../001-agente-pesquisador/spec.md) · alimenta [007](../007-agente-juiz/spec.md) |

---

## 1. Objetivo

Das dezenas de estudos que uma busca devolve, o Juiz recebe apenas um punhado — os que
realmente representam o que a literatura diz sobre aquela alegação, incluindo quando ela
diz coisas opostas.

## 2. Contexto

É o estágio 5 da esteira (002, critérios 19 e 20) e existe por uma razão de engenharia:
mandar 25 abstracts ao Juiz custa caro e piora a resposta, porque afoga o que importa em
ruído. O BERTopic agrupa os abstracts por semelhança semântica e permite escolher poucos
representantes.

**Uma contradição entre specs anteriores é resolvida aqui.** A 001 (critério 12) manda
levar adiante os abstracts mais próximos do centro do cluster **mais alinhado** à alegação.
Mas a 007 exige, para devolver `divergente`, ao menos uma evidência de **cada** lado — e um
lado só sobrevive se a amostra o incluir. Da forma como estava, a literatura minoritária
seria descartada antes de o Juiz sequer vê-la, e `divergente` seria um rótulo impossível de
acontecer na prática. O critério 8 desta spec corrige isso, e a 001 precisa de emenda
quando esta for aprovada.

Vale registrar que este estágio é uma **otimização**, e a constituição (princípio IV) exige
que otimização se justifique por número. O critério 14 torna essa medição obrigatória — e a
remoção do estágio, se ele não se pagar.

## 3. Critérios de aceite

### Entrada e saída

1. Recebe apenas `[{id, abstract}]`. Não recebe a alegação, nem saída de modelo de
   linguagem, nem nada vindo do usuário.
2. Devolve: o cluster de cada documento, os termos representativos de cada cluster, a
   amostra selecionada (no máximo 6 identificadores) e quantos documentos foram
   descartados.
3. Com menos de 10 abstracts, a clusterização é **pulada**: todos seguem adiante (até o
   limite de 6) e a resposta indica que foi pulada.

### Determinismo

4. Mesma entrada produz sempre a mesma saída. As etapas aleatórias do BERTopic têm semente
   fixa — sem isso, o cache guarda um resultado que não se reproduz e o eval mede ruído.
5. A ordem dos documentos na entrada não altera o agrupamento.

### Seleção da amostra

6. A amostra tem no máximo 6 documentos, escolhidos por proximidade ao centro do seu
   cluster.
7. O cluster dominante — o maior — sempre está representado.
8. **Quando existe um cluster minoritário relevante, ao menos um representante dele entra
   na amostra.** Relevante significa ao menos 3 documentos ou 20% do total, o que for
   menor. É esta regra que torna o veredito `divergente` possível de acontecer.
9. Documentos que o BERTopic marca como fora de qualquer cluster não são descartados de
   imediato: se a amostra não se completar com os clusters, eles a completam.
10. Nenhum documento sem abstract legível entra na amostra.

### Falha e degradação

11. Falha da clusterização, ou resultado com um único cluster contendo tudo, cai num
    critério determinístico de reserva — os 6 primeiros documentos por contagem de citações
    — e a resposta registra que houve reserva. Este estágio **nunca** derruba a esteira.
12. O modelo de embeddings é carregado uma vez na subida do processo, nunca por requisição.

### Orçamento

13. Clusterizar 25 abstracts leva no máximo 1,5 s no percentil 95, já descontada a carga
    inicial do modelo.
14. A implementação mede e registra, em 50 verificações reais, a redução de tokens obtida e
    a latência acrescentada. Se a redução não compensar o custo, **o estágio é removido** e
    a amostra passa a ser escolhida pelo critério de reserva do 11. Otimização sem número
    que a justifique é complexidade, e sai.

## 4. Fora de escopo

- **Treinar modelo próprio de embeddings ou de tópicos.**
- **Tópicos globais entre verificações** (descobrir assuntos recorrentes na base). Cada
  verificação é isolada.
- **Guardar embeddings** entre requisições.
- **Interface de visualização de tópicos.**
- **Usar o cluster para decidir o veredito.** O agrupamento organiza; quem julga é o Juiz.
- **Traduzir abstracts.**
- **Rodar como serviço separado.** Fica no processo do backend (002, revisão da arquitetura).

## 5. Comportamento de IA

Não há LLM aqui, mas o estágio **não é determinístico em qualidade**: agrupar texto por
semelhança acerta mais ou menos. As duas naturezas se separam assim:

**Determinístico** (teste unitário, sem rede):

- Menos de 10 abstracts pula a clusterização (critério 3).
- Semente fixa: rodar duas vezes a mesma entrada dá saída idêntica (critério 4).
- Embaralhar a ordem da entrada não muda o agrupamento (critério 5).
- Amostra nunca passa de 6, nunca inclui documento sem abstract.
- Cluster minoritário relevante sempre representado (critério 8), com um caso de 20
  documentos em que 4 formam o grupo divergente.
- Falha da clusterização cai na reserva e não propaga exceção (critério 11).
- O modelo é carregado uma vez: um teste conta as cargas em três requisições seguidas.

**Probabilístico** (eval set):

- **Dataset:** `verificador/backend/evals/bertopic.jsonl` — ao menos 15 conjuntos de
  abstracts reais colhidos de buscas verdadeiras, cada um com os documentos rotulados à mão
  como pertinentes ou ruído, e ao menos 5 conjuntos contendo literatura dos dois lados.
- **Meta:** a amostra de 6 contém ao menos 4 documentos rotulados pertinentes; nos
  conjuntos com literatura dividida, os dois lados aparecem na amostra em ≥ 80% dos casos.
- **Erro inaceitável:** devolver amostra inteiramente composta de ruído quando havia
  documentos pertinentes; eliminar por completo o lado minoritário num conjunto dividido.

## 6. Critérios de sucesso mensuráveis

- **SC-01** — Em 50 verificações reais, o estágio reduz em ao menos 60% a quantidade de
  texto que chega ao Juiz, comparado a mandar tudo.
- **SC-02** — A latência que ele acrescenta fica abaixo de 1,5 s no percentil 95.
- **SC-03** — Nos conjuntos de eval com literatura dividida, os dois lados chegam ao Juiz em
  ao menos 80% dos casos.
- **SC-04** — Nenhuma verificação falha por causa deste estágio.
- **SC-05** — A decisão de manter ou remover o estágio está registrada com os números que a
  sustentam (critério 14).

## 7. Premissas

- Os abstracts estão majoritariamente em inglês; o modelo de embeddings escolhido dá conta
  de texto científico nesse idioma.
- O volume por requisição é pequeno — no máximo 25 documentos (005, critério 8).
- O modelo cabe na memória da máquina de desenvolvimento da equipe.
- Clusterizar 10 a 25 documentos é um uso atípico do BERTopic, pensado para corpora
  grandes; a qualidade nesse volume é justamente o que o eval set precisa medir.

## 8. Perguntas em aberto

- [ ] O limiar de cluster minoritário do critério 8 (3 documentos ou 20%) foi escolhido no
      papel. Ele interage direto com a pergunta nº 1 da 007, sobre quando virar
      `divergente` — as duas deveriam ser respondidas juntas.
- [ ] Qual modelo de embeddings, e ele cabe no orçamento de latência? Decisão de `plan.md`,
      mas se nenhum couber, o critério 13 é que muda.
- [ ] Com 10 a 25 documentos, o BERTopic entrega agrupamento melhor que uma ordenação
      simples por similaridade? Se não entregar, o critério 14 já manda removê-lo.
- [ ] A carga inicial do modelo atrasa a subida do backend a ponto de atrapalhar o
      desenvolvimento (recarga a cada `--reload`)?

## 9. Histórico

| Data | Mudança |
| :--- | :--- |
| 2026-09-16 | Criação da spec |
