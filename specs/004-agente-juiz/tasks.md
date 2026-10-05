# Tarefas — 004 Agente Juiz

- [x] Definir por escrito as três categorias, fronteira da evidência e riscos na spec.
- [ ] Revisar/abrir o PR da spec antes do PR de implementação, conforme a issue.
- [x] Criar eval set JSONL com 40 casos sintéticos rotulados e distribuição equilibrada.
- [x] Implementar prompt versionado e `AgenteJuiz`.
- [x] Validar DOI de saída e referências na justificativa contra os abstracts.
- [x] Bloquear `sustenta` com estudo retratado e tratar lista vazia sem LLM.
- [x] Testar resposta inválida, uma repetição e erro padronizável persistente.
- [x] Implementar runner e validar a estrutura do dataset sem LLM.
- [x] Rodar suíte e Ruff localmente (Python 3.14 com dependências compatíveis).
- [x] Rodar o eval v3 com LLM real e registrar as três métricas nesta task.
- [x] Repetir o eval completo com o prompt atual no Groq.
- [ ] Registrar as métricas da v5 no PR.
- [ ] Revisar com a equipe rótulos/abstracts reais antes de tratar o acerto como qualidade científica.

## Rodada exploratória

Na primeira execução integral com Groq, 27 dos 40 casos acertaram, E02 foi
classificado como `nada_encontrado` em vez de `exagera` e 12 casos receberam
`429` após as tentativas. A taxa de 67,5% não valida a meta: os 12 casos sem
resposta contam como falhas. O prompt v3 separa relação com o abstract de
suporte integral à alegação; o runner mostra apenas metadados seguros do
limite e interrompe a execução no primeiro `429` persistente. Essa execução
foi superada pela rodada integral do v3 abaixo.

Na execução integral do v3 com `--intervalo 10`, houve 39 acertos em 40
(97,5%), zero falsos `sustenta` sem abstract relacionado, zero `sustenta` com
estudo retratado e zero falhas de chamada/validação. E05 foi o único erro:
`nada_encontrado` em vez de `exagera`, apesar de haver estudo pertinente em
camundongos para uma alegação sobre humanos. O prompt v4 explicita essa
fronteira. **Os números do v3 não medem o v4**; repetir o eval integral antes
de atribuir uma taxa de acerto à nova versão.

No v4, E02 voltou a `nada_encontrado` apesar de a justificativa comparar o
estudo pertinente com a alegação. A rodada integral foi interrompida em E05
por limite de tokens por minuto (`429`); a taxa parcial não mede o aceite.
O prompt v5 explicita uma checagem de pertinência anterior à checagem de
suporte integral. Na rodada integral da v5 informada pelo executor, os 40 casos
terminaram com apenas E02 incorreto: 39/40 (97,5%). E02 continuou sendo
`nada_encontrado` em vez de `exagera` e deve constar como limitação conhecida
no PR. Conferir e transcrever as linhas finais do runner no PR, inclusive as
contagens dos dois erros inaceitáveis e das falhas de chamada/validação.
