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
├── engine/         Python — FastAPI + LangGraph (puerto 8001)
├── tui/            Rust — TUI terminal (ratatui + crossterm)
├── dashboard/      TypeScript — React 19 + Vite (puerto 5173)
├── finetune/       Pipeline de fine-tuning (pausado — créditos API)
├── knowledge/      Base de conocimiento RAG
└── mcp/            MCP server
docs/               SDD, ROADMAP, ADRs, security reports
```

## Para levantar el entorno

```bash
# Engine (desde la raíz del repo)
cd src/engine && uv sync && .venv/bin/uvicorn api:app --port 8001

# Dashboard
cd src/dashboard && bun dev

# TUI (compilar primero)
cd src/tui && cargo build && cargo run
```

## Credenciales dev

- Usuario: `omar@omarrobles.dev` / `ovd-dev-2026`
- DB: `postgresql://ovd_dev:changeme@localhost:5432/ovd_dev`
- PostgreSQL en Docker: contenedor `postgres_db` (pgvector/pgvector:pg16, puerto 5432)

## Estado actual (2026-04-16)

- **Sprints completados:** S3 → S18 (Skills externos + MCP context7 + TUI --from-file)
- **Tests:** 471/471 pasando (Python unit, excluye integration/e2e)
- **Próximo foco:** Despliegue centralizado del Engine (servidor VPS + dominio + TLS) como prerrequisito para FASE 5.F distribución TUI
- **Seguridad:** todos los hallazgos corregidos, incluyendo SEC-01 estructural (ver docs/security/SEC-2026-03-28.md)

### Novedades S18 (2026-04-16)
- **Superpowers en agentes:** 7 system prompts actualizados con writing-plans, TDD, verification-before-completion
- **ui-ux-pro-max:** clonado en `src/knowledge/ui-ux/`, consultado dinámicamente por agente frontend vía BM25 (`{ui_context}`)
- **Skills Manager web:** `/admin/skills` — actualiza repos externos desde el dashboard (admin only)
- **MCP Client Pool:** `src/engine/mcp_client.py` — context7 conectado a agentes backend/frontend/database/devops
- **MCP tools adapter:** `src/engine/tools/mcp_tools.py` — convierte MCP tools a LangChain StructuredTool
- **TUI --from-file:** carga archivos .md desde CLI o `Ctrl+O` interactivo en el formulario FR
- **Dependencia nueva:** `mcp>=1.0` (v1.27.0) en `src/engine/pyproject.toml`

## RAG

- **Estado:** activo (`OVD_RAG_ENABLED=true`)
- **Modelo embeddings:** `nomic-embed-text` vía Ollama local
- **Implementación:** directo en pgvector sin Bridge (`src/engine/rag.py`)
- **Bootstrap OVD Platform:** 1617 chunks indexados (docs/ + src/engine/ + CLAUDE.md)
- **Auto-index post-ciclo:** `_index_delivery_report` en graph.py llama a knowledge.bootstrap
- **Nota:** PostgreSQL (`postgres_db`) no tiene restart policy — hay que levantarlo manualmente si Docker Desktop se reinicia: `docker start postgres_db`

## Knowledge externa (S18)

- **ui-ux-pro-max:** `src/knowledge/ui-ux/` — guías de diseño UI/UX consultadas en runtime por agente frontend vía BM25 search (`template_loader.query_ui_context()`). Actualizar: `./scripts/update-skills.sh`
- **superpowers-upstream:** `src/knowledge/superpowers-upstream/` — copia local de obra/superpowers para comparar diffs. Los 6 skills integrados viven en los templates del engine. Actualizar: revisar diff con `scripts/update-skills.sh` y editar templates manualmente.

## Metodología de desarrollo

Este proyecto usa **Superpowers** como framework de desarrollo.
Referencia completa: `docs/SUPERPOWERS_OVD.md`

### Reglas obligatorias
- No implementar código sin plan previo (`writing-plans`)
- TDD estricto para **nodos nuevos** — RED-GREEN-REFACTOR
- Código legacy (fases 1–S17T, nodos WF4 existentes) no requiere cobertura retroactiva
- Siempre ejecutar `verification-before-completion` antes de declarar una tarea lista

### Bloque de inicio de sesión
Al retomar desarrollo, incluir este contexto en el primer mensaje:

```
Context: I'm continuing development of OVD (Oficina Virtual de Desarrollo).
- Stack: LangGraph + FastAPI + pgvector + Ollama (embeddings) + Multi-LLM router (Claude/OpenAI/Ollama) + Oracle 19c (vía MCP server)
- Status: S3→S17T completados, WF4 en desarrollo
- Existing code: do not redesign or refactor already completed phases
- Next task: [DESCRIBIR TAREA CONCRETA]

Skip brainstorming for completed phases. Jump directly to writing-plans
or subagent-driven-development for the next task.
```

## Reglas de trabajo

- Siempre abrir Claude Code desde la carpeta raíz del repo (`ovd-platform/`)
- **Registrar cambios en este CLAUDE.md al final de cada sesión** — rutas, estado de sprints, credenciales
- Hacer commit al final de cada sesión de trabajo
- Rama de features: `dev`, merge a `main` vía PR
