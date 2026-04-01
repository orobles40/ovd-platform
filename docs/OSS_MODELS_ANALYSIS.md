# OVD Platform — Análisis: Soporte de Modelos Open-Source

> **Fecha:** 2026-03-24
> **Autor:** Análisis técnico — Omar Robles
> **Estado:** Propuesta para revisión e iteración

---

## Contexto

OVD Platform fue diseñado inicialmente con Claude (Anthropic) como modelo principal. Este documento analiza los cambios necesarios para operar **end-to-end con modelos open-source locales** (Qwen, Llama, Mistral, etc.) via Ollama, sin dependencia de APIs externas de pago.

Caso de uso primario analizado: **`qwen2.5-coder:7b` / `14b` / `32b` via Ollama local**.

---

## Diagnóstico del estado actual

### Cobertura del model_router por nodo del grafo

| Nodo | Usa model_router | `with_structured_output` | Estado con OSS |
|---|---|---|---|
| `analyze_fr` | ❌ `_llm()` hardcoded | ✅ sí | Siempre Claude |
| `generate_sdd` | ❌ `_llm()` hardcoded | ✅ sí | Siempre Claude |
| `route_agents` | ✅ parcial | ✅ sí | Funciona, frágil en 7B |
| `security_audit` | ✅ | ✅ sí | Frágil en modelos pequeños |
| `qa_review` | ❌ `_llm()` hardcoded | ✅ sí | Siempre Claude |
| `agent_executor` (backend/frontend/etc.) | ✅ | ❌ generación libre | Funciona bien con OSS |
| RAG embeddings | — | — | Hardcoded a OpenAI |
| Cost tracking | — | — | Precio Sonnet fijo ($3/$15) |
| Timeouts LLM | — | — | No configurados |

### Archivo fuente del problema

`src/engine/graph.py` — función `_llm()` (línea ~342):

```python
def _llm() -> ChatAnthropic:
    return ChatAnthropic(
        model=os.environ.get("OVD_MODEL", "claude-sonnet-4-6"),
        api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        max_tokens=8192,
    )
```

Esta función es llamada en `analyze_fr`, `generate_sdd` y `qa_review`, ignorando completamente el `model_router`.

---

## Bloque P1 — Crítico (bloquea uso OSS end-to-end)

### P1.A — Extender model_router a todos los nodos

**Problema:** `analyze_fr`, `generate_sdd`, `qa_review` siempre usan Claude via `_llm()`.

**Solución:** Reemplazar `_llm()` con llamadas al router usando roles especiales por nodo.

Roles nuevos a registrar en `ovd_agent_configs` además de los 4 agentes existentes:

| Rol nuevo | Nodo | Descripción |
|---|---|---|
| `analyzer` | `analyze_fr` | Análisis del Feature Request |
| `sdd` | `generate_sdd` | Generación del SDD |
| `qa` | `qa_review` | Revisión de calidad |

Cambio en `graph.py`:

```python
# Antes
llm = _llm().with_structured_output(FRAnalysisOutput)

# Después
llm = await model_router.get_llm("analyzer", org_id, project_id, jwt_token)
llm = llm.with_structured_output(FRAnalysisOutput)
```

Los nodos `analyze_fr`, `generate_sdd` y `qa_review` necesitan recibir `org_id`, `project_id` y `jwt_token` del state para poder llamar al router — estos campos ya están en `OVDState`.

**Archivos afectados:**
- `src/engine/graph.py` — eliminar `_llm()`, actualizar 3 nodos
- `src/engine/model_router.py` — agregar roles `analyzer`, `sdd`, `qa` a defaults

---

### P1.B — Structured output robusto para modelos OSS

**Problema:** `with_structured_output()` en LangChain con Ollama usa function calling interno. Con modelos 7B-14B, el JSON resultante puede ser malformado, truncado o no válido contra el schema Pydantic. Esto provoca `ValidationError` o `OutputParserException` y el ciclo falla sin posibilidad de recuperarse.

**Comportamiento observado por modelo:**

| Modelo | Structured output via Ollama | Fiabilidad estimada |
|---|---|---|
| qwen2.5-coder:7b | JSON mode básico | ~70% en prompts complejos |
| qwen2.5-coder:14b | Function calling | ~85% |
| qwen2.5-coder:32b | Function calling | ~95% |
| claude-sonnet-4-6 | Native | ~99.9% |

**Solución:** Helper `invoke_structured()` con retry y JSON hint explícito:

```python
import json
from pydantic import BaseModel, ValidationError

async def invoke_structured(
    llm,
    messages: list,
    output_class: type[BaseModel],
    max_retries: int = 2,
) -> BaseModel:
    """
    Invoca el LLM con structured output y reintenta con hint JSON si falla.
    Compatible con Claude (via tool_use) y Ollama (via JSON mode).
    """
    schema_hint = json.dumps(output_class.model_json_schema(), indent=2)
    json_hint = HumanMessage(
        content=(
            f"IMPORTANTE: Responde ÚNICAMENTE con un objeto JSON válido "
            f"que cumpla exactamente este schema:\n{schema_hint}\n"
            "Sin texto adicional, sin markdown, sin explicaciones."
        )
    )

    for attempt in range(max_retries + 1):
        try:
            structured_llm = llm.with_structured_output(output_class)
            msgs = messages if attempt == 0 else messages + [json_hint]
            return await structured_llm.ainvoke(msgs)
        except Exception as exc:
            if attempt == max_retries:
                raise
            log.warning(
                "invoke_structured: intento %d/%d falló (%s), reintentando con JSON hint",
                attempt + 1, max_retries + 1, type(exc).__name__,
            )
```

Reemplaza los `llm.with_structured_output(...).ainvoke(...)` directos en todos los nodos.

**Archivos afectados:**
- `src/engine/graph.py` — nuevo helper, actualizar 5 nodos

---

### P1.C — RAG embeddings sin OpenAI

**Problema:** El RAG usa `text-embedding-3-small` (OpenAI, 1536 dims) hardcodeado. Con OSS no hay acceso a OpenAI.

**Variable de entorno actual:**
```bash
OVD_EMBEDDING_PROVIDER=openai   # único valor soportado hoy
OVD_EMBEDDING_MODEL=text-embedding-3-small
```

**Modelos de embedding via Ollama recomendados:**

| Modelo | Dims | Tamaño | Calidad | Recomendación |
|---|---|---|---|---|
| `nomic-embed-text` | 768 | ~274 MB | Buena | ✅ Default OSS |
| `mxbai-embed-large` | 1024 | ~670 MB | Muy buena | Para proyectos grandes |
| `bge-m3` | 1024 | ~1.2 GB | Excelente | Multilenguaje |

**Cambios necesarios:**

1. `packages/opencode/src/ovd/rag.ts` — agregar provider `ollama` en `embed()`:

```typescript
if (provider === "ollama") {
  const ollamaUrl = process.env.OLLAMA_BASE_URL ?? "http://localhost:11434"
  const model = process.env.OVD_EMBEDDING_MODEL ?? "nomic-embed-text"
  const res = await fetch(`${ollamaUrl}/api/embeddings`, {
    method: "POST",
    body: JSON.stringify({ model, prompt: text }),
  })
  const data = await res.json()
  return data.embedding as number[]
}
```

2. Migración SQL — la dimensión del vector en `ovd_rag_documents` está fija a 1536. Cambiar a 768 (nomic) o 1024 (mxbai) requiere:

```sql
-- ATENCIÓN: destruye todos los embeddings existentes
ALTER TABLE ovd_rag_documents DROP COLUMN embedding;
ALTER TABLE ovd_rag_documents ADD COLUMN embedding vector(768);
```

> ⚠️ **Decisión de diseño pendiente:** Los embeddings de distintos modelos son incompatibles entre sí (distintas dimensiones y espacio vectorial). Si se cambia de proveedor, todos los documentos deben re-indexarse. Opciones:
> - **A (simple):** dimensión fija por instancia via env var, migración manual al cambiar
> - **B (flexible):** columna `embedding_model TEXT` en la tabla + índice separado por modelo, permite coexistencia

**Archivos afectados:**
- `packages/opencode/src/ovd/rag.ts`
- Nueva migración `0009_ovd_rag_embedding_dims.sql`

---

## Bloque P2 — Importante (estabilidad en producción)

### P2.A — Timeouts adaptivos por provider

**Problema:** No hay timeout en los `llm.ainvoke()`. Un modelo `qwen2.5-coder:32b` en CPU puede tardar 10+ minutos por nodo. Si Ollama cuelga, el ciclo queda bloqueado indefinidamente.

**Tiempos de generación estimados (2000 tokens output):**

| Hardware | qwen:7b | qwen:14b | qwen:32b |
|---|---|---|---|
| Mac M2 Pro (12 cores) | ~45s | ~90s | ~4 min |
| NVIDIA RTX 4090 | ~8s | ~15s | ~35s |
| CPU 16 cores | ~5 min | ~12 min | >30 min |

**Solución:** Variable `OVD_LLM_TIMEOUT_SECS` y `request_timeout` en `ChatOpenAI`:

```python
# model_router.py
_LLM_TIMEOUT = float(os.environ.get("OVD_LLM_TIMEOUT_SECS", "300"))  # 5 min default

# En build_llm() para Ollama:
return ChatOpenAI(
    model=config.model,
    base_url=base_url,
    api_key="ollama",
    max_tokens=8192,
    request_timeout=_LLM_TIMEOUT,
)
```

**Archivos afectados:**
- `src/engine/model_router.py`

---

### P2.B — Context window awareness

**Problema:** Los prompts del ciclo (SDD + código generado + retry_feedback) pueden superar la ventana de contexto de modelos 7B (32k tokens).

**Ventanas de contexto:**

| Modelo | Context |
|---|---|
| qwen2.5-coder:7b | 32,768 tokens |
| qwen2.5-coder:14b | 131,072 tokens |
| qwen2.5-coder:32b | 131,072 tokens |
| claude-sonnet-4-6 | 200,000 tokens |

**Puntos de riesgo en el grafo:**

- `agent_executor`: recibe SDD completo + código de otros agentes + retry_feedback
- `security_audit`: recibe output de todos los agentes concatenado (truncado hoy a 4000 chars — ok)
- `qa_review`: recibe SDD + output de agentes (truncado hoy a 3000 chars — ok)

**Solución:** Parámetro `OVD_MAX_CONTEXT_TOKENS` (default 28000 para dejar margen en 32k) aplicado como truncado del SDD y del agente output antes de enviar al LLM.

**Archivos afectados:**
- `src/engine/graph.py` — helper `_truncate_to_tokens(text, max_tokens)`
- `src/engine/model_router.py` — exponer `max_context_tokens` en `ResolvedConfig`

---

### P2.C — Temperature por provider

**Problema:** Temperature no está configurada en ningún nodo. Los modelos OSS pequeños son más inestables con temperature alta en nodos de structured output.

**Valores recomendados:**

| Uso | Claude | Ollama ≤7B | Ollama 14B+ |
|---|---|---|---|
| Structured (analyze, SDD, QA, security) | 0.2 | 0.0 | 0.1 |
| Generación libre (agentes de código) | 0.5 | 0.3 | 0.4 |

**Solución:** Campo `temperature` en `ResolvedConfig` y `AgentConfigTable`, con default según provider.

**Archivos afectados:**
- `src/engine/model_router.py` — `ResolvedConfig.temperature`
- `packages/opencode/src/ovd/agent-config.ts` — campo `temperature` opcional

---

## Bloque P3 — Mejoras (no bloquean)

### P3.A — Cost tracking para modelos locales

Con Ollama el costo monetario es $0, pero `estimateCost()` en `cycle-log.ts` siempre aplica el precio de Sonnet.

**Propuesta:**
- Si `provider == "ollama"` → `estimated_cost_usd = 0`
- Agregar campo `inference_ms` en `ovd_cycle_logs` para medir latencia real como proxy de costo de infraestructura

### P3.B — Capability check en startup

Antes de aceptar tráfico, verificar que el modelo configurado responde correctamente:

```python
# startup_check.py — check adicional para Ollama
async def check_ollama_model(model: str, base_url: str) -> dict:
    try:
        llm = ChatOpenAI(model=model, base_url=f"{base_url}/v1", api_key="ollama")
        resp = await llm.ainvoke([HumanMessage('Responde solo con: {"ok": true}')])
        return {"ok": True, "model": model}
    except Exception as e:
        return {"ok": False, "error": str(e), "model": model}
```

### P3.C — Advertencia de modelo mínimo

Log warning si el modelo configurado es conocidamente pequeño para nodos críticos:

```python
_MIN_RECOMMENDED = {
    "analyzer": "qwen2.5-coder:7b",
    "sdd": "qwen2.5-coder:14b",   # SDD requiere razonamiento más profundo
    "qa": "qwen2.5-coder:7b",
}
```

---

## Plan de implementación

### Sprint 1 — Desbloquea OSS end-to-end

| Tarea | Archivos | Complejidad |
|---|---|---|
| P1.A: model_router para `_llm()` | `graph.py`, `model_router.py` | Baja |
| P1.B: `invoke_structured()` con retry | `graph.py` | Media |
| P1.C: nomic-embed-text via Ollama | `rag.ts`, migración SQL | Alta (requiere decisión de diseño) |

### Sprint 2 — Estabilidad en producción

| Tarea | Archivos | Complejidad |
|---|---|---|
| P2.A: `OVD_LLM_TIMEOUT_SECS` | `model_router.py` | Baja |
| P2.B: truncado de contexto | `graph.py`, `model_router.py` | Media |
| P2.C: temperature por provider | `model_router.py`, `agent-config.ts` | Baja |

### Sprint 3 — Polish

| Tarea | Archivos | Complejidad |
|---|---|---|
| P3.A: cost = 0 + `inference_ms` | `cycle-log.ts`, migración SQL | Baja |
| P3.B: capability check startup | `startup_check.py` | Baja |
| P3.C: warning modelo mínimo | `model_router.py` | Baja |

---

## Decisión de diseño pendiente: RAG multi-modelo (P1.C)

Antes de implementar P1.C se requiere decidir:

**Opción A — Dimensión fija por instancia (simple)**
- Una env var `OVD_EMBEDDING_DIMS` define la dimensión al crear la tabla
- Cambiar de modelo requiere migración manual + re-indexado
- Recomendado para instalaciones single-tenant o equipos pequeños

**Opción B — Índice por modelo (flexible)**
- La tabla `ovd_rag_documents` guarda `embedding_model TEXT` y tiene múltiples columnas de vector
- Permite migrar gradualmente sin perder embeddings existentes
- Mayor complejidad de schema y queries
- Recomendado si se prevé cambiar de modelo frecuentemente

---

## Configuración recomendada para Qwen local (estado actual)

Mientras no se implementa Sprint 1, esta configuración minimiza el uso de Claude:

```bash
# .env — los agentes de código usan Qwen, los nodos de análisis siguen en Claude
OVD_MODEL=qwen2.5-coder:7b          # default para agentes via model_router
OLLAMA_BASE_URL=http://localhost:11434

# Los siguientes siguen requiriendo Claude hasta Sprint 1:
ANTHROPIC_API_KEY=sk-ant-api03-...  # aún necesario para analyze_fr, generate_sdd, qa_review
```

Con Sprint 1 completo:
```bash
# .env — 100% local, sin APIs externas
OVD_MODEL=qwen2.5-coder:14b
OLLAMA_BASE_URL=http://localhost:11434
OVD_EMBEDDING_PROVIDER=ollama
OVD_EMBEDDING_MODEL=nomic-embed-text
OVD_LLM_TIMEOUT_SECS=600
# ANTHROPIC_API_KEY ya no es necesario
```
