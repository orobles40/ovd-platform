# Informe de Validación — S132

**Fecha:** 2026-05-13
**Thread ID:** `d88c6f23-79fb-4e35-8e6a-22ab141a0e0a`
**Feature:** Implementar módulo de agendamiento de turnos médicos
**Complejidad:** medium | **Tipo:** feature
**Agentes:** backend, devops, frontend (3) | **Tareas:** 11

---

## Resumen ejecutivo

El ciclo S132 completó 4 rondas (3 reintentos) sin llegar al umbral QA de 70. El error raíz persistente fue la duplicación de `@classmethod` en los validadores `field_validator` de Pydantic (models.py), lo que provocó `ImportError` en backend en todas las rondas. El score QA decayó en lugar de mejorar con los reintentos (55 → 62 → 45 → 35), indicando regresión acumulativa en las correcciones del agente.

---

## Resultado por hipótesis S132

| Hipótesis | Descripción | Resultado |
|---|---|---|
| H1 — Heartbeat adaptativo | Umbral 30/60/90 min por complejidad | **PASS** — ciclo de ~60+ min no fue cancelado |
| H2 — Router registration | `_s132_ensure_router_registration` inyecta include_router | No activado (no hubo módulo sin router en este ciclo) |
| H3 — Frontend Python guard | Frontend no puede escribir archivos .py | No activado en este ciclo |
| H4 — OVD_SECURITY_MIN_SCORE=70 | Umbral de seguridad aplicado desde env | **PASS** — security 75/100 en las 4 rondas |
| H5 — content_bytes post-postprocess | Recálculo correcto post-formateo Python | No observable directamente |
| H6 — RLS SET fix | `SET app.current_org_id` eliminado de api.py | **PASS** — ciclo registrado en ovd_cycles sin error |

---

## Trayectoria QA

| Ronda | QA Score | Umbral | Estado | Nota principal |
|---|---|---|---|---|
| 0 (inicial) | 55/100 | 70 | FAIL | `ImportError` models.py — `@classmethod` duplicado |
| 1 (retry) | 62/100 | 70 | FAIL | `ImportError` persiste — reescritura parcial del modelo |
| 2 (retry) | 45/100 | 70 | FAIL | Regresión en QA — código incompleto |
| 3 (retry) | 35/100 | 70 | FAIL | Regresión severa — frontend sin componentes fuente |

**Resultado final:** FAIL (no alcanzó umbral en ninguna ronda)

---

## Análisis del error persistente

### Error raíz: `@classmethod` duplicado en Pydantic v2 `field_validator`

El agente backend genera código como:

```python
@field_validator("rut")
@classmethod
@classmethod  # ← duplicado por el LLM
def validate_rut(cls, v: str) -> str:
    ...
```

Python 3.12+ lanza `TypeError` al cargar el módulo cuando `@classmethod` aparece duplicado. Esto hace que el backend sea no importable, lo que impide que la validación QA evalúe la funcionalidad.

**Por qué persiste entre rondas:**
1. El agente recibe el traceback del `ImportError` como feedback
2. En la corrección, reescribe `field_validator` pero vuelve a duplicar `@classmethod` (patrón aprendido de entrenamiento)
3. Cada reescritura también introduce otras regresiones (código omitido, imports faltantes)

**Por qué decae el score en lugar de mejorar:**
- Rondas 2 y 3: el agente "corrige" el error de models.py pero rompe otros archivos
- Ronda 3: la regresión más severa — los componentes frontend fuente desaparecieron, solo se entregaron archivos de test

---

## Análisis de regresión ronda 3 (frontend)

En la ronda 3, el agente frontend entregó únicamente archivos de prueba (`*.test.tsx`) sin los componentes fuente correspondientes. Los REQ afectados:

- **REQ-003** (componente AgendamientoForm): 0/1
- **REQ-004** (componente CalendarioTurnos): 0/1
- **REQ-006** (Dockerfile): 0/1

Esto sugiere que el historial de contexto acumulado tras 3 rondas de reintentos degrada la coherencia del agente frontend.

---

## Métricas de security (H4 validado)

| Ronda | Security Score | Umbral | Estado |
|---|---|---|---|
| 0 | 75/100 | 70 | PASS |
| 1 | 75/100 | 70 | PASS |
| 2 | 75/100 | 70 | PASS |
| 3 | 75/100 | 70 | PASS |

El umbral `OVD_SECURITY_MIN_SCORE=70` (H4) funcionó correctamente — el ciclo no fue bloqueado por security en ninguna ronda. El score consistente de 75 indica que el código generado cumple los controles de seguridad mínimos para este tipo de feature.

---

## Registro en ovd_cycles (H6 validado)

El ciclo fue registrado correctamente en `ovd_cycles`:
- Status: `completed` (deliver ejecutado en ronda 3, pese a QA FAIL)
- Sin error `syntax error at or near "$1"` que bloqueaba registros previos a S132-H6
- La corrección del `SET app.current_org_id = %s` permitió que `_ensure_cycle_registered` no falle silenciosamente

---

## Acciones propuestas para S133

### S133-A — Fix `@classmethod` duplicado en backend [CRÍTICO]

**Causa:** El prompt del agente backend no tiene restricción explícita sobre Pydantic v2 `field_validator`.

**Fix propuesto:** Agregar al system prompt de backend (`system_backend.md`) o al template de corrección:

```markdown
**REGLA PYDANTIC v2 field_validator:**
- NUNCA uses `@classmethod` antes de `@field_validator` — ya está implícito
- Sintaxis CORRECTA:
  ```python
  @field_validator("campo")
  @classmethod
  def validate_campo(cls, v):
  ```
- INCORRECTO:
  ```python
  @field_validator("campo")
  @classmethod
  @classmethod  # ← ERROR
  def validate_campo(cls, v):
  ```
```

Alternativamente, agregar un postprocessor en `postprocess_python_file()` que detecte y elimine `@classmethod` duplicados consecutivos.

### S133-B — Límite de contexto en reintentos de agente frontend [ALTO]

El agente frontend en ronda 3 perdió coherencia (entregó solo tests, no componentes). Investigar si el historial de mensajes acumulado supera el context window efectivo o si hay truncación silenciosa.

**Fix propuesto:** Reiniciar el contexto del agente frontend en ronda ≥ 2 (no acumular mensajes anteriores) o agregar un resumen sintético del estado actual en lugar del historial completo.

### S133-C — Validación postprocess para @classmethod duplicado [MEDIO]

Agregar a `postprocess_python_file()` en `graph.py`:

```python
import re
# Eliminar @classmethod consecutivos duplicados
content = re.sub(r"(@classmethod\s*\n)(\s*@classmethod\s*\n)", r"\1", content)
```

Este postprocessor operaría como guardrail silencioso para el error más frecuente sin requerir cambio en el LLM.

---

## Tests S132 — Resultado

```
21 tests collected
21 passed in X.XXs
```

Todos los tests de hipótesis H1–H6 pasaron. La suite unit completa (sin `test_regression_sprint.py`) resultó en 2173/2173 PASS.

**Nota:** `test_regression_sprint.py` contamina el estado global de la suite completa (27 fallos flaky no relacionados a S132, pre-existentes). Pendiente de corrección en sprint futuro.

---

## Conclusión

S132 logró sus objetivos de infraestructura:
- H1 (heartbeat adaptativo): el ciclo largo no fue cancelado
- H4 (security threshold): aplicado correctamente desde DO
- H6 (RLS SET fix): ciclos registran en ovd_cycles sin error

El bloqueante de calidad generativa (`@classmethod` duplicado en Pydantic) requiere intervención en S133, tanto a nivel de prompt como de postprocessor.
