# 007 - Agente Juiz: veredito e justificativa

| Campo | Valor |
| :--- | :--- |
| **Status** | rascunho |
| **Autor** | Carlos Eduardo Mota |
| **Branch** | `feature/007-agente-juiz` |
| **Depende de** | [002](../002-esteira-de-agentes/spec.md) (estágio 6) · consome a saída de [001](../001-agente-pesquisador/spec.md) e [006](../006-bertopic/spec.md) |

---

## 1. Objetivo

O leitor recebe uma frase curta em português dizendo se a alegação que ele selecionou se
sustenta na literatura encontrada — e essa frase nunca diz mais do que os estudos em mãos
permitem dizer.

## 2. Contexto

O Juiz é o último estágio da esteira (002, critérios 21 a 23) e o único que produz texto
que a pessoa lê. Também é o estágio com maior potencial de dano: um `sustenta` errado
transforma a ferramenta contra o seu próprio propósito — em vez de combater desinformação,
ela a chancela com aparência de rigor científico.

Por isso esta spec é escrita mais como uma lista de coisas que o Juiz **não pode** fazer do
que de coisas que ele faz.

A 002 já fixou, e esta spec não renegocia: cinco estados de conteúdo, com `divergente`
próprio; justificativa de até 280 caracteres em português; teto de 1.500 tokens; nenhuma
citação de estudo que não esteja na lista recebida; zero evidências nunca vira `sustenta`.

## 3. Critérios de aceite

### Entrada

1. Recebe: `alegacao_pt`, de 0 a 6 evidências (título, ano, DOI, autores, contagem de
   citações, marca de retratação e até 600 caracteres de abstract), os termos
   representativos do cluster escolhido, quantos abstracts foram descartados no caminho e
   se o Triador viu outras alegações no trecho.
2. **Não recebe** a URL, o nome do veículo, nem o trecho original selecionado — só a
   alegação canônica. O Juiz não pode julgar a fonte jornalística; ele julga a frase.

### O veredito

3. Devolve `{estado, justificativa, evidencias_de_apoio, evidencias_contrarias}`, com os
   dois últimos sendo listas de índices da lista recebida.
4. O estado vem do conjunto fechado da 002: `sustenta`, `exagera`, `contradiz`,
   `divergente`, `nada_encontrado`.
5. **O veredito sai apenas das evidências recebidas.** Se o modelo "sabe" que a alegação é
   falsa mas nenhuma evidência em mãos diz isso, a resposta é `nada_encontrado`. Conhecimento
   de mundo do modelo não é literatura científica e não pode entrar pela porta dos fundos.
6. `sustenta` exige ao menos uma evidência de apoio e nenhuma contrária.
7. `contradiz` exige ao menos uma evidência contrária.
8. `divergente` exige ao menos uma evidência de **cada** lado. `divergente` apoiado em um
   lado só é saída inválida.
9. `exagera` é para alegação com base real mas ampliada além do que os estudos dizem —
   número inflado, população estendida, certeza que o estudo não tem. Exige ao menos uma
   evidência de apoio, e a justificativa diz **o que** foi esticado.
10. Zero evidências, ou nenhuma evidência relacionada à alegação, devolve
    `nada_encontrado`, e a justificativa não inventa explicação.
11. Evidência marcada como retratada, ou com retratação desconhecida (005, critério 5),
    nunca entra em `evidencias_de_apoio`.

### A justificativa

12. No máximo 280 caracteres, em português simples, sem jargão acadêmico não explicado.
13. Não repete a alegação palavra por palavra — a pessoa acabou de lê-la.
14. Menciona ao menos uma das evidências apontadas nos índices.
15. Número ou percentual só aparece na justificativa se estiver no abstract recebido.
16. Quando `ha_outras_alegacoes` vem marcado, a justificativa avisa que só uma alegação do
    trecho foi verificada.

### Validação da saída (feita no código, não pedida no prompt)

17. Todo DOI, título ou ano citado na justificativa deve existir na lista recebida.
    Violação **não é mostrada ao usuário**: vira `indisponivel`, e o caso é registrado.
18. Índices fora da faixa, estado fora do conjunto fechado, combinação proibida pelos
    critérios 6 a 11 e justificativa acima de 280 caracteres são saídas inválidas, tratadas
    como no critério 17.
19. Saída malformada tem uma tentativa de correção; persistindo, `indisponivel`.

### Orçamento e falha

20. Uma única chamada de modelo, no máximo 1.500 tokens somando entrada e saída, com tempo
    limite de 5 s e **sem** retentativa automática — retentar aqui estoura o orçamento de
    latência da esteira inteira.
21. Falha do Juiz devolve `indisponivel`, e o painel oferece tentar de novo (002,
    critério 24). As evidências **não** são exibidas sem veredito.
22. O dossiê já obtido permanece no cache, de modo que a retentativa custe apenas esta
    chamada.

## 4. Fora de escopo

- **Escolher ou reordenar evidências.** Elas chegam prontas do Pesquisador e do BERTopic.
- **Buscar mais literatura** quando as evidências são fracas. O Juiz não tem ferramentas.
- **Grau de confiança numérico** exibido ao usuário.
- **Conversa de acompanhamento** ("por que você disse isso?").
- **Traduzir o veredito** para outros idiomas — sempre português (002, clarificação).
- **Avaliar a qualidade metodológica** dos estudos (tamanho amostral, desenho, revisão por
  pares). É desejável e é outra spec.
- **Julgar a matéria ou o veículo.**

## 5. Comportamento de IA

**Determinístico** (teste unitário, com dublê no lugar do modelo):

- Cada regra dos critérios 6 a 11, com um caso válido e um inválido: `divergente` com um
  lado só, `sustenta` com evidência contrária, `sustenta` com zero evidências, retratado em
  `evidencias_de_apoio`.
- Dublê que inventa um DOI → `indisponivel`, e nada disso chega à tela (critério 17).
- Justificativa com 281 caracteres é saída inválida.
- Índice fora da faixa e estado inexistente são saídas inválidas.
- Teto de 1.500 tokens e de uma chamada por verificação.
- A URL e o trecho original não aparecem em nenhuma estrutura recebida pelo estágio.
- Nenhum teste unitário chama modelo real.

**Probabilístico** (eval set):

- **Dataset:** `verificador/backend/evals/juiz.jsonl` — ao menos 30 casos, cada um com
  alegação **e** conjunto fixo de evidências, para que o eval rode sem rede e sem depender
  da busca. Cobre os cinco estados, com ao menos 5 casos de `divergente`, 5 de
  `nada_encontrado` e 3 em que a alegação é notoriamente falsa **mas** as evidências em
  mãos não dizem nada a respeito — o teste do critério 5.
- **Rotulagem:** cada caso é rotulado por dois integrantes, de forma independente. Caso em
  que os dois discordam é reescrito ou descartado. Se a equipe não concorda sobre o rótulo,
  ele não serve de gabarito.
- **Meta:** ≥ 75% de acerto de estado; ≥ 95% no subconjunto cuja resposta certa é
  `nada_encontrado`.
- **Erro inaceitável:** `sustenta` sem evidência que sustente; citar estudo que não estava
  na lista; usar conhecimento de mundo em vez das evidências (critério 5); devolver
  `sustenta` num caso rotulado `divergente`, escondendo do leitor que a ciência está em
  disputa.

## 6. Critérios de sucesso mensuráveis

- **SC-01** — Em 30 verificações lidas pela equipe, nenhuma justificativa afirma algo que
  não esteja nas evidências mostradas.
- **SC-02** — Cinco pessoas fora da equipe leem 10 vereditos e explicam corretamente, com
  as próprias palavras, o que cada rótulo significa.
- **SC-03** — O estágio responde em até 2 s no percentil 95 e custa em média menos de 1.200
  tokens.
- **SC-04** — Nenhum caso de artigo retratado apresentado como apoio, em nenhuma execução
  do eval set.
- **SC-05** — A taxa de "não útil" (spec 003) em vereditos `sustenta` e `contradiz` fica
  abaixo de 30% na sessão de teste com usuários.

## 7. Premissas

- As evidências chegam relevantes o suficiente: filtrar ruído é trabalho do BERTopic (006),
  não do Juiz.
- 600 caracteres de abstract bastam para julgar a maioria dos casos; se a medição mostrar o
  contrário, é o número que muda, por emenda.
- O modelo do Juiz é mais capaz (e mais caro) que o do Triador — a escolha é do `plan.md`.
- A justificativa curta é preferível à completa: o veredito é lido no meio de uma leitura,
  não como um artigo.

## 8. Perguntas em aberto

- [ ] Quantas evidências contrárias bastam para virar `divergente` em vez de `sustenta`?
      Uma contrária entre seis de apoio provavelmente não é divergência — é ruído.
- [ ] O Juiz deve ver ano e contagem de citações? Ajuda a pesar a evidência, mas pode
      enviesar para o artigo mais citado, que nem sempre é o mais pertinente.
- [ ] O que fazer quando todas as evidências são fracas (preprint, sem revisão, quase sem
      citações)? Hoje elas valem tanto quanto qualquer outra.
- [ ] 280 caracteres dão conta de explicar um `exagera`, que é o rótulo que mais exige
      nuance? Vale testar antes de fixar o número.
- [ ] `indisponivel` por saída inválida (critério 17) fica invisível para o usuário — como
      a equipe descobre que isso está acontecendo com frequência?

## 9. Histórico

| Data | Mudança |
| :--- | :--- |
| 2026-09-16 | Criação da spec |
