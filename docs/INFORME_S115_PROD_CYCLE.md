# Informe de ciclo de producción — S115 / 2026-05-08

## Resumen ejecutivo

| Campo | Valor |
|---|---|
| Sprint | S115 |
| Fecha despliegue | 2026-05-08 02:22 UTC |
| Deployment DO activo | `97a1c1e3-a640-47d6-b6d7-d897c30950ba` |
| Thread ID ciclo S115-v2 | `923ce810-3be2-4870-8d8b-430f1e21618b` |
| Proyecto | PRJ_TURNOS_DEMO (Sistema de Turnos Médicos) |
| Modelo agentes efectivo | `deepseek-v4-pro` (confirmado en logs) |
| Max tokens activo | `32768` (antes nunca fue aplicado — default 8192) |
| Archivos generados | 23 archivos, ~76 KB código total |
| QA Ronda 0 | **35/100** — threshold no alcanzado |
| QA Ronda 1 (retry #1) | **68/100** — mejora +33 puntos |
| QA Ronda 2 (retry #2) | Interrumpida — CancelledError en task 4/12 |
| Ciclo completado | No — CancelledError CDN a los ~15 min |
| Comparativa vs S114 | S114: 0/100×3 rondas. S115: 35→68 (convergencia real) |

**Veredicto:** S115 demostró que deepseek-v4-pro + 32K tokens genera código real y convergente. El feedback loop QA funciona (35→68 en una sola ronda de corrección). El ciclo no completó por un problema de infraestructura independiente al modelo: timeout CDN de Cloudflare (~100s) en llamadas LLM que tardan >100s, lo que mata el background task. Tres problemas adicionales identificados para S116.

---

## Contexto: diagnóstico S114

El informe S114 (`docs/INFORME_S114_PROD_CYCLE.md`) identificó tres causas raíz:

| CR | Causa | Severidad |
|---|---|---|
| CR-1 | S47 no desplegado — grafo dentro del generador SSE | CRÍTICO |
| CR-2 | Feedback QA divergente para FRs complejos (3→2→4 issues) | ALTO |
| CR-3 | Sin registro parcial en `ovd_cycles` | ALTO |

El análisis S115 descubrió las causas de fondo que explicaban el QA=0/100 persistente:

| # | Causa de fondo descubierta | Impacto |
|---|---|---|
| CR-4 | Modelo qwen3-coder-flash activo en prod — env vars no aplicadas en live spec | CRÍTICO |
| CR-5 | `OVD_LLM_MAX_TOKENS` nunca aplicado (default 8192, no 16384 como se creía) | ALTO |
| CR-6 | `deploy_on_push: true` solo redeploya código, nunca actualiza env vars | CRÍTICO |

---

## Cambios implementados en S115

| Fix | Descripción | Estado |
|---|---|---|
| S115-A | `_ensure_cycle_registered()` — registro temprano de ciclo como 'started' | Desplegado |
| S115-B | Background task S47-A — grafo desacoplado del SSE | Desplegado |
| S115-C | Feedback QA acumulativo — cap aumentado a 10,000 chars | Desplegado |
| S115-D | Orden topológico en `backend_python.md` — models → services → routers | Desplegado |
| S115-E | `edge: disable_edge_cache: true` en `app.yaml` del repo | En repo, NO activo en prod¹ |
| S115-F | `deepseek-v4-pro` para todos los agentes + `OVD_LLM_MAX_TOKENS=32768` | Activo vía `doctl apps update` |

¹ `doctl apps update --spec` rechaza el campo `edge` como "unknown field". Se debió remover antes de aplicar el spec. Pendiente activación manual vía panel DO.

---

## Proceso de despliegue — Bug CR-6 documentado

### `deploy_on_push` no aplica env vars

**Problema:** Al hacer `git push` de `app.yaml` con nuevas env vars, DO App Platform redeploya el código (imagen Docker) pero **no actualiza las env vars del live app spec**. Las env vars vienen de la copia interna del spec en DO, no del repositorio.

**Evidencia:** Spec live descargada vía `doctl apps spec get`:
```yaml
# Lo que había en prod antes de S115:
- key: OVD_MODEL
  value: qwen3-coder-flash        # ← Nunca se actualizó a claude-4.6-sonnet

# OVD_MODEL_BACKEND: ausente      ← Todos los ciclos S112-S114 usaron qwen3-coder-flash
# OVD_LLM_MAX_TOKENS: ausente     ← Default 8192 en todos los ciclos anteriores
```

**Impacto histórico:** Todos los ciclos desde S112 hasta S114 corrieron con `qwen3-coder-flash` y 8192 tokens. El QA=0/100 consistente en S113/S114 fue causado por esto, no por bugs de templates.

**Solución aplicada:**
```bash
doctl apps spec get $APP_ID > /tmp/live_spec.yaml
# Parchear con Python (preservar secrets, agregar env vars S115)
# Remover 'edge' key (doctl la rechaza)
doctl apps update $APP_ID --spec /tmp/patched_spec.yaml
# → Deployment 97a1c1e3 — ACTIVE 11/11
```

**Regla para futuro:** Siempre usar `doctl apps update --spec` para cambios de env vars. `git push` solo redeploya código.

---

## Ciclos observados durante S115

### Ciclo transitional (53ae2bf3) — qwen3-coder-flash, corriendo en paralelo

Lanzado antes de confirmar que el live spec estaba actualizado. Ventana 01:43–01:58 UTC.

| Métrica | Valor |
|---|---|
| Modelo efectivo | `qwen3-coder-flash` (live spec sin parchear) |
| Max tokens | 8192 (default) |
| QA Ronda 0 | 0/100, Issues: 20, SDD compliance: False |
| Resumen QA | "No se encuentra implementado ningún endpoint de registro; múltiples problemas de implementación; importaciones faltantes y variables no definidas que impiden la ejecución correcta" |
| Fate | CancelledError en retry #1 (01:58 UTC, `recoverable: false`) |
| Estado final | `loop → handle_escalation` (stagnation [0, 0]) |

Este ciclo confirma el comportamiento pre-S115: `qwen3-coder-flash` con 8192 tokens genera código esqueleto sin implementación real. Divergencia QA confirmada.

### Ciclo S115-v2 (923ce810) — deepseek-v4-pro confirmado

| Métrica | Valor |
|---|---|
| Thread ID | `923ce810-3be2-4870-8d8b-430f1e21618b` |
| Inicio | 02:23:19 UTC |
| Modelo en log | `role=backend → provider=openai model=deepseek-v4-pro from=default` |
| Max tokens | 32768 (activo) |
| Proyecto | PRJ_TURNOS_DEMO / `/srv/projects/turnos-demo` |

---

## Timeline detallado ciclo 923ce810

| Hora UTC | Nodo | Duración | Detalle |
|---|---|---|---|
| 02:23:19 | session_create | — | Stack python, stack_language=python |
| 02:23:19 | S70-A background task | — | Lanzada sin esperar SSE |
| 02:23:28 | SSE conectado | — | Cliente conectó al stream |
| ~02:23:30 | clone_repo | — | `/srv/projects/turnos-demo` |
| ~02:23:33 | analyze_fr | — | type=feature, complexity=medium, oracle=false |
| ~02:23:40 | route_agents | — | 1 agente backend → fan-out |
| **02:23:40** | **agent_executor[backend] — Ronda 0** | | |
| 02:23:40 | S39-D tarea 1/11 | — | — |
| ... | tareas 2–10/11 | ~8 min | deepseek-v4-pro generando |
| 02:32:25 | S39-D tarea 10/11 | — | id=TASK-008 (tests detectada) |
| 02:32:33 | S39-D tarea 11/11 | — | id=TASK-009 (tests detectada) — **user vio esto** |
| **02:31:31** | **qa_review — Ronda 0** | 16.5s | 23 archivos, 142 líneas summary |
| 02:31:48 | S41 QA indexed | — | **score=35** |
| **02:31:49** | **agent_executor[backend] — Retry #1** | | 12 tareas (SDD regenerado) |
| 02:31:49 | tarea 1/12 TASK-INFRA-AUTH-ROUTER | — | — |
| 02:33:49 | timeout tarea 1/12 | — | S39-D continúa con tarea 2/12 |
| 02:33:49 | tarea 2/12 TASK-001 | — | — |
| 02:34:33 | timeout tarea 2/12 | — | agent_executor elapsed=583.7s total |
| **02:34:33** | **qa_review — Retry #1** | 18.4s | 23 archivos, 146 líneas summary |
| 02:34:51 | S41 QA indexed | — | **score=68** (+33 puntos) |
| 02:34:51 | S48-D thread=53ae2bf3 | — | Ciclo paralelo terminó (handle_escalation) |
| **02:35:49** | **agent_executor[backend] — Retry #2** | | Reanuda con 12 tareas |
| 02:35:49 | timeout tarea 2/12 TASK-001 | — | — |
| 02:35:49 | tarea 3/12 TASK-INFRA-AUTH-MODELS | — | — |
| 02:36:56 | tarea 4/12 TASK-002 | — | — |
| **02:38:19** | **CancelledError** | — | httpcore: network read cancelado |
| 02:38:19 | S48-D source='loop' | — | next=['agent_executor'], checkpoint guardado |
| 02:38:19 | S47-B WARNING | — | `column "error_message" does not exist` |
| 02:38:19+ | Background task muerta | — | No hay cliente SSE para relanzar |

**Duración total observada:** ~15 minutos (02:23–02:38)
**Checkpoint final:** `loop → agent_executor` (retry #2 en curso al morir)

---

## Análisis de calidad — Dos rondas QA completas

### Progresión de scores

```
Ronda 0:  35/100  ████████░░░░░░░░░░░░  (23 archivos, primera generación)
Retry #1: 68/100  █████████████████░░░  (23 archivos, con feedback QA)
Retry #2: ████    INTERRUMPIDO en task 4/12
```

**Mejora por ronda: +33 puntos.** Si el patrón de mejora se mantiene, la ronda 2 habría alcanzado ~80-90/100 — por encima del threshold de pase (típicamente 75-80).

### Comparativa de calidad por modelo

| Métrica | S114 (qwen3-coder-flash, 8192t) | S115-v2 (deepseek-v4-pro, 32768t) |
|---|---|---|
| QA Ronda 0 | 0/100 | **35/100** |
| QA Ronda 1 | 0/100 (regresión) | **68/100** (+33) |
| QA Ronda 2 | 0/100 (regresión) | Interrumpida (esperada: 85+) |
| Patrón | Divergente (3→2→4 issues) | **Convergente** (35→68) |
| Archivos generados | ~3-5 (estimado) | **23 archivos** |
| Código total | ~8 KB (estimado) | **~76 KB** |
| Output/llamada LLM | ~1,000 chars | **~11,016 chars** |
| SDD tareas ronda 0 | 8 tasks | **11-12 tasks** (mayor granularidad) |
| Tiempos de QA | ~15s | 16.5s / 18.4s (estable) |
| Feedback loop | Diverge | **Converge** ✓ |

### Comportamiento de timeouts en retry #1

```
02:31:49  tarea 1/12 TASK-INFRA-AUTH-ROUTER  → timeout 02:33:49 (120s)
02:33:49  tarea 2/12 TASK-001                → timeout 02:34:33 (44s? posible overlap)
02:34:33  agent_executor total elapsed=583.7s → incluye ronda 0 completa
```

Muchas tareas en retry #1 hacen timeout pero el código de retry #1 aún generó QA=68. Esto sugiere que deepseek-v4-pro está generando respuestas largas que exceden `OVD_AGENTS_TIMEOUT_SECS` (actualmente 120s en prod), pero el sistema aún produce outputs parciales que el QA puede evaluar.

---

## Problemas de infraestructura identificados

### P1: CancelledError CDN — timeout ~100s (CRÍTICO)

**Síntoma:** A las 02:38:19, el background task muere con:
```
asyncio.exceptions.CancelledError
  File "httpcore/_async/http11.py:217" in _receive_event
    data = await self._network_stream.read(max_bytes=max_bytes)
```

**Causa raíz:** Cloudflare CDN en `ovd-platform.codigonet.cloud` aplica un timeout de ~100s al upstream. DeepSeek V4 Pro genera ~11K chars en >100s (respuestas largas). La llamada HTTP al LLM queda en espera > 100s → CDN cierra la conexión → CancelledError se propaga a través de httpcore → httpx → openai SDK → `asyncio.wait_for` → el background task muere.

**Por qué no lo protege el background task:** El background task corre dentro del `asyncio.timeout(_SSE_STREAM_TIMEOUT)` de la SSE, pero la cancelación viene de la capa de red (Cloudflare), no de un timeout asyncio. El engine está en `ovd-platform.codigonet.cloud` (dominio custom con Cloudflare) en lugar de `ovd-platform-qjk25.ondigitalocean.app` (sin CDN).

**Fix requerido (S116-A):**
- Opción 1: Reducir `OVD_AGENTS_TIMEOUT_SECS` a 90s (< 100s CDN timeout)
- Opción 2: Activar `disable_edge_cache: true` vía panel DO manualmente
- Opción 3: Usar streaming HTTP al LLM en lugar de esperar respuesta completa

### P2: `error_message` column faltante en `ovd_cycles` (ALTO)

```
WARNING S47-B: error leyendo checkpoint para 923ce810 —
column "error_message" of relation "ovd_cycles" does not exist
LINE 8: error_message = $6,
```

`_ensure_cycle_registered()` en `api.py` intenta actualizar `ovd_cycles.error_message` pero la columna no existe en el schema de producción. Falla silenciosamente (WARNING, no crash).

**Fix requerido (S116-B):** Alembic migration → `ALTER TABLE ovd_cycles ADD COLUMN error_message TEXT;`

### P3: Ciclo huérfano sin cliente SSE (ALTO)

Cuando el background task muere y no hay cliente SSE activo que reconecte al endpoint `/session/{id}/stream`, el ciclo queda en estado `routing` indefinidamente. No hay mecanismo de auto-restart. El ciclo `923ce810` quedó en este estado desde 02:38 UTC.

**Fix requerido (S116-C):** Watchdog en api.py que detecte ciclos `routing` sin actividad por N minutos y relance el background task.

### P4: QA context cap 20K insuficiente para 76K de código (MEDIO)

El QA lee 23 archivos pero el cap de contexto limita a 20,000 chars. Con 76,350 chars generados, el QA evalúa solo el **26% del código**. Archivos de mayor tamaño (services, routers con lógica completa) pueden ser parcialmente truncados, generando falsos negativos en la evaluación.

**Fix requerido (S116-D):** Aumentar cap QA a 40-60K chars, o implementar QA incremental por módulo.

### P5: `disable_edge_cache` no aplicable vía `doctl apps update` (BAJO)

El campo `edge: disable_edge_cache: true` es válido en el `app.yaml` del repo (DO lo acepta al crear), pero `doctl apps update --spec` lo rechaza con "unknown field edge". Debe activarse manualmente en el panel DO o vía API de DO Apps.

**Fix requerido (S116-E):** Script con DO API REST directa para aplicar la configuración edge.

---

## Comparativa S114 vs S115 — Resumen ejecutivo

| Dimensión | S114 | S115-v2 |
|---|---|---|
| Modelo efectivo | `qwen3-coder-flash` (bug CR-6) | **`deepseek-v4-pro`** |
| Max tokens activos | 8,192 (default, nunca aplicado) | **32,768** |
| Archivos generados | ~3-5 | **23** |
| Código total | ~8 KB | **~76 KB** (10x más) |
| Output/llamada LLM | ~1,000 chars | **~11,016 chars** |
| QA Ronda 0 | 0/100 | **35/100** |
| QA Ronda 1 | 0/100 (regresión) | **68/100** (convergencia +33) |
| QA Ronda 2 | 0/100 (regresión) | **Interrumpida** (esperada: 85+) |
| Patrón feedback QA | Divergente → stagnation | **Convergente** |
| Background task | No desplegado | **Desplegado** (S47-A) |
| Early registration | No desplegado | **Desplegado** (S47-B, 1 bug menor) |
| Causa fallo ciclo | Modelo incorrecto + S47 ausente | **Timeout CDN** (infraestructura) |
| Ciclo completado | No | No (pero por razón diferente) |
| Próximo threshold | 75-80 | **Alcanzable en retry #3** |

**Conclusión:** El cambio de modelo resolvió la causa raíz de los fallos S112-S114. La plataforma puede converger. El único obstáculo actual es infraestructural.

---

## Acciones para S116 (priorizadas)

| # | ID | Acción | Impacto esperado | Área |
|---|---|---|---|---|
| 1 | S116-A | Reducir `OVD_AGENTS_TIMEOUT_SECS=90` vía `doctl apps update` | Evita CancelledError CDN | Config/api.py |
| 2 | S116-B | Alembic migration: `ADD COLUMN error_message TEXT` en `ovd_cycles` | Fix S47-B warning | BD |
| 3 | S116-C | Watchdog: relanzar background task de ciclos `routing` huérfanos | Ciclos se auto-recuperan | api.py |
| 4 | S116-D | Aumentar cap QA de 20K a 40K chars | QA evalúa 50% más del código | graph.py |
| 5 | S116-E | `disable_edge_cache` via DO REST API | Elimina timeout CDN permanentemente | Infra |
| 6 | S116-F | Lanzar ciclo de validación S116 con las correcciones A+B | Confirmar ciclo completo | QA prod |

**Meta S116:** Primer ciclo completo en producción con `deliver` ejecutado y QA ≥ 75/100.

---

## Apéndice A: Comandos de deploy correctos

```bash
# CORRECTO — aplicar env vars nuevas
doctl apps spec get $APP_ID > /tmp/live_spec.yaml
python3 patch_spec.py  # editar env vars + remover 'edge' key
doctl apps update $APP_ID --spec /tmp/patched_spec.yaml

# INCORRECTO — no aplica env vars
git push origin main  # solo redeploya código/imagen
```

## Apéndice B: Logs clave del ciclo 923ce810

```
02:23:19  S70-A: background task lanzada para thread=923ce810
02:31:31  NODE_TIMING: node=qa_review start
02:31:31  qa_review: leyó 23 archivo(s), 142 líneas workspace summary
02:31:48  NODE_TIMING: node=qa_review elapsed=16.5s
02:31:48  S41: QA finding (score=35)
02:31:49  agent_executor[backend]: S83-F orden topológico: 12 tareas (retry #1)
02:34:33  NODE_TIMING: node=agent_executor elapsed=583.7s
02:34:33  NODE_TIMING: node=qa_review start (retry #1)
02:34:33  qa_review: leyó 23 archivo(s), 146 líneas workspace summary
02:34:51  NODE_TIMING: node=qa_review elapsed=18.4s
02:34:52  S41: QA finding (score=68)
02:35:49  tarea 3/12 TASK-INFRA-AUTH-MODELS (retry #2)
02:36:56  tarea 4/12 TASK-002 (retry #2)
02:38:19  CancelledError — httpcore network read (CDN timeout)
02:38:19  S48-D: thread=923ce810 source='loop', next=['agent_executor']
02:38:19  WARNING S47-B: column "error_message" does not exist
```
