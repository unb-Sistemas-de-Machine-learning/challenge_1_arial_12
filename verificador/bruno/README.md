# Coleção Bruno

Requisições prontas para exercitar a API à mão. Abra o [Bruno](https://usebruno.com)
em **Open Collection** e aponte para esta pasta; selecione o ambiente `Local`.

Suba a API antes:

```bash
cd verificador/backend
python3 -m uvicorn src.main:app --reload --port 8000
```

| # | Requisição | Precisa de |
| :-- | :--- | :--- |
| 01 | `GET /health` | nada |
| 02 | `POST /verificar` — veredito mock | nada |
| 03 | `POST /verificar` com corpo inválido → `422` | nada |
| 04 | `POST /buscar` — duas variações, top 5 intercalado | `OPENALEX_MAILTO` |
| 05 | `POST /buscar` — consulta booleana | idem |
| 06 | `POST /buscar` com lista vazia → `422` | nada |

As requisições `04` e `05` batem na **OpenAlex de verdade**, e falham com `503`
se ela estiver cortando busca não identificada — veja `OPENALEX_API_KEY` no
README do verificador.

Alternativa sem instalar nada: importe `http://localhost:8000/openapi.json`
pelo **Import Collection → OpenAPI V3**, ou use o Swagger em `/docs`.
