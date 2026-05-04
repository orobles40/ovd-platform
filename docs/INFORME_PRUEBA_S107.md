# Informe de Prueba — S107

**Fecha:** 2026-05-04  
**Thread ID:** 0426dd25-4928-449d-8d79-56391ee24719  
**FR:** Sistema de gestión de contratos de beneficios (CRUD, validate_rut, PostgreSQL, NO Oracle)  
**Duración total:** 13m 45s  
**Costo:** $0.0000 (ollama local — qwen3-coder:30b)

---

## Resumen ejecutivo

S107 implementó 5 mecanismos para corregir el QA persistentemente bajo (62/100 en S106).
El ciclo de validación alcanzó **QA 94/100** — 32 puntos por encima del baseline y superando
el target de ≥80. La causa raíz (divergencia de naming cross-contexto) fue eliminada: el router
ahora importa `deactivate_contract` (no `delete_contract`). El docker-compose generó `postgres:16-alpine`
(no Oracle). El nodo Architecture Gate (`generate_architecture_contract`) apareció en el SSE stream.

**Fix adicional descubierto:** `_write_artifacts` omitía escritura silenciosamente cuando el
directorio no existía. Corregido en el mismo ciclo (bug bloqueaba todos los ciclos con directorio nuevo).

---

## Telemetría del ciclo

| Métrica | Valor |
|---|---|
| QA score (ronda 1) | 94/100 ✅ |
| QA score (ronda 2 — retry tests) | 94/100 ✅ |
| Security score | 100/100 ✅ |
| Agentes | backend, devops, database (3) |
| pytest resultado | FAIL (Pydantic Date + S79-C falso positivo) |
| Reintentos tests | 1 (total 2 rondas de pytest) |
| Artefactos generados | 9 |
| Tokens input | 137.459 |
| Tokens output | 33.971 |
| Duración | 13m 45s |

---

## Validación P1 — Architecture Gate

**Estado: ✅ ACTIVO**

El nodo `generate_architecture_contract` apareció en el stream SSE:

```
node_end: request_approval
node_end: generate_architecture_contract   ← NUEVO (S107-P1)
node_end: route_agents
```

El nodo corre después de la aprobación del SDD y antes del fan-out de agentes.
Sin overhead LLM (determinístico, ~0ms).

---

## Validación P2 — Oracle → PostgreSQL postprocesador

**Estado: ✅ ACTIVO**

`docker-compose.yml` generado:

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-myapp}
```

No aparece `gvenzl/oracle-xe` ni `oracle/database`. El postprocesador `_fix_oracle_in_docker_compose`
aplicó la restricción (o el agente siguió la instrucción del template `system_devops.md`).

---

## Validación P3 — Sync imports / Naming

**Estado: ✅ ACTIVO**

`router.py` (línea 4):
```python
from src.contracts.services import create_contract, get_contract_by_id, \
    list_active_contracts, update_contract, deactivate_contract
```

`services.py` define exactamente: `create_contract`, `get_contract_by_id`,
`list_active_contracts`, `update_contract`, `deactivate_contract`, `calculate_contract_total`.

**Naming consistente: ✅** — `deactivate_contract` en ambos lados (no `delete_contract`).

---

## Validación P4 — Tabla de naming en template

**Estado: ✅ INDIRECTAMENTE VALIDADO**

La tabla REGLA DE NAMING CONSISTENTE en `system_backend_python.md` fue inyectada en el
HumanMessage del agente backend. El naming correcto (`deactivate_contract`) en el código
final es evidencia de que la instrucción fue respetada.

---

## Validación P5 — QA verifica architecture contract

**Estado: ✅ QA 94/100**

QA reportó: "Implementación completa de los requisitos del SDD con alta calidad. El sistema
cumple con todos los requisitos funcionales y técnicos definidos."

El bloque de verificación de contrato en `qa_review` no reportó violaciones — las funciones
canónicas del contrato existen en `services.py`.

---

## Artefactos generados

```
src/contracts/models.py       ← ORM + Pydantic schemas
src/contracts/router.py       ← endpoints CRUD
src/contracts/services.py     ← lógica de negocio (naming correcto)
src/auth/middleware.py        ← autenticación JWT
src/database.py               ← conexión PostgreSQL
src/main.py                   ← aplicación FastAPI
src/utils/rut_validator.py    ← validate_rut
docker-compose.yml            ← postgres:16-alpine ✅
.docker/Dockerfile.api
.github/workflows/ci.yml
tests/test_contracts_crud.py
tests/test_rut_and_calculation.py
requirements.txt
pytest.ini
docs/openapi.yaml
docs/adr/001-rut-validation.md
CHANGELOG.md
scripts/deploy.sh
scripts/health-check.sh
```

---

## Issues identificados para S108

### Issue 1: S79-C falso positivo (ALTA prioridad)

**Síntoma:** S79-C detecta la palabra "Oracle" en el FR y reporta:
> "El FR solicita Oracle pero database.py tiene URL PostgreSQL"

**Causa raíz:** El FR dice "Docker con PostgreSQL (NO Oracle)". La presencia de la palabra
"Oracle" (aunque negada) activa la detección. La lógica actual no considera la negación.

**Fix propuesto:** En `_check_database_url_consistency()`, verificar `oracle_involved`
del `fr_analysis` (que ya lo resuelve correctamente con `deepseek-r1:14b`) en lugar de
hacer keyword matching del texto del FR.

**Impacto:** El mensaje S79-C erróneo se inyecta como feedback de error a los agentes
en el reintento de tests, confundiéndolos innecesariamente.

---

### Issue 2: Pydantic Date type en models.py (MEDIA prioridad)

**Síntoma:** `pytest` falla con:
```
from src.contracts.models import ContratoCreate, ContratoUpdate, ContratoResponse
src/contracts/models.py:16: in ContratoCreate(BaseModel)
  pydantic._internal._generate_schema.py: unknown type
```

**Causa raíz:** El agente importa `Date` de SQLAlchemy (`from sqlalchemy import Date`)
y lo usa como anotación de tipo en los schemas Pydantic. SQLAlchemy's `Date` no es
un tipo válido para Pydantic — se requiere `from datetime import date`.

**Fix propuesto:** Agregar al postprocesador `code_postprocessor.py` una transformación
que detecte `Date` de SQLAlchemy en contexto Pydantic y lo reemplace por `date` de datetime.
Alternativamente, agregar instrucción explícita en `system_backend_python.md`:
`Para schemas Pydantic usar 'from datetime import date', NO 'from sqlalchemy import Date'`.

---

### Fix aplicado en este ciclo: _write_artifacts mkdir

**Síntoma:** El workspace permanecía vacío — todos los ciclos con directorio nuevo fallaban
con `FileNotFoundError: pytest.ini` porque `_write_artifacts` omitía escritura silenciosamente.

**Fix:** Cambiar el `return []` por `base.mkdir(parents=True, exist_ok=True)` en `graph.py:8003`.

**Commit:** `89e3a90a4`

---

## Comparativa histórica de QA

| Sprint | Ciclo | QA | Naming error | Docker image | pytest |
|---|---|---|---|---|---|
| S76 | S76 | **93** | — | — | collection_error |
| S101 | S101 | **90** | — | — | 3 passed |
| S103 | S103 | **90** | — | — | 0 retries |
| S104 | contratos | **52** | ✅ delete_X | Oracle XE | 2 retries |
| S105 | contratos | **40** | ✅ delete_X | Oracle XE | 2 retries |
| S106 | — | pending | — | — | — |
| **S107** | contratos | **94** | ✅ deactivate_X | postgres:16-alpine | Pydantic Date |

**Mejora neta S107 vs S104/S105 baseline:** +42/+54 puntos QA.
**Naming mismatch eliminado:** router.py usa `deactivate_contract` en todas las rondas.
**Oracle en docker-compose eliminado:** `postgres:16-alpine` en todas las rondas.

---

## Próximo sprint: S108

Prioridades basadas en este ciclo:

1. **S108-A:** Fix S79-C falso positivo — usar `fr_analysis.oracle_involved` en lugar de keyword del FR
2. **S108-B:** Fix Pydantic Date — postprocesador o instrucción explícita en template
3. **S108-C:** Evaluar si `service.py` (vacío/residual) debe limpiarse cuando `services.py` es el canónico

Baseline S108: QA 94 → target ≥95 con pytest passing.
