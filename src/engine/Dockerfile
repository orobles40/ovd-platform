# OVD Platform — OVD Engine
# Copyright 2026 Omar Robles

FROM python:3.12-slim

# uv — gestor de dependencias Python (reemplaza pip)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Compilar bytecode al instalar para imports más rápidos en runtime
ENV UV_COMPILE_BYTECODE=1
# Usar el Python del sistema (no crear venv dentro del container)
ENV UV_SYSTEM_PYTHON=1

WORKDIR /app

# Instalar dependencias del sistema para psycopg
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar solo los archivos de dependencias primero (cache de capas Docker)
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

COPY . .

# Entrypoint para cargar Docker Secrets como env vars
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8001

HEALTHCHECK --interval=15s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')" || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "main.py"]
