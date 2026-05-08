# Informe de Ciclo de Validación — S118 Producción
**Ciclo:** `e929a6ca-9446-4834-bd07-4f1566880451`  
**Fecha:** 2026-05-08 15:34 – 15:53+ UTC  
**FR:** "Agregar endpoint REST POST /api/pacientes con validación RUT chileno, SQLAlchemy async, tests pytest con fixtures async"  
**Proyecto:** Sistema de Turnos Médicos (`PRJ_TURNOS_DEMO`)  
**Deploy validado:** S118 (commit `4649499`, DO App Platform ACTIVE 11/11)

---

## 1. Secuencia de nodos (timeline completo)

| Nodo | Estado | Tiempo aprox. |
|---|---|---|
| `clone_repo` | ✅ | 15:34 |
| `describe_image` | ✅ | 15:34 |
| `analyze_fr` | ✅ | 15:34 |
| `generate_sdd` | ✅ | 15:34 |
| `request_approval` | ✅ (auto_approve) | 15:34 |
| `generate_architecture_contract` | ✅ | 15:35 |
| `route_agents` | ✅ | 15:35 |
| `agent_executor` (ronda 0) | ✅ 36 artefactos | 15:36–15:42 |
| `security_audit` | ✅ | 15:42 |
| `qa_review` | ⚠️ 55/100 (umbral 70) | 15:42 |
| `qa_retry` #1 | ↩️ | 15:43 |
| `agent_executor` (ronda 1) | ✅ | 15:43–15:47 |
| `security_audit` | ✅ | 15:47 |
| `qa_review` | ❌ 42/100 (regresión) | 15:47 |
| `qa_retry` #2 | ↩️ | 15:48 |
| `agent_executor` (ronda 2) | ✅ | 15:48–15:49 |
| `security_audit` | ✅ | 15:49 |
| `qa_review` | ✅ 72/100 (≥ umbral 70) | 15:49 |
| `run_tests` (ronda 0) | ❌ 0.3s — S103-P2 | 15:49:52 |
| `test_retry` #1 | ↩️ | 15:49 |
| `route_agents` → `agent_executor` | ✅ (fix PacienteORM) | 15:50–15:52 |
| `security_audit` → `qa_review` | ⚠️ 50/100 | 15:52 |
| `run_tests` (ronda 1) | ❌ 0.8s — No module named pytest | 15:52:46 |
| `test_retry` #2 | ↩️ | 15:52 |
| `route_agents` → `agent_executor` (ronda 3) | en curso... | 15:53+ |

---

## 2. Progresión de scores QA

| Ronda | Score | SDD compliance | Issues |
|---|---|---|---|
| 0 | 55/100 | ❌ | 7 — @classmethod duplicados en PacienteCreate |
| 1 | 42/100 | ❌ | 7 — imports rotos + discrepancia router/services |
| 2 | **72/100** | ✅ | 6 — pasa umbral, decoradores Pydantic y falta import repo |

**Comportamiento `_keep_best_qa`:** funcionó correctamente — el score 72/100 se preservó cuando la ronda 3 (post test_retry) cayó a 50/100.

---

## 3. Validación específica de S118

### S118-A — `_is_structural` acepta "no tests ran" / "ImportError while importing"
**Estado:** No ejercitado en este ciclo.

Los tests fallaron por causas anteriores al output de pytest:
1. **Ronda 0:** S103-P2 pre-check — output = `[S103-P2] NOMBRES NO DEFINIDOS`. No contiene "ImportError", "no tests ran" ni "collected 0 items" → `_is_structural=False`.
2. **Ronda 1:** pytest no instalado en producción — output = `/app/.venv/bin/python: No module named pytest`. Tampoco activa `_is_structural`.

El fix S118-A es correcto para el escenario que diagnosticamos (pytest output real con "no tests ran"), pero no se ejercitó porque hay bugs más tempranos en la cadena.

### S118-B — S57-B `_is_collection_error`
**Estado:** No ejercitado — mismo motivo que S118-A.

### S118-C — `pytest-asyncio` en requirements.txt mínimo
**Estado:** Irrelevante en producción — el problema no es la falta de pytest-asyncio en el workspace sino que pytest **no está instalado en el engine** (`/app/.venv`).

---

## 4. Hallazgos críticos — Bugs nuevos identificados

### BUG-1 (CRÍTICO, PROD-ONLY): pytest no instalado en Docker de producción

**Síntoma:** `/app/.venv/bin/python: No module named pytest`

**Causa raíz:**
```dockerfile
# src/engine/Dockerfile línea ~30
RUN uv sync --frozen --no-dev   # excluye dev-dependencies, incluyendo pytest
```

pytest está en `[dev-dependencies]` de `pyproject.toml` pero el Docker de producción usa `--no-dev`. En desarrollo local `uv sync` sí lo incluye.

**Impacto:** `run_tests` falla en 0.8s en TODOS los ciclos de producción. Los tests nunca se ejecutan. El score QA no recibe el bonus de tests pasados.

**Fix S119-A:** Mover `pytest`, `pytest-asyncio`, `httpx` a las dependencias principales del engine:
```toml
# pyproject.toml — [dependencies]
"pytest>=7.0",         # runner para proyectos generados
"pytest-asyncio>=0.21",
"httpx>=0.24",         # TestClient async
```
O agregar al Dockerfile:
```dockerfile
RUN uv sync --frozen --no-dev
RUN .venv/bin/pip install pytest pytest-asyncio httpx
```

### BUG-2 (ALTO): `last_test_error` vacío para output de S103-P2

**Síntoma:** El output de S103-P2 (`[S103-P2] NOMBRES NO DEFINIDOS`) no activa `_is_structural` → `last_test_error=""` → retries ciegos sin contexto del error anterior.

**Causa:** `_is_structural` solo revisa "ImportError", "ModuleNotFoundError", "no tests ran", "collected 0 items" — no incluye el prefijo `[S103-P2]`.

**Fix S119-B:** En `update_test_retry`, extender `_new_last_error`:
```python
_is_s103_output = "[S103-P2]" in test_output
_new_last_error = test_output if (_is_structural or _is_s65a_output or _is_s103_output) else ""
```

### BUG-3 (ALTO): `last_test_error` vacío para "No module named pytest"

**Síntoma:** Similar al BUG-2. El output "No module named pytest" no activa `_is_structural`.

**Fix S119-B (mismo):** También agregar:
```python
_is_no_module = "No module named" in test_output
_new_last_error = test_output if (_is_structural or _is_s65a_output or _is_s103_output or _is_no_module) else ""
```

O más limpio: generalizar la condición para cualquier error "estructural" de Python:
```python
_STRUCTURAL_MARKERS = (
    "ModuleNotFoundError",
    "ImportError",
    "No module named",
    "[S103-P2]",
    "[S65-A]",
    "[S100-B]",  # SyntaxError
)
_is_structural = any(m in test_output for m in _STRUCTURAL_MARKERS) and (
    "collected 0 items" in test_output
    or "no tests ran" in test_output
    or "ImportError while importing" in test_output
    or "No module named" in test_output
    or "[S103-P2]" in test_output
)
```

---

## 5. Comportamientos validados (funcionando correctamente)

| Mecanismo | Resultado |
|---|---|
| S70-A background task | ✅ SSE desacoplado del grafo |
| S47-A SSE heartbeat | ✅ 30s entre heartbeats |
| S31-C cycle test selection | ✅ 1 test file del ciclo detectado |
| S53-C module contract injection | ✅ contrato inyectado en retry_feedback |
| S54-D disk file logging | ✅ 14 archivos Python en disco |
| S57-C conftest.py regeneración | ✅ regenerado en retry_round=1 |
| `_keep_best_qa` reducer | ✅ 72/100 preservado vs 50/100 post-retry |
| S97-A stagnation detection | ✅ delta=13 > 5 → no dispara falso positivo |
| auto_approve | ✅ aprobación automática sin intervención |
| DO deploy S118 ACTIVE | ✅ 11/11 pasos, commit `4649499` |

---

## 6. Análisis de oscilación QA (55 → 42 → 72 → 50)

El agente tuvo 4 rondas con scores muy variables (+/-30 puntos). El error recurrente fue el `@classmethod` duplicado en Pydantic models — un patrón que el agente introduce, corrige y vuelve a introducir.

**Root cause de oscilación:** El feedback de QA describe el problema pero el agente lo interpreta inconsistentemente. Sin un "architecture contract" que prohíba explícitamente los `@classmethod` duplicados en Pydantic v2, el modelo genera código variable.

**Propuesta S119-C:** Agregar regla explícita en `backend_python.md` para validadores Pydantic v2:
```markdown
## Pydantic v2 validators — PROHIBIDO
- NUNCA usar @classmethod + @validator/field_validator combinados → duplicate decorator
- Usar SOLO: @field_validator("campo") en Pydantic v2
- NUNCA: @classmethod @field_validator(…) — el @classmethod es implícito en v2
```

---

## 7. Artefactos generados (ronda final)

14 archivos Python detectados en disco:
```
conftest.py
src/database.py
src/main.py
src/pacientes/__init__.py
src/pacientes/models.py
src/pacientes/orm.py
src/pacientes/repository.py
src/pacientes/router.py
src/pacientes/services.py
src/utils/__init__.py
src/utils/rut_validator.py
tests/__init__.py
tests/conftest.py
tests/test_pacientes.py
```

Estructura correcta con separación de capas (router → services → repository → models/orm).

---

## 8. Roadmap S119 (prioridades)

| ID | Descripción | Prioridad | Impacto |
|---|---|---|---|
| S119-A | `pytest` + `pytest-asyncio` + `httpx` a deps principales (Dockerfile fix) | CRÍTICO | Tests nunca se ejecutan en prod |
| S119-B | Extender `_is_structural` para `[S103-P2]`, "No module named", `[S100-B]` | ALTO | Retries ciegos sin feedback |
| S119-C | Regla Pydantic v2 `@field_validator` en `backend_python.md` | ALTO | QA oscilación por @classmethod |
| S119-D | `S117-G` — G-Eval rubric-aligned QA scoring | MEDIO | Reduce varianza ±30 → ±10 |
| S119-E | `S117-H` — `handle_escalation` emite mejor intento cuando score ≥ 40 | MEDIO | Cycles con max retries entregan el mejor artefacto |

---

## 9. Conclusión

El ciclo `e929a6ca` validó que S118 está **desplegado y activo** pero **no pudo ejercitar el fix principal (S118-A)** porque el error bloqueante está upstream: pytest no instalado en producción (`uv sync --no-dev`).

**S119-A es el fix más crítico** — sin él, ningún ciclo de producción puede ejecutar tests. El score QA de 72/100 (mejor ronda) es positivo pero sin verificación de tests no hay certeza de que el código funcione en runtime.

**Próximo paso:** Implementar S119-A (Dockerfile + pyproject.toml) y relanzar el ciclo para validar el camino completo hasta `run_tests passed=True`.
