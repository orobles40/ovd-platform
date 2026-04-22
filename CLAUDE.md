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

- **Sprints completados:** S3 → S38 (async tool invocation + QA truncation multi-agent)
- **Tests:** Python unit ~764 + integration 14 + docker 5 | Frontend (Vitest) 34 | Rust inline 26 | Total ~843
- **Rama activa:** `dev` (commits S22→S38 sin mergear a `main`)
- **Próximo foco:** Mergear `dev` → `main` + contratar VPS (C01.A) + configurar dominio (C01.B) + TLS Caddy (C01.C)
- **Seguridad:** todos los hallazgos corregidos, incluyendo SEC-01 estructural (ver docs/security/SEC-2026-03-28.md)
- **Directorio de entregas dev:** `/Users/omarrobles/Workspace/mis-entregas/` (proyecto "Honorarios Médicos")

### Novedades S38 (2026-04-22) — rama `dev`
- **async tool invocation (S38-A):** `_run_agent_with_tools` ahora usa `await tool_fn.ainvoke(args)` con fallback a `tool_fn.invoke(args)` cuando lanza `NotImplementedError`. Fix para context7 `StructuredTool` que fallaba con "does not support sync invocation" en ciclos con research web.
- **QA truncation 12k→20k (S38-B):** `qa_review` trunca `agent_output` a 20000 chars (antes 12000). Con 3 agentes (database+backend+frontend) generando ~6K cada uno, el output total (~18K) se cortaba, perdiendo código del agente frontend del análisis de QA.
- **10 tests nuevos** en `test_s38.py`. **764 tests pasan** (0 fallos).

### Novedades S37 (2026-04-22) — rama `dev`
- **audit_logger bigint fix (S37-A):** El INSERT en `ovd_audit_log` pasaba `str(uuid.uuid4())` para la columna `id` (que es `bigint` con `nextval` sequence). Fix: remover `id` del INSERT, dejar que la BD lo genere automáticamente. Error visible en logs: `invalid input syntax for type bigint: "887ba5d8-..."`.
- **RAG-02 ruta absoluta (S37-B):** `_generate_delivery_report` retornaba `report_name` (solo nombre del archivo) en vez de `str(report_path)` (ruta absoluta). `_index_delivery_report` no podía encontrar el archivo. Fix: `return str(report_path)`. Error visible en logs: `RAG-02: error indexando informe de entrega — Ruta no encontrada: ovd-delivery-*.md`.
- **7 tests nuevos** en `test_s37.py`. **754 tests pasan** (0 fallos).
- **Ciclo `474f6d72` — validación exitosa:** Security 100/100, QA 68/100, **Tests 28/28 PASSED** ✅. S36-A (Issues: 10 en vez de 1548) y S36-B (valores float correctos calculados con `round()`) validados en producción.

### Novedades S36 (2026-04-22) — rama `dev`
- **QA Issues: 1548 fix (S36-A):** `QAReviewOutput` ahora tiene `@field_validator("issues", "missing_requirements", "code_quality_issues", mode="before")` que convierte un `str` en `list[str]` partiendo por líneas, sin iterar caracteres. Causa raíz: Pydantic v2 coerciona `str` → `list[str]` iterando char a char cuando el LLM retorna el campo como texto libre.
- **Float test values fix (S36-B):** `system_backend.md` ahora incluye sección "Regla de valores numéricos en tests" con instrucción explícita: NUNCA escribir valores float de memoria, verificar con `round()` antes de escribir el test. Ejemplo: `round(53.4 / 1.70**2, 2)` = `18.48` (no `18.49`). Evita el loop infinito donde tests siempre fallan por valores incorrectos.
- **13 tests nuevos** en `test_s36.py`. **747 tests pasan** (0 fallos).

### Novedades S35 (2026-04-22) — rama `dev`
- **Dashboard persiste proyecto seleccionado (S35):** `FrLauncher.tsx` ahora inicializa `selectedProject` desde `localStorage('ovd_last_project')`. Si no hay valor guardado o el proyecto ya no existe, auto-selecciona el primer proyecto de la lista. Cada cambio de proyecto actualiza localStorage. Evita lanzar ciclos sin `project_id` (lo que causaba `directory=""` y `run_tests` usando tmpdir en vez del workspace real).
- **Warning en API cuando `directory` vacío:** `session_create` loguea un warning explícito cuando `resolved_directory=""` después de todos los lookups. Facilita diagnóstico en logs del engine.
- **Causa raíz documentada:** El ciclo `ef3ebab7` fue lanzado sin seleccionar proyecto → `project_id=""` → lookup DB no ocurrió → `directory=""` → `run_tests` creó tmpdir (`ovd_tests_hqvg00o0`) → "Sin test files encontrados" aunque el agente sí había escrito en el workspace real.

### Novedades S34 (2026-04-22) — rama `dev`
- **Detección de error repetido (S34-A):** `update_test_retry` compara los `AssertionError` del round actual con los del round anterior (via `_extract_assert_errors`). Si el mismo error aparece dos veces, agrega al feedback: "⚠️ MISMO ERROR POR SEGUNDA VEZ — revisa la fórmula matemática desde cero. El valor esperado ES correcto." Evita que el agente haga ajustes superficiales cuando la lógica es fundamentalmente incorrecta.
- **Extracción de bloque de test fallido (S34-B):** `_extract_failed_test_blocks` parsea el output `--tb=long` y extrae hasta 3 bloques `FAILED test_name / def test_... / E   assert X == Y`. El bloque se incluye al inicio del retry_feedback para que el agente vea exactamente qué función se llama y con qué valores, sin buscar en 200 líneas de output.
- **14 tests nuevos** en `test_s34.py`. **734 tests pasan** (0 fallos).

### Fix dashboard GRAPH_NODES (2026-04-22) — rama `dev`
- **Bug:** `request_approval` estaba en posición 7 de `GRAPH_NODES` (después de `run_tests`), pero en el grafo real dispara en posición 3 (después de `generate_sdd`). La lógica `node_end` activa automáticamente el nodo `idx+1`, por lo que cuando el SDD se auto-aprobaba, `generate_docs` aparecía como spinning simultáneamente con `agents`.
- **Fix:** Reordenado `GRAPH_NODES` en `FrLauncher.tsx` para reflejar el flujo real: `generate_sdd → request_approval → route_agents → agents → ... → run_tests → generate_docs → deliver`. Label cambiada de "Aprobación" a "Aprobar SDD" para mayor claridad.

### Novedades S33 (2026-04-22) — rama `dev`
- **`update_test_retry` instrucción no modificar tests (S33-A):** El feedback de retry ahora incluye "⚠️ INSTRUCCIÓN CRÍTICA: Los tests son la especificación correcta y NO deben modificarse. Solo corrige la IMPLEMENTACIÓN (archivos en src/)." — evita que el agente modifique tests en rondas de retry, lo que causaba regresión (más fallos en round 3 que en round 1).
- **`run_tests` extracción de AssertionError (S33-B):** Cuando pytest retorna exit 1 (fallos lógicos), extrae líneas con `AssertionError` y líneas `assert X == Y` del output y las prepende como `[DIAGNÓSTICO S33-B]`. El agente recibe los fallos de aserción exactos al inicio del retry_feedback, no enterrados en 200 líneas de output.
- **`run_tests` --tb=long en retry (S33-C):** El primer round usa `--tb=short` (más compacto). Rondas de retry (`retry_round > 0`) usan `--tb=long` para dar contexto completo del fallo al agente. Mejora el diagnóstico cuando el agente necesita entender la causa raíz de un fallo de aserción.
- **15 tests nuevos** en `test_s33.py`. **720 tests pasan** (0 fallos).

### Novedades S32 (2026-04-22) — rama `dev`
- **`run_tests` pytest target logic refinada (S32-A):** 3 casos según disponibilidad de test files: (1) hay tests nuevos del ciclo → ejecutar solo esos (S31-C); (2) solo hay tests pre-existentes (proyecto real clonado) → ejecutar `work_dir` completo; (3) sin ningún test file → skip graceful `passed=True` con warning. Corrige regresión donde S31-C hacía skip de tests de proyectos reales.
- **`system_backend.md` orden de escritura (S32-B):** Sección de infraestructura obligatoria ahora incluye etiquetas `← PRIMERO / SEGUNDO / TERCERO / CUARTO` y texto explícito "Solo después escribe el código de negocio". Fuerza al agente a escribir `src/<paquete>/__init__.py` antes que cualquier módulo Python.
- **`run_tests` diagnóstico ImportError (S32-C):** Cuando pytest retorna exit 4 (error de colección), extrae líneas con `ImportError`, `ModuleNotFoundError` o `attempted relative import` del output y los prepende como `[DIAGNÓSTICO S32-C]` con instrucción de solución. Este diagnóstico queda en `retry_feedback` para que el agente corrija la estructura en el siguiente round.
- **16 tests nuevos** en `test_s32.py`. **705 tests pasan** (0 fallos). Tests S22 (`timeout`, `runner_not_installed`) actualizados para crear test files reales en tmpdir (requerido por S32-A).

### Novedades S31 (2026-04-22) — rama `dev`
- **Filtro mtime en `qa_review` y `security_audit` (S31-A):** Solo se leen archivos con `mtime >= cycle_start_ts - 5s`. Evita que archivos de ciclos anteriores contaminen el scoring de QA o la auditoría de seguridad en workspaces compartidos.
- **Cap de `retry_feedback` (S31-B):** `update_test_retry` y `update_qa_retry` truncan el feedback acumulado a 3000 caracteres antes de pasarlo al agente. Previene la explosión de contexto (hasta 48K tokens) en la 3ª ronda de reintentos.
- **`run_tests` test isolation por mtime (S31-C):** Cuando `cycle_start_ts` está disponible, pytest recibe como target solo los `test_*.py` con mtime del ciclo actual, no el `work_dir` completo. Evita que pytest recoja tests de ciclos anteriores acumulados en el workspace.
- **9 tests nuevos** en `test_s31.py`. **696 tests pasan** (0 fallos).

### Novedades S30 (2026-04-22) — rama `dev`
- **`write_file` dirname guard (S30-A):** `dir_path = os.path.dirname(abs_path); if dir_path: os.makedirs(dir_path, exist_ok=True)` — evita `FileNotFoundError` cuando el agente escribe un archivo sin directorio (e.g. `"main.py"` sin ruta).
- **Warning en tool failure (S30-B):** `_run_agent_with_tools` captura errores de tool calls y emite `log.warning` con nombre de tool y agente. Facilita diagnóstico sin romper el ciclo.
- **Instrucción de subdirectorios (S30-C):** El `human_content` enviado a cada agente incluye: "IMPORTANTE: Organiza los archivos en subdirectorios apropiados (ej: src/app/components/). NO uses rutas planas sin directorio." Reduce archivos escritos en raíz del workspace.
- **Compresión de mensajes (S30-D):** Loop de tool-calling mantiene solo system + human + últimos 8 mensajes (`_MAX_HIST=8`). Previene acumulación de 48K+ tokens en conversaciones largas con múltiples tool calls.
- **`cycle_start_ts` en estado (S30-E):** `OVDState` incluye `cycle_start_ts: float` inicializado con `time.time()` al crear el ciclo. Usado por S31-A y S31-C para filtrar artefactos por timestamp.
- **11 tests nuevos** en `test_s30.py`. **687 tests pasan** (0 fallos).

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
- Status: S3→S34 completados, próximo: despliegue VPS (C01)
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
