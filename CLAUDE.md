# OVD Platform — Omar Robles

Este repositorio es **ovd-platform**, un fork de OpenCode mantenido por Omar Robles como producto interno para acelerar el desarrollo y mantención de sistemas de sus clientes.

## Contexto del proyecto

- **Producto:** OVD Platform (Oficina Virtual de Desarrollo)
- **Empresa:** Omar Robles
- **Usuarios:** desarrolladores y arquitectos de Omar Robles (no clientes finales)
- **Repo:** `git@github.com:omarrobles/ovd-platform.git`
- **Rama principal:** `main`

## Estructura del código

```
src/
├── ovd-engine/     Python — FastAPI + LangGraph (puerto 8001)
├── tui/            Rust — TUI terminal (ratatui)
├── ovd-dashboard/  TypeScript — React 19 + Vite (puerto 5173)
├── finetune/       Pipeline de fine-tuning (pausado)
└── knowledge/      Base de conocimiento RAG
docs/               SDD, ROADMAP, ADRs
```

## Para levantar el entorno

```bash
# Engine (desde la raíz del repo)
cd src/engine && uvicorn api:app --port 8001

# Dashboard
cd src/dashboard && bun dev

# TUI (compilar primero)
cd src/tui && cargo build && cargo run
```

## Credenciales dev

- Usuario: `omar@omarrobles.dev` / `ovd-dev-2026`
- DB: `postgresql://ovd_dev:changeme@localhost:5432/ovd_dev`
- PostgreSQL en Docker: contenedor `postgres_db` (pgvector/pgvector:pg16, puerto 5432)

## Estado actual (2026-03-27)

- **Sprints completados:** S3 → S16T (TUI completa, engine, dashboard, GitHub PAT, RAG, fine-tuning)
- **Sin commit:** S16T, UX-01/02/03, SEC-01 (cambios en working tree)
- **Pendiente prioritario:** probar S16T en vivo, BUG-01 (cursor login), S16T.F (exportar informe)

## Reglas de trabajo

- Siempre abrir Claude Code desde esta carpeta (`opencode/`)
- Hacer commit al final de cada sesión de trabajo
- Rama de features: `dev`, merge a `main` vía PR
