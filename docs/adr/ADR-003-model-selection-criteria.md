# ADR-003 — Criterios de selección y evaluación de modelos LLM locales

**Estado:** Aceptado — referencia para evaluaciones futuras
**Fecha:** 2026-04-28
**Contexto:** Sprint S76 — cambio de modelo SDD; análisis de propuesta externa rechazada

---

## Resumen

Documenta los criterios de selección de modelos LLM locales en OVD Platform y rechaza una propuesta externa (recibida en sesión S76) que sugería migrar a modelos no existentes y a un orquestador distinto. Sirve como referencia para futuras evaluaciones de migración de stack, generación de frontend complejo, y soporte de sistemas legados en producción.

---

## Contexto

Durante el sprint S76, se recibió una recomendación externa con las siguientes premisas:

1. Cambiar el modelo de frontend a `Qwen3.6-72B` o `Qwen3.6-27B-Vision`
2. Cargar el modelo arquitecto + programador en paralelo en VRAM
3. Migrar el orquestador a Autogen o CrewAI
4. Usar quantization Q6_K o Q8_0 "para no perder inteligencia"

Se realizó un análisis con investigación del estado actual del Qwen ecosystem (abril 2026) y de la arquitectura Apple Silicon. La propuesta fue **rechazada en su totalidad** por hallazgos verificables. Este ADR documenta los criterios para evitar repetir el análisis.

---

## Hallazgos verificados

### 1. Modelos alucinados en la propuesta

| Modelo propuesto | Existencia | Detalle |
|------------------|-----------|---------|
| **Qwen3.6-72B** | ❌ NO existe | Familia Qwen3.6 solo tiene 27B dense + 35B-A3B MoE |
| **Qwen3.6-27B-Vision** | ❌ NO existe | El 27B de Qwen3.6 es text/coding-only |
| Qwen2.5-72B-Instruct | ✅ Existe | Sept 2024, dense, **sin vision** |
| Qwen2.5-VL-72B | ✅ Existe | Enero 2025, vision-language |
| Qwen2.5-Coder-32B | ✅ Existe | Nov 2024, generación anterior |
| Qwen3-VL (varios) | ✅ Existe | Sept-Oct 2025, vision-language MoE/dense |

**Lección:** Verificar existencia en `ollama.com/library` antes de planear cualquier migración. Recomendaciones de ChatGPT/asistentes pueden alucinar nombres de modelos.

### 2. Realidad de Apple Silicon vs NVIDIA

La propuesta asumía paralelismo tipo NVIDIA dual-GPU. En Apple Silicon:

| Aspecto | NVIDIA dual-GPU | Apple Silicon (M-series) |
|---------|-----------------|--------------------------|
| Memoria | VRAM dedicada por GPU | Unificada CPU/GPU |
| Paralelismo | Real (2 modelos = 2× throughput) | **Serial** (GPU única) |
| 2 modelos cargados | Cada uno en su GPU, paralelo | Comparten GPU, time-slicing |
| Throughput con 2 modelos | ~2× single-stream | **~50% single-stream cada uno** |

**Implicación:** "Cargar arquitecto + programador en paralelo para supervisión en tiempo real" no funciona como prometido en Apple Silicon. La GPU única serializa requests entre modelos.

### 3. Benchmarks reales en M5 Pro Max 128 GB

Velocidades verificadas (Q4_K_M, single stream):

| Tamaño | Tipo | tok/s | Tiempo SDD ~3700 tok |
|--------|------|-------|---------------------|
| 8B | Dense | 35-55 | ~70 seg |
| 27-32B | Dense | 12-22 | ~3 min |
| 30B-A3B | MoE (3B activos) | 25-40 | ~1.5 min |
| 70-72B | Dense | **5-9** | **~7-13 min** |
| 235B-A22B | MoE (22B activos) | 8-14 | No cabe en 128 GB |

**Implicación:** Modelos densos 70B+ son inviables para uso interactivo en M5 Pro Max. Los MoE de 30B-A3B son el **sweet spot de velocidad/calidad** en este hardware.

### 4. Quantization — costo/beneficio

| Quantization | Pérdida vs FP16 | Memoria 30B | Recomendación OVD |
|--------------|----------------|-------------|-------------------|
| Q4_K_M | ~3% | 18 GB | **Default — sweet spot** |
| Q6_K | ~1% | 27 GB | Solo para nodos críticos |
| Q8_0 | ~0.5% | 35 GB | Sobredimensionado |

**Implicación:** Q4_K_M validado empíricamente con QA 93/100 en S76. Subir a Q6/Q8 incrementa memoria 50-94% por mejora marginal <2% en QA. ROI negativo.

### 5. Orquestadores — LangGraph vs Autogen/CrewAI

| Aspecto | LangGraph (actual OVD) | Autogen | CrewAI |
|---------|------------------------|---------|--------|
| Nivel | Bajo (state graphs) | Medio | Alto |
| Flexibilidad | Máxima | Media | Baja |
| Conditional edges | ✅ Nativo | Limitado | No |
| Send API (parallel) | ✅ Nativo | Limitado | No |
| Checkpointing | ✅ Nativo | Manual | No |
| Retry loops | ✅ Nativo | Manual | Manual |
| Structured output | ✅ Nativo | Limitado | Limitado |
| Costo de migración | 0 | **Reescritura completa** | **Reescritura completa** |

**Implicación:** LangGraph proporciona **todo** lo que Autogen/CrewAI ofrecen y más. Migrar sería una regresión arquitectural de 6+ meses sin beneficio funcional.

---

## Decisión

OVD Platform mantiene su stack actual y rechaza la propuesta externa.

**Stack confirmado (S76):**
- **Orquestador:** LangGraph (no migrar)
- **Modelo SDD:** `qwen3-coder:30b` (MoE, validado QA 93/100)
- **Modelo coder/runner:** `qwen3-coder:30b`
- **Modelo analyzer:** `deepseek-r1:14b`
- **Modelo QA:** `qwen3-coder:30b`
- **Modelo vision:** `qwen2.5vl:7b`
- **Embeddings:** `nomic-embed-text`
- **Quantization default:** Q4_K_M

---

## Criterios para evaluaciones futuras

Cuando aparezca una propuesta de cambio de modelo o stack, aplicar este checklist **antes** de implementar:

### Checklist de validación de propuestas

1. **Verificar existencia del modelo**
   - [ ] `ollama.com/library/<modelo>` retorna resultado
   - [ ] Versión y fecha de release confirmadas en fuente oficial
   - [ ] Modelfile inspeccionado (`ollama show <modelo> --modelfile`) — distinguir wrapper vs fine-tuned real

2. **Validar viabilidad de hardware**
   - [ ] Memoria Q4_K_M cabe en 128 GB con margen para Postgres + engine
   - [ ] Velocidad estimada (tok/s) suficiente para el SDD esperado (~3700 tok)
   - [ ] Si el modelo se carga con otros, considerar serialización GPU en Apple Silicon

3. **Validar empíricamente vs baseline**
   - [ ] A/B test con FR estándar (PLAN_PRUEBA_OVD.md)
   - [ ] Métricas: QA score, duración, cobertura módulos FR, tareas SDD
   - [ ] Mínimo 3 ciclos para promediar varianza
   - [ ] El nuevo modelo debe **superar** consistentemente el baseline (no empatar)

4. **Costo de migración vs beneficio**
   - [ ] Calcular esfuerzo (líneas de código, tests, docs)
   - [ ] Calcular ahorro o mejora medible (QA, duración, tokens)
   - [ ] Si ratio beneficio/esfuerzo < 2×, descartar

5. **Argumento técnico verificable**
   - [ ] La propuesta cita fuentes oficiales o benchmarks reproducibles
   - [ ] Las premisas (memoria, paralelismo, capacidades) son verificables
   - [ ] No depende de capacidades alucinadas o no documentadas

**Si la propuesta no pasa los 5 puntos: rechazar y documentar.**

---

## Casos de uso futuros donde reevaluar

Este ADR debe revisarse cuando:

### Caso A — Migración de proyecto a otro stack

Cuando un proyecto cliente pida migrar de Oracle a PostgreSQL, de Java a Python, o similar:
- Evaluar si el modelo coder actual (`qwen3-coder:30b`) tiene cobertura suficiente del stack destino
- Si no, considerar modelos especializados (ej: `deepseek-coder:33b` para Java legacy)
- Aplicar checklist de validación antes de cambiar

### Caso B — Frontend complejo con análisis visual

Cuando OVD genere UIs complejas (wireframes, diseños, dashboards interactivos):
- `qwen2.5vl:7b` actual es suficiente para describir imágenes simples
- Para casos complejos (Figma → JSX, error visual → fix CSS), considerar:
  - **Opción A (conservadora):** `qwen3-vl:30b-a3b` (20 GB, MoE 3B activos, ~25-40 tok/s)
  - **Opción B (calidad):** `qwen3-vl:32b` dense (21 GB, 12-22 tok/s)
  - **NO recomendado:** `qwen2.5vl:72b` (49 GB, 5-9 tok/s — overkill y lento)
- Configurar con `OVD_VISION_MODEL=qwen3-vl:30b-a3b` (1 línea en `.env`)
- **No requiere multi-modelo paralelo** — el nodo `describe_image` se ejecuta una vez por ciclo

### Caso C — Soporte de sistemas legados en producción

Cuando OVD soporte issues de producción (root cause, hotfix, troubleshooting):
- El analyzer (`deepseek-r1:14b`) destaca en reasoning — adecuado para diagnóstico
- Para casos críticos (debugging de Oracle 12c, Java Struts, COBOL):
  - Considerar dedicar un agente "investigador" con modelo más grande (Claude Sonnet 4.6 vía API si la calidad lo justifica)
  - Modelos locales gratuitos suficientes para 80% casos
  - API solo para casos críticos donde tiempo > costo
- Patrón: análisis con modelo grande + parche con modelo coder + validación con QA

### Caso D — Especialización por agente del flujo

Hoy todos los agentes runner usan `qwen3-coder:30b` por simplicidad. Si en algún sprint se observa que:
- El SDD necesita más reflexión → considerar `qwen3.6:35b-a3b` (MoE más nuevo, abril 2026)
- El analyzer es lento o impreciso → considerar `qwen3.6:27b` dense
- El frontend agent genera mal CSS → considerar vision model (Caso B)

**Cambio = 1 línea en `.env`:**
```bash
OVD_MODEL_SDD=qwen3.6:35b-a3b
OVD_MODEL_FRONTEND=qwen3-vl:30b-a3b
OVD_MODEL_ANALYZER=qwen3.6:27b
```

OVD ya soporta routing por nodo vía `model_router`. **La infraestructura permite especialización; la decisión es solo qué modelo asignar.**

---

## Tabla de modelos candidatos (referencia rápida)

Modelos verificados y disponibles en `ollama.com/library` (abril 2026):

### Para SDD/architect

| Modelo | Tamaño Q4 | tok/s M5 PM | Cuándo usar |
|--------|-----------|-------------|-------------|
| `qwen3-coder:30b` | 18 GB | 50-60 | **Default actual — validado QA 93** |
| `qwen3.6:35b-a3b` | 24 GB | 25-40 | Si quieres MoE más nuevo |
| `qwen3.6:27b` | 17 GB | 12-22 | Si necesitas dense con calidad |
| `qwen3-coder-next` | 51 GB | 8-15 | Solo casos críticos — lento |

### Para coding (runners)

| Modelo | Tamaño Q4 | tok/s M5 PM | Cuándo usar |
|--------|-----------|-------------|-------------|
| `qwen3-coder:30b` | 18 GB | 50-60 | **Default actual** |
| `qwen2.5-coder:32b` | 20 GB | 12-22 | Solo si qwen3-coder regresiona |
| `deepseek-coder:33b` | 19 GB | 12-22 | Java legacy / sistemas COBOL-style |

### Para frontend con vision

| Modelo | Tamaño Q4 | tok/s M5 PM | Cuándo usar |
|--------|-----------|-------------|-------------|
| `qwen2.5vl:7b` | 6 GB | 35-55 | **Default actual — describe_image básico** |
| `qwen3-vl:30b-a3b` | 20 GB | 25-40 | Frontend agentes con visión |
| `qwen3-vl:32b` | 21 GB | 12-22 | Mockup → JSX complejo |
| `qwen2.5vl:72b` | 49 GB | 5-9 | NO recomendado — overkill |

### Para analyzer/reasoning

| Modelo | Tamaño Q4 | tok/s M5 PM | Cuándo usar |
|--------|-----------|-------------|-------------|
| `deepseek-r1:14b` | 9 GB | 25-40 | **Default actual** |
| `qwen3.6:27b` | 17 GB | 12-22 | Si reasoning más profundo |

---

## Anti-patrones documentados

Lo que NO se debe hacer en OVD:

1. **Cambiar modelos sin A/B test cuantitativo** — la varianza del LLM es alta, una sola corrida no es evidencia
2. **Migrar a Autogen/CrewAI sin justificación funcional clara** — LangGraph ya cubre los casos
3. **Cargar 3+ modelos pinned simultáneamente en Apple Silicon** — la GPU se serializa, no hay paralelismo real
4. **Usar Q6_K/Q8_0 por default** — Q4_K_M validado, costo memoria no justifica el ~2% de mejora
5. **Confiar en recomendaciones sin verificar `ollama.com/library`** — ChatGPT/asistentes pueden alucinar nombres de modelos
6. **Asumir que Apple Silicon = NVIDIA con menos VRAM** — arquitecturas distintas (memoria unificada, GPU única)
7. **Usar modelos densos 70B+ para nodos del flujo** — 5-9 tok/s mata la duración del ciclo

---

## Métricas de éxito del stack actual (baseline a superar)

Cualquier propuesta futura debe superar consistentemente:

| Métrica | Baseline S76 | Objetivo |
|---------|--------------|----------|
| QA score | 93/100 | ≥ 93 |
| SDD compliance | True | True |
| Tareas SDD (FR contratos) | 12 | 10-14 |
| Cobertura módulos FR | 100% | 100% |
| Duración ciclo completo | ~13 min | ≤ 13 min |
| Costo por ciclo | $0 (Ollama local) | ≤ $0.05 |
| Memoria total ocupada | ~30 GB (modelos cargados) | ≤ 50 GB |

---

## Referencias

- [Ollama Library — Qwen3.6](https://ollama.com/library/qwen3.6)
- [Ollama Library — Qwen3-VL](https://ollama.com/library/qwen3-vl)
- [Ollama Library — Qwen2.5-VL](https://ollama.com/library/qwen2.5vl)
- [Apple ML Research — MLX en M5 GPU](https://machinelearning.apple.com/research/exploring-llms-mlx-m5)
- [Apple Silicon M1-M5 LLM benchmark](https://craftrigs.com/benchmarks/apple-silicon-m-series-llm-benchmark-m1-m5/)
- [Qwen3-VL Technical Report (arxiv:2511.21631)](https://arxiv.org/abs/2511.21631)
- [LangGraph vs Autogen vs CrewAI comparativa](https://www.langchain.com/langgraph)
- INFORME_PRUEBA_S76.md (entregas) — validación empírica del baseline
- ADR-002 — Qwen3 thinking mode (precedente de análisis de modelo)

---

## Historial

| Fecha | Cambio |
|-------|--------|
| 2026-04-28 | ADR creado tras análisis de propuesta externa en sesión S76 |
