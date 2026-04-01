# OVD Platform — Estrategia de Modelo Propio
**Versión:** 1.0
**Fecha:** 2026-03-25
**Autor:** Omar Robles

---

## 1. Declaración estratégica

Uno de los objetivos centrales del OVD es construir un **modelo de IA propio**, especializado en desarrollo de software, entrenado sobre datos reales generados por los propios ciclos de la plataforma.

Este modelo no reemplaza a los modelos de base — los complementa y eventualmente los supera en el dominio específico: generación de código para los stacks tecnológicos concretos que operamos.

**La meta en tres etapas:**

```
ETAPA 1 — Ejecutar con modelos de base
  Hoy: qwen2.5-coder:7b (Ollama local)
  El modelo no conoce nuestros patrones. Lo compensamos con prompts detallados.

ETAPA 2 — Modelo fine-tuneado especializado
  Nuestro propio qwen (u otro base) entrenado en ciclos reales aprobados.
  El modelo ya conoce los patterns de nuestro stack. Menos prompting, mejor output.

ETAPA 3 — Modelo competitivo en el dominio
  Después de suficientes ciclos de calidad, el modelo supera al base en nuestro dominio.
  Para stacks conocidos, ya no se necesita Claude API — el costo cae a cero.
```

---

## 2. El circuito de aprendizaje continuo

Cada ciclo OVD completado y aprobado es una oportunidad de entrenamiento. El circuito es:

```
Feature Request
      │
      ▼
   OVD Engine (LangGraph)
      │
      ▼
   SDD generado → aprobado por humano    ← señal de calidad
      │
      ▼
   Código generado → QA score ≥ umbral   ← señal de calidad
      │
      ▼
   ovd_cycle_logs (tokens, costo, score)
      │
      ▼
   JSONL export diario                   ← datos de entrenamiento
   (solo ciclos con QA score ≥ 0.80 y aprobación humana)
      │
      ▼
   Fine-tuning pipeline (Unsloth / LlamaFactory)
      │
      ▼
   Modelo registrado en ovd_fine_tuned_models
      │
      ▼
   Evaluación benchmark (score antes vs. después)
      │
      ▼
   Activación → agente usa el modelo mejorado
      │
      ▼
   Próximos ciclos generan mejores datos → el ciclo continúa
```

**El circuito ya tiene infraestructura implementada** a nivel de schema y pipeline. La estrategia define cómo usarlo con intención.

---

## 3. Selección del modelo de base

### Estado actual
- **Modelo en uso:** `qwen2.5-coder:7b` via Ollama
- **VRAM disponible:** 4.8GB (limitación de hardware actual)
- **Capacidad:** adecuado para tareas de código moderno. Lento en fan-out multi-agente.

### Criterios de selección de modelo base

El modelo de base correcto para fine-tuning cumple:

| Criterio | Descripción |
|---|---|
| **Licencia permisiva** | Apache 2.0 o equivalente — permite uso comercial y redistribución del modelo fine-tuneado |
| **Especialización en código** | Familia `*-coder` preferida (Qwen-Coder, DeepSeek-Coder, StarCoder2) |
| **Tamaño manejable** | 7B–14B para desarrollo/fine-tuning local; 34B+ para producción en servidor dedicado |
| **Soporte structured output** | Fundamental para que los agentes generen JSON válido en el grafo LangGraph |
| **Comunidad activa** | Actualizaciones frecuentes y benchmarks públicos comparables |

### Candidatos evaluados

| Modelo | Tamaño | Licencia | Structured Output | Evaluación |
|---|---|---|---|---|
| `qwen2.5-coder:7b` | 7B | Apache 2.0 | Bueno | **Actual — MVP** |
| `qwen2.5-coder:14b` | 14B | Apache 2.0 | Muy bueno | Siguiente paso cuando VRAM lo permita |
| `qwen2.5-coder:32b` | 32B | Apache 2.0 | Excelente | Servidor dedicado en producción |
| `deepseek-coder-v2` | 16B | DeepSeek License | Bueno | Evaluar — restricciones comerciales |
| `starcoder2:15b` | 15B | BigCode OpenRAIL | Bueno | Alternativa si Qwen falla en algún stack |
| `codellama:13b` | 13B | Llama 2 License | Regular | Descartado — licencia restrictiva para producto |

### Estrategia de evolución del modelo base

```
HOY          → qwen2.5-coder:7b     (dev local, limitado por VRAM)
FASE B       → qwen2.5-coder:14b    (servidor con más VRAM, mejor calidad)
FASE C       → qwen2.5-coder:32b    (servidor dedicado en producción)
              + modelo fine-tuneado Omar Robles sobre la base Qwen 32B
```

El fine-tuning siempre se hace sobre la versión más grande que el hardware de producción soporte. Más parámetros = más capacidad para absorber los patrones específicos del dominio.

---

## 4. Calidad de los datos de entrenamiento

**Un modelo propio es tan bueno como los datos con los que se entrena.**

### Criterios de inclusión en el dataset de fine-tuning

Solo entran al dataset ciclos que cumplan **todos** los siguientes criterios:

| Criterio | Umbral |
|---|---|
| QA score | ≥ 0.80 |
| Aprobación humana | Requerida (no auto_approve) |
| Ciclo completado | Status = "done", no fallido ni escalado |
| Artefactos completos | requirements.md + design.md + código generado |
| Sin retry loops excesivos | ≤ 2 reintentos en QA/Security |

### Estructura del sample de entrenamiento

Cada ciclo aprobado genera un sample en formato JSONL con la estructura instruction-tuning estándar:

```jsonl
{
  "instruction": "Genera el diseño técnico y código para el siguiente Feature Request en el stack [TypeScript/Hono/Bun/PostgreSQL]:\n\n{feature_request}",
  "input": "{stack_registry_context}",
  "output": "{sdd_completo}\n---\n{codigo_generado}",
  "metadata": {
    "org_id": "...",
    "workspace": "...",
    "stack": "typescript-hono-bun",
    "qa_score": 0.92,
    "agent_role": "backend",
    "cycle_id": "..."
  }
}
```

### Volumen mínimo para fine-tuning efectivo

| Ciclos aprobados | Efecto esperado |
|---|---|
| < 50 | Insuficiente — no entrenar |
| 50–200 | Fine-tuning superficial — mejora leve en patrones frecuentes |
| 200–500 | Fine-tuning sólido — el modelo conoce el stack del equipo |
| 500–1000 | Especialización fuerte — comportamiento diferenciado del base |
| > 1000 | Dominio propio — supera al base en las tareas del dominio |

**Proyección para Omar Robles:** con un ritmo de 5–10 ciclos semanales, el primer fine-tuning significativo es posible en 3–6 meses de uso activo.

---

## 5. Pipeline de fine-tuning

### Herramientas seleccionadas

| Herramienta | Uso | Razón |
|---|---|---|
| **Unsloth** | Fine-tuning primario | 2x más rápido que HuggingFace nativo, optimizado para consumer hardware |
| **LlamaFactory** | Alternativa / experimentación | Interfaz visual, más opciones de configuración |
| **Ollama** | Serving del modelo resultante | Integración nativa ya implementada en el Engine |

### Técnica de fine-tuning

**LoRA (Low-Rank Adaptation)** para todos los fine-tunings. Razón:
- No modifica los pesos base del modelo — el adapter es un archivo pequeño (~100MB)
- Un workspace puede tener su propio adapter sin necesidad de un modelo separado
- Costo computacional bajo: una GPU de 24GB puede entrenar un adapter para Qwen 14B

```
modelo_base (qwen2.5-coder:14b) — inmutable
      +
adapter_omar_v1.gguf (LoRA)
      =
modelo efectivo: qwen2.5-coder:14b + patrones Omar Robles
```

### Proceso de activación

```
1. Dataset JSONL exportado y validado (≥ 200 ciclos de calidad)
2. Fine-tuning via Unsloth → genera adapter .gguf
3. Evaluación benchmark:
   - 20 FRs de referencia ejecutados con modelo base
   - Los mismos 20 FRs ejecutados con modelo fine-tuneado
   - Comparar: QA score, tokens usados, tiempo de ciclo, calidad subjetiva
4. Si eval_score > base_score: activar en ovd_fine_tuned_models
5. El agente usa el modelo fine-tuneado desde el próximo ciclo
6. El ciclo continúa: el modelo mejorado genera mejores outputs → mejor dataset
```

---

## 6. Modelo propio como diferenciador del producto SaaS

Cuando el OVD evolucione a SaaS, el modelo propio es un diferenciador competitivo real:

### Para Omar Robles (uso interno)
- Costo operacional cae con el tiempo: menos dependencia de Claude API para ciclos estándar
- El modelo aprende los patrones del stack de Alemana — genera Oracle 12c correcto sin instrucciones explícitas
- El modelo aprende los patrones de calidad del equipo — QA scores más altos con menos iteraciones

### Para clientes SaaS (Fase C)
- Cada organización cliente genera su propio dataset de fine-tuning
- El modelo de cada cliente se especializa en su stack específico
- **El modelo entrenado en los datos de un cliente pertenece a ese cliente** — esto es una garantía de privacidad y diferenciador comercial fuerte
- Los datos de fine-tuning de un cliente nunca se mezclan con los de otro

### Posicionamiento competitivo
```
GitHub Copilot / Cursor:  modelo genérico entrenado en código público
                          no conoce tu stack, tus patrones, tus restricciones

OVD con modelo propio:    modelo entrenado en TU código, TUS decisiones aprobadas,
                          TUS restricciones de stack
                          cada ciclo lo hace más inteligente para TU contexto
```

---

## 7. Hitos del modelo

| Hito | Descripción | Condición |
|---|---|---|
| **M0 — Base operativo** | qwen2.5-coder:7b ejecutando ciclos en producción | Estado actual ✅ |
| **M1 — Primer dataset** | 200 ciclos de calidad exportados en JSONL válido | ~3 meses de uso activo |
| **M2 — Primer fine-tuning** | Adapter LoRA v1 generado y evaluado | Después de M1 |
| **M3 — Modelo activo** | El adapter supera al base en benchmark propio | Después de M2 |
| **M4 — Especialización Alemana** | El modelo genera Oracle 12c correcto sin restricciones explícitas en el prompt | Después de M3 + Stack Registry estructurado |
| **M5 — Modelo por workspace** | Cada workspace tiene su propio adapter LoRA, entrenado en sus ciclos específicos | Fase B madura |
| **M6 — Modelo producto** | El modelo fine-tuneado es parte del valor diferencial del SaaS — cada org cliente tiene el suyo | Fase C |

---

## 8. Infraestructura ya implementada

El camino hacia M3 no parte de cero. Lo siguiente ya existe:

| Componente | Archivo | Estado |
|---|---|---|
| Schema `ovd_fine_tuned_models` | `packages/opencode/migration-ovd/0003_ovd_fine_tuned_models.sql` | ✅ |
| Model Registry API | `packages/opencode/src/ovd/model-registry.ts` | ✅ |
| JSONL export de ciclos | `src/finetune/export_cycles.py` | ✅ |
| Validación de dataset | `src/finetune/validate_dataset.py` | ✅ |
| Benchmark pre/post fine-tuning | `src/finetune/benchmark.py` | ✅ |
| Pipeline OSS (Unsloth/LlamaFactory) | `src/finetune/upload_finetune_oss.py` | ✅ |
| Pipeline Anthropic | `src/finetune/upload_finetune.py` | ✅ |
| Model activation endpoint | `POST /ovd/models/:id/activate` | ✅ |
| Model router por agente | `src/engine/model_router.py` | ✅ |
| QA score mínimo configurable | `OVD_QA_MIN_SCORE` en Engine | ✅ |

**Lo que falta para llegar a M1 (la distancia es menor de lo esperado):**
- Verificar que `export_cycles.py` filtra por `qa_score ≥ 0.80` y `aprobacion_humana = true` (no solo ciclos completados)
- Dashboard de progreso del dataset en tiempo real: cuántos ciclos válidos acumulados, proyección de cuándo se alcanza el umbral de 200 para el primer fine-tuning
- Conectar `benchmark.py` al Model Registry: que al registrar un modelo la evaluación benchmark quede registrada en `ovd_fine_tuned_models.eval_score`

---

## 9. Decisiones de diseño

**¿Por qué no fine-tuning en la nube (Anthropic, OpenAI)?**
- Los datos de entrenamiento son nuestros — no los enviamos a terceros
- El modelo resultante vive en nuestro servidor — control total
- Sin costo por inferencia una vez deployado via Ollama

**¿Por qué Qwen como base y no Llama?**
- Licencia Apache 2.0 — permite uso comercial sin restricciones en producto SaaS
- La familia Qwen-Coder es consistentemente top en benchmarks de código
- Soporte robusto de structured output — crítico para el grafo LangGraph

**¿Cuándo se usa Claude API vs. modelo propio?**
- Stack legacy complejo (Oracle 12c, Java EE, COBOL) → Claude API (mientras el modelo propio no tenga suficientes ciclos de ese dominio)
- Stack moderno conocido → modelo propio fine-tuneado
- Esta decisión la toma el Context Resolver automáticamente via `model_routing` en el Stack Registry

---

*Documento vivo — actualizar al completar cada hito del modelo.*
