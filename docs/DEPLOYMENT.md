# OVD Platform — Guía de Despliegue en Producción

> **Copyright 2026 Omar Robles**

Esta guía cubre el despliegue completo de OVD Platform en un VPS propio o instancia cloud,
usando Docker Compose con TLS (Let's Encrypt) y Docker Secrets para gestión segura de credenciales.

---

## Índice

1. [Prerequisitos](#1-prerequisitos)
2. [Preparar el servidor](#2-preparar-el-servidor)
3. [Clonar y configurar el proyecto](#3-clonar-y-configurar-el-proyecto)
4. [Crear Docker Secrets](#4-crear-docker-secrets)
5. [Obtener certificado TLS (Let's Encrypt)](#5-obtener-certificado-tls-lets-encrypt)
6. [Configurar Nginx](#6-configurar-nginx)
7. [Construir imágenes](#7-construir-imágenes)
8. [Aplicar migraciones](#8-aplicar-migraciones)
9. [Lanzar en producción](#9-lanzar-en-producción)
10. [Verificar el despliegue](#10-verificar-el-despliegue)
11. [Renovación automática de TLS](#11-renovación-automática-de-tls)
12. [Rollback](#12-rollback)
13. [Variables de entorno de referencia](#13-variables-de-entorno-de-referencia)

---

## 1. Prerequisitos

| Requisito | Mínimo recomendado |
|---|---|
| VPS / instancia cloud | 2 vCPU, 4 GB RAM, 40 GB SSD |
| Sistema operativo | Ubuntu 22.04 LTS |
| Docker | 25.x o superior |
| Docker Compose plugin | v2.24 o superior |
| Dominio | Con registro A apuntando a la IP del servidor |
| Puerto 80 y 443 | Abiertos en el firewall |

### Instalar Docker en Ubuntu

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
```

---

## 2. Preparar el servidor

```bash
# Actualizar sistema
sudo apt-get update && sudo apt-get upgrade -y

# Instalar certbot
sudo apt-get install -y certbot

# Ajustar límites del sistema para NATS y Postgres
echo "fs.file-max = 65536" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

---

## 3. Clonar y configurar el proyecto

```bash
git clone https://github.com/omar/ovd-platform.git /opt/ovd
cd /opt/ovd

# Copiar y editar variables no secretas
cp .env.prod.example .env.prod
nano .env.prod   # ajustar OVD_MODEL, LOG_LEVEL, OVD_QA_ALERT_THRESHOLD, etc.
```

---

## 4. Crear Docker Secrets

Los valores sensibles se gestionan como Docker Secrets — nunca van en archivos `.env` ni variables de entorno del compose.

```bash
# API Key de Anthropic
echo "sk-ant-api03-TU_API_KEY_REAL" | docker secret create anthropic_api_key -

# Password de PostgreSQL (generar aleatoria)
openssl rand -base64 32 | docker secret create db_password -

# Secret del Engine para firma de payloads internos
openssl rand -hex 32 | docker secret create ovd_engine_secret -

# JWT Secret para tokens de sesión
openssl rand -hex 32 | docker secret create jwt_secret -

# Webhook signing key para HMAC-SHA256
openssl rand -hex 32 | docker secret create ovd_webhook_signing_key -

# Verificar que los secrets existen
docker secret ls
```

> **Importante**: Los secrets se almacenan en el daemon de Docker y solo son accesibles
> desde dentro del contenedor en `/run/secrets/<nombre>`. Nunca aparecen en `docker inspect`.

---

## 5. Obtener certificado TLS (Let's Encrypt)

Sustituir `YOUR_DOMAIN` por el dominio real (ej. `api.ovd.omarrobles.devoud`):

```bash
# Levantar nginx temporalmente en modo HTTP para el challenge ACME
# (antes de tener el certificado)
sudo certbot certonly \
  --standalone \
  --preferred-challenges http \
  -d YOUR_DOMAIN \
  --email tu@email.com \
  --agree-tos \
  --no-eff-email

# Verificar que los certificados existen
ls /etc/letsencrypt/live/YOUR_DOMAIN/
# fullchain.pem  privkey.pem
```

---

## 6. Configurar Nginx

Sustituir el placeholder del dominio en la configuración:

```bash
sed -i 's/YOUR_DOMAIN/api.ovd.omarrobles.devoud/g' infra/nginx/conf.d/ovd.conf
```

Verificar la configuración (opcional, requiere nginx instalado localmente o en contenedor):

```bash
docker run --rm \
  -v $(pwd)/infra/nginx/nginx.conf:/etc/nginx/nginx.conf:ro \
  -v $(pwd)/infra/nginx/conf.d:/etc/nginx/conf.d:ro \
  nginx:1.27-alpine nginx -t
```

---

## 7. Construir imágenes

```bash
cd /opt/ovd

# Construir Engine
docker build -t ovd-engine:latest src/engine/

# El Bridge se construye vía compose (packages/opencode/Dockerfile)
docker compose -f docker-compose.prod.yml build ovd-bridge
```

---

## 8. Aplicar migraciones

```bash
# Levantar solo postgres primero
docker compose -f docker-compose.prod.yml up -d postgres

# Esperar que esté healthy
docker compose -f docker-compose.prod.yml ps

# Ejecutar migraciones (desde el contenedor del bridge o localmente)
docker compose -f docker-compose.prod.yml run --rm ovd-bridge \
  bun run db:migrate

# Alternativa: aplicar SQLs manualmente
DB_PASS=$(docker secret inspect db_password --pretty 2>/dev/null || echo "ver_secret")
# psql postgresql://ovd_prod:${DB_PASS}@localhost:5432/ovd_prod < packages/opencode/migration-ovd/0001_ovd_orgs.sql
```

---

## 9. Lanzar en producción

```bash
cd /opt/ovd

# Cargar variables no secretas
set -a && source .env.prod && set +a

# Lanzar todos los servicios
docker compose -f docker-compose.prod.yml up -d

# Ver estado
docker compose -f docker-compose.prod.yml ps

# Ver logs en tiempo real
docker compose -f docker-compose.prod.yml logs -f --tail=50
```

---

## 10. Verificar el despliegue

```bash
# Health check del Bridge
curl -s https://YOUR_DOMAIN/health

# Health check del Engine (interno, desde otro contenedor)
docker exec ovd-bridge wget -qO- http://ovd-engine:8001/health

# Verificar certificado TLS
curl -vI https://YOUR_DOMAIN 2>&1 | grep -E "SSL|TLS|expire"

# Smoke test: login
curl -s -X POST https://YOUR_DOMAIN/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"..."}' | jq .

# OpenAPI docs
open https://YOUR_DOMAIN/docs
```

---

## 11. Renovación automática de TLS

Let's Encrypt emite certificados de 90 días. Configurar renovación automática con cron:

```bash
# Editar crontab del root
sudo crontab -e

# Agregar: renovar a las 3:00 AM los días 1 y 15 de cada mes
0 3 1,15 * * certbot renew --quiet && docker compose -f /opt/ovd/docker-compose.prod.yml restart nginx
```

---

## 12. Rollback

```bash
cd /opt/ovd

# Ver versiones disponibles (si se usa tag de imagen versionada)
docker images ovd-engine
docker images ovd-bridge

# Rollback a versión anterior
OVD_ENGINE_VERSION=v1.2.0 OVD_BRIDGE_VERSION=v1.2.0 \
  docker compose -f docker-compose.prod.yml up -d ovd-engine ovd-bridge

# Rollback de base de datos: aplicar migration de reversión si existe
# psql ... < packages/opencode/migration-ovd/rollback_XXXX.sql
```

---

## 13. Variables de entorno de referencia

| Variable | Descripción | Default |
|---|---|---|
| `OVD_MODEL` | Modelo Claude a usar | `claude-sonnet-4-6` |
| `OVD_QA_ALERT_THRESHOLD` | Score mínimo QA antes de alerta webhook | `70` |
| `LOG_LEVEL` | Nivel de log (`debug`, `info`, `warn`, `error`) | `info` |
| `LANGCHAIN_TRACING_V2` | Activar tracing LangSmith | `false` |
| `LANGCHAIN_API_KEY` | API Key de LangSmith (si tracing activo) | — |
| `OVD_RAG_EMBEDDING_PROVIDER` | Provider de embeddings (`openai` \| `ollama`) | `openai` |
| `OLLAMA_BASE_URL` | URL de Ollama (si provider=ollama) | — |

### Docker Secrets requeridos

| Secret | Descripción |
|---|---|
| `anthropic_api_key` | API Key de Anthropic (`sk-ant-api03-...`) |
| `db_password` | Password de PostgreSQL |
| `ovd_engine_secret` | HMAC secret para comunicación Bridge↔Engine |
| `jwt_secret` | Secret para firmar JWT de sesión |
| `ovd_webhook_signing_key` | HMAC-SHA256 key para firma de webhooks |

---

## Arquitectura de red en producción

```
Internet
   │
   ▼
[Nginx :443/80]  ← TLS termination, rate limiting, security headers
   │
   ▼ (red interna ovd-prod-network)
[ovd-bridge :4096]  ← Bun/Hono API + SSE
   │
   ├──▶ [ovd-engine :8001]  ← LangGraph Python
   ├──▶ [postgres :5432]    ← PostgreSQL + pgvector
   ├──▶ [nats :4222]        ← NATS JetStream
   └──▶ [otel :4317/4318]   ← OpenTelemetry Collector
```

> Ningún servicio interno expone puertos al host excepto Nginx (80/443).
> Los secrets nunca tocan el sistema de archivos del host ni variables de entorno del proceso.
