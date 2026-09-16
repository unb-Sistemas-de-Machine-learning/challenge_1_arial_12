# 005 - Ferramenta MCP de busca na OpenAlex

| Campo | Valor |
| :--- | :--- |
| **Status** | rascunho |
| **Autor** | Carlos Eduardo Mota |
| **Branch** | `feature/005-ferramenta-mcp-openalex` |
| **Depende de** | [002](../002-esteira-de-agentes/spec.md) (estágio 4) · consumida pela [001](../001-agente-pesquisador/spec.md) |

---

## 1. Objetivo

O Agente Pesquisador consegue buscar literatura científica real chamando uma única
ferramenta, com parâmetros declarados — e o sistema devolve estudos com abstract legível,
sem que o agente precise saber nada sobre a API da OpenAlex.

## 2. Contexto

É o estágio 4 da esteira (002, critérios 15 a 18) e a única peça que fala com o mundo lá
fora. Tudo que o Pesquisador enxerga da literatura passa por aqui.

**Esta ferramenta pode ser adotada pronta ou construída por nós.** Existem servidores MCP
para a OpenAlex publicados no GitHub, e adotar um poupa trabalho real — a API da OpenAlex
tem armadilhas (o abstract vem como índice invertido, a paginação é peculiar, o *polite
pool* muda o comportamento do limite de taxa) que alguém já resolveu. Mas adotar também
traz dependência de código de terceiro num ponto crítico do produto.

Esta spec **não escolhe** entre as duas. Ela define o contrato que a ferramenta deve
cumprir de qualquer forma, e os critérios objetivos que decidem a adoção — de modo que a
escolha seja uma decisão registrada no `plan.md`, com justificativa, e não um hábito.

## 3. Critérios de aceite

### O contrato da ferramenta (vale para qualquer origem)

1. Expõe **uma** ferramenta de busca, com schema declarado, aceitando: termos de busca,
   ano mínimo e máximo, exigir presença de abstract, excluir retratados e limite de
   resultados (teto de 25).
2. É **inteiramente determinística**: nenhuma chamada de modelo dentro dela. Mesmos
   parâmetros, mesmo resultado enquanto a OpenAlex não mudar.
3. Devolve, por resultado: identificador OpenAlex, título, ano, DOI, autores, contagem de
   citações, marca de retratação e o texto do abstract.
4. Reconstrói o abstract a partir do índice invertido da OpenAlex. Registro cujo abstract
   não possa ser reconstruído é devolvido **marcado como sem abstract** — nunca com texto
   parcial passando por completo.
5. A marca de retratação reflete o campo da OpenAlex; na ausência do campo, o registro é
   marcado como "retratação desconhecida", não como "não retratado".
6. Identifica a aplicação à OpenAlex (*polite pool*), com tempo limite de 5 s e uma única
   retentativa.
7. Falha, tempo esgotado ou resposta inesperada sinalizam **indisponibilidade** ao
   chamador. Lista vazia significa "busquei e não achei" e nada mais.
8. O limite de 25 resultados é imposto do nosso lado, mesmo que a origem aceite mais: é o
   que protege o orçamento de tokens do Pesquisador.

### Fronteira de adaptação (o que torna a troca barata)

9. O Pesquisador fala com uma **interface interna nossa**, nunca com o servidor MCP
   diretamente. Trocar servidor de terceiro por implementação própria — ou o contrário —
   não altera uma linha do agente.
10. A normalização para o nosso formato de registro acontece nessa fronteira. Nenhum
    formato de terceiro vaza para dentro da esteira.
11. Existe um **teste de contrato** que roda contra a implementação ativa, seja ela qual
    for, cobrindo os critérios 1 a 8. Uma origem que não passa nesse teste não entra.

### Critérios para adotar um servidor de terceiros

12. Só é adotável o servidor que, verificadamente: tem licença compatível com o projeto;
    não exige chave paga; cobre os filtros do critério 1; reconstrói o abstract
    (critério 4); roda localmente sem enviar nossas consultas a nenhum serviço além da
    própria OpenAlex; e teve manutenção nos últimos 6 meses.
13. Servidor adotado é **fixado por versão**, nunca seguindo a branch principal do autor.
14. O levantamento das opções disponíveis, com a avaliação de cada uma contra o critério
    12, é registrado na tabela de decisões do `plan.md`. Se nenhuma opção passar, a decisão
    é construir — e isso também fica escrito.
15. Adotar um servidor não dispensa o teste de contrato do critério 11, nem a fronteira do
    critério 9.

### Privacidade

16. Só a consulta formulada pelo agente sai da máquina — nunca o trecho selecionado pelo
    usuário, nem a URL da matéria.
17. Servidor de terceiro que colete telemetria, mesmo anônima, é inadotável.

## 4. Fora de escopo

- **Bases além da OpenAlex** (PubMed, Crossref, Semantic Scholar).
- **Cache dos resultados.** É responsabilidade da esteira (002, critério 11) e do
  Pesquisador (001), não da ferramenta.
- **Decidir o que buscar.** A ferramenta não formula consulta; ela executa a que recebeu.
- **Ranquear ou filtrar por relevância semântica.** Quem faz isso é o BERTopic (006).
- **Escrever na OpenAlex** ou usar qualquer endpoint que não seja de leitura.
- **Publicar nosso servidor MCP**, caso construamos um.

## 5. Comportamento de IA

Esta feature **não usa LLM** — o critério 2 proíbe explicitamente. Ela é consumida por um
agente, o que é diferente de ser um agente.

Testes, portanto, são todos determinísticos:

- Reconstrução do abstract invertido, com um caso real gravado e um caso de índice
  corrompido.
- Cada filtro do critério 1 aplicado isoladamente.
- Teto de 25 imposto mesmo quando a resposta traz mais.
- Registro sem campo de retratação vira "desconhecida", não "não retratada" (critério 5).
- Tempo esgotado e resposta malformada viram indisponibilidade, não lista vazia.
- Nenhum teste unitário toca a rede: tudo roda sobre respostas gravadas da OpenAlex.
- **Um** teste de integração, marcado e fora da suíte padrão, bate na OpenAlex de verdade
  para detectar quando a API mudar sob nossos pés.

## 6. Critérios de sucesso mensuráveis

- **SC-01** — Trocar a origem da ferramenta (terceiro ↔ própria) não exige mudança em
  nenhum arquivo do Pesquisador, e o teste de contrato passa nas duas.
- **SC-02** — Numa amostra de 50 buscas reais, ao menos 80% dos resultados devolvidos têm
  abstract legível.
- **SC-03** — Uma busca completa responde em até 2 s no percentil 95.
- **SC-04** — Nenhuma verificação envia à rede qualquer texto que a pessoa selecionou.
- **SC-05** — A decisão adotar-ou-construir está registrada com as opções avaliadas, e um
  integrante que não participou consegue reconstruir o porquê lendo o `plan.md`.

## 7. Premissas

- A OpenAlex atende sem chave e o limite gratuito comporta o volume da equipe.
- O *polite pool* exige apenas um e-mail de contato, que é variável de ambiente.
- O servidor MCP roda local, no mesmo host do backend.
- A OpenAlex pode mudar formato sem aviso — daí o teste de integração do critério de
  testes acima.

## 8. Perguntas em aberto

- [ ] Qual servidor MCP de terceiro, se houver algum que passe no critério 12? O
      levantamento ainda não foi feito — é a primeira tarefa do `plan.md`.
- [ ] O servidor se comunica por entrada e saída padrão ou por HTTP local? Muda como o
      backend o inicia e como ele é empacotado no `docker-compose`.
- [ ] Quem reroda o teste de integração e com que frequência? Um teste que ninguém executa
      não detecta mudança nenhuma da API.
- [ ] As respostas gravadas usadas nos testes são atualizadas quando? Fixture velha dá
      falsa sensação de segurança.
- [ ] Se adotarmos um servidor e ele for abandonado no meio do projeto, o plano é
      implementar na hora ou manter um fork? O critério 9 torna as duas baratas, mas a
      decisão precisa existir antes da urgência.

## 9. Histórico

| Data | Mudança |
| :--- | :--- |
| 2026-09-16 | Criação da spec |
