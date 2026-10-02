# Plano - 003 Agente Triador

## 1. Abordagem

O LLM deixa de escrever strings de busca e passa a devolver **quatro termos**
(intervenção, desfecho, condição, população), já no jargão inglês da literatura.
Quem combina esses termos em strings é o código, por eixos fixos. A instrução
dada ao modelo sai do Python e vira um artefato versionado em Markdown, com um
glossário que o código **aplica** — e não apenas pede que o modelo siga.

A razão é a instabilidade medida em produção: a mesma frase recuperava o estudo
rotulado numa tentativa e não recuperava na seguinte, porque a cada chamada o
modelo escolhia outro sinônimo (`brain shrinkage` / `cerebral atrophy`), outra
quantidade de palavras e outra ordem. Nada disso precisa de LLM. Sobrou para o
modelo a única parte que só ele faz: reconhecer o conceito e traduzi-lo.

## 2. Arquivos tocados

| Arquivo | O que muda |
| :--- | :--- |
| `verificador/backend/src/agents/orientacoes/__init__.py` | **novo** — carrega as orientações em Markdown e separa o cabeçalho de metadados do corpo |
| `verificador/backend/src/agents/orientacoes/triador/ORIENTACOES.md` | **novo** — as regras que o variador semântico segue; vai no prompt |
| `verificador/backend/src/agents/orientacoes/triador/referencias/glossario.md` | **novo** — tabela conceito → termo canônico → variantes; lida pelo código |
| `verificador/backend/src/agents/orientacoes/triador/referencias/exemplos.md` | **novo** — sete trechos resolvidos; vão no prompt |
| `verificador/backend/src/agents/orientacoes/triador/referencias/formatos-de-busca.md` | **novo** — documenta os eixos e a montagem; **não** vai no prompt |
| `verificador/backend/src/agents/triador.py` | schema `TermosDeBusca`, forma canônica, glossário, eixos, montagem |
| `verificador/backend/src/services/llm.py` | `temperatura` (padrão 0) e `seed` no provedor |
| `verificador/backend/src/core/config/settings.py` | `LLM_TEMPERATURA`, `LLM_SEED` |
| `verificador/backend/scripts/eval_triador.py` | `--repeticoes` e `--limite`; relatório de acerto **e** de estabilidade |
| `verificador/backend/src/tests/unit/test_triador.py` | reescrito: forma canônica, glossário, eixos, agente, prompt |
| `verificador/backend/src/tests/unit/test_llm.py` | temperatura e semente na requisição |

## 3. Contratos

```python
class TermosDeBusca(BaseModel):
    """O que o LLM devolve. Os quatro campos são obrigatórios; vazio é resposta."""
    intervencao: str   # o que age: tratamento, substância, hábito, fenômeno
    desfecho: str      # o que é afetado: doença, sintoma, medida, evento
    condicao: str      # a doença ou o contexto clínico, se o trecho nomear
    populacao: str     # em quem ou em quê, se o trecho disser


class AgenteTriador:
    def __init__(
        self,
        cliente_llm: ClienteLLM,
        max_variacoes: int = 6,            # = número de eixos
        max_tamanho_variacao: int = 200,
        *,
        glossario: Glossario | None = None,  # costura de teste
    ): ...

    async def extrair_buscas(self, trecho: str) -> list[str]:
        """[trecho original, ...variações]. Nunca levanta; degrada."""

    def montar_lista(self, trecho: str, termos: TermosDeBusca) -> list[str]:
        """A metade determinística, testável sem LLM nenhum."""
```

Os eixos, em `EIXOS`, na ordem em que as buscas saem:

| `id` | Campos |
| :--- | :--- |
| `completo` | condição + intervenção + desfecho |
| `nucleo` | intervenção + desfecho |
| `sinonimo` | variante (do glossário) da intervenção + desfecho |
| `condicao_intervencao` | condição + intervenção |
| `condicao_desfecho` | condição + desfecho |
| `populacao` | intervenção + desfecho + população |

## 4. Decisões técnicas

| Decisão | Alternativa descartada | Por quê |
| :--- | :--- | :--- |
| LLM extrai termos; código monta strings | pedir ao modelo "seja consistente" e baixar a temperatura | temperatura 0 reduz a variação, não a elimina: qualquer mudança de contexto reabre a escolha de sinônimo. Tirar a decisão do modelo elimina |
| Orientações em Markdown, fora do código | f-string no módulo (era assim) | a instrução é revisada por quem não mexe em Python, e em f-string o diff vem embaralhado com indentação |
| Glossário aplicado pelo código | só pedir no prompt que o modelo use o termo canônico | pedido é seguido na maioria das vezes; "maioria das vezes" é exatamente o defeito que se quer corrigir |
| Variante do eixo `sinonimo` vem do glossário | pedir ao modelo um sinônimo num quinto campo | sinônimo pedido ao modelo é a parte mais instável de todas; vindo da tabela, a diversidade é editada à mão e versionada |
| Eixos cobrem os três pares entre condição, intervenção e desfecho | um eixo por campo isolado, como piso | dois campos preenchidos já garantem busca; um campo sozinho só produz busca de uma palavra, que devolve a literatura inteira da área |
| Dedup por conjunto de palavras | dedup por string | a busca da OpenAlex é a conjunção dos termos: duas ordens das mesmas palavras gastam duas requisições para o mesmo resultado |
| Teto de 5 palavras por campo | só o teto de 200 caracteres por busca | o teto de caracteres não distingue "termo" de "frase inteira"; o de palavras distingue, e `non small cell lung cancer` cabe |
| `temperatura` e `seed` no construtor do provedor | parâmetros de `completar()` | o `ProvedorLLM` é um protocolo que o `DubleLLM` implementa; mexer na assinatura por configuração que não muda entre chamadas quebraria o dublê sem ganho |
| Trecho original sempre na primeira posição | só as variações montadas | é o chão determinístico e o que sobra quando o LLM não responde (critério 4) |

## 5. Como testar

- **Unit** (`src/tests/unit/test_triador.py`, 43 casos): o `DubleLLM` entra no
  lugar do provedor, então timeout, repetição e validação de schema rodam de
  verdade. Os casos de comportamento montam o próprio `Glossario`, para que
  editar o arquivo versionado não derrube teste nenhum; dois casos no fim
  cobram do arquivo de verdade que ele tenha conteúdo, esteja em forma canônica
  e documente os mesmos eixos que o código tem. Nenhum teste toca a rede.
- **Integração:** nada novo. O agente não tem rota própria ainda.
- **Eval:** `python scripts/eval_triador.py --repeticoes 3`, com as duas metas
  da spec (acerto ≥ 80%, estabilidade ≥ 90%). Precisa de `.env` em
  `verificador/backend/` com `LLM_API_KEY` e `OPENALEX_MAILTO`.

## 6. Riscos

- **O glossário vira trabalho sem dono.** Ele só funciona se crescer a partir
  dos casos que oscilaram de verdade. O procedimento está no próprio arquivo, e
  o `--repeticoes` existe para produzir o sinal. Se ninguém rodar, ele envelhece
  em silêncio — e aí o eixo `sinonimo` deixa de contribuir.
- **Os eixos podem perder recall em relação às strings livres do modelo.** A
  medida é o eval: se a taxa de acerto cair, o lugar de mexer é a tabela de
  eixos, com o número na mão.
- **O prompt cresceu** (~13 mil caracteres, ~3,5 mil tokens por chamada). No
  nível gratuito da Groq isso aproxima o limite de tokens por minuto numa rodada
  de eval longa. Se incomodar, o corte natural é `exemplos.md`.
- **Trecho vago deixou de gerar busca** ("Novo tratamento para o câncer de mama
  é promissor" rende um campo só). É o comportamento desejado — não há o que
  verificar numa frase assim —, mas aparece como erro no eval set atual, que tem
  esse caso rotulado com um estudo esperado.
