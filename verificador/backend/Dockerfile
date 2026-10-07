FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin app

COPY --chown=app:app src ./src
COPY --chown=app:app alembic.ini .
COPY --chown=app:app migrations ./migrations
# O script de inicializacao da plataforma gerenciada; o compose local
# passa o proprio `command:` e nao usa este caminho.
COPY --chown=app:app scripts/iniciar.sh ./scripts/iniciar.sh

EXPOSE 8000

USER app

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
