# 002 - Esteira de agentes: contrato ponta a ponta do Verificador

| Campo | Valor |
| :--- | :--- |
| **Status** | rascunho |
| **Autor** | Carlos Eduardo Mota |
| **Branch** | `feature/002-esteira-de-agentes` |
| **Depende de** | — (é a spec-mãe; a [001](../001-agente-pesquisador/spec.md) detalha um de seus estágios) |

---

## 1. Objetivo

O leitor seleciona uma frase numa matéria e recebe, em segundos, um veredito com os
estudos por trás dele — e diz se aquilo lhe foi útil. Esta spec define o contrato de cada
peça dessa esteira, para que elas possam ser construídas em paralelo e substituídas uma a
uma sem quebrar as vizinhas.

## 2. Contexto

Esta é uma spec de **arquitetura e contratos**, não de uma funcionalidade isolada. Ela
existe porque a [Arquitetura](../../docs/pages/arquitetura.md) descreve os contêineres em
prosa, mas não diz o que cada um recebe, o que decide e o que devolve — e sem isso duas
pessoas implementando lados diferentes não se encontram (princípio II da constituição).

As specs filhas implementam os estágios; esta define as fronteiras entre eles.

### 2.1 Revisão crítica da arquitetura atual

Sete pontos apurados lendo `docs/pages/arquitetura.md` contra o código que existe hoje.
Não tratamos o documento como verdade — ele é a hipótese inicial.

| # | O que a arquitetura diz | Problema | O que esta spec decide |
| :-- | :--- | :--- | :--- |
| 1 | Triador "gera variações com o mesmo significado semântico para ampliar a cobertura da busca" | Colide com o Pesquisador, que na 001 formula as próprias consultas. Duas peças decidindo a mesma coisa | Triador vira **portão e canonizador**: decide se há alegação verificável, extrai a alegação em uma frase e a verte para inglês. Quem formula consulta é o Pesquisador |
| 2 | Pesquisador "repassa as strings para o cache ou para o integrador externo" | Isso é roteamento, não agência. Um roteador não precisa de LLM | Vira agente com laço de ferramentas, teto de 3 iterações (spec 001) |
| 3 | "Cache Validator" é um contêiner | Uma tabela e duas funções não são um contêiner; a separação cobra latência de rede sem devolver nada | Cache é um **serviço interno** do backend sobre o Postgres, consultado pelo Gateway antes de qualquer LLM |
| 4 | BERTopic é um "Python Service" | Clusterizar 6 documentos não reduz ruído, só custa latência; e um serviço à parte exige modelo carregado em memória separada | Roda **no processo do backend** e só acima de 10 abstracts (spec 001, critério 11) |
| 5 | Postgres guarda "feedback do usuário e histórico de requisições do cache" | Não diz se guarda a URL da matéria — que revela o que a pessoa está lendo | Decisão de privacidade explícita nesta spec (critério 25) |
| 6 | Nada é dito sobre falha de LLM, de rede ou de OpenAlex | A esteira tem 5 pontos de falha externa e nenhum comportamento definido | Estado `indisponivel` em toda a esteira, com degradação definida no critério 24 |
| 7 | "O Gateway registra o feedback" | A extensão **não tem** feedback nenhum hoje, nem id que ligue voto e veredito — logo a taxa de aceitação, que é a métrica de sucesso do produto no README, é hoje immensurável | `id_requisicao` no contrato desde já (critério 2) e rota de feedback (critério 5) |

### 2.2 Estado real do código

- `backend/main.py` devolve um veredito fixo; `backend/src/` está praticamente vazio.
- `extensao/tipos.ts` comporta **um** estudo e três estados; a esteira produz várias
  evidências e sete estados (ver critério 3).
- Não existe Postgres em uso, nem cliente da OpenAlex, nem servidor MCP, nem eval set.

## Clarificações

### Sessão 2026-09-16

- Q: O que fica guardado no banco quando alguém vota num veredito? → A: Voto +
  `id_requisicao` + estado do veredito + métricas. A alegação vive apenas na tabela de
  cache, sem chave que ligue as duas. URL não é persistida em lugar nenhum.
- Q: Quantos rótulos de veredito existem e como tratar literatura dividida? → A: Cinco
  estados de conteúdo — `sustenta`, `exagera`, `contradiz`, `divergente`,
  `nada_encontrado` —, com `divergente` como rótulo próprio para literatura em disputa.
- Q: Com o Juiz fora do ar, mostramos as evidências sem veredito? → A: Não. O painel diz
  apenas que não foi possível verificar agora e oferece tentar de novo. O dossiê já obtido
  fica no cache, para que a retentativa não repita a busca.
- Q: O portão de "isto é alegação verificável?" usa LLM ou regra? → A: Regra
  determinística primeiro (barata, testável); o LLM só julga o que passa pelo filtro.
- Q: E se o trecho selecionado não estiver em português? → A: Qualquer idioma é aceito na
  entrada; o Triador verte a alegação para inglês como já faz, e a justificativa do Juiz
  sai sempre em português.

## 3. Critérios de aceite

### Contrato da fronteira externa (extensão ↔ Gateway)

1. `POST /verificar` aceita `{trecho, url, idioma}` com trecho entre 10 e 500 caracteres;
   fora disso devolve erro de validação sem acionar a esteira.
2. Toda resposta carrega um `id_requisicao` único, que a extensão guarda e reenvia ao
   votar. Sem ele, voto e veredito não se ligam.
3. A resposta tem exatamente um destes estados: `sustenta`, `exagera`, `contradiz`,
   `divergente`, `nada_encontrado` e `nao_verificavel` — mais `indisponivel` para falha.
   `divergente` significa que a literatura encontrada está em disputa, com evidências
   relevantes dos dois lados; é rótulo próprio e não um caso de `exagera`. Os estados
   `contradiz` e `divergente` não existem no `tipos.ts` atual e são acrescentados aqui.
4. A resposta traz de 0 a 6 evidências, cada uma com título, ano, DOI, autores, contagem
   de citações e marca de retratação, além da justificativa em português e das métricas da
   requisição.
5. `POST /feedback` aceita `{id_requisicao, util}` e devolve 204; um voto para um
   `id_requisicao` inexistente é recusado.
6. `/verificar` aplica limite de 20 requisições por minuto por origem; o excedente recebe
   429 e a extensão o exibe como "aguarde um instante", não como erro.

### Estágio 1 — Triador

7. Recebe `{trecho, idioma}` em **qualquer idioma** — a extensão roda em todo site, e
   matéria em inglês é caso comum, não exceção. Devolve `{verificavel, motivo, alegacao_pt,
   alegacao_en, entidades, dominio}`: `alegacao_en` alimenta a busca e `alegacao_pt` é o que
   o Juiz e o painel exibem, traduzida quando a origem não for português. Idioma não
   reconhecido não é motivo de recusa.
8. O portão tem duas camadas. A primeira é **determinística e sem modelo**: descarta
   trecho fora dos limites de tamanho, trecho interrogativo, trecho sem verbo que sustente
   afirmação factual e trecho com marcador explícito de opinião ("eu acho", "na minha
   opinião"). A segunda só roda no que sobreviveu à primeira, e é o modelo julgando ironia,
   generalidade e ambiguidade. Trecho barrado na primeira camada custa **zero token**.
   Ambos devolvem `nao_verificavel` com o motivo em uma frase, antes de qualquer busca.
9. Reduz o trecho a uma única alegação. Trecho com duas alegações gera a mais específica,
   e o fato de haver outras é informado na resposta.
10. Quando chega à segunda camada, custa no máximo 400 tokens e uma única chamada de
    modelo. A primeira camada não tem custo de modelo.

### Estágio 2 — Cache

11. A consulta ao cache acontece **depois** do Triador e **antes** do Pesquisador, com
    chave derivada de `alegacao_en` normalizada.
12. Acerto devolve o dossiê armazenado sem nenhuma chamada externa, em até 800 ms, e é
    marcado como tal nas métricas.
13. Entrada com mais de 24h é ignorada e recomputada.

### Estágio 3 — Pesquisador

14. Definido integralmente na [spec 001](../001-agente-pesquisador/spec.md). Fronteira
    aqui: recebe a saída do Triador e o orçamento; devolve o dossiê de evidências.

### Estágio 4 — Ferramenta MCP da OpenAlex

15. Expõe uma única ferramenta de busca, com parâmetros declarados em schema: termos,
    faixa de anos, exigir abstract, excluir retratados e limite de resultados (teto 25).
16. É **inteiramente determinística**: nenhum LLM dentro dela. Recebe parâmetros, devolve
    registros normalizados.
17. Reconstrói o texto do abstract a partir do índice invertido da OpenAlex; registro cujo
    abstract não possa ser reconstruído é devolvido marcado como sem abstract, nunca com
    texto parcial silencioso.
18. Identifica a aplicação à OpenAlex (*polite pool*), tem tempo limite de 5 s e uma única
    retentativa; esgotado isso, sinaliza indisponibilidade ao chamador em vez de devolver
    lista vazia.

### Estágio 5 — BERTopic

19. Recebe apenas `[{id, abstract}]` e devolve `[{id, cluster}]` mais os termos
    representativos de cada cluster. Não recebe a alegação nem saída de LLM.
20. É pulado abaixo de 10 abstracts, e a resposta indica que foi pulado.

### Estágio 6 — Juiz

21. Recebe `alegacao_pt` e até 6 evidências, cada uma com no máximo 600
    caracteres de abstract. Devolve estado, justificativa de até 280 caracteres em
    português e os índices das evidências que o sustentam. Ao devolver `divergente`, cita
    ao menos uma evidência de **cada** lado — um `divergente` apoiado em um só lado é
    saída inválida e tratada como no critério 22.
22. **Nunca cita DOI, título ou ano que não esteja na lista recebida** — a verificação é
    determinística, feita no código sobre a saída do modelo; violação vira `indisponivel`
    e é registrada, não é mostrada ao usuário.
23. Com zero evidências devolve `nada_encontrado` sem inventar justificativa; jamais
    `sustenta`. Custa no máximo 1.500 tokens.

### Transversais

24. Falha em qualquer estágio degrada com clareza, e em nenhum caso o painel exibe
    evidência sem veredito — lista de estudos sem rótulo é lida como "confirmado" e é
    justamente a distorção que o produto combate. Triador fora do ar → `indisponivel`;
    OpenAlex fora → `indisponivel` com as consultas tentadas; Juiz fora → `indisponivel`
    com a mensagem "não foi possível verificar agora" e a opção de tentar de novo. Quando a
    busca teve êxito e só o Juiz falhou, o dossiê é gravado no cache assim mesmo, de modo
    que a retentativa custe apenas a chamada ao Juiz.
25. A URL da matéria não é persistida em nenhuma tabela; serve apenas para registro em log
    volátil de depuração. A persistência é **separada em duas ilhas sem chave entre si**: a
    tabela de cache guarda a alegação e o dossiê; a tabela de votos guarda
    `id_requisicao`, estado do veredito, métricas e o voto — e **nenhuma referência à
    alegação**. Não deve existir consulta capaz de responder "quem votou o quê sobre qual
    frase".
26. Nenhuma chave de modelo ou credencial aparece em código ou artefato versionado, e o
    `.env.example` lista toda variável nova.
27. O custo somado da esteira não passa de 5.000 tokens por verificação, e a mediana do
    tempo entre o clique e o painel preenchido fica abaixo de 4 s (8 s no percentil 95).
28. As métricas de cada requisição — estado, latência por estágio, tokens e acerto de
    cache — são persistidas na tabela de votos junto do voto, quando houver. A taxa de
    aceitação sai dessa tabela sozinha, sem precisar cruzar com o cache.

## 4. Fora de escopo

- **Implementar os estágios.** Esta spec fixa fronteiras; cada estágio tem (ou terá) a sua.
- **Escolha de provedor e modelo de LLM** — decisão de `plan.md`, não de spec.
- **Deploy, domínio, HTTPS e publicação nas lojas de extensão.**
- **Contas de usuário, histórico pessoal e sincronização entre dispositivos.**
- **Bases além da OpenAlex.**
- **Verificação de página inteira**, detecção automática de alegações sem seleção, e
  verificação de imagem ou vídeo.
- **Internacionalização da interface** — os textos do painel são em português apenas, o que
  não impede a entrada em outros idiomas (critério 7).
- **Reescrever `docs/pages/arquitetura.md`**: a atualização do documento é tarefa da
  implementação, mas o conteúdo normativo é o desta spec.

## 5. Comportamento de IA

**Determinístico** (teste unitário, com dublê no lugar de LLM e de rede):

- Contrato de entrada e saída de `/verificar` e `/feedback`, incluindo a recusa de trecho
  fora dos limites e de `id_requisicao` inexistente.
- Curto-circuito: `nao_verificavel` do Triador não aciona cache, Pesquisador, MCP,
  BERTopic nem Juiz — verificável contando as chamadas nos dublês.
- A primeira camada do portão (critério 8) é testada sozinha, sem dublê de LLM: cada regra
  de descarte tem um caso que ela barra e um caso vizinho que ela **não** pode barrar.
- Trecho barrado na primeira camada não constrói prompt nenhum: o dublê de LLM registra
  zero chamadas.
- Validação da saída do Juiz contra a lista de evidências (critério 22), com caso de teste
  em que o dublê inventa um DOI.
- A primeira camada do portão não barra trecho apenas por estar fora do português: caso de
  teste com alegação factual em inglês e em espanhol atravessando o filtro.
- Comportamento de cada estágio diante de saída inválida do modelo e de falha externa
  (critério 24), um teste por estágio.
- Tetos de tokens por estágio e teto somado.
- Ferramenta MCP: reconstrução do abstract invertido, aplicação dos filtros e limite de 25.
- Nenhum teste unitário toca rede ou LLM real.

**Probabilístico** (eval set por agente, cada um com seu arquivo):

- **Triador** — `verificador/backend/evals/triador.jsonl`: ao menos 40 trechos reais
  rotulados verificável/não verificável, incluindo os casos-limite que a primeira camada
  deixa passar de propósito (ironia, generalização, afirmação vaga) e ao menos 5 trechos
  fora do português. O eval mede as duas
  camadas juntas, como o usuário as experimenta. **Meta:** ≥ 90% de acerto no portão.
  **Erro inaceitável:** deixar passar opinião pura, que queima a esteira inteira à toa;
  barrar alegação legítima na camada determinística, que é o erro caro — o usuário nunca
  saberá que havia estudo.
- **Pesquisador** — `evals/pesquisador.jsonl`, meta e erros definidos na spec 001.
- **Juiz** — `verificador/backend/evals/juiz.jsonl`: ao menos 30 casos de alegação +
  conjunto fixo de evidências, rotulados com o estado correto, cobrindo os cinco estados de
  conteúdo e com ao menos 5 casos de `divergente`. Cada caso é rotulado por dois
  integrantes de forma independente; caso em que os dois discordam é reescrito ou
  descartado — se a equipe não concorda sobre o rótulo, ele não serve de gabarito.
  **Meta:** ≥ 75% de acerto geral e ≥ 95% no subconjunto cuja resposta certa é
  `nada_encontrado`. **Erro inaceitável:** `sustenta` sem evidência que sustente; citar
  estudo que não estava na lista; devolver `sustenta` num caso rotulado `divergente`,
  escondendo do leitor que a ciência está em disputa.

## 6. Critérios de sucesso mensuráveis

- **SC-01** — Um integrante que nunca viu o código consegue implementar um estágio lendo
  apenas esta spec e a do estágio, sem perguntar ao autor do estágio vizinho.
- **SC-02** — Trocar a implementação de um estágio (outro modelo, outra biblioteca de
  clusterização) não exige mudança em nenhum outro estágio.
- **SC-03** — Mediana abaixo de 4 s do clique ao painel; 8 s no percentil 95.
- **SC-04** — Média de no máximo 5.000 tokens por verificação; trecho não verificável custa
  no máximo os 400 tokens do Triador, e o barrado pela camada determinística custa zero.
- **SC-05** — A taxa de aceitação é calculável a qualquer momento lendo **apenas** a tabela
  de votos, sem instrumentação adicional e sem cruzar com a tabela de cache.
- **SC-06** — Em 20 verificações seguidas, nenhuma exibe estudo que não veio da OpenAlex e
  nenhuma exibe estudo sem o veredito correspondente.

## 7. Premissas

- A OpenAlex atende sem chave e seu limite gratuito comporta o volume da equipe.
- A interface é em português e a justificativa sai sempre em português, mas o trecho
  selecionado pode vir em qualquer idioma; a literatura científica está majoritariamente em
  inglês.
- Postgres, backend e BERTopic rodam na mesma máquina, via `docker-compose`, sem rede
  pública.
- A extensão roda em Chrome (MV3) e Firefox (MV2), com o `fetch` no background.
- O orçamento de latência supõe o LLM como maior parcela do tempo; se o provedor escolhido
  não couber, é o provedor que muda, não o orçamento (princípio IV).

## 8. Mapa de specs derivadas

| Spec | Estágio | Situação |
| :-- | :--- | :--- |
| 001 | [Agente Pesquisador e laço de ferramentas](../001-agente-pesquisador/spec.md) | rascunho, escrita |
| 003 | [Feedback do usuário e taxa de aceitação](../003-feedback-do-usuario/spec.md) | rascunho, escrita |
| 004 | [Agente Triador: portão de economia e canonização](../004-agente-triador/spec.md) | rascunho, escrita |
| 005 | [Ferramenta MCP de busca na OpenAlex](../005-ferramenta-mcp-openalex/spec.md) | rascunho, escrita |
| 006 | [BERTopic: redução de ruído e seleção da amostra](../006-bertopic/spec.md) | rascunho, escrita |
| 007 | [Agente Juiz: veredito e justificativa](../007-agente-juiz/spec.md) | rascunho, escrita |

Nenhuma dessas specs pode alterar as fronteiras fixadas aqui sem emendar esta spec.

## 9. Perguntas em aberto

- [ ] Que modelo roda a segunda camada do Triador? Ele é um classificador simples e
      provavelmente cabe num modelo bem mais barato que o do Juiz — decisão de `plan.md`.
- [ ] O cache é por alegação (compartilhado entre usuários) ou por usuário? Compartilhado é
      muito mais eficaz, é o que o critério 11 assume, e o critério 25 já o torna seguro.

## 10. Histórico

| Data | Mudança |
| :--- | :--- |
| 2026-09-16 | Criação da spec |
| 2026-09-16 | Sessão de clarificação: privacidade do voto, cinco estados de conteúdo, degradação sem o Juiz, portão em duas camadas, entrada multilíngue |
