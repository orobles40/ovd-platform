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

- **Sprints completados:** S3 → S28 (SDD agent routing: devops solo infra; pytest exit codes diagnóstico)
- **Tests:** Python unit ~666 + integration 14 + docker 5 | Frontend (Vitest) 34 | Rust inline 26 | Total ~745
- **Rama activa:** `dev` (commits S22→S27 sin mergear a `main`)
- **Próximo foco:** Mergear `dev` → `main` + contratar VPS (C01.A) + configurar dominio (C01.B) + TLS Caddy (C01.C)
- **Seguridad:** todos los hallazgos corregidos, incluyendo SEC-01 estructural (ver docs/security/SEC-2026-03-28.md)
- **Directorio de entregas dev:** `/Users/omarrobles/Workspace/mis-entregas/` (proyecto "Honorarios Médicos")

### Novedades S28 (2026-04-22) — rama `dev`
- **`system_sdd.md` regla de agentes (S28-A):** Tabla explícita que mapea tipo de tarea → agente correcto. `devops` EXCLUSIVAMENTE para Dockerfile/CI/CD/Kubernetes. Para Python puro → solo `backend`. Prohibición explícita de asignar código de aplicación a `devops`. Elimina la contaminación de 2 agentes escribiendo el mismo archivo.
- **`run_tests` exit codes pytest (S28-C):** Eliminado conflicto `-v`/`-q` en el comando pytest. Nuevos warnings diferenciados: exit 5 = "0 tests encontrados, verificar convención test_*.py", exit 4 = "error de colección (SyntaxError/ImportError)", exit 2 = "ejecución interrumpida". Lista de archivos .py en workspace incluida en el warning de exit 5.
- **S28-B descartado** (workspace cleanup): riesgo de borrar código preexistente del proyecto. La raíz real era S28-A.
- **9 tests nuevos** en `test_s28.py`. **666 tests pasan** (0 fallos).

### Novedades S27 (2026-04-22) — rama `dev`
- **`run_tests` conftest.py injection (S27-A):** Si `conftest.py` en la raíz del workspace está vacío o no existe, `run_tests` lo inyecta automáticamente con `sys.path.insert(0, "src")`. No sobreescribe si ya tiene contenido. Elimina el bloqueo de QA por conftest vacío.
- **`audit_logger` JSON fix (S27-B):** El campo `metadata` (JSONB) se pasaba como `dict` Python → `cannot adapt type 'dict'`. Fix: `json.dumps({...})`. Eventos `session_created` y `cycle_completed` ahora se graban correctamente en BD.
- **`_index_delivery_report` sys.path fix (S27-C):** `from knowledge import bootstrap` fallaba porque `src/` no estaba en sys.path. Fix: insertar `sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))` antes del import. Informes de entrega ahora se indexan en RAG.
- **`system_qa.md` cláusula infraestructura (S27-D):** QA ya no marca `sdd_compliance=False` por diferencias menores en archivos de infraestructura (conftest.py vacío vs con contenido) ni por tener más tests que los especificados en el SDD.
- **9 tests nuevos** en `test_s27.py` — conftest injection (3 casos), audit_logger JSON, RAG-02 sys.path, QA template.
- **657 tests pasan** (0 fallos).

### Novedades S26 (2026-04-22) — rama `dev`
- **`system_backend.md` fix (S26-A):** Prohibición explícita de `__init__.py` en la raíz del workspace. Estructura correcta: `src/<paquete>/` + `conftest.py` con `sys.path.insert(0, "src")`. Ejemplo visual de ✅ vs ❌ estructura.
- **`run_tests` cwd + flags (S26-B):** `cwd=work_dir` para todos los runners (antes solo vitest/cargo). Nuevos flags: `--rootdir={work_dir}` y `--import-mode=importlib` → resuelve `ImportError: attempted relative import with no known parent package`.
- **`security_audit` filesystem-first (S26-C):** Mismo patrón S24-C de qa_review — lee archivos del workspace en vez de depender de `output`. Elimina el problema de "No se proporcionó código" en el flujo tool-calling.
- **9 tests nuevos** en `test_s26.py` — template, run_tests flags/cwd, security_audit filesystem.
- **648 tests pasan** (0 fallos).

### Novedades S25 (2026-04-22) — rama `dev`
- **`run_tests` usa `sys.executable` (S25-A):** en vez de `"python"` (no en PATH en macOS), usa el intérprete del venv del engine → pytest 9.0.3 disponible. Validado: 10 tests recolectados y ejecutados, loop de retry 3 rondas funcional.
- **Diagnóstico validado S23+S24:** reimport `sys` en `graph.py` (no estaba importado). Engine **sin `--reload`** → reiniciar manualmente después de cada cambio de código.
- **Resultado ciclo de validación S25:** Security 100/100, QA 95/100 (round 1), run_tests ejecuta pytest real, retry loop funcional. Tests fallan por estructura de agente (`__init__.py` raíz con import relativo) — issue pendiente en template `system_backend.md`.

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
