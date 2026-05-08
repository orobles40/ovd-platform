# Informe ciclo de validación — S122

**Ciclo:** `7990efb6-7557-49fc-a178-6b8c50565109` (S122b — fix paso 2 generalizado)
**Ciclo anterior:** `a28e335d-1dd5-44e7-8ded-cfcefc1e8044` (S122 inicial)
**Fecha:** 2026-05-08 18:38 – 18:49 UTC
**Sprint:** S122
**Duración total:** ~11 minutos
**Feature Request:** Sistema de gestión de turnos médicos — endpoint POST /turnos con validación de conflicto de agenda

---

## Resumen ejecutivo

| Métrica | Valor |
|---|---|
| FR tipo | feature / medium |
| Agente activo | backend + database + devops |
| QA rondas | 3 (rondas QA + 1 final) |
| Mejor QA score | **95/100** (ronda final) |
| run_tests passed | **False** (3 rondas) |
| S122-A postprocessor | ✅ **VALIDADO** — disparado 2 veces |
| Causa fallo persistente | test files importan `async_session_maker` de `src.database` (renombrado por S122-A) |
| ciclo persistido | ✓ ovd_cycles |

---

## Flujo de ejecución

```
analyze_fr → generate_sdd → approval → architecture_contract → route_agents
  → agent_executor[0] → security(100) → qa(55/FAIL) → run_tests[0] FAIL (name_validator)
  → test_retry(1/2) → agent_executor[1] → security → qa(90/FAIL) → run_tests[1] FAIL (pytest)
  → test_retry(2/2) → agent_executor[2] → qa(55) → run_tests[2] FAIL (name_validator, max retries)
  → generate_docs → deliver ✓
```

---

## QA — Historial de scores

| Ronda | Score | Nota |
|---|---|---|
| 0 | 55/100 | Primer intento |
| 1 | 90/100 | Post retry_round=0 — mejora importante |
| 2 | 55/100 | Regresión en retry_round=1 |
| 3 (final) | **95/100** | **Mejor score histórico** |

**Comparación histórica:**
| Ciclo | QA máximo |
|---|---|
| S120 | 93/100 |
| S121 | 72/100 |
| S122 | **95/100** |

---

## S122-A — Validación del postprocessor

### Activaciones confirmadas en logs DO

```
18:46:15 [code_postprocessor] WARNING [S122-A] database.py: engine module-level → lazy get_engine() + get_session_factory()
18:49:02 [code_postprocessor] WARNING [S122-A] database.py: engine module-level → lazy get_engine() + get_session_factory()
```

**Ciclo inicial (a28e335d):** el postprocessor detectó `async_session_factory = async_sessionmaker(get_engine(), ...)` a nivel de módulo — variable con nombre no estándar (`async_session_factory` vs `AsyncSessionLocal`). El fix del paso 2 generalizado corrigió esto.

### Patrón reescrito

El modelo generó:
```python
engine = create_async_engine(DATABASE_URL, echo=False, pool_size=10, max_overflow=20)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

S122-A reescribió a:
```python
_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(DATABASE_URL, echo=False, pool_size=10, max_overflow=20)
    return _engine

_session_factory = None

def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)
    return _session_factory
```

**Resultado:** El ImportError original por `create_async_engine` a nivel de módulo fue resuelto. ✅

---

## run_tests — Análisis de fallos

### Ronda 0 — name_validator

```
src/turnos/router.py: from src.turnos.services import create_appointment ← no definido
```

Error de naming: el modelo importó `create_appointment` pero la función en `services.py` tiene otro nombre.

### Ronda 1 — pytest EXIT 2

```
ERROR collecting tests/test_turnos.py
collected 4 items / 1 error
```

**Causa probable:** `test_turnos.py` importa `async_session_maker` de `src.database` — nombre que no existe después de S122-A. Confirmado por round 2.

### Ronda 2 — name_validator (max retries)

```
tests/test_turnos.py:    from src.database import async_session_maker ← 'async_session_maker' no definido
tests/test_migrations.py: from src.database import async_session_maker ← 'async_session_maker' no definido
```

**Causa raíz:** El postprocessor S122-A renombra la session factory a `get_session_factory()`. El modelo, sin saberlo, genera test files que importan el nombre original `async_session_maker` desde `src.database`.

---

## Estado S122 por fix

| Fix | Estado | Evidencia |
|---|---|---|
| **S122-A**: postprocessor reescribe engine module-level | ✅ **VALIDADO** | `[S122-A]` disparado 2 veces en logs |
| **S122-A paso 2**: variable arbitraria (no solo `AsyncSessionLocal`) | ✅ **VALIDADO** | `async_session_factory` convertida correctamente |
| **S122-B**: detección conftest→src.main en update_test_retry | ⚠️ **NO VERIFICADO** | No ocurrió el ImportError de conftest en este ciclo (S122-A lo previno) |

---

## Nuevo problema detectado: S123

### Descripción

El postprocessor S122-A reescribe la API pública de `database.py`:
- `AsyncSessionLocal` / `async_session_factory` → `get_session_factory()`
- `engine` → `get_engine()`

Pero el modelo genera test files que importan los **nombres originales** desde `src.database`:
```python
from src.database import async_session_maker  # ← no existe después de S122-A
from src.database import async_session_factory  # ← no existe después de S122-A
```

### Propuestas para S123

#### P1 — Prohibir imports de src.database en test files (CRÍTICO)

En `backend_python.md` y en el hint S121-C/S122-B: agregar regla explícita:

```
NUNCA en archivos de test/conftest:
  from src.database import ...
SIEMPRE:
  from src.main import app  (para fixture client)
  # Para fixtures de setup/teardown, crear engine propio:
  from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
  TEST_DATABASE_URL = "sqlite+aiosqlite:///test.db"
  test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
```

#### P2 — Postprocessor también revisa test files (ALTERNATIVO)

Escanear `tests/*.py` y reemplazar `from src.database import async_session_maker/AsyncSessionLocal/engine` por imports directos de SQLAlchemy o remove.

#### P3 — Agregar alias en database.py post-S122-A

Agregar al output de S122-A:
```python
# Legacy aliases (compatibilidad con tests generados)
AsyncSessionLocal = get_session_factory
async_session_maker = get_session_factory
```

(Menos limpio — expone nombres confusos)

**Recomendación:** P1 es la solución correcta — los test files deben ser self-contained y no depender de nombres internos de `src.database`.

---

## Comparación con ciclos anteriores

| Ciclo | Sprint | run_tests | QA mejor | Causa fallo principal |
|---|---|---|---|---|
| S120 | `a18c7b32` | FAIL | 93/100 | conftest `from src.database import` directo |
| S121 | `46d2d42a` | FAIL | 72/100 | `database.py` con engine module-level |
| **S122** | `7990efb6` | **FAIL** | **95/100** | test files importan nombres renombrados por S122-A |

**Progreso real:**
1. S121-B: conftest ya no importa `src.database` directamente ✅
2. S122-A: engine module-level ya no llega a pytest ✅
3. **Barrera actual:** test files con `from src.database import <nombre_renombrado>` ← S123

---

## Próximos pasos (S123)

1. `backend_python.md`: prohibir `from src.database import` en test files (S123-A)
2. Hint S121-C/S122-B: agregar patrón de test fixture con engine propio (S123-A)
3. Postprocessor `_fix_test_database_imports`: detectar y eliminar `from src.database import` en test files, reemplazar por fixture propio con SQLite in-memory (S123-B)
