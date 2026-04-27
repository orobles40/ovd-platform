# Roadmap S60 — Plan con fundamentos técnicos

**Fecha:** 2026-04-26  
**Sprint anterior:** S59 (ciclo `16fdee79` validado — dispatch_frontend ✅, tests FAIL ❌)  
**Objetivo S60:** Ciclo complejo < 10 min, pytest exit 0, QA ≥ 80/100

---

## Resumen de problemas a resolver

| ID | Problema | Impacto medido | Prioridad |
|----|----------|----------------|-----------|
| S60-A | `ModuleNotFoundError: No module named 'src.main'` | +11min (3 rondas × 9 tareas) | CRÍTICO |
| S56-A | QA persistente 65/100 por comparar contra SDD incorrecto | Score subóptimo, sdd_compliance=False | ALTO |
| S60-B | S53-B retries agente completo para error estructural | +11min de retries inútiles | ALTO |
| S60-C | S42-B cleanup elimina archivos que no se regeneran | deliver sin archivos backend | MEDIO |
| S59-C | SSE sin Last-Event-ID → gap visual en reconexión | UX degradado | BAJO |

---

## S60-A — Fix `ModuleNotFoundError: No module named 'src.main'` (CRÍTICO)

### Diagnóstico

El ciclo `16fdee79` falló en pytest exit 2 las 3 rondas:

```
tests/test_auth.py:4: in <module>
    from src.main import app
E   ModuleNotFoundError: No module named 'src.main'
```

El agente backend generó `src/auth/main.py` y `src/contracts/main.py` como entry points separados por módulo, siguiendo el patrón natural de FastAPI con múltiples routers. Los tests generados importaron `from src.main import app`, que es correcto para una aplicación FastAPI con punto de entrada único — pero ese archivo no existe.

El problema tiene dos dimensiones:
1. **El template `system_backend.md` no prescribe un entry point unificado.** El agente infiere la estructura a partir del SDD sin guía explícita.
2. **`pytest.ini` no configura `pythonpath = src` ni `importmode = importlib`**, por lo que el resolver de imports falla antes de ejecutar un solo test.

### Fundamento técnico

**FastAPI — documentación oficial ([fastapi.tiangolo.com](https://fastapi.tiangolo.com/tutorial/bigger-applications/)):**

> "You can use an APIRouter the same way you would use a FastAPI class. [...] you'll import it and create a 'router' [...] The main app would then include those routers."

El patrón canónico de FastAPI para aplicaciones multi-módulo es:

```python
# src/auth/router.py
from fastapi import APIRouter
router = APIRouter()

# src/contracts/router.py
from fastapi import APIRouter
router = APIRouter()

# src/main.py  ← ENTRY POINT ÚNICO
from fastapi import FastAPI
from src.auth.router import router as auth_router
from src.contracts.router import router as contracts_router

app = FastAPI()
app.include_router(auth_router, prefix="/auth")
app.include_router(contracts_router, prefix="/contracts")
```

Sin `src/main.py`, `uvicorn src.main:app` y `from src.main import app` en tests son imposibles.

**pytest — documentación oficial ([docs.pytest.org](https://docs.pytest.org/en/stable/explanation/pythonpath.html)):**

> "`importmode=importlib` [...] This mode does not require `__init__.py` files [...] and is the recommended mode."
> "`pythonpath` [...] List of paths that should be added to `sys.path`. Paths are relative to `rootdir`."

Con `pytest.ini`:
```ini
[pytest]
pythonpath = src
importmode = importlib
```

Los tests pueden escribir `from auth.router import router` o `from main import app` directamente, sin `sys.path.insert` en `conftest.py`.

**qwen3-coder — few-shot es más efectivo que reglas abstractas:**

El modelo de 30B entiende mejor ejemplos concretos que instrucciones negativas. La instrucción "crea un entry point unificado" es menos efectiva que mostrar el patrón completo con los tres archivos involucrados.

### Fix propuesto

**Archivo 1: `src/engine/templates/system_backend.md`**

Agregar sección obligatoria después del bloque "Formato de salida":

```markdown
## Estructura obligatoria para proyectos FastAPI multi-módulo [S60-A]

Cuando el SDD define múltiples módulos (auth, contracts, users, etc.),
DEBES generar los siguientes archivos en ESTE ORDEN:

**PASO 1 — Entry point unificado (OBLIGATORIO):**
```python:src/main.py
from fastapi import FastAPI
from src.auth.router import router as auth_router
from src.contracts.router import router as contracts_router
# Agrega aquí todos los routers del SDD

app = FastAPI(title="OVD API")
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(contracts_router, prefix="/contracts", tags=["contracts"])
```

**PASO 2 — Cada módulo exporta APIRouter (NO FastAPI):**
```python:src/auth/router.py
from fastapi import APIRouter
router = APIRouter()

@router.post("/login")
async def login(...):
    ...
```

**PASO 3 — pytest.ini en la raíz (OBLIGATORIO):**
```ini:pytest.ini
[pytest]
pythonpath = src
addopts = --import-mode=importlib
testpaths = tests
```

**PASO 4 — Tests importan desde src.main:**
```python:tests/test_auth.py
from src.main import app
from fastapi.testclient import TestClient
client = TestClient(app)
```

> ❌ PROHIBIDO: exportar `app = FastAPI()` desde módulos individuales (`src/auth/main.py`).  
> ✅ CORRECTO: un único `app` en `src/main.py` que registra todos los routers.
```

**Archivo 2: `src/engine/templates/system_backend_python.md`** (stack overlay)

Agregar la misma sección S60-A para que `render_composed()` la incluya en el contexto del agente cuando el stack es Python/FastAPI.

### Impacto esperado

- Elimina 100% del tiempo de retry por `ModuleNotFoundError` (~11min en el ciclo S59)
- `pytest.ini` con `pythonpath = src` + `importmode = importlib` evita `sys.path` manual en `conftest.py`
- El patrón few-shot es entendible por qwen3-coder:30b en la primera iteración

---

## S56-A — QA contextual al ciclo (ALTO)

### Diagnóstico

QA retornó 65/100 en las 3 rondas del ciclo `16fdee79` con `sdd_compliance=False`, a pesar de que el código sí implementaba el FR (sistema de contratos + autenticación). El reviewer marcó como ausentes lógicas de Oracle/RUT que no pertenecen al feature request del ciclo.

El problema es arquitectónico en `qa_review`:

```python
# graph.py línea ~2754
human_content = (
    _build_qa_sdd_block(state["sdd"])  # S56-A: requirements del ciclo
    + "\n\n" + agent_output_block
)
```

Pero en `template_loader.render("system_qa", project_context=project_ctx)`:

```
# system_qa.md línea 64
{project_context}
```

El `project_context` es el perfil del proyecto (Oracle, RUT, restricciones legacy) que se inyecta en el **SystemMessage**. El revisor recibe instrucción del sistema con restricciones que no aplican, y luego en el HumanMessage ve un SDD diferente. La instrucción S56-A en el template dice "evalúa SOLO los requisitos del SDD", pero el contexto del proyecto en SystemMessage contamina el frame de evaluación del LLM.

### Fundamento técnico

**PRE — Pointwise Rubric Evaluation ([Zheng et al., 2023](https://arxiv.org/abs/2306.05685)):**

Investigación sobre evaluación con LLMs muestra que el enfoque de **Evaluación por Rúbrica Puntual** (evaluar cada requisito individualmente con pregunta sí/no) logra 85% de alineación con evaluadores humanos, versus 65-70% con evaluación de bloque único donde el LLM genera un score global.

El patrón PRE aplicado a QA de código:
```
Para REQ-001: "¿El endpoint POST /auth/login retorna JWT con claims org_id y role?"
  → Sí (1pt) / No (0pt) / Parcial (0.5pt)
Para REQ-002: "¿El endpoint valida formato de RUT chileno antes de procesar?"
  → Sí / No / Parcial
Score = (suma de puntos / total requisitos) × 100
```

**Arquitectura de prompts — instrucciones al inicio:**

La investigación sobre LLMs ([Liu et al., 2023 "Lost in the Middle"](https://arxiv.org/abs/2307.03172)) muestra que las instrucciones son más efectivas cuando aparecen al **inicio** del contexto, no al final. El SDD del ciclo actual debe estar antes del `project_context` en el prompt del revisor.

**LangGraph / separación de contextos:**

El estado `OVDState` ya contiene `state["sdd"]` (el SDD del ciclo) y `state.get("project_context")` (el perfil del proyecto). Son objetos distintos. La QA debe usar primero el SDD del ciclo como referencia primaria.

### Fix propuesto

**Archivo: `src/engine/graph.py` — función `qa_review`**

Cambio en la construcción del SystemMessage. En lugar de pasar `project_context` directamente al template, pasar una versión filtrada que excluye restricciones de BD que no aplican al FR actual:

```python
# ANTES (línea ~2720):
system_content = template_loader.render("system_qa", project_context=project_ctx)

# DESPUÉS S56-A-fix:
# Separar contexto de proyecto del SDD del ciclo
# El SDD del ciclo va primero en el SystemMessage como referencia primaria
sdd_for_qa = _build_qa_sdd_block(state.get("sdd", {}))
project_ctx_filtered = _strip_db_restrictions(project_ctx)  # ya existe S56-C

system_content = template_loader.render(
    "system_qa",
    project_context=project_ctx_filtered,
    cycle_sdd_context=sdd_for_qa,  # nuevo parámetro
)
```

**Archivo: `src/engine/templates/system_qa.md`**

Mover el bloque de evaluación del SDD al inicio del SystemMessage (antes de `{project_context}`), y agregar evaluación por requisito:

```markdown
## Requisitos del ciclo actual a evaluar [S56-A] (referencia primaria)

{cycle_sdd_context}

---

Evalúa CADA requisito listado arriba de forma individual con escala:
- **✅ Implementado** (1.0): la funcionalidad está completa y cumple el criterio de aceptación
- **⚠️ Parcial** (0.5): existe pero incompleto o con limitaciones
- **❌ Ausente** (0.0): no hay implementación del requisito

Score final = (suma de puntos / total requisitos) × 100

RESTRICCIÓN ABSOLUTA: No evalúes requisitos de Oracle, RUT, ni infraestructura
que NO aparezcan en la lista de requisitos del ciclo arriba.

---

{project_context}
```

**`_build_qa_sdd_block` ya existe** en `graph.py` (línea 2639). Solo requiere moverlo al SystemMessage en lugar del HumanMessage.

### Impacto esperado

- QA score 65 → 80+ (estimado basado en PRE: evaluación por requisito elimina penalizaciones por contexto incorrecto)
- `sdd_compliance=True` en ciclos donde el código implementa correctamente el SDD del ciclo
- El `project_context` del perfil legacy queda como contexto secundario, no como marco de evaluación primario

---

## S60-B — No retry para errores estructurales (ALTO)

### Diagnóstico

El ciclo `16fdee79` ejecutó S53-B tres veces:
- Ronda 1: backend 9 tareas (~4min) → FAIL exit 2 `ModuleNotFoundError`
- Ronda 2: backend 9 tareas (~4min) → FAIL exit 2 `ModuleNotFoundError` (mismo error)
- Ronda 3: backend 9 tareas (~7min) → FAIL exit 2 `ModuleNotFoundError` (mismo error)

Total: ~11min 24s desperdiciados. El error `ModuleNotFoundError: No module named 'src.main'` es **estructural**: no cambia entre rondas porque el agente sigue generando la misma estructura de módulos separados, dado que el template no prescribe un entry point unificado.

S53-B tiene lógica de detección del agente fallido en `_infer_failing_agent_from_test_output()` (línea 3323), pero no detecta si el error es **no-retryable** (mismo error en rondas consecutivas).

S34-A ya detecta errores repetidos (`_extract_assert_errors`), pero solo para `AssertionError`, no para `ModuleNotFoundError` de exit 2.

### Fundamento técnico

**LangGraph — `RetryPolicy` nativa:**

```python
from langgraph.pregel import RetryPolicy

# RetryPolicy retries solo el nodo fallido, no el grafo completo
# retry_on permite filtrar qué excepciones merecen retry
RetryPolicy(
    max_attempts=3,
    retry_on=(TransientError,),  # NO retries para StructuralError
    backoff_factor=2.0,
)
```

El concepto clave es que `RetryPolicy` permite discriminar por tipo de excepción. Aplicado a nuestro caso: si el error es de collection (exit 2, ImportError/ModuleNotFoundError sin cambio entre rondas), no hay ninguna razón para re-ejecutar el agente.

**Patrón "fail fast" en sistemas de CI:**

La práctica estándar en CI/CD (GitHub Actions, CircleCI) es **fallar inmediatamente** cuando se detecta un error de configuración que no puede resolverse sin intervención humana. Un `ModuleNotFoundError` en pytest es análogo a un error de compilación: no se resuelve con más intentos del mismo código.

**Evidencia del ciclo S59:**

El mismo error aparece idéntico en las 3 rondas:
```
E   ModuleNotFoundError: No module named 'src.main'
```
El agente backend recibió el diagnóstico S57-B en `retry_feedback` pero generó la misma estructura en el retry, porque el template no le dice cómo resolver el problema estructural.

### Fix propuesto

**Archivo: `src/engine/graph.py` — función `update_test_retry`**

Agregar detección de errores no-retryables antes de la lógica S53-B existente:

```python
def update_test_retry(state: OVDState) -> dict:
    tr = state.get("test_result", {})
    test_output = tr.get("output", "")
    rc = tr.get("return_code", 0)

    # S60-B: detectar error estructural no-retryable
    # exit 2 = pytest interrumpido (collection error)
    # mismo ModuleNotFoundError en rondas consecutivas = no hay solución sin fix de template
    _is_structural_error = (
        rc == 2
        and ("ModuleNotFoundError" in test_output or "ImportError" in test_output)
        and "collected 0 items" in test_output
    )

    _prev_output = state.get("retry_feedback", "")
    _same_error_repeated = (
        _is_structural_error
        and "ModuleNotFoundError" in _prev_output  # mismo error en ronda anterior
    )

    if _same_error_repeated:
        log.warning(
            "update_test_retry: S60-B error estructural repetido (exit %d) — "
            "omitiendo retry, pasando a deliver directamente. Error: %s",
            rc,
            [l for l in test_output.splitlines() if "ModuleNotFoundError" in l][:2],
        )
        return {
            "test_retry_count": _MAX_TEST_RETRIES,  # marca como agotado
            "retry_feedback": _prev_output,
            "selective_retry_agents": [],
            "status": "structural_error_no_retry",
            "messages": state.get("messages", []) + [{
                "role": "agent",
                "content": (
                    "S60-B: Error estructural de imports — no retryable. "
                    "El error persiste entre rondas. Pasando a deliver con diagnóstico."
                ),
            }],
        }

    # ... resto de la lógica existente de update_test_retry ...
```

**Condición para saltar retry:** `_same_error_repeated` requiere que el mismo tipo de error aparezca en **dos rondas consecutivas**. La primera ronda puede intentar el retry (el agente podría corregirlo si el template le da guía correcta). Solo si repite en la segunda ronda se cancela.

### Impacto esperado

Con S60-A aplicado, S60-B no debería dispararse (el template corrige la estructura en la primera ronda). S60-B es la red de seguridad para casos donde el agente genera estructura incorrecta a pesar del template.

- Elimina rondas 2 y 3 de retry cuando el error structural no cambia: -7min en el peor caso
- El ciclo entrega con diagnóstico en lugar de desperdiciar tokens en retries inútiles

---

## S60-C — S42-B cleanup condicional (MEDIO)

### Diagnóstico

S42-B (`run_tests`, línea ~3270) elimina todos los archivos del workspace con `mtime >= cycle_start_ts - 5s` antes del retry. En el ciclo `16fdee79`:

1. Backend genera: `src/auth/models.py`, `src/auth/service.py`, `src/auth/main.py`, `src/contracts/...`
2. S42-B elimina todos esos archivos antes del retry
3. El retry re-ejecuta backend con 9 tareas
4. El retry regenera los archivos, pero con **estructura diferente** (varía entre rondas)
5. En el deliver final, los archivos de producción del backend **no están en disco** porque S42-B los eliminó y no todos se regeneraron

El informe `INFORME_PRUEBA_S59.md` reporta: "S42-B cleanup elimina los archivos backend antes del retry. El retry los reescribe, pero en la entrega final el cleanup los eliminó antes del `deliver`. Solo 5 artefactos únicos reportados."

### Fundamento técnico

**Principio de cleanup quirúrgico:**

El objetivo de S42-B es dar al agente un workspace limpio para el retry, evitando que el agente asuma que su output anterior es válido. Pero eliminar **todos** los archivos del ciclo es demasiado agresivo cuando:
- El agente de frontend escribió archivos que NO causaron el error de tests
- Los archivos de database (migrations) son independientes del error de imports en backend

El cleanup debe ser **selectivo**: eliminar solo los archivos que el retry va a regenerar, no los de otros agentes.

**LangGraph state: `selective_retry_agents`**

S53-B ya calcula `selective_retry_agents` — la lista de agentes que se van a re-ejecutar. Esta información está disponible en el estado al momento de cleanup.

### Fix propuesto

**Archivo: `src/engine/graph.py` — función `_cleanup_workspace_before_retry`** (nueva, reemplaza la lógica inline de S42-B en `run_tests`)

```python
def _cleanup_workspace_before_retry(
    work_dir: str,
    cycle_start_ts: float,
    agents_to_retry: list[str],
    sdd: dict,
) -> list[str]:
    """S60-C: elimina solo archivos que el retry regenerará.
    
    En vez de borrar todos los archivos del ciclo, determina qué paths
    pertenecen a cada agente según el SDD y solo limpia esos.
    """
    # Construir conjunto de paths que el retry regenerará
    paths_to_clean: set[str] = set()
    tasks = sdd.get("tasks", [])
    for task in tasks:
        if task.get("agent") in agents_to_retry:
            for artifact in task.get("artifacts", []):
                paths_to_clean.add(artifact.get("path", ""))

    base = pathlib.Path(work_dir)
    removed: list[str] = []
    for fp in list(base.rglob("*")):
        if not fp.is_file():
            continue
        rel = str(fp.relative_to(base))
        # Solo eliminar si: (1) el retry lo regenerará O (2) es un test file de agente en retry
        will_be_regenerated = any(rel.startswith(p.lstrip("/")) for p in paths_to_clean if p)
        is_test_of_retry_agent = (
            fp.name.startswith("test_") and fp.suffix == ".py"
            and "backend" in agents_to_retry  # los tests del backend causaron el error
        )
        if not (will_be_regenerated or is_test_of_retry_agent):
            continue
        try:
            mtime = fp.stat().st_mtime
        except OSError:
            continue
        if mtime >= cycle_start_ts - 5:
            try:
                fp.unlink()
                removed.append(rel)
            except OSError:
                pass

    if removed:
        log.info(
            "run_tests: S60-C cleanup quirúrgico — eliminados %d archivo(s) "
            "(solo paths de agentes %s): %s",
            len(removed), agents_to_retry, removed[:10],
        )
    return removed
```

### Impacto esperado

- Archivos de frontend y database sobreviven al cleanup aunque haya retry de backend
- `deliver` reporta todos los artefactos del ciclo, no solo los del último retry
- Menos trabajo de regeneración para el agente en el retry (solo regenera lo que realmente falló)

---

## S59-C — SSE Last-Event-ID replay (BAJO)

### Diagnóstico

Cuando el browser reconecta el SSE (S47-A ya soporta esto), el cliente no recibe los eventos emitidos durante la desconexión. El dashboard muestra un gap: el estado visual salta desde el punto de desconexión al estado actual.

### Fundamento técnico

**SSE — especificación W3C ([html.spec.whatwg.org](https://html.spec.whatwg.org/multipage/server-sent-events.html)):**

> "If the event source's last event ID string is not the empty string, then [...] the user agent will include a `Last-Event-ID` HTTP header in the reconnection request."

El protocolo SSE nativo soporta replay: si el servidor emite `id: <n>` en cada evento, el browser envía `Last-Event-ID: <n>` al reconectar, y el servidor puede emitir los eventos perdidos.

**Implementación con `asyncio.Queue`:**

La arquitectura S47-A ya usa `_event_queues: dict[str, asyncio.Queue]`. Para soportar replay, se puede mantener un buffer secundario (`_event_buffers: dict[str, list]`) que almacene los últimos N eventos con su ID. Al reconectar con `Last-Event-ID`, el servidor emite los eventos desde ese ID.

### Fix propuesto

**Archivo: `src/engine/api.py`**

```python
_event_buffers: dict[str, list[dict]] = {}  # thread_id → [(id, event_str)]
_MAX_REPLAY_BUFFER = 200  # eventos máximos en buffer

async def event_generator():
    last_id_header = request.headers.get("last-event-id", "")
    event_id = 0
    
    # Replay desde last_id si el cliente reconecta
    if last_id_header and thread_id in _event_buffers:
        try:
            resume_from = int(last_id_header)
            for (eid, event_str) in _event_buffers[thread_id]:
                if eid > resume_from:
                    yield event_str
        except ValueError:
            pass
    
    while not (done_ev.is_set() and queue.empty()):
        try:
            event = await asyncio.wait_for(queue.get(), timeout=30.0)
            event_id += 1
            # Agregar id: al evento SSE
            event_with_id = f"id: {event_id}\n{event}"
            # Buffer para replay
            buf = _event_buffers.setdefault(thread_id, [])
            buf.append((event_id, event_with_id))
            if len(buf) > _MAX_REPLAY_BUFFER:
                buf.pop(0)
            yield event_with_id
        except asyncio.TimeoutError:
            if await request.is_disconnected():
                break
            yield f"event: heartbeat\ndata: {{}}\n\n"
```

---

## Orden de implementación

```
S60-A (template system_backend.md + system_backend_python.md)  ← primero, más impacto
S56-A (qa_review SystemMessage + template system_qa.md)        ← segundo
S60-B (update_test_retry detección no-retryable)               ← tercero, depende de ver efecto de S60-A
S60-C (_cleanup_workspace_before_retry quirúrgico)             ← cuarto
S59-C (SSE Last-Event-ID replay)                               ← último, independiente
```

## Tests

| Test | Verifica | Archivo |
|------|----------|---------|
| `test_s60_a_pytest_ini_generated` | El backend genera `pytest.ini` con `pythonpath = src` | `test_s60.py` |
| `test_s60_a_main_py_entry_point` | El backend genera `src/main.py` con `include_router` | `test_s60.py` |
| `test_s60_a_modules_export_router` | Módulos exportan `APIRouter`, no `FastAPI()` | `test_s60.py` |
| `test_s56_a_sdd_in_system_message` | `qa_review` incluye SDD del ciclo en SystemMessage | `test_s56.py` (nuevo) |
| `test_s56_a_per_req_evaluation` | `_build_qa_sdd_block` genera un item por REQ-* | existente |
| `test_s56_a_project_ctx_filtered` | `_strip_db_restrictions` aplicado antes de SystemMessage | `test_s56.py` |
| `test_s60_b_structural_error_no_retry` | `update_test_retry` con ModuleNotFoundError repetido → max_retries | `test_s60.py` |
| `test_s60_b_first_round_retries_normally` | Primera ronda con ModuleNotFoundError → retry normal | `test_s60.py` |
| `test_s60_c_cleanup_only_retry_agent_paths` | `_cleanup_workspace_before_retry` no elimina archivos frontend | `test_s60.py` |
| `test_s60_c_cleanup_preserves_database_files` | archivos migrations sobreviven al cleanup de backend | `test_s60.py` |

## Meta de duración post-S60

| Fase | Duración estimada | Cambio vs S59 |
|------|-------------------|---------------|
| analyze_fr + generate_sdd + route_agents | ~1min | sin cambio |
| backend (9 tareas) | ~4min | sin cambio |
| database (2 tareas, paralelo) | ~30s | sin cambio |
| frontend (4 tareas) | ~2.5min | sin cambio |
| security + QA | ~2min | -1min (QA sin project ctx oracle) |
| run_tests + deliver | ~30s | **-11min** (sin retries estructurales) |
| **Total** | **~10min** | **-12min vs 22m 38s** |

---

## Referencias

- FastAPI — Bigger Applications: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- pytest — Import modes: https://docs.pytest.org/en/stable/explanation/pythonpath.html
- LangGraph — RetryPolicy: https://langchain-ai.github.io/langgraph/reference/pregel/#langgraph.pregel.RetryPolicy
- LangGraph — Command pattern: https://langchain-ai.github.io/langgraph/how-tos/command/
- Zheng et al. (2023) — Judging LLM-as-a-Judge: https://arxiv.org/abs/2306.05685
- Liu et al. (2023) — Lost in the Middle: https://arxiv.org/abs/2307.03172
- W3C SSE spec: https://html.spec.whatwg.org/multipage/server-sent-events.html
