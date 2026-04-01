# OVD Platform — Getting Started

Guía para levantar la plataforma en desarrollo local por primera vez.

**Tiempo estimado:** 20-30 minutos
**Prerequisitos:** Docker Desktop, Bun >= 1.1, Python >= 3.12, [uv](https://docs.astral.sh/uv/getting-started/installation/), Git

---

## 1. Clonar y configurar el entorno

```bash
git clone <repo-url> ovd-platform
cd ovd-platform

# Copiar variables de entorno
cp .env.example .env
```

Abrir `.env` y completar las variables marcadas con `[REQUIRED]`:

| Variable | Dónde obtenerla |
|----------|-----------------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) → API Keys |
| `JWT_SECRET` | `openssl rand -hex 32` |
| `DATABASE_URL` | Se configura automáticamente con Docker Compose (ver paso 2) |

> Las variables `OVD_ENGINE_SECRET`, `OVD_TOKEN` y `LANGCHAIN_API_KEY` son opcionales en desarrollo local.

---

## 2. Levantar los servicios de infraestructura

```bash
# PostgreSQL + pgvector, NATS, OTEL Collector
docker compose up -d postgres nats otel

# Verificar que arrancan correctamente
docker compose ps
```

Esperar ~10 segundos hasta que PostgreSQL esté saludable:

```bash
docker compose exec postgres pg_isready -U ovd_dev
# OK: localhost:5432 - accepting connections
```

---

## 3. Aplicar migraciones de base de datos

```bash
# Aplicar todas las migraciones en orden
./scripts/migrate.sh

# Verificar estado
./scripts/migrate.sh --status
```

Las migraciones crean las tablas OVD con Row-Level Security habilitado.

---

## 4. Levantar el OVD Engine (Python)

```bash
cd src/engine

# uv crea el .venv e instala dependencias en un solo paso
uv sync

# Arrancar el engine (valida variables al inicio)
uv run python api.py
# INFO: startup config ok
# INFO: Application startup complete.
```

> **uv** gestiona automáticamente el `.venv`. No es necesario activarlo manualmente — `uv run` lo usa internamente. Si prefieres activar el venv explícitamente: `source .venv/bin/activate`.

**Otros componentes Python:**

```bash
# Fine-tuning pipeline (solo dependencias base)
cd src/finetune && uv sync

# Fine-tuning con GPU (Unsloth/torch — requiere CUDA)
cd src/finetune && uv sync --extra gpu

# MCP Server Oracle
cd src/mcp/oracle && uv sync

# MCP Server NATS
cd src/mcp/nats && uv sync
```

El Engine queda escuchando en `http://localhost:8001`.

---

## 5. Levantar el Bridge (TypeScript / Bun)

```bash
# Desde la raíz del proyecto
bun install

# Arrancar el Bridge (valida variables al inicio)
bun run dev
# INFO startup config ok
# INFO server listening on port 3000
```

El Bridge queda en `http://localhost:3000`.

---

## 6. Verificar que todo funciona

```bash
# Health check del Engine
curl http://localhost:8001/health
# {"status":"ok","engine":"ovd-engine","version":"0.1.0"}

# Health check del Bridge
curl http://localhost:3000/health
# {"status":"ok"}
```

---

## 7. Crear la primera organización y usuario admin

```bash
# Crear organización
curl -X POST http://localhost:3000/tenant/org \
  -H "Content-Type: application/json" \
  -d '{"name": "Mi Empresa", "slug": "mi-empresa"}'

# El endpoint devuelve un JWT de admin — guardarlo para los próximos pasos
```

> Endpoint en desarrollo — ver FASE 4.B en el ROADMAP.

---

## 8. Indexar el Project Profile en RAG (opcional)

Si ya tienes un proyecto configurado con su stack tecnológico:

```bash
./scripts/seed-rag.sh \
  --org <ORG_ID> \
  --project <PROJECT_ID> \
  --token <JWT_ADMIN> \
  --dir docs/
```

---

## Perfiles Docker Compose

El `docker-compose.yml` tiene perfiles para servicios opcionales:

```bash
# Solo infraestructura base (postgres + nats + otel)
docker compose up -d

# + Infisical (gestión de secrets por workspace — Sprint 9)
docker compose --profile infisical up -d

# + OVD Engine (requiere imagen construida)
docker compose --profile ovd up -d

# + MCP Oracle (requiere credenciales Oracle)
docker compose --profile oracle up -d
```

---

## Configurar Infisical (Sprint 9 — gestión de secrets)

Infisical reemplaza el `.env.local` para credenciales de bases de datos de clientes.

### Setup inicial

```bash
# 1. Generar claves de cifrado (ejecutar una sola vez, guardar el resultado)
openssl rand -hex 32   # → INFISICAL_ENCRYPTION_KEY
openssl rand -hex 32   # → INFISICAL_AUTH_SECRET

# 2. Agregar al .env
echo "INFISICAL_ENCRYPTION_KEY=<valor generado>" >> .env
echo "INFISICAL_AUTH_SECRET=<valor generado>" >> .env

# 3. Levantar Infisical
docker compose --profile infisical up -d
```

### Configurar el primer workspace

```bash
# 4. Abrir UI de Infisical
open http://localhost:8080

# 5. Crear cuenta admin y proyecto "ovd-platform"
# 6. Crear un environment por workspace del cliente:
#    - "alemana-cas"
#    - "alemana-cat"
#    - "alemana-cav"

# 7. En cada environment, crear los secrets:
#    ORACLE_HOST, ORACLE_PORT, ORACLE_USER, ORACLE_PASS, ORACLE_SERVICE

# 8. Crear Machine Identity con acceso al proyecto "ovd-platform"
#    Settings → Machine Identities → Create → copiar el token

# 9. Agregar al .env del engine
echo "INFISICAL_TOKEN=<machine-identity-token>" >> .env
echo "INFISICAL_PROJECT_ID=<project-id>" >> .env
```

### Asociar un workspace OVD a sus credenciales

```bash
# Actualizar el Project Profile del workspace con el secret_ref
curl -X PUT http://localhost:3000/ovd/project/<PROJECT_ID>/profile \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"secretRef": "alemana-cas"}'

# Desde ese momento, el Context Resolver recupera las credenciales
# de Infisical automáticamente en cada ciclo — sin .env.local
```

> **Fallback en desarrollo**: si `INFISICAL_TOKEN` no está configurado, el engine
> cae al `EnvAdapter` que lee variables con prefijo `OVD_SECRET_<WORKSPACE>_*` del `.env.local`.
> Esto es solo para desarrollo local. Para uso con clientes reales, configurar Infisical.

---

## Variables de entorno — referencia rápida

| Variable | Requerida | Default | Descripción |
|----------|-----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Sí | — | API key Anthropic |
| `DATABASE_URL` | Sí | — | URL PostgreSQL |
| `JWT_SECRET` | Sí | — | Secret JWT (min 32 chars) |
| `OVD_MODEL` | No | `claude-sonnet-4-6` | Modelo base de agentes |
| `OVD_ENGINE_URL` | No | `http://localhost:8001` | URL del Engine |
| `OVD_ENGINE_SECRET` | No | `""` | Secret Bridge↔Engine |
| `OVD_BRIDGE_URL` | No | `http://localhost:3000` | URL del Bridge |
| `NATS_URL` | No | `nats://localhost:4222` | URL NATS |
| `OVD_RAG_ENABLED` | No | `true` | Activar RAG |
| `LANGCHAIN_TRACING_V2` | No | `false` | LangSmith tracing |

Ver `.env.example` para la lista completa con descripciones.

---

## Solución de problemas comunes

**El Engine no arranca — `[REQUIRED] ANTHROPIC_API_KEY`**
→ Asegúrate que `.env` tiene `ANTHROPIC_API_KEY=sk-ant-...` y que el archivo está cargado.

**El Bridge no conecta con el Engine — `OVD Engine error 401`**
→ `OVD_ENGINE_SECRET` debe ser igual en Bridge y Engine, o dejarlo vacío en ambos.

**Error de migración — `permission denied for table`**
→ El usuario `ovd_dev` necesita ser owner de las tablas. Ejecutar `./scripts/migrate.sh --rls` para aplicar las políticas RLS.

**pgvector no disponible — `type "vector" does not exist`**
→ La imagen Docker usa `pgvector/pgvector:pg16`. Verificar con `docker compose exec postgres psql -U ovd_dev -c "SELECT extname FROM pg_extension WHERE extname='vector';"`.
