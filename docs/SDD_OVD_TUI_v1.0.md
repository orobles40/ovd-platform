# SDD — Oficina Virtual de Desarrollo + Terminal Agent
## Spec-Driven Development Document v1.0

**Proyecto:** OVD-TUI — Terminal Agent para la Oficina Virtual de Desarrollo
**Lider tecnico:** Omar — Arquitecto de Soluciones
**Organizacion:** Omar Robles
**Version:** 1.5 — Marzo 2026
**Clasificacion:** CONFIDENCIAL — Uso interno

---

## Indice

1. [Vision general](#1-vision-general)
2. [Estrategia de fork y licencia](#2-estrategia-de-fork-y-licencia)
3. [Requirements](#3-requirements)
4. [Design](#4-design)
5. [Constraints](#5-constraints)
6. [Arquitectura detallada](#6-arquitectura-detallada)
7. [Tasks — Breakdown por componente](#7-tasks)
8. [Fases de implementacion](#8-fases-de-implementacion)
9. [Criterios de aceptacion globales](#9-criterios-de-aceptacion-globales)
10. [Riesgos y mitigaciones](#10-riesgos-y-mitigaciones)
11. [Glosario](#11-glosario)

> **Changelog v1.1:** se agrega seccion completa de Fine-tuning en requirements, design, constraints, arquitectura, tasks, fases y riesgos.
> **Changelog v1.2:** se agrega seccion 2 — Estrategia de fork y licencia Apache 2.0.

---

## 1. Vision general

### 1.1 Problema que resuelve

La Oficina Virtual de Desarrollo (OVD) existe como un sistema multi-agente LangGraph funcional, con demos validadas y metodologia SDD probada. Sin embargo, hoy solo es accesible via scripts Python directos, sin interfaz para el equipo de desarrollo, sin multi-tenancy y sin capacidad de escalar a otros proyectos o clientes.

El objetivo de este documento es especificar el sistema completo que transforma la OVD de un prototipo funcional a un producto utilizable por un equipo, desplegable en cloud privado y con camino claro hacia SaaS empresarial.

### 1.2 Que se construye

**El producto es un fork directo de OpenCode** (`anomalyco/opencode`, Apache 2.0). Se extiende el codigo fuente existente desde adentro — no se construye una capa externa ni se reescribe lo que ya funciona.

OpenCode ya provee, listo para usar:
- TUI completa en SolidJS corriendo en terminal via `opentui`
- Servidor HTTP interno en Hono (TypeScript/Bun)
- Sistema de sesiones, herramientas (bash, edit, read, lsp, grep, glob...) y providers
- Soporte nativo para Anthropic, OpenAI, Google, Ollama, OpenRouter y mas
- Arquitectura cliente/servidor que permite clientes remotos
- Sistema de agentes configurable con permisos granulares

Lo que se construye encima de ese fork:

```
EXTENSION 1 — OVD Integration (TypeScript/Bun, dentro del fork)
  Nuevo provider/agent-type en packages/opencode que conecta al OVD Engine.
  El OVD Engine (LangGraph) se invoca como un "agente especializado" de OpenCode.
  La sesion de OpenCode orquesta los agentes LangGraph, mostrando el progreso en el TUI existente.

EXTENSION 2 — Multi-tenancy (TypeScript/Bun, dentro del fork)
  Capa de organizaciones y proyectos sobre el servidor Hono existente.
  Row-Level Security en la DB local (SQLite → PostgreSQL para produccion).
  Auth JWT sobre el servidor existente.

EXTENSION 3 — TUI ampliada (SolidJS, dentro del fork packages/app)
  Pantallas nuevas sobre el TUI existente: selector de proyecto, modal de aprobacion OVD,
  pantalla de fine-tuning, dashboard de telemetria.
  Reutiliza todos los componentes, temas y keybindings de OpenCode.

EXTENSION 4 — OVD Engine (Python / LangGraph) — YA EXISTE, servicio separado
  El grafo de agentes, el RAG, los sandboxes Docker.
  Se expone via HTTP para que el fork de OpenCode lo consuma.
  Se extiende para soportar multi-proyecto. No se reescribe.

EXTENSION 5 — Fine-tuning Pipeline (Python / unsloth o axolotl) — servicio separado
  Recolecta training samples de sesiones aprobadas.
  Jobs de fine-tuning sobre modelos locales (Ollama).
  Model registry por proyecto.

EXTENSION 6 — Telemetria (OpenTelemetry) — servicio separado
  Instrumentacion del fork y del OVD Engine.
  Almacenamiento local en PostgreSQL, exportacion opcional a Grafana.
```

### 1.3 Alcance del documento

Este SDD cubre las Extensiones 1, 2, 3, 5 y 6 sobre el fork de OpenCode. La Extension 4 (OVD Engine) esta documentada en `SDD_VDO_v19.docx` y se referencia pero no se redisena aqui, salvo los cambios necesarios para multi-tenancy y la recoleccion de training samples.

### 1.4 Usuarios objetivo

| Usuario | Como usa el sistema | Prioridad |
|---------|---------------------|-----------|
| Developer del equipo (Omar, equipo Omar Robles) | TUI diario para enviar FRs y aprobar planes | Fase 1 |
| Tech Lead / Arquitecto | Aprobacion de specs y escalaciones via TUI | Fase 1 |
| Otro proyecto cliente | Onboarding de su stack en OVD, uso via TUI | Fase 2 |
| Admin de la plataforma | Gestion de organizaciones y proyectos | Fase 3 |
| Cliente SaaS futuro | Web UI o TUI, billing, self-service | Fase 4+ |

---

## 2. Estrategia de fork y licencia

### 2.1 Base legal: Apache 2.0

OpenCode esta publicado bajo **Apache License 2.0** por Anomaly Co. Esta es una de las licencias mas permisivas del ecosistema open source y otorga libertad casi total para construir sobre el proyecto. A continuacion se detalla exactamente que implica esto para la OVD-TUI.

### 2.2 Lo que la licencia permite (libertades garantizadas)

| Libertad | Aplicacion en este proyecto |
|----------|----------------------------|
| **Modificar el codigo** | Fork completo del repositorio `anomalyco/opencode`. Se puede cambiar la logica de agentes, herramientas, providers y TUI sin restriccion |
| **Uso comercial** | La OVD-TUI puede usarse en proyectos de clientes (Alemana, etc.) y eventualmente como SaaS de pago sin pagar royalties |
| **Redistribucion** | La version modificada puede distribuirse libremente al equipo o a clientes, siempre que se mantengan los avisos de copyright originales |
| **Integracion de modelos propios** | No hay obligacion de usar OpenCode Zen ni ningun servicio de pago de Anomaly. La OVD usa sus propios providers (Ollama, Claude API, RunPod) |
| **Sublicenciamiento** | El codigo propio nuevo (API Layer, fine-tuning, TUI extendido) puede publicarse bajo la licencia que se prefiera, siempre que el codigo derivado de OpenCode mantenga Apache 2.0 |

### 2.3 Obligaciones y limitaciones

| Obligacion | Accion requerida |
|------------|-----------------|
| **Mantener avisos de copyright** | Conservar el header `Copyright (c) Anomaly Co.` en todos los archivos copiados o derivados del codigo original de OpenCode |
| **Incluir la licencia** | El repositorio de OVD-TUI debe incluir el archivo `LICENSE` original de OpenCode en la carpeta `third_party/opencode/` |
| **NOTICE file** | Si OpenCode incluye un archivo `NOTICE`, debe preservarse en la distribucion |
| **Documentar cambios** | Los archivos modificados deben indicar que fueron alterados respecto al original (convencion: comentario en el header del archivo) |

> **Importante:** Apache 2.0 incluye una clausula de **patent grant**: los contribuidores de OpenCode otorgan licencia de patentes sobre sus contribuciones. Esto protege a la OVD-TUI de demandas de patentes relacionadas con el codigo de OpenCode.

### 2.4 Marca registrada — accion obligatoria antes del lanzamiento publico

El codigo es libre pero **el nombre "OpenCode" y sus logotipos son marca de Anomaly Co.** Si la OVD-TUI se distribuye al publico o a clientes externos, usar el nombre "OpenCode" en el producto podria constituir infraccion de marca.

**Nombre propuesto para el producto:** `OVD` o `Oficina Virtual` o un nombre comercial nuevo a definir por el arquitecto antes de Fase 3.

Acciones obligatorias antes de distribucion publica:
1. Definir nombre comercial del producto (decision del arquitecto)
2. Remover o reemplazar todos los logotipos y referencias a "OpenCode" en la TUI y documentacion
3. Actualizar el `README.md` del fork con la clausula de disassociation: *"Este proyecto es un fork independiente basado en OpenCode (Apache 2.0). No esta afiliado ni respaldado por Anomaly Co."*
4. Mantener credito a los autores originales en el `CREDITS.md`

### 2.5 Estrategia tecnica del fork

OpenCode esta escrito en **TypeScript/Bun**. El TUI usa **SolidJS** corriendo en terminal via `opentui`. El servidor interno es **Hono**. Todo corre sobre **Bun** como runtime. El stack de OpenCode se mantiene y extiende — no se reescribe.

**Estructura de ramas:**

```
REPOSITORIO: ovd-platform (privado, Omar Robles)
|
|-- Rama: main          ← extensiones propias (OVD integration, multi-tenancy, fine-tuning, telemetria)
|-- Rama: upstream/dev  ← tracking del branch dev de anomalyco/opencode
|
|  Sincronizacion mensual:
|    git fetch upstream
|    git merge upstream/dev --no-ff  (trae mejoras, fixes, nuevos providers)
|    resolver conflictos en archivos modificados
|    conservar headers de copyright en archivos del upstream
```

**Que se toma de OpenCode y que se construye propio:**

| Componente | Origen | Accion |
|-----------|--------|--------|
| `packages/opencode/src/` — core engine | OpenCode | Extender: agregar `src/ovd/`, `src/tenant/`, hooks de fine-tuning |
| `packages/app/` — TUI SolidJS | OpenCode | Extender: agregar nuevas pantallas y componentes OVD |
| `packages/opencode/src/server/` — Hono server | OpenCode | Extender: agregar rutas de multi-tenancy, OVD, telemetria |
| `packages/opencode/src/provider/` — providers IA | OpenCode | Usar tal cual — ya soporta Anthropic, Ollama, OpenRouter, etc. |
| `packages/opencode/src/tool/` — herramientas (bash, edit, lsp...) | OpenCode | Usar tal cual — disponibles para los agentes OVD |
| `packages/opencode/src/agent/` — sistema de agentes | OpenCode | Extender: registrar agentes OVD como agentes nativos del sistema |
| `packages/opencode/src/session/` — sesiones | OpenCode | Extender: conectar sesion de OpenCode con thread LangGraph |
| OVD Engine (LangGraph) | Propio | Servicio Python separado, expuesto via HTTP |
| Fine-tuning pipeline | Propio | Servicio Python separado |
| Telemetria | Propio | Servicio OpenTelemetry, alimentado desde el fork y el OVD Engine |
| Multi-tenancy (org/project/user) | Propio | Nuevo modulo dentro del fork: `packages/opencode/src/tenant/` |

**Stack tecnologico resultante:**

```
Fork OpenCode  →  TypeScript / Bun / SolidJS / Hono / Effect.ts / SQLite→PostgreSQL
OVD Engine     →  Python / LangGraph / FastAPI / pgvector
Fine-tuning    →  Python / unsloth o axolotl
Telemetria     →  OpenTelemetry collector + PostgreSQL
Infra          →  Docker Compose → Kubernetes (Fase 3)
```

### 2.6 Checklist de compliance antes de cada release

- [ ] Archivos copyright de OpenCode presentes en `third_party/opencode/LICENSE`
- [ ] Headers de copyright conservados en archivos derivados
- [ ] Nombre "OpenCode" ausente de la interfaz de usuario visible al cliente
- [ ] `CREDITS.md` actualizado con version de OpenCode base usada
- [ ] `README.md` incluye clausula de disassociation de Anomaly Co.
- [ ] Clausula de patent grant verificada para cualquier dependencia nueva de terceros

---

## 3. Requirements

### 2.1 Funcionales — TUI Client

| ID | Requisito | Prioridad |
|----|-----------|-----------|
| REQ-TUI-001 | El usuario puede autenticarse con usuario y password desde el TUI | Alta |
| REQ-TUI-002 | El usuario puede seleccionar organizacion y proyecto activo | Alta |
| REQ-TUI-003 | El usuario puede escribir un Feature Request en lenguaje natural y enviarlo al OVD | Alta |
| REQ-TUI-004 | El TUI muestra en tiempo real el progreso de cada nodo del grafo LangGraph via streaming | Alta |
| REQ-TUI-005 | El TUI presenta los specs generados (requirements.md, design.md, constraints.md, tasks.md) para revision antes de continuar | Alta |
| REQ-TUI-006 | El usuario puede aprobar o rechazar el plan desde el TUI (human_approval) | Alta |
| REQ-TUI-007 | El TUI presenta las escalaciones del agente Legacy y permite resolverlas o escalar al arquitecto | Alta |
| REQ-TUI-008 | El TUI muestra los entregables finales con syntax highlighting y diff coloreado | Alta |
| REQ-TUI-009 | El TUI muestra los reportes de QA y Security con sus hallazgos | Alta |
| REQ-TUI-010 | El usuario puede ver el historial de sesiones del proyecto activo | Media |
| REQ-TUI-011 | El usuario puede retomar una sesion interrumpida | Media |
| REQ-TUI-012 | El TUI soporta modo offline para consultar historial sin conexion al servidor | Baja |
| REQ-TUI-013 | El binario es multiplataforma: macOS (Apple Silicon + Intel), Linux x86_64, Windows x64 | Alta |
| REQ-TUI-014 | Instalacion via script curl o package manager (brew, scoop, cargo) | Media |

### 2.2 Funcionales — API Layer

| ID | Requisito | Prioridad |
|----|-----------|-----------|
| REQ-API-001 | La API expone autenticacion JWT con refresh tokens | Alta |
| REQ-API-002 | La API implementa multi-tenancy por organizacion y proyecto con aislamiento completo de datos | Alta |
| REQ-API-003 | La API expone un endpoint para iniciar una sesion de feature request | Alta |
| REQ-API-004 | La API transmite eventos del grafo LangGraph via Server-Sent Events (SSE) | Alta |
| REQ-API-005 | La API expone endpoint de aprobacion humana que desbloquea el interrupt de LangGraph | Alta |
| REQ-API-006 | La API expone endpoint de resolucion de escalaciones | Alta |
| REQ-API-007 | La API expone CRUD de organizaciones y proyectos | Alta |
| REQ-API-008 | La API expone el historial de sesiones y mensajes de un proyecto | Media |
| REQ-API-009 | La API soporta configuracion de RAG por proyecto (seed de knowledge base) | Media |
| REQ-API-010 | La API expone health check y metricas basicas | Alta |
| REQ-API-011 | Todos los endpoints requieren autenticacion. Sin excepciones. | Alta |
| REQ-API-012 | La API tiene rate limiting por organizacion | Media |
| REQ-API-013 | La API expone endpoints para gestionar el dataset de fine-tuning por proyecto | Media |
| REQ-API-014 | La API expone endpoints para lanzar, monitorear y cancelar jobs de fine-tuning | Media |
| REQ-API-015 | La API expone un registro de modelos fine-tuned por proyecto con estado y metricas | Media |
| REQ-API-016 | La API permite activar un modelo fine-tuned como modelo preferido para un agente especifico | Media |
| REQ-API-017 | La API expone endpoint para que el curador humano apruebe o rechace un dataset antes del fine-tuning | Alta |

### 2.4 Funcionales — Fine-tuning Pipeline

| ID | Requisito | Prioridad |
|----|-----------|-----------|
| REQ-FT-001 | Cada sesion completada y aprobada genera automaticamente training samples candidatos | Alta |
| REQ-FT-002 | Los training samples incluyen: FR original, specs generados, codigo producido, resultado QA y Security | Alta |
| REQ-FT-003 | Los training samples con datos sensibles de pacientes quedan marcados y excluidos del training set por defecto | Alta |
| REQ-FT-004 | Un curador humano puede revisar, aprobar o descartar cada training sample desde el TUI o via API | Alta |
| REQ-FT-005 | El sistema soporta fine-tuning de modelos Ollama locales usando unsloth o axolotl como backend | Alta |
| REQ-FT-006 | Los jobs de fine-tuning se ejecutan en GPU local (Mac M-series) o en RunPod bajo demanda | Alta |
| REQ-FT-007 | Un modelo fine-tuned nuevo pasa por evaluacion automatica antes de poder activarse | Alta |
| REQ-FT-008 | El modelo registry mantiene historial de versiones por proyecto con metricas de evaluacion | Media |
| REQ-FT-009 | El sistema permite routing A/B: porcentaje de sesiones al modelo base vs al fine-tuned para comparacion | Media |
| REQ-FT-010 | El TUI muestra el estado del dataset, jobs activos y modelos disponibles en una pantalla de Fine-tuning | Media |
| REQ-FT-011 | El fine-tuning es estrictamente por proyecto: el modelo de un proyecto nunca entrena con datos de otro | Alta |
| REQ-FT-012 | El sistema emite alertas cuando el dataset acumula suficientes samples para un nuevo job (umbral configurable) | Baja |

### 2.5 Funcionales — Extensibilidad (Skills, MCP, Agentes custom)

| ID | Requisito | Prioridad |
|----|-----------|-----------|
| REQ-EXT-001 | El sistema soporta Skills como archivos markdown en `.opencode/command/` invocables con `/nombre` dentro de cualquier sesion | Alta |
| REQ-EXT-002 | Los skills pueden definirse a nivel global y a nivel de proyecto, con los de proyecto tomando precedencia | Alta |
| REQ-EXT-003 | El sistema soporta servidores MCP externos configurables por proyecto en `opencode.jsonc` | Alta |
| REQ-EXT-004 | El sistema incluye un MCP server nativo para Oracle multi-sede que el agente puede invocar para ejecutar queries | Alta |
| REQ-EXT-005 | El MCP server de Oracle enruta automaticamente al pool correcto segun la sede (CAS → PSOL7/ROBLE, CAT/CAV → PSOL8) | Alta |
| REQ-EXT-006 | El MCP server de Oracle opera exclusivamente sobre entornos de desarrollo — nunca sobre produccion | Alta |
| REQ-EXT-007 | El sistema permite definir agentes custom por proyecto con modelo propio, temperatura, prompt y permisos de herramientas especificos | Alta |
| REQ-EXT-008 | Cada agente puede configurarse para usar un LLM diferente: Claude API para tareas complejas, Ollama local para tareas acotadas | Alta |
| REQ-EXT-009 | El sistema soporta MCP servers adicionales definidos por el usuario: NATS, Jira, Confluence, APIs internas | Media |
| REQ-EXT-010 | Los MCP servers se registran en `opencode.jsonc` por proyecto y estan disponibles como tools del agente en esa sesion | Media |
| REQ-EXT-011 | El TUI muestra las tools MCP disponibles en la sesion activa y su estado (conectado / desconectado) | Media |
| REQ-EXT-012 | Un agente con modelo fine-tuned activo puede combinarse con skills y MCP servers sin restriccion | Media |

### 2.3 No funcionales

| ID | Requisito | Metrica |
|----|-----------|---------|
| REQ-NF-001 | Latencia de arranque del TUI | < 200ms en cold start |
| REQ-NF-002 | Latencia primer token en streaming | < 2s desde envio del FR |
| REQ-NF-003 | Aislamiento de datos entre organizaciones | 100% — verificado con tests |
| REQ-NF-004 | Disponibilidad del API en cloud privado | 99.5% uptime |
| REQ-NF-005 | Logs de auditoria de todas las acciones del usuario | Retencion 90 dias |
| REQ-NF-006 | Datos de pacientes nunca salen del servidor propio | Verificado por arquitecto |
| REQ-NF-007 | Un job de fine-tuning no degrada la disponibilidad del API Layer | CPU/GPU en proceso separado |
| REQ-NF-008 | Los modelos fine-tuned se almacenan en el servidor propio, nunca en servicios externos | Verificado por arquitecto |
| REQ-NF-009 | Mejora de calidad verificable: el modelo fine-tuned supera al base en benchmark del stack del proyecto | Medido antes de activacion |

---

## 3. Design

### 3.1 Modelo de datos multi-tenant

El aislamiento es el principio de diseno numero uno. Cada tabla de negocio lleva `org_id` y `project_id`. Se usa Row-Level Security (RLS) de PostgreSQL como segunda linea de defensa.

```sql
-- Jerarquia de tenancy
organizations
  id         UUID PRIMARY KEY
  slug       TEXT UNIQUE        -- ej: "omar", "alemana"
  name       TEXT
  created_at TIMESTAMPTZ

projects
  id          UUID PRIMARY KEY
  org_id      UUID REFERENCES organizations(id)
  slug        TEXT               -- ej: "profesi-honorari", "hhmm-pipeline"
  name        TEXT
  stack       JSONB              -- descripcion del stack tecnologico
  constraints TEXT               -- constraints.md especifico del proyecto
  created_at  TIMESTAMPTZ
  UNIQUE(org_id, slug)

users
  id         UUID PRIMARY KEY
  org_id     UUID REFERENCES organizations(id)
  email      TEXT UNIQUE
  role       TEXT               -- "developer" | "tech_lead" | "admin"
  created_at TIMESTAMPTZ

sessions
  id          UUID PRIMARY KEY
  project_id  UUID REFERENCES projects(id)
  org_id      UUID REFERENCES organizations(id)
  created_by  UUID REFERENCES users(id)
  status      TEXT               -- "running" | "pending_approval" | "escalated" | "completed" | "failed"
  thread_id   TEXT               -- ID del checkpointer de LangGraph
  feature_req TEXT               -- el FR original en lenguaje natural
  created_at  TIMESTAMPTZ
  updated_at  TIMESTAMPTZ

session_events
  id          UUID PRIMARY KEY
  session_id  UUID REFERENCES sessions(id)
  org_id      UUID REFERENCES organizations(id)
  type        TEXT               -- "node_start" | "node_end" | "approval_req" | "escalation" | "completed"
  node        TEXT               -- nombre del nodo LangGraph
  payload     JSONB
  created_at  TIMESTAMPTZ

artifacts
  id          UUID PRIMARY KEY
  session_id  UUID REFERENCES sessions(id)
  org_id      UUID REFERENCES organizations(id)
  type        TEXT               -- "requirements" | "design" | "constraints" | "tasks" | "code" | "qa_report" | "security_report"
  filename    TEXT
  content     TEXT
  created_at  TIMESTAMPTZ

-- FINE-TUNING: training samples generados de sesiones aprobadas
training_samples
  id              UUID PRIMARY KEY
  project_id      UUID REFERENCES projects(id)
  org_id          UUID REFERENCES organizations(id)
  session_id      UUID REFERENCES sessions(id)
  agent           TEXT               -- agente que genero el output: "legacy" | "backend" | "qa" | etc.
  input           TEXT               -- prompt / FR / tarea que recibio el agente
  output          TEXT               -- respuesta generada por el agente
  quality_score   FLOAT              -- score automatico basado en resultado QA/Security
  has_sensitive   BOOLEAN DEFAULT false  -- true si contiene datos de pacientes
  curator_status  TEXT DEFAULT 'pending'  -- "pending" | "approved" | "rejected"
  curator_note    TEXT
  curated_by      UUID REFERENCES users(id)
  curated_at      TIMESTAMPTZ
  created_at      TIMESTAMPTZ

-- FINE-TUNING: jobs de entrenamiento
fine_tuning_jobs
  id              UUID PRIMARY KEY
  project_id      UUID REFERENCES projects(id)
  org_id          UUID REFERENCES organizations(id)
  base_model      TEXT               -- ej: "qwen3:8b", "codellama:13b"
  target_model    TEXT               -- nombre del modelo fine-tuned a producir
  status          TEXT               -- "queued" | "running" | "completed" | "failed" | "cancelled"
  sample_count    INTEGER            -- cantidad de samples usados
  backend         TEXT               -- "unsloth" | "axolotl"
  compute         TEXT               -- "local" | "runpod"
  runpod_job_id   TEXT
  started_at      TIMESTAMPTZ
  completed_at    TIMESTAMPTZ
  error_log       TEXT
  created_by      UUID REFERENCES users(id)
  created_at      TIMESTAMPTZ

-- FINE-TUNING: registro de modelos entrenados
model_registry
  id              UUID PRIMARY KEY
  project_id      UUID REFERENCES projects(id)
  org_id          UUID REFERENCES organizations(id)
  job_id          UUID REFERENCES fine_tuning_jobs(id)
  name            TEXT               -- ej: "ovd-alemana-legacy-v1"
  base_model      TEXT
  ollama_tag      TEXT               -- tag cargado en Ollama para servir el modelo
  status          TEXT               -- "evaluating" | "ready" | "active" | "retired"
  eval_score      FLOAT              -- score en benchmark del proyecto
  eval_details    JSONB              -- breakdown por categoria del benchmark
  is_active       BOOLEAN DEFAULT false
  activated_by    UUID REFERENCES users(id)
  activated_at    TIMESTAMPTZ
  created_at      TIMESTAMPTZ
```

### 3.2 Instrumentacion de sesiones para fine-tuning

Cada vez que un agente completa su tarea y el ciclo pasa QA y Security, el OVD Engine emite un evento `training_sample_candidate`. El API Layer lo captura y persiste en `training_samples` con estado `pending`.

```
Flujo automatico de recoleccion:

  agent_executor completa tarea
       |
       v
  qa_validation [APROBADO]
       |
       v
  security_audit [APROBADO o OBSERVATIONS]
       |
       v  evento interno: training_sample_candidate
  API Layer — recolector
       |
       |-- extrae input/output del agente desde session_events
       |-- detecta datos sensibles (regex + clasificador) → has_sensitive
       |-- calcula quality_score segun resultado QA/Security
       |-- inserta en training_samples con status = "pending"
       |
       v
  Curador humano (TUI o API) revisa → "approved" o "rejected"
```

**Estructura de un training sample:**

```json
{
  "agent": "legacy",
  "input": "Tarea LEGACY-2026-001: agregar validacion RUT en LiquidacionHonorariosForm.\nConstraints: Struts 1.3, iBATIS 2.x, interfaz Validatable congelada.\n...",
  "output": "// RutValidator.java\npublic class RutValidator {\n  public static boolean validate(String rut) {...}\n}\n// TestRutValidator.java\n...",
  "quality_score": 0.92,
  "has_sensitive": false
}
```

### 3.3 RAG multi-proyecto

En pgvector, cada proyecto tiene su propio namespace. El Research agent del OVD solo accede al namespace del proyecto activo.

```
pgvector collections por proyecto:
  {project_id}_oracle_constraints
  {project_id}_legacy_patterns
  {project_id}_integration_patterns
  {project_id}_security_rules
  {project_id}_decisions_history
  {project_id}_task_outputs
  {project_id}_tech_docs
```

### 3.4 Flujo de una sesion completa

```
Developer en TUI
  |
  | POST /api/v1/session
  | { project_id, feature_request }
  |
  v
API Layer crea Session en DB, asigna thread_id, lanza LangGraph en background
  |
  | SSE /api/v1/session/{id}/stream
  |
  v
TUI consume el stream y renderiza eventos en tiempo real:

  [evento: node_start]       → muestra "Coordinator analizando..."
  [evento: artifact]         → muestra requirements.md generado
  [evento: approval_required] → PAUSA. Muestra plan. Espera input del usuario.

  Developer lee el plan en TUI, aprueba o rechaza:
  POST /api/v1/session/{id}/approve   { decision: "approved" | "rejected", comment }

  [evento: node_start]       → muestra "Despachando agentes..."
  [evento: agent_progress]   → "Legacy agent: analizando LiquidacionHonorariosForm.java"
  [evento: escalation]       → PAUSA. Muestra el bloqueo. Espera resolucion.

  POST /api/v1/session/{id}/escalate  { resolution }

  [evento: agent_progress]   → agente continua
  [evento: qa_result]        → muestra reporte QA
  [evento: security_result]  → muestra reporte Security
  [evento: completed]        → muestra entregables con diffs
```

### 3.5 Puente LangGraph <-> HTTP (el componente mas critico)

LangGraph usa interrupts via `interrupt_before`. Para exponerlos como HTTP, se usa el `AsyncPostgresCheckpointer` de LangGraph con un patron de espera activa:

```python
# Patron de implementacion
class OVDRunner:
    async def run_session(self, session_id: str, feature_request: str):
        config = {"configurable": {"thread_id": session_id}}

        # Correr hasta el primer interrupt
        async for event in self.graph.astream(
            {"feature_request": feature_request},
            config=config,
            stream_mode="values",
            interrupt_before=["human_approval", "handle_escalation"]
        ):
            await self.publish_event(session_id, event)

    async def resume_session(self, session_id: str, human_input: dict):
        config = {"configurable": {"thread_id": session_id}}
        # LangGraph retoma desde el checkpointer
        async for event in self.graph.astream(
            human_input,
            config=config,
            stream_mode="values",
        ):
            await self.publish_event(session_id, event)

    async def publish_event(self, session_id: str, event: dict):
        # Guarda en session_events y notifica via SSE
        await db.insert_event(session_id, event)
        await sse_manager.broadcast(session_id, event)
```

### 3.6 Diseno del TUI (Rust / ratatui)

El TUI se divide en pantallas con navegacion por teclado:

```
PANTALLA: Login
  [input] Email
  [input] Password (masked)
  [boton] Conectar

PANTALLA: Selector de proyecto
  Organizacion: Omar Robles
  > PROFESI-HONORARI-J2E    [ultimo FR: hace 2 dias]
    HHMM-PIPELINE           [ultimo FR: hace 1 semana]
  [N] Nuevo proyecto

PANTALLA PRINCIPAL (layout de 3 paneles)
  ┌──────────────────┬─────────────────────────────┐
  │ SESIONES         │ SESION ACTIVA               │
  │                  │                             │
  │ > FR-2026-003    │ [progreso del grafo]        │
  │   FR-2026-002    │                             │
  │   FR-2026-001    │ Coordinator... [OK]         │
  │                  │ generate_specs... [OK]      │
  │                  │ human_approval... [PAUSADO] │
  │                  │                             │
  └──────────────────┴─────────────────────────────┘
  │ PROMPT                                         │
  │ > Describe el feature request...               │
  └────────────────────────────────────────────────┘

PANTALLA: Revision de plan (modal sobre layout principal)
  ┌─ PLAN GENERADO — Aprobacion requerida ────────┐
  │ [tab] requirements  [tab] design              │
  │ [tab] constraints   [tab] tasks               │
  │                                               │
  │ # Requirements                                │
  │ ...contenido del artefacto...                 │
  │                                               │
  │ [A] Aprobar   [R] Rechazar   [C] Comentar     │
  └───────────────────────────────────────────────┘

PANTALLA: Entregables (al completar)
  ┌─ ENTREGABLES — FR-2026-003 ───────────────────┐
  │ [tab] Codigo  [tab] QA  [tab] Security        │
  │                                               │
  │ RutValidator.java                    [NUEVO]  │
  │ + public class RutValidator {                 │
  │ +   public static boolean validate(...)       │
  │                                               │
  │ TestRutValidator.java                [NUEVO]  │
  │                                               │
  │ [S] Guardar todos   [C] Copiar al portapapeles│
  └───────────────────────────────────────────────┘
```

### 3.7 Diseno del pipeline de fine-tuning

El pipeline tiene cuatro etapas claramente separadas: **recoleccion → curacion → entrenamiento → activacion**.

```
ETAPA 1 — Recoleccion automatica
  OVD Engine (post-sesion aprobada)
       |
       v
  fine_tuning.collector.py
    - extrae pares input/output de session_events por agente
    - aplica detector de datos sensibles
    - calcula quality_score (QA pass + security pass + escalaciones)
    - inserta en training_samples con status = "pending"

ETAPA 2 — Curacion humana (human-in-the-loop obligatorio)
  TUI pantalla Fine-tuning → lista de samples pendientes
    - el curador lee input/output en el TUI
    - aprueba [A] o rechaza [R] con nota opcional
    - PUT /api/v1/training-sample/{id}/curate { status, note }
    - samples sin curacion NUNCA entran a un job de training

ETAPA 3 — Entrenamiento
  Admin lanza job desde TUI:
    - selecciona modelo base (ej: qwen3:8b)
    - selecciona samples aprobados del proyecto
    - configura backend (unsloth local | axolotl + RunPod)
    - POST /api/v1/project/{id}/finetune/job
    |
    v
  fine_tuning.trainer.py
    - exporta dataset en formato JSONL (instruccion / respuesta)
    - lanza proceso de fine-tuning en GPU local o RunPod
    - publica progreso via SSE → TUI muestra loss curve
    - al completar: guarda modelo en /models/{project_id}/{version}/
    - registra en model_registry con status = "evaluating"

ETAPA 4 — Evaluacion y activacion
  fine_tuning.evaluator.py
    - corre benchmark del proyecto (set de FRs historicos con respuesta esperada)
    - calcula eval_score y eval_details por categoria
    - actualiza model_registry status = "ready"
    |
    v
  Admin revisa metricas en TUI
    - compara eval_score vs modelo anterior
    - activa el modelo si supera umbral: POST /api/v1/model/{id}/activate
    - OVD Engine empieza a routear ese agente al modelo fine-tuned
    - routing A/B opcional: porcentaje configurable base vs fine-tuned
```

**Formato JSONL de entrenamiento (instruccion / respuesta):**

```jsonl
{"instruction": "Eres el Legacy agent del OVD. Stack: Struts 1.3, iBATIS 2.x, Spring 2.5, Oracle 12c. Tarea: LEGACY-2026-001 — agregar validacion RUT en LiquidacionHonorariosForm. Constraints: interfaz Validatable congelada. Genera el codigo.", "response": "// RutValidator.java\n..."}
{"instruction": "Eres el QA agent. Genera tests JUnit 4 para RutValidator con cobertura minima 60%.", "response": "// TestRutValidator.java\n..."}
```

**Estrategia de routing cuando hay modelo fine-tuned activo:**

```python
# En specialized.py del OVD Engine (extension)
def get_model_for_agent(agent_name: str, project_id: str) -> str:
    active = model_registry.get_active(project_id, agent_name)
    if active and active.eval_score >= ACTIVATION_THRESHOLD:
        if AB_ROUTING_ENABLED:
            return active.ollama_tag if random() < AB_RATIO else BASE_MODEL
        return active.ollama_tag
    return BASE_MODEL
```

### 3.8 Diseno de extensibilidad — Skills, MCP y Agentes custom

#### 3.8.1 Skills por proyecto

Los skills son archivos markdown que definen instrucciones especializadas invocables con `/nombre` en cualquier sesion. Se guardan en dos niveles:

```
~/.opencode/command/          ← skills globales (todos los proyectos)
.opencode/command/            ← skills del proyecto (toman precedencia)
  |-- consulta-oracle.md
  |-- fix-legacy.md
  |-- revision-seguridad.md
  |-- validar-nats.md
```

**Ejemplo de skill para Oracle multi-sede:**

```markdown
<!-- .opencode/command/consulta-oracle.md -->
# Consulta Oracle

Cuando el usuario pida ejecutar una consulta SQL:

1. Identificar la sede objetivo: CAS (Oracle 12c) | CAT | CAV (Oracle 19c)
2. Si la sede es CAS o ALL, verificar que el SQL no use features 19c:
   - NO: JSON nativo, SQL Macros, LISTAGG overflow, partitioning exclusivo 19c
3. Invocar la tool `mcp_oracle__query` con { sql, sede }
4. Si hay error ORA-, analizar el codigo y proponer correccion
5. Mostrar resultado con formato tabla
```

#### 3.8.2 MCP servers del proyecto

Los MCP servers se registran en `.opencode/opencode.jsonc` y quedan disponibles como tools del agente. OpenCode ya tiene soporte nativo para MCP — solo se configura.

```jsonc
// .opencode/opencode.jsonc (proyecto Alemana)
{
  "mcp": {
    "oracle": {
      "command": "python",
      "args": ["-m", "mcp_servers.oracle"],
      "env": {
        "ORACLE_DEV_HOST": "dev-oracle.alemana.local",
        "ORACLE_WALLET_PATH": "/secrets/oracle_wallet"
      }
    },
    "nats": {
      "command": "python",
      "args": ["-m", "mcp_servers.nats"],
      "env": { "NATS_URL": "nats://dev-nats.alemana.local:4222" }
    },
    "confluence": {
      "type": "http",
      "url": "https://wiki.alemana.cl/mcp",
      "headers": { "Authorization": "Bearer ${CONFLUENCE_TOKEN}" }
    }
  }
}
```

**Tools que expone cada MCP server al agente:**

```
oracle MCP server:
  ├── query_oracle(sql: string, sede: "CAS"|"CAT"|"CAV"|"ALL")
  │     → ejecuta en pool correcto, retorna rows o error ORA-
  ├── validate_sql_compat(sql: string, target_sede: string)
  │     → verifica compatibilidad 12c/19c, retorna { valid, issues[] }
  ├── get_table_schema(table: string, sede: string)
  │     → describe columnas, indices, constraints
  └── get_ibatis_mapping(mapper: string)
        → retorna el SQL map de iBATIS para ese mapper

nats MCP server:
  ├── publish_event(topic: string, payload: object)
  ├── subscribe_peek(topic: string, count: int)
  └── get_queue_stats(topic: string)

confluence MCP server:
  ├── search_docs(query: string, space?: string)
  └── get_page(page_id: string)
```

#### 3.8.3 Agentes custom por proyecto

Cada proyecto define sus agentes en `.opencode/opencode.jsonc`. Los agentes custom se combinan con los agentes nativos de OpenCode (`build`, `plan`, `general`, `explore`).

```jsonc
// .opencode/opencode.jsonc (proyecto Alemana)
{
  "agent": {
    "oracle-dba": {
      "description": "Agente especializado en SQL/PL-SQL para Oracle multi-sede Alemana",
      "model": "anthropic/claude-sonnet-4-6",
      "prompt": "Eres un DBA senior especializado en Oracle 12c y 19c para el sistema Alemana. Siempre verificas compatibilidad de sede antes de generar SQL. Usas la tool validate_sql_compat antes de proponer cualquier query. Nunca accedes a produccion.",
      "permission": {
        "bash": "deny",
        "mcp_oracle__query_oracle": "allow",
        "mcp_oracle__validate_sql_compat": "allow",
        "mcp_oracle__get_table_schema": "allow",
        "mcp_oracle__get_ibatis_mapping": "allow",
        "read": "allow",
        "edit": "ask"
      }
    },
    "python-backend": {
      "description": "Agente para desarrollo Python/FastAPI del pipeline HHMM",
      "model": "ollama/qwen2.5-coder:14b",
      "prompt": "Eres desarrollador Python senior. Trabajas con FastAPI, suscriptores NATS y modelos Pydantic v2. El pipeline se llama HHMM. Sigues los patrones del proyecto y generas tests pytest.",
      "permission": {
        "*": "allow",
        "mcp_oracle__query_oracle": "deny"
      }
    },
    "legacy-java": {
      "description": "Mantenimiento de PROFESI-HONORARI-J2E — solo bugfixes, nunca arquitectura nueva",
      "model": "anthropic/claude-sonnet-4-6",
      "prompt": "Eres especialista en Java EE legacy: Struts 1.3, iBATIS 2.x, Spring 2.5, WebLogic. Tu unico rol es mantenimiento conservador: bugs, campos, SQL maps. NUNCA propones refactorizaciones ni modulos nuevos. Siempre verificas que los cambios compilan con Maven antes de entregarlos.",
      "permission": {
        "read": "allow",
        "edit": "ask",
        "bash": "ask",
        "mcp_oracle__get_ibatis_mapping": "allow",
        "mcp_oracle__validate_sql_compat": "allow",
        "external_directory": { "*": "deny" }
      },
      "steps": 20
    },
    "integration": {
      "description": "Cambios cross-componente Oracle AQ → NATS → APIVALID",
      "model": "anthropic/claude-sonnet-4-6",
      "permission": {
        "*": "allow",
        "mcp_oracle__query_oracle": "allow",
        "mcp_nats__publish_event": "allow",
        "mcp_nats__get_queue_stats": "allow"
      }
    }
  }
}
```

#### 3.8.4 Flujo completo con Skills + MCP + Agente custom

```
Developer en TUI: /consulta-oracle
                  "¿cuantos honorarios pendientes hay en CAS este mes?"
        |
        v
Agente oracle-dba recibe el skill como contexto
        |
        | LLM decide invocar validate_sql_compat primero
        v
tool: mcp_oracle__validate_sql_compat
  { sql: "SELECT COUNT(*) FROM honorarios WHERE...", target_sede: "CAS" }
  → { valid: true, issues: [] }
        |
        | LLM decide ejecutar el query
        v
tool: mcp_oracle__query_oracle
  { sql: "SELECT COUNT(*) FROM honorarios WHERE estado='PENDIENTE' AND TRUNC(fecha,'MM')=TRUNC(SYSDATE,'MM')", sede: "CAS" }
  → { rows: [{ "COUNT(*)": 147 }], execution_time_ms: 23 }
        |
        v
Agente retorna respuesta formateada al TUI:
  "Hay 147 honorarios pendientes en CAS este mes.
   (Ejecutado en PSOL7/ROBLE, Oracle 12c — compatible)"
```

#### 3.8.5 Estructura de los MCP servers (servicios Python)

```
mcp_servers/                  # En el repositorio, como servicio separado
|-- oracle/
|   |-- __main__.py           # Entrypoint MCP server
|   |-- tools.py              # Implementacion de las tools
|   |-- pool.py               # Connection pool por sede (CAS/CAT/CAV)
|   |-- validator.py          # Validador de compatibilidad 12c/19c
|   |-- Dockerfile
|
|-- nats/
|   |-- __main__.py
|   |-- tools.py
|   |-- Dockerfile
|
|-- confluence/               # Opcional — proxy MCP para Confluence
|   |-- __main__.py
|   |-- tools.py
|
|-- base/
    |-- server.py             # Clase base MCP server reutilizable
    |-- auth.py               # Manejo de credenciales via Oracle Wallet / env
```

### 3.9 API — Endpoints completos

```
AUTH
  POST   /api/v1/auth/login           { email, password } → { access_token, refresh_token }
  POST   /api/v1/auth/refresh         { refresh_token } → { access_token }
  POST   /api/v1/auth/logout

ORGANIZACIONES (solo admin)
  GET    /api/v1/org                  → Organization[]
  POST   /api/v1/org                  → Organization
  GET    /api/v1/org/{id}             → Organization

PROYECTOS
  GET    /api/v1/org/{org_id}/project → Project[]
  POST   /api/v1/org/{org_id}/project → Project
  GET    /api/v1/project/{id}         → Project
  PUT    /api/v1/project/{id}         → Project (actualizar constraints, stack)
  DELETE /api/v1/project/{id}

RAG / KNOWLEDGE BASE
  POST   /api/v1/project/{id}/rag/seed   { documents[] } → seeding job
  GET    /api/v1/project/{id}/rag/status → { status, doc_count }

SESIONES
  POST   /api/v1/project/{id}/session      { feature_request } → Session
  GET    /api/v1/project/{id}/session      → Session[]
  GET    /api/v1/session/{id}              → Session + events
  DELETE /api/v1/session/{id}

  GET    /api/v1/session/{id}/stream       → SSE stream de eventos
  POST   /api/v1/session/{id}/approve      { decision, comment? }
  POST   /api/v1/session/{id}/escalate     { resolution }
  POST   /api/v1/session/{id}/abort

ARTEFACTOS
  GET    /api/v1/session/{id}/artifact     → Artifact[]
  GET    /api/v1/artifact/{id}             → Artifact (contenido completo)

FINE-TUNING — TRAINING SAMPLES
  GET    /api/v1/project/{id}/training-sample              → TrainingSample[] (paginado)
  GET    /api/v1/training-sample/{id}                      → TrainingSample
  PUT    /api/v1/training-sample/{id}/curate               { status, note } → TrainingSample
  GET    /api/v1/project/{id}/training-sample/export       → JSONL descargable (solo aprobados)
  GET    /api/v1/project/{id}/training-sample/stats        → { total, pending, approved, rejected }

FINE-TUNING — JOBS
  POST   /api/v1/project/{id}/finetune/job   { base_model, backend, compute, sample_ids[] } → Job
  GET    /api/v1/project/{id}/finetune/job   → Job[]
  GET    /api/v1/finetune/job/{id}           → Job + progreso
  GET    /api/v1/finetune/job/{id}/stream    → SSE: loss curve, logs en tiempo real
  POST   /api/v1/finetune/job/{id}/cancel    → Job

FINE-TUNING — MODEL REGISTRY
  GET    /api/v1/project/{id}/model          → ModelRegistry[]
  GET    /api/v1/model/{id}                  → ModelRegistry + eval_details
  POST   /api/v1/model/{id}/activate         → ModelRegistry (activa el modelo)
  POST   /api/v1/model/{id}/retire           → ModelRegistry
  PUT    /api/v1/project/{id}/ab-routing     { enabled, ratio } → config AB

TELEMETRIA
  POST   /api/v1/telemetry/event             → acepta eventos del TUI y Engine
  GET    /api/v1/telemetry/dashboard         → metricas de uso, tokens, latencias (solo admin)

SALUD
  GET    /api/v1/health                      → { status, db, rag, langgraph, ollama, finetune }
  GET    /api/v1/metrics                     → metricas basicas (solo admin)
```

---

## 4. Constraints

Estas constraints son NO NEGOCIABLES. Aplican a toda decision tecnica en este proyecto.

### 4.1 Aislamiento de datos

```
PROHIBIDO: cualquier query sin filtro por org_id + project_id
PROHIBIDO: compartir instancias del grafo LangGraph entre proyectos
PROHIBIDO: compartir namespaces del RAG entre proyectos
OBLIGATORIO: Row-Level Security activo en PostgreSQL para todas las tablas de negocio
OBLIGATORIO: tests de aislamiento multi-tenant antes de cada release
```

### 4.2 Seguridad y datos sensibles

```
PROHIBIDO: datos de pacientes (Alemana) fuera de la infraestructura controlada
PROHIBIDO: logs que contengan contenido de FRs de un cliente visible para otro
PROHIBIDO: tokens JWT con expiracion mayor a 24 horas para access_token
PROHIBIDO: credenciales en codigo fuente, variables de entorno sin secret manager
OBLIGATORIO: HTTPS en todos los endpoints (incluso en cloud privado)
OBLIGATORIO: refresh token rotation en cada uso
OBLIGATORIO: audit log de todas las acciones del usuario (inmutable)
```

### 4.3 Compatibilidad del OVD Engine

```
PROHIBIDO: modificar la logica interna de los agentes especializados
PROHIBIDO: cambiar el schema del grafo LangGraph sin actualizar este SDD
PROHIBIDO: acceder al OVD Engine directamente desde el TUI (siempre via API)
OBLIGATORIO: el OVD Engine se extiende, no se reescribe
OBLIGATORIO: toda extension al Engine debe pasar por revision del arquitecto
```

### 4.4 Lenguajes y tecnologias

```
OBLIGATORIO: TypeScript + Bun para todo codigo dentro del fork de OpenCode
OBLIGATORIO: SolidJS para extensiones del TUI (pantallas y componentes nuevos)
OBLIGATORIO: Hono para nuevas rutas en el servidor del fork
OBLIGATORIO: Python 3.11+ para OVD Engine, fine-tuning y telemetria (servicios separados)
OBLIGATORIO: Effect.ts para logica de dominio nueva dentro del fork (consistencia con el codebase existente)
OBLIGATORIO: PostgreSQL 16+ con pgvector para produccion (el fork usa SQLite en dev, consistente con OpenCode)
OBLIGATORIO: bun.lock commiteado en el fork. Cargo.lock no aplica — no hay Rust.
PROHIBIDO: reescribir en Rust o Go componentes que ya existen funcionando en OpenCode
PROHIBIDO: introducir un ORM distinto al que usa OpenCode internamente (Drizzle)
PROHIBIDO: agregar dependencias NPM sin revisar si OpenCode ya las provee en su workspace catalog
```

### 4.5 Distribucion

```
OBLIGATORIO: el producto se distribuye como binario compilado con Bun (bun build --compile)
  Bun genera un ejecutable standalone que incluye el runtime — sin necesidad de instalar Bun o Node.
OBLIGATORIO: cross-compilation verificada: macOS aarch64, macOS x86_64, Linux x86_64, Windows x64
  (OpenCode ya tiene este pipeline en .github/workflows/publish.yml — reutilizar)
OBLIGATORIO: el binario pesa menos de 50MB (Bun standalone es mas pesado que Rust, aceptable)
OBLIGATORIO: los servicios Python (OVD Engine, fine-tuning) se distribuyen como imagenes Docker
```

### 4.6 Fine-tuning

```
PROHIBIDO: usar training samples de proyecto A para entrenar modelo de proyecto B
PROHIBIDO: incluir datos con has_sensitive = true en ningun training set
PROHIBIDO: activar un modelo fine-tuned sin pasar la evaluacion automatica
PROHIBIDO: subir modelos fine-tuned a servicios externos (Hugging Face, etc.)
PROHIBIDO: lanzar un job de fine-tuning con samples en estado "pending" (solo "approved")
OBLIGATORIO: curacion humana de cada sample antes de incluirlo en cualquier job
OBLIGATORIO: el eval_score del modelo nuevo debe superar al modelo anterior antes de activacion
OBLIGATORIO: mantener el modelo base como fallback siempre disponible
OBLIGATORIO: jobs de fine-tuning en proceso separado — no bloquean el API Layer
OBLIGATORIO: los modelos fine-tuned se almacenan en almacenamiento local del servidor propio
```

### 4.7 Telemetria

```
PROHIBIDO: enviar datos de negocio (contenido de FRs, codigo generado) a servicios externos de telemetria
PROHIBIDO: telemetria que identifique usuarios individuales sin su consentimiento
OBLIGATORIO: toda telemetria se almacena primero en PostgreSQL local antes de cualquier exportacion
OBLIGATORIO: el sistema funciona completamente sin telemetria externa (modo offline-first)
OBLIGATORIO: metricas de costo de tokens por organizacion para control de presupuesto
```

### 4.8 Skills, MCP y agentes custom

```
PROHIBIDO: MCP server de Oracle con acceso a instancias de produccion (PSOL7/PSOL8 prod)
PROHIBIDO: MCP server que exponga credenciales en logs o en respuestas al LLM
PROHIBIDO: agente custom que desactive el aislamiento de tenant (org_id en todos los contextos)
OBLIGATORIO: Oracle Wallet para todas las credenciales de DB — nunca usuario/password en texto plano
OBLIGATORIO: el MCP server de Oracle valida compatibilidad 12c/19c antes de ejecutar cualquier query
OBLIGATORIO: skills del proyecto almacenados en el repositorio bajo control de versiones
OBLIGATORIO: cada MCP server tiene su propio Dockerfile y corre como contenedor aislado
PROHIBIDO: un MCP server acceder a namespaces RAG o datos de otro proyecto
OBLIGATORIO: timeout maximo de 30 segundos en cualquier tool MCP — si supera, retorna error descriptivo
```

### 4.9 Herencia de constraints del OVD

Las constraints del SDD_VDO_v19.docx siguen vigentes para el Engine:

```
Oracle 12c como minimo denominador comun para sede CAS
Stack Java legacy: solo mantenimiento, no arquitectura nueva
Datos sensibles de pacientes: solo modelos locales (Ollama)
Maximo 3 iteraciones de rechazo por agente antes de escalacion humana
```

---

## 5. Arquitectura detallada

### 5.1 Diagrama completo de componentes

```
┌─────────────────────────────────────────────────────────────────────┐
│  FORK DE OPENCODE (TypeScript / Bun)                                │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  packages/app — TUI (SolidJS + opentui)                    │    │
│  │                                                            │    │
│  │  [OpenCode existente]          [Nuevo — OVD extensions]   │    │
│  │  - session chat                - pantalla selector org     │    │
│  │  - diff viewer                 - modal aprobacion OVD      │    │
│  │  - file tree                   - stream agentes LangGraph  │    │
│  │  - provider selector           - pantalla fine-tuning      │    │
│  │  - settings                    - dashboard telemetria      │    │
│  └────────────────────┬───────────────────────────────────────┘    │
│                       │ IPC / HTTP local                           │
│  ┌────────────────────▼───────────────────────────────────────┐    │
│  │  packages/opencode — Servidor Hono + Core engine (Bun)     │    │
│  │                                                            │    │
│  │  [OpenCode existente]          [Nuevo — OVD extensions]   │    │
│  │  src/server/     (Hono)        src/tenant/   (multi-tenant)│    │
│  │  src/session/    (sesiones)    src/ovd/      (OVD bridge) │    │
│  │  src/agent/      (agentes)     src/auth/ext/ (JWT multi)  │    │
│  │  src/tool/       (bash,edit..) src/finetune/ (FT hooks)   │    │
│  │  src/provider/   (LLM providers)                          │    │
│  │  src/lsp/        (LSP nativo)                             │    │
│  └────────────────────┬───────────────────────────────────────┘    │
│                       │ HTTP (localhost)                           │
└───────────────────────┼─────────────────────────────────────────────┘
                        │
         ┌──────────────┴──────────────┐
         │                             │
┌────────▼──────────┐        ┌─────────▼──────────────────────────────┐
│  OVD ENGINE       │        │  SERVICIOS DE SOPORTE                  │
│  Python/LangGraph │        │                                        │
│  (FastAPI HTTP)   │        │  Fine-tuning Pipeline (Python)         │
│                   │        │  - collector, trainer, evaluator       │
│  Coordinator      │        │  - unsloth / axolotl + RunPod          │
│  Legacy agent     │        │                                        │
│  Backend agent    │        │  Telemetria (OpenTelemetry)            │
│  QA agent         │        │  - otel-collector → PostgreSQL         │
│  Security agent   │        │  - Grafana (Fase 3)                   │
│  ...              │        │                                        │
│  RAG (pgvector)   │        │  Docker Sandboxes                      │
│  Sandboxes        │        │  vdo-sandbox-python | vdo-sandbox-java │
└───────────────────┘        │                                        │
                             │  MCP Servers (configurados x proyecto) │
                             │  oracle-mcp → Oracle dev multi-sede    │
                             │  nats-mcp   → NATS broker dev          │
                             │  confluence-mcp → wiki interna         │
                             │  [extensibles por proyecto/usuario]    │
                             └────────────────────────────────────────┘
         │
┌────────▼──────────────────────────────────────────────────────────┐
│  INFRAESTRUCTURA                                                  │
│  PostgreSQL 16 + pgvector   Ollama   RunPod   LangSmith           │
│  Docker Compose → Kubernetes (Fase 3)                             │
└───────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│  INFRAESTRUCTURA                                                    │
│                                                                     │
│  PostgreSQL 16 + pgvector   LangGraph Checkpointer (PostgreSQL)    │
│  Ollama (modelos locales)   RunPod (GPU remota bajo demanda)        │
│  LangSmith (trazabilidad)   Docker / Docker Compose / K8s (Fase 3) │
└─────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│  FINE-TUNING PIPELINE                                               │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────────┐ │
│  │  Collector   │→ │  Trainer     │→ │  Evaluator + Model        │ │
│  │  (post-      │  │  unsloth /   │  │  Registry                 │ │
│  │  sesion)     │  │  axolotl     │  │                           │ │
│  └──────────────┘  └──────────────┘  └───────────────────────────┘ │
│                                                                     │
│  training_samples → fine_tuning_jobs → model_registry → Ollama     │
│  Curacion humana via TUI obligatoria antes de cada job             │
└─────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│  TELEMETRIA                                                         │
│                                                                     │
│  OpenTelemetry collector (local)  →  PostgreSQL (almacenamiento)   │
│  Metricas: tokens/sesion, latencia por nodo, costo por org,        │
│            tasa de aprobacion, eval_score de modelos FT            │
│  Exportacion opcional: Grafana / Prometheus (cloud privado Fase 3) │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 Estructura de repositorio

El repositorio es el fork de OpenCode. Se mantiene la estructura original intacta y se agregan los modulos nuevos en los lugares correctos del monorepo.

```
ovd-platform/  (fork de anomalyco/opencode)
|
|-- packages/
|   |
|   |-- opencode/src/             # Core engine — EXTENDIDO
|   |   |-- [... existente ...]   # Todo el codigo de OpenCode original
|   |   |
|   |   |-- tenant/               # NUEVO — multi-tenancy
|   |   |   |-- index.ts          # Organizaciones, proyectos, users
|   |   |   |-- middleware.ts     # Inyeccion de tenant context en cada request
|   |   |   |-- schema.sql.ts     # Tablas: organizations, projects, users (Drizzle)
|   |   |   |-- repo.ts
|   |   |
|   |   |-- ovd/                  # NUEVO — puente OpenCode <-> OVD Engine
|   |   |   |-- index.ts          # Registro del OVD como tipo de agente
|   |   |   |-- bridge.ts         # HTTP client hacia el OVD Engine Python
|   |   |   |-- session.ts        # Mapeo session OpenCode <-> thread LangGraph
|   |   |   |-- events.ts         # Transformacion de eventos LangGraph → bus OpenCode
|   |   |   |-- approval.ts       # Manejo de interrupts (human_approval, escalation)
|   |   |
|   |   |-- finetune/             # NUEVO — hooks de fine-tuning
|   |   |   |-- collector.ts      # Captura training samples post-sesion
|   |   |   |-- schema.sql.ts     # Tablas: training_samples, ft_jobs, model_registry
|   |   |
|   |   |-- server/               # EXTENDIDO — nuevas rutas Hono
|   |       |-- [... existente ...]
|   |       |-- routes/
|   |           |-- tenant.ts     # NUEVO /org, /project endpoints
|   |           |-- ovd.ts        # NUEVO /ovd/session, /ovd/approve endpoints
|   |           |-- finetune.ts   # NUEVO /finetune/* endpoints
|   |           |-- telemetry.ts  # NUEVO /telemetry/* endpoints
|   |
|   |-- app/src/                  # TUI SolidJS — EXTENDIDO
|   |   |-- [... existente ...]   # Todo el TUI de OpenCode original
|   |   |
|   |   |-- pages/ovd/            # NUEVO — pantallas OVD
|   |   |   |-- project-select.tsx     # Selector de org y proyecto
|   |   |   |-- approval-modal.tsx     # Human approval con tabs SDD
|   |   |   |-- escalation-modal.tsx   # Resolucion de escalaciones
|   |   |   |-- finetune.tsx           # Gestion de fine-tuning
|   |   |   |-- telemetry.tsx          # Dashboard de telemetria
|   |   |
|   |   |-- components/ovd/       # NUEVO — componentes OVD
|   |       |-- agent-stream.tsx       # Stream de eventos del grafo LangGraph
|   |       |-- sample-reviewer.tsx    # Revisor de training samples
|   |
|   |-- [... otros packages existentes de OpenCode ...]
|
|-- engine/                       # OVD Engine Python (servicio separado)
|   |-- graph.py
|   |-- coordinator.py
|   |-- specialized.py
|   |-- api.py                    # NUEVO — FastAPI HTTP server (expone el grafo)
|   |-- rag/
|   |   |-- store.py              # EXTENDIDO para namespace por proyecto
|   |   |-- seed.py
|   |   |-- research.py
|   |-- templates/
|   |-- Dockerfile
|
|-- docker/
|   |-- docker-compose.yml        # Dev local completo
|   |-- docker-compose.prod.yml   # Cloud privado
|   |-- Dockerfile.api
|   |-- Dockerfile.sandbox-python
|   |-- Dockerfile.sandbox-java
|
|-- infra/                        # K8s manifests (Fase 3)
|   |-- namespace.yaml
|   |-- api-deployment.yaml
|   |-- postgres-statefulset.yaml
|   |-- ...
|
|-- mcp_servers/                  # MCP Servers (servicios Python, uno por integracion)
|   |-- base/
|   |   |-- server.py             # Clase base MCP reutilizable
|   |   |-- auth.py               # Manejo de credenciales (Oracle Wallet, env)
|   |-- oracle/
|   |   |-- __main__.py           # Entrypoint MCP server Oracle
|   |   |-- tools.py              # query_oracle, validate_sql_compat, get_table_schema, get_ibatis_mapping
|   |   |-- pool.py               # Connection pool por sede (CAS/CAT/CAV)
|   |   |-- validator.py          # Validador compatibilidad Oracle 12c/19c
|   |   |-- Dockerfile
|   |   |-- tests/
|   |-- nats/
|   |   |-- __main__.py
|   |   |-- tools.py              # publish_event, subscribe_peek, get_queue_stats
|   |   |-- Dockerfile
|   |-- confluence/               # Opcional
|       |-- __main__.py
|       |-- tools.py
|
|-- fine_tuning/                  # Fine-tuning Pipeline (Python)
|   |-- collector.py              # Recoleccion de training samples post-sesion
|   |-- detector.py               # Deteccion de datos sensibles en samples
|   |-- trainer.py                # Lanzamiento de jobs (unsloth / axolotl)
|   |-- evaluator.py              # Benchmark automatico de modelos entrenados
|   |-- exporter.py               # Exporta dataset aprobado en formato JSONL
|   |-- benchmark/
|   |   |-- alemana_legacy.jsonl  # Benchmark especifico del proyecto Alemana
|   |   |-- base_benchmark.jsonl  # Benchmark generico reutilizable
|   |-- Dockerfile.trainer        # Imagen para jobs de fine-tuning
|
|-- telemetry/                    # Telemetria (OpenTelemetry)
|   |-- otel_collector.yaml       # Configuracion del collector local
|   |-- instruments.py            # Instrumentacion del API Layer y Engine
|   |-- dashboard/
|   |   |-- grafana_dashboard.json  # Dashboard para Fase 3
|
|-- scripts/
|   |-- setup-dev.sh              # Setup rapido del entorno dev
|   |-- seed-project.py           # Seed RAG de un proyecto nuevo
|   |-- create-org.py             # Script de onboarding de org
|   |-- export-dataset.py         # Exporta training samples aprobados de un proyecto
|
|-- .env.example
|-- README.md
|-- CONTRIBUTING.md
```

### 5.3 Docker Compose para desarrollo local

```yaml
# docker-compose.yml (referencia de diseno)
services:
  api:
    build: ./api
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql://ovd:ovd@postgres:5432/ovd
      JWT_SECRET: dev-secret-cambiar-en-prod
    depends_on: [postgres, ollama]

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: ovd
      POSTGRES_USER: ovd
      POSTGRES_PASSWORD: ovd
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports: ["5432:5432"]

  ollama:
    image: ollama/ollama
    ports: ["11434:11434"]
    volumes:
      - ollama_data:/root/.ollama

  langsmith:
    # Opcional en dev, obligatorio en staging/prod
    image: langchain/langsmith-backend:latest

  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    volumes:
      - ./telemetry/otel_collector.yaml:/etc/otel/config.yaml
    command: ["--config=/etc/otel/config.yaml"]
    ports: ["4317:4317"]   # gRPC
    depends_on: [postgres]

  trainer:
    build:
      context: ./fine_tuning
      dockerfile: Dockerfile.trainer
    profiles: ["finetune"]   # solo se levanta cuando se necesita
    volumes:
      - models_data:/models
      - ./fine_tuning:/app
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]

volumes:
  postgres_data:
  ollama_data:
  models_data:
```

---

## 6. Tasks

### 6.1 TASK-FORK-001 — Setup del fork y entorno de desarrollo

**Agente:** Developer TypeScript/Bun
**Dependencias:** ninguna
**Criterios de aceptacion:**
- Fork de `anomalyco/opencode` creado en la organizacion de Omar Robles (repositorio privado)
- Rama `upstream/dev` configurada para tracking del repo original
- `bun install` exitoso y `bun run dev` levanta el TUI de OpenCode sin modificaciones
- Rama `main` con primer commit: agregar carpetas `packages/opencode/src/tenant/`, `src/ovd/`, `src/finetune/` vacias con `index.ts` de placeholder
- `docker-compose.yml` actualizado con servicio `ovd-engine` (Python) y `otel-collector`
- README del fork con clausula de disassociation y creditos a Anomaly Co. (cumplimiento Apache 2.0)
- Variables de entorno documentadas en `.env.example`

**Artefactos:**
- Repositorio fork configurado
- `docker-compose.yml` con todos los servicios
- `CREDITS.md` con atribucion a OpenCode
- `README.md` del fork con disassociation clause

---

### 6.2 TASK-FORK-002 — Multi-tenancy en el core de OpenCode

**Agente:** Developer TypeScript/Bun
**Dependencias:** TASK-FORK-001
**Criterios de aceptacion:**
- Tablas `organizations`, `projects`, `users` creadas con migracion Drizzle en `packages/opencode/src/tenant/schema.sql.ts`
- Row-Level Security habilitado en PostgreSQL para las tablas de negocio
- Middleware Hono que extrae `org_id` del JWT y lo inyecta en el contexto de cada request
- Rutas nuevas en el servidor Hono: `GET/POST /org`, `GET/POST/PUT/DELETE /project`
- Auth JWT extendido: login con email/password retorna token con `org_id` y `role`
- Test de aislamiento: queries de org A no retornan datos de org B
- `bun test` pasa todos los tests de aislamiento

**Artefactos:**
- `packages/opencode/src/tenant/index.ts`, `schema.sql.ts`, `middleware.ts`, `repo.ts`
- `packages/opencode/src/server/routes/tenant.ts`
- Tests en `packages/opencode/src/tenant/*.test.ts`

---

### 6.3 TASK-FORK-003 — OVD Bridge (el componente mas critico)

**Agente:** Developer TypeScript/Bun + Arquitecto
**Dependencias:** TASK-FORK-002
**Criterios de aceptacion:**
- `packages/opencode/src/ovd/bridge.ts` consume la API HTTP del OVD Engine Python
- Una sesion de OpenCode puede invocar el grafo LangGraph y recibir sus eventos via SSE
- Los interrupts de LangGraph (`human_approval`, `handle_escalation`) se traducen a eventos del bus de OpenCode que el TUI puede escuchar
- `packages/opencode/src/ovd/session.ts` mapea `session.id` de OpenCode al `thread_id` de LangGraph
- El OVD aparece como un tipo de agente seleccionable en OpenCode (igual que `build` o `plan`)
- Rutas Hono nuevas: `POST /ovd/session`, `POST /ovd/session/:id/approve`, `POST /ovd/session/:id/escalate`
- Test end-to-end con OVD Engine mock que simula interrupt y resume

**Artefactos:**
- `packages/opencode/src/ovd/bridge.ts`
- `packages/opencode/src/ovd/session.ts`
- `packages/opencode/src/ovd/events.ts`
- `packages/opencode/src/ovd/approval.ts`
- `packages/opencode/src/server/routes/ovd.ts`
- `engine/api.py` — FastAPI HTTP wrapper del grafo LangGraph

---

### 6.4 TASK-FORK-004 — TUI: pantallas OVD en SolidJS

**Agente:** Developer SolidJS/TypeScript
**Dependencias:** TASK-FORK-003
**Criterios de aceptacion:**
- Pantalla de seleccion de organizacion y proyecto al arrancar (si hay mas de uno disponible)
- Modal de aprobacion del plan SDD con tabs: requirements / design / constraints / tasks — scrolleable
- El usuario puede aprobar [A] o rechazar [R] con comentario opcional
- Modal de escalacion: muestra el bloqueo del agente y campo de resolucion
- Panel de progreso del grafo LangGraph en el area de sesion activa: nombre del nodo + estado (running/ok/error)
- Los eventos del OVD Bridge se consumen via el bus de OpenCode existente
- Todos los atajos de teclado siguen el patron de OpenCode (documentados en settings-keybinds)

**Artefactos:**
- `packages/app/src/pages/ovd/project-select.tsx`
- `packages/app/src/pages/ovd/approval-modal.tsx`
- `packages/app/src/pages/ovd/escalation-modal.tsx`
- `packages/app/src/components/ovd/agent-stream.tsx`

---

### 6.5 TASK-FORK-005 — RAG multi-proyecto y onboarding

**Agente:** Developer Python
**Dependencias:** TASK-FORK-002
**Criterios de aceptacion:**
- `engine/rag/store.py` extendido para usar namespace por `project_id` en pgvector
- Script `scripts/seed-project.py` carga el RAG de un proyecto nuevo desde documentos
- Script `scripts/create-org.py` crea org + proyecto + usuario admin en un paso
- El Research agent del OVD accede solo al namespace del proyecto activo
- Test de aislamiento RAG: seed en proyecto A no aparece en queries del proyecto B
- Seed inicial de Alemana ejecutado y verificado

**Artefactos:**
- Extension de `engine/rag/store.py`
- `scripts/seed-project.py`
- `scripts/create-org.py`
- `packages/opencode/src/server/routes/rag.ts` (endpoints de seed y status)

---

### 6.6 TASK-API-006 — SSE Manager + Endpoints de sesion

**Agente:** Developer Backend
**Dependencias:** TASK-API-005
**Criterios de aceptacion:**
- GET /api/v1/session/{id}/stream envia eventos SSE mientras la sesion corre
- El cliente puede reconectarse al stream y recibir eventos desde el ultimo recibido (Last-Event-ID)
- POST /session/{id}/approve desbloquea el interrupt `human_approval`
- POST /session/{id}/escalate desbloquea el interrupt `handle_escalation`
- POST /session/{id}/abort cancela la sesion limpiamente
- Test con cliente SSE mock

**Artefactos:**
- `api/app/services/sse_manager.py`
- `api/app/routers/session.py`
- `api/tests/test_sse.py`

---

### 6.7 TASK-API-007 — RAG multi-proyecto

**Agente:** Developer Backend
**Dependencias:** TASK-API-004
**Criterios de aceptacion:**
- `rag_service.py` extiende el `store.py` del OVD Engine para usar namespace por `project_id`
- POST /project/{id}/rag/seed acepta documentos y los indexa en el namespace del proyecto
- Script `seed-project.py` para cargar el RAG de Alemana en el proyecto Alemana
- El Research agent del OVD lee solo del namespace del proyecto activo
- Test: seed en proyecto A no es visible en queries del proyecto B

**Artefactos:**
- `api/app/services/rag_service.py`
- `api/app/routers/rag.py`
- `scripts/seed-project.py`
- `api/tests/test_rag_isolation.py`

---

### 6.8 TASK-TUI-001 — Setup del proyecto Rust

**Agente:** Developer Rust
**Dependencias:** ninguna (paralelo a TASK-API-001)
**Criterios de aceptacion:**
- Proyecto Rust inicializado con `cargo new tui`
- Dependencias en Cargo.toml: ratatui, crossterm, tokio, reqwest, serde_json, eventsource-client
- Estructura de modulos segun 5.2
- `cargo build --release` exitoso en macOS y Linux
- Loop principal de ratatui corriendo (pantalla en blanco funcional)

**Artefactos:**
- `tui/Cargo.toml`
- `tui/src/main.rs`
- `tui/src/app.rs`

---

### 6.9 TASK-TUI-002 — API Client + modelos

**Agente:** Developer Rust
**Dependencias:** TASK-TUI-001, TASK-API-002
**Criterios de aceptacion:**
- `api/client.rs` implementa: login, refresh, listar proyectos, crear sesion, aprobar, escalar
- `api/models.rs` refleja todos los tipos de respuesta del API Layer
- El cliente guarda el token en `~/.ovd/config.toml`
- Test unitario de serializacion/deserializacion de responses

**Artefactos:**
- `tui/src/api/client.rs`
- `tui/src/api/models.rs`
- `tui/src/config.rs`

---

### 6.10 TASK-TUI-003 — SSE consumer

**Agente:** Developer Rust
**Dependencias:** TASK-TUI-002, TASK-API-006
**Criterios de aceptacion:**
- `api/client.rs` implementa consumo de SSE con reconexion automatica
- Los eventos SSE se deserializan a tipos Rust definidos en `models.rs`
- Los eventos se envian a un canal tokio para que el loop de ratatui los consuma
- Reconexion con Last-Event-ID funciona correctamente
- Test con servidor SSE mock

**Artefactos:**
- Extension de `tui/src/api/client.rs`

---

### 6.11 TASK-TUI-004 — Pantallas: Login y Selector de proyecto

**Agente:** Developer Rust
**Dependencias:** TASK-TUI-002
**Criterios de aceptacion:**
- Pantalla Login: campos email y password (password enmascarado), manejo de error 401
- Pantalla Selector: lista de proyectos de la org, navegacion con flechas, Enter para seleccionar
- Transicion Login → Selector → Layout principal funcional
- El token se persiste entre sesiones del TUI

**Artefactos:**
- `tui/src/screens/login.rs`
- `tui/src/screens/project_select.rs`

---

### 6.12 TASK-TUI-005 — Layout principal + Stream view

**Agente:** Developer Rust
**Dependencias:** TASK-TUI-003, TASK-TUI-004
**Criterios de aceptacion:**
- Layout de 3 paneles: lista de sesiones (izquierda), sesion activa (centro-top), prompt (centro-bottom)
- Panel de sesion activa muestra eventos del stream en tiempo real con colores por tipo de nodo
- Input de FR envia al API y arranca el stream de la nueva sesion
- Indicador visual de estado: running / pending_approval / escalated / completed / failed
- Navegacion con teclado documentada en barra de ayuda inferior

**Artefactos:**
- `tui/src/screens/main_layout.rs`
- `tui/src/components/stream_view.rs`
- `tui/src/components/prompt_input.rs`
- `tui/src/components/session_list.rs`

---

### 6.13 TASK-TUI-006 — Modal de aprobacion y escalaciones

**Agente:** Developer Rust
**Dependencias:** TASK-TUI-005
**Criterios de aceptacion:**
- Al recibir evento `approval_required`, el TUI muestra modal con tabs (requirements / design / constraints / tasks)
- El usuario puede navegar entre tabs, scrollear el contenido y aprobar [A] o rechazar [R] con comentario
- Al recibir evento `escalation`, el TUI muestra el bloqueo y permite escribir la resolucion
- El modal se cierra y el stream continua tras la decision
- Test visual con evento simulado

**Artefactos:**
- `tui/src/screens/approval_modal.rs`

---

### 6.14 TASK-TUI-007 — Diff viewer y pantalla de entregables

**Agente:** Developer Rust
**Dependencias:** TASK-TUI-005
**Criterios de aceptacion:**
- Al recibir evento `completed`, se habilita pantalla de entregables
- Muestra lista de archivos entregados con indicador NUEVO / MODIFICADO
- Diff coloreado (verde adiciones, rojo eliminaciones) con syntax highlighting basico
- Tabs: Codigo / QA / Security con sus reportes
- [S] guarda los archivos al filesystem local
- [C] copia al portapapeles

**Artefactos:**
- `tui/src/screens/artifacts.rs`
- `tui/src/components/diff_viewer.rs`

---

### 6.15 TASK-EXT-001 — MCP server Oracle multi-sede

**Agente:** Developer Python + DBA
**Dependencias:** TASK-FORK-001
**Criterios de aceptacion:**
- `mcp_servers/oracle/` implementa el protocolo MCP con las tools: `query_oracle`, `validate_sql_compat`, `get_table_schema`, `get_ibatis_mapping`
- El pool de conexiones enruta automaticamente segun sede: CAS → PSOL7/ROBLE (Oracle 12c), CAT/CAV → PSOL8 (Oracle 19c)
- `validate_sql_compat` rechaza features 19c cuando `target_sede` incluye CAS (JSON nativo, SQL Macros, LISTAGG overflow)
- Credenciales gestionadas exclusivamente via Oracle Wallet — ningun usuario/password en variables de entorno ni logs
- Timeout de 30s en toda ejecucion — retorna error descriptivo al LLM si supera el limite
- El servidor MCP NO tiene acceso a instancias de produccion (verificado por constraint de red)
- Test: agente invoca `query_oracle` con SQL valido en cada sede y recibe resultado correcto
- Test: agente invoca `validate_sql_compat` con SQL que usa JSON nativo de 19c para sede CAS → retorna `{ valid: false, issues: ["JSON_OBJECT() no disponible en Oracle 12c"] }`

**Artefactos:**
- `mcp_servers/oracle/__main__.py`
- `mcp_servers/oracle/tools.py`
- `mcp_servers/oracle/pool.py`
- `mcp_servers/oracle/validator.py`
- `mcp_servers/oracle/Dockerfile`
- `mcp_servers/base/server.py`
- `mcp_servers/base/auth.py`
- Tests en `mcp_servers/oracle/tests/`

---

### 6.16 TASK-EXT-002 — Skills del proyecto Alemana

**Agente:** Arquitecto + Developer
**Dependencias:** TASK-FORK-001
**Criterios de aceptacion:**
- Skills creados en `.opencode/command/` para el proyecto Alemana:
  - `consulta-oracle.md` — protocolo para generar y ejecutar SQL multi-sede
  - `fix-legacy.md` — protocolo para modificar codigo Struts/iBATIS/Spring 2.5
  - `revision-seguridad.md` — checklist OWASP adaptado a healthcare
  - `validar-nats.md` — protocolo para verificar integracion con NATS
  - `nuevo-endpoint.md` — patron para crear endpoints FastAPI en pipeline HHMM
- Cada skill documentado con: proposito, cuando usarlo, pasos, ejemplos
- Skills versionados en el repositorio bajo control de cambios
- Test: invocar `/fix-legacy` en una sesion y verificar que el agente sigue el protocolo definido

**Artefactos:**
- `.opencode/command/consulta-oracle.md`
- `.opencode/command/fix-legacy.md`
- `.opencode/command/revision-seguridad.md`
- `.opencode/command/validar-nats.md`
- `.opencode/command/nuevo-endpoint.md`

---

### 6.17 TASK-EXT-003 — Agentes custom en opencode.jsonc

**Agente:** Arquitecto
**Dependencias:** TASK-EXT-001, TASK-EXT-002
**Criterios de aceptacion:**
- `.opencode/opencode.jsonc` del proyecto Alemana define los agentes: `oracle-dba`, `python-backend`, `legacy-java`, `integration`
- Cada agente tiene: modelo, prompt especializado y permisos granulares de tools
- `legacy-java` usa Claude API (nunca Ollama), `python-backend` usa Ollama local por defecto
- Los agentes aparecen disponibles en el selector de agentes del TUI (Tab para ciclar)
- Los permisos MCP estan correctamente restringidos por agente (ej: `python-backend` no puede invocar `mcp_oracle__query_oracle`)
- Test: cambiar al agente `oracle-dba` y verificar que solo las tools Oracle MCP estan disponibles
- Test: cambiar al agente `legacy-java` y verificar que el modelo usado es Claude API

**Artefactos:**
- `.opencode/opencode.jsonc` con configuracion completa de los 4 agentes
- `scripts/validate-config.ts` — valida el opencode.jsonc contra el schema esperado

---

### 6.18 TASK-EXT-004 — MCP server NATS (opcional, Fase 2)

**Agente:** Developer Python
**Dependencias:** TASK-EXT-001
**Criterios de aceptacion:**
- `mcp_servers/nats/` implementa las tools: `publish_event`, `subscribe_peek`, `get_queue_stats`
- Solo conecta al broker NATS de desarrollo — nunca produccion
- El agente `integration` puede invocar las tools NATS en sus sesiones
- Test: agente publica evento en topic de dev y verifica la respuesta

**Artefactos:**
- `mcp_servers/nats/__main__.py`
- `mcp_servers/nats/tools.py`
- `mcp_servers/nats/Dockerfile`

---

### 6.15 TASK-FT-001 — Collector de training samples

**Agente:** Developer Backend
**Dependencias:** TASK-API-006 (sesiones completas ya existentes)
**Criterios de aceptacion:**
- `fine_tuning/collector.py` se activa automaticamente al completar una sesion con status `completed`
- Extrae pares input/output por agente desde `session_events`
- Aplica `detector.py` para marcar `has_sensitive = true` si detecta patrones de datos sensibles (RUT, nombre paciente, diagnostico)
- Calcula `quality_score` basado en resultado QA (pass=1.0, observations=0.7, rejected=0.0) y escalaciones (-0.1 por escalacion)
- Inserta en `training_samples` con `curator_status = "pending"`
- Test: sesion aprobada de Alemana genera al menos un sample por agente participante
- Test: sesion con datos de pacientes genera samples con `has_sensitive = true`

**Artefactos:**
- `fine_tuning/collector.py`
- `fine_tuning/detector.py`
- `api/tests/test_ft_collector.py`

---

### 6.16 TASK-FT-002 — API de curacion y pantalla TUI

**Agente:** Developer Backend + Developer Rust
**Dependencias:** TASK-FT-001, TASK-TUI-005
**Criterios de aceptacion:**
- GET /project/{id}/training-sample retorna lista paginada con filtro por `curator_status`
- PUT /training-sample/{id}/curate actualiza status con registro del curador y timestamp
- Pantalla TUI "Fine-tuning": lista samples pendientes, muestra input/output en panel lateral, teclas [A]/[R] para aprobar/rechazar
- Samples con `has_sensitive = true` se muestran con advertencia visual en rojo
- Test: curador aprueba sample → status cambia y queda registrado quien lo hizo

**Artefactos:**
- `api/app/routers/fine_tuning.py` (endpoints de samples)
- `tui/src/screens/fine_tuning.rs`
- `api/tests/test_ft_curation.py`

---

### 6.17 TASK-FT-003 — Trainer + evaluator + model registry

**Agente:** Developer Backend + ML Engineer
**Dependencias:** TASK-FT-002
**Criterios de aceptacion:**
- `fine_tuning/exporter.py` genera JSONL con samples aprobados en formato instruccion/respuesta
- `fine_tuning/trainer.py` lanza job usando unsloth (GPU local) o axolotl + RunPod API
- Job publica progreso (step, loss, eta) via SSE al TUI
- Al completar, el modelo se guarda en `/models/{project_id}/{job_id}/` y se registra en `model_registry` con status `evaluating`
- `fine_tuning/evaluator.py` corre benchmark del proyecto y actualiza `eval_score` y `eval_details`
- Status cambia a `ready` al terminar la evaluacion
- Test: job completo con dataset dummy de 10 samples en CPU (modo test sin GPU real)

**Artefactos:**
- `fine_tuning/exporter.py`
- `fine_tuning/trainer.py`
- `fine_tuning/evaluator.py`
- `fine_tuning/benchmark/base_benchmark.jsonl`
- `api/app/routers/fine_tuning.py` (endpoints de jobs y model registry)
- `api/tests/test_ft_trainer.py`

---

### 6.18 TASK-FT-004 — Activacion y routing de modelos

**Agente:** Developer Backend
**Dependencias:** TASK-FT-003
**Criterios de aceptacion:**
- POST /model/{id}/activate carga el modelo en Ollama via `ollama pull` y actualiza `is_active = true`
- El OVD Engine lee `model_registry` al inicio de cada sesion para seleccionar modelo por agente
- Routing A/B funcional: configurable via PUT /project/{id}/ab-routing { enabled, ratio }
- Un solo modelo activo por agente por proyecto a la vez (activar uno desactiva el anterior)
- Test: activar modelo A, verificar que Engine lo usa. Activar modelo B, verificar que A queda retired

**Artefactos:**
- Extension de `engine/specialized.py` (funcion `get_model_for_agent`)
- Extension de `api/app/routers/fine_tuning.py`
- `api/tests/test_ft_activation.py`

---

### 6.19 TASK-TEL-001 — Instrumentacion con OpenTelemetry

**Agente:** Developer Backend
**Dependencias:** TASK-API-005
**Criterios de aceptacion:**
- `telemetry/instruments.py` instrumenta el API Layer con spans de OpenTelemetry para cada request y cada llamada al OVD Engine
- Metricas recolectadas: tokens_input, tokens_output, latencia_por_nodo, costo_estimado_api, modelo_usado, agente, proyecto
- El OVD Engine emite eventos de traza al iniciar y completar cada nodo del grafo
- El collector local escribe a PostgreSQL (`telemetry_events` table) sin dependencia de servicios externos
- GET /api/v1/telemetry/dashboard retorna metricas agrupadas por org/proyecto/agente
- Test: ejecutar sesion de prueba y verificar que todos los spans aparecen en la tabla

**Artefactos:**
- `telemetry/instruments.py`
- `telemetry/otel_collector.yaml`
- `api/app/db/migrations/002_telemetry.py` (tabla telemetry_events)
- `api/app/routers/telemetry.py`
- `api/tests/test_telemetry.py`

---

### 6.20 TASK-TEL-002 — Dashboard de telemetria en TUI

**Agente:** Developer Rust
**Dependencias:** TASK-TEL-001, TASK-TUI-005
**Criterios de aceptacion:**
- Pantalla TUI "Telemetria" muestra: tokens usados hoy/mes, costo estimado, latencia promedio por agente, tasa de aprobacion de FRs, eval_score de modelos activos
- Filtros: por proyecto, por agente, por rango de fechas (semana / mes)
- Los datos se cargan desde GET /api/v1/telemetry/dashboard
- Exportacion a CSV desde el TUI: [E] exportar
- En Fase 3: conexion a Grafana/Prometheus disponible via otel_collector.yaml

**Artefactos:**
- `tui/src/screens/telemetry.rs`
- `telemetry/dashboard/grafana_dashboard.json`

---

### 6.15 TASK-INFRA-001 — Docker Compose de produccion

**Agente:** DevOps / Arquitecto
**Dependencias:** TASK-API-007, TASK-TUI-001
**Criterios de aceptacion:**
- `docker-compose.prod.yml` levanta: API, PostgreSQL, Ollama, sandboxes
- Variables de entorno desde archivo `.env` (nunca hardcodeadas)
- Volumen persistente para PostgreSQL y Ollama
- Health checks configurados
- Script `setup-dev.sh` funcional en macOS y Linux
- README con instrucciones de instalacion para el equipo

**Artefactos:**
- `docker-compose.prod.yml`
- `scripts/setup-dev.sh`
- `README.md`

---

### 6.16 TASK-INFRA-002 — Pipeline CI/CD

**Agente:** DevOps
**Dependencias:** TASK-INFRA-001
**Criterios de aceptacion:**
- GitHub Actions: tests de API en cada PR
- GitHub Actions: build del binario TUI para las 4 plataformas en cada tag
- Binarios adjuntados al GitHub Release automaticamente
- Tests de aislamiento multi-tenant corren en CI

**Artefactos:**
- `.github/workflows/test-api.yml`
- `.github/workflows/build-tui.yml`
- `.github/workflows/release.yml`

---

## 7. Fases de implementacion

### Fase 0 — Fundacion (Semanas 1-3)

**Objetivo:** el equipo puede conectarse al sistema y enviar un FR via TUI

**Tasks en paralelo:**
- TASK-FORK-001 — Setup fork y entorno de desarrollo
- TASK-EXT-002 — Skills del proyecto Alemana (paralelo, no tiene dependencias de codigo)

**Tasks secuenciales:**
- TASK-FORK-002 — Multi-tenancy en el core
- TASK-FORK-003 — OVD Bridge
- TASK-FORK-004 — TUI: pantallas OVD
- TASK-EXT-001 — MCP server Oracle multi-sede
- TASK-EXT-003 — Agentes custom en opencode.jsonc

**Entregable:** el developer hace login, selecciona proyecto Alemana, escribe un FR con el agente `oracle-dba` y el agente consulta Oracle directamente via MCP

**Costo infraestructura:** $20-50 USD/mes (misma Fase 0 del OVD original)

---

### Fase 1 — Loop completo (Semanas 4-7)

**Objetivo:** el ciclo completo de FR → aprobacion → entregables funciona

**Tasks:**
- TASK-API-005 — OVD Runner (la mas critica)
- TASK-API-006 — SSE Manager + endpoints sesion
- TASK-TUI-003 — SSE consumer
- TASK-TUI-005 — Layout principal + Stream view
- TASK-TUI-006 — Modal aprobacion y escalaciones
- TASK-TUI-007 — Diff viewer y entregables

**Entregable:** el equipo puede completar un FR real de Alemana end-to-end via TUI, con aprobacion humana y entregables con diffs

**Costo infraestructura:** $110-160 USD/mes (suma RunPod para Java legacy)

---

### Fase 2 — Multi-proyecto + Fine-tuning + Telemetria (Semanas 8-14)

**Objetivo:** onboarding de segundo proyecto, primer ciclo de fine-tuning completo y telemetria operativa

**Tasks:**
- TASK-API-007 — RAG multi-proyecto
- TASK-INFRA-001 — Docker Compose produccion
- TASK-INFRA-002 — CI/CD
- TASK-FT-001 — Collector de training samples
- TASK-FT-002 — API de curacion + pantalla TUI
- TASK-FT-003 — Trainer + evaluator + model registry
- TASK-FT-004 — Activacion y routing de modelos
- TASK-TEL-001 — Instrumentacion OpenTelemetry
- TASK-TEL-002 — Dashboard telemetria en TUI

**Actividades adicionales:**
- Onboarding de segundo proyecto (stack diferente a Alemana)
- Seed del RAG con conocimiento del segundo proyecto
- Validacion de aislamiento en produccion
- Primer ciclo de fine-tuning con datos reales de Alemana (Legacy agent + QA agent)
- Validacion de mejora de quality_score vs modelo base
- Activacion del primer modelo fine-tuned en produccion

**Entregable:**
- Dos proyectos de distintas organizaciones sin interferencia
- Dashboard de telemetria mostrando tokens, costos y latencias reales
- Primer modelo fine-tuned activo reduciendo llamadas a Claude API para tareas Python/QA
- Binario TUI distribuible via GitHub Releases

**Costo infraestructura:** $160-240 USD/mes + costo puntual de job RunPod (~$5-15 por run de fine-tuning)

---

### Fase 3 — Cloud privado (Semanas 13-20)

**Objetivo:** sistema desplegado en servidor dedicado, accesible para el equipo via red privada

**Tasks:**
- K8s manifests para API y PostgreSQL
- Keycloak o auth propio para gestion de usuarios
- Dashboard de admin en TUI (gestion de orgs y proyectos)
- Observabilidad: LangSmith + logs centralizados
- SLA 99.5% uptime

**Entregable:** cloud privado Omar Robles funcionando con multiples clientes

**Costo infraestructura:** $240-310 USD/mes

---

### Fase 4 — Base SaaS (Fase futura, sin fecha)

**Actividades:**
- Web UI para clientes que no usan terminal
- Billing y planes de pricing basado en tokens y modelos fine-tuned
- Self-service onboarding
- K8s autoscaling
- Soporte multi-region
- Fine-tuning como servicio: los clientes SaaS construyen modelos especializados en su stack
- Telemetria multi-tenant con dashboards por cliente

---

### Fase 5 — TUI propio en Rust (Fase futura, sin fecha)

**Contexto y motivacion:**

En las fases anteriores el TUI es el fork de OpenCode (SolidJS/opentui). Esta fase reemplaza ese cliente por un TUI escrito completamente desde cero en Rust, sin ningun codigo derivado de OpenCode. El backend (servidor Hono + OVD Engine) no cambia — el TUI nuevo consume exactamente los mismos endpoints.

Esta fase tiene sentido cuando se cumplan al menos dos de estas condiciones:
- El producto esta validado comercialmente y justifica la inversion
- Se necesita distribuir a entornos sin acceso a internet o con restricciones de instalacion (binario puro sin runtime)
- El TUI de OpenCode upstream genera conflictos recurrentes al sincronizar mejoras
- Se requiere UX o rendimiento que SolidJS/opentui no puede proveer
- Se quiere eliminar toda dependencia del codigo de Anomaly Co.

**Stack:**

```
Lenguaje:    Rust (edition 2021)
TUI:         ratatui + crossterm
Async:       tokio
HTTP/SSE:    reqwest + eventsource-client
Config:      ~/.ovd/config.toml (toml crate)
Build:       cargo build --release + cross (cross-compilation)
Distribucion: binario ~5-15MB sin dependencias de runtime
```

**Lo que se construye:**

```
tui-rust/
|-- src/
|   |-- main.rs
|   |-- app.rs               # Estado global, event loop
|   |-- api/
|   |   |-- client.rs        # HTTP client + SSE consumer
|   |   |-- models.rs        # Tipos que reflejan los endpoints del servidor Hono
|   |-- screens/
|   |   |-- login.rs
|   |   |-- project_select.rs
|   |   |-- main_layout.rs   # 3 paneles: sesiones / chat activo / prompt
|   |   |-- approval_modal.rs # Human-in-the-loop con tabs SDD
|   |   |-- escalation.rs
|   |   |-- artifacts.rs     # Entregables con diff coloreado
|   |   |-- finetune.rs      # Gestion de fine-tuning
|   |   |-- telemetry.rs     # Dashboard de telemetria
|   |-- components/
|   |   |-- diff_viewer.rs   # Syntax highlight + verde/rojo
|   |   |-- stream_view.rs   # Stream de eventos LangGraph en tiempo real
|   |   |-- session_list.rs
|   |   |-- prompt_input.rs
|   |-- config.rs
|-- Cargo.toml
|-- Cargo.lock
```

**Ventajas respecto al TUI del fork:**

| Aspecto | Fork OpenCode (SolidJS) | TUI Rust propio |
|---------|------------------------|-----------------|
| Codigo derivado de OpenCode | Si | No — 100% propio |
| Tamano del binario | ~40-50MB (Bun standalone) | ~5-15MB |
| Runtime requerido | Bun incluido en el binario | Ninguno |
| Velocidad de arranque | ~300-500ms | < 100ms |
| Dependencia del upstream | Si (merges mensuales) | Ninguna |
| Tiempo de construccion | Semanas (ya existe la base) | Meses (desde cero) |
| Flexibilidad de UX | Limitada por opentui | Total |

**Criterios de aceptacion para esta fase:**
- El binario TUI Rust corre en macOS aarch64, macOS x86_64, Linux x86_64 y Windows x64
- El binario pesa menos de 20MB
- Cold start menor a 100ms
- Todas las pantallas del fork replicadas con paridad funcional
- El servidor Hono no requiere ningun cambio para soportar el nuevo cliente
- El fork de OpenCode se mantiene como cliente alternativo (desktop/web) en paralelo

**Relacion con el fork durante esta fase:**

```
Servidor Hono (fork OpenCode)   ← sin cambios
        |
        |── TUI fork SolidJS    (clientes desktop, web, usuarios no-terminal)
        |
        └── TUI Rust propio     (desarrolladores, entornos enterprise sin runtime)
```

Ambos clientes coexisten consumiendo el mismo backend. La migracion es gradual.

---

## 8. Criterios de aceptacion globales

El sistema se considera production-ready para Fase 1 cuando:

| Criterio | Como se verifica |
|----------|-----------------|
| Un FR de Alemana (stack Java) completa el ciclo end-to-end via TUI | Demo en vivo con el equipo |
| El aislamiento multi-tenant no tiene fugas de datos | Test automatizado en CI |
| El binario TUI instala y corre en macOS Apple Silicon sin dependencias | Verificado en maquina limpia |
| Los interrupts de aprobacion funcionan sin perdida de estado | Test con sesion interrumpida y retomada |
| Los datos de Alemana nunca pasan por modelos externos en tareas sensibles | Audit de logs de LangSmith |
| El tiempo de arranque del TUI es menor a 200ms | Medido con `hyperfine` |
| El primer ciclo de fine-tuning produce un modelo con eval_score mayor al base | Reporte del evaluator |
| La telemetria muestra tokens y costo estimado real de al menos una semana de uso | Dashboard TUI con datos reales |
| Ningun training sample con has_sensitive llega a un job de fine-tuning | Test automatizado en CI |

---

## 9. Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigacion |
|--------|-------------|---------|------------|
| El puente LangGraph <-> HTTP introduce latencia inaceptable | Media | Alto | Profiling temprano en TASK-API-005. Usar `asyncio` nativo. |
| La reconexion SSE pierde eventos durante interrupciones de red | Media | Alto | Implementar Last-Event-ID y buffer de eventos en DB desde el inicio |
| Cross-compilation de Rust falla en alguna plataforma | Baja | Medio | Verificar en CI desde TASK-INFRA-002 con `cross` o GitHub Actions runners nativos |
| El RAG de un proyecto "contamina" queries de otro | Baja | Critico | Test de aislamiento desde TASK-API-007. RLS en PostgreSQL como fallback |
| Costo de Claude API supera lo proyectado al escalar | Media | Medio | Rate limiting por org desde TASK-API-002. Monitoring de tokens en LangSmith |
| El estado del grafo LangGraph se corrompe si el proceso muere | Media | Alto | Usar `AsyncPostgresCheckpointer` desde el inicio. El estado survives reinicios |
| El modelo fine-tuned degrada la calidad respecto al base | Media | Alto | Evaluacion automatica obligatoria antes de activacion. Fallback al base siempre disponible |
| El detector de datos sensibles produce falsos negativos | Media | Critico | Curacion humana obligatoria como segunda linea. Auditorias periodicas del detector |
| Un job de fine-tuning consume toda la GPU e impacta las sesiones activas | Media | Alto | Trainer en proceso separado con prioridad baja. Jobs solo en horario de baja carga o RunPod |
| La telemetria introduce latencia en el path critico de una sesion | Baja | Medio | Instrumentacion asincrona (fire-and-forget). El API Layer no espera confirmacion del collector |
| El costo de fine-tuning en RunPod supera el ahorro en Claude API | Baja | Medio | Calcular ROI antes de cada job: tokens ahorrados proyectados vs costo GPU. Visible en dashboard |
| Incumplimiento de la licencia Apache 2.0 (perder copyright headers) | Baja | Medio | Checklist de compliance en cada release (seccion 2.6). Linter de copyright en CI |
| Conflicto de marca si se distribuye con el nombre "OpenCode" | Media | Alto | Definir nombre comercial propio antes de Fase 3. Verificacion de nombre en CI de release |
| Divergencia excesiva del upstream hace dificil incorporar mejoras de OpenCode | Media | Medio | Mantener rama `upstream/dev` sincronizada mensualmente. Minimizar cambios en archivos del core que no sean extensiones |
| Iniciar Fase 5 (TUI Rust) antes de que el producto este validado comercialmente | Media | Alto | La Fase 5 es opcional y condicionada a criterios de negocio explicitos. No iniciar por preferencia tecnica sino por necesidad real |
| El MCP server de Oracle accidentalmente conecta a produccion | Baja | Critico | Constraint de red en Docker: el contenedor oracle-mcp solo puede resolver hostnames de dev. Verificado en cada deploy |
| El LLM filtra credenciales de Oracle en su respuesta | Baja | Alto | Las credenciales nunca pasan por el LLM — el MCP server las gestiona internamente. El LLM solo recibe el resultado de la query |
| Un skill mal definido lleva al agente a tomar decisiones incorrectas en produccion | Media | Alto | Los skills se versionan y revisan como codigo. Cambios en skills de legacy-java requieren aprobacion del arquitecto |

---

## 10. Glosario

| Termino | Definicion |
|---------|-----------|
| OVD | Oficina Virtual de Desarrollo — sistema multi-agente LangGraph existente |
| FR | Feature Request — solicitud de desarrollo en lenguaje natural |
| SDD | Spec-Driven Development — metodologia que genera specs antes de codigo |
| TUI | Terminal User Interface — interfaz de usuario en terminal |
| SSE | Server-Sent Events — protocolo HTTP para streaming unidireccional servidor → cliente |
| RLS | Row-Level Security — seguridad a nivel de fila en PostgreSQL |
| RAG | Retrieval-Augmented Generation — busqueda semantica sobre knowledge base |
| Multi-tenancy | Aislamiento de datos entre organizaciones en una misma instalacion |
| Interrupt | Punto de pausa en el grafo LangGraph que espera input humano |
| Checkpointer | Mecanismo de LangGraph para persistir estado del grafo y permitir resume |
| Namespace | Particion logica del RAG por proyecto |
| Thread ID | Identificador de una conversacion/sesion en LangGraph |
| cloud privado | Servidor dedicado bajo control de Omar Robles, sin SaaS publico |
| Skill | Archivo markdown en `.opencode/command/` que define instrucciones especializadas invocables con `/nombre` durante una sesion |
| MCP | Model Context Protocol — protocolo estandar para conectar LLMs con herramientas y fuentes de datos externas |
| MCP server | Servicio que expone tools al agente via MCP — en este proyecto: oracle-mcp, nats-mcp, confluence-mcp |
| Tool MCP | Funcion callable que el LLM puede invocar durante su razonamiento (ej: `query_oracle`, `publish_event`) |
| Agente custom | Agente definido en `opencode.jsonc` con modelo, prompt y permisos especificos para un rol en el proyecto |
| Oracle Wallet | Mecanismo de Oracle para almacenar credenciales cifradas sin exponerlas en texto plano |
| validate_sql_compat | Tool MCP que verifica si un SQL usa features no disponibles en Oracle 12c cuando el target incluye sede CAS |
| Apache 2.0 | Licencia open source permisiva que permite uso comercial, modificacion y redistribucion conservando avisos de copyright y patent grant |
| Fork | Copia independiente de un repositorio sobre la cual se desarrolla una variante propia |
| Upstream | El repositorio original (anomalyco/opencode) del cual se deriva el fork |
| Patent grant | Clausula de Apache 2.0 que protege al usuario del fork de demandas de patentes relacionadas con el codigo contribuido |
| NOTICE file | Archivo requerido por Apache 2.0 que lista atribuciones de terceros; debe preservarse en la distribucion |
| Disassociation | Declaracion explicita de que el producto no esta afiliado al proyecto original ni a sus autores |
| Fine-tuning | Proceso de re-entrenamiento de un modelo base usando datos especificos del proyecto para mejorar su desempeno en ese dominio |
| Training sample | Par input/output extraido de una sesion aprobada, usado como dato de entrenamiento |
| Curacion | Revision humana de training samples para aprobar o rechazar su inclusion en un job |
| Model registry | Catalogo de modelos fine-tuned por proyecto con versiones, metricas y estado de activacion |
| Benchmark | Conjunto de FRs historicos con respuesta esperada, usado para evaluar la calidad de un modelo |
| Routing A/B | Division de sesiones entre modelo base y modelo fine-tuned para comparacion en produccion |
| has_sensitive | Flag en training_sample que indica presencia de datos de pacientes u otros datos protegidos |
| eval_score | Puntuacion normalizada (0-1) del modelo en el benchmark del proyecto |
| unsloth | Framework Python de fine-tuning eficiente para GPU local (Mac M-series compatible) |
| axolotl | Framework Python de fine-tuning configurable, usado con RunPod para modelos grandes |
| OpenTelemetry | Estandar abierto para instrumentacion de observabilidad: trazas, metricas y logs |
| Span | Unidad de traza en OpenTelemetry que representa una operacion con duracion medida |
| Telemetria | Recoleccion automatica de metricas de uso, rendimiento y costo del sistema |
| TUI Rust propio | Version futura del cliente terminal escrita desde cero en Rust, sin codigo derivado de OpenCode, que consume el mismo backend Hono |
| opentui | Framework de OpenCode que permite correr una aplicacion SolidJS dentro del terminal |
| cross-compilation | Compilacion de un binario para una plataforma diferente a la del equipo de desarrollo (ej: compilar para Windows desde macOS) |

---

*Documento generado como artefacto SDD. Toda desviacion de este diseno debe ser revisada por el arquitecto antes de implementar.*

*v1.1 — se agrega fine-tuning pipeline completo (Capa 4), telemetria con OpenTelemetry, nuevas secciones, tasks TASK-FT-001/002/003/004 y TASK-TEL-001/002, actualizacion de Fase 2 y criterios de aceptacion.*

*v1.2 — se agrega seccion 2 completa de Estrategia de fork y licencia Apache 2.0: libertades, obligaciones, marca registrada, estrategia tecnica del fork y checklist de compliance.*

*v1.5 — se agrega seccion completa de extensibilidad: Skills (2.5), MCP servers y agentes custom (3.8), constraints MCP (4.8), tasks TASK-EXT-001/002/003/004, MCP servers en arquitectura y estructura de repo, riesgos y glosario.*

*v1.4 — se agrega Fase 5 (TUI propio en Rust): motivacion, criterios de activacion, stack tecnico, estructura de codigo, tabla comparativa vs fork SolidJS y modelo de coexistencia de clientes.*

*Proxima revision: al completar Fase 0 — actualizar con hallazgos del OVD Runner. Al completar Fase 1 — definir nombre comercial del producto y benchmark especifico del proyecto Alemana para el evaluator.*
