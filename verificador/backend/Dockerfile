FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py ./
COPY src ./src

EXPOSE 8000

# Hoje quem responde e o stub da Fase 01 (main.py). Quando a spec 001 mover a
# aplicacao para src/main.py, trocar para "src.main:app".
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
