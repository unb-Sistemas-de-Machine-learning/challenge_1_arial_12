# 003 - Feedback do usuário e taxa de aceitação

| Campo | Valor |
| :--- | :--- |
| **Status** | rascunho |
| **Autor** | Carlos Eduardo Mota |
| **Branch** | `feature/003-feedback-do-usuario` |
| **Depende de** | [002](../002-esteira-de-agentes/spec.md) (contrato, `id_requisicao` e regra de privacidade) |

---

## 1. Objetivo

Depois de ler o veredito, a pessoa diz em um clique se aquilo ajudou — e a equipe passa a
saber, em número, se o produto está servindo para alguma coisa.

## 2. Contexto

O `README.md` do projeto declara que o sucesso do Verificador se mede pela **taxa de
aceitação**: o usuário julga o resultado exibido, e esse ciclo valida a utilidade prática
da ferramenta. Hoje isso é impossível de medir — a extensão não tem botão de voto, o
backend não tem rota para recebê-lo e não existe identificador que ligue um voto ao
veredito que o provocou.

Esta spec fecha essa lacuna. Ela é pequena de propósito e **não depende da esteira de IA
estar pronta**: funciona contra o veredito mock de hoje, e continua funcionando quando o
mock for substituído. É a primeira entrega que pode ir para a mão de um usuário real.

Duas decisões já tomadas na 002 mandam aqui e não se renegociam nesta spec:

- Todo veredito carrega um `id_requisicao` (002, critério 2), e o voto se refere a ele.
- Voto e alegação vivem em tabelas **sem chave entre si** (002, critério 25). Não deve
  existir consulta capaz de responder "quem votou o quê sobre qual frase".

## 3. Critérios de aceite

### Interface

1. Quando o painel exibe um resultado final, aparecem dois botões — **útil** e **não
   útil** — no rodapé do painel, junto de uma pergunta curta ("este resultado ajudou?").
2. Os botões aparecem em **todo** estado final, inclusive `nada_encontrado` e
   `nao_verificavel`. Um "não útil" num `nao_verificavel` é o sinal mais valioso que
   existe: quer dizer que o portão do Triador barrou algo que a pessoa queria verificar.
3. Os botões **não** aparecem durante o carregamento nem no estado `indisponivel` — não se
   pede avaliação de um erro.
4. Clicar registra na hora: o botão escolhido fica marcado, a pergunta é substituída por
   "obrigado", e a interface **não espera** a resposta do servidor para confirmar.
5. Enquanto o painel estiver aberto, a pessoa pode trocar o voto; cada verificação tem no
   máximo um voto registrado, e vale o último.
6. Falha de rede ao enviar o voto **não** é mostrada ao usuário: tenta-se uma vez, e o
   voto se perde em silêncio. Estressar o leitor por causa da nossa telemetria é pior do
   que perder um dado.
7. Os botões são alcançáveis por teclado, têm rótulo textual lido por leitor de tela, área
   de clique de ao menos 32×32 px e seguem a paleta de
   [style_guidelines](../../docs/pages/style_guidelines.md).
8. Fechar e reabrir o painel com uma nova seleção começa uma verificação nova, com
   `id_requisicao` novo e sem voto.

### Backend

9. `POST /feedback` aceita `{id_requisicao, util}`, devolve 204 e nada mais; `util` é
   booleano, sem terceiro valor.
10. `id_requisicao` desconhecido devolve 404 e não cria linha nenhuma.
11. Voto repetido para o mesmo `id_requisicao` sobrescreve o anterior, sem erro.
12. `/feedback` tem limite de 60 requisições por minuto por origem.
13. O `id_requisicao` é gerado pelo Gateway como identificador aleatório — **nunca**
    derivado da alegação, da URL ou de qualquer hash do conteúdo. Um id derivado do texto
    religaria as duas ilhas de dados e anularia o critério 25 da 002.

### Dados

14. Toda verificação concluída grava uma linha na tabela de votos no momento da resposta,
    com `id_requisicao`, estado do veredito, latência total, tokens consumidos, acerto de
    cache, data e hora, e o campo de voto **vazio**. O voto preenche esse campo depois,
    se vier. Isso torna mensurável não só a aceitação, mas quantas pessoas se dão ao
    trabalho de votar.
15. Essa tabela **não** contém a alegação, o trecho selecionado, a URL, o dossiê nem
    qualquer chave estrangeira para a tabela de cache.
16. A hora gravada tem precisão de hora, não de segundo — carimbo de tempo exato é dado
    reidentificador quando a base é pequena.
17. Um comando único devolve, a partir **só** dessa tabela: total de verificações, quantas
    receberam voto, taxa de aceitação global e taxa por estado.
18. Os dados são apagados ao fim do projeto ou após 12 meses, o que vier primeiro.

## 4. Fora de escopo

- **Campo de texto livre** para a pessoa explicar o voto — é o próximo passo natural, mas
  texto livre volta a ser dado potencialmente identificador e merece spec própria.
- **Painel ou dashboard de métricas.** O critério 17 é um comando de terminal, não uma tela.
- **Telemetria para serviço externo** (Analytics, Sentry e afins). Nada sai da máquina.
- **Contas, identidade de usuário ou deduplicação por pessoa.** Não sabemos quem votou, e
  é assim que deve ser.
- **Usar o voto para retreinar ou ajustar prompt automaticamente.** O voto informa a
  equipe; quem muda prompt é gente, com eval set (constituição, princípio III).
- **Teste A/B de variações de veredito.**
- **Sincronizar votos entre navegadores ou dispositivos.**

## 5. Comportamento de IA

Esta feature **não usa LLM**. Todos os critérios acima são determinísticos e viram teste
automatizado normal. Não há eval set associado.

Atenção na revisão: o voto é *sobre* a saída de um agente, mas não é entrada de agente
nenhum. Se alguém propuser realimentar o voto no prompt, isso é outra spec.

## 6. Critérios de sucesso mensuráveis

- **SC-01** — Um integrante roda um comando e obtém a taxa de aceitação, sem abrir o banco
  à mão e sem cruzar tabelas.
- **SC-02** — Numa sessão de teste com 5 pessoas fora da equipe, ao menos 30% das
  verificações recebem voto.
- **SC-03** — O retorno visual do clique é imediato — a pessoa não percebe espera, mesmo
  com o backend lento.
- **SC-04** — Inspecionando o schema, não existe caminho de consulta que ligue um voto ao
  texto que a pessoa selecionou.
- **SC-05** — O fluxo inteiro, do veredito ao voto, é completável só com teclado.

## 7. Premissas

- O veredito exibido continua sendo o mock enquanto a esteira não estiver pronta; isso não
  impede testar o fluxo de voto com gente de verdade.
- Postgres disponível pelo `docker-compose` do backend.
- Sem autenticação: qualquer pessoa com a extensão pode votar, e um voto por verificação é
  proteção suficiente contra ruído nesta escala.
- O volume da fase de testes é de dezenas de verificações por dia, não milhares.

## 8. Perguntas em aberto

- [ ] Votos em `nao_verificavel` entram na taxa de aceitação principal ou são contados à
      parte? Misturá-los mede duas coisas diferentes no mesmo número.
- [ ] Qual a amostra mínima antes de a equipe olhar a taxa e decidir alguma coisa? Com 12
      votos, qualquer número parece significativo e não é.
- [ ] O voto some ao fechar o painel (critério 5) ou a pessoa pode mudar de ideia depois,
      reabrindo? Hoje a spec assume que some.
- [ ] Guardar a hora com precisão de hora (critério 16) atrapalha alguma análise de
      latência que vocês queiram fazer depois?

## 9. Histórico

| Data | Mudança |
| :--- | :--- |
| 2026-09-16 | Criação da spec |
