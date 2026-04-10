# OVD Platform — Getting Started

Guía para levantar la plataforma en desarrollo local desde cero (Apple Silicon Mac).

**Tiempo estimado:** 20-30 minutos
**Prerequisitos:** Docker Desktop, Rust (cargo), Python >= 3.12, [uv](https://docs.astral.sh/uv/), Ollama

---

## 1. Clonar el repositorio

```bash
git clone git@github.com:omarrobles/ovd-platform.git
cd ovd-platform
```

---

## 2. Levantar PostgreSQL con pgvector

El proyecto usa un contenedor Docker standalone (sin compose) con pgvector:

```bash
# Levantar (o crear por primera vez)
docker run -d \
  --name postgres_db \
  -e POSTGRES_USER=ovd_dev \
  -e POSTGRES_PASSWORD=changeme \
  -e POSTGRES_DB=ovd_dev \
  -p 5432:5432 \
  pgvector/pgvector:pg16

# Verificar que arrancó
docker ps | grep postgres_db
# Debe mostrar: 0.0.0.0:5432->5432/tcp

# Verificar conexión
docker exec postgres_db pg_isready -U ovd_dev
# OK: /var/run/postgresql:5432 - accepting connections
```

> **Nota:** el contenedor no tiene restart policy. Si Docker Desktop se reinicia, levantarlo manualmente:
> ```bash
> docker start postgres_db
> ```

### Aplicar migraciones

```bash
cd src/engine
uv sync
uv run python -c "from db import run_migrations; run_migrations()"
```

---

## 3. Instalar y configurar Ollama

```bash
# Instalar (si no está)
brew install ollama

# Levantar el servidor
ollama serve &

# Descargar los modelos requeridos
ollama pull qwen2.5-coder:7b      # Agentes OVD (LLM principal)
ollama pull nomic-embed-text       # Embeddings RAG
```

Verificar:
```bash
ollama list
# NAME                     ID            SIZE    MODIFIED
# nomic-embed-text:latest  ...           274 MB  ...
# qwen2.5-coder:7b         ...           4.7 GB  ...
```

---

## 4. Configurar variables de entorno del Engine

```bash
cd src/engine
cp .env.example .env   # Si no existe, crear desde la plantilla
```

Variables mínimas en `src/engine/.env`:

```env
# Base de datos
DATABASE_URL=postgresql://ovd_dev:changeme@localhost:5432/ovd_dev

# LLM
ANTHROPIC_API_KEY=sk-ant-...       # Obtener en console.anthropic.com
OVD_MODEL=claude-sonnet-4-6

# Ollama local
OLLAMA_BASE_URL=http://localhost:11434

# RAG (activo por defecto)
OVD_RAG_ENABLED=true
OVD_EMBED_MODEL=nomic-embed-text
OVD_RAG_TOP_K=5
OVD_RAG_MIN_SCORE=0.65

# Auth
JWT_SECRET=<generar con: openssl rand -hex 32>
```

> `ANTHROPIC_API_KEY` es la única variable que requiere registro externo.
> El resto funciona con los valores por defecto de desarrollo local.

---

## 5. Levantar el Engine (Python / FastAPI)

```bash
cd src/engine
uv sync   # Crea .venv e instala dependencias

# Cargar .env y arrancar
env $(grep -v '^#' .env | grep '=' | xargs) uv run uvicorn api:app --port 8001 --reload
```

Verificar:
```bash
curl http://localhost:8001/health
# {"status":"ok","engine":"ovd-engine","version":"0.1.0"}
```

---

## 6. Indexar el contexto del proyecto en RAG (bootstrap)

El RAG necesita estar poblado para que los agentes tengan contexto del proyecto.

```bash
cd src/engine

# Indexar docs/ + src/engine/ + CLAUDE.md (≈1617 chunks, ~2 minutos)
env $(grep -v '^#' .env | grep '=' | xargs) \
  uv run python -c "
import asyncio, sys, pathlib
sys.path.insert(0, '.')
from knowledge.bootstrap import run
result = asyncio.run(run(
    org_id='omar',
    project_id='ovd-platform',
    source_path=pathlib.Path('../../docs'),
    doc_type='doc',
))
print(f'Indexados: {result.indexed}, Fallidos: {result.failed}')
"
```

> El bootstrap se ejecuta automáticamente al final de cada ciclo de entrega vía `_index_delivery_report` en `graph.py`. El paso manual solo es necesario la primera vez.

---

## 7. Compilar y lanzar el TUI (Rust)

```bash
cd src/tui
cargo build --release    # Primera vez: ~2-3 minutos
cargo run
```

El TUI se conecta al Engine en `http://localhost:8001` por defecto.

**Navegación básica:**
- `Tab` / `Shift+Tab` — cambiar panel
- `Enter` — confirmar / enviar
- `q` / `Esc` — salir del modo actual
- `Ctrl+C` — salir del TUI

---

## 8. Crear usuario admin inicial

```bash
curl -X POST http://localhost:8001/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "omar@omarrobles.dev",
    "password": "ovd-dev-2026",
    "org_name": "Omar Robles"
  }'
```

El endpoint devuelve un JWT de admin. Guardarlo para llamadas a la API.

---

## Arquitectura actual

```
TUI (Rust)
    │
    └─► Engine (Python FastAPI :8001)
            │
            ├─► LangGraph (agentes OVD)
            │       └─► Ollama (qwen2.5-coder:7b)
            │
            ├─► RAG (rag.py)
            │       ├─► pgvector (PostgreSQL :5432)
            │       └─► OllamaEmbeddings (nomic-embed-text)
            │
            └─► PostgreSQL (checkpointer + OVD tables)
```

> **Nota Bridge:** el Bridge TypeScript (puerto 3000) referenciado en documentación antigua **no está implementado**. El RAG y todos los endpoints relevantes están en el Engine Python directamente. Ver ADR-001.

---

## Solución de problemas comunes

| Síntoma | Causa probable | Solución |
|---------|---------------|----------|
| `connection refused` en puerto 5432 | postgres_db detenido | `docker start postgres_db` |
| `type "vector" does not exist` | pgvector no instalado | Verificar imagen `pgvector/pgvector:pg16` |
| `OVD_RAG_ENABLED` ignorado | .env no cargado en uvicorn | Usar `env $(cat .env \| xargs) uv run uvicorn ...` |
| `could not connect to server` en RAG | Ollama no corre | `ollama serve` en otra terminal |
| `model not found: nomic-embed-text` | Modelo no descargado | `ollama pull nomic-embed-text` |
| Engine arranca pero RAG falla silencioso | DATABASE_URL sin psycopg2 | `rag.py` convierte automáticamente `postgresql://` → `postgresql+psycopg2://` |
| Puerto 5432 sin `0.0.0.0:` en `docker ps` | Contenedor sin `-p` | Recrear con `-p 5432:5432` (ver paso 2) |

---

## Ejecutar los tests

```bash
cd src/engine

# Tests unitarios y de regresión (sin infraestructura)
uv run pytest tests/test_rag_unit.py tests/test_rag_chunkers.py tests/test_rag_regression.py -v

# Todos los tests Python (requiere DB y Ollama para integración)
uv run pytest tests/ -v --timeout=30

# Tests Rust
cd ../tui && cargo test
```

**Suite actual:** 314 tests (279 Python + 35 Rust), todos pasando sin infraestructura activa para la fase A.

---

## Bugs conocidos

| ID | Módulo | Descripción | Severidad |
|----|--------|-------------|-----------|
| BUG-005 | `knowledge/chunkers.py` | `_split_text()` loop infinito si `max_chars <= 200` | Media (no afecta producción) |

Ver `docs/bugs/BUG-005-split-text-loop-infinito.md` para el fix propuesto.
