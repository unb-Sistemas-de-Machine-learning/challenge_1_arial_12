# 001 - Agente Pesquisador com busca autônoma na OpenAlex

| Campo | Valor |
| :--- | :--- |
| **Status** | rascunho |
| **Autor** | Carlos Eduardo Mota |
| **Branch** | `feature/001-agente-pesquisador` |
| **Depende de** | — (primeira spec; substitui o mock da Fase 01) |

---

## 1. Objetivo

Quando o leitor seleciona uma alegação científica numa matéria, o sistema devolve os
estudos reais que sustentam ou contradizem aquela frase — e não um resultado fixo —
gastando o mínimo possível de tempo e de chamadas a modelo.

## 2. Contexto

Esta spec troca o veredito mock de `verificador/backend/main.py` pela primeira etapa
real da esteira descrita na [Arquitetura](../../docs/pages/arquitetura.md): o **Agente
Pesquisador**, a ferramenta MCP de busca na OpenAlex, o **Cache Validator** e o
**BERTopic**. O Agente Juiz continua fora: esta spec entrega o *dossiê de evidências*,
não o veredito final.

Três observações sobre o estado atual do repositório, apuradas antes de escrever isto,
porque elas mudam o que precisa ser construído:

- **O Pesquisador descrito na arquitetura não é um agente.** O documento diz que ele
  "gerencia a aquisição de dados repassando as strings para o cache ou para o integrador
  externo" — isso é um serviço de roteamento, e um serviço não precisa de LLM. Esta spec
  o redefine: o Pesquisador **decide** o que buscar, formula a consulta, lê o que voltou e
  decide se busca de novo ou se para. A arquitetura será atualizada junto com a
  implementação (ver critério 13).
- **O contrato atual só cabe um estudo.** `verificador/extensao/tipos.ts` define
  `estudo: Estudo | null`. Uma busca real devolve várias evidências, às vezes
  divergentes entre si. O contrato muda nesta spec, e a extensão muda junto — ao
  contrário do que o `verificador/README.md` afirma na seção "O que a Fase 02 encosta".
- **O layout de código da arquitetura ainda não existe.** `backend/src/main.py` está
  vazio e todo o código vive em `backend/main.py`. A implementação desta spec é a
  primeira a ocupar `src/agents/`, `src/services/` e `src/mcp/`.

## 3. Critérios de aceite

**Entrada e portão de economia**

1. O Pesquisador recebe um objeto com: a alegação em texto (até 500 caracteres), o
   idioma detectado, a URL de origem e o orçamento da requisição (teto de iterações e
   teto de tokens). Não recebe a página inteira nem o HTML.
2. Uma seleção que não contenha alegação verificável (opinião, pergunta, trecho sem
   afirmação factual) é recusada **antes** de qualquer chamada de busca ou de LLM de
   pesquisa, devolvendo `nao_verificavel` com a razão. Esse portão é o principal
   mecanismo de economia de tokens.
3. Uma alegação já consultada nas últimas 24h devolve o dossiê armazenado **sem** chamar
   o LLM e **sem** chamar a OpenAlex. A chave de cache é a alegação normalizada
   (minúsculas, espaços colapsados, pontuação removida), não o texto bruto.

**O loop do agente**

4. O Pesquisador formula a consulta em inglês, em forma de palavras-chave — nunca
   repassando a frase do usuário literalmente para a busca —, e pode aplicar filtros de
   ano, tipo de publicação, presença de abstract e status de retratação.
5. O agente executa no máximo **3 chamadas de ferramenta** por requisição. A quarta
   tentativa é impedida pelo código, não pelo prompt.
6. Entre uma chamada e outra o agente enxerga apenas **título, ano, número de citações e
   os primeiros 200 caracteres do abstract** de cada resultado. O abstract completo nunca
   entra no contexto do agente.
7. O agente para assim que tiver ao menos 8 resultados com abstract relacionados à
   alegação; se a primeira consulta já satisfaz, ele **não** faz uma segunda.
8. Uma consulta que volta vazia ou irrelevante é reformulada pelo agente ao menos uma
   vez — com termos diferentes da anterior — antes de o sistema concluir
   `nada_encontrado`.
9. Cada consulta formulada é registrada no dossiê, em ordem, com a quantidade de
   resultados que devolveu.

**Fronteira com o BERTopic**

10. O BERTopic recebe uma lista de abstracts em texto puro, cada um com seu identificador
    da OpenAlex, e devolve para cada documento o cluster a que pertence e os termos
    representativos de cada cluster. Ele não recebe a alegação do usuário nem qualquer
    saída de LLM.
11. Com menos de 10 abstracts, a clusterização é **pulada** e todos os abstracts seguem
    adiante: agrupar 4 documentos não reduz ruído nenhum e custa latência.
12. Da clusterização sai uma amostra de no máximo 6 abstracts — os mais próximos do
    centro do cluster mais alinhado à alegação —, e é só essa amostra que seguiria para o
    Juiz. O número de abstracts descartados aparece no dossiê.

**Saída**

13. A saída é um dossiê contendo: a alegação normalizada, a lista de consultas
    executadas, de 0 a 6 evidências (título, ano, DOI, autores, contagem de citações,
    marca de retratação e o trecho de abstract usado), os termos representativos do
    cluster escolhido e as métricas da requisição (iterações, tokens consumidos, latência
    e se houve acerto de cache).
14. Uma evidência marcada como retratada na OpenAlex é sinalizada no dossiê e nunca
    aparece como evidência de sustentação.
15. Falha ou indisponibilidade da OpenAlex devolve `indisponivel` com as consultas
    tentadas — nunca uma lista vazia disfarçada de `nada_encontrado`.
16. A extensão exibe as evidências devolvidas em vez do estudo único de hoje, e mostra na
    interface o que foi buscado quando o resultado é `nada_encontrado`.

**Orçamento**

17. Acerto de cache responde em até 800 ms; uma verificação completa responde em até 4 s
    na mediana e 8 s no percentil 95, medidos do clique no botão até o painel preenchido.
18. O Pesquisador consome no máximo 3.000 tokens por requisição, somando entrada e saída
    de todas as iterações. Estourar o teto encerra o loop e devolve o que já foi
    coletado, marcado como parcial.

## 4. Fora de escopo

- **O Agente Juiz e o veredito.** Esta spec entrega evidências; classificar em
  `sustenta`/`exagera` é a próxima spec. Até lá o campo de estado reflete apenas o
  resultado da busca.
- **O Agente Triador como container separado.** O portão do critério 2 e a normalização
  da alegação vivem por ora dentro do Pesquisador. Separar em container próprio só se
  medição mostrar que vale.
- **Gostei / não gostei na interface.** Vai para a spec 002.
- **Persistência do feedback no Postgres.** Idem. Aqui o Postgres só guarda o cache.
- **Bases além da OpenAlex** (PubMed, Semantic Scholar, Crossref).
- **Verificação de página inteira ou de múltiplas alegações de uma vez.** Uma seleção,
  uma alegação.
- **Autenticação, contas de usuário e histórico por pessoa.**
- **Deploy.** Tudo roda em `localhost` nesta entrega.
- **Reescrever a interface.** Só o mínimo para caber a lista de evidências.

## 5. Comportamento de IA

**Determinístico** (vira teste unitário normal, com dublê no lugar do LLM e da OpenAlex):

- O teto de 3 chamadas de ferramenta é imposto pelo código: um dublê de LLM que insiste
  em chamar a ferramenta uma quarta vez é interrompido.
- O teto de 3.000 tokens encerra o loop e devolve resultado parcial em vez de estourar.
- Saída malformada do LLM (JSON inválido, ferramenta inexistente, argumento fora do
  schema) é tratada: uma tentativa de correção e, persistindo, `indisponivel`.
- A chave de cache normaliza a alegação; duas seleções que diferem só por maiúsculas,
  espaços ou pontuação final colidem na mesma chave.
- Com menos de 10 abstracts o BERTopic não é invocado.
- A amostra enviada adiante nunca passa de 6 abstracts.
- Nenhum teste unitário chama a OpenAlex ou um LLM de verdade.

**Probabilístico** (vira eval set):

- **Dataset:** `verificador/backend/evals/pesquisador.jsonl` — ao menos 30 alegações
  colhidas de matérias reais em português, rotuladas à mão com os DOIs que uma busca
  competente deveria encontrar, incluindo casos sem literatura nenhuma e ao menos 3
  trechos que não são alegação verificável.
- **Meta:** em ≥ 70% dos casos rotulados, ao menos um dos DOIs esperados aparece entre as
  6 evidências devolvidas; média de iterações ≤ 2.
- **Erro inaceitável:** devolver evidência sem relação temática com a alegação e
  apresentá-la como relacionada; usar um artigo retratado como sustentação; gastar as 3
  iterações num trecho que deveria ter sido barrado no critério 2.

## 6. Critérios de sucesso mensuráveis

- **SC-01** — Em 30 alegações reais, ao menos 70% retornam pelo menos um estudo que um
  integrante da equipe julga pertinente ao lê-lo.
- **SC-02** — A mediana do tempo entre o clique e o painel preenchido fica abaixo de 4 s.
- **SC-03** — Com a mesma alegação repetida, a segunda verificação responde abaixo de
  800 ms e não gera chamada externa.
- **SC-04** — O custo médio por verificação não passa de 3.000 tokens, e trechos não
  verificáveis custam zero token de pesquisa.
- **SC-05** — Nenhuma verificação apresenta artigo retratado como evidência de apoio.

## 7. Premissas

- A OpenAlex responde sem chave de API e seu limite gratuito comporta o volume de testes
  da equipe; o *polite pool* (e-mail no cabeçalho) é usado.
- A literatura é majoritariamente em inglês, e a alegação chega em português — traduzir a
  consulta é responsabilidade do agente.
- Abstract vazio ou ausente acontece com frequência na OpenAlex; resultado sem abstract
  não serve como evidência.
- O Postgres do `docker-compose.yml` está disponível para o cache.
- O BERTopic roda no mesmo processo do backend nesta fase, sem serviço separado.
- A extensão e o backend continuam em `localhost`, sem autenticação.

## 8. Perguntas em aberto

- [ ] A tradução da alegação para inglês é feita pelo próprio LLM do agente (mais barato,
      uma chamada a menos) ou por uma etapa dedicada e testável?
- [ ] O que conta como "relacionado" no critério 7 — o julgamento do próprio agente, ou um
      corte por similaridade calculado fora do LLM?
- [ ] **Emenda pendente ao critério 12.** A [spec 006](../006-bertopic/spec.md), critério 8,
      determina que um cluster minoritário relevante sempre entre na amostra — do contrário
      o veredito `divergente` da [007](../007-agente-juiz/spec.md) nunca aconteceria. O
      critério 12 daqui ainda diz "o cluster mais alinhado" e precisa ser corrigido quando a
      006 for aprovada.
- [ ] A URL de origem é guardada no cache e no log? Ela diz o que a pessoa estava lendo —
      decidir antes de persistir qualquer coisa.
- [ ] Qual LLM e qual provedor, considerando o orçamento de latência do critério 17?

## 9. Histórico

| Data | Mudança |
| :--- | :--- |
| 2026-09-16 | Criação da spec |
