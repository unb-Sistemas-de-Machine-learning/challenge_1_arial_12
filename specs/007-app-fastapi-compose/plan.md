# Plano — 007 Inicialização da API pelo Docker Compose

> Plano técnico da task #7. A spec registra o comportamento; este arquivo detalha como implementá-lo.

## 1. Abordagem

Criar uma fábrica mínima em `src/main.py` que obtém `Settings`, configura FastAPI e CORS e inclui o router do gateway. O gateway expõe apenas `GET /health`. Preservar `POST /verificar` no stub `backend/main.py`, alinhar seu healthcheck a `/health` e copiar o arquivo na imagem para que possa ser iniciado separadamente até B05. Mudar o serviço `api` do Compose e o `CMD` da imagem para `src.main:app`.

Para que a falta de `.env` resulte no erro da variável obrigatória, declarar o `env_file` do Compose como opcional. A mensagem de validação da spec 006 precisa exibir o nome `DATABASE_URL`, sem mostrar o valor de nenhum segredo.
O comando padrão não usa `--reload`: assim, uma falha na importação da aplicação encerra o contêiner em vez de deixar o processo supervisor ativo sem API funcional.

## 2. Arquivos tocados

| Arquivo | O que muda |
| :--- | :--- |
| `verificador/backend/src/main.py` | `criar_app()`, `app`, título, versão, CORS e registro do router |
| `verificador/backend/src/api/gateway/routes.py` | Router e rota técnica `/health` |
| `verificador/backend/main.py` | Healthcheck `/health`, preservando `POST /verificar` |
| `verificador/backend/src/api/gateway/__init__.py` | Exportação do router |
| `verificador/backend/src/core/config/settings.py` | Nomear `DATABASE_URL` no erro de validação sem expor seu valor |
| `verificador/backend/docker-compose.yml` | `src.main:app`, `.env` opcional e volumes para código atual/stub legado |
| `verificador/backend/Dockerfile` | Usuário não-root e CMD da nova aplicação, preservando camada de dependências |
| `verificador/backend/src/tests/unit/test_app_factory.py` | Factory, singleton `app`, router e CORS |
| `verificador/backend/src/tests/integration/test_app_compose.py` | Healthcheck, falha de configuração e compatibilidade do stub |
| `verificador/README.md` | Subida por Compose e execução alternativa do stub por venv |

## 3. Contratos

```python
def criar_app() -> FastAPI: ...

app: FastAPI = criar_app()

# GET /health -> 200 {"ok": true}
```

A fábrica chama `get_settings()` antes de construir o app. O `router` exportado por `src.api.gateway` é incluído uma vez. Não há acesso ao banco na construção do app ou no healthcheck. O stub continua separado em `backend/main.py` e mantém `POST /verificar`.

## 4. Decisões técnicas

| Decisão | Alternativa descartada | Por quê |
| :--- | :--- | :--- |
| Rota `/health` no gateway | Handler no `src/main.py` | Deixa a fábrica sem lógica de endpoint |
| `env_file` opcional no Compose | Arquivo obrigatório para o Compose | Permite a validação de `Settings` nomear `DATABASE_URL` |
| Manter `main.py` na imagem e no repositório | Remover o stub agora | Preserva o fluxo da extensão até B05 |
| Instalar `requirements.txt` antes de copiar o código | Copiar tudo antes do `pip install` | Reaproveita a camada de dependências |
| Usuário não-root no contêiner | Executar como root | Reduz privilégios da API |
| Comando padrão sem `--reload` | Supervisor de desenvolvimento sempre ativo | Permite que erro de configuração derrube `api` com código de saída não zero |

## 5. Como testar

- **Unitários:** injetar configuração de teste na fábrica via substituição de `get_settings`; verificar título, versão, debug, router e CORS sem `.env` real.
- **Integração:** usar `TestClient` para `/health`; importar o módulo sem `DATABASE_URL` e verificar erro antes da primeira requisição; confirmar que o stub antigo ainda responde `/verificar`.
- **Compose:** verificar configuração efetiva com `docker compose config`, subir `api` e `db` com `.env` temporário e consultar `http://localhost:8000/health`; repetir sem `.env` e conferir o nome `DATABASE_URL` nos logs da API. Não commitar `.env`.
- **Eval:** não se aplica.

## 6. Riscos

- A ausência de `.env` é tratada de forma diferente por versões antigas do Compose; a sintaxe de `env_file.required: false` requer versão que a suporte.
- O serviço `db` pode continuar de pé quando `api` falhar por configuração; isso é esperado.
- A nova aplicação ainda não possui `/verificar`; o README deve orientar quem testa a extensão a iniciar o stub até B05.
- O contêiner `db` inicia mesmo que `api` falhe por falta de `DATABASE_URL`; isso é esperado e foi verificado no Compose.
