# Plan S98 — Optimización de paralelismo de agentes

**Fecha:** 2026-04-29  
**Sprint:** S98  
**Fuentes:** INFORME_PRUEBA_S97.md + ADR-004 + investigación profunda de código + documentación Ollama/LangGraph/repos referencia

---

## Corrección al ADR-004 — El fan-out real

El ADR-004 original documentó "8 agentes" — es impreciso. El código real tiene:

```python
_AGENT_RUNNERS = {
    "frontend": _run_frontend_agent,
    "backend":  _run_backend_agent,
    "database": _run_database_agent,
    "devops":   _run_devops_agent,
}
_SERVER_SIDE_AGENTS = frozenset({"database", "backend", "devops"})
_CLIENT_SIDE_AGENTS = frozenset({"frontend"})
```

**4 runners máximo**, no 8. Lo que genera 48-64 llamadas LLM es que cada runner ejecuta N subtareas del SDD con llamadas LLM individuales. El cuello de botella no es el número de runners sino el número de subtareas × tiempo por llamada.

---

## Hallazgo de alto impacto: Ollama ya es 0.21 con backend MLX

```
ollama version is 0.21.0
```

Ollama 0.19+ migró al backend MLX para Apple Silicon. Velocidad de decode:
- v0.18: ~58 tok/s para modelos 30B MoE
- v0.19+: ~112-134 tok/s con int4 (2× mejora)
- Time-to-first-token: hasta 4× más rápido en M5 por los Neural Accelerators

**Conclusión:** El sistema ya tiene la mejora de velocidad gratuita de MLX. Los tiempos del ADR-004 original (~7 min/request) probablemente ya se redujeron a ~3-4 min/request. Esto mejora todas las opciones A/B/C sin código adicional.

**Modelos disponibles actualmente:**
```
qwen3-coder:30b      18 GB  ← actual en producción
qwen3-coder-next     51 GB  ← variante extendida
qwen2.5vl:7b          6 GB  ← disponible (visión)
deepseek-r1:14b       9 GB  ← disponible (razonamiento)
```

`qwen3-coder:8b` y `qwen3-coder:14b` **no están descargados**. Hay que verificar disponibilidad en ollama.com/library antes de planificar la Opción B.

---

## Opción D — Claude API ~~DESCARTADA~~ — Solución solo con modelos locales

> **Decisión 2026-04-29:** La Opción D (Claude API) está descartada por política.
> La solución debe implementarse íntegramente con modelos locales vía Ollama.
> El engine ya tiene la infraestructura para usarla (`OVD_AGENT_PROVIDER=claude`),
> pero no se activará. El camino es optimizar Ollama local (Opciones A, B, C).

---

## Opción A — Filtrado agresivo de runners (IMPLEMENTAR DESPUÉS DE D)

### Diagnóstico preciso

El nodo `route_agents()` (graph.py:2900) ya tiene lógica de selección:

```python
# Línea 2961: selección basada en SDD
sdd_agents = {t.get("agent") for t in tasks_from_sdd if t.get("agent") in _AGENT_RUNNERS}
```

El problema: el SDD genera tareas para todos los agentes que el LLM considere necesarios, sin restricción por tipo de FR. Para un FR "API REST + PostgreSQL" el SDD puede incluir frontend porque el modelo LLM asume que toda API tiene UI.

### Gap identificado

No existe `_FR_AGENT_MAP` ni heurística de filtrado pre-SDD. La selección de agentes depende enteramente de lo que el LLM genera en el SDD — sin override determinístico por tipo de FR.

### Plan de implementación

**Archivo: `src/engine/graph.py`**

**1. Agregar constante de mapeo FR→agentes mínimos** (antes de `route_agents`, ~línea 2900):

```python
# Agentes mínimos por tipo de FR — override pre-SDD
# Si el SDD agrega más agentes, se acumulan. Este mapa define el mínimo garantizado.
_FR_AGENT_REQUIRED: dict[str, set[str]] = {
    "api_rest":          {"backend", "devops"},
    "api_rest_db":       {"backend", "database", "devops"},
    "frontend_only":     {"frontend"},
    "fullstack":         {"backend", "database", "devops", "frontend"},
    "bug_fix":           {"backend"},
    "security":          {"backend", "devops"},
    "feature":           {"backend", "devops"},  # default conservador
}

# Palabras clave para detectar si frontend es necesario (post-filtrado)
_FRONTEND_KEYWORDS = frozenset({
    "frontend", "ui", "react", "vue", "angular", "html", "css",
    "dashboard", "formulario", "interfaz", "componente", "vista",
})
```

**2. Agregar filtrado en `route_agents()`** (después del bloque de selección vía SDD, ~línea 2965):

```python
# S98-A: filtrado agresivo — omitir frontend si FR no lo menciona explícitamente
fr_raw = state.get("fr_analysis", {}).get("raw", "").lower()
fr_type = state.get("fr_analysis", {}).get("type", "feature").lower()

if "frontend" in selected:
    has_frontend_keyword = any(kw in fr_raw for kw in _FRONTEND_KEYWORDS)
    if not has_frontend_keyword and fr_type not in {"fullstack", "frontend_only"}:
        selected = [a for a in selected if a != "frontend"]
        log.info("route_agents: S98-A omitiendo 'frontend' — FR no lo menciona explícitamente")
```

**3. Agregar setting de control** (`src/engine/settings.py`):

```python
ovd_agent_filter_enabled: bool = True   # activa filtrado heurístico S98-A
ovd_max_tasks_per_agent: int = 5        # limita subtareas por agente (reduce llamadas LLM)
```

**4. Agregar cap de subtareas por agente** en `_build_agent_sdd_content()`:

```python
max_tasks = get_settings().ovd_max_tasks_per_agent
if len(tasks) > max_tasks:
    log.warning("S98-A: truncando %d → %d subtareas para agente %s", len(tasks), max_tasks, agent)
    tasks = tasks[:max_tasks]
```

### Impacto estimado

Con Ollama 0.21 MLX (~3-4 min/request) y filtrado:

| Configuración | Runners | Subtareas totales | Tiempo estimado |
|---|---|---|---|
| Actual (sin filtro) | 4 | 16-24 | 48-96 min |
| Con S98-A (sin frontend) | 3 | 9-15 | 27-60 min |
| Con S98-A + cap 4 tareas | 3 | 9-12 | 27-48 min |

### Riesgos

| Riesgo | Mitigación |
|---|---|
| QA penaliza si falta frontend en FR fullstack | `_FRONTEND_KEYWORDS` cubre los casos explícitos; fr_type="fullstack" nunca filtra |
| Cap de tareas produce código incompleto | Ajustable vía env: `OVD_MAX_TASKS_PER_AGENT=6` si QA baja |
| SDD inconsistente (tareas para agente omitido) | Loggear warning; no es error crítico (el agente simplemente no ejecuta) |

**Tiempo de implementación: 1-2 días**

---

## Opción B — Modelos mixtos por rol

### Estado de disponibilidad de modelos (verificado 2026-04-29)

```
qwen3-coder:30b    → 18 GB  — DISPONIBLE (activo)
qwen3-coder:8b     → NO EXISTE en ollama.com/library
qwen3-coder:14b    → NO EXISTE en ollama.com/library
qwen3-coder:480b   → 250+ GB — inviable en el hardware
```

**qwen3-coder solo tiene dos tamaños: 30b y 480b.** No hay versiones dense de 8b ni 14b.

**Alternativas reales disponibles en el sistema para roles ligeros:**

```
qwen2.5vl:7b      → 6 GB   — DISPONIBLE (visión — no ideal para código puro)
deepseek-r1:14b   → 9 GB   — DISPONIBLE (razonamiento, no coding especializado)
qwen2.5-coder:7b  → ~5 GB  — NO descargado, pero existe en ollama.com/library
                             ollama pull qwen2.5-coder:7b
```

**Candidato real para devops:** `qwen2.5-coder:7b` — modelo coding especializado de la generación anterior. Más pequeño, más rápido, suficiente para Dockerfiles y CI/CD YAML.

**Acción previa requerida:** `ollama pull qwen2.5-coder:7b` antes de implementar la Opción B.

### Hallazgo: OLLAMA_MAX_LOADED_MODELS ya soporta multi-modelo

Ollama 0.19+ puede tener hasta 3 modelos en VRAM simultáneamente (`OLLAMA_MAX_LOADED_MODELS=3` por defecto). Si se llama a `qwen3-coder:8b` para devops mientras `qwen3-coder:30b` atiende backend, Ollama carga ambos automáticamente si caben en VRAM.

**Presupuesto de VRAM en M5 Pro Max:**
- qwen3-coder:30b Q4_K_M: ~19 GB
- qwen3-coder:8b Q4_K_M (estimado): ~5-6 GB
- Total: ~25 GB de ~48-80 GB efectivos → **holgura suficiente**

### Plan de implementación

**Archivo: `src/engine/settings.py`** — agregar campos:

```python
# S98-B: modelo por rol específico (override sobre ovd_agent_model)
ovd_model_backend:  str = ""  # default: usa ovd_agent_model
ovd_model_database: str = ""  # default: usa ovd_agent_model
ovd_model_devops:   str = ""  # default: usa ovd_agent_model
ovd_model_frontend: str = ""  # default: usa ovd_agent_model
```

**Archivo: `src/engine/model_router.py`** — agregar en `resolve()` o en el bloque de defaults:

```python
_ROLE_MODEL_OVERRIDES: dict[str, str] = {
    "devops":    _s.ovd_model_devops,
    "frontend":  _s.ovd_model_frontend,
    "backend":   _s.ovd_model_backend,
    "database":  _s.ovd_model_database,
}

# En la función resolve(), después de obtener el config del Bridge:
def _apply_role_override(config: ResolvedConfig, agent_role: str) -> ResolvedConfig:
    """S98-B: aplica override de modelo por rol si está configurado."""
    override_model = _ROLE_MODEL_OVERRIDES.get(agent_role, "")
    if override_model and config.provider == "ollama":
        return ResolvedConfig(**{**config.__dict__, "model": override_model})
    return config
```

**Configuración `.env` para modo mixto:**

```bash
# Modelo ligero para roles de documentación/infraestructura
OVD_MODEL_DEVOPS=qwen2.5-coder:7b    # qwen3-coder:8b no existe — alternativa real
OVD_MODEL_FRONTEND=qwen2.5-coder:7b  # frontend tiene menos lógica crítica que backend

# Modelo pesado para roles de lógica crítica (sin cambio)
OVD_MODEL_BACKEND=qwen3-coder:30b
OVD_MODEL_DATABASE=qwen3-coder:30b
```

**Prerequisito Ollama:**

```bash
OLLAMA_KEEP_ALIVE=-1       # mantener ambos modelos en VRAM permanentemente
OLLAMA_MAX_LOADED_MODELS=2 # confirmar que puede cargar 2 modelos simultáneos
```

### Impacto estimado

`qwen2.5-coder:7b` (~5 GB, dense) vs `qwen3-coder:30b` (18 GB, MoE 3B activos):
- El 7b dense tiene ~7B parámetros activos vs ~3B del MoE 30b — similar en calidad
- El 7b es más rápido en time-to-first-token (modelo más pequeño en disco/VRAM)
- Estimación: ~3-4× más rápido en throughput por ser un modelo más pequeño

| Runner | Modelo | Subtareas | Tiempo estimado (con A) |
|---|---|---|---|
| backend | qwen3-coder:30b | 4-5 | 12-20 min |
| database | qwen3-coder:30b | 3-4 | 9-16 min |
| devops | qwen2.5-coder:7b | 2-3 | 2-5 min |
| **Total (serial)** | | 9-12 | **23-41 min** |

Combinado con Opción A (cap de subtareas + filtrado): **15-25 min con Ollama**

### Mandatorio: A/B test cuantitativo (ADR-003)

Según ADR-003, mínimo 3 ciclos baseline vs 3 ciclos con 7b antes de adoptar en producción. Métricas:
- QA score: si cae >10 puntos con 7b en devops → revertir a 30b
- Tiempo: medir con telemetría por nodo (S98 prerequisito)
- Artefactos: revisar calidad de Dockerfiles y CI/CD YAML generados por 7b

**Prerequisito:** `ollama pull qwen2.5-coder:7b` (~5 GB)

**Tiempo de implementación: 2 días** (settings + model_router) + 3 días de A/B test

---

## Opción C — OLLAMA_NUM_PARALLEL y multi-instancia

### Análisis en dos fases

#### Fase C-1: OLLAMA_NUM_PARALLEL (cero código, experimento antes de S99)

`OLLAMA_NUM_PARALLEL=2` permite que un solo proceso Ollama atienda 2 requests intercalados. El trade-off:
- +20-40% overhead por request individual (context switching de GPU)
- 3-4× más throughput total para workloads multi-agente

Para OVD: 4 runners simultáneos con 1 modelo = `OLLAMA_NUM_PARALLEL=4` en teoría atiende todos en paralelo. Pero con MLX en Ollama 0.19+, **no está documentado si `OLLAMA_NUM_PARALLEL` funciona en el nuevo backend MLX** — es el riesgo principal de esta opción.

**Experimento previo a S99 (cero código):**

```bash
# Detener Ollama
brew services stop ollama

# Reiniciar con paralelismo
OLLAMA_NUM_PARALLEL=2 OLLAMA_FLASH_ATTENTION=1 brew services start ollama

# Ejecutar ciclo y comparar tiempos vs baseline
```

Si el experimento muestra reducción real (>30%): implementar en producción como variable de entorno en el launchd plist de Ollama.

#### Fase C-2: Multi-instancia Ollama en macOS (si C-1 no es suficiente)

**Procedimiento macOS (sin systemd):**

```bash
# Instancia principal — ya existe
# brew services start ollama → puerto 11434

# Instancia secundaria — proceso manual
OLLAMA_HOST=127.0.0.1:11435 \
OLLAMA_MODELS=$HOME/.ollama-inst2 \
OLLAMA_KEEP_ALIVE=-1 \
ollama serve &

# Pre-cargar modelo ligero en instancia 2
OLLAMA_HOST=127.0.0.1:11435 ollama pull qwen3-coder:8b
```

**Cambios en el engine:**

`src/engine/settings.py`:
```python
ollama_instance_2_url: str = ""  # http://localhost:11435
```

`src/engine/model_router.py` — routing por instancia en `build_llm()`:
```python
# Rol devops/frontend → instancia 2 (modelo ligero)
_ROLE_INSTANCE_MAP = {
    "backend":  _s.ollama_base_url,
    "database": _s.ollama_base_url,
    "devops":   _s.ollama_instance_2_url or _s.ollama_base_url,
    "frontend": _s.ollama_instance_2_url or _s.ollama_base_url,
}
```

`scripts/ollama-instances.sh` (nuevo archivo):
```bash
#!/usr/bin/env bash
case "$1" in
  start)
    brew services start ollama  # instancia 1 principal en 11434
    OLLAMA_HOST=127.0.0.1:11435 OLLAMA_MODELS=$HOME/.ollama-inst2 ollama serve &
    echo "Instancias Ollama: 11434 (30b) y 11435 (8b)"
    ;;
  stop)
    brew services stop ollama
    pkill -f "OLLAMA_HOST=127.0.0.1:11435"
    ;;
esac
```

### Impacto estimado (C-2 completo)

Con backend/database en instancia 1 (30b) y devops/frontend en instancia 2 (8b) corriendo en paralelo real:

| Grupo | Instancia | Tiempo |
|---|---|---|
| backend + database | Puerto 11434 / 30b | 20-35 min |
| devops + frontend | Puerto 11435 / 8b | 5-10 min |
| **Total (paralelo real)** | | **max(20-35, 5-10) = 20-35 min** |

### Riesgos

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| MLX en Ollama 0.21 no soporta NUM_PARALLEL estable | Media | Verificar con experimento C-1 antes de codear |
| Dos instancias consumen >48 GB VRAM efectivos | Baja | 19 + 6 GB = 25 GB, bien dentro del presupuesto |
| macOS sin systemd = proceso manual frágil al reiniciar | Alta | Script en `scripts/` + instrucción en README; no auto-start |
| Fragmentación de memoria unificada entre dos llm.go processes | Incierta | No documentado para MLX; requiere medición con vm_stat durante ciclo |

**Tiempo de implementación: 4-5 días** (C-1: 1 día experimento; C-2: 3-4 días si C-1 es insuficiente)

---

## Tabla de decisión actualizada (solo modelos locales)

| Opción | Tiempo ciclo estimado | Código a escribir | Riesgo | Costo/ciclo | Estado |
|---|---|---|---|---|---|
| Baseline actual (0.21 MLX) | ~120-240 min | — | — | $0 | Activo |
| ~~D — Claude API~~ | ~~15-20 min~~ | ~~0 líneas~~ | — | ~~$0.30-0.40~~ | **Descartado** |
| **A — Filtrar runners** | **~27-60 min** | **~50 líneas** | Bajo | $0 | **Recomendado S98** |
| **A+B — Filtrar + 8b** | **~15-25 min** | **~80 líneas** | Medio | $0 | **Objetivo S99** |
| C-1 — NUM_PARALLEL=2 | ~60-120 min | 0 líneas | Bajo | $0 | Experimento pre-S99 |
| C-2 — Multi-instancia | ~20-35 min | ~100 líneas | Alto | $0 | S100 si A+B insuf. |

---

## Roadmap recomendado S98-S100 (solo Ollama local)

```
S98 (semana actual):
  ├─ Telemetría por nodo: logging duración+tokens en graph.py    (prerequisito métricas)
  ├─ A:  filtrado runners por FR-type + cap subtareas            (1-2 días código)
  └─ C-1: experimento OLLAMA_NUM_PARALLEL=2 (cero código)       (1 día validación)

S99:
  ├─ ollama pull qwen2.5-coder:7b  (qwen3-coder:8b/14b no existen — solo 30b y 480b)
  ├─ B:  settings ovd_model_devops=qwen2.5-coder:7b + override en model_router    (2 días código)
  └─ A/B test mandatorio: 3 ciclos baseline vs 3 con 7b (QA + tiempo)

S100:
  └─ C-2: multi-instancia si A+B no alcanza target 20-30 min    (4 días)
          → solo si telemetría S99 muestra A+B > 40 min
```

---

## Prerrequisito transversal: telemetría por nodo (S98)

Sin datos cuantitativos por nodo, ninguna decisión A/B/C puede evaluarse objetivamente. El prerequisito para cualquier optimización de S99 en adelante:

**Archivo: `src/engine/graph.py`** — agregar logging al inicio/fin de cada nodo:

```python
# Decorador para nodos con timing
import time

def _timed_node(node_name: str):
    def decorator(fn):
        async def wrapper(state, *args, **kwargs):
            t0 = time.monotonic()
            result = await fn(state, *args, **kwargs)
            elapsed = time.monotonic() - t0
            log.info("NODE_TIMING: node=%s elapsed=%.1fs", node_name, elapsed)
            return result
        return wrapper
    return decorator
```

**Métricas mínimas por nodo:**
- `elapsed_secs`: duración real
- `llm_calls`: número de llamadas LLM dentro del nodo
- `tokens_in` / `tokens_out`: desde `state["tokens_by_agent"]`

---

## Referencias

- `src/engine/model_router.py:61-65` — `_AGENT_PROVIDER`, `_AGENT_MODEL`, `_AGENT_ROLES`
- `src/engine/graph.py:2607-2618` — `_AGENT_RUNNERS`, `_SERVER_SIDE_AGENTS`
- `src/engine/graph.py:2900` — `route_agents()` — lógica de selección actual
- `src/engine/graph.py:3061` — `_dispatch_agents()` — fan-out via Send()
- `src/engine/settings.py:57-64` — campos `ovd_agent_provider`, `ovd_agent_model`, `ollama_base_url`
- `docs/adr/ADR-002-qwen3-thinking-mode.md` — S97-F: reasoning=False fix
- `docs/adr/ADR-003-model-selection-criteria.md` — criterios A/B test mandatorio
- `docs/adr/ADR-004-agent-parallelism-options.md` — opciones originales (este doc las actualiza)
- `docs/INFORME_PRUEBA_S97.md` — telemetría de referencia
