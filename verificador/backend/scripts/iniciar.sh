#!/bin/sh
# Inicializacao em uma plataforma gerenciada (Render).
#
# Existe como arquivo, e nao como `dockerCommand` de uma linha, porque o
# `&&` nao atravessa o parser do Render: ele entrega a string inteira ao `sh`
# como um unico nome de comando, e a subida falha com
# "... --port 10000: not found".
#
# Nao vale para o docker compose local, que passa o proprio `command:`.
set -e

# As migracoes rodam aqui porque `preDeployCommand` exige plano pago no Render.
# `upgrade head` em banco atualizado nao faz nada, entao repetir a cada subida
# (inclusive ao acordar do sleep do plano gratuito) e inofensivo.
alembic upgrade head

# A plataforma escolhe a porta e a informa em $PORT; o 8000 e so para o mesmo
# script funcionar fora dela.
exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-8000}"
