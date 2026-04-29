# Propuesta Profesional — Claude Code Skills para OVD Platform
## Versión 1.0 | 2026-04-28 | ✅ APROBADA — Fase 1 implementada

### Decisiones aprobadas el 2026-04-28

| Decisión | Estado |
|---|---|
| Separar CLAUDE.md en CLAUDE.md (permanente) + .claude/CONTEXT.md (dinámico) | ✅ Implementado |
| Sesión dedicada a corregir los 5 fallos pre-existentes (S96-G) | ✅ Planificado en CURRENT.md |
| Fix POST /auth/login 500 con prioridad S96-F (antes de S96-D y S96-E) | ✅ Planificado en CURRENT.md |
| Implementar Fase 1 (4 skills) inmediatamente | ✅ Implementado |
| Evaluar impacto Fase 1 antes de proceder con Fase 2 | ✅ Fecha: 2026-05-12 |

### Estado de implementación

| Skill | Archivo | Estado |
|---|---|---|
| `session-start` | `.claude/skills/session-start/SKILL.md` | ✅ Activo |
| `session-close` | `.claude/skills/session-close/SKILL.md` | ✅ Activo |
| `run-tests` | `.claude/skills/run-tests/SKILL.md` | ✅ Activo |
| `pre-push` | `.claude/skills/pre-push/SKILL.md` | ✅ Activo |

### Nota de evaluación Fase 2

> **Fecha de evaluación:** 2026-05-12
> **Criterios:** ¿Sesiones inician más rápido? ¿CI falla menos post-push?
> ¿CONTEXT.md se mantiene actualizado? ¿Reducción de prompts repetitivos?
> Si impacto positivo confirmado → proceder con tdd-cycle, tdd-green, cycle-debug, fix-test.

---

---

## RESUMEN EJECUTIVO

OVD Platform es un sistema de generación de código multi-agente con 17 nodos LangGraph, 4 agentes especializados, 107 archivos de test y un ciclo de desarrollo basado en sprints. El equipo repite los mismos workflows en cada sesión de desarrollo sin automatización de procedimientos.

**Propuesta:** Implementar **12 skills especializados** organizados en 4 categorías estratégicas, mapeados directamente a los flujos diarios identificados en el análisis arquitectónico.

**Beneficio estimado:** Reducir fricción cognitiva en sesiones de desarrollo ~40%, eliminando prompts repetitivos y estandarizando procedimientos.

---

## PARTE 1: ANÁLISIS DEL PROYECTO

### 1.1 Stack Tecnológico

| Capa | Tecnología | Relevancia para Skills |
|---|---|---|
| Orquestación | LangGraph 0.3.0 (17 nodos, 4 agentes) | Skills específicos por nodo/agente |
| API | FastAPI 0.115.0 + SSE | Skills de debugging de endpoints |
| LLMs | Ollama (qwen3-coder:30b) + Claude + OpenAI | Skill de switch de modelo (ADR-003) |
| Base de datos | PostgreSQL 16 + pgvector | Skills de RAG y schema |
| Testing | pytest (unit/integration/e2e/docker) | Skill TDD con markers |
| CI/CD | GitHub Actions (10 jobs paralelos) | Skill de pre-push validation |
| Frontend | React 19 + Vite + TypeScript | Skills diferenciados |
| TUI | Rust + Ratatui | Skills de build/debug |
| Templates | 22 system prompts .md | Skills de auditoría de prompts |
| RAG | pgvector + nomic-embed-text | Skill de consulta RAG |

### 1.2 Workflows Diarios Identificados

| # | Workflow | Frecuencia | Tiempo manual | Candidato |
|---|---|---|---|---|
| 1 | Abrir sesión → leer contexto sprint | Diario | 5-8 min | ✅ ALTO |
| 2 | Implementar tarea TDD (RED-GREEN-REFACTOR) | Diario | Variable | ✅ ALTO |
| 3 | Ejecutar suite tests con markers correctos | Diario | 2-3 min | ✅ ALTO |
| 4 | Debug ciclo OVD fallido | 3-4×/semana | 15-20 min | ✅ ALTO |
| 5 | Commit + update CURRENT.md + push | Diario | 5-10 min | ✅ ALTO |
| 6 | Agregar nodo al grafo (TDD) | 1-2×/semana | 30-45 min | ✅ MEDIO |
| 7 | Cambiar modelo LLM (ADR-003) | Semanal | 10-15 min | ✅ MEDIO |
| 8 | Revisar/editar system prompt de agente | Semanal | 10-20 min | ✅ MEDIO |
| 9 | Validar pre-push (lint + tests + ci) | Diario | 3-5 min | ✅ MEDIO |
| 10 | Consultar RAG para contexto previo | 2-3×/semana | 5-10 min | ✅ BAJO |

### 1.3 Puntos de Dolor Activos

1. `graph.py` tiene 8.226 líneas — encontrar un nodo requiere búsqueda manual
2. 5 tests fallidos pre-existentes — sin diagnóstico sistemático
3. 22 templates sin auditoría consolidada — cambios en uno pueden romper el ciclo
4. ADR-003 no se consulta consistentemente — cambios de modelo sin checklist
5. `CURRENT.md` se actualiza tarde o inconsistentemente — historial incompleto
6. `/auth/login` retorna 500 — bug no documentado con workaround claro
7. Ciclos de sprint sin punto de entrada definido — cada sesión empieza de cero

---

## PARTE 2: MARCO TÉCNICO DE SKILLS

### 2.1 Estructura de Directorio Propuesta

```
ovd-platform/
└── .claude/
    ├── CLAUDE.md                          # existente — no modificar
    ├── settings.json                      # existente
    └── skills/
        ├── session-start/                 # Skill 1
        │   ├── SKILL.md
        │   └── reference/
        │       └── sprint-context.md
        ├── tdd-cycle/                     # Skill 2
        │   ├── SKILL.md
        │   ├── reference/
        │   │   └── pytest-markers.md
        │   └── templates/
        │       └── test-template.py
        ├── run-tests/                     # Skill 3
        │   └── SKILL.md
        ├── cycle-debug/                   # Skill 4
        │   ├── SKILL.md
        │   └── reference/
        │       └── node-index.md
        ├── session-close/                 # Skill 5
        │   └── SKILL.md
        ├── node-scaffold/                 # Skill 6
        │   ├── SKILL.md
        │   └── templates/
        │       └── node-template.py
        ├── model-switch/                  # Skill 7
        │   ├── SKILL.md
        │   └── reference/
        │       └── adr-003-checklist.md
        ├── prompt-audit/                  # Skill 8
        │   └── SKILL.md
        ├── pre-push/                      # Skill 9
        │   └── SKILL.md
        ├── rag-search/                    # Skill 10
        │   └── SKILL.md
        ├── fix-test/                      # Skill 11
        │   ├── SKILL.md
        │   └── reference/
        │       └── failing-tests.md
        └── sprint-report/                 # Skill 12
            └── SKILL.md
```

### 2.2 Convenciones de Diseño

| Convención | Aplicación |
|---|---|
| `SKILL.md` < 500 líneas | Documentación en `reference/` separado |
| `description` front-loaded | Primera oración = caso de uso principal |
| `disable-model-invocation: true` | Skills con side-effects (commit, push, model-switch) |
| `context: fork` | Skills de investigación o análisis largos |
| `allowed-tools` explícito | Cada skill declara solo las tools que necesita |
| `$ARGUMENTS` tipados | Argumentos nombrados con `argument-hint` |
| `paths:` para auto-activación | Skills de template usan paths para detectar contexto |

---

## PARTE 3: LOS 12 SKILLS

### CATEGORÍA A — GESTIÓN DE SESIÓN

#### Skill 1 — `session-start`
*Carga contexto completo del sprint al abrir sesión*

**Invocación:** `/session-start [tarea-opcional]`
**Frecuencia:** Diaria | **Tiempo ahorrado:** 5-8 min/sesión

Qué hace:
- Lee `docs/sprints/CURRENT.md` y extrae sprint activo y tareas pendientes
- Verifica estado de Docker (postgres_db, NATS)
- Muestra los 5 fallos de tests pre-existentes como contexto
- Confirma rama de trabajo (`dev` o feature/SXX)
- Propone la primera tarea con razonamiento

```yaml
---
name: session-start
description: >
  Carga el contexto completo del sprint activo (CURRENT.md, estado infra,
  fallos conocidos) y propone la primera tarea. Invocar al inicio de cada
  sesión de desarrollo de OVD Platform.
argument-hint: "[tarea-específica]"
allowed-tools: Read Bash(docker *) Bash(git *)
disable-model-invocation: false
---
```

---

#### Skill 5 — `session-close`
*Cerrar sesión: commit + update CURRENT.md + push*

**Invocación:** `/session-close "descripción del trabajo realizado"`
**Frecuencia:** Diaria | **Tiempo ahorrado:** 10-15 min/sesión
**`disable-model-invocation: true`** — Claude no puede commitear/pushear por iniciativa propia

Qué hace:
- Corre ruff check + ruff format
- Ejecuta suite rápida (unit only)
- Actualiza `docs/sprints/CURRENT.md` con lo completado
- Genera commit message siguiendo convención del repo
- Solicita confirmación antes de push

```yaml
---
name: session-close
description: >
  Cierra sesión: lint, tests unit, actualiza CURRENT.md, genera commit
  siguiendo convención del proyecto y solicita confirmación para push.
  Usar al final de cada sesión.
argument-hint: "[descripción del trabajo realizado]"
allowed-tools: Bash(ruff *) Bash(python -m pytest *) Read Write Edit Bash(git *)
disable-model-invocation: true
---
```

---

#### Skill 12 — `sprint-report`
*Genera reporte del sprint activo para revisión*

**Invocación:** `/sprint-report`
**Frecuencia:** Final de sprint / demanda | **Tiempo ahorrado:** 20-30 min

Qué hace:
- Lee CURRENT.md e HISTORY.md
- Analiza git log desde inicio del sprint
- Genera tabla de tareas completadas/pendientes con métricas
- Incluye: tests agregados, cobertura delta, líneas modificadas

```yaml
---
name: sprint-report
description: >
  Genera reporte completo del sprint activo: tareas completadas, pendientes,
  métricas git y cobertura. Usar al cierre de sprint o cuando se necesita
  visibilidad del avance.
allowed-tools: Read Bash(git *) Bash(python -m pytest *)
context: fork
agent: Explore
---
```

---

### CATEGORÍA B — DESARROLLO TDD

#### Skill 2 — `tdd-cycle`
*Ciclo TDD completo: RED-GREEN-REFACTOR para OVD*

**Invocación:** `/tdd-cycle "descripción de la funcionalidad"`
**Frecuencia:** 3-5× por sesión

Qué hace:
- **RED:** Genera `tests/test_SXX_feature.py`. Ejecuta pytest. Bloquea si pasan.
- **GREEN:** Implementa código mínimo. Ejecuta pytest hasta GREEN.
- **REFACTOR:** Aplica ruff, revisa patrones OVD (settings.py, exceptions.py).
- Actualiza CURRENT.md al completar.

```yaml
---
name: tdd-cycle
description: >
  Ejecuta ciclo completo RED-GREEN-REFACTOR para OVD Platform. Genera tests
  primero, implementa mínimo para pasar, refactoriza. Invocar cuando
  implementes nueva funcionalidad en el engine.
argument-hint: "[descripción de la funcionalidad a implementar]"
allowed-tools: Read Write Edit Bash(python -m pytest *) Bash(ruff *) Glob Grep
disable-model-invocation: false
---
```

---

#### Skill 3 — `run-tests`
*Ejecutar suite correcta según contexto*

**Invocación:** `/run-tests [unit|integration|e2e|docker|regression]`
**Frecuencia:** Múltiples veces por sesión

Qué hace:
- Selecciona el comando pytest correcto según el marker
- Excluye automáticamente los 5 tests fallidos conocidos con aviso explícito
- Muestra resumen: passed/failed/skipped y cobertura si `--cov`
- Si hay fallo nuevo (no pre-existente): activa diagnóstico inmediato

```yaml
---
name: run-tests
description: >
  Ejecuta la suite de tests correcta para OVD Platform según el marker.
  Maneja automáticamente unit/integration/e2e, excluye fallos pre-existentes
  conocidos y reporta delta. Invocar antes de cada commit.
argument-hint: "[unit|integration|e2e|docker|regression|all]"
arguments: [marker]
allowed-tools: Bash(python -m pytest *) Read
---
```

---

#### Skill 6 — `node-scaffold`
*Crear nuevo nodo LangGraph con TDD desde cero*

**Invocación:** `/node-scaffold "nombre_nodo" "descripción"`
**Frecuencia:** 1-2× por semana | **Tiempo ahorrado:** 30-45 min de boilerplate

Qué hace:
- Genera función async `_run_{nombre}(state: OVDState) -> dict` con estructura OVD
- Genera `tests/test_{nombre}.py` con tests básicos
- Agrega el nodo al registro en `graph.py` con el patrón correcto
- Asigna timeout apropiado siguiendo clasificación de `settings.py`
- Guía el routing condicional necesario

```yaml
---
name: node-scaffold
description: >
  Genera estructura completa para nuevo nodo LangGraph: función async,
  tests TDD, registro en graph.py, timeout en settings.py y routing
  condicional. Invocar cuando se añade funcionalidad nueva al grafo.
argument-hint: "[nombre_nodo] [descripción breve]"
arguments: [nombre, descripcion]
allowed-tools: Read Write Edit Grep Glob
---
```

---

### CATEGORÍA C — DEBUGGING Y DIAGNÓSTICO

#### Skill 4 — `cycle-debug`
*Diagnosticar ciclo OVD fallido sistemáticamente*

**Invocación:** `/cycle-debug [thread_id o nodo]`
**Frecuencia:** 3-4× por semana | **Tiempo ahorrado:** 15-20 min

Qué hace:
- Identifica el nodo de fallo con índice de 17 nodos
- Navega directamente al nodo en `graph.py`
- Revisa el template del agente involucrado si aplica
- Verifica `model_router.py` si el error es de LLM
- Revisa `code_postprocessor.py` si el output está malformado
- Propone fix con contexto del historial de sprints

**Índice de nodos (reference/node-index.md):**

| Nodo | Template | Timeout |
|---|---|---|
| `clone_repo` | — | 120s |
| `describe_image` | — | 120s |
| `analyze_fr` | system_analyzer.md | 300s |
| `web_research` | — | 300s |
| `generate_sdd` | system_sdd.md | 600s |
| `request_approval` | — | — |
| `route_agents` | — | 120s |
| `agent_executor` | system_backend*.md / system_frontend*.md etc. | 1800s |
| `dispatch_frontend` | — | 120s |
| `security_audit` | system_security.md | 1800s |
| `security_retry` | — | 120s |
| `qa_review` | system_qa.md | 1200s |
| `qa_retry` | — | 120s |
| `run_tests` | — | 300s |
| `test_retry` | — | 120s |
| `generate_docs` | — | 300s |
| `deliver` | — | 120s |

```yaml
---
name: cycle-debug
description: >
  Diagnostica ciclo OVD fallido identificando el nodo exacto, revisando
  template, model_router y postprocessor. Invocar cuando un ciclo aborta,
  produce output incorrecto o se cuelga.
argument-hint: "[thread_id | nombre_nodo]"
arguments: [target]
allowed-tools: Read Grep Glob Bash(python -c *)
context: fork
agent: Explore
---
```

---

#### Skill 11 — `fix-test`
*Diagnosticar y corregir tests fallidos del backlog*

**Invocación:** `/fix-test [nombre_test o "all"]`
**Frecuencia:** Sesiones de mantenimiento

Qué hace:
- Carga contexto de los 5 fallos pre-existentes desde `reference/failing-tests.md`
- Para cada test: lee el test, lee el código involucrado, diagnostica causa raíz
- Propone fix mínimo sin romper contratos de sprints anteriores
- Ejecuta test después del fix para confirmar GREEN

**Contenido de reference/failing-tests.md:**

| Test | Causa conocida | Prioridad |
|---|---|---|
| `test_s31::test_cycle_start_ts_reciente` | Flaky por timing — race condition | Media |
| `test_s39::test_usa_cap_800_en_truncate` | Cap 800 obsoleto desde S61-B | Alta (fácil) |
| `test_s47::test_dispatch_frontend_despacha_pendientes` | Roto por S94-fix | Alta |
| `test_s55::test_write_artifacts_overwrites_when_new_content_larger` | write_artifacts cambió post-S55 | Alta |
| `test_s63::test_s63b_cleanup_not_in_run_tests` | RuntimeError — roto por S94-fix | Alta |

```yaml
---
name: fix-test
description: >
  Diagnostica y corrige tests fallidos del backlog pre-existente de OVD.
  Tiene contexto de los 5 fallos conocidos y sus causas raíz. Invocar
  en sesiones de deuda técnica.
argument-hint: "[nombre_test | all]"
arguments: [target]
allowed-tools: Read Grep Bash(python -m pytest *)
---
```

---

### CATEGORÍA D — ARQUITECTURA Y CALIDAD

#### Skill 7 — `model-switch`
*Cambiar modelo LLM siguiendo ADR-003*

**Invocación:** `/model-switch [rol] [modelo]`
**Frecuencia:** Semanal
**`disable-model-invocation: true`** — ningún cambio de modelo sin aprobación explícita

Qué hace:
- Ejecuta checklist obligatorio ADR-003
- Verifica existencia del modelo en `ollama.com/library`
- Calcula VRAM requerida vs disponible (M5 Pro Max: 128 GB)
- Actualiza variable en `.env` y `settings.py`
- Propone A/B test: mínimo 3 ciclos (baseline: QA 93/100, 13 min)

```yaml
---
name: model-switch
description: >
  Cambia el modelo LLM para un rol específico siguiendo checklist ADR-003.
  Verifica existencia, VRAM, baseline y actualiza configuración. Invocar
  SIEMPRE antes de cambiar cualquier modelo.
argument-hint: "[rol: sdd|analyzer|qa|backend|frontend] [modelo:tag]"
arguments: [rol, modelo]
disable-model-invocation: true
allowed-tools: Read Edit Bash(ollama *)
---
```

---

#### Skill 8 — `prompt-audit`
*Auditar system prompt de un agente*

**Invocación:** `/prompt-audit [nombre_agente o "all"]`
**Frecuencia:** Semanal / antes de sprint con cambios de template

Qué hace:
- Carga el template desde `src/engine/templates/system_{agente}.md`
- Verifica variables requeridas: `{project_context}`, `{rag_context}`, `{retry_feedback}`
- Verifica restricciones críticas (NUNCA generes .py desde devops, etc.)
- Compara coherencia con SDD del agente
- Propone ajustes con razonamiento

```yaml
---
name: prompt-audit
description: >
  Audita el system prompt de un agente OVD verificando variables requeridas,
  restricciones críticas y coherencia con SDD. Invocar antes de modificar
  templates o cuando un agente produce outputs inesperados.
argument-hint: "[backend|frontend|database|devops|sdd|qa|security|all]"
arguments: [agente]
allowed-tools: Read Grep Glob
paths: "src/engine/templates/**/*.md"
---
```

---

#### Skill 9 — `pre-push`
*Validación completa pre-push: espeja GitHub Actions*

**Invocación:** `/pre-push`
**Frecuencia:** Diaria (antes de push)
**`disable-model-invocation: true`** — gate explícito, no automático

Qué hace:
- `ruff check --no-fix src/engine/` — verifica sin alterar
- `ruff format --check src/engine/`
- `pytest tests/ -m "not integration and not e2e and not docker" -q`
- Verifica que no haya `os.environ.get` directos en módulos migrados a `settings.py`
- Reporta PASS/FAIL con detalle de cada gate
- Solo si todo pasa: confirma que es seguro hacer push

```yaml
---
name: pre-push
description: >
  Ejecuta la misma validación que CI de GitHub Actions (lint + format +
  tests unit) antes de hacer push. Verifica además convenciones OVD
  (settings.py, imports). Invocar antes de cada git push.
allowed-tools: Bash(ruff *) Bash(python -m pytest *) Bash(git *) Grep Read
disable-model-invocation: true
---
```

---

#### Skill 10 — `rag-search`
*Consultar la base de conocimiento RAG del proyecto*

**Invocación:** `/rag-search "consulta semántica"`
**Frecuencia:** 2-3× por semana

Qué hace:
- Ejecuta búsqueda en pgvector vía script Python
- Retorna top-5 resultados con score de similitud (mínimo 0.65)
- Filtra por colección de proyecto si se especifica
- Útil para recuperar decisiones previas y ciclos similares

```yaml
---
name: rag-search
description: >
  Busca en la base de conocimiento pgvector usando búsqueda semántica.
  Útil para recuperar decisiones de sprints anteriores, ciclos similares
  o contexto histórico. Invocar cuando necesites recordar algo previo.
argument-hint: "[consulta en lenguaje natural]"
arguments: [query]
allowed-tools: Bash(python -c *) Read
---
```

---

## PARTE 4: PLAN DE TRABAJO

### Fases de Implementación

```
FASE 1 — Fundación (1-2 sesiones) — ALTA ROI, BAJO RIESGO
  └── Skill 3: run-tests      ← más usado, más simple
  └── Skill 1: session-start  ← contexto diario
  └── Skill 5: session-close  ← commit diario

FASE 2 — Desarrollo (2-3 sesiones) — CORE DEL WORKFLOW
  └── Skill 2: tdd-cycle       ← metodología central
  └── Skill 9: pre-push        ← gate de calidad
  └── Skill 4: cycle-debug     ← debugging frecuente

FASE 3 — Especialización (2-3 sesiones) — SKILLS TÉCNICOS OVD
  └── Skill 6: node-scaffold   ← nuevo nodo LangGraph
  └── Skill 11: fix-test       ← deuda técnica activa
  └── Skill 8: prompt-audit    ← templates críticos

FASE 4 — Arquitectura (1-2 sesiones) — DECISIONES Y CONOCIMIENTO
  └── Skill 7: model-switch    ← ADR-003 enforced
  └── Skill 10: rag-search     ← knowledge retrieval
  └── Skill 12: sprint-report  ← cierre de sprint
```

### Criterios de Aceptación

| Skill | Criterio de éxito |
|---|---|
| `session-start` | Carga CURRENT.md + estado infra en < 30 seg |
| `session-close` | Commit con formato correcto + CURRENT.md actualizado |
| `run-tests` | Selecciona markers correctos, excluye 5 fallos con aviso |
| `tdd-cycle` | RED confirmado como fallo antes de avanzar a GREEN |
| `cycle-debug` | Identifica nodo y propone fix en < 5 interacciones |
| `node-scaffold` | Genera tests + implementación que pasa `pre-push` |
| `model-switch` | No permite cambio sin completar ADR-003 checklist |
| `prompt-audit` | Detecta variables faltantes y restricciones violadas |
| `pre-push` | Espeja exactamente los gates de GitHub Actions |
| `rag-search` | Retorna resultados con score > 0.65 en < 10 seg |
| `fix-test` | Diagnostica con causa raíz antes de proponer fix |
| `sprint-report` | Genera tabla completa con métricas git en < 2 min |

---

## PARTE 5: ANTI-PATRONES EVITADOS

| Anti-patrón (documentado) | Decisión de diseño |
|---|---|
| Skills > 500 líneas en SKILL.md | Todos bajo 500 líneas; detalle en `reference/` |
| `description` genérica | Cada description tiene frase trigger específica |
| `disable-model-invocation` ausente en side-effects | session-close, pre-push, model-switch lo tienen |
| `context: fork` en guías de referencia | Solo en cycle-debug y sprint-report (tarea explícita) |
| Skills que reemplazan CLAUDE.md | Reglas permanentes en CLAUDE.md; procedimientos en skills |
| Más de 10 skills activos | 12 skills pero 3 con `disable-model-invocation: true` |

---

## PARTE 6: MÉTRICAS DE ÉXITO (30 días)

| Métrica | Baseline actual | Objetivo |
|---|---|---|
| Tiempo promedio apertura sesión | 5-8 min | < 2 min |
| Ciclos TDD sin gate RED confirmado | No medible | 0 |
| Fallos CI post-push evitables | No medible | -80% |
| Tiempo debug ciclo fallido | 15-20 min | < 8 min |
| Commits sin CURRENT.md actualizado | Frecuente | 0 |
| Tests fallidos pre-existentes | 5 | 0 (con Skill 11) |

---

## PARTE 7: ROADMAP DE VERSIONES

### v1.0 — Esta propuesta (12 skills)
Workflows principales cubiertos.

### v1.1 — Post-validación (2-4 semanas)
- `pr-create` — genera PR con descripción estandarizada
- `migration-gen` — genera migración Alembic desde cambio de modelo
- `docker-reset` — reset limpio de infra local (postgres + NATS)

### v2.0 — Post-S96
- `agent-benchmark` — benchmarkea ciclo vs baseline (QA 93/100, 13 min)
- `knowledge-index` — re-indexa RAG con entregas recientes
- `dependency-audit` — verifica compatibilidad de upgrades

---

## FUENTES DE INVESTIGACIÓN

- Documentación oficial Claude Code Skills: `code.claude.com/docs/en/skills`
- Repositorio `wshobson/commands` — 57 comandos production-ready
- Repositorio `glebis/claude-skills` — patrón TDD con subagentes
- Repositorio `awesome-skills/code-review-skill` — patrón progressive loading
- Repositorio `qdhenry/Claude-Command-Suite` — 216+ comandos
- `marmelab.com` — anti-patrones documentados en producción
- `builder.io` — 50 mejores prácticas Claude Code
- `alexop.dev` — workflow TDD forzado con hooks
- Análisis directo del código fuente OVD Platform (2026-04-28)
