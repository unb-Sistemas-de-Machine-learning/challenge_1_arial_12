# 022 — Agente Pesquisador e esteira real do `/verificar`

| Campo | Valor |
| :--- | :--- |
| **Status** | em revisão |
| **Autor** | Breno Fernandes |
| **Branch** | `feature/020-agente-pesquisador` |
| **Issue** | [#20](https://github.com/unb-Sistemas-de-Machine-learning/challenge_1_arial_12/issues/20) |
| **Depende de** | `002` (busca OpenAlex), `003` (Triador e camada LLM), `004` (Juiz), `009` (persistência), `011` (erro padronizado) |

---

## 1. Objetivo

O leitor que seleciona um trecho recebe um veredito de verdade, calculado a partir dos estudos encontrados para aquela alegação, e não mais a resposta fixa da Fase 01.

## 2. Contexto

Na visão de contêineres da [Arquitetura](../../docs/pages/arquitetura.md) (item 4), o **Agente Pesquisador** gerencia a aquisição de dados: recebe as variações do Triador, decide entre cache e busca externa e entrega os trabalhos ao Juiz. Hoje `src/agents/pesquisador.py` está vazio e `POST /verificar` devolve um veredito fixo.

As peças de baixo já existem e são reutilizadas sem mudança de comportamento:

- **Triador** (`003-agente-triador`): transforma o trecho em strings de busca. Se o LLM falhar, segue só com o trecho original.
- **Cliente OpenAlex** (`002`): busca em paralelo, repete falhas transitórias, remonta abstracts e remove repetidos pelo id da OpenAlex.
- **Juiz** (`004`): já descarta trabalhos sem abstract ou sem DOI e devolve `nada_encontrado` sem chamar o LLM quando não sobra nenhum.
- **Persistência** (`009`): `registrar_veredito` grava a verificação e devolve o `id` que o feedback (`021`) usa.

Esta spec cria o Pesquisador e liga a esteira **Triador → Pesquisador → Juiz** em `POST /verificar`. O gateway passa a só orquestrar; a aquisição de dados da esteira fica no Pesquisador.

## 3. Critérios de aceite

### Pesquisador

1. O Pesquisador recebe a lista de buscas do Triador e devolve uma lista consolidada de trabalhos, **sem duplicatas por DOI**. A comparação ignora maiúsculas e o prefixo `https://doi.org/`. Trabalhos sem DOI continuam sendo desduplicados pelo id da OpenAlex.
2. As buscas são disparadas concorrentemente, respeitando um **limite de concorrência configurável** pelo `.env`. Com o limite em `N`, nunca há mais de `N` buscas em andamento ao mesmo tempo.
3. Falha em parte das buscas não derruba a verificação: o resultado consolida as que funcionaram e registra no log quais falharam e por quê.
4. Falha em **todas** as buscas resulta no erro padronizado `openalex_indisponivel` (HTTP 503).
5. Existe um **ponto único de extensão** para consultar um cache antes da busca externa, por string de busca. Sem cache configurado, toda busca vai à OpenAlex. Com um cache que já tem a resposta, a OpenAlex não é chamada para aquela string.
6. O Pesquisador chama o cliente da OpenAlex diretamente, por função, e **nunca** a rota HTTP `POST /buscar`.
7. O Pesquisador **não** descarta trabalhos sem abstract ou sem DOI: esse filtro já é do Juiz e não é duplicado.

### Esteira em `POST /verificar`

8. `POST /verificar` executa Triador → Pesquisador → Juiz e devolve o `Veredito` produzido pelo Juiz, no mesmo contrato HTTP de hoje (`Veredito` da B05). A extensão não precisa mudar.
9. `routes.py` não contém lógica de aquisição para a esteira: a rota apenas chama as três etapas, registra o veredito e responde.
10. O veredito é gravado com `registrar_veredito`, e o `id` devolvido ao leitor é o da linha gravada, válido para `POST /feedback`. Se a gravação falhar, o leitor recebe o mesmo veredito com `id = null` (a extensão esconde os botões de feedback) e a falha é registrada no log; a verificação não vira erro.
11. Erros chegam à extensão no formato padronizado da spec `011`:
    - todas as buscas falharam → `openalex_indisponivel` (503);
    - o Juiz estourou o tempo → `llm_timeout` (504);
    - o Juiz não conseguiu responder de forma válida → `llm_indisponivel` (503).
12. Falha do LLM **no Triador** não vira erro: a esteira segue só com o trecho original, como já definido na spec do Triador.
13. `POST /buscar` continua existindo, sem mudança de contrato, para testes manuais (Postman, `/docs`).
14. O campo `termos` do veredito traz os **conceitos** que o Triador extraiu do trecho (intervenção, desfecho, condição e população, já na forma canônica do glossário), um por item, sem vazios e sem repetição. Quando o LLM do Triador falha, `termos` vem vazio e a extensão esconde a seção.
15. O Juiz recebe no máximo **5 trabalhos**, o padrão atual do cliente OpenAlex (`TOP_PADRAO`). O valor pode ser aumentado depois, se a qualidade pedir.
16. Não há teto de tempo para a verificação inteira: cada etapa segue com o próprio timeout já configurado (LLM e OpenAlex).
17. O `verificador/README.md` informa que testar `POST /verificar` exige `LLM_API_KEY` e `OPENALEX_MAILTO` preenchidos no `.env`, e o roteiro local deixa de prometer o circuito "sem IA e sem OpenAlex". Não existe modo mock: sem chave, `/verificar` responde `llm_indisponivel` (503).

## 4. Fora de escopo

- **Implementar o cache de buscas.** Aqui só existe o ponto de extensão e um "sem cache" padrão; o cache real tem issue própria.
- Reaproveitar um veredito anterior pelo hash do trecho (`buscar_por_hash`).
- BERTopic, ranqueamento ou qualquer reclassificação dos trabalhos além da ordem que a OpenAlex e o cliente já produzem.
- Servidor MCP para a OpenAlex.
- Mudar o comportamento do Juiz, o prompt de qualquer agente ou a camada de LLM. No Triador, a única mudança é **expor** os conceitos que ele já extrai (critério 14); as buscas que ele gera continuam idênticas.
- Orçamento de tempo total para a verificação.
- Mudar a extensão ou o contrato HTTP de `/verificar`, `/buscar` e `/feedback`.
- Remover o campo `url` do pedido (discussão separada, ligada à spec `021`).
- Novo eval set: o Pesquisador é determinístico, e Triador e Juiz já têm os seus.

## 5. Comportamento de IA

O Pesquisador **não usa LLM**. A esteira usa os LLMs do Triador e do Juiz sem alterar prompt nem schema deles.

**Determinístico** (vira teste unitário/integração, sem rede e sem LLM real):

- Desduplicação por DOI, inclusive com DOI em formatos diferentes.
- Limite de concorrência respeitado.
- Falha parcial consolida o restante; falha total vira `openalex_indisponivel`.
- Cache com resposta evita a chamada externa; sem cache, toda busca vai à OpenAlex.
- `/verificar` com dublês de Triador, OpenAlex e LLM: devolve o veredito do Juiz com o `id` gravado, e cada falha prevista vira o erro padronizado correspondente.

**Probabilístico:** não há eval novo. As metas continuam sendo as das specs do Triador e do Juiz.

## 6. Perguntas em aberto

- [x] **`termos` do veredito.** Decidido: conceitos do Triador (critério 14).
- [x] **Falha ao gravar no banco.** Decidido: veredito com `id = null` e falha no log (critério 10), para não descartar uma análise que já custou duas chamadas de LLM.
- [x] **Quantos trabalhos vão ao Juiz.** Decidido: mantém 5 (critério 15). Aumentar só se a qualidade pedir, sabendo que muitos trabalhos chegam sem abstract.
- [x] **Tempo total da verificação.** Decidido: sem teto nesta entrega (critério 16).
- [x] **Sem `LLM_API_KEY` no servidor.** Decidido: aceito, sem modo mock; o README é atualizado (critério 17).

## 7. Histórico

| Data | Mudança |
| :--- | :--- |
| 2026-10-05 | Criação da spec a partir da issue #20; o contrato fica numa spec própria porque a `004` virou a spec do Juiz |
| 2026-10-05 | Decide `termos` (conceitos do Triador), limite de 5 trabalhos, ausência de teto de tempo, README sem modo mock e `id = null` quando a gravação falha; spec vai para revisão |
| 2026-10-05 | Critério 17 simplificado no plano: sem chave, `/verificar` responde `llm_indisponivel` sempre, pela dependência `obter_cliente_llm` que já existe |
