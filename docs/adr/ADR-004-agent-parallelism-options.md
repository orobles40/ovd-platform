# ADR-004 — Opciones de paralelismo real en el fan-out de agentes

**Estado:** Decisión tomada — Opción D adoptada en producción (S112)
**Fecha análisis:** 2026-04-29 | **Fecha decisión:** 2026-05-05
**Contexto:** Sprint S97 — observación de cuello de botella en fan-out de 8 agentes con Ollama local

---

## Problema

El nodo `_dispatch_agents` lanza los agentes (backend, database, devops, frontend, docs, security, router, etc.) como tasks asyncio en paralelo via `Send()`. Sin embargo, Ollama serializa todas las inferencias porque la GPU es un recurso no divisible: el modelo qwen3-coder:30b (20 GB VRAM) ocupa la totalidad de la memoria disponible, lo que impide concurrencia real.

**Resultado:** el tiempo total del fan-out es `Σ(tiempo_por_agente)`, no `max(tiempo_por_agente)`.

### Medición observada (S97, ciclo 4793c5e1, 2026-04-29)

| Agentes despachados | Tiempo por agente (estimado) | Tiempo total fan-out |
|---|---|---|
| 8 (todos los seleccionados) | ~7 min c/u con reasoning=False | ~56 min |

### Baseline de referencia (S76, ciclo con Claude API)

| Agentes despachados | Tiempo por agente | Tiempo total fan-out |
|---|---|---|
| 4 (backend, db, devops, docs) | ~2-3 min c/u | ~10 min (paralelo real) |

---

## Opciones evaluadas

### Opción A — Reducir agentes seleccionados (filtrado más agresivo en route_agents)

**Descripción:** El nodo `route_agents` actualmente selecciona agentes basándose en el SDD. La heurística podría ser más restrictiva: para un FR de "API REST + PostgreSQL", despachar solo backend + database + devops (3 agentes), omitiendo docs y frontend cuando no aplican.

**Implementación estimada:** 1-2 días — modificar `_select_agents()` en graph.py con reglas más estrictas.

**Impacto esperado:**
- Fan-out de 8 → 3-4 agentes = reducción del 50-62% del tiempo
- Tiempo estimado: 21-28 min (vs 56 min actual)

**Riesgos:**
- Omitir agentes puede resultar en artefactos faltantes que QA detecta y penaliza
- Requiere calibración cuidadosa de las reglas de selección

**Veredicto:** Mayor relación esfuerzo/impacto. Quedó sin implementar — se adoptó Opción D directamente en S112.

---

### Opción B — Modelo más pequeño para agentes no críticos

**Descripción:** Usar qwen3-coder:8b para agentes de baja criticidad (docs, devops) y mantener qwen3-coder:30b solo para backend y database. El modelo 8B cabe simultáneamente en VRAM junto al 30B en el M5 Pro Max (128 GB RAM unificada, ~48 GB VRAM efectiva).

**Modelos candidatos:**
| Agente | Modelo actual | Modelo propuesto |
|---|---|---|
| backend | qwen3-coder:30b | qwen3-coder:30b (mantener) |
| database | qwen3-coder:30b | qwen3-coder:30b (mantener) |
| devops | qwen3-coder:30b | qwen3-coder:8b |
| docs | qwen3-coder:30b | qwen3-coder:8b |
| frontend | qwen3-coder:30b | qwen3-coder:14b |

**Implementación estimada:** 2-3 días — agregar campo `model_override` por rol en el sistema de configuración + profiling de calidad.

**Impacto esperado:**
- Agentes ligeros (8B): ~1-2 min c/u (vs ~7 min con 30B)
- Tiempo total estimado: ~25-35 min

**Riesgos:**
- Calidad inferior en devops puede generar Dockerfiles con errores
- Requiere A/B test (mínimo 3 ciclos por configuración) antes de adoptar
- Dos modelos simultáneos en VRAM pueden ralentizarse mutuamente si la memoria se fragmenta

**Veredicto:** Alto impacto, riesgo medio. Requiere validación experimental.

---

### Opción C — Múltiples instancias Ollama en puertos distintos

**Descripción:** Levantar 2-3 instancias de Ollama en puertos separados (11434, 11435, 11436), cada una con un modelo diferente. El `model_router` distribuye agentes entre instancias según disponibilidad (round-robin o por rol).

**Configuración posible en el M5 Pro Max 128 GB:**
```
Puerto 11434: qwen3-coder:30b (backend, database, qa, security)
Puerto 11435: qwen3-coder:14b (frontend, router)  
Puerto 11436: qwen3-coder:8b  (devops, docs)
```

**Implementación estimada:** 3-5 días — cambios en model_router para routing multi-instancia + scripts de gestión de instancias.

**Impacto esperado:**
- Paralelismo parcial: 2-3 agentes simultáneos
- Tiempo estimado: 15-25 min (vs 56 min actual)

**Riesgos:**
- Complejidad operacional: 3 procesos Ollama a gestionar
- Fragmentación de VRAM puede reducir el throughput por instancia
- Requiere profiling de memoria para evitar OOM

**Veredicto:** Alto impacto, alta complejidad. Viable a largo plazo.

---

### Opción D — Claude API / DO GenAI Platform para agentes en producción ✅ ADOPTADA

> **Decisión 2026-05-05 (S112):** Adoptada como modelo de producción para el despliegue en
> DigitalOcean App Platform. La plataforma opera con Ollama en desarrollo local (sin cambios)
> y con DO GenAI Platform en producción vía `OVD_AGENT_PROVIDER=claude` (o `openai` según modelo).
> Todos los roles — implementadores y análisis — usan DO GenAI. Ver C7 en S112.
>
> **Razón del cambio respecto a 2026-04-29:** El producto tiene cliente real (demo 2026-05-18).
> El costo por ciclo (~$0.20-0.30 USD con Claude Sonnet 4.6) se justifica con el valor entregado.
> La dependencia de Ollama en producción no es viable en App Platform (sin GPU, sin Ollama).

**Descripción original:** Usar la API de Anthropic (Claude Sonnet 4.5/4.6) para los agentes en ciclos de producción. La API de Anthropic permite concurrencia real: múltiples requests simultáneos, cada uno procesado en infraestructura distribuida.

**Impacto esperado:**
- Fan-out genuinamente paralelo: tiempo total ≈ `max(tiempos)` ≈ 5-10 min
- Calidad superior en generación de código (modelos más capaces)
- Reducción del ciclo completo de ~90 min → ~20-30 min

**Costo estimado:**
| Ciclo | Tokens input | Tokens output | Costo (Sonnet 4.5) |
|---|---|---|---|
| Agentes (×4) | ~40k | ~20k | ~$0.15 USD |
| QA + Security | ~30k | ~5k | ~$0.05 USD |
| Total por ciclo | | | **~$0.20-0.30 USD** |

**Riesgos:**
- Costo recurrente: ~$6-9 USD/mes con 30 ciclos mensuales
- Dependencia de API externa (disponibilidad, rate limits, cambios de precios)
- Requiere gestión de API keys en producción

**Veredicto:** Máximo impacto, costo controlado. Recomendado para producción una vez validado el producto.

---

## Análisis comparativo

| Opción | Tiempo estimado fan-out | Esfuerzo implementación | Riesgo | Costo |
|---|---|---|---|---|
| Baseline (actual) | ~56 min | — | — | $0 |
| A — Menos agentes | ~21-28 min | Bajo (1-2 días) | Bajo | $0 |
| B — Modelos mixtos | ~25-35 min | Medio (2-3 días) | Medio | $0 |
| C — Multi-instancia | ~15-25 min | Alto (3-5 días) | Medio | $0 |
| D — Claude API | ~5-10 min | Bajo (1 día) | Bajo | ~$0.20/ciclo |

---

## Recomendación de roadmap

> **Actualización 2026-05-05 (S112):** El roadmap original A→B→D quedó sin ejecutar.
> Ante la necesidad de tener producción operativa antes de la demo 2026-05-18, se adoptó
> Opción D directamente. Las opciones A, B y C quedan disponibles para optimizar el
> entorno de desarrollo local (donde Ollama sigue siendo el proveedor).

```
[SUPERSEDED] S98: Implementar Opción A (filtrado de agentes)
[SUPERSEDED] S99: Evaluar Opción B (modelos mixtos)
[ADOPTADO]   S112: Opción D — DO GenAI Platform en producción, Ollama en desarrollo local
```

**Opciones A/B/C como trabajo futuro (solo desarrollo local):**
- Opción A (menos agentes): válida para reducir tiempo en ciclos locales con Ollama
- Opción B (modelos mixtos): requiere A/B test antes de adoptar
- Opción C (multi-instancia): viable a largo plazo para paralelismo real en local

---

## Datos requeridos para decisión final

Para comparar las opciones con rigor, se necesita telemetría por nodo:

1. **Duración por agente** — actualmente no se registra individualmente
2. **Tokens generados por agente** — disponible en `token_usage` del estado
3. **Tiempo en cola Ollama** — diferencia entre dispatch y primer token
4. **QA score por configuración** — impacto de modelos más pequeños en calidad

Implementar este logging detallado es prerequisito para cualquier decisión basada en datos (ver propuesta en INFORME_PRUEBA_S97.md cuando esté disponible).

---

## Referencias

- ADR-002: Deshabilitar thinking mode (hallazgo S97-F: `think=False` ignorado)
- ADR-003: Criterios de selección de modelos LLM
- `src/engine/graph.py`: `_dispatch_agents()`, `route_agents()`
- `src/engine/model_router.py`: `build_llm()`, `get_llm_with_context()`
- `docs/OPTIMIZATION_PLAN_S39_S40.md`: análisis previo de optimización
