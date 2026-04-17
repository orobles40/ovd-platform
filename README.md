# OVD Platform — Oficina Virtual de Desarrollo

> Herramienta interna de Omar Robles para acelerar el desarrollo y mantención de sistemas de sus clientes.
> No es un producto público ni está afiliado con OpenCode. Ver [CREDITS.md](CREDITS.md) para atribuciones del fork base.

OVD Platform es un agente de desarrollo multi-LLM que toma una **Feature Request** en lenguaje natural, genera un **SDD (Software Design Document)**, lo somete a revisión humana y luego ejecuta agentes especializados (backend, frontend, database, devops) que escriben el código real en el directorio del proyecto.

---

## Índice

1. [Arquitectura](#arquitectura)
2. [Prerrequisitos](#prerrequisitos)
3. [Setup de desarrollo](#setup-de-desarrollo)
4. [Variables de entorno](#variables-de-entorno)
5. [Primer ciclo de uso](#primer-ciclo-de-uso)
6. [Correr los tests](#correr-los-tests)
7. [Estructura del repositorio](#estructura-del-repositorio)
8. [Flujo de trabajo del equipo](#flujo-de-trabajo-del-equipo)
9. [Despliegue en producción](#despliegue-en-producción)
10. [Troubleshooting](#troubleshooting)

---

## Arquitectura

```
┌─────────────────┐     ┌──────────────────────────────────────────┐
│   TUI Rust      │     │          OVD Engine (FastAPI)            │
│  `ovd` binary   │────▶│  LangGraph + 4 agentes especializados    │
│  puerto: CLI    │     │  puerto: 8001                            │
└─────────────────┘     └──────────┬───────────────────────────────┘
                                   │
┌─────────────────┐                │      ┌─────────────────────────┐
│ Dashboard React │────────────────┤      │   PostgreSQL 16          │
│  Vite + Recharts│                │─────▶│   + pgvector (RAG)       │
│  puerto: 5173   │                │      │   puerto: 5432           │
└─────────────────┘                │      └─────────────────────────┘
                                   │
                                   │      ┌─────────────────────────┐
                                   └─────▶│   Ollama (embeddings)   │
                                          │   nomic-embed-text       │
                                          │   puerto: 11434          │
                                          └─────────────────────────┘
```

**Flujo de un ciclo completo:**

```
FR (texto libre)
  → [Agente Analizador]  clasifica tipo y complejidad
  → [Agente SDD]         genera requisitos, tareas, restricciones, diseño
  → [Revisión humana]    aprobar / rechazar / pedir revisión con feedback
  → [Fan-out paralelo]   backend + frontend + database + devops ejecutan en paralelo
  → [Agente Security]    audita el código generado
  → [Agente QA]          valida contra el SDD original
  → [Entrega]            escribe archivos al directorio, genera informe, crea branch + PR
```

---

## Prerrequisitos

Instalar todo lo siguiente **antes** de clonar el repo.

| Herramienta | Versión mínima | Instalación |
|-------------|----------------|-------------|
| Docker Desktop | 4.x | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop) |
| Python | 3.12 | `brew install python@3.12` (macOS) |
| uv | 0.4+ | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Bun | 1.2+ | `curl -fsSL https://bun.sh/install \| bash` |
| Rust + Cargo | 1.78+ | `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh` |
| Ollama | 0.3+ | `brew install ollama` (macOS) o [ollama.com](https://ollama.com) |

> **macOS Apple Silicon:** todo el stack corre nativo. No se necesita Rosetta.
>
> **Linux:** reemplazar los comandos `brew` por el gestor de paquetes de tu distro.
>
> **Windows:** usar WSL2 con Ubuntu 22.04. El TUI Rust funciona en Windows nativo pero el engine requiere Linux.

---

## Setup de desarrollo

### 1. Clonar el repositorio

```bash
git clone git@github-personal:orobles40/ovd-platform.git
# o empresa:
git clone git@github.com:codigonet-cloud/ovd-platform.git

cd ovd-platform
```

### 2. Levantar PostgreSQL con pgvector

El engine necesita PostgreSQL 16 con la extensión `pgvector` instalada. Usamos la imagen oficial de pgvector:

```bash
docker run -d \
  --name postgres_db \
  -e POSTGRES_DB=ovd_dev \
  -e POSTGRES_USER=ovd_dev \
  -e POSTGRES_PASSWORD=changeme \
  -p 5432:5432 \
  pgvector/pgvector:pg16
```

Verificar que levantó correctamente:

```bash
docker exec postgres_db pg_isready -U ovd_dev
# Resultado esperado: /var/run/postgresql:5432 - accepting connections
```

> **Importante:** este contenedor no tiene `restart: always`. Si Docker Desktop se reinicia, hay que levantarlo manualmente:
> ```bash
> docker start postgres_db
> ```

### 3. Configurar variables de entorno del Engine

```bash
cd src/engine
cp .env .env.local   # .env ya tiene valores de desarrollo listos
```

El archivo `.env` incluido en el repo tiene todos los valores necesarios para desarrollo local. **No es necesario modificarlo** para el primer arranque, salvo agregar tu propia `ANTHROPIC_API_KEY` si quieres usar Claude en lugar de Ollama.

Editar `.env` si corresponde:

```bash
# Opción A: usar Ollama local (sin costo, sin API key)
OVD_MODEL=qwen2.5-coder:7b
OLLAMA_BASE_URL=http://localhost:11434

# Opción B: usar Claude Sonnet (requiere API key de Anthropic)
OVD_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...   # reemplazar con tu key real
```

### 4. Descargar modelo Ollama (si usas Opción A)

```bash
# Modelo principal para agentes
ollama pull qwen2.5-coder:7b

# Modelo de embeddings para RAG (siempre requerido en dev)
ollama pull nomic-embed-text
```

Verificar que Ollama está corriendo:

```bash
ollama list
# Debe mostrar qwen2.5-coder:7b y nomic-embed-text
```

### 5. Instalar dependencias y ejecutar migraciones del Engine

```bash
cd src/engine

# Instalar dependencias Python con uv (crea .venv automáticamente)
uv sync

# Ejecutar migraciones de base de datos (crea tablas OVD + extensiones)
.venv/bin/alembic upgrade head
```

Si la migración fue exitosa verás:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 20260412_0001, web_sources
```

### 6. Crear usuario administrador inicial

```bash
# Aplicar seed de desarrollo (usuario + org + proyecto de ejemplo)
psql postgresql://ovd_dev:changeme@localhost:5432/ovd_dev \
  -f migrations/seed_prod.sql
```

Esto crea:
- **Org:** `ORG_OMAR_ROBLES`
- **Usuario admin:** `omar@omarrobles.dev` / contraseña: `ovd-dev-2026`
- **Proyecto:** `HHMM` (ejemplo de proyecto cliente)

### 7. Arrancar el Engine

```bash
cd src/engine

# Con el .env del repo (Ollama local)
.venv/bin/uvicorn api:app --port 8001 --reload

# O explícitamente cargando el archivo
.venv/bin/uvicorn api:app --port 8001 --reload --env-file .env
```

Verificar que el engine responde:

```bash
curl http://localhost:8001/health
# {"status":"ok","engine":"ovd-engine","version":"0.1.0"}
```

### 8. Arrancar el Dashboard (opcional)

El dashboard es la interfaz web. No es necesario para usar el TUI.

```bash
cd src/dashboard
bun install
bun dev
# Abrir http://localhost:5173
```

### 9. Compilar y ejecutar el TUI

```bash
cd src/tui

# Primera vez: compilar (tarda 2-3 minutos)
cargo build

# Ejecutar
cargo run

# O con un archivo de requisitos precargado
cargo run -- --from-file /ruta/a/requisitos.md
```

Al abrir por primera vez aparece el **Onboarding Wizard** (3 pasos):
1. URL del engine: `http://localhost:8001`
2. Org ID: `ORG_OMAR_ROBLES`
3. Confirmar

Luego pide login con `omar@omarrobles.dev` / `ovd-dev-2026`.

---

## Variables de entorno

Variables del Engine (`src/engine/.env`). Las marcadas como **requeridas** impiden que el engine arranque si no están definidas.

| Variable | Requerida | Default dev | Descripción |
|----------|-----------|-------------|-------------|
| `DATABASE_URL` | ✅ Sí | `postgresql://ovd_dev:changeme@localhost:5432/ovd_dev` | Conexión PostgreSQL |
| `JWT_SECRET` | ✅ Sí | valor en `.env` | Secreto para firmar JWT (mín. 32 chars). Nunca compartir. |
| `OVD_MODEL` | No | `qwen2.5-coder:7b` | Modelo LLM para los agentes |
| `OLLAMA_BASE_URL` | No | `http://localhost:11434` | URL de Ollama local |
| `ANTHROPIC_API_KEY` | No | — | Requerida solo si `OVD_MODEL=claude-*` |
| `OPENAI_API_KEY` | No | — | Requerida si `OVD_RAG_EMBEDDING_PROVIDER=openai` |
| `OVD_RAG_ENABLED` | No | `true` | Activar RAG con pgvector |
| `OVD_EMBED_MODEL` | No | `nomic-embed-text` | Modelo de embeddings |
| `OVD_RAG_EMBEDDING_PROVIDER` | No | `ollama` | `ollama` o `openai` |
| `OVD_ENGINE_SECRET` | No | `""` | Secret compartido con el Bridge (vacío = desactivado en dev) |
| `OVD_QA_MIN_SCORE` | No | `0` | Score mínimo QA para aprobar ciclo (0 = desactivado en dev) |
| `OVD_SECURITY_MIN_SCORE` | No | `0` | Score mínimo Security (0 = desactivado en dev) |
| `LOG_LEVEL` | No | `debug` | Nivel de logging: `debug`, `info`, `warning`, `error` |
| `NATS_URL` | No | `nats://localhost:4222` | NATS JetStream (opcional, solo si usas NATS local) |

> El archivo `src/engine/.env` tiene todos los valores de desarrollo listos. Solo hay que reemplazar las API keys con las tuyas.

---

## Primer ciclo de uso

Con el engine corriendo y el TUI abierto:

### Opción A: TUI

```
1. Login: omar@omarrobles.dev / ovd-dev-2026
2. Seleccionar workspace: HHMM (o crear uno nuevo con [n])
3. Dashboard → [n] Nueva Feature Request
4. Escribir la FR: "Implementar endpoint GET /pacientes con paginación"
5. Ctrl+S para enviar
6. El engine procesa: Analizador → SDD → (pausa para revisión)
7. En el panel de aprobación: [y] aprobar / [r] pedir revisión / [n] rechazar
8. Si se aprueba: los agentes ejecutan y generan el código
9. [d] ver pantalla de entrega con archivos creados y scores
```

Teclas globales del TUI:

| Tecla | Acción |
|-------|--------|
| `n` | Nueva Feature Request |
| `h` | Historial de ciclos |
| `u` | Dashboard de quota/tokens |
| `q` | Cambiar workspace |
| `Shift+L` | Logout |
| `Ctrl+O` | Cargar archivo .md como FR |
| `Ctrl+C` | Salir |

### Opción B: Dashboard Web

1. Abrir `http://localhost:5173`
2. Login con `omar@omarrobles.dev` / `ovd-dev-2026`
3. Ir a **Panel de Aprobación** para revisar SDDs pendientes
4. Ir a **Telemetría** para ver métricas de ciclos, tokens y costos

---

## Correr los tests

### Engine (Python)

```bash
cd src/engine

# Tests unitarios — rápidos, sin infraestructura
.venv/bin/pytest -m "not integration and not docker" -q

# Tests de integración — requieren PostgreSQL corriendo
.venv/bin/pytest -m integration -q

# Tests de smoke Docker — requieren Docker daemon
.venv/bin/pytest -m docker tests/test_docker_smoke.py -v

# Todos los tests unitarios (modo verbose)
.venv/bin/pytest -m "not integration and not docker" -v
```

### Dashboard (Vitest + Testing Library)

```bash
cd src/dashboard

# Instalar devDependencies si no están
bun install

# Correr tests (modo CI — sin watcher)
bunx vitest run --config vitest.config.ts

# Modo watch durante desarrollo
bunx vitest --config vitest.config.ts
```

### TUI (Rust)

```bash
cd src/tui

# Todos los tests inline de los módulos
cargo test

# Con output detallado
cargo test -- --nocapture
```

### Estado esperado (suite completa)

| Suite | Tests | Tiempo aprox. |
|-------|-------|---------------|
| Python unit | ~471 | 45s |
| Python integration | 14 | 10s (requiere PG) |
| Frontend Vitest | 34 | 8s |
| Rust `cargo test` | 63 | 1s |

---

## Estructura del repositorio

```
ovd-platform/
│
├── src/
│   ├── engine/                 Python — FastAPI + LangGraph (puerto 8001)
│   │   ├── api.py              Endpoints FastAPI + middleware CORS/rate-limit
│   │   ├── graph.py            Grafo LangGraph con todos los nodos y agentes
│   │   ├── rag.py              RAG con pgvector (Ollama o OpenAI embeddings)
│   │   ├── auth.py             JWT access tokens + refresh tokens
│   │   ├── model_router.py     Router multi-LLM (Claude/OpenAI/Ollama)
│   │   ├── routers/            Sub-routers FastAPI (auth_router, api_v1)
│   │   ├── templates/          System prompts de cada agente (.md)
│   │   ├── tools/              LangChain tools (write_file, read_file, MCP)
│   │   ├── migrations/         Alembic + seeds SQL
│   │   ├── tests/              Suite de tests Python
│   │   ├── Dockerfile          Build de producción
│   │   ├── docker-entrypoint.sh  Carga secrets + migraciones + uvicorn
│   │   └── .env                Variables de entorno de desarrollo
│   │
│   ├── dashboard/              TypeScript — React 19 + Vite (puerto 5173)
│   │   ├── src/pages/          Páginas React (Login, Dashboard, Approval, Telemetry...)
│   │   ├── src/api/            Clientes HTTP (ovd.ts, auth.ts)
│   │   ├── src/context/        AuthContext con refresh automático
│   │   ├── src/tests/          Tests Vitest + MSW
│   │   ├── Dockerfile          Build multi-stage: bun → nginx
│   │   └── nginx.conf          Config nginx para SPA + health check
│   │
│   ├── tui/                    Rust — TUI terminal (binario `ovd`)
│   │   ├── src/ui/             Pantallas ratatui (login, session, delivery...)
│   │   ├── src/api/client.rs   Cliente HTTP hacia el engine
│   │   ├── src/config/mod.rs   Config local ~/.ovd/config.toml + tokens
│   │   └── src/models/         Structs de serialización (workspace, auth, session)
│   │
│   ├── knowledge/              Base de conocimiento RAG
│   │   ├── ui-ux/              Guías de diseño (ui-ux-pro-max-skill)
│   │   └── superpowers-upstream/  Framework de metodología (referencia)
│   │
│   └── finetune/               Pipeline de fine-tuning (pausado — créditos API)
│       └── data/merged.jsonl   312 ejemplos de entrenamiento listos
│
├── docs/                       Documentación técnica del proyecto
│   ├── ROADMAP.md              Estado de todas las fases y sprints
│   ├── security/               Reportes de seguridad
│   └── MODEL_STRATEGY.md       Plan de modelo propio (M2.A/M2.B)
│
├── infra/
│   ├── caddy/Caddyfile         Reverse proxy con TLS automático
│   └── postgres/               Scripts de inicialización de producción
│
├── docker-compose.prod.yml     Stack completo de producción (Caddy + engine + dashboard + backup)
├── .env.prod.example           Template de variables de producción
└── CLAUDE.md                   Contexto del proyecto para Claude Code
```

---

## Flujo de trabajo del equipo

### Ramas

```
main      ← producción — solo merge via PR, siempre debe compilar y pasar tests
dev       ← integración — base para features
feat/*    ← features nuevas (ej: feat/s19-nuevo-agente)
fix/*     ← correcciones
```

### Proceso estándar

```bash
# 1. Partir desde dev actualizado
git checkout dev && git pull origin dev

# 2. Crear rama de feature
git checkout -b feat/mi-feature

# 3. Desarrollar con TDD
# Escribir test → confirmar falla → implementar → confirmar pasa

# 4. Verificar que todos los tests pasan antes de hacer PR
cd src/engine && .venv/bin/pytest -m "not integration and not docker" -q
cd src/dashboard && bunx vitest run
cd src/tui && cargo test

# 5. Commit
git add <archivos-específicos>
git commit -m "feat(componente): descripción concisa del cambio"

# 6. Push y abrir PR hacia dev
git push origin feat/mi-feature
gh pr create --base dev --title "feat: ..."
```

### Convención de commits

```
feat(scope): nueva funcionalidad
fix(scope):  corrección de bug
test(scope): agregar o corregir tests
docs(scope): documentación
refactor(scope): refactor sin cambio de comportamiento
chore(scope): cambios de configuración, dependencias
```

### Reglas obligatorias antes de hacer PR

- Tests pasan en local (unit + frontend + rust)
- No hay `print()` de debug en código Python
- No hay credenciales hardcodeadas
- Si se modifica el engine, actualizar `CLAUDE.md` con el estado del sprint

---

## Despliegue en producción

El despliegue completo usa Docker Compose con Caddy como reverse proxy y TLS automático.

**Prerrequisitos en el servidor:**
- VPS con Ubuntu 22.04 LTS, mínimo 4 GB RAM / 2 vCPU / 40 GB SSD
- Docker Engine 24+ instalado
- Dominio apuntando al IP del servidor (A record en DNS)

**Pasos rápidos:**

```bash
# 1. Clonar en el servidor
git clone git@github.com:codigonet-cloud/ovd-platform.git
cd ovd-platform

# 2. Crear Docker Secrets (contraseñas y API keys)
echo "TU_PASSWORD_DB"       | docker secret create db_password -
echo "TU_ANTHROPIC_KEY"     | docker secret create anthropic_api_key -
echo "TU_OPENAI_KEY"        | docker secret create openai_api_key -
openssl rand -hex 32        | docker secret create ovd_engine_secret -

# 3. Configurar variables de entorno
cp .env.prod.example .env.prod
# Editar .env.prod: DOMAIN, VITE_API_URL, OVD_CORS_ORIGINS

# 4. Levantar el stack
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

# 5. Verificar
docker compose -f docker-compose.prod.yml ps
curl https://TU_DOMINIO/health
```

Ver detalles completos en `.env.prod.example` y `docker-compose.prod.yml`.

---

## Troubleshooting

### El engine no arranca: `DATABASE_URL not set` o `RuntimeError`

```bash
# Verificar que .env está en el directorio correcto
ls src/engine/.env

# Verificar que postgres está corriendo
docker ps | grep postgres_db

# Si postgres no aparece, levantarlo
docker start postgres_db
```

### `alembic upgrade head` falla: `connection refused`

El engine no puede conectar a PostgreSQL. Verificar:

```bash
# 1. Confirmar que el contenedor está corriendo
docker ps -a | grep postgres_db

# 2. Si está en estado Exited, levantarlo
docker start postgres_db

# 3. Probar conexión directa
psql postgresql://ovd_dev:changeme@localhost:5432/ovd_dev -c "SELECT 1"
```

### `ModuleNotFoundError` al iniciar el engine

El virtualenv no está creado o las dependencias no están instaladas:

```bash
cd src/engine
uv sync          # reinstala todo
.venv/bin/python -c "import fastapi; print('OK')"
```

### El TUI muestra `Error cargando workspaces: connection refused`

El engine no está corriendo. Verificar:

```bash
curl http://localhost:8001/health
# Si falla: arrancar el engine primero (paso 7 del setup)
```

### Los agentes siempre devuelven score 0 en Security

Ocurre cuando el modelo Ollama (qwen2.5-coder:7b) no sigue el formato JSON esperado. El engine tiene un fallback que devuelve 75 en ese caso. Si el score es consistentemente 0, verificar:

```bash
# Confirmar que Ollama está corriendo
ollama list

# Si no está corriendo
ollama serve
```

### `bun dev` falla: `Cannot find module '@tanstack/react-query'`

```bash
cd src/dashboard
bun install   # reinstalar dependencias
bun dev
```

### El dashboard muestra `401 Unauthorized` en todas las peticiones

El JWT del navegador expiró (1 hora). El dashboard hace refresh automático, pero si el engine estuvo caído, el refresh token también puede haber caducado (7 días). Solución: hacer logout y login nuevamente.

### `cargo build` falla: `linker 'cc' not found` (Linux)

```bash
sudo apt-get install build-essential
cargo build
```

### Embeddings RAG no funcionan: `connection refused` a Ollama

```bash
# Verificar que Ollama está corriendo
curl http://localhost:11434/api/tags

# Si no responde, iniciar Ollama
ollama serve

# En macOS, Ollama corre como app — abrir desde Applications
```

---

## Credenciales de desarrollo

> Estas credenciales son **solo para entornos de desarrollo local**. Nunca usar en producción.

| Recurso | Valor |
|---------|-------|
| Dashboard / TUI — usuario | `omar@omarrobles.dev` |
| Dashboard / TUI — contraseña | `ovd-dev-2026` |
| PostgreSQL host | `localhost:5432` |
| PostgreSQL DB | `ovd_dev` |
| PostgreSQL usuario | `ovd_dev` |
| PostgreSQL contraseña | `changeme` |
| Engine URL | `http://localhost:8001` |
| Dashboard URL | `http://localhost:5173` |

---

> **Preguntas o problemas:** abrir un issue en el repositorio o contactar a Omar Robles.
