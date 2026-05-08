# Informe ciclo de validación — S121

**Ciclo:** `46d2d42a-619f-4d9a-88e2-30bddc08febc`
**Fecha:** 2026-05-08 17:36 – 17:59 UTC
**Sprint:** S121
**Duración total:** ~23 minutos
**Feature Request:** Sistema de gestión de turnos médicos — endpoint POST /turnos con validación de conflicto de agenda

---

## Resumen ejecutivo

| Métrica | Valor |
|---|---|
| FR tipo | feature / medium |
| Agente activo | backend (1) |
| QA rondas | 4 (3 retries QA + 1 final) |
| Mejor QA score | 72/100 |
| run_tests passed | **False** (3 rondas, todas import_error) |
| Artefactos entregados | 9 (backend) + 2 docs |
| ciclo persistido | ✓ ovd_cycles |
| RAG indexado | ✓ SDD + test failure |

---

## Flujo de ejecución

```
analyze_fr → generate_sdd → approval → architecture_contract → route_agents
  → agent_executor[0] → security(100) → qa(65/FAIL) → qa_retry(1/3)
  → agent_executor[1] → security(100) → qa(5/FAIL)  → qa_retry(2/3)
  → agent_executor[2] → security(100) → qa(56/FAIL) → qa_retry(3/3)
  → agent_executor[3] → security(100) → qa(72/FAIL) → run_tests[0] FAIL
  → test_retry(1/2) → agent_executor[4] → qa(55) → run_tests[1] FAIL
  → test_retry(2/2) → agent_executor[5] → run_tests[2] FAIL (max retries)
  → generate_docs → deliver ✓
```

---

## QA — Historial de scores

| Ronda | Score | SDD compliance | Issues | Nota |
|---|---|---|---|---|
| 0 | 65/100 | True | 7 | Primer intento — mejor base |
| 1 | 5/100 | False | 7 | Regresión severa tras retry |
| 2 | 56/100 | False | 6 | Recuperación parcial |
| 3 | 72/100 | False | 7 | Mejor score pero aún bajo umbral |
| test-retry-1 | 55/100 | False | 6 | Post primer test failure |

**Observación:** variabilidad extrema (5–72). El modelo `deepseek-v4-pro` mostró inestabilidad en los retries de QA — las instrucciones de corrección no convergieron.

---

## run_tests — Análisis de fallos

### Ronda 0 (retry_round=0) — 7.3s

```
ImportError while loading conftest '/srv/projects/turnos-demo/conftest.py'
conftest.py:17:  from src.main import app           ← S121-B: patrón correcto ✅
src/main.py:8:   from src.turnos.router import router
src/turnos/router.py:11: from src.turnos.services import create_turno...
```

**Error:** `src/turnos/router.py` → `services.py` fallaba al importar. Probable `database.py` con engine module-level en `services.py`.

### Ronda 1 (retry_round=1) — 5.8s

```
ImportError while loading conftest '/srv/projects/turnos-demo/tests/conftest.py'
tests/conftest.py:14:  from src.main import app     ← S121-B: patrón correcto ✅
src/main.py:10:  from src.turnos.models import TurnoCreate, TurnoResponse
src/turnos/models.py:11: class Turno(Base):         ← falla aquí
```

**Error:** `models.py` define `class Turno(Base)` pero `Base` viene de `database.py` que aún tiene `create_async_engine` a nivel de módulo — S121-A no respetado.

### Ronda 2 (retry_round=2) — 6.4s

```
ImportError while loading conftest '/srv/projects/turnos-demo/tests/conftest.py'
tests/conftest.py:14:  from src.main import app     ← S121-B: patrón correcto ✅
[misma cadena que ronda 1]
```

**Nota:** conftest regenerado en ronda 2 (S57-C), mismo patrón, mismo fallo subyacente.

---

## Validación S121 — estado por fix

| Fix | Estado | Evidencia |
|---|---|---|
| **S121-B**: conftest usa `from src.main import app` | ✅ **VALIDADO** | conftest.py:17 y tests/conftest.py:14 usan el patrón correcto en las 3 rondas |
| **S121-A**: `database.py` no llama `create_async_engine` a nivel de módulo | ❌ **NO EFECTIVO** | El modelo regeneró `database.py` con 1566→1567 bytes (prácticamente idéntico) — engine module-level persiste |
| **S121-C**: `update_test_retry` inyecta hint para conftest ImportError | ⚠️ **PARCIAL** | La detección requiere `"database"` en test_output; el traceback del ronda 0 no lo incluye explícitamente |

---

## Anomalías detectadas

### 1. `src/utils/prime_validator.py` presente en disco

En las 3 rondas de tests aparece `src/utils/prime_validator.py` (509 bytes) — un validador de números primos completamente fuera de contexto en un sistema de gestión de turnos médicos. Señal clara de alucinación del modelo.

**Impacto:** los QA scores bajos (5/100, 56/100) correlacionan con este tipo de código espurio. El agente `backend` generó lógica de negocio irrelevante en lugar de enfocarse en el endpoint de turnos.

### 2. Regresión severa QA ronda 1 (65→5)

De 65 a 5 en el primer QA retry. Indica que el feedback de corrección del QA fue contraproducente — el modelo reformuló todo el código en vez de corregir solo los issues señalados.

### 3. `src/__init__.py` escrito con 0 bytes en disco

Log: `archivo 'src/__init__.py' escrito pero 0 bytes en disco (content_len=14)`. Posible bug en `_write_artifacts` para archivos de 14 bytes que se truncan a 0. No se investiga en este ciclo.

### 4. `retry_feedback` truncado a 2000 chars (de 12782 chars)

El feedback acumulado de 12782 chars se truncó a 2000. Con múltiples rondas de QA + test retry, el feedback se saturó. El modelo recibió instrucciones incompletas.

---

## Artefactos entregados (ronda final)

| Archivo | Tamaño | Estado |
|---|---|---|
| `src/database.py` | 1567 bytes | ✓ en disco (pero engine module-level) |
| `src/main.py` | 432 bytes | ✓ en disco |
| `src/turnos/router.py` | 864 bytes | ✓ en disco |
| `src/turnos/models.py` | (presente) | ✓ en disco |
| `src/turnos/services.py` | (presente) | ✓ en disco |
| `src/utils/prime_validator.py` | 509 bytes | ✓ espurio |
| `tests/test_turnos.py` | 8035 bytes | ✓ en disco |
| `pytest.ini` | 121 bytes | ✓ en disco |
| `docs/openapi.yaml` | 2573 bytes | ✓ |
| `docs/README.md` | 74 bytes | ✓ |

---

## Métricas de infraestructura

| Métrica | Valor |
|---|---|
| S47-A (background task) | ✓ SSE cancelado 17:58:13, grafo continuó |
| S120-B (FK ovd_cycles) | ✓ `ciclo persistido en ovd_cycles` |
| RAG indexado | ✓ 1 chunk SDD + 1 chunk test failure + 1 chunk QA finding |
| deploy DO | ACTIVE (3a8292e4, 11/11 steps) |

---

## Causa raíz del fallo persistente

El modelo `deepseek-v4-pro` sigue generando `src/database.py` con `create_async_engine` a nivel de módulo pese a la regla S121-A en `backend_python.md`. La cadena de fallo es:

```
tests/conftest.py
  └── from src.main import app
        └── from src.turnos.models import ...
              └── from src.database import Base
                    └── engine = create_async_engine(DATABASE_URL, ...)  ← FALLA AQUÍ
```

El problema ya no está en el conftest (S121-B lo resolvió), sino en que `database.py` persiste en inicializar el engine a nivel de módulo. La regla en el template no es suficiente — el modelo la ignora.

---

## Propuestas para S122

### P1 — Postprocessor `_fix_database_module_level_engine` (CRÍTICO)

Después de `_write_artifacts`, escanear `src/database.py` y reescribir automáticamente el patrón module-level a lazy:

```python
# Detectar: engine = create_async_engine(...)  fuera de función
# Reescribir a: _engine=None; def get_engine(): global _engine; ...
```

### P2 — Reforzar S121-C: ampliar detección a toda la cadena

Incluir `"class.*Base\|from src.database"` en el traceback para disparar el hint, no solo `"database"` literal.

### P3 — Limitar cap de `prime_validator` y código espurio

`_classify_pytest_failures` podría detectar archivos `utils/*.py` que no se mencionan en el SDD y marcarlos en el feedback para que el modelo los elimine.

### P4 — Aumentar cap de retry_feedback (2000→3000)

Con 4 rondas QA + 2 test retries, 2000 chars no es suficiente para preservar todas las instrucciones de corrección.

---

## Comparación con ciclos anteriores

| Ciclo | Sprint | run_tests | QA mejor | Causa fallo |
|---|---|---|---|---|
| S118 | `ef23a1dd` | FAIL | — | pytest no instalado en prod |
| S119 | `ef23a1dd` | FAIL | — | directory vacío + FK missing |
| S120 | `a18c7b32` | FAIL | 93/100 | conftest `from src.database import` (module-level engine) |
| **S121** | `46d2d42a` | **FAIL** | **72/100** | conftest correcto ✅ pero `database.py` sigue con engine module-level |

**Progreso real:** el fallo migró de "conftest importa src.database directamente" a "database.py tiene engine module-level". S121-B resolvió la capa superficial; S122 debe resolver la capa profunda con un postprocessor.
