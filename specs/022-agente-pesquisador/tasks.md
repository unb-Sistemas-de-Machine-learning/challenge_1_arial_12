# Tarefas - 022 Agente Pesquisador e esteira real do `/verificar`

Cada tarefa termina com os testes dela passando e o Ruff limpo. A ordem vai de baixo para cima: primeiro as peças isoladas, por último a rota que junta tudo.

## Peças de baixo

- [x] 1. Tornar públicas `intercalar` (com parâmetro `chave`, padrão `Trabalho.chave`) e `normalizar_buscas` em `openalex.py`. A suíte do cliente continua verde sem ajuste, e um teste novo cobre `chave` personalizada.
- [x] 2. Escrever `CacheDeBuscas` e `SemCache` em `src/services/cache.py`.
- [x] 3. Adicionar `pesquisador_concorrencia` em `settings.py` (padrão 5, de 1 a 10) e em `.env.example`, com teste em `test_settings.py`.

## Pesquisador

- [x] 4. Criar `AgentePesquisador.pesquisar` com busca por string e conversão para `TrabalhoEncontrado`, sem cache e sem limite de concorrência ainda. Teste: caminho feliz com fixture.
- [x] 5. Desduplicar por DOI normalizado (sem DOI, pelo id) dentro da intercalação, antes do corte em 5. Testes: DOI em formatos diferentes; trabalhos sem DOI.
- [x] 6. Limitar a concorrência com semáforo em volta da chamada externa. Teste: com limite 2, nunca há mais de 2 requisições simultâneas.
- [x] 7. Consolidar falha parcial em `falhas` com log. Teste: uma busca falha, a outra entrega trabalhos.
- [x] 8. Levantar `OpenAlexIndisponivel` quando todas falham. Teste.
- [x] 9. Consultar o cache antes da OpenAlex e guardar depois; erro de cache vira "sem cache". Testes: acerto evita a requisição; cache quebrado não derruba.

## Triador

- [x] 10. Criar `ExtracaoDoTriador` e `AgenteTriador.extrair`, com `extrair_buscas` delegando a ele. Testes: conceitos ordenados, sem vazios e sem repetição; LLM falhando devolve `conceitos=[]`; testes atuais de `extrair_buscas` sem mudança.

## Esteira no gateway

- [x] 11. Criar `src/api/gateway/dependencias.py` com `obter_triador`, `obter_pesquisador` e `obter_juiz` (LLM por `obter_cliente_llm`, OpenAlex por `cliente_compartilhado`, configuração ausente da OpenAlex vira `openalex_indisponivel`).
- [x] 12. Reescrever `/verificar` para encadear Triador → Pesquisador → Juiz e trocar `termos` pelos conceitos, removendo os `print`. Testes de integração: caminho feliz, Triador falhando, todas as buscas falhando, timeout e resposta inválida do Juiz, sem `LLM_API_KEY`.
- [x] 13. Gravar o veredito com `registrar_veredito` e devolver o `id`; falha na gravação devolve `id = null` com log. Testes: sem banco → `id = null`; com banco (`exige_banco`) → `id` aceito por `POST /feedback`.
- [x] 14. Remover o teste do stub e a fixture `veredito_fase01.json`; renomear `_VEREDITO_FIXO` para `_EXEMPLO_DE_VEREDITO`, usado só no exemplo do OpenAPI, e conferir que o teste do OpenAPI continua verde.
- [x] 15. Conferir que `test_rota_busca.py` passa sem mudança (`/buscar` intacta).

## Documentação

- [x] 16. Atualizar `verificador/README.md`: o roteiro local exige `LLM_API_KEY` e `OPENALEX_MAILTO`, sai a promessa de circuito "sem IA e sem OpenAlex", e entra uma seção do Pesquisador com `PESQUISADOR_CONCORRENCIA`.
- [x] 17. Teste manual com chaves reais: um trecho pelo Postman e um pela extensão, registrando o resultado no PR.

## Antes de abrir o PR de implementação

- [x] Todos os critérios de aceite da spec têm teste correspondente
- [x] `spec.md` atualizado com o que mudou durante a implementação
- [ ] Status da spec alterado para `implementada`
- [ ] Linha da spec atualizada no índice (`specs/README.md`)
