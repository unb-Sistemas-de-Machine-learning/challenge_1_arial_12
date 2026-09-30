# 003 - Camada de acesso a LLM com timeout e degradação

| Campo | Valor |
| :--- | :--- |
| **Status** | em revisão |
| **Autor** | Breno Fernandes |
| **Branch** | `feature/003-camada-llm` |
| **Issue** | #17 |
| **Depende de** | `006`, `011` |

---

## 1. Objetivo

Os agentes Triador e Juiz chamam um LLM por uma única porta, que devolve um
objeto já validado ou um erro claro. Quando o provedor demora ou falha, o
leitor vê uma mensagem amigável, e nunca um erro 500.

## 2. Contexto

Atende aos contêineres **Agente Triador** e **Agente Juiz** da
[arquitetura](../../docs/pages/arquitetura.md), sem implementar nenhum deles.
A camada não contém regra de agente: não sabe o que é "gerar variações" nem
"julgar evidência". Ela só recebe um prompt e o formato esperado da resposta.

**Provedores: só camada gratuita.** A equipe decidiu não usar nada pago. A
camada fala com **Groq** e **Google Gemini**, que oferecem uso gratuito e
expõem um endpoint compatível com a API da OpenAI. Por isso a biblioteca
`openai`, já presente em `requirements.txt`, continua sendo o cliente HTTP:
o que muda entre os provedores é só o endereço, a chave e o modelo.

A configuração vem da spec `006`. Os códigos de erro seguem o contrato fechado
da spec `011`, que já tem `llm_timeout`.

## 3. Critérios de aceite

1. Existe uma interface única, `ClienteLLM.gerar(prompt, schema)`, que recebe
   o prompt e um modelo Pydantic e devolve uma instância desse modelo, já
   validada.
2. Uma resposta que não é JSON ou não obedece ao schema levanta
   `RespostaInvalidaDoLLM`. Nenhum dicionário parcial é devolvido.
3. Cada chamada tem um timeout total, configurável por `LLM_TIMEOUT_SEGUNDOS`
   (padrão **15 s**) e sobrescrevível por chamada. Um provedor dublado que
   demora mais que o limite faz a chamada terminar com `LLMTempoEsgotado`
   dentro do limite, e não quando o provedor responde.
4. Toda chamada registra em log, numa linha, o provedor, o modelo, a latência
   em ms, os tokens de entrada e de saída, o número de tentativas e o
   resultado. Nenhum log contém a chave de API, inclusive nos casos de falha.
5. Existe um dublê de LLM (`DubleLLM`) com o mesmo formato do provedor real.
   Ele é injetável: a rota recebe o cliente por `Depends(obter_cliente_llm)`,
   que o teste troca por `app.dependency_overrides`. Toda a suíte unitária
   roda sem rede e sem chave real.
6. Falhas transitórias do provedor (429, 5xx, falha de conexão) são repetidas
   até `LLM_MAX_TENTATIVAS` (padrão **2**). Esgotadas as tentativas, ou diante
   de uma recusa definitiva (chave inválida, modelo inexistente), a chamada
   levanta `LLMIndisponivel`.
7. O gateway traduz os erros da camada para o contrato da spec `011`:

   | Erro da camada | Status | `codigo` |
   | :--- | :--- | :--- |
   | `LLMTempoEsgotado` | 504 | `llm_timeout` |
   | `LLMIndisponivel` | 503 | `llm_indisponivel` (novo) |
   | `RespostaInvalidaDoLLM` | 503 | `llm_indisponivel` (novo) |

8. `LLM_PROVEDOR` aceita apenas `groq` ou `gemini`. Qualquer outro valor
   impede a inicialização com um erro que nomeia a variável.

## 4. Fora de escopo

- Os agentes Triador e Juiz, seus prompts e seus eval sets.
- Ligar a camada à rota `/verificar`, que continua devolvendo o veredito mock.
- Qualquer provedor pago (OpenAI, Anthropic etc.) ou modelo local (Ollama).
- Streaming de resposta, chamadas de ferramenta (*tool calling*) e imagens.
- Cache de respostas do LLM (é a spec do Cache).
- Troca automática de provedor quando um falha (*fallback* Groq → Gemini).
- Controle de cota diária da camada gratuita. O 429 do provedor já é tratado
  como falha transitória.

## 5. Comportamento de IA

**Determinístico** (vira teste unitário normal):

- A resposta é validada contra o schema. Aceita-se JSON cercado por bloco de
  código markdown, porque alguns modelos o enviam mesmo em modo JSON.
- Resposta inválida não é repetida: repetir gasta cota gratuita e, na maior
  parte das vezes, o mesmo prompt gera o mesmo erro.
- Timeout, retry e tradução de erro, todos testados com o dublê.

**Probabilístico:** não se aplica aqui. A qualidade da resposta é medida nos
eval sets dos agentes.

## 6. Perguntas em aberto

- [x] Qual provedor usar? **Groq e Gemini, só na camada gratuita.**
- [ ] A camada gratuita do Gemini permite que o Google use os dados enviados
  para melhorar os produtos dele. Os trechos são de notícias públicas, então a
  equipe precisa confirmar se isso é aceitável.
- [ ] O modelo padrão de cada provedor deve ser revisto antes da entrega: a
  lista de modelos gratuitos muda com frequência.

## 7. Histórico

| Data | Mudança |
| :--- | :--- |
| 2026-09-29 | Criação da spec |
