# OVD Platform — MCP Oracle Server
# Copyright 2026 Omar Robles
#
# Imagen basada en python-slim + Oracle Instant Client
# oracle/instantclient:21-tools incluye librerias necesarias para oracledb

FROM python:3.12-slim

# Oracle Instant Client dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libaio1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Puerto HTTP solo para health check del docker compose
EXPOSE 8002

# Health check: ejecuta el flag --health del servidor
HEALTHCHECK --interval=20s --timeout=10s --start-period=30s --retries=3 \
    CMD python server.py --health || exit 1

# El servidor MCP usa stdio — el CMD es para el health endpoint
# El proceso real se inicia via opencode.jsonc con command/args
CMD ["python", "server.py"]
