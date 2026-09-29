# Fixtures da OpenAlex

Respostas **gravadas de chamadas reais** a `GET https://api.openalex.org/works`,
em 2026-09-28. Nenhum teste unitário fala com a rede: o `httpx.MockTransport`
devolve estes arquivos.

Todas as gravações usam o mesmo `select` que o cliente usa em produção:

```text
select=id,display_name,title,publication_year,doi,is_retracted,abstract_inverted_index,relevance_score,cited_by_count
```

Os testes unitários não conseguem chamar a rede nem por engano: `conftest.py` em
`src/tests/unit/` bloqueia soquete e estoura apontando a linha que tentou.

| Arquivo | O que cobre | Consulta |
| :--- | :--- | :--- |
| `busca_polilaminina.json` | Caso comum: 5 trabalhos, um deles sem abstract | `search=polylaminin spinal cord injury&per-page=5` |
| `busca_sem_doi.json` | 3 trabalhos sem DOI, um deles também sem abstract | `search=spinal cord injury&filter=has_doi:false&per-page=3` |
| `busca_retratado.json` | 2 trabalhos com `is_retracted: true` | `search=spinal cord injury&filter=is_retracted:true&per-page=2` |
| `busca_sem_resultados.json` | `results` vazio, que não é erro | `search=zzzqqqxyw nonexistent term 12345&per-page=5` |

As gravações saíram sem `mailto` porque a equipe ainda não tem uma caixa de
contato definida (ver *Perguntas em aberto* na spec `002`). O parâmetro decide
em qual pool a requisição entra e não muda o corpo da resposta.

Para regravar, repita a consulta da tabela e salve o JSON formatado com dois
espaços de indentação.
