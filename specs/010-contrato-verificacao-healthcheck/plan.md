# Plano — 010 Contrato de verificação entre extensão e backend

> Implementação automatizada integrada à aplicação da #7. O roteiro manual da extensão ainda está pendente.

## 1. Abordagem

Preservar o JSON exato do stub como fixture antes de substituí-lo. Definir modelos Pydantic equivalentes às interfaces da extensão e expor `POST /verificar` com `response_model`, mantendo o veredicto fixo. Reutilizar `GET /health` e a fábrica de aplicação da #7, sem consultar o banco nessa rota. Após os testes de contrato e integração, retirar o stub antigo.

Os tamanhos mínimo e máximo de `trecho` e o tamanho máximo de `justificativa` permanecem **indefinidos**; não adicionar limites de comprimento nesta entrega. <!-- TODO: revisar a spec, os testes e este plano quando os limites forem definidos. -->

## 2. Arquivos tocados

| Arquivo | O que muda |
| :--- | :--- |
| `verificador/backend/src/api/schemas/verificacao.py` | Modelos `Pedido`, `Estudo`, `Veredito` e enum `Estado` |
| `verificador/backend/src/api/gateway/routes.py` | Rotas `/verificar` e `/health`, exemplos OpenAPI |
| `verificador/backend/src/main.py` | Fábrica da #7 com as rotas, configuração centralizada e sem conexão obrigatória ao banco |
| `verificador/backend/src/tests/fixtures/veredito_fase01.json` | Cópia do payload legado antes de remover o stub |
| `verificador/backend/src/tests/unit/test_contrato_verificacao.py` | Validação dos modelos e paridade com `tipos.ts` |
| `verificador/backend/src/tests/integration/test_rotas_verificacao.py` | Requisições HTTP, OpenAPI, fixture e saúde sem banco |
| `verificador/backend/main.py` | Remoção depois da migração e dos testes de regressão |
| `verificador/backend/Dockerfile` e `verificador/backend/docker-compose.yml` | Inicialização por `src.main:app` e remoção do volume do stub |
| `verificador/README.md` | Comandos e roteiro manual atualizados para `/health` e o novo ponto de entrada |

## 3. Contratos

Entrada de `POST /verificar`:

```json
{"trecho": "texto selecionado", "url": "file:///pagina-teste.html"}
```

`trecho` é obrigatório e do tipo string; `url` é uma string opcional que também aceita `file://`. Não há regra de comprimento definida nesta spec. O backend aceita a requisição usada pela extensão existente, sem alteração do cliente.

Saída de `POST /verificar` (HTTP 200):

```json
{
  "estado": "exagera",
  "estudo": {"titulo": "(mock) Estudo de exemplo", "ano": 2019, "doi": "10.0000/mock", "retratado": false},
  "termos": ["polylaminin", "spinal cord injury", "regeneration"],
  "justificativa": "(mock) Resposta de teste — a IA entra na Fase 04."
}
```

`estado`: `sustenta | exagera | nada_encontrado`; `estudo`: objeto ou `null`; `termos`: lista de strings; `justificativa`: string. Quando há estudo, `titulo` e `retratado` são obrigatórios; `ano` e `doi` também estão presentes, mas aceitam `null`. A fixture deve ser copiada do stub, não reconstruída a partir deste exemplo.

`GET /health` responde HTTP 200 com `{"ok": true}`. A rota não consulta o banco, mesmo com `DATABASE_URL` inválida.

## 4. Decisões técnicas

| Decisão | Alternativa descartada | Por quê |
| :--- | :--- | :--- |
| Modelos Pydantic e `response_model` no FastAPI | Retornar dicionário sem validação | Publica o contrato no OpenAPI e detecta respostas incompatíveis |
| Preservar payload do stub como fixture literal | Escrever manualmente o JSON esperado | Evita mascarar mudanças acidentais na migração |
| Teste de paridade que lê as declarações relevantes em `tipos.ts` | Conferência apenas visual | Faz a CI falhar quando campos ou valores de `Estado` divergem |
| Não usar validação de comprimento agora | Escolher limites arbitrários | Os limites continuam indefinidos na spec |
| Manter o CORS atual na aplicação migrada | Alterar a política de origens | Evita quebrar a extensão sem ampliar o escopo |

## 5. Como testar

- **Unitários:** construir modelos válidos e inválidos, incluindo `estado` desconhecido, `estudo=null`, `ano=null` e `doi=null`; comparar campos e enum com `tipos.ts`. Nenhum teste chama a rede.
- **Integração:** usar cliente de teste local para `POST /verificar`, `GET /health`, `/docs` e `/openapi.json`; comparar o JSON com a fixture; inicializar com `DATABASE_URL` inválida; verificar erro 422 para entrada estruturalmente inválida. Nenhum teste depende de serviços externos.
- **Manual:** seguir `verificador/README.md` com uma extensão previamente instalada, sem recompilar; conferir veredicto exibido, `POST /verificar` e `GET /health`.
- **Eval:** não se aplica; não há LLM nesta feature.

## 6. Riscos

- **Dependência #7 integrada:** manter a inicialização por `get_settings()` e executar os testes sem `.env` real por injeção de configuração.
- **Teste de paridade frágil:** isolar a leitura de `tipos.ts` e usar exemplos de mudança de campo/enum para provar que o teste falha quando deve.
- **Mudança do JSON fixo:** capturar a fixture antes de retirar `backend/main.py` e comparar a resposta completa, inclusive campos aninhados.
- **Compatibilidade da extensão:** não alterar `tipos.ts` nem exigir rebuild no roteiro manual.
