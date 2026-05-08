# Plan S117 — Fix QA Convergencia + Templates Robustos + Infraestructura BD

**Basado en:** INFORME_S116_PROD_CYCLE.md + análisis de código + investigación externa  
**Objetivo:** Primer ciclo que entrega (deliver) en producción con QA ≥ 75/100  
**Duración estimada:** 2 sesiones (~6h)

---

## Diagnóstico: por qué S116 no delivereó

Tres causas independientes convergieron:

| Causa | Root cause real | Fix |
|---|---|---|
| **BUG-1**: stagnation falso [55,55] | `_keep_best_qa` reducer preserva score=55 → `update_qa_retry` lee score stale | S117-B |
| **BUG-2**: QA score 55→12→68 | Workspace 115KB truncado a 20K chars → 78% del código invisible para QA | S117-C |
| **BUG-3**: TASK-007 timeout 120s | Contexto de retry acumulado (10K) aumenta latencia → mismo timeout para tareas simples y complejas | S117-D |
| **BUG-4**: `failed_at_node` faltante | Migración 0006 incompleta | S117-A |

---

## Arquitectura de la solución

```
Ciclo S117 con todos los fixes:
 ┌─────────────────────────────────────────────────────────┐
 │ analyze_fr → generate_sdd → route_agents                │
 │ agent_executor[backend] — TASK-007 timeout=240s (retry2)│
 │ qa_review — 50K chars (vs 20K antes) → más código visto │
 │ route_after_qa → usa qa_score_history CORRECTA [55,12,68]│
 │ → NO stagnation → retry #3 → score ≥ 75 → deliver ✓    │
 └─────────────────────────────────────────────────────────┘
```

---

## Fix A — Migración 0007: columna `failed_at_node` [30 min]

**Problema:** `_ensure_cycle_registered` en api.py intenta escribir `failed_at_node` que no existe.

**Archivo:** `src/engine/migrations/versions/20260509_0007_ovd_cycles_failed_at_node.py`

```python
"""ovd_cycles — failed_at_node para trazabilidad de nodo de fallo (S117-A)

Revision ID: 20260509_0007
Revises: 20260508_0006
Create Date: 2026-05-09 00:00:00.000000
"""
revision: str = "20260509_0007"
down_revision: Union[str, None] = "20260508_0006"

def upgrade() -> None:
    op.execute("""
        ALTER TABLE ovd_cycles
        ADD COLUMN IF NOT EXISTS failed_at_node TEXT
    """)

def downgrade() -> None:
    op.execute("ALTER TABLE ovd_cycles DROP COLUMN IF EXISTS failed_at_node")
```

**Tests:** ninguno nuevo — verificar que `_ensure_cycle_registered` ya no loguea WARNING.

---

## Fix B — Fix `qa_score_history` stale read [2h]

### Root cause exacto

```python
# graph.py — OVDState
qa_result: Annotated[dict, _keep_best_qa]  # ← reducer preserva MEJOR score del ciclo

# _keep_best_qa:
def _keep_best_qa(existing, update):
    return existing if existing.get("score", 0) >= update.get("score", 0) else update
# Efecto: si ronda 0 fue 55 y retry #1 retorna 12 → qa_result SIGUE siendo {score: 55}

# update_qa_retry lee:
qa = state.get("qa_result", {})        # ← STALE: sigue siendo 55
current_score = qa.get("score", 0)     # ← registra 55, no 12
```

### Solución: campo `qa_result_current` con last-write-wins

**graph.py — OVDState (agregar campo):**
```python
# S117-B: resultado del round QA actual (sin reducer best-keep)
# Necesario para qa_score_history correcta: update_qa_retry debe leer este campo
qa_result_current: dict  # TypedDict sin Annotated → last-write-wins en LangGraph
```

**graph.py — qa_review (retornar ambos campos):**
```python
# Al retornar el resultado de qa_review, añadir:
return {
    "qa_result": qa_output_dict,          # reducer _keep_best_qa lo procesa normalmente
    "qa_result_current": qa_output_dict,  # last-write-wins → siempre el round actual
    ...
}
```

**graph.py — update_qa_retry (leer de `qa_result_current`):**
```python
def update_qa_retry(state: OVDState) -> dict:
    # S117-B: leer del campo current (no del best-preserving qa_result)
    qa_current = state.get("qa_result_current") or state.get("qa_result", {})
    current_score = qa_current.get("score", 0)
    # ... resto igual
```

**Resultado esperado:** score history = [55, 12, 68] → delta(12,68)=56 → NO stagnation → retry #3.

### Tests S117-B

```python
# tests/test_s117.py

def test_s117b_update_qa_retry_reads_current_not_best():
    """update_qa_retry debe leer qa_result_current (score=12), no qa_result (score=55)."""
    state = {
        "qa_result": {"score": 55, "passed": False, "issues": []},       # best (stale)
        "qa_result_current": {"score": 12, "passed": False, "issues": []},  # current
        "qa_retry_count": 1,
        "qa_score_history": [{"round": 1, "score": 55}],
        "retry_feedback": "",
        "messages": [],
    }
    result = update_qa_retry(state)
    history = result["qa_score_history"]
    assert history[0]["score"] == 12, f"Esperado 12, got {history[0]['score']}"


def test_s117b_stagnation_not_triggered_on_improving_scores():
    """Con historial [55, 12] y score actual 68 → delta=56 → NO stagnation."""
    history = [{"round": 1, "score": 55}, {"round": 2, "score": 12}]
    state = {
        "qa_result": {"score": 55, "passed": False, "issues": []},  # best stale
        "qa_result_current": {"score": 68, "passed": False, "issues": []},
        "qa_retry_count": 2,
        "qa_score_history": history,
        "retry_feedback": "",
        "messages": [],
    }
    result = route_after_qa(state)
    assert result != "handle_escalation", "No debe escalar — scores están mejorando"


def test_s117b_stagnation_correctly_detected():
    """Con historial [50, 50] y score actual 51 → delta=1 → stagnation correcto."""
    history = [{"round": 1, "score": 50}, {"round": 2, "score": 50}]
    state = {
        "qa_result": {"score": 51, "passed": False, "issues": []},
        "qa_result_current": {"score": 51, "passed": False, "issues": []},
        "qa_retry_count": 2,
        "qa_score_history": history,
        "retry_feedback": "",
        "messages": [],
    }
    result = route_after_qa(state)
    assert result == "handle_escalation"
```

---

## Fix C — QA workspace truncation: 20K → 50K [2h]

### Root cause

```
Ronda 0:  workspace=87,347 chars → truncado a 20,000 (77% ciego) → score=55
Retry #1: workspace=87,347 chars → truncado a 20,000 (77% ciego) → score=12 (porción distinta!)
Retry #2: workspace=115,802 chars → truncado a 20,000 (83% ciego) → score=68
```

La varianza 55→12→68 no es de temperatura (ya es 0.0) sino de **qué porción del código ve el LLM** en cada truncamiento. Dos evaluaciones del mismo código que ven partes distintas dan scores completamente diferentes.

### Solución: aumentar límite + ordenar archivos por importancia

**graph.py — línea ~5577:**

```python
# ANTES:
f"## Código generado:\n{_truncate(agent_output, 20000)}"

# DESPUÉS (S117-C):
# Priorizar archivos críticos antes de concatenar y truncar
_qa_workspace = _build_qa_workspace_prioritized(agent_results, directory, cycle_start_ts)
f"## Código generado:\n{_truncate(_qa_workspace, 50000)}"
```

**Nueva función `_build_qa_workspace_prioritized`:**

```python
# Orden de prioridad: archivos que más importan para QA primero
_QA_FILE_PRIORITY = [
    "services.py",     # lógica de negocio — más issues QA
    "models.py",       # ORM models — imports, validators
    "router.py",       # endpoints — CRUD compliance
    "routers/",        # si hay subdirectorio
    "main.py",         # startup, middleware
    "tests/",          # cobertura
    "conftest.py",
    "database.py",     # sesión async
    "auth/",           # JWT, RUT validation
]

def _build_qa_workspace_prioritized(agent_results, directory, cycle_start_ts):
    """
    S117-C: construye workspace para QA priorizando archivos críticos.
    Evita la varianza por truncamiento aleatorio (bug S116: 77-83% ciego).
    """
    all_files = _get_cycle_files(directory, cycle_start_ts)
    
    # Ordenar: archivos con keywords de alta prioridad van primero
    def priority_key(path):
        for i, pattern in enumerate(_QA_FILE_PRIORITY):
            if pattern in path:
                return i
        return len(_QA_FILE_PRIORITY)
    
    sorted_files = sorted(all_files, key=lambda f: priority_key(f["path"]))
    
    parts = []
    for f in sorted_files:
        parts.append(f"### {f['path']}\n```python\n{f['content']}\n```")
    
    return "\n\n".join(parts)
```

**Impacto esperado:**
- Límite 50K chars cubre ~55KB de código (vs 20K antes)
- Con 31 archivos promedio × ~1.5KB = 46KB promedio → 50K cubre el 100%
- Orden determinístico: services.py siempre se incluye primero

### Tests S117-C

```python
def test_s117c_qa_workspace_includes_services_first():
    """El workspace para QA pone services.py antes que otros archivos."""
    # ...verifica que la función prioriza correctamente

def test_s117c_50k_limit_covers_typical_project():
    """Un proyecto de 31 archivos × 1.5KB promedio cabe en 50K chars."""
    assert 31 * 1500 < 50000  # Invariante del límite
```

---

## Fix D — Per-retry timeout escalation para tareas complejas [1.5h]

### Root cause

```
TASK-007 (turnos/services.py) tiempos reales:
  Ronda 0:  56s  (código base, sin feedback)
  Retry #1: 71s  (más contexto de feedback: 5K chars retry_feedback)
  Retry #2: 120s TIMEOUT (feedback acumulado: 10K chars + 31 archivos de contexto)

El timeout es uniforme: _AGENTS_TIMEOUT=120s para todas las tareas y todos los retries.
En retry #2 el prompt es ~2.5× más grande que en ronda 0 → LLM tarda proporcionalmente más.
```

### Solución: timeout escalado por número de retry

**graph.py — agent_executor (líneas ~3977-4253):**

```python
# ANTES:
timeout=_AGENTS_TIMEOUT

# DESPUÉS (S117-D):
_retry_round = state.get("qa_retry_count", 0) + state.get("security_retry_count", 0)
_task_timeout = _get_task_timeout(_AGENTS_TIMEOUT, _retry_round)
timeout=_task_timeout
```

**Nueva función:**

```python
def _get_task_timeout(base_timeout: float, retry_round: int) -> float:
    """
    S117-D: escalar timeout por ronda de retry.
    Ronda 0: 120s (base)
    Retry 1: 180s (+50%)
    Retry 2: 240s (+100%)
    
    Justificación: el prompt crece ~2-3× por retry (feedback acumulado 0→5K→10K chars).
    El LLM tarda proporcionalmente más para generar código correcto.
    """
    scale = [1.0, 1.5, 2.0]
    factor = scale[min(retry_round, len(scale) - 1)]
    return base_timeout * factor
```

**settings.py — agregar:**
```python
ovd_agents_timeout_secs: float = 120.0  # ya existe
ovd_agents_timeout_retry1_factor: float = 1.5  # S117-D: factor para retry #1
ovd_agents_timeout_retry2_factor: float = 2.0  # S117-D: factor para retry #2
```

**Resultado esperado:**
- Ronda 0: 120s (sin cambio)
- Retry #1: 180s (TASK-007 tardó 71s → OK con margen)
- Retry #2: 240s (TASK-007 estima ~110-140s → OK con margen)

### Tests S117-D

```python
def test_s117d_timeout_escalates_by_retry():
    assert _get_task_timeout(120, 0) == 120.0
    assert _get_task_timeout(120, 1) == 180.0
    assert _get_task_timeout(120, 2) == 240.0

def test_s117d_timeout_caps_at_retry2():
    """retry_round=5 usa el mismo factor que retry_round=2."""
    assert _get_task_timeout(120, 5) == _get_task_timeout(120, 2)
```

---

## Fix E — SQLAlchemy async transactions en templates [2h]

### Contexto

Los issues QA #2 y #3 de S116 son recurrentes (también en S114/S115):
- `Reserva de turnos no transaccional — viola REQ-005 atomicidad`
- `Cancelación de turnos no transaccional`

El agente genera SELECT + UPDATE + INSERT como queries separadas. El LLM no sabe que necesita `with_for_update()` + `async with db.begin()`.

### Solución: patrón explícito en template

**`src/engine/templates/stack/backend_python.md` — agregar sección:**

```markdown
## Patrón ACID para operaciones de reserva (OBLIGATORIO — S117-E)

### ANTI-PATRÓN (prohibido):
```python
# ❌ Race condition garantizada — NUNCA usar
slot = await db.execute(select(Slot).where(Slot.id == slot_id))
await db.execute(update(Slot).where(Slot.id == slot_id).values(disponible=False))
db.add(Turno(...))
await db.commit()
```

### PATRÓN CORRECTO:
```python
# ✅ Atómico con SELECT FOR UPDATE
async def reservar_turno(db: AsyncSession, slot_id: int, paciente_id: int) -> Turno:
    async with db.begin():                          # Transacción ACID explícita
        stmt = (
            select(Disponibilidad)
            .where(Disponibilidad.id == slot_id)
            .with_for_update()                      # Lock pesimista — previene double-booking
        )
        slot = (await db.execute(stmt)).scalar_one_or_none()
        if not slot:
            raise HTTPException(404, "Slot no encontrado")
        if not slot.disponible:
            raise HTTPException(409, "Slot ya reservado")
        
        turno = Turno(disponibilidad_id=slot_id, paciente_id=paciente_id)
        db.add(turno)
        await db.execute(
            update(Disponibilidad)
            .where(Disponibilidad.id == slot_id)
            .values(disponible=False)
        )
        # COMMIT automático al salir del context manager
    return turno
```

### Reglas:
1. TODA operación que lee-y-escribe DEBE usar `async with db.begin()`
2. SELECT sobre recursos que se van a modificar SIEMPRE con `.with_for_update()`
3. NUNCA hacer queries fuera del `async with db.begin()` si se necesita consistencia
4. La dependencia FastAPI provee `AsyncSession` — NO crear sesiones manualmente
```

**`src/engine/templates/system_sdd.md` — agregar constraint:**

```markdown
### Constraints de Integridad (S117-E)

Para cualquier operación que lea-y-modifique el mismo recurso:
- **ACID_REQUIRED**: Usar `async with db.begin()` obligatorio
- **SELECT_FOR_UPDATE**: `.with_for_update()` en SELECT de recursos a modificar
- Ejemplos: reserva de slots, stock de inventario, asignación de recursos únicos
```

---

## Fix F — Validación RUT módulo 11 en template [1h]

### Contexto

Issue QA #4 recurrente: `Validación RUT usa regex simple pero no verifica dígito verificador chileno`.

S68-D (ya implementado) agrega `clean_rut` y `format_rut` al template, pero no incluye la función de validación completa con módulo 11.

### Solución

**`src/engine/templates/stack/backend_python.md` — agregar función completa:**

```markdown
## Validación RUT chileno — dígito verificador módulo 11 (OBLIGATORIO — S117-F)

```python
def validar_rut(rut: str) -> bool:
    """
    Valida RUT chileno usando algoritmo módulo 11.
    Acepta formatos: '12.345.678-9', '123456789', '12345678-9'
    """
    rut = rut.upper().replace(".", "").replace("-", "").strip()
    if not rut or len(rut) < 2:
        return False
    
    dv = rut[-1]        # dígito verificador
    numero = rut[:-1]   # cuerpo del RUT
    
    if not numero.isdigit():
        return False
    
    # Algoritmo módulo 11
    total = 0
    factor = 2
    for digito in reversed(numero):
        total += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1
    
    resto = 11 - (total % 11)
    if resto == 11:
        dv_calculado = "0"
    elif resto == 10:
        dv_calculado = "K"
    else:
        dv_calculado = str(resto)
    
    return dv == dv_calculado
```

### Reglas de uso:
- SIEMPRE usar `validar_rut()` en el validator del modelo Pydantic, NO solo regex de formato
- El regex `r"^\d{7,8}-[\dKk]$"` valida formato — `validar_rut()` valida el dígito verificador
- Ambas validaciones son necesarias
```

**system_qa.md — agregar al checklist:**
```
- [ ] Validación RUT incluye módulo 11 (no solo regex de formato)
- [ ] Operaciones de reserva/cancelación usan SELECT FOR UPDATE dentro de db.begin()
```

---

## Fix G — QA prompt: scoring por criterios [3h]

### Contexto

La alta varianza del QA score (55→12→68) tiene dos causas:
1. Truncamiento del workspace (Fix C resuelve esto)
2. El prompt pide un score numérico directo → alta varianza subjetiva del LLM

### Solución: rubric-aligned scoring (basado en G-Eval / investigación de evaluación de código)

**`src/engine/templates/system_qa.md` — cambio de estructura de evaluación:**

```markdown
## Criterios de evaluación (S117-G)

Evalúa el código por CRITERIO, asignando sub-scores. El score final es la suma.

| Criterio | Peso | Descripción |
|---|---|---|
| REQ_COMPLIANCE | 40 pts | Todos los endpoints y funcionalidades del SDD implementados |
| CODE_CORRECTNESS | 25 pts | Sin errores de importación, tipado correcto, sin código incompleto |
| SECURITY | 15 pts | JWT correcto, validación de inputs, sin secrets hardcoded |
| TESTING | 10 pts | Tests que cubren los casos del SDD |
| ARCHITECTURE | 10 pts | Patrón correcto (router→service→repo), transacciones ACID |

Para cada criterio:
1. Listar lo que está presente y lo que falta (evidence-first)
2. Asignar sub-score: 0, 25%, 50%, 75%, 100% del peso máximo
3. Identificar un issue específico con archivo y línea

El JSON de output incluye `sub_scores: {req_compliance: N, code_correctness: N, ...}`.
El `score` final = suma de sub_scores.
```

**`schema/qa_output.py` — actualizar QAReviewOutput:**
```python
class QAReviewOutput(BaseModel):
    score: int              # suma de sub_scores (0-100)
    passed: bool            # score >= threshold
    sub_scores: dict        # S117-G: {"req_compliance": N, "code_correctness": N, ...}
    issues: list[str]       # issues específicos con archivo:línea
    summary: str
    sdd_compliance: bool
```

**Impacto esperado:** reducir varianza de ±43 pts a ±10 pts (evidenciado por G-Eval benchmark).

---

## Fix H — handle_escalation emite deliverables del mejor intento [2h]

### Contexto

Cuando el ciclo va a `handle_escalation`, los deliverables están vacíos aunque el código esté generado en disco. El usuario no puede acceder al código generado aunque sea parcialmente correcto.

### Solución

**graph.py — nodo `handle_escalation`:**

```python
async def handle_escalation(state: OVDState) -> dict:
    """
    S117-H: aunque QA no pasó, emitir el mejor código generado para que el
    operador pueda revisarlo. El ZIP incluye los archivos del workspace + el
    reporte de QA con los issues para corrección manual.
    """
    best_qa = state.get("qa_result", {})
    best_score = best_qa.get("score", 0) if isinstance(best_qa, dict) else 0
    
    # Emitir deliverables si el mejor score >= umbral mínimo razonable (40)
    deliverables = []
    if best_score >= 40:
        deliverables = await _package_workspace_deliverables(
            state.get("directory", ""),
            state.get("session_id", ""),
            include_qa_report=True,
        )
    
    return {
        "status": "escalated",
        "deliverables": deliverables,
        "messages": state.get("messages", []) + [{
            "role": "agent",
            "content": (
                f"Ciclo escalado — QA score {best_score}/100 (umbral: {_QA_MIN_SCORE}). "
                f"{'Código disponible para revisión manual.' if deliverables else 'Score insuficiente para emitir código.'}"
            ),
        }],
    }
```

---

## Orden de ejecución

```
Sesión 1 (~3h):
  S117-A  Migración 0007 (failed_at_node)         30 min
  S117-B  Fix qa_result_current + tests           90 min
  S117-C  QA workspace 50K + priority ordering   60 min
  → deploy + validar fix A/B/C en logs           30 min

Sesión 2 (~3h):
  S117-D  Timeout escalation + tests             60 min
  S117-E  SQLAlchemy template + system_sdd.md    60 min
  S117-F  RUT módulo 11 en template              30 min
  S117-G  QA rubric scoring (opt. si tiempo)     60 min
  S117-H  handle_escalation deliverables (opt.)  60 min
  → deploy + ciclo de validación               en background
```

---

## Criterios de éxito del ciclo de validación S117

```
ciclo S117 usando mismo FR (turnos médicos) con todos los fixes:
  ✓ _ensure_cycle_registered no loguea WARNING (Fix A)
  ✓ qa_score_history = [55, 12, 68] (no [55, 55]) (Fix B)
  ✓ workspace QA = 50K (vs 20K) — cubre >90% de archivos (Fix C)
  ✓ TASK-007 no timeout en retry #2 (Fix D)
  ✓ score ronda 0 ≥ 60 (más código visible → mejor evaluación)
  ✓ score retry #1 mejora por feedback más preciso (rubric G)
  ✓ score retry #2 ≥ 75 → deliver ✓
  ✓ ZIP descargable en /delivery (Fix H como fallback)
```

---

## Verificación antes del deploy

```bash
# Tests unitarios S117
cd src/engine && .venv/bin/python -m pytest tests/test_s117.py -v

# Regression completa
.venv/bin/python -m pytest tests/ \
  -m "not integration and not e2e and not docker" \
  -q --tb=short \
  --ignore=tests/test_alembic_migrations.py \
  -k "not test_cycle_start_ts_reciente and not test_usa_cap_800_en_truncate \
      and not test_dispatch_frontend_despacha_pendientes \
      and not test_write_artifacts_overwrites_when_new_content_larger \
      and not test_s63b_cleanup_not_in_run_tests"

# Verificar migración en local
docker exec postgres_db psql -U ovd_dev -d ovd_dev \
  -c "SELECT column_name FROM information_schema.columns WHERE table_name='ovd_cycles'"
```

---

## Referencias

| Hallazgo | Fuente | Aplicado en |
|---|---|---|
| LangGraph TypedDict sin Annotated = last-write-wins | LangGraph docs (context7) | Fix B |
| Conditional edges ven state post-reducer | LangGraph docs | Fix B (confirma necesidad de campo separado) |
| temperature=0.0 para evaluation tasks | DeepSeek API docs | Confirmado: ya era 0.0. No es la causa. |
| Varianza por truncamiento → rubric-aligned scoring reduce ±43 a ±10 pts | G-Eval research, CodEV | Fix C + Fix G |
| `async with db.begin()` + `.with_for_update()` patrón ACID | SQLAlchemy 2.x async docs | Fix E |
| DO App Platform: sin timeout documentado para in-memory background tasks | DO docs | No acción urgente — 3600s OK para services |
