# OVD Platform — Plan de Optimización Multi-Agente
**Investigado:** 2026-04-22 | **Rama:** dev | **Estado:** pendiente de implementación

## Contexto

Ciclo de validación `ab3c661e` (gestión de contratos) reveló tres problemas:
- Agentes `database` y `backend` timeout a los 600s
- QA score 65/100 con código correcto (28/28 tests pasan)
- Tiempo total de ciclo: 15m 29s con paralelismo no real

Investigación basada en: documentación Ollama, LangGraph oficial, repositorios de referencia (SWE-agent, MetaGPT, OpenHands, AutoGen), benchmarks de modelos qwen3.

---

## Hallazgo principal: qwen3-coder-next es MoE, no denso

`qwen3-coder-next:latest` es arquitectura **Mixture of Experts (MoE)**:
- 80B parámetros totales, **3B activos por token** en cada forward pass
- 52 GB en memoria unificada Apple Silicon (Q4_K_M)
- Velocidad real: ~20+ tokens/s en M-series
- **Sin thinking mode** (coder-next no genera bloques `<think>`)

El timeout de 600s ocurre porque los agentes generan 10-15K tokens por llamada (código completo + tests + infraestructura). A 20 t/s = 500-750s. No es un problema del modelo sino de longitud de output sin límite.

---

## Diagnóstico de problemas

| Problema | Causa raíz | Solución propuesta |
|----------|-----------|-------------------|
| Timeout agents 600s | `num_predict` sin límite → outputs 10-15K tokens | Cambiar modelo o aumentar timeout |
| QA score 65/100 | QA recibe output vacío tras timeout; no hay resumen del código en disco | `SummarizeAgentOutput` antes de `qa_review` |
| Paralelismo no real | Ollama serializa por defecto; 3×54GB no paralelo viable | Cambiar a `qwen3-coder:30b` (19GB) |

---

## Nivel 1 — Cambios inmediatos (minutos, sin código)

### 1-A: Cambiar OVD_MODEL a `qwen3-coder:30b`

`qwen3-coder:30b` es también MoE (30B/3.3B activos):
- 19 GB (vs 52 GB del next) — libera 33 GB
- ~50-60 t/s (vs 20+ t/s) — **3× más rápido**
- Calidad levemente inferior pero suficiente para Python estándar
- 3 instancias paralelas caben en 57 GB (vs 162 GB imposible con next)

```bash
# .env — cambios
OVD_MODEL=qwen3-coder            # :30b — agentes de código (19GB, rápido)
OVD_MODEL_SDD=ovd-arch-assistant # mantener (arquitectura)
OVD_MODEL_QA=qwen3-coder-next    # mantener next para QA (calidad de revisión)
```

Primero descargar: `ollama pull qwen3-coder:30b`

### 1-B: Aumentar timeout a 1200s

```bash
OVD_LLM_TIMEOUT_SECS=1200   # era 600
```

### 1-C: Activar keep-alive indefinido en Ollama

```bash
OLLAMA_KEEP_ALIVE=-1   # evita cold start de 10-30s entre nodos
```

Agregar como variable de entorno antes de iniciar el proceso Ollama (launchd o shell).

**Impacto estimado Nivel 1:** tiempo de ciclo 15m → ~5m

---

## Nivel 2 — Sprint S39 (½ día de desarrollo)

### S39-A: `asyncio.wait_for()` por agente con timeout diferenciado

LangGraph no tiene timeout por nodo nativo. Hoy el timeout aplica al ciclo completo.

```python
# En agent_executor (graph.py)
_AGENT_TIMEOUTS = {"backend": 300, "database": 180, "devops": 120}

async def agent_executor(state: OVDState) -> dict:
    agent_type = state.get("agent_type", "backend")
    timeout = _AGENT_TIMEOUTS.get(agent_type, 300)
    try:
        result = await asyncio.wait_for(
            _run_agent_with_tools(state), timeout=timeout
        )
    except asyncio.TimeoutError:
        log.warning("agent_executor: timeout parcial en '%s' — filesystem fallback", agent_type)
        result = {"output": "", "artifacts": []}
    return result
```

El fallback filesystem (S24-A) recupera automáticamente los archivos escritos antes del timeout.

### S39-B: `_summarize_for_qa()` antes de `qa_review`

Patrón de MetaGPT `SummarizeCode`: el QA no recibe código completo sino un resumen estructurado del workspace.

```python
async def _summarize_for_qa(state: OVDState) -> str:
    """Lee el workspace y produce: archivos + funciones/clases públicas."""
    work_dir = pathlib.Path(state.get("directory", ""))
    if not work_dir.exists():
        return ""
    lines = []
    for fp in sorted(work_dir.rglob("*.py")):
        if any(p in str(fp) for p in ("__pycache__", ".venv", "node_modules")):
            continue
        rel = fp.relative_to(work_dir)
        source = fp.read_text(errors="replace")
        defs = [l.strip() for l in source.splitlines()
                if l.strip().startswith(("def ", "class ", "async def "))]
        if defs:
            lines.append(f"### {rel}\n" + "\n".join(defs[:20]))
    return "\n\n".join(lines)
```

Inyectar en `qa_review` como contexto adicional antes del prompt al LLM.

**Impacto:** QA score estimado +15-20 pts (de 65 → 80-85) cuando hay timeouts de agentes.

### S39-C: Retry con solo stderr (no output completo)

Patrón MetaGPT: `update_test_retry` ya extrae AssertionError (S33-B) y bloques fallidos (S34-B).
Gap: `retry_feedback` incluye hasta 3000 chars de output.

Propuesta: reducir a 800 chars totales:
```
[DIAGNÓSTICO]\n{assert_errors}\n\n{failed_blocks_truncated_500}
```

Reducción de contexto en retry: ~3000 → ~800 chars.

### S39-D: Task-by-task execution — una tarea por llamada al LLM

**Problema actual:** `agent_executor` envía todas las tareas del agente en un solo prompt. Con 10-15 tareas el output supera 10-15K tokens → timeout 600s. No hay retry granular: si la tarea 8/15 falla, se re-ejecuta desde la 1.

**Causa raíz identificada (2026-04-22):** `_build_agent_sdd_content` filtra las tareas por agente pero las entrega todas juntas en `## Your Tasks (backend)`. El modelo tiene que planificar e implementar todo en una sola invocación.

**Solución:** loop secuencial dentro de `agent_executor` — una llamada al LLM por tarea:

```python
async def agent_executor(state: OVDState) -> dict:
    agent_name = state.get("current_agent", "backend")
    agent_tasks = [t for t in state["sdd"].get("tasks", [])
                   if t.get("agent") == agent_name]

    all_artifacts = []
    for task in agent_tasks:
        # Leer lo que ya está en disco (S17T.C — read_project_context)
        prior_ctx = read_project_context(directory, agent_name)

        # SDD reducido: solo esta tarea + contexto compartido
        task_sdd = _build_single_task_sdd_content(state["sdd"], agent_name, task, prior_ctx)

        result = await _run_agent_with_tools(state, sdd_content=task_sdd)
        all_artifacts.extend(result.get("artifacts", []))

    return {"agent_results": [{"agent": agent_name, "artifacts": all_artifacts, ...}]}
```

**Por qué una tarea a la vez es superior a batches de N:**

| Factor | Batch N | Una a la vez |
|--------|---------|-------------|
| Tokens por llamada | ~2-3K | ~800 |
| Timeout posible | Sí (batch complejo) | No |
| Retry granular | Por batch | Por tarea |
| Dependencias entre archivos | Parcial | Natural (secuencial) |
| Complejidad | Media | Baja |

**Acumulación de contexto sin cambios adicionales:** `read_project_context` (S17T.C, línea 1291) ya lee los archivos escritos en disco antes de cada llamada. La TASK-002 ve automáticamente los archivos que TASK-001 escribió — sin lógica extra de "pasar contexto" entre iteraciones.

**Impacto estimado:**
- Timeout: eliminado estructuralmente (cada tarea ~40s con qwen3-coder:30b)
- 15 tareas × 40s = 10 min de trabajo real vs 10 min de espera + timeout + retry desde cero
- Imports rotos entre archivos: reducidos (dependencias se resuelven por orden de ejecución)
- Retry: quirúrgico — solo la tarea fallida, no el agente completo

**Tiempo de implementación:** 3h (loop en `agent_executor` + nuevo helper `_build_single_task_sdd_content`)

---

## Nivel 3 — Sprint S40 (1-2 días, rediseño estructural)

### S40-A: Subgraphs por agente con checkpointer propio

**Problema actual:** el fan-out `Send()` es atómico. Si `backend` falla en el tool call 8/12, hay que re-ejecutarlo desde cero junto con todos los otros agentes.

**Solución:** cada agente como subgraph con checkpointer propio:

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

agent_subgraph = (
    StateGraph(AgentState)
    .add_node("call_llm", call_llm)
    .add_node("run_tool", run_tool)
    .add_conditional_edges("run_tool", should_continue, ["call_llm", END])
    .compile(checkpointer=MemorySaver())
)
```

Con esto, un agente que timeout en tool call 8/12 puede resumirse desde el checkpoint del tool call 7 — sin re-ejecutar los 7 anteriores.

### S40-B: Paralelismo real con `OLLAMA_NUM_PARALLEL=3`

Solo viable con `qwen3-coder:30b` (19GB × 3 = 57GB, cabe en ~96GB):

```bash
OLLAMA_NUM_PARALLEL=3          # 3 requests simultáneas al mismo modelo
OLLAMA_MAX_LOADED_MODELS=1     # un solo modelo en RAM
OLLAMA_MAX_QUEUE=512
```

Con el modelo actual (54GB × 3 = 162GB) no es viable.

**Impacto:** el tiempo del fan-out pasa de `max(t1, t2, t3)` con serialización a `max(t1, t2, t3)` con paralelismo real → estimado -40% del tiempo total de agentes.

### S40-C: StreamWriter por tool call al dashboard

```python
from langgraph.types import StreamWriter

async def agent_executor(state: AgentState, writer: StreamWriter):
    async for event in _run_agent_with_tools_streaming(state):
        if event["type"] == "file_written":
            writer({
                "type": "file_written",
                "agent": state["agent_type"],
                "path": event["path"],
                "size": event["size"]
            })
```

UX: el dashboard muestra cada archivo generándose en tiempo real vs esperar 5-15 min en silencio.

---

## Tabla de impacto consolidada

| Acción | Sprint | Tiempo impl. | Velocidad | Calidad QA |
|--------|--------|-------------|-----------|------------|
| `qwen3-coder:30b` para agentes | config | 5 min | **-60%** | -5% (leve) |
| `OVD_LLM_TIMEOUT_SECS=1200` | config | 1 min | elimina falsos timeouts | — |
| `OLLAMA_KEEP_ALIVE=-1` | config | 2 min | -10s/nodo cold start | — |
| `asyncio.wait_for` diferenciado | S39 | 2h | timeout preciso por agente | — |
| `_summarize_for_qa()` | S39 | 3h | — | **+15-20 pts** |
| Retry solo stderr | S39 | 1h | -30% tokens en retry | +5 pts |
| Task-by-task execution | S39 | 3h | **elimina timeout estructural** | imports correctos |
| Subgraphs con checkpointer | S40 | 1 día | elimina restart desde 0 | — |
| `OLLAMA_NUM_PARALLEL=3` | S40 | 1h config | paralelo real (-40%) | — |
| StreamWriter tool calls | S40 | 4h | — | UX real-time |

---

## Comparativa de modelos para agentes de código

| Modelo | Tamaño | Arquitectura | Velocidad M-series | Calidad código |
|--------|--------|-------------|-------------------|----------------|
| `qwen3-coder-next` (actual) | 52 GB | MoE 80B/3B | ~20 t/s | Máxima local |
| `qwen3-coder:30b` (propuesto) | 19 GB | MoE 30B/3.3B | ~50-60 t/s | Muy buena |
| `qwen2.5-coder:32b` | ~20 GB | Dense 32B | ~10-15 t/s | Muy buena |
| `deepseek-coder-v2:16b` | ~10 GB | MoE 16B/2.4B | ~60-80 t/s | Buena |
| `qwen2.5-coder:7b` | 4.7 GB | Dense 7B | ~80-100 t/s | Limitada (probado) |

---

## Secuencia de implementación recomendada

```
Hoy:
  1. ollama pull qwen3-coder:30b
  2. .env: OVD_MODEL=qwen3-coder, OVD_LLM_TIMEOUT_SECS=1200
  3. OLLAMA_KEEP_ALIVE=-1 en proceso Ollama
  4. Reiniciar engine → validar ciclo de prueba

Sprint S39 (½ día):
  5. asyncio.wait_for por agente
  6. _summarize_for_qa() antes de qa_review
  7. Retry con solo stderr
  8. Task-by-task execution en agent_executor

Sprint S40 (1-2 días):
  8. Subgraphs con checkpointer
  9. OLLAMA_NUM_PARALLEL=3 (después de validar 30b)
  10. StreamWriter tool calls al dashboard
```

---

## Referencias

- [Ollama FAQ — concurrent requests, keep_alive](https://docs.ollama.com/faq)
- [qwen3-coder-next — Unsloth docs](https://unsloth.ai/docs/models/qwen3-coder-next)
- [qwen3-coder en Ollama](https://ollama.com/library/qwen3-coder)
- [LangGraph — asyncio.wait_for para timeout por nodo (issue #4927)](https://github.com/langchain-ai/langgraph/issues/4927)
- [LangGraph — StreamWriter](https://langchain-ai.github.io/langgraph/concepts/streaming/)
- [MetaGPT — SummarizeCode](https://github.com/geekan/MetaGPT/blob/main/metagpt/actions/summarize_code.py)
- [SWE-agent — ClosedWindowHistoryProcessor](https://github.com/princeton-nlp/SWE-agent/blob/main/sweagent/agent/history_processors.py)
- [langgraph-supervisor](https://github.com/langchain-ai/langgraph-supervisor-py)
