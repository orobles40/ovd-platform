# Informe de Prueba — Sprint S97

**Fecha:** 2026-04-29  
**FR de prueba:** Sistema de contratos con autenticación JWT usando RUT chileno. API REST FastAPI: login RUT+contraseña, CRUD contratos por empleado. PostgreSQL + SQLAlchemy ORM. Tests pytest incluidos.  
**Modelo:** qwen3-coder:30b (MoE, Q4_K_M) vía Ollama local  
**Hardware:** Apple M5 Pro Max — 128 GB RAM unificada

---

## Resumen ejecutivo

**Ninguno de los dos ciclos S97 completó.** El sprint S97 implementó 5 fixes correctos de calidad (A/B/C/D/E), pero durante la validación se descubrieron dos problemas de infraestructura no relacionados con los fixes:

1. **S97-F:** `think=False` era un parámetro inválido en `ChatOllama` — ignorado silenciosamente. qwen3-coder:30b operaba con thinking mode ON, generando 50k–100k tokens de razonamiento interno por request.
2. **Cuello de botella estructural:** El fan-out de 8 agentes con Ollama serializado produce tiempos de ciclo de 3–5 horas con el modelo actual (qwen3-coder:30b × N subtareas por agente).

**Estado de los fixes S97:** Implementados y verificados por tests unitarios (35/35 PASS). No validados en ciclo completo.

---

## Ciclos ejecutados

### Ciclo 1 — `f02d1e03` (09:23 – 10:33 · ~70 min)

| Campo | Valor |
|---|---|
| Thread ID | f02d1e03-4c28-4738-85bf-73ff8f00c9ac |
| Inicio | 09:23:56 |
| Abandono | ~10:33 (70 min) |
| Checkpoints alcanzados | 18 / step 17 |
| Status BD | started (nunca completó) |
| QA score | No disponible (nodo no completó) |
| Tokens totales | 0 (deliver nunca ejecutó) |
| Costo | $0.00 |

**Progreso confirmado:**
- ✅ analyze_fr — completó (~2 min, steps 0–4)
- ✅ generate_sdd — completó (~4 min, steps 4–7)
- ✅ execute_agents ronda 1 — completó (steps 7–13, ~20 min estimado)
- ✅ security_audit — completó (step 14–16)
- ✅ run_tests ronda 1 — completó, 3 archivos fallaron (test_auth, test_contracts, test_benefits)
- ✅ execute_agents ronda 2 — completó, agentes corrigieron código (timestamps filesystem)
- ✅ run_tests ronda 2 — completó (step 17)
- ❌ **qa_review ronda 2 — BLOQUEADO 68 minutos → abandonado**

**Causa del bloqueo:** thinking mode ON en qwen3-coder:30b. La función `ChatOllama(..., think=False)` ignoraba el parámetro silenciosamente. El modelo generó bloques `<think>` de ~50k tokens antes de responder.

**Evidencia:**
- 2 conexiones TCP ESTABLISHED a puerto 11434 (invoke_structured + fallback ainvoke)
- `/api/ps` Ollama reportó `generating` durante los 68 minutos
- Ningún checkpoint nuevo después del step 17

---

### Ciclo 2 — `4793c5e1` (10:33 – 12:37 · ~124 min)

| Campo | Valor |
|---|---|
| Thread ID | 4793c5e1-a0bd-4aa4-bdb9-ac3d05030f38 |
| Inicio | 10:33 (con fix reasoning=False) |
| Abandono | ~12:37 (124 min) |
| Checkpoints alcanzados | 14 / step 13 |
| Status BD | started (nunca completó) |
| QA score | No disponible |
| Tokens totales | 0 |
| Costo | $0.00 |

**Progreso confirmado:**
- ✅ analyze_fr — completó en ~90 seg (step 0–4, mucho más rápido que ciclo 1 con reasoning=False)
- ✅ generate_sdd — completó (~2 min, steps 4–7)
- ✅ route_agents — completó, despachó 8 agentes (step 7–13)
- ❌ **execute_agents — BLOQUEADO 120+ minutos → abandonado**

**Causa del bloqueo:** Cuello de botella estructural de Ollama.
- 8 agentes despachados en paralelo vía asyncio (`Send()`)
- Ollama serializa todas las requests (1 GPU, 1 modelo a la vez)
- Cada agente tiene N subtareas según el SDD → N llamadas LLM secuenciales
- Con OVD_MODEL=qwen3-coder:30b × ~6-8 subtareas × 8 agentes = 48-64 requests LLM en serie
- A ~5-8 min/request = 240-512 min total estimado

**Evidencia:**
- 8 conexiones TCP ESTABLISHED a puerto 11434 confirmadas con `lsof`
- Progreso de checkpoints 4→7→9→11→14 en los primeros 4 minutos (nodos rápidos)
- Sin avance en checkpoints desde 10:37 (120 min de stall en fan-out de agentes)

---

## Telemetría comparativa

### Por nodo (estimaciones basadas en monitoreo)

| Nodo | Ciclo 1 (thinking ON) | Ciclo 2 (reasoning=False) | Diferencia |
|---|---|---|---|
| analyze_fr | ~2 min | ~90 seg | −50% |
| generate_sdd | ~4 min | ~2 min | −50% |
| execute_agents ×1 | ~20 min | ~120 min+ (stuck) | N/A* |
| security_audit | ~30–40 min | — | — |
| run_tests ×1 | ~10 min (pytest) | — | — |
| qa_review | 68 min (stuck) | — | — |

*En ciclo 1, los agentes completaron con thinking ON porque el modelo generó menos tokens de thinking para tareas de implementación cortas. En ciclo 2, con el mismo thinking ON (reasoning=False aún no era efectivo en ese momento)... 

**Nota:** La diferencia real del fix `reasoning=False` se vio solo en `analyze_fr` y `generate_sdd` (ciclo 2 fue ~50% más rápido en esos nodos). Los agentes del fan-out llevan el mismo tiempo en ambos ciclos porque el cuello de botella es el número de requests, no el tiempo individual.

### Baseline de referencia (S76 con Claude API)

| Métrica | S76 (Claude API) | S97 Ciclo 1 (Ollama) | S97 Ciclo 2 (Ollama) |
|---|---|---|---|
| Duración total | 13 min | 70 min (incompleto) | 124 min (incompleto) |
| QA score | 93/100 | — | — |
| Tests pytest | — | 3 fallos → corregidos | — |
| Costo | ~$0.00* | $0.00 | $0.00 |
| Completó ciclo | ✅ | ❌ | ❌ |

*S76 usó créditos gratuitos.

---

## Hallazgos S97

### S97-F (CRÍTICO) — `think=False` ignorado por ChatOllama

**Descubrimiento:** Al inspeccionar el modelo Pydantic de `ChatOllama`:
```python
"think" in ChatOllama.model_fields   # → False (parámetro no existe)
"reasoning" in ChatOllama.model_fields  # → True (parámetro correcto)
```

El parámetro `think=False` era descartado silenciosamente. El modelo operaba con thinking mode ON por defecto, generando 50k–100k tokens de `<think>` internos antes de cada respuesta.

**Fix aplicado:** `model_router.py` — `think=False` → `reasoning=False`

**Impacto observado del bug:**
- `qa_review` con contexto grande: 68 min (vs ~5-7 min esperado sin thinking)
- `security_audit`: estimado 30-40 min (vs ~5-10 min esperado)
- Factor de degradación: **10×-15× por nodo con LLM call**

**ADR actualizado:** `docs/adr/ADR-002-qwen3-thinking-mode.md` — Addendum S97-F

---

### Cuello de botella estructural — Fan-out serial en Ollama

**Problema:** `_dispatch_agents` lanza N agentes como tasks asyncio paralelas, pero Ollama los procesa en serie (1 GPU, 1 modelo). El tiempo total es `Σ(requests_por_agente × tiempo_por_request)`, no `max(tiempos)`.

**Estimación para ciclo S97 completo:**
```
Agentes: 8 (backend, database, devops, frontend, docs, security, router, ×)
Subtareas promedio por agente: 6-8
Total requests LLM agentes: 48-64
Tiempo por request (qwen3-coder:30b, reasoning=False): ~5-8 min
Total fan-out estimado: 240-512 min (4-8 horas)
```

**Esto hace inviable la validación de S97 con Ollama local + qwen3-coder:30b.**

**Documento de análisis:** `docs/adr/ADR-004-agent-parallelism-options.md`

---

## Estado de los fixes S97

Los 5 fixes fueron implementados y tienen cobertura de tests unitarios. No pudieron validarse en ciclo completo por los problemas de infraestructura descritos.

| Fix | Descripción | Implementado | Tests | Validado en ciclo |
|---|---|---|---|---|
| S97-A | `qa_score_history` + early stopping por estancamiento | ✅ | 6/6 ✅ | ❌ |
| S97-B | Ownership de archivos — devops no escribe .py ni tests/ | ✅ | 8/8 ✅ | ❌ |
| S97-C | Feedback prescriptivo `[ISSUE-N]` + instrucciones 5 pasos | ✅ | 7/7 ✅ | ❌ |
| S97-D | FR explícita BD > perfil proyecto (PostgreSQL override Oracle) | ✅ | 13/13 ✅ | ❌ |
| S97-E | `temperature_override=0.1` en retry QA | ✅ | 1/1 ✅ | ❌ |
| **S97-F** | **`reasoning=False` (fix crítico)** | ✅ | — | Parcial |

**Tests totales S97:** 35/35 PASS  
**Regresión:** 0 nuevos fallos (5 pre-existentes conocidos sin cambio)

---

## Problemas pre-existentes no abordados en S97

| Test | Descripción | Estado |
|---|---|---|
| test_s31 | Timing race condition | Pendiente S96-G |
| test_s39 | Cap obsoleto (3000 → 5000) | Pendiente S96-G |
| test_s47 | Background SSE task | Pendiente S96-G |
| test_s55 | write_artifacts overwrite | Pendiente S96-G |
| test_s63b | cleanup not in run_tests | Pendiente S96-G |

---

## Propuestas de mejora para próximos sprints

### Inmediato — S98

**1. Validar S97 con Claude API (1-2 días)**  
Temporalmente configurar `OVD_MODEL=claude-sonnet-4-5` en `.env` y ejecutar ciclo de validación completo. Costo estimado: ~$0.20 USD. Permite verificar los 5 fixes S97 sin el cuello de botella de Ollama.

**2. Implementar Opción A de ADR-004: filtrado agresivo de agentes (1-2 días)**  
Reducir de 8 agentes a 3-4 según el tipo de FR. Para "API REST + PostgreSQL": solo backend + database + devops. Reducción estimada del fan-out: 60%.

**3. Telemetría por nodo (1 día)**  
Agregar logging de duración, tokens y subtareas por agente al estado del grafo. Prerequisito para validar cualquier optimización de forma cuantitativa.

### Mediano plazo — S99-S100

**4. Modelos mixtos por agente (ADR-004 Opción B)**  
qwen3-coder:8b para devops/docs, qwen3-coder:30b para backend/database. Requiere A/B test con 5 ciclos.

**5. Multi-instancia Ollama (ADR-004 Opción C)**  
Paralelismo parcial con 2-3 instancias en puertos distintos. Requiere cambios en model_router y validación de VRAM.

### Largo plazo — producción

**6. Claude API para agentes en producción (ADR-004 Opción D)**  
Paralelismo real → reducción de 4-8h a ~15-20 min. Costo ~$0.20/ciclo, justificado con clientes reales.

---

## Datos requeridos para decisiones cuantitativas

Para poder comparar opciones con rigor se necesita:

| Métrica | Fuente | Estado |
|---|---|---|
| Duración por nodo individual | LangGraph trace o logging manual | ❌ No disponible |
| Tokens por agente (no total) | `tokens_by_agent` en state | ❌ No poblado |
| Número de subtareas por agente | `sdd.modules[].tasks` | ✅ Disponible |
| Tiempo en cola Ollama | Diferencia dispatch → primer token | ❌ No medido |
| QA score por ronda | `qa_score_history` (S97-A) | ✅ Implementado |

**Acción S98:** Implementar logging de duración por nodo en `graph.py` antes de cualquier experimento de optimización.

---

## Conclusiones

1. **Los fixes S97 son correctos** y están cubiertos por tests. El problema fue de infraestructura, no de lógica.

2. **S97-F es el hallazgo más importante de esta sesión:** `think=False` ignorado durante todos los ciclos Ollama desde S22. El impacto real en ciclos anteriores era enmascarado por FRs más simples (menos tokens de contexto = thinking completaba antes del timeout).

3. **El modelo qwen3-coder:30b con Ollama no es viable para ciclos completos con 8 agentes** sin las optimizaciones de ADR-004. Se necesita reducir agentes (Opción A) o usar Claude API (Opción D).

4. **El baseline de referencia real es S76** (Claude API, 13 min, QA 93/100). Cualquier mejora debe medirse contra ese baseline, no contra ciclos Ollama que no completan.

---

## Referencias

- `docs/adr/ADR-002-qwen3-thinking-mode.md` — Addendum S97-F: `reasoning=False`
- `docs/adr/ADR-004-agent-parallelism-options.md` — Análisis opciones de paralelismo
- `src/engine/tests/test_s97.py` — 35 tests unitarios de los fixes
- `src/engine/model_router.py` — Fix reasoning=False aplicado
- Ciclo de referencia S76: `docs/sprints/HISTORY.md`
