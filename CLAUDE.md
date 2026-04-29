# OVD Platform — Omar Robles

Este repositorio es **ovd-platform**, un agente de desarrollo interno para acelerar la construcción y mantención de sistemas de clientes.

## Contexto del proyecto

- **Producto:** OVD Platform (Oficina Virtual de Desarrollo)
- **Empresa:** Omar Robles
- **Repo:** `git@github.com:omarrobles/ovd-platform.git`
- **Rama principal:** `main` | **Rama de desarrollo:** `dev`

## Estructura del código

```
src/
├── engine/         Python — FastAPI + LangGraph (puerto 8001)
├── tui/            Rust — TUI terminal (ratatui + crossterm)
├── dashboard/      TypeScript — React 19 + Vite (puerto 5173)
├── finetune/       Pipeline de fine-tuning (pausado)
├── knowledge/      Base de conocimiento RAG
└── mcp/            MCP server
docs/
├── adr/            ADRs (ADR-001, ADR-002, ADR-003)
├── sprints/
│   ├── CURRENT.md  Sprint activo (S96) — roadmap y ciclo de validación
│   └── HISTORY.md  Historial S19–S95
└── ...
```

## Para levantar el entorno

```bash
# Engine
cd src/engine && uv sync
env ANTHROPIC_API_KEY="" .venv/bin/uvicorn api:app --port 8001

# Dashboard
cd src/dashboard && bun dev

# TUI
cd src/tui && cargo build && cargo run

# PostgreSQL (si Docker Desktop reinició)
docker start postgres_db
```

## Credenciales dev

- Usuario: `omar@omarrobles.dev` / `ovd-dev-2026`
- DB: `postgresql://ovd_dev:changeme@localhost:5432/ovd_dev`
- PostgreSQL en Docker: contenedor `postgres_db` (pgvector/pgvector:pg16, puerto 5432)
- OVD_SECRET: ver `src/engine/.env`

## Estado actual

Ver `.claude/CONTEXT.md` para estado dinámico del proyecto:
- Sprint activo, tareas pendientes y completadas
- Fallos pre-existentes a corregir
- Issues abiertos
- Ciclos de referencia
- Skills activos

`CONTEXT.md` se actualiza con `/session-close` al final de cada sesión.

## ADR-003 — Selección de modelos LLM

Referencia obligatoria (`docs/adr/ADR-003-model-selection-criteria.md`) antes de cambiar modelos, migrar stacks, o trabajar con frontend visual.

**Reglas clave:**
1. Verificar existencia en `ollama.com/library` — propuestas externas suelen alucinar nombres
2. Apple Silicon serializa GPU — 2 modelos pinned NO dan paralelismo real
3. Q4_K_M es default — Q6/Q8 sobredimensionado para casos típicos
4. NO migrar de LangGraph a Autogen/CrewAI — regresión arquitectural
5. A/B test cuantitativo (mínimo 3 ciclos) antes de cambiar modelo en producción
6. Baseline a superar: QA 93/100, duración 13 min, costo $0 (S76)

## RAG

- **Estado:** activo (`OVD_RAG_ENABLED=true`)
- **Embeddings dev:** `nomic-embed-text` vía Ollama
- **Embeddings prod:** `text-embedding-3-small` vía OpenAI
- **Bootstrap:** 1617 chunks (docs/ + src/engine/ + CLAUDE.md)
- **Auto-index:** `_index_delivery_report` en graph.py post-ciclo

## Knowledge externa

- `src/knowledge/ui-ux/` — guías UI/UX para agente frontend (BM25 search)
- `src/knowledge/superpowers-upstream/` — referencia skills integrados

## Metodología de desarrollo

Framework: **Superpowers** (`docs/SUPERPOWERS_OVD.md`)

### Reglas obligatorias
- No implementar sin plan previo (`writing-plans`)
- TDD estricto para nodos nuevos — RED-GREEN-REFACTOR
- Ejecutar `verification-before-completion` antes de declarar una tarea lista

### Bloque de inicio de sesión

```
Context: I'm continuing development of OVD Platform (Oficina Virtual de Desarrollo).
Stack: LangGraph + FastAPI + pgvector + Ollama + Multi-LLM router + Oracle 19c (MCP)
Status: S3→S95 completados en rama dev. Próximo: S96.
Existing code: do not redesign or refactor already completed phases.
Next task: [DESCRIBIR TAREA CONCRETA]

Sprint activo y ciclo de validación: docs/sprints/CURRENT.md
Historial S19–S95: docs/sprints/HISTORY.md
```

## Reglas de trabajo

- Abrir Claude Code desde la raíz del repo (`ovd-platform/`)
- Actualizar `docs/sprints/CURRENT.md` al final de cada sesión
- Commit al final de cada sesión
- Merge a `main` vía PR desde `dev`
- Para operaciones destructivas (DROP, DELETE, force push): pedir confirmación siempre
