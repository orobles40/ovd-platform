# OVD Platform — Gaps vs Diseño de Referencia
**Fecha de análisis:** 2026-03-24
**Fuente:** `/Volumes/TOSHIBA EXT/Proyectos Personales/Oficina Virtual/` (SDD v19, graph.zip, RAG zip, templates)
**Estado:** En revisión

---

## Resumen ejecutivo

Comparación entre la implementación actual (Phase 1 + Phase 2) y el diseño de referencia
original del sistema VDO (SDD_VDO_v19, graph.zip). Se identificaron 10 gaps ordenados
por impacto sobre la correctitud y el costo operativo.

---

## GAP-001 — Nodo `security_audit` faltante
**Estado:** ⬜ Pendiente
**Impacto:** Alto
**Complejidad:** Media
**Archivo a modificar:** `src/engine/graph.py`

### Descripción
El diseño de referencia tiene dos nodos de validación separados y secuenciales:

```
qa_validation → security_audit → finalize
```

La implementación actual solo tiene `qa_review`, que mezcla QA y seguridad en una sola llamada LLM.
El `SecurityAgent` de referencia corre checks específicos:
- Bandit (Python)
- SpotBugs (Java legacy)
- OWASP Top 10 healthcare
- Validación de Oracle Wallet (credenciales nunca en texto plano)
- Datos sensibles de pacientes (nunca fuera de infra controlada)

### Impacto actual
Sin `security_audit` dedicado, los checks de seguridad quedan subsumidos en el score QA
y pueden no ejecutarse con el rigor necesario para un sistema que maneja datos de pacientes.

### Fix requerido
1. Agregar clase `SecurityAuditOutput` (Pydantic) con campos: `passed`, `score`, `findings`,
   `owasp_concerns`, `healthcare_violations`, `credentials_exposure`
2. Agregar nodo `security_audit` en el grafo después de `qa_review`
3. Actualizar `route_after_qa` para ir a `security_audit` (no a `deliver`)
4. Agregar `route_after_security` que va a `deliver` o `handle_escalation`

---

## GAP-002 — `Send()` API de LangGraph no usada en dispatch
**Estado:** ✅ Implementado
**Impacto:** Medio
**Complejidad:** Media
**Archivo a modificar:** `src/engine/graph.py`

### Descripción
La referencia usa el fan-out nativo de LangGraph:

```python
def dispatch_agents(state: VDOState) -> list[Send]:
    return [Send("agent_executor", {"spec": spec}) for spec in specs]
```

La implementación actual usa `asyncio.gather` dentro del nodo `execute_agents`.

### Diferencia clave
Con `Send()`:
- Cada agente tiene su propio nodo en el grafo → checkpointing individual
- Re-dispatch selectivo posible (solo los agentes que fallaron)
- LangGraph Studio puede visualizar el fan-out correctamente
- Compatible con retry loops (GAP-005)

Con `asyncio.gather` (actual):
- Un solo nodo → un solo checkpoint para todos los agentes
- Si uno falla, no hay forma de re-ejecutar solo ese agente
- No se puede visualizar el fan-out en LangGraph Studio

### Fix requerido
1. Separar `execute_agents` en `dispatch_agents` (devuelve `list[Send]`) y
   `agent_executor` (instanciado N veces)
2. Actualizar el `OVDState` para usar `Annotated[list, operator.add]` en `agent_results`
   (acumulación en lugar de reemplazo)

---

## GAP-003 — Sistema de configuración de modelos por agente (desde la plataforma)
**Estado:** ✅ Implementado via GAP-013a
**Impacto:** Alto (costo operativo + flexibilidad)
**Complejidad:** Alta
**Archivos a crear/modificar:**
- `packages/opencode/src/ovd/agent-config.ts` — tabla y namespace de config de agentes
- `packages/opencode/src/server/routes/ovd.ts` — endpoints CRUD de config
- `src/engine/model_router.py` — carga config desde DB y resuelve el modelo en runtime
- `src/engine/graph.py` — usa `model_router` en lugar de `_llm()` fijo

### Descripción
Se requiere un sistema de configuración de modelos **gestionable desde la propia OVD Platform**
(no un archivo externo), donde el administrador puede definir qué modelo usa cada agente:

```
┌─────────────────────────────────────────────────────────┐
│  Configuración de Agentes — org: omar-demo         │
├──────────────┬──────────────────┬────────┬──────────────┤
│ Agente       │ Modelo           │ Provider │ Endpoint   │
├──────────────┼──────────────────┼────────┼──────────────┤
│ legacy       │ qwen2.5-coder:14b│ ollama │ localhost:…  │
│ data         │ kimi-k2          │ api    │ moonshot.cn  │
│ backend      │ qwen2.5-coder:7b │ ollama │ localhost:…  │
│ frontend     │ qwen2.5-coder:7b │ ollama │ localhost:…  │
│ database     │ qwen2.5-coder:14b│ ollama │ localhost:…  │
│ devops       │ qwen2.5-coder:7b │ ollama │ localhost:…  │
│ qa           │ qwen2.5-coder:7b │ ollama │ localhost:…  │
│ security     │ claude-sonnet-4-6│ claude │ anthropic    │
└──────────────┴──────────────────┴────────┴──────────────┘
```

La config se persiste en PostgreSQL por `org_id`, los agentes la leen en cada ciclo.
Cambiar el modelo desde la plataforma tiene efecto en el próximo ciclo — sin reiniciar.

### Providers soportados

| Provider | Cómo se conecta | Casos de uso |
|----------|-----------------|--------------|
| `ollama` | HTTP a `OLLAMA_BASE_URL` local | Modelos locales: Qwen, Kimi-local, DeepSeek, Llama |
| `claude` | Anthropic SDK con `ANTHROPIC_API_KEY` | Claude Haiku / Sonnet / Opus |
| `openai` | OpenAI SDK compatible | GPT-4o, o1, cualquier API OpenAI-compatible |
| `custom` | HTTP directo con API key configurable | Kimi API, Moonshot, Groq, Together, etc. |

### Tabla de base de datos

```sql
CREATE TABLE ovd_agent_configs (
  id           TEXT PRIMARY KEY,
  org_id       TEXT NOT NULL,
  agent_role   TEXT NOT NULL,   -- legacy | data | backend | frontend | database | devops | qa | security
  provider     TEXT NOT NULL,   -- ollama | claude | openai | custom
  model        TEXT NOT NULL,   -- qwen2.5-coder:14b | claude-sonnet-4-6 | kimi-k2 | etc.
  base_url     TEXT,            -- para ollama y custom
  api_key_env  TEXT,            -- nombre de la variable de entorno con la API key
  skill_file   TEXT,            -- path al template de prompt personalizado
  active       BOOLEAN NOT NULL DEFAULT true,
  time_updated TIMESTAMP NOT NULL DEFAULT NOW(),
  UNIQUE (org_id, agent_role)
);
```

### Endpoints requeridos

```
GET  /ovd/agent-config              — listar config de todos los agentes de la org
PUT  /ovd/agent-config/:agentRole   — actualizar modelo/provider de un agente
POST /ovd/agent-config/reset        — restaurar defaults de la org
```

### Fix requerido
1. Crear tabla `ovd_agent_configs` en migración SQL y schema Drizzle
2. Crear `packages/opencode/src/ovd/agent-config.ts` con CRUD y defaults
3. Agregar endpoints en `ovd.ts`
4. Crear `src/engine/model_router.py` que consulta la config vía API del Engine
   y devuelve el `ChatModel` (LangChain) correspondiente al agente y org
5. Actualizar `graph.py` para que cada agente llame `model_router.resolve(agent_role, org_id)`
   en lugar de `_llm()` fijo
6. Agregar al dashboard: tabla de configuración de agentes por org

### Estado inicial (defaults al crear una org)
Todos los agentes apuntan a Ollama local con `qwen2.5-coder:7b`.
El agente `legacy` tiene `force_cloud_warning: true` como recordatorio de que
tareas Java/iBATIS/Spring 2.5 requieren un modelo de mayor capacidad.

---

## GAP-004 — Sin `constraints_version` ni Uncertainty Register
**Estado:** ⬜ Pendiente
**Impacto:** Alto
**Complejidad:** Media
**Archivo a modificar:** `src/engine/graph.py`, `OVDState`

### Descripción
El diseño de referencia incluye en el estado del grafo:

```python
constraints_version: str = "1.0"   # versión vigente de constraints.md
```

Cada agente:
1. Lee `constraints.md` completo antes de generar código
2. Incluye `-- CONSTRAINTS_VERSION: 1.0` en la cabecera de todo SQL generado
3. Emite `uncertainty_alerts` cuando detecta ambigüedad no resuelta

Ejemplo real del `output_FR_2026_002.json`:
```json
"uncertainty_alerts": [
  "Compatibilidad WebLogic 12.2.1.4 con JDK 11 sin confirmar. Verificar versión JVM antes del deploy en cada sitio."
]
```

El Uncertainty Register protege contra deploys con supuestos no verificados.

### Fix requerido
1. Agregar `constraints_version: str` y `uncertainty_alerts: list[str]` al `OVDState`
2. Crear `constraints_alemana_v1.0.md` en `src/engine/` con todas las restricciones
3. Inyectar el contenido de constraints.md en cada system prompt de agente
4. Agregar campo `uncertainty_alerts` al evento `done` del Engine
5. Persistir alerts en `ovd_cycle_logs` (nueva columna `uncertainty_alerts_json`)

---

## GAP-005 — Sin retry loops en QA y Security (máx. 3 iteraciones)
**Estado:** ⬜ Pendiente
**Impacto:** Medio
**Complejidad:** Baja
**Archivo a modificar:** `src/engine/graph.py`

### Descripción
El diseño de referencia permite hasta 3 re-ejecuciones antes de escalar:

```
qa_validation → rechazado → dispatch_agents (re-ejecución, intento 2)
             → rechazado → dispatch_agents (re-ejecución, intento 3)
             → rechazado → handle_escalation (humano)
```

La implementación actual:
```
qa_review → falla → handle_escalation (humano directo)
```
Sin re-intentos automáticos, el arquitecto debe intervenir en cada falla de QA,
incluso en casos que el agente podría corregir solo.

### Fix requerido
1. Agregar `qa_iterations: int` y `security_iterations: int` al `OVDState`
2. Actualizar `route_after_qa` y `route_after_security` para incrementar el contador
   y redirigir a `execute_agents` si `iterations < 3`, o a escalación si `>= 3`

---

## GAP-006 — RAG sin seed de conocimiento Alemana
**Estado:** ⬜ Pendiente
**Impacto:** Alto
**Complejidad:** Alta
**Archivos a crear:** `src/engine/rag_seed.py`, `src/engine/constraints_alemana_v1.0.md`

### Descripción
La referencia incluye `seed.py` que carga en pgvector antes del primer uso:

- Features **prohibidas** en Oracle 12c Release 1:
  - `FETCH FIRST N ROWS ONLY` (usar `ROWNUM`)
  - `WITH RECURSIVE` (usar `CONNECT BY / START WITH`)
  - JSON nativo (`JSON_VALUE`, `JSON_OBJECT`, etc.)
  - `APPROX_COUNT_DISTINCT`
- Patrones de cabecera SQL obligatoria con `-- CONSTRAINTS_VERSION`
- Estructura de los 270+ SQL mapping files de iBATIS
- Reglas de bifurcación por sede: `/bifur/cas/`, `/bifur/cat/`, `/bifur/cav/`
- Arquitectura del pipeline HHMM: Oracle AQ → NATS → APIVALID
- Stack Java legacy: Struts 1.3, iBATIS 2.x, Spring 2.5, WebLogic 12.2.1.4

Sin este seed, los agentes no tienen contexto del stack de Alemana al arrancar
y pueden generar código incompatible con Oracle 12c o con la arquitectura legacy.

### Fix requerido
1. Crear `constraints_alemana_v1.0.md` con todas las restricciones del proyecto
2. Crear `src/engine/rag_seed.py` que indexe el archivo en pgvector al arrancar
3. Agregar llamada a `rag_seed.py` en el startup de `api.py` (solo si RAG está vacío)
4. Agregar script `scripts/seed-rag.sh` para ejecución manual

---

## GAP-007 — `generate_sdd` produce 1 doc en lugar de 4 artefactos
**Estado:** ✅ Implementado
**Impacto:** Bajo
**Complejidad:** Baja
**Archivo a modificar:** `src/engine/graph.py`

### Descripción
La referencia genera 4 artefactos separados:

| Artefacto | Contenido |
|-----------|-----------|
| `requirements.md` | Qué construir, criterios de aceptación, sedes afectadas |
| `design.md` | Cómo construirlo, stack, patrones |
| `constraints.md` | Qué NO hacer (restricciones específicas de la tarea) |
| `tasks.md` | Sub-tareas por agente con dependencias |

La implementación actual genera un solo documento Markdown como SDD.

### Fix requerido
Actualizar `generate_sdd` para producir los 4 documentos y almacenarlos en el
`sdd` dict del estado: `{ requirements, design, constraints, tasks, content }`.

---

## GAP-008 — Templates de prompts hardcodeados en graph.py
**Estado:** ⬜ Pendiente
**Impacto:** Bajo
**Complejidad:** Baja
**Archivo a crear:** `src/engine/templates/`

### Descripción
La referencia tiene templates versionados en archivos externos:
- `template_data_agent_v1.0.md`
- `template_legacy_agent_v1.0.md`
- `template_integration_agent_v1.0.md`
- `template_otros_agentes_v1.0.md`

Los system prompts actuales están hardcodeados en `graph.py`.
Los templates externos permiten actualizar los prompts sin tocar el código.

### Fix requerido
1. Crear `src/engine/templates/` con un `.md` por agente
2. Cargarlos en `graph.py` al inicializar con `Path("templates/...").read_text()`

---

## GAP-009 — Research Agent no implementado
**Estado:** ✅ Implementado
**Impacto:** Bajo (a largo plazo)
**Complejidad:** Alta
**Archivo a crear:** `src/engine/research.py`

### Descripción
Agente dedicado que mantiene el RAG actualizado con:
- CVEs nuevos relevantes para el stack (Java EE, Oracle, FastAPI)
- Deprecaciones de APIs usadas
- Nuevas versiones de Oracle con features habilitables en CAT/CAV
- Actualizaciones de documentación legacy

No existe en la implementación actual.

### Fix requerido
Implementar `ResearchAgent` siguiendo el patrón de `research.py` de la referencia.
Activable vía endpoint `POST /ovd/research/run` o scheduled job.

---

## GAP-010 — Sin LangSmith tracing
**Estado:** ✅ Implementado
**Impacto:** Bajo
**Complejidad:** Baja
**Archivos modificados:** `docker-compose.yml`

### Descripción
La referencia recomienda LangSmith para:
- Trazabilidad de llamadas LLM (qué prompt generó qué output)
- Métricas de costo por ciclo (tokens usados por agente)
- Debugging de prompts en producción

La implementación actual tiene logging básico pero sin integración de tracing.

### Fix requerido
1. Agregar `LANGCHAIN_TRACING_V2=true` y `LANGCHAIN_API_KEY` en `docker-compose.yml`
2. El SDK de LangChain ya instrumenta automáticamente si las variables están presentes

---

## GAP-011 — Project Profile: stack tecnológico configurable por proyecto
**Estado:** ⬜ Pendiente
**Impacto:** Crítico (escalabilidad de la plataforma)
**Complejidad:** Alta
**Archivos a crear/modificar:**
- `packages/opencode/src/tenant/schema.ts` — extender `ovd_projects` o nueva tabla
- `packages/opencode/src/server/routes/tenant.ts` — endpoints de perfil
- `src/engine/graph.py` — inyectar perfil en prompts dinámicamente
- `packages/opencode/migration-ovd/` — nueva migración SQL

### Descripción
Sin este gap, la OVD Platform está **acoplada al stack de Alemana**. Los system prompts
mencionan Oracle 12c/19c, iBATIS, Spring 2.5 y Bun+Hono hardcodeados. Si un cliente
usa PHP+MySQL, Python+FastAPI o .NET+SQL Server, los agentes generarán código incorrecto.

**El objetivo de la plataforma es ser universal:** cualquier empresa, cualquier stack,
sistemas legados o nuevos. El Project Profile es la pieza que hace posible esto.

### Cómo funciona

Cada proyecto tiene un perfil que define su stack. Los agentes leen ese perfil antes
de generar código y adaptan sus respuestas al contexto del cliente:

```
Empresa A — Proyecto "Sistema RRHH"      Empresa B — Proyecto "E-commerce"
─────────────────────────────────────    ─────────────────────────────────
Stack:       Java 11 + Spring Boot       Stack:       Next.js + TypeScript
Base datos:  Oracle 19c                  Base datos:  PostgreSQL 15
Legado:      Struts 1.3 + iBATIS         Legado:      ninguno
QA tools:    JUnit 5 + Checkstyle        QA tools:    Vitest + ESLint
Restricciones: sin lambdas Java 8-       Restricciones: sin N+1 queries
Agentes:     backend, data, legacy       Agentes:     frontend, backend
```

Los prompts de los agentes se construyen dinámicamente:
```
"Eres un agente backend. El proyecto usa {stack}. La base de datos es {db_engine}.
Restricciones específicas: {constraints}. Herramientas de QA: {qa_tools}."
```

### Tabla de base de datos

```sql
CREATE TABLE ovd_project_profiles (
  id                  TEXT PRIMARY KEY,
  project_id          TEXT NOT NULL UNIQUE REFERENCES ovd_projects(id) ON DELETE CASCADE,
  org_id              TEXT NOT NULL,

  -- Stack tecnológico
  language            TEXT NOT NULL DEFAULT 'typescript',   -- typescript | python | java | php | csharp | etc.
  framework           TEXT,                                  -- hono | spring-boot | fastapi | laravel | etc.
  db_engine           TEXT NOT NULL DEFAULT 'postgresql',   -- postgresql | oracle | mysql | mongodb | sqlserver | etc.
  db_version          TEXT,                                  -- 19c | 15 | 8.0 | etc.

  -- Sistemas legados del proyecto (puede estar vacío)
  legacy_stack        TEXT,                                  -- descripción del stack legacy si existe
  legacy_constraints  TEXT,                                  -- restricciones específicas del legado

  -- Criterios de calidad
  qa_tools            TEXT NOT NULL DEFAULT 'jest',         -- herramientas de test del proyecto
  min_coverage        INTEGER NOT NULL DEFAULT 80,          -- cobertura mínima requerida (%)
  security_framework  TEXT NOT NULL DEFAULT 'owasp',        -- owasp | pci | hipaa | custom

  -- Restricciones libres del proyecto
  custom_constraints  TEXT,                                  -- restricciones adicionales en texto libre

  -- Agentes habilitados para este proyecto
  enabled_agents      TEXT NOT NULL DEFAULT 'frontend,backend,database,devops',

  -- Contexto de negocio (alimenta el RAG seed del proyecto)
  business_context    TEXT,                                  -- descripción del dominio de negocio
  architecture_notes  TEXT,                                  -- notas de arquitectura relevantes

  time_created        TIMESTAMP NOT NULL DEFAULT NOW(),
  time_updated        TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### Endpoints requeridos

```
GET  /tenant/project/:id/profile         — obtener perfil del proyecto
PUT  /tenant/project/:id/profile         — crear o actualizar perfil
GET  /tenant/project/:id/profile/agents  — listar agentes habilitados
```

### Cambios en el Engine

`graph.py` debe recibir el perfil en el estado del grafo y usarlo para construir
los system prompts dinámicamente:

```python
class OVDState(TypedDict):
    # ... campos actuales ...
    project_profile: dict   # ← NUEVO: perfil del proyecto inyectado al iniciar sesión

def _build_system_prompt(agent_role: str, profile: dict) -> str:
    """Construye el system prompt del agente basado en el perfil del proyecto."""
    return AGENT_PROMPT_TEMPLATES[agent_role].format(
        language=profile.get("language", "typescript"),
        framework=profile.get("framework", ""),
        db_engine=profile.get("db_engine", "postgresql"),
        db_version=profile.get("db_version", ""),
        legacy_stack=profile.get("legacy_stack", "ninguno"),
        legacy_constraints=profile.get("legacy_constraints", ""),
        qa_tools=profile.get("qa_tools", "jest"),
        security_framework=profile.get("security_framework", "owasp"),
        custom_constraints=profile.get("custom_constraints", ""),
    )
```

### Relación con otros gaps

- **GAP-003** (config de modelos): el perfil puede definir qué agentes usar → el router
  solo instancia los agentes habilitados para el proyecto
- **GAP-006** (RAG seed): en lugar de seed global de Alemana, cada proyecto tiene su
  propio seed basado en `business_context` + `architecture_notes`
- **GAP-008** (templates): los templates de prompts usan variables del perfil

### Impacto si NO se implementa
La plataforma solo funciona correctamente para proyectos Oracle + Java/TypeScript.
Cualquier otro cliente requeriría modificar el código fuente.

---

## GAP-012 — Model Registry: ciclo de aprendizaje continuo por cliente
**Estado:** ✅ Implementado via GAP-013b
**Impacto:** Crítico (diferenciador competitivo de la plataforma)
**Complejidad:** Alta
**Archivos a crear/modificar:**
- `packages/opencode/src/ovd/model-registry.ts` — tabla y namespace
- `packages/opencode/src/server/routes/ovd.ts` — endpoints de registro y asignación
- `src/finetune/upload_finetune.py` — registrar el modelo al completar el job
- `packages/opencode/src/server/routes/dashboard.ts` — mostrar modelos activos por org

### Descripción
El Model Registry cierra el **ciclo de aprendizaje continuo** de la plataforma:

```
Empresa usa la plataforma
        ↓
Ciclos reales se acumulan en ovd_cycle_logs (por org_id y project_id)
        ↓
Fine-tuning pipeline: export → validate → upload → job Anthropic
        ↓
Modelo fine-tuneado registrado en ovd_fine_tuned_models
  (qué org, qué proyecto, qué stack, cuántos ciclos, cuándo)
        ↓
Se asigna automáticamente al agente correspondiente en ovd_agent_configs
        ↓
Próximos ciclos de esa empresa usan el modelo que aprendió de su propio trabajo
        ↓
Más ciclos → siguiente versión del modelo → mejor calidad progresiva
```

El modelo no solo conoce el stack genérico — conoce **las convenciones específicas de ese
cliente**: cómo nombra variables, qué patrones usa, qué restricciones aplica, cómo
estructura sus tests. Esto es imposible de lograr con un modelo genérico.

### Tabla de base de datos

```sql
CREATE TABLE ovd_fine_tuned_models (
  id                  TEXT PRIMARY KEY,
  org_id              TEXT NOT NULL,
  project_id          TEXT,            -- NULL = aplica a toda la org

  -- Origen del modelo
  base_model          TEXT NOT NULL,   -- claude-haiku-4-5-20251001
  ft_model_id         TEXT NOT NULL,   -- ID devuelto por Anthropic Fine-tuning API
  ft_job_id           TEXT NOT NULL,   -- job_id del pipeline de fine-tuning
  file_id             TEXT NOT NULL,   -- file_id del dataset subido

  -- Métricas de entrenamiento
  trained_on_cycles   INTEGER NOT NULL,  -- cuántos ciclos usados para entrenar
  dataset_path        TEXT,              -- ruta al JSONL usado
  stack               TEXT,              -- stack del proyecto (del profile)
  training_loss       FLOAT,             -- loss final (si disponible)

  -- Control
  status              TEXT NOT NULL DEFAULT 'training',  -- training | active | deprecated
  active              BOOLEAN NOT NULL DEFAULT false,
  time_created        TIMESTAMP NOT NULL DEFAULT NOW(),
  time_activated      TIMESTAMP,

  UNIQUE (org_id, ft_model_id)
);
```

### Flujo de activación

```
1. Fine-tuning job completa (status = "completed" en Anthropic API)
2. upload_finetune.py registra el modelo en ovd_fine_tuned_models (status = "active")
3. Se asigna automáticamente en ovd_agent_configs para el agente "implementacion"
   de esa org (o del proyecto específico si hay project_id)
4. El dashboard muestra: "Modelo activo: haiku-empresa-a-v2 (entrenado en 150 ciclos)"
5. El siguiente ciclo ya usa el modelo fine-tuneado
```

### Niveles de optimización habilitados

| Criterio | Mecanismo | Resultado |
|----------|-----------|-----------|
| Por empresa | `org_id` en `ovd_fine_tuned_models` | Modelo que conoce las convenciones de la empresa |
| Por proyecto | `project_id` en `ovd_fine_tuned_models` | Modelo especializado en un sistema específico |
| Por stack | `stack` en el perfil + routing GAP-003 | Modelo seleccionado según el lenguaje/framework |
| Progresivo | Nuevas versiones del modelo con cada batch | Calidad mejora con el uso real de la plataforma |

### Endpoints requeridos

```
GET  /ovd/models                        — listar modelos registrados de la org
GET  /ovd/models/active                 — modelo activo por agente
POST /ovd/models/:modelId/activate      — activar un modelo fine-tuneado
POST /ovd/models/:modelId/deprecate     — desactivar un modelo
GET  /ovd/models/training-status        — estado de jobs de fine-tuning en curso
```

### Relación con otros gaps

- **GAP-003** (config de modelos): el registry auto-actualiza `ovd_agent_configs`
  cuando un modelo fine-tuneado se activa
- **GAP-011** (project profile): el `stack` del perfil se guarda en el registro
  para facilitar el routing a modelos especializados por stack
- **Pipeline Semana 10**: `upload_finetune.py` registra el modelo al completar el job

### Impacto si NO se implementa
El pipeline de fine-tuning existe pero los modelos generados se pierden — no hay
forma de saber qué modelo entrenado corresponde a qué cliente, ni de asignarlo
automáticamente. La plataforma no aprende del uso real.

---

## GAP-013 — Configuration Layer: UI + herencia org → proyecto → agente + fine-tuning open source
**Estado:** ✅ Implementado (GAP-013a + GAP-013b)
**Impacto:** Crítico (cierra el ciclo de aprendizaje continuo para cualquier modelo)
**Complejidad:** Alta
**Archivos a crear/modificar:**
- `packages/opencode/src/ovd/agent-config.ts` — tabla config por org/proyecto/agente
- `packages/opencode/src/server/routes/ovd.ts` — endpoints CRUD con herencia
- `packages/opencode/src/server/routes/dashboard.ts` — panel UI de configuración
- `src/engine/model_router.py` — resuelve modelo en runtime según config + herencia
- `src/engine/graph.py` — usa model_router por agente
- `src/finetune/upload_finetune_oss.py` — pipeline fine-tuning para modelos open source

---

### GAP-013a — Configuration Layer con herencia org → proyecto → agente

#### Descripción

Todo lo que afecta el comportamiento de un agente debe ser:
- **Configurable** desde la interfaz gráfica (no editando código)
- **Almacenado en DB** (trazable, con historial)
- **Jerarquizado** por tres niveles que se heredan y sobreescriben:

```
Nivel 1: Org (cliente)          ← defaults globales del cliente
    └── Nivel 2: Proyecto       ← sobreescribe para un sistema específico
          └── Nivel 3: Agente   ← sobreescribe para un agente específico
```

**Regla de herencia**: el nivel inferior sobreescribe al superior campo por campo.
Si un campo no está definido en el nivel inferior, se hereda del nivel superior.

```
Ejemplo:
  Org:      { language: "python", db_engine: "mysql", qa_tools: "pytest" }
  Proyecto: { db_engine: "postgresql" }            ← sobreescribe db_engine
  Agente:   { constraints: "usar stored procedures" } ← agrega restricción

  Resultado efectivo para el agente:
  { language: "python", db_engine: "postgresql", qa_tools: "pytest",
    constraints: "usar stored procedures" }
```

#### Tabla de base de datos

```sql
CREATE TABLE ovd_agent_configs (
  id              TEXT PRIMARY KEY,
  org_id          TEXT NOT NULL,
  project_id      TEXT,            -- NULL = aplica a toda la org
  agent_role      TEXT,            -- NULL = aplica a todos los agentes del nivel
                                   -- frontend | backend | database | devops | qa | security

  -- Modelo LLM para este nivel/agente
  provider        TEXT,            -- ollama | claude | openai | custom
  model           TEXT,            -- qwen2.5-coder:7b | claude-sonnet-4-6 | kimi-k2 | etc.
  base_url        TEXT,            -- para ollama y custom
  api_key_env     TEXT,            -- nombre de la var de entorno con la API key

  -- Instrucciones adicionales (se acumulan por herencia)
  extra_instructions TEXT,         -- instrucciones adicionales para el agente en este nivel
  constraints     TEXT,            -- restricciones adicionales
  code_style      TEXT,            -- convenciones de codigo

  -- Control
  active          BOOLEAN NOT NULL DEFAULT true,
  time_created    TIMESTAMP NOT NULL DEFAULT NOW(),
  time_updated    TIMESTAMP NOT NULL DEFAULT NOW(),

  UNIQUE (org_id, project_id, agent_role)
);
```

#### Resolución de herencia en el Engine

```python
# model_router.py
async def resolve(agent_role: str, org_id: str, project_id: str) -> ResolvedConfig:
    """
    Resuelve la config efectiva para un agente aplicando herencia:
    org defaults → project overrides → agent overrides
    """
    configs = await fetch_configs(org_id, project_id, agent_role)

    effective = {}
    for level in ["org", "project", "agent"]:   # orden de herencia
        cfg = configs.get(level, {})
        effective = {**effective, **{k: v for k, v in cfg.items() if v is not None}}

    return ResolvedConfig(**effective)
```

#### Endpoints requeridos

```
GET  /ovd/config                            — config efectiva de la org (todos los niveles)
PUT  /ovd/config/org                        — defaults de la org
PUT  /ovd/config/project/:projectId         — overrides del proyecto
PUT  /ovd/config/project/:projectId/agent/:role  — overrides del agente específico
GET  /ovd/config/project/:projectId/resolved     — preview config efectiva por agente
DELETE /ovd/config/project/:projectId/agent/:role — eliminar overrides del agente
```

#### Panel en Dashboard (UI)

Sección nueva en `/dashboard` con:
- Tabla de configuración por agente (editable inline)
- Indicador visual de qué nivel define cada campo (org / proyecto / agente)
- Preview del prompt efectivo que recibirá el agente con la config actual
- Botón "Resetear a defaults de la org"

---

### GAP-013b — Pipeline fine-tuning para modelos open source

#### Descripción

El pipeline actual (`upload_finetune.py`) solo soporta Anthropic Fine-tuning API.
Para poder entrenar modelos open source (Qwen, Kimi, DeepSeek, Llama) con los
ciclos acumulados, se necesita un pipeline paralelo que use herramientas OSS.

```
ovd_cycles.jsonl  (mismo dataset que hoy)
        ↓
  ┌─────────────────────────────┐    ┌─────────────────────────────┐
  │  Pipeline Anthropic (hoy)   │    │  Pipeline OSS (GAP-013b)    │
  │  upload_finetune.py         │    │  upload_finetune_oss.py      │
  │  → Anthropic API            │    │  → Unsloth / LlamaFactory   │
  │  → ftjob-xxx                │    │  → LoRA adapter .gguf        │
  │  → haiku fine-tuned         │    │  → Ollama local              │
  └─────────────────────────────┘    └─────────────────────────────┘
                    ↓                              ↓
              Model Registry (GAP-012) ←──────────┘
              ovd_fine_tuned_models
                    ↓
              Agent Config (GAP-013a)
              modelo asignado al agente
```

#### Flujo completo de aprendizaje continuo

```
1. Empresa usa la plataforma → ciclos reales en ovd_cycle_logs
2. export_cycles.py → ovd_cycles.jsonl  (datos de entrenamiento)
3. validate_dataset.py → verifica calidad del dataset
4. upload_finetune_oss.py → entrena LoRA sobre Qwen2.5-Coder base
5. Modelo registrado en ovd_fine_tuned_models (provider: ollama)
6. Se asigna automáticamente en ovd_agent_configs para esa org
7. Próximos ciclos usan el modelo especializado en el stack del cliente
8. Más ciclos → siguiente versión → calidad mejora progresivamente
```

El **mismo dataset JSONL** puede alimentar:
- Anthropic API (fine-tuning Haiku) — en la nube, sin GPU propia
- Unsloth + Qwen/DeepSeek — en servidor con GPU, LoRA eficiente
- LlamaFactory + Kimi/Mistral — alternativa con más modelos soportados
- A futuro: pre-entrenamiento de "OVD-Coder-7B" propio sobre base open source

#### Herramientas OSS

| Herramienta | Para qué | Modelos compatibles |
|-------------|----------|---------------------|
| Unsloth | Fine-tuning eficiente (LoRA/QLoRA) | Qwen, Llama, Mistral, DeepSeek |
| LlamaFactory | Fine-tuning con UI web | Qwen, Kimi, Llama, Phi, Gemma |
| Ollama | Servir modelos fine-tuneados localmente | .gguf de cualquier modelo |
| PEFT | LoRA adapters (PyTorch) | cualquier HuggingFace model |

#### Archivo a crear: `src/finetune/upload_finetune_oss.py`

```python
# Script equivalente a upload_finetune.py pero para modelos OSS
# python upload_finetune_oss.py --input data/ovd_cycles.jsonl \
#                                --base-model qwen2.5-coder-7b \
#                                --tool unsloth \
#                                --output models/ovd-qwen-v1
```

#### Metadatos de entrenamiento enriquecidos

Cada ciclo en `ovd_cycle_logs` ya tiene:
- `feature_request` → input del modelo
- `fr_analysis` + `sdd` → razonamiento intermedio (chain of thought)
- `agent_results` → output de implementación
- `qa_result.score` → señal de calidad para DPO/RLHF
- `complexity` + `fr_type` → metadatos de filtrado
- `project_id` → permite datasets por proyecto/stack

El Project Profile (GAP-011) enriquece cada ejemplo con el contexto del stack,
permitiendo modelos especializados por tecnología sin mezclar datos de distintos stacks.

#### Relación con GAP-012

GAP-013b extiende GAP-012 agregando `provider: "ollama"` al Model Registry.
El mismo registro unifica modelos Anthropic fine-tuned y modelos OSS locales.

---

## Tabla de estado

| Gap | Descripción | Impacto | Complejidad | Estado |
|-----|-------------|---------|-------------|--------|
| GAP-001 | `security_audit` node faltante | Alto | Media | ✅ Implementado |
| GAP-002 | `Send()` fan-out nativo LangGraph | Medio | Media | ✅ Implementado |
| GAP-003 | Config de modelos por agente desde la plataforma | Alto | Alta | ✅ Implementado |
| GAP-004 | `constraints_version` + Uncertainty Register | Alto | Media | ✅ Implementado |
| GAP-005 | Retry loops QA/Security (máx. 3) | Medio | Baja | ✅ Implementado |
| GAP-006 | RAG seed con conocimiento del proyecto | Alto | Alta | ✅ Implementado |
| GAP-007 | 4 artefactos SDD separados | Bajo | Baja | ✅ Implementado |
| GAP-008 | Templates externos de prompts | Bajo | Baja | ✅ Implementado |
| GAP-009 | Research Agent | Bajo | Alta | ✅ Implementado |
| GAP-010 | LangSmith tracing | Bajo | Baja | ✅ Implementado |
| GAP-011 | Project Profile: stack configurable por proyecto | Crítico | Alta | ✅ Implementado |
| GAP-012 | Model Registry: ciclo de aprendizaje continuo | Crítico | Alta | ✅ Implementado |
| GAP-013a | Config Layer UI: herencia org → proyecto → agente | Crítico | Alta | ✅ Implementado |
| GAP-013b | Pipeline fine-tuning modelos open source (Qwen/Kimi) | Crítico | Alta | ✅ Implementado |

---

## Orden de implementación sugerido (revisado)

**Batch 0 — Fundación universal (GAP-011)** ✅ Completado
Project Profile con stack configurable por proyecto e inyección en prompts.

**Batch A — Configuration Layer (GAP-003, GAP-012, GAP-013a, GAP-013b)** ✅ Completado
Herencia org → proyecto → agente + UI en dashboard + Model Registry + pipeline OSS.

**Batch B — graph.py + seguridad (GAP-001, GAP-004, GAP-005)** ✅ Completado
Nodo security_audit + constraints_version + retry loops.

**Batch C — Modelos y conocimiento (GAP-003, GAP-006, GAP-008)** ✅ Completado
Config de modelos desde la plataforma + RAG seed por proyecto + templates.

**Batch D — Model Registry + Fine-tuning OSS (GAP-012, GAP-013b)**
Registro de modelos fine-tuneados + pipeline Unsloth/LlamaFactory para Qwen/Kimi.
Cierra el ciclo de aprendizaje continuo.
Estimación: 2 sesiones.

**Batch E — Arquitectura LangGraph y observabilidad (GAP-002, GAP-007, GAP-009, GAP-010)**
Send() fan-out + 4 artefactos SDD + Research Agent + LangSmith.
Mejoras incrementales, menor urgencia operativa.
Estimación: 2 sesiones.
