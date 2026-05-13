# Informe de Validación — S133

**Fecha:** 2026-05-13
**Thread ID:** `079611ff-76c6-4d59-a0a4-a8ed885e93d5`
**Feature:** Implementar módulo de agendamiento de turnos médicos
**Complejidad:** medium (no registrada en session_meta — ver bug S132-H1)

---

## Resumen ejecutivo

El ciclo S133 corrió 3 rondas de QA (68→55→68) antes de ser cancelado por el heartbeat watcher a los 30 minutos. La cancelación fue causada por un bug en S132-H1: la complejidad del ciclo no está disponible en `session_meta` al momento del registro inicial de la sesión, por lo que el umbral adaptativo devuelve el default (30 min) en lugar de los 60 min que corresponden a complexity=medium. S133-C (postprocessor @classmethod duplicado) mostró mejora marginal en QA vs S132.

---

## Resultado por hipótesis S133

| Hipótesis | Descripción | Resultado |
|---|---|---|
| S133-C — `_fix_duplicate_classmethod` | Elimina `@classmethod` duplicados post-S77B | **PARCIALMENTE VALIDADO** — QA 68/55/68 vs S132 55/62/45/35 |
| S133-B — Retry full-delivery | Preamble indica entregar todos los archivos | No observable directamente en este ciclo |
| S133-A — Alerta template | Aviso S133-A en backend_python.md | Template change, sin medición directa |

---

## Trayectoria QA

| Ronda | QA Score | Umbral | Estado |
|---|---|---|---|
| 0 | 68/100 | 70 | FAIL |
| 1 | 55/100 | 70 | FAIL |
| 2 | 68/100 | 70 | FAIL |
| — | — | — | Cancelado por heartbeat a 30 min |

Comparación con S132 (mismo feature): 55 → 62 → 45 → 35. El postprocessor S133-C aplanó la regresión acumulativa (el score no cayó a 35 en ronda 3), aunque no fue suficiente para superar el umbral.

---

## Bug detectado: S132-H1 regression

### Causa raíz

El `_threshold_for_session()` usa la `complexity` almacenada en `session_meta`. La `session_meta` se registra en `_run_graph_background` al inicio del stream, antes de que `analyze_fr` ejecute y determine la complejidad:

```python
# _run_graph_background (api.py)
snap = await _graph.aget_state(config)
if snap and snap.values:
    v = snap.values
    session_meta = {
        ...
        "complexity": (v.get("fr_analysis") or {}).get("complexity", ""),  # "" si analyze_fr no corrió aún
    }
register_session(thread_id, session_meta)
```

En la primera sesión de un thread nuevo, `fr_analysis` no existe → `complexity=""` → `_threshold_for_session` retorna el default (30 min).

El log confirmó: `elapsed=30min (umbral=30min complexity=)`.

### Impacto

Todos los ciclos medium/high/critical con más de 30 minutos de ejecución serán cancelados prematuramente. El umbral adaptativo de S132-H1 nunca se activa porque la complexity siempre es vacía al momento del registro.

---

## Incidente: crashloop por reconexiones agresivas

Un monitor loop con reconexiones cada 10s causó saturación de conexiones DB (una por reconexión) en el container `professional-xs` (512MB), causando OOM y crashloop durante ~8 minutos (18:36–18:42).

**Lección:** El monitor SSE debe conectar **una sola vez** sin loop de reconexión agresivo. El DO App Platform `professional-xs` no aguanta burst de conexiones simultáneas.

---

## Acciones propuestas para S134

### S134-A — Fix S132-H1: actualizar complexity post-analyze_fr [CRÍTICO]

El `session_meta` debe actualizarse cuando `analyze_fr` completa y la complexity queda disponible en el estado del grafo.

**Fix propuesto en `api.py` — `_run_graph_background`:**

Después de registrar la sesión, suscribirse a eventos del grafo para actualizar `session_meta` cuando llegue el nodo `analyze_fr`:

```python
# En _run_graph_background, dentro del loop de eventos:
async for event in _stream_graph_events(thread_id, config):
    # S134-A: actualizar complexity en session_meta cuando analyze_fr complete
    if event_indicates_analyze_fr_complete(event):
        snap = await _graph.aget_state(config)
        if snap and snap.values:
            new_complexity = (snap.values.get("fr_analysis") or {}).get("complexity", "")
            if new_complexity:
                _active_sessions[thread_id]["complexity"] = new_complexity
    await queue.put(event)
```

O alternativa más simple: en `detect_stale_sessions`, re-leer la complexity desde el checkpoint antes de calcular el threshold (en lugar de depender del session_meta registrado al inicio).

### S134-B — Límite de reconexiones en monitor SSE [ALTO]

El dashboard y TUI deben implementar backoff exponencial para reconexiones SSE:
- Primera reconexión: después de 30s
- Reconexiones siguientes: +30s adicionales hasta máximo 5 min
- Evitar bursts de conexiones simultáneas

### S134-C — Validar QA score con S133-C activo [MEDIO]

Lanzar un ciclo de validación controlado sin interrupciones para medir el impacto real de `_fix_duplicate_classmethod`:
- Ajustar threshold a 90 min (critical) para evitar cancelación prematura
- O corregir S134-A primero y luego relanzar

---

## Conclusión S133

Los cambios de S133 fueron desplegados y commitados correctamente:
- **S133-C**: `_fix_duplicate_classmethod` postprocessor activo en producción
- **S133-B**: retry preamble actualizado con instrucción de entrega completa
- **S133-A**: alerta de alta visibilidad en `backend_python.md`
- **15 tests**: 15/15 PASS, 2188 regresión PASS

La validación del impacto en QA scores quedó incompleta por dos bloqueos:
1. Bug S132-H1 (complexity="" → umbral 30 min insuficiente para ciclos medium/long)
2. Crashloop por monitor agresivo (resuelto)

El bloqueante prioritario para S134 es S134-A (fix S132-H1).
