# 002 — Busca de trabalhos na OpenAlex

| Campo | Valor |
| :--- | :--- |
| **Status** | implementada |
| **Autor** | Equipe Arial 12 |
| **Branch** | `feature/002-busca-openalex` |
| **Depende de** | `006` — configuração centralizada; `011` — contrato de erro |
| **Origem** | Task "Ponte MCP de busca na OpenAlex" |

---

## 1. Objetivo

Permitir que o veredicto seja formado a partir de literatura científica real, e
não de um estudo fixo: strings de busca entram e saem os trabalhos publicados
mais relevantes, com título, ano, DOI, indicador de retratação e abstract.

## 2. Contexto

É o contêiner 6 da [visão de contêineres](../../docs/pages/arquitetura.md#22-nível-2-contêineres),
a integração que converte uma busca em requisição para a OpenAlex API. Antes
desta spec, `POST /verificar` devolvia o veredicto fixo da spec `010`.

É a primeira integração com um sistema de terceiro, e é ela que define como o
projeto se comporta quando a OpenAlex está lenta, limitando o tráfego ou
devolvendo um registro incompleto. A spec `011` já reservou o código de erro
`openalex_indisponivel` para esse caso.

**A task original pedia um servidor MCP; esta spec entrega HTTP puro.** O
porquê está na seção 6c.

## 3. Critérios de aceite

### A busca

1. `POST /buscar` recebe uma **lista** de strings de busca e devolve os
   trabalhos das várias buscas numa lista única. Cada trabalho tem `id`,
   `titulo`, `ano`, `doi`, `retratado`, `abstract`, `relevancia` e `citacoes`.
2. O resultado traz **5 trabalhos por padrão** — o top 5 que a OpenAlex já
   ordenou por relevância, sem reclassificação nossa.
3. Com várias buscas, a lista final intercala por **posição**: o 1º de cada,
   depois o 2º de cada. Não por `relevancia`, porque o escore mede o quanto o
   trabalho casa com *aquela* string e a escala muda com a string — medido,
   para o mesmo assunto: 870 na formulação curta contra 227 na longa.
4. O mesmo trabalho encontrado por duas buscas aparece uma vez só. A identidade
   é o identificador da OpenAlex; sem ele, o DOI; sem os dois, título e ano.
5. Cada string é repassada à OpenAlex sem alteração, para que a sintaxe dela
   funcione: aspas para frase exata, `AND`, `OR` e `NOT` em maiúsculas, e
   parênteses para agrupar.
6. `total_por_busca` informa quantos trabalhos casaram com cada string antes do
   corte. "Achei 5" e "achei 5 de 4.293" levam a decisões diferentes.
7. Uma busca que falha não derruba as outras: ela é nomeada em
   `buscas_com_falha`, com o motivo, e as demais entregam o que acharam. Só
   quando **nenhuma** funciona é que o erro sobe.

### A requisição à OpenAlex

8. Toda requisição identifica o projeto para o *polite pool*: o e-mail de
   contato configurado vai no parâmetro `mailto` e no `User-Agent`. Sem e-mail
   configurado, o cliente falha ao ser criado, e não no meio de uma verificação.
9. Uma chave de API, se configurada, vai no cabeçalho `Authorization` — nunca
   na URL. É opcional, mas sem ela a OpenAlex trata o tráfego como anônimo e
   responde `503` sob carga, mesmo com o `mailto` preenchido. Esse `503`
   específico produz uma mensagem que nomeia a causa e a correção.
10. Toda requisição tem timeout explícito. Falha transitória — `429`, `5xx`,
    timeout ou erro de conexão — é repetida até um número máximo de tentativas,
    com espera crescente; um `Retry-After` recebido é respeitado dentro de um
    teto.
11. Erro que não é transitório (`4xx` fora do `429`) não é repetido.
12. Esgotadas as tentativas, o cliente levanta `OpenAlexIndisponivel`. Nenhuma
    exceção de `httpx` atravessa a fronteira do módulo.

### Leitura da resposta

13. Um trabalho sem abstract ou sem DOI devolve `null` nesses campos e continua
    na lista; nenhum registro incompleto derruba a busca inteira. O mesmo vale
    para título e ano ausentes, que a OpenAlex não produz hoje mas cujo
    contrato permite.
14. O DOI é devolvido em forma curta (`10.1234/abcd`), e o `id` também
    (`W2110406916`), sem os prefixos de URL que a OpenAlex usa.
15. O abstract é remontado a partir do índice invertido da OpenAlex, na ordem
    original das palavras.
16. Um trabalho retratado devolve `retratado: true`; a ausência do campo na
    resposta vale como `false`.

### Limites e entrada

17. O número de resultados é configurável em dois níveis: `limite` (quantos
    saem no fim, 5 por padrão) e `quantidade` (candidatos por busca, teto de
    200 — o limite que a própria OpenAlex impõe ao `per-page`). Pedido acima do
    teto é reduzido, e não recusado. A lista aceita até 10 strings, e o
    resultado no máximo 500 trabalhos.
18. A ordenação é escolhível entre relevância (padrão), citações e ano; fora de
    relevância a OpenAlex devolve `relevancia` nula, porque só a calcula quando
    é o critério.
19. Lista vazia, ou só com strings em branco, é recusada sem chamar a rede;
    strings repetidas não geram requisição duplicada. Uma string passada no
    lugar da lista é recusada, e não iterada caractere a caractere.

### HTTP e testes

20. As falhas de `POST /buscar` usam o contrato de erro da spec `011`:
    configuração ausente e indisponibilidade dão `503 openalex_indisponivel`;
    lista inválida e consulta recusada pela OpenAlex dão
    `422 entrada_invalida`. Nenhuma mensagem crua vaza para o corpo.
21. Nenhum teste unitário faz chamada de rede, e isso é **verificado**: abrir
    soquete dentro de `src/tests/unit/` estoura o teste. As respostas da
    OpenAlex são fixtures gravadas de chamadas reais; o único corpo montado à
    mão é o do registro sem título e sem ano, que não existe na base para ser
    gravado.
22. Existe um teste de integração que consulta a API de verdade, marcado de
    modo que a verificação automática **não** o execute.

## 4. Fora de escopo

- Chamar a busca a partir de `POST /verificar`. A rota continua devolvendo o
  veredicto fixo da spec `010`. `POST /buscar` **não** é a esteira: ela devolve
  a busca crua, sem Triador e sem Juiz.
- O Agente Pesquisador, o Triador e qualquer uso de LLM.
- Cache de buscas (spec própria, com meta de taxa de acerto).
- **Clusterização com BERTopic.** Ver seção 6b.
- **Servidor MCP.** Ver seção 6c.
- Paginação além dos 200 de uma página, e filtro por ano ou tipo de trabalho.
- Buscar em outras bases (Crossref, PubMed, Retraction Watch).
- Persistir as respostas da OpenAlex no Postgres.
- Limitar quem pode chamar `POST /buscar`. Ver seção 6a.

## 5. Comportamento de IA

Não se aplica. A busca é uma integração HTTP determinística: mesma entrada e
mesma resposta da OpenAlex produzem exatamente a mesma lista. Nenhum modelo é
chamado.

## 6. Perguntas em aberto

- [ ] **Quem registra a chave gratuita da OpenAlex?** Descoberto durante a
      implementação: o `mailto` sozinho não basta mais. Sob carga, a API
      responde `503` com "Anonymous search is paused… use a free API key", e
      considera anônimo quem manda só o `mailto`. O suporte à chave já está
      implementado e é opcional; falta alguém criar a conta em
      <https://openalex.org/rest-api> e pôr o valor no `.env`. Enquanto isso, a
      busca funciona de forma intermitente.
- [ ] Qual e-mail a equipe usa no *polite pool*? Precisa ser uma caixa que
      alguém lê: é por ele que a OpenAlex avisa antes de bloquear. O `.env` de
      quem desenvolve hoje usa um endereço pessoal; `.env.example` fica com o
      campo em branco de propósito, porque é arquivo versionado.
- [ ] O trecho selecionado pelo usuário é português e a OpenAlex indexa quase
      tudo em inglês. A tradução é responsabilidade do Triador (spec própria) ou
      desta busca? Assumido aqui: do Triador — a busca recebe a string pronta.

## 6a. Consequência aceita: `/buscar` é pública

A rota não tem autenticação nem limite próprio. Quem alcançar a API consome a
cota da OpenAlex do projeto — e, se houver `OPENALEX_API_KEY`, a cota
identificada. Aceito para esta entrega porque a API roda em `localhost` durante
o desenvolvimento.

Antes de qualquer implantação exposta, isto precisa de resposta: limite por
origem (a spec de *rate limiting* já está em andamento noutra branch) ou tornar
a busca interna, chamada só por `/verificar`.

## 6b. Por que não há BERTopic

O contêiner 7 da [arquitetura](../../docs/pages/arquitetura.md) prevê clusterizar
os abstracts para filtrar ruído e amostrar antes do Juiz. Ele resolve um
problema real — uma consulta de revisão sistemática casa com milhares de
trabalhos, e 4.293 abstracts são ~1,19 milhão de tokens, contra os ~200 mil de
contexto de um modelo.

A decisão foi resolver o mesmo problema sem ele: **a OpenAlex já ordena por
relevância**, e o top 5 dela é a amostra. Custa zero token, zero dependência
(o BERTopic puxa `torch`, ~2 GB) e zero latência.

O que se perde: diversidade temática. Os 5 mais relevantes podem falar todos do
mesmo recorte, enquanto o BERTopic garantiria um representante por agrupamento.
Se o veredicto começar a errar por ver sempre o mesmo ângulo, é aqui que se
volta.

## 6c. Por que não há servidor MCP

A task original pedia uma ponte MCP, e ela chegou a ser construída: um servidor
`FastMCP` expondo a ferramenta `buscar_trabalhos`, testado e funcionando.

Foi removido em 2026-09-28. O motivo é que ele não estava comprando nada. MCP
é um protocolo para expor ferramentas a modelos **através de um processo
separado**, falando JSON-RPC por `stdin`/`stdout`. Faz sentido quando o cliente
é externo — o Claude Desktop, outra IDE. Aqui o agente e a busca moram no mesmo
processo Python, então o protocolo acrescentava um subprocesso, uma
serialização e uma dependência (`mcp==1.2.0`) para uma chamada de função.

E, no fim da linha, **a OpenAlex não fala MCP**: ela tem uma API REST. O
servidor MCP era um adaptador de HTTP para HTTP, com JSON-RPC no meio.

O que se perde: plugar a busca num cliente MCP de terceiros sem escrever
código. Se isso virar requisito, o caminho de volta é curto — `ClienteOpenAlex`
não mudou, e a camada MCP eram ~40 linhas.

**A `arquitetura.md` ainda descreve o contêiner 6 como "MCP Server" e o
contêiner 7 como BERTopic.** Atualizá-la é decisão da equipe, não desta spec.

## 7. Histórico

| Data | Mudança |
| :--- | :--- |
| 2026-09-28 | Criação da spec a partir da task de busca na OpenAlex |
| 2026-09-28 | Implementação do cliente, da ferramenta MCP e dos testes com fixtures gravadas |
| 2026-09-28 | Entrada passa a ser uma lista de buscas, com desduplicação por trabalho e falha parcial reportada; `Trabalho` ganha `id` |
| 2026-09-28 | Suporte a `OPENALEX_API_KEY`: a API passou a cortar busca anônima sob carga, e só o `mailto` não evita o `503` |
| 2026-09-28 | Rota temporária `POST /dev/buscar` sob `APP_DEBUG`, com coleção Bruno, para exercitar a busca por HTTP |
| 2026-09-28 | Amostra ordenada por relevância com `total_por_busca`, `relevancia` e `citacoes`; teto por busca vai a 200. Guarda de soquete torna o critério 21 verificável |
| 2026-09-28 | Top 5 direto da relevância da OpenAlex, sem BERTopic; lote intercala por posição, não por escore |
| 2026-09-28 | Camada MCP removida: HTTP puro. Módulo vai para `src/services/openalex.py`, a busca vira `POST /buscar` pública e `mcp` sai das dependências |
