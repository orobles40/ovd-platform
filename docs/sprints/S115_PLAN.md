# Plan S115 — Resiliencia de ciclo y calidad QA en producción

> Basado en: INFORME_S114_PROD_CYCLE.md + investigación oficial LangGraph, DO App Platform, DeepSeek API
> Fecha: 2026-05-07 | Rama: `dev`

---

## Diagnóstico de origen (resumen ejecutivo de investigación)

### Hallazgo 1 — DO App Platform: timeout hard de 100s (Cloudflare)

**Fuente:** Documentación DO + soporte oficial confirmado.

El edge de DO (Cloudflare) aplica un **timeout irremovible de 100 segundos** a todas las conexiones HTTP. No es configurable desde App Platform. El SSE requiere adicionalmente `disable_edge_cache: true` en el app spec (feature liberada agosto 2025) + dominio personalizado (`ovd-platform.codigonet.cloud`). Sin esto, los ciclos que superen los 100s sin actividad se cortan.

**Consecuencia directa para OVD:** El ciclo S114 con 8 tareas y 3 reintentos duró ~15-20 min. El SSE se cortó dos veces. Sin S47, cada corte cancela el grafo.

**Fix requerido:** S47 (background task) + `disable_edge_cache: true` en `.do/app.yaml`.

---

### Hallazgo 2 — LangGraph: `asyncio.create_task` + `asyncio.Queue` es el patrón correcto

**Fuente:** Documentación oficial LangGraph + repositorio `agent-service-toolkit` (JoshuaC215).

El patrón estándar en la comunidad de FastAPI + LangGraph es ejecutar `graph.astream()` dentro del generador SSE directamente (igual que OVD hoy). El patrón de background task con queue separada es menos común pero existe y es el correcto para DO App Platform.

La alternativa nativa es **LangGraph Platform SDK** (`client.runs.create()`) — requiere LangGraph Cloud, no aplica a self-hosted.

El plan S47 existente (`.claude/plans/reflective-scribbling-neumann.md`) es arquitectónicamente correcto: `asyncio.create_task` + `asyncio.Queue(maxsize=2000)` + `asyncio.Event` de fin. **No requiere rediseño, solo implementación.**

---

### Hallazgo 3 — Reflection pattern: critique acumulativo en `messages`

**Fuente:** `langchain-ai/langgraph-reflection` (repositorio oficial).

El patrón de auto-corrección en LangGraph usa dos nodos en loop condicional:
- **generate**: produce output
- **critique**: evalúa con LLM judge separado o linter/parser

La diferencia clave con el retry actual de OVD: **la crítica se acumula en `state["messages"]`**, de modo que el agente siempre ve el historial completo de intentos anteriores y sus problemas. El modelo actual de OVD solo pasa el último error.

Patrón de convergencia documentado: con historial completo, el modelo auto-corrige porque evita reproducir los mismos errores de iteraciones anteriores.

---

### Hallazgo 4 — DeepSeek en DO: límites de output por modelo

**Fuente:** DO GenAI Platform docs + DeepSeek API docs.

| Modelo en DO | Max output tokens | Adecuado para 8 archivos Python |
|---|---|---|
| `deepseek-r1-distill-llama-70b` | **32,768** | Borderline (8 archivos ~20-25K tokens) |
| `deepseek-3.2` | **64,000** | Sí |
| `deepseek-v4-pro` | **1,048,576** | Sí |
| `anthropic-claude-4.6-sonnet` (DO) | ~32K output | Sí |

**Benchmarks SWE-bench** (resolución de issues reales en repos GitHub, el más cercano al caso de uso OVD):
- Claude Sonnet 4.5: **77.2%**
- DeepSeek V3.2: **72-74%**

Claude Sonnet supera a DeepSeek para el tipo de tarea de OVD (implementar código en repos reales con dependencias). Si se usa `deepseek-r1-distill-llama-70b` en producción, el techo de 32K tokens es el cuello de botella directo para 8 archivos.

**Estrategia de prompting probada (SCoT, +13.79% Pass@1):** Structured Chain-of-Thought + explícito orden topológico de dependencias entre archivos.

---

## Fixes del sprint S115

### Fix A — Background graph task [S47] (CRÍTICO)

**Problema:** Grafo corre dentro del generador SSE. Si el cliente desconecta → `GeneratorExit` → LangGraph cancela el grafo.

**Solución:** Plan ya diseñado, solo implementar.

#### A1. Habilitar SSE en DO App Platform

En `.do/app.yaml`, agregar en la sección del engine:

```yaml
# S115-A1: habilitar SSE streaming sin buffer en DO (requiere dominio personalizado)
edge:
  disable_edge_cache: true
```

Requiere que `ovd-platform.codigonet.cloud` esté apuntando al app (D4/D6 del sprint S112 ya configurado).

#### A2. Nuevas estructuras globales en `api.py`

Después de las estructuras de sesión existentes (~línea 65):

```python
# S115-A: background graph execution — grafo independiente del SSE
_graph_tasks: dict[str, asyncio.Task] = {}
_event_queues: dict[str, asyncio.Queue] = {}
_stream_done: dict[str, asyncio.Event] = {}
```

#### A3. Función `_run_graph_background`

```python
async def _run_graph_background(thread_id: str, config: dict) -> None:
    """S115-A: grafo corre independientemente del cliente SSE."""
    queue = _event_queues[thread_id]
    done_ev = _stream_done[thread_id]
    try:
        async with SessionLock(thread_id):
            from task_checkout import register_session, unregister_session
            # Extraer metadata del checkpoint
            session_meta = {"org_id": "", "project_id": "", "feature_request": "", "session_id": ""}
            if _graph:
                try:
                    snap = await _graph.aget_state(config)
                    if snap and snap.values:
                        v = snap.values
                        session_meta = {
                            "org_id": v.get("org_id", ""),
                            "project_id": v.get("project_id", ""),
                            "feature_request": v.get("feature_request", ""),
                            "session_id": v.get("session_id", ""),
                        }
                except Exception:
                    pass
            register_session(thread_id, session_meta)
            current_task = asyncio.current_task()
            if current_task is not None:
                register_task(thread_id, current_task)
            try:
                async with asyncio.timeout(_SSE_STREAM_TIMEOUT):
                    async for event in _stream_graph_events(thread_id, config):
                        await queue.put(event)
            except asyncio.TimeoutError:
                await queue.put(_make_sse_event("error", {
                    "message": f"Timeout global ({_SSE_STREAM_TIMEOUT:.0f}s)",
                    "recoverable": False,
                }))
            finally:
                unregister_session(thread_id)
    except AlreadyRunningError:
        await queue.put(_make_sse_event("error", {"message": "Ciclo ya en ejecución", "recoverable": False}))
    except Exception as exc:
        log.error("S115-A: error fatal thread=%s: %s", thread_id, exc, exc_info=True)
        await queue.put(_make_sse_event("error", {"message": str(exc) or type(exc).__name__, "recoverable": False}))
    finally:
        done_ev.set()
        _graph_tasks.pop(thread_id, None)
        await _ensure_cycle_registered(thread_id, config)  # S115-B
        asyncio.create_task(_deferred_cleanup(thread_id, 600))
```

#### A4. Refactorizar `stream_session`

```python
@app.get("/session/{thread_id}/stream")
async def stream_session(thread_id, request, x_ovd_secret=...):
    verify_secret(x_ovd_secret)
    config = {"configurable": {"thread_id": thread_id}}

    if thread_id not in _event_queues:
        _event_queues[thread_id] = asyncio.Queue(maxsize=2000)
        _stream_done[thread_id] = asyncio.Event()
    queue = _event_queues[thread_id]
    done_ev = _stream_done[thread_id]

    existing = _graph_tasks.get(thread_id)
    if existing is None or existing.done():
        done_ev.clear()
        task = asyncio.create_task(
            _run_graph_background(thread_id, config),
            name=f"ovd_graph_{thread_id[:8]}",
        )
        _graph_tasks[thread_id] = task

    async def event_generator():
        while not (done_ev.is_set() and queue.empty()):
            try:
                event = await asyncio.wait_for(queue.get(), timeout=25.0)
                yield event
            except asyncio.TimeoutError:
                if await request.is_disconnected():
                    log.info("S115-A: cliente SSE desconectado para %s — grafo continúa", thread_id)
                    break
                yield _make_sse_event("heartbeat", {"ts": time.time()})

    return EventSourceResponse(event_generator())
```

**Heartbeat cada 25s:** mantiene la conexión activa dentro del timeout de Cloudflare (100s). El `_SSE_STREAM_TIMEOUT` puede subirse a 30 min sin problema porque el grafo corre en background.

---

### Fix B — Early cycle registration [S47-B] (ALTO)

**Problema:** `ovd_cycles` solo se escribe en `deliver`. Si el ciclo falla antes, el registro queda vacío o inexistente.

#### B1. Migración Alembic

Archivo: `src/engine/migrations/versions/0005_ovd_cycles_status.py`

```python
def upgrade():
    op.execute("""
        ALTER TABLE ovd_cycles 
        ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'started'
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_ovd_cycles_thread_id 
        ON ovd_cycles (thread_id)
    """)
```

#### B2. INSERT en `session_create` (status='started')

En `api.py`, antes del `return JSONResponse(status_code=201)`:

```python
# S115-B: registrar ciclo con status='started' al crear la sesión
try:
    _db_url = os.environ.get("DATABASE_URL", "")
    if _db_url:
        import psycopg
        async with await psycopg.AsyncConnection.connect(_db_url) as conn:
            await conn.execute(
                """INSERT INTO ovd_cycles
                   (id, org_id, project_id, session_id, thread_id, fr_text, auto_approved, status)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,'started')
                   ON CONFLICT (thread_id) DO NOTHING""",
                (str(uuid.uuid4()), body.org_id, body.project_id or None,
                 session_id, thread_id, body.feature_request, body.auto_approve),
            )
            await conn.commit()
except Exception as e:
    log.warning("S115-B: error registrando ciclo started — %s", e)
```

#### B3. UPSERT en `deliver` (status='completed')

En `graph.py`, cambiar el `INSERT INTO ovd_cycles` en el nodo `deliver` a:

```sql
INSERT INTO ovd_cycles (id, org_id, project_id, session_id, thread_id, ...)
VALUES (...)
ON CONFLICT (thread_id) DO UPDATE SET
  fr_analysis = EXCLUDED.fr_analysis,
  sdd = EXCLUDED.sdd,
  agent_results = EXCLUDED.agent_results,
  qa_result = EXCLUDED.qa_result,
  qa_score = EXCLUDED.qa_score,
  complexity = EXCLUDED.complexity,
  fr_type = EXCLUDED.fr_type,
  tokens_input = EXCLUDED.tokens_input,
  tokens_output = EXCLUDED.tokens_output,
  tokens_total = EXCLUDED.tokens_total,
  tokens_by_agent = EXCLUDED.tokens_by_agent,
  cost_usd = EXCLUDED.cost_usd,
  status = 'completed'
```

#### B4. Helper `_ensure_cycle_registered` en `api.py`

```python
async def _ensure_cycle_registered(thread_id: str, config: dict) -> None:
    """S115-B: marcar como 'failed' si deliver no lo completó."""
    try:
        _db_url = os.environ.get("DATABASE_URL", "")
        if not _db_url:
            return
        import psycopg
        async with await psycopg.AsyncConnection.connect(_db_url) as conn:
            cur = await conn.execute(
                "SELECT status FROM ovd_cycles WHERE thread_id = %s", (thread_id,)
            )
            row = await cur.fetchone()
            if row and row[0] == 'completed':
                return  # deliver ya finalizó correctamente
            if _graph:
                snap = await _graph.aget_state(config)
                if snap and snap.values:
                    v = snap.values
                    qa = v.get("qa_result", {})
                    await conn.execute(
                        """UPDATE ovd_cycles SET
                            status = 'failed',
                            fr_analysis = %s,
                            sdd = %s,
                            qa_score = %s,
                            complexity = %s,
                            fr_type = %s
                        WHERE thread_id = %s AND status != 'completed'""",
                        (
                            json.dumps(v.get("fr_analysis", {})),
                            json.dumps(v.get("sdd", {})),
                            qa.get("score", 0) if isinstance(qa, dict) else 0,
                            v.get("fr_analysis", {}).get("complexity", ""),
                            v.get("fr_analysis", {}).get("type", ""),
                            thread_id,
                        ),
                    )
                    await conn.commit()
    except Exception as e:
        log.warning("S115-B: _ensure_cycle_registered error — %s", e)
```

---

### Fix C — Reflection pattern con feedback acumulativo (ALTO)

**Problema:** El retry actual pasa solo el último error. El modelo regenera sin saber qué salió mal en intentos anteriores → divergencia (3→2→4 issues).

**Solución:** Implementar el patrón `langchain-ai/langgraph-reflection` — la crítica se acumula en el historial de mensajes del agente.

#### C1. Modificar estado del grafo

En `graph.py`, agregar al `GraphState`:

```python
qa_feedback_history: list[dict]  # acumula {round, issues, score} por reintento
```

#### C2. Acumular feedback en `qa_review`

En el nodo `qa_review`, antes de emitir el resultado:

```python
# S115-C: acumular historial de QA para el agente en el próximo reintento
feedback_entry = {
    "round": state.get("retry_round", 0),
    "score": qa_score,
    "issues": qa_issues,  # lista de strings con descripción del issue
    "files_with_issues": extract_files_from_issues(qa_issues),  # nuevo helper
}
new_history = state.get("qa_feedback_history", []) + [feedback_entry]
```

#### C3. Inyectar historial en el prompt del agente backend

En `execute_agents` (o en la construcción del `HumanMessage`), cuando `retry_round > 0`:

```python
# S115-C: construir feedback acumulativo para el agente
if retry_round > 0 and qa_feedback_history:
    history_text = "\n".join([
        f"### Intento {h['round']+1} — QA Score: {h['score']}/100\n"
        f"Issues encontrados:\n" +
        "\n".join(f"  - [{h.get('files_with_issues', ['?'])[i] if i < len(h.get('files_with_issues',[])) else '?'}] {issue}"
                  for i, issue in enumerate(h['issues']))
        for h in qa_feedback_history
    ])
    correction_prefix = (
        f"HISTORIAL DE INTENTOS FALLIDOS — CORRÍGELOS TODOS:\n\n{history_text}\n\n"
        f"INSTRUCCIÓN: Al regenerar, verifica que CADA uno de los issues anteriores "
        f"esté resuelto. NO introduzcas nuevos problemas al corregir los existentes."
    )
```

#### C4. Helper `extract_files_from_issues`

```python
def extract_files_from_issues(issues: list[str]) -> list[str]:
    """Extrae nombres de archivo mencionados en los issues QA."""
    import re
    files = []
    for issue in issues:
        matches = re.findall(r'\b(?:src/\S+\.py|\w+\.py)\b', issue)
        files.extend(matches)
    return list(set(files)) or ["(archivo no especificado)"]
```

---

### Fix D — SCoT prompting + orden topológico para multi-archivo (MEDIO)

**Problema:** El agente genera 8 archivos en una sola llamada sin estructura explícita de dependencias → inconsistencias entre archivos.

**Solución:** Structured Chain-of-Thought (SCoT) obligatorio en el prompt del agente backend para FRs con ≥ 4 tareas.

#### D1. Agregar a `system_backend.md` (sección nueva al inicio)

```markdown
### Orden obligatorio de generación para proyectos multi-archivo (S115-D)

Cuando debes generar múltiples archivos interdependientes, SIEMPRE sigue este orden:

1. **models.py** — ORM SQLAlchemy (sin dependencias de otros módulos del proyecto)
2. **schemas.py** — Pydantic BaseModel (importa solo from models si hay from_attributes)
3. **utils/** — funciones puras (validación RUT, helpers) (sin dependencias del proyecto)
4. **services.py** — lógica de negocio (importa models + schemas)
5. **routers/*.py** — endpoints FastAPI (importa services + schemas)
6. **main.py** — app FastAPI + include_router (importa routers)
7. **conftest.py** + **tests/test_*.py** — tests (importa main + schemas)

Antes de generar cada archivo, escribe en un comentario al inicio:
`# Dependencias: [lista de archivos que importa de este proyecto]`

NUNCA generes un archivo que importe de uno que aún no existe en el output.
```

#### D2. Detectar en `execute_agents` y activar SCoT

En el nodo `execute_agents`:

```python
# S115-D: activar SCoT para tareas con ≥4 archivos interdependientes
task_count = len([t for t in sdd_tasks if t.get("agent") == agent_role])
use_scot = task_count >= 4
if use_scot:
    scot_header = (
        "Antes de escribir código, declara el orden topológico de tus archivos "
        "y las dependencias entre ellos. Luego genera cada archivo en ese orden."
    )
```

---

### Fix E — `disable_edge_cache` en `.do/app.yaml` (CRÍTICO para SSE)

**Problema:** Sin esta config, DO/Cloudflare buffer la respuesta SSE completa antes de enviarla → el cliente nunca ve los eventos en tiempo real.

**Cambio en `.do/app.yaml`:**

```yaml
- name: ovd-engine
  source_dir: src/engine
  # ... resto de la config existente ...
  http_port: 8001
  instance_count: 1
  instance_size_slug: professional-xs
  routes:
    - path: /health
    - path: /auth
    - path: /session
    - path: /api/v1/orgs
    # ... rutas existentes ...
  edge:
    disable_edge_cache: true   # S115-E: habilitar SSE streaming sin buffer
```

**Nota:** Requiere dominio personalizado activo. Con `*.ondigitalocean.app` no funciona.

---

### Fix F — Diagnóstico del modelo en producción (MEDIO)

**Problema:** No se sabe si el modelo en producción es `deepseek-r1-distill-llama-70b` (32K output, insuficiente) o `deepseek-v4-pro` (1M output, suficiente).

#### F1. Agregar log del modelo al inicio de cada nodo agente

```python
log.info("S115-F: modelo=%s max_tokens=%s para task=%s", 
         model_name, getattr(llm, 'max_tokens', 'unknown'), task_id)
```

#### F2. Si el modelo actual es R1-distill-70B, migrar a deepseek-v4-pro o claude-4.6-sonnet

En `app.yaml`, cambiar:
```yaml
- name: OVD_AGENT_MODEL
  value: deepseek-v4-pro   # de: deepseek-r1-distill-llama-70b
```

**Evidencia de benchmark:** Claude Sonnet 4.5 → 77.2% SWE-bench vs DeepSeek V3.2 → 72-74%. Para el caso de uso OVD (implementar APIs FastAPI con SQLAlchemy en repos reales), Claude Sonnet tiene ventaja empírica.

---

## Tests requeridos — `src/engine/tests/test_s115.py`

| # | Test | Nodo/función | Valida |
|---|------|------|------|
| 1 | `test_background_task_creates_queue` | `stream_session` | Queue y done_event se crean |
| 2 | `test_background_task_survives_client_disconnect` | `_run_graph_background` | Cancelar `event_generator` no cancela el graph task |
| 3 | `test_heartbeat_emitted_on_timeout` | `event_generator` | Si no hay eventos en 25s → heartbeat |
| 4 | `test_deferred_cleanup_removes_queue` | `_deferred_cleanup` | Queue y done_event se limpian a los N segundos |
| 5 | `test_session_create_inserts_started` | `session_create` | INSERT en `ovd_cycles` con status='started' |
| 6 | `test_ensure_registered_marks_failed` | `_ensure_cycle_registered` | Ciclo no completado → status='failed' |
| 7 | `test_ensure_registered_skips_completed` | `_ensure_cycle_registered` | No sobreescribe ciclo completado |
| 8 | `test_deliver_upserts_completed` | `deliver` | UPSERT actualiza a status='completed' |
| 9 | `test_qa_feedback_history_accumulates` | `qa_review` | `qa_feedback_history` crece por cada ronda |
| 10 | `test_correction_prefix_includes_all_history` | `execute_agents` | HumanMessage contiene issues de todos los intentos |
| 11 | `test_extract_files_from_issues` | `extract_files_from_issues` | Extrae nombres de archivo de texto de issues |
| 12 | `test_scot_activated_for_4_plus_tasks` | `execute_agents` | SCoT header presente cuando task_count ≥ 4 |
| 13 | `test_backend_template_topological_order` | `system_backend.md` | Contiene "models.py", "schemas.py", "services.py" en orden |
| 14 | `test_disable_edge_cache_in_app_yaml` | `.do/app.yaml` | Contiene `disable_edge_cache: true` |

---

## Orden de implementación

```
Fix E  (app.yaml disable_edge_cache)    ← 15 min — sin código, solo config
Fix B1 (migración Alembic)              ← 30 min — schema antes del código
Fix A  (background task api.py)         ← 3h — el cambio principal
Fix B2 (INSERT started)                 ← 30 min — depende de B1
Fix B3 (UPSERT deliver graph.py)        ← 30 min — depende de B1
Fix B4 (_ensure_cycle_registered)       ← 30 min — depende de B1
Fix C  (reflection + feedback history)  ← 2h — graph.py
Fix D  (SCoT prompt + topológico)       ← 1h — template + execute_agents
Fix F  (diagnóstico y migración modelo) ← 30 min — app.yaml + logs
Tests  (test_s115.py)                   ← 2h — al final
```

**Estimado total: ~11h** (2 sesiones de trabajo)

---

## Métricas de éxito

| Métrica | Antes (S114) | Objetivo S115 |
|---|---|---|
| Ciclos que sobreviven SSE drop | 0% | 100% |
| QA score en FR medium (8 tareas) | 0/100 | ≥ 60/100 |
| Ciclos con status registrado en BD | 0% fallidos registrados | 100% |
| Issues QA convergentes en reintento | Divergentes (3→2→4) | Decrecientes (≤ ronda anterior) |
| SSE activo en DO con dominio custom | Sin `disable_edge_cache` | `disable_edge_cache: true` activo |

---

## Deuda técnica complementaria (no bloqueante para S115)

| Item | Descripción | Sprint sugerido |
|---|---|---|
| FR splitter | Detectar FRs con >5 componentes y proponer al usuario dividir | S116 |
| Sub-ciclos secuenciales | Infrastructure phase → Services phase → Routes phase | S116 |
| `status` en dashboard | Mostrar 'started' / 'failed' / 'completed' en lista de ciclos | S116 |
| ADR-004 corrección | Actualizar contradicción Option D vs Option A | S115 (15 min) |
| D4 verify dominio | `curl https://ovd-platform.codigonet.cloud/health` | Inmediato |

---

## Referencias de investigación

| Fuente | Hallazgo clave | URL |
|---|---|---|
| DO App Platform docs | Timeout 100s hard (Cloudflare) | https://docs.digitalocean.com/products/app-platform/ |
| DO Edge Controls | `disable_edge_cache: true` para SSE | https://docs.digitalocean.com/products/app-platform/how-to/configure-edge-settings/ |
| langchain-ai/langgraph-reflection | Critique acumulativo en `messages` | https://github.com/langchain-ai/langgraph-reflection |
| LangGraph interrupts docs | `interrupt()` + `Command(resume=...)` con context dict | https://docs.langchain.com/oss/python/langgraph/interrupts |
| agent-service-toolkit | Patrón FastAPI + SSE + LangGraph (sin background queue) | https://github.com/JoshuaC215/agent-service-toolkit |
| DeepSeek API docs | V4 Pro: 1M output; R1-distill-70B: 32K output | https://api-docs.deepseek.com/ |
| DO GenAI Platform models | deepseek-v4-pro, deepseek-3.2, deepseek-r1-distill-llama-70b | https://docs.digitalocean.com/products/genai-platform/details/models/ |
| SWE-bench 2026 | Claude Sonnet 77.2% vs DeepSeek V3.2 72-74% | https://www.singularitymoments.com/ai-coding-benchmark-swe-bench/ |
| SCoT paper (TOSEM 2025) | +13.79% Pass@1 vs CoT estándar en generación de código | Structured Chain-of-Thought |

---

*Plan S115 generado: 2026-05-07 | Basado en INFORME_S114_PROD_CYCLE.md + investigación oficial*
