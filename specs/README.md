# Specs (Spec-Driven Development)

Esta pasta é a fonte da verdade do desenvolvimento do Verificador Científico.
Nenhuma feature entra no código sem passar por aqui primeiro.

A ideia do **SDD (Spec-Driven Development)** é simples: a especificação vem
antes do código, a revisão da equipe acontece na especificação (e não só no
code review), e o código é o resultado de executar aquilo que foi combinado.
Como boa parte da implementação é assistida por IA, um documento claro vale
mais do que instruções soltas no chat — a IA segue a spec, e o que não estiver
escrito nela será inventado.

---

## Índice de specs

| # | Spec | Status | Branch |
| :-- | :--- | :--- | :--- |
| 006 | [Configuração centralizada do backend](006-configuracao-centralizada/spec.md) | em revisão | `feature/006-configuracao-centralizada` |
| 007 | [Inicialização da API pelo Docker Compose](007-app-fastapi-compose/spec.md) | implementada | `feature/007-app-fastapi-compose` |
| 010 | [Contrato de verificação + healthcheck](010-contrato-verificacao-healthcheck/spec.md) | em revisão | `feature/010-rota-verificar-health` |

**Status possíveis:** `rascunho` → `em revisão` → `aprovada` → `implementada`.
Uma spec que morreu no caminho vira `abandonada`, mas **continua na tabela** e
o número dela nunca é reaproveitado.

---

## Onde fica cada coisa

```text
challenge_1_arial_12/
├── specs/                     # SDD mora aqui, na raiz
│   ├── README.md              # este arquivo: índice + instruções
│   ├── _template/             # molde que você copia para criar uma spec nova
│   │   ├── spec.md            # o QUE e o PORQUÊ
│   │   ├── plan.md            # o COMO
│   │   └── tasks.md           # os passos
│   └── NNN-slug-curto/        # uma pasta por feature
│       ├── spec.md
│       ├── plan.md
│       └── tasks.md
├── verificador/
│   ├── backend/               # o código, derivado das specs
│   └── extensao/              # extensão de navegador
└── docs/                      # site publicado (docsify)
```

Os specs ficam na raiz, e não dentro de `docs/`, porque são artefato de
engenharia: nascem e morrem junto do código, são revisados em PR e mudam a cada
entrega. A pasta `docs/` guarda a documentação estável do produto e do processo,
publicada pelo docsify.

Os datasets de avaliação dos agentes de IA **não** ficam aqui: eles são dado de
teste e moram em `verificador/backend/evals/`, versionados junto do código. A spec apenas
aponta para o arquivo e define a meta.

---

## Os três documentos

| Arquivo | Responde | Quem lê | Quando é escrito |
| :--- | :--- | :--- | :--- |
| `spec.md` | O que vamos construir e por quê | a equipe inteira | antes de tudo |
| `plan.md` | Como vamos construir | quem implementa | depois da spec aprovada |
| `tasks.md` | Em que ordem | quem implementa (e a IA) | depois do plano |

A separação existe por um motivo prático: discutir "o veredicto precisa citar
as fontes" é uma conversa de produto, e discutir "as fontes vêm num campo
`evidencias` do JSON" é uma conversa de engenharia. Misturar as duas faz a
primeira desaparecer.

---

## Passo a passo para criar uma feature

### Passo 1 — Escolha o número

Olhe as pastas existentes e pegue o **próximo número livre**, com três dígitos.
Se o último é `003`, o seu é `004`. Números nunca são reutilizados nem
renumerados, porque eles aparecem em branch, PR e commit — é o que permite
voltar de uma linha de código até a decisão que a originou.

O slug é curto, em minúsculas, com hífen, e descreve a entrega:
`004-cache-de-buscas`, e não `004-melhorias` nem `004-parte-do-pesquisador`.

### Passo 2 — Copie o template

```bash
cp -r specs/_template specs/004-cache-de-buscas
```

### Passo 3 — Crie a branch

Seguindo a [Política de Branches](../docs/pages/politicas_repositorio.md), a branch
sai da `develop` e carrega o número da spec:

```bash
git switch develop && git pull
git switch -c feature/004-cache-de-buscas
```

### Passo 4 — Preencha **apenas** o `spec.md`

Ainda não abra o `plan.md`. Nesta etapa você está decidindo o que o sistema faz,
não como. Três armadilhas comuns:

- **Critério de aceite vago.** "O cache deve funcionar bem" não é verificável.
  Troque por "uma consulta repetida em menos de 24h não gera nova chamada à
  OpenAlex".
- **Decisão técnica disfarçada de requisito.** "Usar Redis" é plano, não spec.
  Na spec fica "o resultado de uma busca é reaproveitado por 24h".
- **Fora de escopo vazio.** Se você não escreveu o que *não* será feito, a
  feature vai crescer sozinha durante a implementação.

Se surgir qualquer dúvida que você não consiga resolver sozinho, registre em
**Perguntas em aberto**. O que não estiver escrito será decidido no impulso por
quem implementar.

### Passo 5 — Abra o PR da spec (e só da spec)

Commit e PR contendo **somente** o `spec.md` preenchido:

```bash
git add specs/004-cache-de-buscas/
git commit -m "docs(spec): adiciona spec 004 de cache de buscas"
```

No PR, título `[Spec 004] Cache de buscas` e status da spec como `em revisão`.

Este é o passo que diferencia SDD de "escrever documentação". É um PR de
markdown que a equipe revisa em dez minutos e que evita dias de retrabalho —
se a discordância sobre o comportamento aparece só no code review, o processo
já falhou. Peça a revisão de pelo menos uma pessoa, como manda a política do
repositório.

### Passo 6 — Com a spec aprovada, escreva `plan.md` e `tasks.md`

Mude o status para `aprovada` e só então desça para o nível técnico:

- No `plan.md`, liste os arquivos que serão tocados, as assinaturas e os
  contratos de entrada/saída, e registre cada decisão com uma linha de
  justificativa. A tabela de decisões é o que responde, três semanas depois,
  "por que isso foi feito assim?".
- No `tasks.md`, quebre em passos que caibam numa sessão de trabalho e terminem
  num estado verificável. Uma ordem que funciona bem: definir contrato →
  escrever os testes dos critérios de aceite (falhando) → implementar até
  passarem.

### Passo 7 — Implemente tarefa por tarefa

Trabalhe um item do `tasks.md` por vez, marcando o checkbox só quando o passo
estiver testado. Se você usa IA para implementar, **coloque o `spec.md` e o
`plan.md` no contexto da sessão** e peça uma tarefa por vez — é essa restrição
que mantém o resultado dentro do que foi combinado.

Descobriu no meio do caminho que a spec estava errada? Isso é normal e
esperado. Pare, corrija a spec, e siga. O que não pode é o código divergir em
silêncio: a partir do momento que isso acontece, a pasta vira ficção e a IA
passa a gerar código errado com aparência de certo.

### Passo 8 — Feche o ciclo antes do merge

Percorra o checklist que está no fim do `tasks.md`:

- todo critério de aceite tem teste correspondente;
- `spec.md` reflete o que foi realmente construído;
- status alterado para `implementada`;
- linha da feature atualizada na tabela deste arquivo.

### Passo 9 — PR de implementação

Título referenciando a spec (`[004] Cache de buscas`) e descrição apontando
para ela. Após o merge com **Squash and Merge**, apague a branch.

---

## Regras de ouro

1. **Uma feature, uma spec, uma branch, um número.** Sem exceção.
2. **Nada de código sem spec aprovada.** Se apareceu um PR sem spec
   correspondente, alguém pulou etapa.
3. **Spec desatualizada é pior que spec inexistente**, porque ela é seguida com
   confiança. Atualizar faz parte da definição de pronto.
4. **Fatie em vertical.** Prefira "a rota `/verificar` devolve um veredicto
   fixo, ponta a ponta" a "todos os schemas do projeto". Cada spec deve
   terminar em algo demonstrável.
5. **Spec curta é spec lida.** Uma página basta; ninguém revisa cinco.

---

## Como especificar uma feature que usa LLM

Os agentes Triador e Juiz não têm saída determinística, então parte da spec não
vira `assert`. Separe as duas naturezas na seção 5 do template:

- **O que é determinístico** — formato da resposta, comportamento quando o
  modelo devolve algo inválido, limites de quantidade, validação de entrada.
  Isso é a maior parte do código e vira teste unitário comum, com dublê no
  lugar do LLM.
- **O que é probabilístico** — a qualidade do resultado. O critério de aceite
  aqui não é um teste, é um **eval set**: um conjunto de casos reais rotulados
  à mão pela equipe (`verificador/backend/evals/<agente>.jsonl`), com uma meta de acerto e
  uma lista de erros inaceitáveis.

Vale montar o eval set cedo, mesmo pequeno. Sem ele, não há como afirmar que
uma mudança de prompt melhorou alguma coisa — e a taxa de aceitação da extensão
só dá esse sinal depois que o produto já está na mão do usuário.

---

## Sugestão de ordem das primeiras specs

| Ordem | Feature | Por que nessa ordem |
| :-- | :--- | :--- |
| 1 | Contrato de verificação + healthcheck | destrava o time da extensão com um veredicto fixo |
| 2 | Busca na OpenAlex | integração real, ainda sem LLM |
| 3 | Agente Triador | primeira spec com eval set |
| 4 | Agente Juiz | define com precisão as categorias de classificação |
| 5 | Cache de buscas | mensurável: taxa de hit e latência |
| 6 | Clusterização com BERTopic | otimização de custo, justificada por número |
| 7 | Feedback e taxa de aceitação | fecha o ciclo de métrica do produto |
