# 007 — Inicialização da API pelo Docker Compose

| Campo | Valor |
| :--- | :--- |
| **Status** | implementada |
| **Autor** | Equipe Arial 12 |
| **Branch** | `feature/007-app-fastapi-compose` |
| **Depende de** | `006` — configuração centralizada |
| **Origem** | [Task #7](https://github.com/unb-Sistemas-de-Machine-learning/challenge_1_arial_12/issues/7) |

---

## 1. Objetivo

Permitir que a equipe suba a nova estrutura do backend com Docker Compose e confirme que a API está disponível, sem interromper os testes da extensão que ainda dependem do stub da Fase 01.

## 2. Contexto

Antes desta entrega, o contêiner **API Gateway** da [arquitetura](../../docs/pages/arquitetura.md) iniciava `verificador/backend/main.py`, enquanto `src/main.py` e o gateway estavam vazios. A spec 006 introduziu `get_settings()` e a validação de `DATABASE_URL` na inicialização; esta entrega reutiliza esse objeto na nova fábrica de aplicação.

O Compose passa a iniciar `src.main:app`. O stub `backend/main.py` continua disponível para executar `/verificar` com o veredicto fixo até a integração da B05. A nova aplicação expõe somente o healthcheck; não migra a regra de negócio do stub nesta task.

## 3. Critérios de aceite

1. `src/main.py` expõe `criar_app() -> FastAPI` e `app`, criada por essa função, sem handler ou regra de negócio nesse arquivo.
2. A aplicação criada por `criar_app()` inclui o router exportado por `src.api.gateway` e responde `GET /health` com HTTP `200` e `{"ok": true}`.
3. A fábrica usa a configuração da spec 006 para `APP_DEBUG` e `CORS_ORIGINS`, e valida as variáveis obrigatórias antes de atender requisições.
4. `docker-compose.yml` inicia os serviços `api` e `db` e executa Uvicorn com `src.main:app` na porta 8000; com `.env` válido, `GET http://localhost:8000/health` responde HTTP `200`.
5. Sem arquivo `.env` e sem `DATABASE_URL` no ambiente, o contêiner `api` falha na inicialização e a mensagem de erro identifica `DATABASE_URL` pelo nome; o Compose não substitui essa mensagem por erro de arquivo `.env` ausente.
6. O Dockerfile instala somente `requirements.txt`, não instala `requirements-nlp.txt`, e executa a aplicação como usuário não-root.
7. O stub `backend/main.py` não é removido: preserva `POST /verificar` e seu mock para testar a extensão, mas seu healthcheck passa a ser `GET /health`.
8. O README de `verificador/` ensina a subir a nova API por Compose, verificar `/health` e continuar usando o stub via venv quando `/verificar` for necessário.
9. Testes automatizados verificam a fábrica, healthcheck, CORS, falha por configuração ausente e preservação do stub; uma verificação de Compose cobre comando, serviços e imagem.

## 4. Fora de escopo

- Migrar `/verificar` e o veredicto fixo para o novo router (B05).
- Buscar evidências, chamar OpenAlex ou LLM, ou conectar ao banco no healthcheck.
- Alterar o contrato da extensão ou exigir sua recompilação.
- Instalar dependências pesadas de NLP na imagem da API.
- Criar migrações, tabelas ou políticas novas de autenticação e CORS.
- Exigir que a ausência de `.env` derrube o serviço `db`; apenas `api` depende das configurações da aplicação.

## 5. Comportamento de IA

Não se aplica. Esta feature não invoca LLM e é testável de forma determinística.

## 6. Perguntas em aberto

Nenhuma para o escopo desta spec.

## 7. Histórico

| Data | Mudança |
| :--- | :--- |
| 2026-09-19 | Criação da spec a partir da task #7 |
| 2026-09-19 | Implementação e validação por testes e Docker Compose; comando padrão sem `--reload` para falhar de forma visível sem `.env` |
| 2026-09-19 | Padronização do healthcheck em `/health` na nova API e no stub legado |
