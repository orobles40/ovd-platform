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

## Estado actual (2026-04-27)

- **Sprints completados:** S3 → S69 (commit `7c1543630`)
- **Tests:** Python unit ~1221 (suite principal) + integration 14 + docker 5 | Frontend (Vitest) 34 | Rust inline 26 | Total ~1264
- **Rama activa:** `dev` (S69 commiteado, sin mergear a `main`)
- **Próximo foco:** S70-A (session_create → grafo inmediato), S70-C (conftest oracledb mock), S70-B (routers fantasma)
- **Seguridad:** todos los hallazgos corregidos (ver docs/security/SEC-2026-03-28.md)
- **Directorio de entregas dev:** `/Users/omarrobles/Workspace/mis-entregas/contratos-beneficios/`
- **Ciclo de validación S69:** `e3888513` — 6m 54s, QA 95/100, status=completed. S69-A/B validados. src/main.py generado por primera vez. Tests FAIL: `ModuleNotFoundError: oracledb` (diferente al bloqueador S68).
- **Fallos pre-existentes (no regresar):** `test_s31::test_cycle_start_ts_reciente` (flaky), `test_s63b_cleanup_not_in_run_tests` (RuntimeError), `test_alembic_migrations::test_revision_actual_es_head` (timestamp), `test_s39::test_usa_cap_800_en_truncate` (obsoleto por S61-B)

### Novedades S66 (2026-04-27) — rama `dev`

- **S66-A:** `_validate_artifacts_imports()` — escanea archivos en disco para construir mapa `export_name → módulo`. Cuando detecta import fantasma, sugiere corrección exacta: `→ CORRECCIÓN: usa 'from src.auth.utils import validate_rut'`. También lista "MÓDULOS DISPONIBLES EN DISCO" para que el agente sepa qué puede importar sin adivinar.
- **S66-B:** `generate_sdd` — post-procesamiento limita máx 5 tareas/agente. Enforcement en código: si el LLM genera 11 tareas en backend, quedan 5. Registrado en `log.warning` con `backend(11→5)`.
- **S66-C:** `run_tests` — detecta cuando S65-A genera el mismo feedback de imports rotos que el round anterior (líneas 1-3 idénticas). Si `retry_round ≥ 1`: `Command(goto=generate_docs)` directo. Elimina el loop de 34 min del ciclo bc5bcba1.
- **10 tests nuevos** en `test_s66.py`. **1192 tests pasan** en suite completa.

### Novedades S65 (2026-04-27) — rama `dev`

- **S65-A:** `_validate_artifacts_imports()` — `ast.parse()` + `importlib.util.find_spec()` detecta phantom imports ANTES de pytest. Si módulo importado no está en disco ni stdlib ni instalado → retorna `(False, feedback)` y omite pytest.
- **S65-B:** `_validate_orm_patterns()` — detecta `db.add(PydanticModel(...))` en lugar de `db.add(ORMModel(...))`.
- **S65-C:** `_check_fastapi_route_ordering()` — detecta rutas parametrizadas (`{id}`) registradas antes que rutas estáticas con mismo prefijo.
- **S65-D:** `_ensure_auth_dependencies()` — auto-genera `src/auth/dependencies.py` cuando el FR menciona JWT/auth y el archivo no existe.
- **S65-E:** `_ensure_python_infrastructure()` — auto-crea `requirements.txt` si no existe en work_dir después de execute_agents.
- **Ciclo validación bc5bcba1:** 34m 4s, QA=65/100, status=completed. S65-A detectó 7 phantom imports por ronda pero agentes no corrigieron porque feedback no indicaba ruta correcta → corregido en S66-A.

### Novedades S61 (2026-04-26) — rama `dev`

- **S61-A:** `pythonpath = .` (no `src`) en templates `system_backend_python.md` + `system_backend.md`. S27-A skip conftest.py injection cuando `pytest.ini` ya tiene `pythonpath` — evita doble prefijo `src/src/main.py`.
- **S61-B:** `last_test_error: str` en `OVDState` (sin truncar). S60-B usa `last_test_error` en vez de `retry_feedback` (truncado a 800 chars) para detectar errores estructurales repetidos.
- **S61-C:** `qa_review` retorna resultado previo sin llamar al LLM cuando `selective_retry_agents` no vacío. Evita score volátil (95→57→95) en retries selectivos.
- **S61-D:** `_kept_agent_results` en `OVDState`. `route_agents` preserva resultados de agentes no-retried. `deliver` fusiona kept + current — informa todos los agentes (no solo el último retried).
- **13 tests nuevos** en `test_s61.py`. **1138 tests pasan** (2 flaky pre-existentes: `test_s31`, `test_s47`).

### Bug conocido — `ovd_refresh_tokens` columna faltante
- `ALTER TABLE ovd_refresh_tokens ADD COLUMN IF NOT EXISTS revoked_reason TEXT;` — ya aplicado en Docker postgres_db
- Causaba crash del engine cuando el dashboard refrescaba JWT durante execute_agents

### Bug conocido — `ANTHROPIC_API_KEY` con comentario inline en `.env`
- `ANTHROPIC_API_KEY=   # comentario` es leído como valor truthy por el parser de dotenv → context resolver detecta Oracle + API key → routea a Claude → `AuthenticationError 401`
- **Fix:** separar el comentario en línea propia. La API key debe quedar en línea propia sin texto posterior.
- **Inicio del engine:** usar `env ANTHROPIC_API_KEY="" .venv/bin/uvicorn ...` si la shell tiene la variable exportada desde `~/.zshrc`

### Roadmap S52 — Próximo sprint

#### S52-A — Diagnóstico de archivos de producción no escritos (crítico)
- **Síntoma:** directorios `src/calculadora/` y `src/models/` creados pero vacíos tras el ciclo S51. El informe de entrega reporta los archivos pero no están en disco.
- **Fix:** en el S49-C path (y S49-A), si `_write_artifacts` retorna `[]` pero `output` es no-vacío, loguear un `WARNING` con los primeros 500 chars del output para diagnóstico. También añadir verificación post-write: `if not target.exists(): log.error(...)`.
- **Test:** `test_s52.py::TestS52ADiagnostics` — verificar que el warning se emite y que los archivos existen en disco tras `_write_artifacts`.

#### S52-B — Optimización del retry S51-C
- **Síntoma:** S51-C agrega ~3.5 min al ciclo enviando el SDD completo como contexto del retry.
- **Fix:** en el retry S51-C, construir un prompt mínimo: solo el módulo de producción ya escrito + instrucción directa de generar `tests/test_<paquete>.py`. Sin el SDD completo.
- **Impacto esperado:** reducir el retry de ~3.5 min a ~1 min.

#### S52-C — Verificación física en S51-C
- **Síntoma:** S51-C verifica artifacts en memoria pero no en disco. Si los archivos del retry no se escriben al disco, run_tests falla igual.
- **Fix:** después del retry de S51-C, verificar `(Path(directory) / "tests").glob("test_*.py")` físicamente. Si no hay archivos, intentar `_write_artifacts` explícitamente con el output del retry.

#### S52-D — Flush de log para diagnóstico
- **Fix:** agregar `logging.basicConfig(force=True)` con `stream=sys.stdout` y `flush=True` al inicio de `api.py` para asegurar que los `log.info/_write_artifacts` aparezcan en tiempo real en el log del engine.

### Novedades S55 (2026-04-26) — rama `dev`

- **S55-A:** `graph.py` — `_log_runner_response()` cambia `log.info` → `log.warning` para el diagnóstico principal de `done_reason`/`eval_count` y el reporte de fences encontrados. Ahora son visibles en el log del engine sin configuración adicional.
- **S55-B:** `graph.py` — `_write_artifacts()` acepta `preserve_nonempty: bool = False`. Cuando `True`, si un archivo ya existe con contenido y el nuevo contenido está vacío o es <50% del original, se preserva el existente. Activo en paths S49-C y S49-A cuando `retry_feedback` está presente. Previene sobreescritura destructiva en rondas de retry por efecto "Lost in the Middle".
- **S55-C:** `graph.py` — `_build_single_task_sdd_content()` inyecta hint `[S55-C]` con instrucción `round()` cuando la tarea es de tests (keywords: `test`, `pytest`, `unitari`, `spec`). Elimina float literals hardcoded → todos los asserts usan `round(peso / altura**2, 2)`.
- **S55-D:** `graph.py` — `update_test_retry` S54-D cambia `log.info` → `log.warning` para el reporte de archivos en disco antes del retry.
- **11 tests nuevos** en `test_s55.py`. **1051 tests pasan** (1 flaky pre-existente: `test_s31.py::test_cycle_start_ts_reciente`).
- **Resultado ciclo validación S55:** `9d939f29` — **1m 35s** (vs 3m 47s en S54), **pytest exit 0** (primer éxito histórico), 7/7 tests PASS, 30k tokens (vs 120k en S54 = -75%), 0 retries, 4 archivos en disco. Todos los asserts con `round()` — sin float mismatch.

### Novedades S67 (2026-04-27) — rama `dev`

- **S67-B implementado:** `generate_sdd` — cap dinámico por complejidad del FR. `_TASK_CAPS = {low:5, medium:8, high:10, critical:12}`. Confirmado: `backend(15→8)` en ciclo b3de3b92 (high complexity).
- **Ciclo validación S67 (b3de3b92):** 22m 4s, QA 60/100, 12 archivos en disco, 68,763 tokens. Primer ciclo con `directory` correcto → S65-A y S66-A activados.
- **S65-A ✅ VALIDADO:** detectó 10 phantom imports con correcciones exactas (`→ CORRECCIÓN: usa 'from src.auth.utils import validate_rut'`).
- **S66-A ✅ VALIDADO:** lista de módulos disponibles en disco + correcciones por import.
- **S66-C ❌ BUG:** `retry_round=0` en ambas pasadas por `run_tests` → S66-C nunca activa. Fix en S68-A.
- **Bug org_id:** `org_id` correcto es `ORG_OMAR_ROBLES` (no `"omar"`). Curl de prueba corregido en CLAUDE.md.
- **3 bugs críticos para S68:** (A) `retry_round=0` impide S66-C; (B) `retry_feedback` no llega a agentes en retry; (C) `src/database.py` + `src/main.py` no en SDD.
- **Ciclo validación S66 (34f25350):** 2m 10s (**-94% vs S65**), tokens 20k (**-97%**), QA 50/100. S66-B funcionó. `directory=''` porque `org_id` incorrecto.
- **Telemetría acumulada (~51 ciclos):** QA promedio ~55%, 7 ciclos alta calidad (≥80, 14%), costo total $0.

### Novedades S68 (2026-04-27) — rama `dev`

- **S68-A:** `update_test_retry` — `_is_s65a_output` detecta `"[S65-A] IMPORTS ROTOS"` en `test_output` y preserva `last_test_error`. Corrige el bug donde `retry_round` siempre era 0 en S66-C.
- **S68-B:** `_extract_import_corrections()` — extrae líneas `→ CORRECCIÓN:` del feedback S65-A e inyecta al inicio del HumanMessage (antes del SDD). Confirmado en log: 5/5 tareas inyectadas en todas las rondas.
- **S68-C:** `_is_infra_task()` — separa tareas de infraestructura (`src/__init__.py`, `src/database.py`, `src/main.py`, `src/auth/dependencies.py`) del cap de complejidad. En `generate_sdd`: `infra + business[:MAX]`.
- **S68-D:** `system_backend_python.md` — agregadas `format_rut()`, `require_valid_rut()`, regla de almacenamiento RUT en BD, UNIQUE constraint por (org_id, rut_limpio).
- **16 tests nuevos** en `test_s68.py`. **1208 tests pasan** (suite principal).
- **Ciclo validación S68 (33b0ed21):** 7m 49s (-77% vs S65), QA 60/100, tests FAIL. Bloqueador: `src/main.py` nunca generado por el SDD — `from src import app` falla con ImportError.

### Novedades S69 (2026-04-27) — rama `dev`

- **S69-A:** `_ensure_fastapi_main_task()` en `generate_sdd` — inyecta `TASK-INFRA-MAIN` si el FR menciona FastAPI y el LLM no incluyó `src/main.py`. Validado: src/main.py generado por primera vez.
- **S69-B:** `system_sdd.md` — tabla VERIFICACIÓN OBLIGATORIA al inicio del template (posición 0%) con `src/main.py`, `src/database.py`, `src/auth/dependencies.py`. Combate "Lost in the Middle".
- **S69-C:** `_validate_artifacts_imports` — auto-genera `src/main.py` mínimo cuando import roto es `src.main` y el archivo no existe en disco. Incluye `include_router()` para cada `router.py` detectado.
- **13 tests nuevos** en `test_s69.py`. **1221 tests pasan** (suite principal).
- **Ciclo validación S69 (e3888513):** 6m 54s (-12% vs S68), QA 95/100 (+58%), src/main.py generado ✅, sdd_compliance=True. Tests FAIL: `ModuleNotFoundError: oracledb` (nuevo error — ya no es `ImportError src.main`).
- **Nota SSE:** El grafo S47-A solo inicia cuando se conecta al SSE. Sin conexión SSE, el ciclo queda `started`. Fix en S70-A.

### Roadmap S70 — Próximo sprint

#### S70-A — Iniciar grafo en session_create (CRÍTICO)
En `session_create`, después de guardar el checkpoint inicial, disparar `asyncio.create_task(_run_graph_background(thread_id, config))` directamente. Elimina el requisito de SSE para iniciar la ejecución.

#### S70-B — Router detection en _ensure_fastapi_main_task (ALTO)
`src/main.py` importa `router.py` que no existe. En `_ensure_fastapi_main_task`, solo incluir `include_router()` para módulos que tienen `router.py` en el SDD. Si no hay router, usar import directo del service.

#### S70-C — conftest.py con mock oracledb (ALTO)
En `_ensure_python_infrastructure`, si detecta `oracledb` en database.py, crear/actualizar `conftest.py` con:
```python
import sys
from unittest.mock import MagicMock
sys.modules['oracledb'] = MagicMock()
```
Impacto esperado: pytest exit 0 sin Oracle instalado localmente.

#### S70-D — Prohibir auto-import circular (ALTO)
Agregar regla en `system_backend_python.md`: "NUNCA importes desde el mismo módulo que estás escribiendo. Los modelos ORM van en `models.py`, no en `service.py`."

#### S70-E — Consistencia JWT library (MEDIO)
Agregar regla: "Usa una sola librería JWT. Preferir `python-jose[cryptography]`."

#### Ciclo de validación S70

```bash
rm -rf /Users/omarrobles/Workspace/mis-entregas/contratos-beneficios/src/ /Users/omarrobles/Workspace/mis-entregas/contratos-beneficios/tests/
curl -s -X POST http://localhost:8001/session \
  -H "Content-Type: application/json" \
  -d '{
    "org_id": "ORG_OMAR_ROBLES",
    "project_id": "PROJ_CONTRATOS_BENEFICIOS",
    "feature_request": "Sistema de contratos con autenticación JWT usando RUT chileno. API REST FastAPI: login RUT+contraseña, CRUD contratos por empleado, listado de beneficios. PostgreSQL + SQLAlchemy ORM.",
    "auto_approve": true
  }'
```

**Métricas objetivo S70:** duración <8 min, QA ≥95, pytest exit 0, src/main.py ✅, grafo inicia sin SSE.

### Roadmap S69 — COMPLETADO (2026-04-27)

#### S69-A — Post-procesar SDD para inyectar src/main.py (CRÍTICO)

En `generate_sdd`, después del parseo del JSON del LLM:
```python
def _ensure_fastapi_main_task(sdd: dict, fr_analysis: dict) -> dict:
    """S69-A: si el FR menciona FastAPI y no hay tarea para src/main.py, inyectarla."""
    if not any(kw in fr_analysis.get("raw","").lower() for kw in ("fastapi","api rest","endpoint")):
        return sdd
    has_main = any("main.py" in (t.get("file","") + t.get("title","") + t.get("description","")).lower()
                   for t in sdd.get("tasks", []))
    if not has_main:
        sdd["tasks"].insert(0, {
            "id": "TASK-INFRA-MAIN", "agent": "backend",
            "title": "Crear src/main.py con app FastAPI y todos los routers",
            "description": "src/main.py con app = FastAPI(), include_router() para cada módulo del SDD",
            "file": "src/main.py", "depends_on": [], "estimated_complexity": "low"
        })
        log.warning("S69-A: src/main.py inyectado como TASK-INFRA-MAIN")
    return sdd
```

#### S69-B — QA contextual al SDD del ciclo (GAP-S56-A)

QA score 60/100 persistente. El reviewer evalúa con el perfil del proyecto en vez del SDD del ciclo.
Fix: pasar `sdd_json` al template `system_qa.md` como contexto primario.
**Impacto esperado:** QA 60 → 75+.

#### S69-C — Auto-generar src/main.py desde _validate_artifacts_imports

Cuando S65-A detecta `from src.main import app ← módulo no existe` Y `src/main.py` no está en disco → generar un `src/main.py` mínimo con los routers detectados antes de lanzar el retry.

#### Ciclo de validación S69

```bash
rm -rf /Users/omarrobles/Workspace/mis-entregas/contratos-beneficios/src/
curl -s -X POST http://localhost:8001/session \
  -H "Content-Type: application/json" \
  -d '{
    "org_id": "ORG_OMAR_ROBLES",
    "project_id": "PROJ_CONTRATOS_BENEFICIOS",
    "feature_request": "Sistema de contratos con autenticación JWT usando RUT chileno. API REST FastAPI: login RUT+contraseña, CRUD contratos por empleado, listado de beneficios. PostgreSQL + SQLAlchemy ORM.",
    "auto_approve": true
  }'
```

**Métricas objetivo S69:** duración <8 min, QA ≥70, pytest exit 0, src/main.py generado.

### Roadmap S68 — COMPLETADO (2026-04-27)

#### S68-A — Fix retry_round para S66-C (CRÍTICO)
En `run_tests`, usar `last_test_error` para detectar import loop en lugar de `retry_round`:
```python
_retry_round_effective = 1 if "[S65-A] IMPORTS ROTOS" in state.get("last_test_error", "") else retry_round
```

#### S68-B — Propagar retry_feedback a agentes en retry (CRÍTICO)
En `_build_single_task_sdd_content`, si `retry_feedback` contiene `→ CORRECCIÓN:`, inyectarlo al inicio del prompt.

#### S68-C — Tareas infra obligatorias fuera del cap (CRÍTICO)
En `system_sdd.md`: `src/database.py` y `src/main.py` son tareas obligatorias para backend Python, NO cuentan contra el cap de complejidad.

#### S68-D — Completar clean_rut + format_rut en backend_python.md (ALTO)
Agregar implementaciones completas en la tabla de RUTs.

#### Ciclo de validación S68

```bash
rm -rf /Users/omarrobles/Workspace/mis-entregas/contratos-beneficios/src/
curl -s -X POST http://localhost:8001/session \
  -H "Content-Type: application/json" \
  -d '{
    "org_id": "ORG_OMAR_ROBLES",
    "project_id": "PROJ_CONTRATOS_BENEFICIOS",
    "feature_request": "Sistema de contratos con autenticación JWT usando RUT chileno. API REST FastAPI: login RUT+contraseña, CRUD contratos por empleado, listado de beneficios. PostgreSQL + SQLAlchemy ORM.",
    "auto_approve": true
  }'
```

**Métricas objetivo S68:** duración <15 min, QA ≥70, pytest exit 0, S66-C activa.

### Roadmap S67 — COMPLETADO (2026-04-27)

#### Acción inmediata: reiniciar engine con S67-B y lanzar ciclo CORRECTO

```bash
# 1. Limpiar entrega anterior
rm -rf /Users/omarrobles/Workspace/mis-entregas/contratos-beneficios/src/
rm -f  /Users/omarrobles/Workspace/mis-entregas/contratos-beneficios/requirements.txt

# 2. Iniciar engine con S66+S67-B activos
cd /Users/omarrobles/Workspace/Proyectos\ Personales/agente\ de\ terminal/ovd-platform/src/engine
set -a && source <(grep -v '^#' .env | grep '=' | sed 's/ *#.*//') && set +a
env ANTHROPIC_API_KEY="" .venv/bin/uvicorn api:app --port 8001

# 3. Lanzar ciclo — SIEMPRE incluir project_id (sin esto, código va a tmpdir)
SECRET=$(grep OVD_SECRET .env | head -1 | sed 's/.*=//' | tr -d ' \r')
curl -s -X POST http://localhost:8001/session \
  -H "Content-Type: application/json" \
  -H "X-OVD-Secret: $SECRET" \
  -d '{
    "org_id": "ORG_OMAR_ROBLES",
    "project_id": "PROJ_CONTRATOS_BENEFICIOS",
    "feature_request": "Sistema de contratos con autenticación JWT usando RUT chileno. API REST FastAPI: login RUT+contraseña, CRUD contratos por empleado, listado de beneficios. PostgreSQL + SQLAlchemy ORM.",
    "auto_approve": true
  }'
```

#### S67-A — Validar S66-A corrección de imports (crítico)
- **Target:** el agente recibe `→ CORRECCIÓN: usa 'from src.auth.utils import validate_rut'` y en ronda 1 corrige el import. `run_tests` pasa a ejecutar pytest real.
- **Métrica:** ciclo completa sin import loop. QA ≥ 70/100.

#### S67-B — Validar S66-C shortcut (crítico)
- **Target:** si import loop persiste en ronda 1, `Command(goto=generate_docs)` debe disparar. Duración < 20 min (vs 34 min en S65).
- **Métrica:** log muestra `S66-C import loop detectado (ronda=1)`.

#### S67-C — Fix phantom router imports en main.py (alto)
- **Síntoma:** `src/main.py` siempre importa `from src.auth.router import router` y `from src.contracts.router import router` aunque ningún agente genere `router.py`.
- **Fix:** En `system_backend_python.md` agregar regla: "main.py solo importa routers que TÚ generas. Si no hay router.py en el SDD, NO lo importes."
- **Alternativa:** S65-A detecta el phantom en main.py → S66-A sugiere omitirlo.

#### S67-D — Actualizar línea base de ciclos
| Sprint | Ciclo | Duración | QA | Tests | Tokens in |
|--------|-------|----------|----|-------|-----------|
| S55 | `9d939f29` | 1m 35s | 65 | exit 0 | 30k |
| S65 | `bc5bcba1` | 34m 4s | 65 | 0/2 (col. error) | 687k |
| **S67 objetivo** | — | **<20 min** | **≥70** | **exit 0** | **~200k** |

### Roadmap S56 — Próximo sprint

#### S56-A — QA contextualizado al FR del ciclo (crítico)
- **Síntoma:** QA score 65/100 persistente — el reviewer compara código IMC vs SDD del proyecto "contratos" (Oracle + RUT). `sdd_compliance=False` aunque el código implementa correctamente el FR.
- **Fix:** En `qa_review`, pasar el SDD generado en el ciclo como contexto primario, no el perfil del proyecto legacy. El reviewer debe evaluar: ¿el código implementa *este* SDD?
- **Impacto esperado:** QA 65 → 80+, `sdd_compliance=True`.

#### S56-B — log.info → log.warning en nodos de flujo
- **Síntoma:** `run_tests`, `qa_review`, `deliver` logs invisibles en engine log. Solo visibles vía SSE.
- **Fix:** Elevar logs de diagnóstico clave a `log.warning()` o aplicar S52-D (basicConfig force=True nivel INFO).
- **Impacto:** Diagnóstico completo offline sin dashboard.

#### S56-C — Filtrar constraints del proyecto que no aplican al FR
- **Síntoma:** SDD agrega constraints Oracle (`FETCH FIRST`, `python-oracledb thick`) a un FR de IMC puro.
- **Fix:** En `generate_sdd`, filtrar constraints del perfil del proyecto si el FR no menciona BD.

#### S56-D — Reducir tokens por tarea en SDD multi-tarea
- **Síntoma:** `prompt_eval_count` crece de 6062 → 9415 entre tarea 1 y 4 en el mismo ciclo.
- **Fix:** Incluir solo requirements relevantes a cada tarea en `_build_single_task_sdd_content`.
- **Impacto esperado:** -20-30% tokens por tarea en SDDs con >4 tareas.

### Línea base temporal de ciclos

| Sprint | Ciclo | Duración | QA | Tests en disco | run_tests | Tokens in |
|--------|-------|----------|----|----------------|-----------|-----------|
| S48 | — | ~56 min | — | no | skip | — |
| S49 | `232f864e` | 1m 18s | 65 | no | skip | ~156k |
| S50 | `4cf452ca` | 1m 17s | 65 | no | skip | ~156k |
| S51 | `8f04d629` | 5m 04s | 65 | **sí** | **exit 2** | 120k |
| S54 | `4e2f7663` | 3m 47s | 65 | sí | exit 2 | 120k |
| **S55** | `9d939f29` | **1m 35s** | **65** | **sí** | **exit 0** | **30k** |
| S56 objetivo | — | ~1m 20s | **80+** | sí | exit 0 | ~25k |

### Novedades S51 (2026-04-25) — rama `dev`

- **S51-A:** `graph.py` S39-D loop — detección de tarea de tests por keywords (`test`, `pytest`, `spec`, `unitari`). Inyecta `[PRIORIDAD MÁXIMA — S51-A]` al inicio del `task_sdd_content`. El LLM recibe la instrucción antes que cualquier otro contexto.
- **S51-B:** `system_backend.md` — ítem 5 obligatorio en ORDEN DE ESCRITURA: `tests/test_<paquete>.py`. Texto explícito: "PROHIBIDO entregar sin `tests/test_<paquete>.py`."
- **S51-C:** `graph.py` S39-D loop — después de todas las tareas, verifica si el SDD tenía tarea de tests pero ningún `test_*.py` está en `all_artifacts`. Si detecta ausencia, hace un retry automático con `[PRIORIDAD MÁXIMA — S51-C SEGUNDO INTENTO]`. El retry refresca el contexto del proyecto (incluye archivos ya escritos).
- **Fix `.env`:** `ANTHROPIC_API_KEY` separado del comentario inline. Comentario movido a línea propia.
- **11 tests nuevos** en `test_s51.py`. **1040 tests pasan** (0 fallos nuevos; `test_s31.py::test_cycle_start_ts_reciente` flaky pre-existente).
- **Resultado ciclo validación S51:** `8f04d629` — 5m 04s, S51-C disparó, `tests/test_imc.py` generado (8 casos con floats correctos), pytest exit 2 por ImportError (src/ vacío).

### Línea base temporal de ciclos

| Sprint | Ciclo | Duración | QA | Tests en disco | run_tests |
|--------|-------|----------|----|----------------|-----------|
| S48 | — | ~56 min | — | no | skip |
| S49 | `232f864e` | 1m 18s | 65 | no | skip |
| S50 | `4cf452ca` | 1m 17s | 65 | no | skip |
| S51 | `8f04d629` | 5m 04s | 65 | **sí** | **exit 2** |
| S52 | — | objetivo: ~2.5 min | objetivo: 75+ | sí | objetivo: exit 0 |

### Novedades S50 (2026-04-25) — rama `dev`

- **S50-A:** `_run_agent_with_tools` — en los paths S49-A (iter=0, sin tool_calls) y S49-C (Ollama directo), llama `_write_artifacts(output, directory)` si el runner retorna `artifacts=[]` y `output` no vacío. Permite que `run_tests` detecte archivos en disco durante `execute_agents`.
- **S50-B:** `deliver` — deduplicación de artefactos por path con `seen_paths` dict. Elimina duplicados generados por S39-D (N tareas × runner = mismo archivo N veces). S49 reportaba 13 archivos, S50 reporta 4 únicos.
- **S50-C:** `system_backend.md` — sección Pydantic v2 obligatorio con `@field_validator` + `@classmethod`. Marca `@validator` como DEPRECADO. Etiqueta S50-C.
- **S50-D:** `system_backend.md` — regla floats con ejemplos explícitos: `round(65/1.72**2, 2) → 21.97` (no 22.35). Previene valores hardcodeados incorrectos en tests.
- **12 tests nuevos** en `test_s50.py`. **1029 tests pasan** (0 fallos nuevos).
- **Resultado ciclo validación S50:** `4cf452ca` — 1m 17s, 4 archivos únicos, Pydantic v2 respetado, floats correctos, sin tests en disco.

### Novedades S49 (2026-04-25) — rama `dev`

- **S49-A:** `_run_agent_with_tools` — switch inmediato a runner cuando `iter=0` y `tool_calls=[]`. Evita el overhead S30-B (parse markdown) para modelos que nunca usan tools
- **S49-B:** `system_sdd.md` — límite estricto de **5 tareas por agente** (antes 6-7). Justificación explícita: 18 tareas = 56 min, 5 tareas = ~1.5 min
- **S49-C:** Detección de modelos Ollama en `_run_agent_with_tools` via `stack_routing='ollama'` + heurística de nombre de modelo (`_looks_like_ollama_model`). Salta `bind_tools` directamente al runner
- **Helpers nuevos:** `_get_chat_ollama_class()` + `_looks_like_ollama_model()` en `graph.py`
- **Fix tests:** `test_graph_routing.py` + `test_regression_sprint.py` — usar `monkeypatch.setattr(graph, '_SECURITY_MIN_SCORE', 70)` para tests de retry de seguridad (roto por S48-A bypass)
- **15 tests nuevos** en `test_s49.py`. **1017 tests pasan** (0 fallos nuevos)
- **Resultado ciclo validación:** duración **1m 18s** (vs ~56 min en S48), 5 tareas SDD, 12 archivos reales generados, 9/10 tests PASS

### Novedades S48 (2026-04-25) — rama `dev`

- **S48-A:** `security_audit` — bypass completo cuando `OVD_SECURITY_MIN_SCORE=0` (retorna `passed=True, score=100` sin llamar al LLM). Antes tardaba 20+ min antes de timeout
- **S48-B:** `system_sdd.md` — sección "Contrato de interfaces compartidas" para prevenir `ImportError` entre agentes por nombres de clase inconsistentes
- **S48-C:** `_run_agent_with_tools` — log `WARNING` cuando `iter=0` y `tool_calls=[]` (diagnóstico de que qwen3-coder:30b nunca usa tools)
- **S48-D:** `_run_graph_background` — log del nodo de fallo en el bloque `finally`
- **Fix DB:** `ALTER TABLE ovd_refresh_tokens ADD COLUMN IF NOT EXISTS revoked_reason TEXT` — crash del engine durante JWT refresh

### Novedades S47 (2026-04-25) — rama `dev`

- **S47-A:** `api.py` — background `asyncio.Task` para el grafo. El grafo corre independiente del SSE → sobrevive desconexión del cliente
- **S47-B:** Registro temprano de ciclos — `status='started'` al crear sesión, `status='failed'` si muere antes de deliver, `status='completed'` en deliver (UPSERT)
- **Migración BD:** `ALTER TABLE ovd_cycles ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'started'` + `CREATE UNIQUE INDEX ... ON ovd_cycles(thread_id)`

### Novedades S40 (2026-04-23) — rama `dev` (pendiente de commit)

#### S40-templates — Mejoras de calidad en 3 templates
- **S40-A `system_sdd.md`:** Regla explícita: máx 6-7 tareas por agente, prohibición de tareas scaffold-only (con ejemplos ❌/✅), tarea de tests unitarios obligatoria por agente, hooks deben quedar integrados en el SDD
- **S40-B `system_backend.md`:** Nueva sección "Validación de RUT chileno" con implementación de referencia completa (`validate_rut`, `clean_rut`, `format_rut`, `require_valid_rut`), reglas de almacenamiento (sin puntos ni guión), UNIQUE constraint por org_id, casos de test obligatorios
- **S40-C `system_frontend.md`:** Nueva sección "Tests Vitest obligatorios" (estructura `.test.tsx`, mínimo 2 tests por componente) + regla "Hooks — integración obligatoria" (hook sin usar = bug) + nota RUT en UI
- **Documentado en:** `docs/TEMPLATE_IMPROVEMENTS_S40.md`
- **Impacto esperado:** QA score ≥80/100 (era 62), SDD compliance True (era False), test files ≥1 por agente (era 0)

#### Nivel1-E — Fix security bypass (`graph.py`)
- **Bug:** `OVD_SECURITY_MIN_SCORE=0` nunca activaba el bypass porque el código chequeaba `_SECURITY_MIN_SCORE > 0` (0 > 0 = False) → security retry loop siempre se ejecutaba en dev
- **Fix:** Cambiado a `if _SECURITY_MIN_SCORE == 0: passed = True` en `route_after_security_audit`
- **Efecto:** Con `OVD_SECURITY_MIN_SCORE=0` en `.env`, la auditoría de seguridad ya no bloquea ni genera retry loops en dev

#### Ajustes `.env` (dev)
- `OVD_MODEL=qwen3-coder:30b` — tag explícito requerido (bare name `qwen3-coder` no resuelto por Ollama)
- `OVD_SSE_STREAM_TIMEOUT_SECS=3600` — aumentado desde 900s → 1800s → 3600s (ciclos con retry loops duraban >30 min)
- `OVD_NODE_TIMEOUT_SECS=1200` — 1200s por nodo (Nivel1-B)
- `OVD_LLM_TIMEOUT_SECS=1200` — 1200s LLM (Nivel1-B)

#### Ciclos de validación S40 (resultados)
- `a2c87c99` — pre-fix: QA 62/100, SDD compliance False, 0 test files, hooks sin integrar
- `974da8c2` — timeout SSE 900s durante agents
- `d6bac9e5` — timeout SSE 1800s por security retry (Nivel1-E no aplicado aún)
- `128b19c9` — cancelado heartbeat 30min (agente backend colgado en nodo agents)
- **Pendiente:** relanzar ciclo con todos los fixes activos (Nivel1-E + SSE 3600s + S40-templates)

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
