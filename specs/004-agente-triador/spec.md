# 004 - Agente Triador: portão de economia e canonização da alegação

| Campo | Valor |
| :--- | :--- |
| **Status** | rascunho |
| **Autor** | Carlos Eduardo Mota |
| **Branch** | `feature/004-agente-triador` |
| **Depende de** | [002](../002-esteira-de-agentes/spec.md) (contrato do estágio 1 e regra de privacidade) |

---

## 1. Objetivo

Antes de gastar qualquer busca ou qualquer token de pesquisa, o sistema decide se o trecho
selecionado contém mesmo uma alegação verificável — e, se contém, reduz o trecho a uma
frase única e precisa, em inglês, que a busca consiga usar.

## 2. Contexto

O Triador é o primeiro estágio da esteira (002, critérios 7 a 10) e o único que roda em
**toda** seleção, inclusive nas que serão descartadas. É por isso que ele é o maior
mecanismo de economia do projeto: cada trecho barrado aqui é uma esteira inteira que não
rodou.

A [arquitetura](../../docs/pages/arquitetura.md) descreve o Triador como quem "gera
variações com o mesmo significado semântico para ampliar a cobertura da busca". A 002
mudou esse papel: quem formula consulta é o Pesquisador, que decide as próprias buscas no
laço de ferramentas (001). O Triador é **portão e canonizador** — decide se passa, e
entrega a alegação num formato único.

A 002 já fixou, e esta spec não renegocia: duas camadas, sendo a primeira sem modelo
(critério 8); teto de 400 tokens na segunda (critério 10); entrada em qualquer idioma
(critério 7); e saída sempre com `alegacao_pt` e `alegacao_en`.

## 3. Critérios de aceite

### Entrada

1. Recebe `{trecho, idioma}`. **Não recebe a URL** da matéria: o Triador não tem uso para
   ela, e o que não é recebido não pode vazar para um prompt nem para um log.
2. Um trecho repetido nas últimas 24h devolve o resultado guardado, sem chamar modelo. A
   chave é o trecho normalizado (minúsculas, espaços colapsados, pontuação de borda
   removida). Selecionar duas vezes a mesma frase custa zero.

### Camada 1 — determinística, sem modelo

3. Barra, sem custo de token: trecho sem nenhuma letra; trecho que é uma pergunta; trecho
   composto apenas por nomes e números sem predicado (manchete, legenda, título de
   tabela); e trecho com marcador explícito de opinião em primeira pessoa ("eu acho",
   "na minha opinião", "I think", "creo que").
4. As regras que dependem de idioma só se aplicam aos idiomas com lista mantida no
   repositório — português, inglês e espanhol na primeira entrega. Idioma fora dessa lista
   passa direto pelas regras linguísticas e só encontra as que independem de idioma.
5. **Na dúvida, passa.** Barrar uma alegação legítima é o erro caro: a pessoa nunca saberá
   que havia estudo, e nem nós. Deixar passar um trecho ruim custa no máximo 400 tokens.
6. Cada regra da camada 1 tem, nos testes, um caso que ela barra e um caso vizinho que ela
   **não pode** barrar.

### Camada 2 — modelo

7. Só roda no que sobreviveu à camada 1. Devolve `{verificavel, motivo, alegacao_pt,
   alegacao_en, entidades, dominio, ha_outras_alegacoes}`.
8. `verificavel: false` vem sempre com `motivo` em uma frase, em português, dizendo o que
   falta — "é uma opinião", "não afirma nada verificável", "é uma previsão sobre o futuro".
9. `alegacao_pt` e `alegacao_en` preservam **todo número, percentual, população e recorte
   temporal** presentes no trecho. "Reduz em 50% o risco em idosos" não pode virar "reduz o
   risco": é exatamente esse detalhe que depois separa `sustenta` de `exagera`.
10. Trecho com mais de uma alegação gera a **mais específica**, e `ha_outras_alegacoes`
    marca que havia outras — o painel avisa a pessoa de que só uma foi verificada.
11. `entidades` contém apenas termos presentes no trecho (ou sua tradução direta). Termo
    que o modelo acrescentou por conta própria é saída inválida.
12. `dominio` vem de um conjunto fechado: saúde, nutrição, clima, tecnologia,
    comportamento, outro.
13. Custa no máximo 400 tokens e uma única chamada de modelo, com limite de 3 s e uma
    retentativa.

### Falhas

14. Saída malformada do modelo tem uma tentativa de correção; persistindo, o estágio
    devolve `indisponivel` — **nunca** `nao_verificavel`. Falha nossa não pode ser
    apresentada ao usuário como "sua frase não dá para verificar".
15. Modelo fora do ar ou estouro de tempo devolve `indisponivel`.

### Observabilidade

16. Cada verificação registra em qual camada o trecho foi barrado, ou que passou pelas
    duas. Sem esse número não há como saber se o portão está apertado demais ou frouxo
    demais.

## 4. Fora de escopo

- **Gerar variações da consulta de busca.** É do Pesquisador (001). O Triador entrega uma
  alegação, não um conjunto de termos de busca.
- **Traduzir o veredito final.** A justificativa em português é do Juiz (002, critério 21).
- **Detectar o idioma.** Chega pronto do Gateway; se vier errado, o Triador não corrige.
- **Verificar mais de uma alegação por seleção.**
- **Julgar se a alegação é verdadeira.** O Triador não sabe nada de literatura; ele só
  decide se a frase é do tipo que se pode verificar.
- **Separar o Triador em contêiner próprio.** Continua dentro do backend.

## 5. Comportamento de IA

**Determinístico** (teste unitário, com dublê no lugar do modelo):

- Cada regra da camada 1, com seu par barra/não-barra (critério 6).
- Trecho barrado na camada 1 não constrói prompt algum: o dublê registra zero chamadas.
- Regras linguísticas não se aplicam a idioma fora da lista (critério 4).
- Saída malformada → uma correção → `indisponivel`, nunca `nao_verificavel` (critério 14).
- `dominio` fora do conjunto fechado é saída inválida.
- `entidades` com termo ausente do trecho é saída inválida.
- Teto de 400 tokens e de uma chamada por verificação.
- Acerto de cache não chama modelo.
- A URL não aparece em nenhum prompt nem em nenhuma estrutura recebida pelo estágio.

**Probabilístico** (eval set):

- **Dataset:** `verificador/backend/evals/triador.jsonl` — ao menos 40 trechos colhidos de
  matérias reais, rotulados verificável/não verificável, com pelo menos: 5 trechos fora do
  português, 5 opiniões disfarçadas de fato, 5 manchetes sem predicado, 5 trechos com duas
  alegações e 5 alegações com número ou percentual.
- **Meta:** ≥ 90% de acerto no portão; em 100% dos casos verificáveis com número, o número
  sobrevive na `alegacao_en` (critério 9).
- **Erro inaceitável:** barrar alegação legítima — o erro caro do critério 5; perder o
  quantificador da frase original; inventar entidade que não estava no trecho.

## 6. Critérios de sucesso mensuráveis

- **SC-01** — Numa amostra de 50 seleções reais feitas por pessoas fora da equipe, ao menos
  30% são descartadas antes de qualquer chamada de modelo.
- **SC-02** — Nenhuma alegação legítima da amostra é barrada pela camada 1.
- **SC-03** — O estágio inteiro responde em até 1 s no percentil 95, e instantaneamente
  quando o trecho já foi triado nas últimas 24h.
- **SC-04** — O custo médio do Triador por seleção fica abaixo de 250 tokens, somando as
  seleções barradas de graça.
- **SC-05** — A equipe consegue dizer, a qualquer momento, quantas seleções pararam em cada
  camada.

## 7. Premissas

- O Gateway já validou tamanho e formato do trecho (002, critério 1); o Triador não repete
  essa validação.
- O idioma chega detectado pela extensão ou pelo Gateway.
- A literatura está em inglês, então `alegacao_en` é o que interessa à busca; `alegacao_pt`
  existe para o Juiz e para a tela.
- Um modelo pequeno e barato dá conta da camada 2 — a escolha é do `plan.md`.

## 8. Perguntas em aberto

- [ ] Manchete sem verbo ("Café e câncer: o que diz a ciência") é barrada pela camada 1 —
      mas é justamente o tipo de trecho que alguém selecionaria. Barrar mesmo, ou mandar
      para a camada 2 decidir?
- [ ] Existe limiar de confiança abaixo do qual o modelo diz "não sei"? Hoje a saída é
      binária, e um "não sei" tratado como `false` é o erro caro do critério 5.
- [ ] Alegação sobre o futuro ("vai revolucionar o tratamento") é `nao_verificavel` ou é
      uma alegação exagerada a ser julgada pelo Juiz? O critério 8 hoje assume a primeira.
- [ ] O conjunto fechado de domínios (critério 12) serve para alguma coisa hoje, ou é campo
      que ninguém vai ler? Se não tem uso, sai — custa tokens.

## 9. Histórico

| Data | Mudança |
| :--- | :--- |
| 2026-09-16 | Criação da spec |
