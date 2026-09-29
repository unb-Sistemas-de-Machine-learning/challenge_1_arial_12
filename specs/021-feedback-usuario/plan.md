# Plano de Implementação: Feedback do Usuário

## 1. Arquivos Modificados/Criados

### Backend
- `verificador/backend/app/api/schemas/feedback.py`: Criação do Pydantic schema `FeedbackRequest`.
- `verificador/backend/app/api/routes/feedback.py`: Criação da rota `POST /feedback` com rate limiting e processamento assíncrono.
- `verificador/backend/app/main.py`: Inclusão do router de feedback.
- `verificador/backend/app/db/repository/feedback.py` (ou onde ficar a persistência): Implementação da lógica de salvar assincronamente no DB (com `asyncio.create_task` ou `BackgroundTasks` do FastAPI) com captura de exceções para não travar a API.
- `verificador/backend/app/models/feedback.py`: Definição do modelo SQLAlchemy ou similar para o banco (se já houver sqlalchemy).
- `verificador/backend/tests/api/test_feedback.py`: Testes da rota (sucesso, rate limit, payload inválido, falha de DB capturada assincronamente).

### Extensão
- `verificador/extensao/painel.ts`: Adicionar os botões de feedback na UI e manipular os cliques para acionar a requisição.
- `verificador/extensao/requisicoes.ts`: Implementar a função que faz o `POST /feedback`.
- `verificador/extensao/tests/painel.test.mjs`: Testes do painel atualizados.

## 2. Assinaturas e Contratos

**Contrato `POST /feedback`:**
Request:
```json
{
  "veredicto_id": "uuid-do-veredicto",
  "util": true,
  "data_hora": "2023-10-15T12:00:00Z"
}
```
Response:
```json
{
  "status": "recebido"
}
```

## 3. Decisões de Design

| Decisão | Justificativa |
| :--- | :--- |
| **Processamento Assíncrono com BackgroundTasks** | O FastAPI fornece `BackgroundTasks` que executa a persistência após retornar a resposta ao cliente, atendendo o requisito de não atrasar a resposta e capturar falhas de banco de forma transparente. |
| **Não enviar URL na requisição** | Mantém a permissão do `manifest.json` restrita conforme política estabelecida na documentação e spec 021. |
| **Rate Limit** | Evita spam de submissões. Usaremos a dependência ou middleware já configurado em #12. |
