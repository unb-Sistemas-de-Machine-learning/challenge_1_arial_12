# Plano — 004 Agente Juiz

## Abordagem

Reutilizar `ClienteLLM.gerar()` com um modelo Pydantic para o JSON do Juiz. O prompt versionado define as categorias e trata os abstracts como dados não confiáveis. Após cada resposta, o código valida as regras de domínio (DOI permitido, estudo não retratado para `sustenta`, idioma/tamanho da justificativa) e constrói o `Veredito` usando apenas metadados da entrada. Uma resposta inválida permite mais uma chamada; não há retry extra para timeout do provedor.

## Arquivos

| Arquivo | Mudança |
| :--- | :--- |
| `src/agents/juiz.py` | schema de resposta, agente, validações e montagem de `Veredito` |
| `src/agents/orientacoes/juiz/ORIENTACOES.md` | prompt versionado e definições das categorias |
| `src/tests/unit/test_juiz.py` | testes sem rede com `DubleLLM` |
| `evals/juiz.jsonl` | 40 cenários rotulados, com origem declarada |
| `scripts/eval_juiz.py` | runner de avaliação e relatório das três métricas |

## Decisões de segurança

- O LLM escolhe apenas o DOI; título, ano e retratação vêm do objeto `TrabalhoEncontrado` recebido.
- Normalizar DOI antes de comparar, mas não aceitar DOI citado que não veio nos abstracts.
- `nada_encontrado` sem abstract utilizável é caminho determinístico e gratuito.
- Fonte retratada não pode sustentar mesmo se o modelo disser o contrário.
- Não enviar instruções contidas dentro de abstracts como comandos; elas são dados delimitados.

## Verificação

Executar unitários, suíte do backend, Ruff e validação estrutural do JSONL sem chave. Com `LLM_API_KEY` disponível, executar o runner real e registrar acerto ≥ 80%, falsos `sustenta` sem relacionado = 0 e suporte por retratado = 0. Sem chave, reportar as métricas como **não medidas**, nunca como 0% ou sucesso.
