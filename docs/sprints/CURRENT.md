# Sprint activo — S106 (completado) / Validación pendiente

> Última actualización: 2026-05-04 | Rama: `dev`
> Skills Fase 1 implementados: session-start, session-close, run-tests, pre-push

## Estado del ciclo de validación

| Ciclo | Sprint | QA | Duración | Notas |
|-------|--------|----|----------|-------|
| 9b9fd5cb | S104/S105 (engine) | — | — | 1801 unit tests PASS |
| 69ba0b13 | S105 | **40** ❌ | 21m 49s | Naming mismatches + RAG Oracle |
| 078f18ca | S104 | **52** ❌ | 27m 51s | 2 retries |
| d2d92f15 | S103 | **90** ✅ | 10m 4s | 0 retries |

**S106 completado (2026-05-04):**
- P1: Auto-generación schemas Pydantic (Create/Update/Response) en type contract
- P2: Prohibición `validate_rut_format` en template + auto-corrección en disco
- P3: Filtro infra Oracle (`xepdb1`, `:1521`, etc.) en `_strip_db_restrictions()`
- P4: Guard devops en `_fix_sdd_agent_assignments()` — no reasignar sin output_file
- P5: `_calc_naming_mismatch_penalty()` — -2 pts/mismatch en qa_review (S62-B)
- P6: Auto-añadir `list_{entity}s(db: Session)` en type contract para service.py

**Próximo paso:** Ciclo validación S106 — target QA ≥ 80

---

## Roadmap S102

### S102-A — Fix try/except ImportError silencioso en routers (CRÍTICO)

**Problema:** `contracts/router.py` genera `try: from src.contracts.service import ... except ImportError: pass` — silencia el error, endpoints crashean en runtime con NameError.

**Fix:** postprocesador en `code_postprocessor.py` que detecta el patrón y genera un stub mínimo `service.py` con las funciones importadas si el archivo no existe.

```python
def _fix_silent_import_error_router(content: str, work_dir: str, rel_path: str) -> str:
    """S102-A: detecta try/except ImportError silencioso en routers y genera service.py stub."""
    ...
```

**Criterio de aceptación:** `contracts/router.py` sin try/except y `contracts/services.py` stub generado con funciones vacías que retornan 501 Not Implemented.

### S102-B — SDD output_file obligatorio en tasks (ALTO)

**Problema:** SDD genera tasks sin `output_file` → `_fix_sdd_agent_assignments()` (S101-B) no puede inferir agente → frontend/database/devops no se generan.

**Fix A (template):** Agregar a `system_sdd.md`:
```
REGLA OBLIGATORIA (S102-B): Cada task DEBE tener "output_file" con la ruta exacta del archivo.
Ejemplos: "src/components/LoginForm.tsx", "migrations/001_create_tables.sql", "Dockerfile"
```

**Fix B (fallback inferencia por título):** Si `output_file` ausente, `_fix_sdd_agent_assignments()` analiza el campo `id` o `description` para palabras clave (tsx, sql, docker, migrations, components, pages).

**Criterio de aceptación:** ciclo de validación genera agentes frontend + backend (mínimo 2 agentes activados).

### S102-C — Verificación pre-ciclo: reinicio engine (OPERACIONAL)

**Acción inmediata antes del primer ciclo S102:** reiniciar engine para activar S101-C (DATABASE_URL postprocessor).

```bash
# Verificar que el postprocesador está activo
cd src/engine && grep -n "_fix_database_url_hardcoded" code_postprocessor.py
# Reiniciar
pkill -f "uvicorn api:app" && .venv/bin/uvicorn api:app --port 8001
```

### S102-G — Sesión dedicada: corregir 5 fallos pre-existentes (MEDIO)

**Pendiente desde S96-G** — no mezclar con features. Usar `/fix-test [nombre]`.

| Test | Causa | Esfuerzo estimado |
|---|---|---|
| `test_s39::test_usa_cap_800_en_truncate` | Actualizar valor cap a post-S61-B | 15 min |
| `test_s47::test_dispatch_frontend_despacha_pendientes` | Actualizar test a lógica S94 | 30 min |
| `test_s55::test_write_artifacts_overwrites_when_new_content_larger` | Actualizar test a write_artifacts actual | 30 min |
| `test_s63::test_s63b_cleanup_not_in_run_tests` | RuntimeError — coordinar con S96-D | 45 min |
| `test_s31::test_cycle_start_ts_reciente` | Fix timing o marcar con `@pytest.mark.flaky` | 20 min |

---

### S96-H — RAG actualizado: re-indexación incremental + post-ciclo (ALTO)

**Contexto:** El RAG de `ovd-platform` tiene una foto congelada del código (bootstrap puntual, fecha desconocida). Cada sesión de desarrollo modifica `graph.py`, `api.py`, etc. sin que el RAG se actualice. Esto bloquea el escenario futuro donde OVD se desarrolla a sí mismo vía ciclos.

#### H1 — Re-bootstrap inicial (una sola vez)

Ejecutar bootstrap completo para poner el RAG al día con el código actual:

```python
# Vía endpoint existente POST /orgs/{org_id}/knowledge/index
# o directamente via script:
await bootstrap.run(
    org_id="01KMK160F1TJ807Z0BDSJD504D",
    project_id="ovd-platform",
    source_path="src/engine/",
    doc_type="codebase",
)
await bootstrap.run(
    org_id="01KMK160F1TJ807Z0BDSJD504D",
    project_id="ovd-platform",
    source_path="docs/",
    doc_type="doc",
)
```

Antes de re-indexar: limpiar chunks obsoletos de la colección `ovd_project_ovd-platform`.

#### H2 — Post-ciclo: indexar SDD, código generado, errores y métricas

Extender `_index_delivery_report()` en `graph.py` para indexar 4 tipos adicionales al finalizar cada ciclo:

| doc_type | Contenido | Condición |
|---|---|---|
| `sdd` | SDD generado por `generate_sdd` | Siempre |
| `lesson_backend` / `lesson_frontend` / `lesson_database` / `lesson_devops` | Artefactos de código aprobados por agente | Solo si `qa_score >= 70` |
| `lesson_general` | Errores de pytest + fix aplicado en reintentos | Si hubo ≥1 reintento |
| `cycle_metrics` | JSON: qa_score, duración, stack, fr_type, complejidad, agentes fallidos | Siempre |

#### H3 — Re-indexación incremental en session-close

Agregar **Paso 9** al skill `session-close`: re-indexar solo los archivos de `src/engine/` y `docs/` modificados en la sesión actual.

```bash
# Obtener archivos .py y .md modificados desde el último commit
git diff --name-only HEAD | grep -E "^src/engine/.*\.py$|^docs/.*\.md$"
```

Por cada archivo modificado → llamar al endpoint `/orgs/{org_id}/knowledge/index` con ese archivo específico (no re-bootstrap completo).

**Impacto:** el RAG refleja el estado real del proyecto después de cada sesión, sin costo de re-indexación total.

---

### S96-I — Base de conocimiento externa: repos de referencia (BAJO)

Clonar repos seleccionados en `src/knowledge/external/` para consulta directa durante sesiones de desarrollo. **No se indexan en pgvector.**

**Propósito:** antes de diseñar una solución a un problema en OVD, buscar si ya fue resuelto en alguno de estos repos y cómo lo implementaron. Claude Code hace `grep` o lectura directa cuando enfrenta un issue.

**Mantenimiento:** `git pull` manual cuando se detecte contenido nuevo relevante. Sin fecha fija. Se puede eliminar cualquier repo con `rm -rf` sin impacto en el engine.

---

#### Categoría 1 — Metodología y skills

| Repo | GitHub | Qué aporta |
|---|---|---|
| `superpowers` | `obra/superpowers` | ya existe en `superpowers-upstream/` — sincronizar |
| `hermes-agent` | `NousResearch/hermes-agent` | ~500 skills, FastMCP/FastAPI templates, web design systems |

Directorios útiles de hermes-agent: `optional-skills/mcp/fastmcp/`, `skills/creative/popular-web-designs/`, `skills/github/`, `skills/software-development/`, `optional-skills/mlops/`

---

#### Categoría 2 — AI Coding Agents (referencia arquitectural)

| Repo | GitHub | Lenguaje | Qué aporta |
|---|---|---|---|
| `opencode` | `anomalyco/opencode` | TypeScript | CLI agent más cercano a Claude Code — tool use, session mgmt, MCP, TUI |
| `aider` | `Aider-AI/aider` | Python | repo-map con tree-sitter, edit formats (diff/whole), git workflow profundo |
| `OpenHands` | `OpenHands/OpenHands` | Python | multi-agent con sandbox Docker, browser automation, SWE-bench eval |
| `SWE-agent` | `SWE-agent/SWE-agent` | Python | AgentComputer Interface (ACI), fix automático de issues GitHub |
| `cline` | `cline/cline` | TypeScript | VSCode extension, tool use step-by-step con aprobación usuario |
| `codex` | `openai/codex` | Rust | coding agent minimalista en Rust, sandbox, referencia de diseño ligero |

---

#### Categoría 3 — Frameworks multi-agente

| Repo | GitHub | Lenguaje | Qué aporta |
|---|---|---|---|
| `langgraph` | `langchain-ai/langgraph` | Python | el framework que usa OVD — ejemplos oficiales, patterns de estado |
| `autogen` | `microsoft/autogen` | Python | orquestación multi-agente conversacional, human-in-the-loop |

---

#### Categoría 4 — Stack técnico del engine

| Repo | GitHub | Lenguaje | Qué aporta |
|---|---|---|---|
| `litellm` | `BerriAI/litellm` | Python | router multi-LLM con fallbacks — comparable a `model_router.py` |
| `pydantic-ai` | `pydantic/pydantic-ai` | Python | agentes con validación de tipos estricta — mejoras a OVDState |
| `full-stack-fastapi-template` | `tiangolo/full-stack-fastapi-template` | Python/TS | template oficial FastAPI + PostgreSQL + React — referencia directa para código generado |

---

## Ciclo de validación S102

```bash
# Antes del ciclo: reiniciar engine para activar S101-C
pkill -f "uvicorn api:app" 2>/dev/null; cd src/engine && .venv/bin/uvicorn api:app --port 8001 &

# Limpiar entrega anterior
rm -rf /Users/omarrobles/Workspace/mis-entregas/contratos-beneficios/src/ \
       /Users/omarrobles/Workspace/mis-entregas/contratos-beneficios/tests/ \
       /Users/omarrobles/Workspace/mis-entregas/contratos-beneficios/conftest.py \
       /Users/omarrobles/Workspace/mis-entregas/contratos-beneficios/pytest.ini \
       /Users/omarrobles/Workspace/mis-entregas/contratos-beneficios/requirements.txt

SECRET=$(grep '^OVD_SECRET=' src/engine/.env | head -1 | sed 's/.*=//' | tr -d ' \r')
curl -s -X POST http://localhost:8001/session \
  -H "Content-Type: application/json" \
  -H "X-OVD-Secret: $SECRET" \
  -d @/Users/omarrobles/Workspace/mis-entregas/PLAN_PRUEBA_OVD.md
```

**Métricas objetivo S102:**
- ≥ 2 agentes activados (backend + frontend mínimo)
- DATABASE_URL via env (no hardcodeada) — S101-C activo
- contracts/router.py sin try/except silencioso — S102-A activo
- QA ≥ 85 (consolidar S101)

---

## Issues abiertos

| Issue | Descripción | Estado | Sprint |
|-------|-------------|--------|--------|
| SDD tasks sin output_file | Frontend no se genera, S101-B inefectivo | **PRIORITARIO** | S102-B |
| contracts/service.py faltante | router.py silencia ImportError | **PRIORITARIO** | S102-A |
| DATABASE_URL hardcodeada | S101-C no activó (engine sin reiniciar) | Pendiente | S102-C |
| test_s63b regresión | `test_s63b_cleanup_in_retry_round_zero` roto por S94-fix | Pendiente | S102-G |

## Fallos pre-existentes — pendientes de corrección en S96-G

> Estos fallos tienen sesión dedicada asignada (S96-G). No son permanentes.
> Usar `/fix-test [nombre]` con contexto precargado.

| Test | Causa | Prioridad |
|---|---|---|
| `test_s31::test_cycle_start_ts_reciente` | Flaky por timing | Media |
| `test_s39::test_usa_cap_800_en_truncate` | Cap obsoleto desde S61-B | Alta (fácil) |
| `test_s47::test_dispatch_frontend_despacha_pendientes` | Roto por S94-fix | Alta |
| `test_s55::test_write_artifacts_overwrites_when_new_content_larger` | write_artifacts cambió post-S55 | Alta |
| `test_s63::test_s63b_cleanup_not_in_run_tests` | RuntimeError por S94-fix | Alta |

## Skills Claude Code

| Fase | Skills | Estado | Fecha |
|---|---|---|---|
| Fase 1 | session-start, session-close, run-tests, pre-push | ✅ Implementados | 2026-04-28 |
| Fase 2 | tdd-cycle, tdd-green, cycle-debug, fix-test | ⏳ Evaluar en 2026-05-12 | — |

> **Nota:** Evaluar impacto de Fase 1 el **2026-05-12** (2 semanas). Si los 4 skills reducen
> fricción mediblemente, proceder con Fase 2. Criterio: ¿sesiones inician más rápido?
> ¿CI falla menos post-push? ¿CONTEXT.md se mantiene actualizado?
