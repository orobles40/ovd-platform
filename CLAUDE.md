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

## Estado actual (2026-04-22)

- **Sprints completados:** S3 → S24 (Robustez tool calling — artifacts, QA, run_tests filesystem-first)
- **Tests:** Python unit ~639 + integration 14 + docker 5 | Frontend (Vitest) 34 | Rust inline 26 | Total ~718
- **Rama activa:** `dev` (commits S22+S23+S24 sin mergear a `main`)
- **Próximo foco:** Mergear `dev` → `main` + contratar VPS (C01.A) + configurar dominio (C01.B) + TLS Caddy (C01.C)
- **Seguridad:** todos los hallazgos corregidos, incluyendo SEC-01 estructural (ver docs/security/SEC-2026-03-28.md)
- **Directorio de entregas dev:** `/Users/omarrobles/Workspace/mis-entregas/` (proyecto "Honorarios Médicos")

### Novedades S24 (2026-04-22) — rama `dev`
- **`_scan_workspace_artifacts()`:** nueva función — escanea el workspace por archivos de código cuando `written_files[]` queda vacío por bug en tracking de tool calls. Excluye `__pycache__`, `node_modules`, `.md`, `.DS_Store`, `ovd-delivery-*`.
- **`_detect_test_runner()` filesystem-first (S24-B):** busca `test_*.py`/`*.test.ts`/`*.rs` en disco directamente antes de revisar artifacts[] u output. Ignora `__pycache__` y `.venv` en el rglob.
- **`qa_review` filesystem-first (S24-C):** cuando `directory` está seteado, lee TODOS los archivos `.py/.ts/.sql/etc.` del workspace directamente, sin depender de `artifacts[]` ni `output`. Evita el score bajo por "main.py vacío" que ocurría en S23.
- **`deliver` S24-A fallback:** cuando `existing_arts=[]` y `agent_output=""`, llama `_scan_workspace_artifacts()` para recuperar los archivos que el agente escribió pero no registró.
- **Logging S24-D:** `log.info` en `_run_agent_with_tools` (written_files, artifacts finales) y en `run_tests` (directory, artifacts por agente, runner detectado).
- **639 tests pasan** (0 fallos)

### Diagnóstico confirmado S24 (para referencia futura)
- **Causa raíz artifacts=[]:** `tool_result` de `write_file` puede no ser `str` puro con algunos wrappers de LangChain/Ollama → `isinstance(tool_result, str)` falla silenciosamente → `written_files=[]` → `artifacts=[]`.
- **Efecto cascada:** `run_tests` no detecta tests (runner=none), `qa_review` ve output vacío (score bajo), `deliver` reporta files=0 aunque los archivos SÍ estén en disco.
- **Fix:** filesystem-first en todos los nodos que necesitan saber qué archivos existen.

### Novedades S23 (2026-04-22) — rama `dev`
- **`deliver` S23-A:** usa `artifacts[]` directamente cuando el agente escribió con tool calling (no re-parsea output vacío)
- **`_detect_test_runner` S23-B:** busca en artifacts[], output fences y filesystem glob
- **`qa_review` S23-C:** lee archivos del disco via artifacts+directory cuando output=""
- **`system_backend.md` S23-D:** sección "Infraestructura obligatoria para proyectos Python" (`__init__.py`, `pytest.ini`, `conftest.py`) — ahora el SDD genera 4 req + 5 tareas incluyendo infraestructura
- **Correcciones:** `factories.make_agent_result` artifacts=[] (era formato incorrecto), `test_s12_api_v1` mock row sin columna oracle_involved obsoleta

### Novedades S22 (2026-04-21) — rama `dev`
- **Nodo `run_tests`:** detecta runner (pytest/vitest/cargo), ejecuta con timeout 60s, retry loop máx 2 rondas antes de continuar
- **Security scan CLI:** helpers `_run_security_scans` + `_exec_scan_tool` — semgrep, gitleaks, pip-audit — activado con `OVD_SECURITY_SCAN_ENABLED=true` (default: false)
- **Nodo `generate_docs`:** genera README/OpenAPI/ADR/CHANGELOG según tipo de FR; falla gracefully (generated_docs=[] si LLM falla)
- **Template `system_docs.md`:** `src/engine/templates/system_docs.md` — nuevo template para el documentador
- **SSE events nuevos:** `test_results` y `generated_docs` emitidos en el stream; ambos incluidos en el evento `done`
- **Dashboard:** 2 nodos nuevos en `GRAPH_NODES` (`Ejecutar tests`, `Generar docs`) + aliases en `NODE_ALIAS`
- **Grafo actualizado:** `qa_review → run_tests → generate_docs → deliver` (antes: `qa_review → deliver`)
- **Tests S22:** 23 tests nuevos en `test_s22_run_tests.py`, `test_s22_security_scan.py`, `test_s22_generate_docs.py`

### Novedades S21 (sesión anterior)
- **Nodo `describe_image`:** visión multimodal para wireframes/mockups adjuntos al FR
- **Dashboard approval panel:** feedback textarea, acción `revise`, adjunto de archivo, contador de revisiones, exportar SDD
- **Documentación automática:** analizado y planificado (implementado en S22)

### Novedades S19 (2026-04-17)
- **Tests Block C (frontend):** Vitest — `Approval.test.tsx` y `Telemetry.test.tsx` corregidos (34 tests pasando)
- **Tests Block D (Docker smoke):** `src/engine/tests/test_docker_smoke.py` — 5 tests `@pytest.mark.docker` con lifecycle completo
- **Tests Block E (Rust inline):** `#[cfg(test)]` en `workspace.rs`, `auth.rs`, `config/mod.rs` — 26 tests
- **CORS:** `CORSMiddleware` en `src/engine/api.py` — configurable vía `OVD_CORS_ORIGINS`
- **RAG multi-provider:** `src/engine/rag.py` — switch `OVD_RAG_EMBEDDING_PROVIDER=openai|ollama`
- **`docs/ROADMAP.md`:** actualizado a v0.9.0-quality-docs

## RAG

- **Estado:** activo (`OVD_RAG_ENABLED=true`)
- **Modelo embeddings dev:** `nomic-embed-text` vía Ollama local (`OVD_RAG_EMBEDDING_PROVIDER=ollama`)
- **Modelo embeddings prod:** `text-embedding-3-small` vía OpenAI (`OVD_RAG_EMBEDDING_PROVIDER=openai`)
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
- Status: S3→S19 completados, próximo: despliegue VPS (C01)
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
