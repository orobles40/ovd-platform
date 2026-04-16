# OVD Platform — Dashboard React
# Build multi-stage: bun build → nginx estático
# Copyright 2026 Omar Robles
#
# Build args:
#   VITE_API_URL  URL del engine (ej: https://api.ovd.omarrobles.dev)
#
# Uso local:
#   docker build --build-arg VITE_API_URL=http://localhost:8001 -t ovd-dashboard:test .

# ── Stage 1: build ────────────────────────────────────────────────────────────
FROM oven/bun:1 AS builder

WORKDIR /app

# Copiar manifiestos primero para aprovechar cache de capas
COPY package.json bun.lock* ./
RUN bun install --frozen-lockfile

COPY . .

# URL del engine — se inyecta en build time como variable de entorno Vite
ARG VITE_API_URL=http://localhost:8001
ENV VITE_API_URL=$VITE_API_URL

RUN bun run build

# ── Stage 2: servidor nginx ───────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runner

# Configuración nginx para SPA React
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost/health.txt || exit 1

CMD ["nginx", "-g", "daemon off;"]
