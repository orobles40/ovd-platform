# ADR-002 — Deshabilitar thinking mode en Qwen3-Coder via Ollama

**Estado:** Aceptado — Fix 3-B implementado y validado  
**Fecha:** 2026-04-22  
**Contexto:** Sprint S22 — pruebas de ciclo completo con FR de alta complejidad

---

## Contexto

Durante las pruebas de S22, los agentes de implementación (backend/frontend) completaban el ciclo sin generar artefactos de código. La telemetría OTEL registraba tokens de output (347–456) pero `response.content` retornaba vacío en todos los ciclos.

## Causa raíz identificada

`qwen3-coder-next` opera en **thinking mode** por defecto. Genera un bloque extenso de razonamiento interno antes de producir código. La estructura de respuesta en el endpoint OpenAI-compatible de Ollama (`/v1/chat/completions`) es:

```json
{
  "choices": [{
    "message": {
      "content": "",
      "reasoning": "...tokens de razonamiento..."
    }
  }]
}
```

`LangChain ChatOpenAI` lee únicamente `choices[0].message.content` y **descarta silenciosamente** el campo `reasoning`. Cuando el modelo agota su presupuesto de tokens en el razonamiento sin producir código real, `content` queda vacío.

Issues relacionados en LangChain: [#33672](https://github.com/langchain-ai/langchain/issues/33672), [#36413](https://github.com/langchain-ai/langchain/issues/36413) — sin resolver a la fecha.

## Intentos fallidos

| Intento | Por qué falló |
|---|---|
| `extra_body={"think": False}` | El struct `ChatCompletionRequest` del endpoint `/v1/` de Ollama no tiene el campo `think` — solo existe en `/api/chat` nativo |
| Aumentar `OVD_NODE_TIMEOUT_SECS` a 600s | Resolvió el timeout pero el problema de contenido vacío persistió |
| `OVD_AGENT_PROVIDER=claude` | Funcional pero requiere API externa (Anthropic) — descartado por política |
| `model_kwargs={"reasoning_effort": "none"}` vía `ChatOpenAI` | LangChain emite warning y no lo pasa al modelo; contenido sigue vacío |
| `reasoning_effort="none"` como parámetro directo de `ChatOpenAI` | LangChain ignora el parámetro; QA model (qwen3) generó tokens de razonamiento por 700+ segundos sin producir output |

## Decisión final — Fix 3-B: migrar a `ChatOllama` (2026-04-22)

Migrar el provider `ollama` de `ChatOpenAI` a `ChatOllama` (`langchain-ollama`), que usa la API nativa `/api/chat` de Ollama donde `think=False` funciona de forma confiable.

```python
# model_router.py — provider ollama
from langchain_ollama import ChatOllama

base_url = (config.base_url or _DEFAULT_OLLAMA_URL).rstrip("/")
if base_url.endswith("/v1"):
    base_url = base_url[:-3]  # ChatOllama no usa /v1

return ChatOllama(
    model=config.model,
    base_url=base_url,
    num_predict=8192,
    temperature=config.temperature,
    think=False,  # Deshabilita thinking mode Qwen3+ via API nativa
)
```

El provider `custom` mantiene `ChatOpenAI` con `base_url` arbitraria (Kimi, Groq, etc.) — no se ve afectado.

**Por qué `ChatOllama` y no `ChatOpenAI`:**  
`ChatOllama` usa el endpoint `/api/chat` de Ollama donde `think` es un parámetro de primera clase, mapeado directamente al campo `options.think` del request. El endpoint `/v1/chat/completions` (compatible con OpenAI) no expone este parámetro de forma confiable a través de LangChain.

## Validación (2026-04-22)

Ciclo completo con FR `factorial(n: int) -> int`:
- `agent_executor`: completó en ~15s — generó `src/factorial.py` con 457 tokens de output real
- `qa_review`: completó — score 65/100 con 7 issues reales listados (no vacío)
- `generate_docs`: completó — README generado
- Duración total del ciclo: **1m 18s** (vs. timeouts de 600s+ con el issue activo)

## Otros hallazgos del diagnóstico (2026-04-22)

### Timeout insuficiente (corregido)
`OVD_NODE_TIMEOUT_SECS=120` era insuficiente para FRs con 16+ tareas en Ollama local. Aumentado a 600s. Se propone timeout dinámico basado en número de tareas del SDD para S23 (GAP-R1).

### Agentes paralelos saturan GPU (pendiente S23)
`_dispatch_agents` lanza backend y frontend en paralelo via `Send`. Con Ollama local, ambos compiten por la misma GPU — cada uno consume el timeout simultáneamente. Propuesta: `OVD_CONCURRENCY_MODE=serial|parallel` para serializar en entornos locales.

### DB schema desactualizado (pendiente)
```
psycopg.errors.UndefinedColumn: column p.time_created does not exist
relation "ovd_audit_logs" does not exist
```
No bloquea el ciclo principal pero rompe la auditoría. Requiere ejecutar migraciones pendientes.

### Dashboard: "Ciclo finalizado — undefined" (corregido)
`FrLauncher.tsx` case `done` leía `ev.data.status` (inexistente) en vez de `ev.data.summary`. Corregido en el mismo commit.

## Bug adicional corregido — `_write_artifacts` argumento faltante

`graph.py` línea 1454 (path S17T tool calling fallback): llamada a `_write_artifacts(final_output, directory)` con 2 argumentos en vez de 3. Corregido a `_write_artifacts(final_output, directory, agent_name)`.

## Consecuencias

- Todos los modelos `ollama` en `build_llm()` usan `ChatOllama` con `think=False` — no afecta a modelos sin thinking mode (el parámetro es ignorado por modelos como `ovd-arch-assistant` y `deepseek-r1`)
- Provider `custom` sigue usando `ChatOpenAI` — sin cambios para integraciones externas
- Si un modelo Ollama futuro tiene comportamiento distinto con `think=False`, revisar este parámetro

---

## Addendum S97-F (2026-04-29) — `think=False` era ignorado silenciosamente

**Estado:** Corregido — `reasoning=False` implementado en model_router.py

### Síntoma observado

Durante la validación del ciclo S97, el nodo `qa_review` estuvo bloqueado **68 minutos** en lugar de los ~5-7 min esperados. El nodo `security_audit` y los agentes del fan-out presentaron el mismo problema (~60 min cada uno).

### Causa raíz

`ChatOllama` (langchain-ollama) **no tiene `think` como campo válido** en su modelo Pydantic. Al pasar `think=False` al constructor, el parámetro era silenciosamente descartado (Python acepta kwargs extras sin error). El modelo qwen3-coder:30b operaba en thinking mode ON por defecto, generando bloques `<think>` de 50,000–100,000 tokens antes de cada respuesta.

```python
# Verificación
from langchain_ollama import ChatOllama
"think" in ChatOllama.model_fields  # → False
"reasoning" in ChatOllama.model_fields  # → True
```

El campo correcto documentado en langchain-ollama es `reasoning` (tipo `bool | str | None`):

```python
# model_router.py — ANTES (S22, ignorado)
return ChatOllama(..., think=False)

# model_router.py — DESPUÉS (S97-F, correcto)
return ChatOllama(..., reasoning=False)
```

### Impacto antes del fix

| Nodo | Duración observada | Duración esperada |
|---|---|---|
| `qa_review` | ~68 min | ~5-7 min |
| `security_audit` | ~60 min | ~5-10 min |
| Agentes fan-out (×8) | ~7 min c/u → ~56 min total | ~5 min c/u → ~40 min total |
| Ciclo completo | >2h (nunca completó) | ~60-90 min |

### Lección

El parámetro `think=False` funcionaba aparentemente en S22 porque el modelo usado era `qwen3-coder-next` (diferente variante) o el contexto era suficientemente pequeño para que el thinking completara dentro del timeout. Con `qwen3-coder:30b` y contextos grandes (20k+ tokens de código), el thinking supera ampliamente los timeouts configurados.

**Regla:** Antes de usar un parámetro de constructor en un modelo Pydantic de LangChain, verificar con `ModelClass.model_fields`. Parámetros no reconocidos se descartan sin error ni warning.
