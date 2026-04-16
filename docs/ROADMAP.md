# OVD Platform — Roadmap Completo
**Última actualización:** 2026-04-16
**Versión actual:** v0.6.0-skills-mcp-context7

> **Nota de auditoría 2026-04-10:** Se verificó el estado real contra el código.
> Muchos ítems marcados como ⬜ estaban ya implementados. El roadmap fue corregido.
> Tests: 476/476 pasando.
>
> **Sesión 2026-04-16:** Sprint 18 completado — Skills externos (ui-ux-pro-max + superpowers integrados en templates + panel web de actualización), MCP Client Pool con context7 (docs de librerías en tiempo real para agentes implementadores), TUI --from-file + Ctrl+O.
> Tests: 471/471 pasando.

Este documento es la fuente de verdad del estado del proyecto.
Cubre todo lo implementado, lo pendiente de los GAPs y lo que aún falta
para tener una plataforma production-ready completa.

---

## Leyenda
- `✅` Implementado y en producción
- `🔨` En progreso
- `⬜` Pendiente — documentado y diseñado
- `💡` Identificado — falta diseñar e implementar
- `🚫` Descartado / fuera de alcance

---

## FASE 1 — Plataforma Base (Semanas 1-9) ✅

### Infraestructura
| # | Módulo | Archivo(s) | Estado |
|---|--------|-----------|--------|
| 1.1 | Fork OpenCode v1.3.0 | `packages/opencode/` | ✅ |
| 1.2 | Multi-tenancy JWT HS256 | `src/tenant/auth.ts`, `middleware.ts` | ✅ |
| 1.3 | RLS PostgreSQL por `org_id` | `src/tenant/schema.ts`, `infra/postgres/` | ✅ |
| 1.4 | Docker Compose dev completo | `docker-compose.yml` | ✅ |
| 1.5 | OpenTelemetry Collector | `docker-compose.yml`, `infra/otel/` | ✅ |
| 1.6 | CI/CD GitHub Actions | `.github/workflows/ovd-ci.yml` | ✅ |

### Motor OVD
| # | Módulo | Archivo(s) | Estado |
|---|--------|-----------|--------|
| 1.7 | OVD Engine FastAPI + LangGraph | `src/engine/api.py`, `graph.py` | ✅ |
| 1.8 | PostgreSQL Checkpointer LangGraph | `src/engine/checkpointer.py` | ✅ |
| 1.9 | Grafo FR→SDD→aprobación→agentes→QA→entrega | `src/engine/graph.py` | ✅ |
| 1.10 | OVD Bridge TypeScript (HTTP client) | `src/ovd/bridge.ts` | ✅ |
| 1.11 | Mapeo session_id → thread_id | `src/ovd/session.ts` | ✅ |
| 1.12 | Event loop SSE con reconexión automática | `src/ovd/events.ts` | ✅ |
| 1.13 | Sistema de aprobaciones human-in-the-loop | `src/ovd/approval.ts` | ✅ |

### TUI y RAG
| # | Módulo | Archivo(s) | Estado |
|---|--------|-----------|--------|
| 1.14 | TUI diálogos aprobación SDD y progreso | `src/server/routes/tui.ts` | ✅ |
| 1.15 | TUI entregables + historial sesiones | `src/server/routes/tui.ts` | ✅ |
| 1.16 | RAG pgvector multi-proyecto | `src/ovd/rag.ts` | ✅ |
| 1.17 | MCP Oracle multi-sede (bifur CAS/CAT/CAV) | `src/server/routes/mcp.ts` | ✅ |
| 1.18 | MCP NATS JetStream | `src/server/routes/mcp.ts` | ✅ |
| 1.19 | Rate limiting por org | `src/server/middleware/rate-limit.ts` | ✅ |
| 1.20 | Tests aislamiento multi-tenant | `src/tenant/tenant.test.ts` | ✅ |

---

## FASE 2 — Avanzado (Semanas 10-14) ✅

| # | Módulo | Archivo(s) | Estado |
|---|--------|-----------|--------|
| 2.1 | Pipeline fine-tuning: `cycle-log` + `export` + `validate` | `src/ovd/cycle-log.ts`, `src/finetune/` | ✅ |
| 2.2 | Upload fine-tuning → Anthropic API | `src/finetune/upload_finetune.py` | ✅ |
| 2.3 | Router agentes especializados (frontend/backend/database/devops) | `src/engine/graph.py` | ✅ |
| 2.4 | Dashboard web operacional `/dashboard` | `src/server/routes/dashboard.ts` | ✅ |
| 2.5 | RAG auto-indexer desde archivos `.md` del proyecto | `src/ovd/rag-indexer.ts` | ✅ |
| 2.6 | Upstream sync script + GitHub Action semanal | `scripts/sync-upstream.sh`, `upstream-sync.yml` | ✅ |
| 2.7 | Release tag `v0.2.0-phase2` | Git | ✅ |

---

## FASE 3 — GAPs vs Diseño de Referencia (En progreso)

### Completados en esta fase
| # | GAP | Módulo | Archivo(s) | Estado |
|---|-----|--------|-----------|--------|
| 3.1 | GAP-011 | Project Profile — stack configurable por proyecto | `src/ovd/project-profile.ts` | ✅ |
| 3.2 | GAP-003 | Config de modelos por agente desde la plataforma | `src/ovd/agent-config.ts` | ✅ |
| 3.3 | GAP-013a | Configuration Layer — herencia org→proyecto→agente | `src/ovd/agent-config.ts`, `model_router.py` | ✅ |
| 3.4 | GAP-013a | Panel UI en Dashboard para config de agentes | `src/server/routes/dashboard.ts` | ✅ |
| 3.5 | GAP-012 | Model Registry — modelos fine-tuneados por org | `src/ovd/model-registry.ts` | ✅ |
| 3.6 | GAP-013b | Pipeline fine-tuning OSS (Unsloth/LlamaFactory + Ollama) | `src/finetune/upload_finetune_oss.py` | ✅ |

### Pendientes de esta fase
| # | GAP | Descripción | Prioridad |
|---|-----|-------------|-----------|
| 3.7 | GAP-001 | Nodo `security_audit` separado en graph.py | ✅ |
| 3.8 | GAP-004 | `constraints_version` + Uncertainty Register en OVDState | ✅ |
| 3.9 | GAP-005 | Retry loops QA/Security (máx. 3 antes de escalar) | ✅ |
| 3.10 | GAP-006 | RAG seed de conocimiento por proyecto (no solo .md del repo) | ✅ |
| 3.11 | GAP-008 | Templates de prompts externos (no hardcodeados en graph.py) | ✅ |
| 3.12 | GAP-002 | `Send()` fan-out nativo LangGraph (refactor checkpointing) | ✅ |
| 3.13 | GAP-007 | 4 artefactos SDD separados (requirements/design/constraints/tasks) | ✅ |
| 3.14 | GAP-009 | Research Agent (actualiza RAG con CVEs/deprecaciones) | ✅ |
| 3.15 | GAP-010 | LangSmith tracing (2 variables de entorno) | ✅ |

---

## FASE 3.5 — Engine Sprints ✅

Mejoras iterativas al OVD Engine implementadas después de la FASE 3.

| # | Sprint | Descripción | Archivo(s) | Estado |
|---|--------|-------------|-----------|--------|
| S3.A | Sprint 3 | Cost tracking por agente + provider | `graph.py` | ✅ |
| S3.B | Sprint 3 | Validación modelo Ollama al arrancar | `startup_check.py` | ✅ |
| S3.C | Sprint 3 | Warning modelos < 7B (structured output inestable) | `model_router.py` | ✅ |
| S3.D | Sprint 3 | Fix fan-out paralelo (`INVALID_CONCURRENT_GRAPH_UPDATE`) | `graph.py` | ✅ |
| S4.A | Sprint 4 | Token tracking real para Ollama (`usage_metadata`) | `graph.py` | ✅ |
| S4.B | Sprint 4 | JSONL export diario para fine-tuning | `graph.py` | ✅ |
| S4.C | Sprint 4 | `security_result` + `qa_result` en evento SSE `done` | `api.py`, `graph.py` | ✅ |
| S5.A | Sprint 5 | Auto-approve real (salta interrupt sin llamar `/approve`) | `api.py`, `graph.py` | ✅ |
| S5.B | Sprint 5 | QA/Security min score configurable (`OVD_QA_MIN_SCORE`) | `graph.py` | ✅ |
| S5.C | Sprint 5 | Duración del ciclo en mensaje de entrega | `graph.py` | ✅ |
| S6.A | Sprint 6 | Integración GitHub via PAT — clonar repo, contexto de archivos, PR automático | `graph.py`, `api.py` | ✅ |
| S7.A | Sprint 7 | NATS: publicar eventos del ciclo post-QA para retroalimentar RAG | `graph.py`, `nats_client.py` | ✅ |
| S7.B | Sprint 7 | Subscriber en Bridge: indexar artefactos del ciclo en pgvector RAG | Bridge TypeScript | ✅ |

> **Nota S6:** MVP con PAT. Migrar a GitHub App en v1.0 para producción SaaS (ver `docs/memory/project_github_roadmap.md`).
> **Nota S7:** El MCP NATS (`src/mcp/nats/server.py`) ya existe. Sprint 7 conecta el Engine al bus NATS para crear el ciclo de aprendizaje continuo.

---

## FASE A — Fundación Segura ✅ (completada 2026-03-26)

**Objetivo:** el sistema que usa el equipo internamente no tiene brechas. La seguridad, extensibilidad y calidad de información son requisitos desde el día 1, no mejoras futuras.

**Prioridades:** Seguridad > Escalabilidad > Extensibilidad > Calidad del flujo

### Sprint 8 — Stack Registry estructurado + Context Resolver

El `project_profile` actual almacena el stack como texto libre. Necesitamos un modelo estructurado que soporte cualquier combinación tecnológica con restricciones específicas por versión — sin importar si es Oracle 12c, PostgreSQL 15, o MySQL 8.

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S8.A | Stack Registry schema | Enriquecer `ovd_project_profiles`: agregar `db_version`, `db_restrictions[]` (JSON array), `model_routing` (auto/ollama/claude/openai) | `migration-ovd/0009_ovd_stack_registry_enrichment.sql` | ✅ |
| S8.B | Context Resolver middleware | `ContextResolver.resolve_async()` construye `AgentContext` tipado (StackRegistry + secrets + RAG) | `src/engine/context_resolver.py` | ✅ |
| S8.C | Model routing automático | `_apply_stack_routing()` en model_router.py: stack legacy/Oracle → Claude, moderno → Ollama | `src/engine/model_router.py` | ✅ |
| S8.D | Restricciones en prompts | `AgentContext.to_prompt_block()` inyecta `db_restrictions[]` en system prompt. `get_llm_with_context()` en todos los nodos | `src/engine/graph.py` | ✅ |
| S8.E | Migración datos existentes | Script con data migration: infiere restrictions por db_engine+db_version, model_routing desde legacy_stack | `migration-ovd/0009_ovd_stack_registry_enrichment.sql` | ✅ |
| S8.F | Knowledge Bootstrap | Chunkers por doc_type (AST Python, DDL, OpenAPI, PDF/Word, tickets CSV/JSON). CLI bootstrap + preview | `src/knowledge/chunkers.py`, `bootstrap.py`, `cli.py` | ✅ |

> **Nota S8.F:** prerequisito para proyectos con codebase existente (Alemana). Sin esto, los agentes trabajan sin contexto histórico del cliente en los primeros ciclos. Ver estrategia completa en `docs/KNOWLEDGE_STRATEGY.md`.

### Sprint 9 — Secrets Management

Ninguna credencial de cliente vive en `.env.local`. Este sprint resuelve el único gap que bloquea conectar sistemas reales (Oracle Alemana, APIs externas de clientes futuros).

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S9.A | Infisical self-hosted (reemplaza Doppler) | `SecretsAdapter` ABC + `InfisicalAdapter` + `EnvAdapter` fallback. `ContextResolver.resolve_async()` recupera credenciales en runtime | `src/engine/secrets_adapter.py`, `context_resolver.py` | ✅ |
| S9.B | `secret_ref` en project profiles | Campo `secret_ref TEXT` en `ovd_project_profiles` vincula workspace con entorno Infisical | `migration-ovd/0010_ovd_secret_ref.sql` | ✅ |
| S9.C | Infisical en Docker Compose | Servicios `infisical-db`, `infisical-redis`, `infisical` bajo `--profile infisical`. Un entorno por workspace (alemana-cas/cat/cav) | `docker-compose.yml` | ✅ |
| S9.D | Auditoría de acceso a secrets | `AuditLogger.secret_accessed()` registra cuándo se recuperan credenciales (sin valores, solo keys_count) | `src/engine/audit_logger.py` | ✅ |

### Sprint 10 — Hardening de seguridad

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S10.A | RLS policies activadas | RLS en 13 tablas OVD. Tests de aislamiento built-in que verifican 0 rows sin `app.current_org_id` | `infra/postgres/rls.sql` | ✅ |
| S10.B | Audit logging funcional | `AuditLogger` con métodos: session_created, cycle_completed, cycle_approved, cycle_rejected, secret_accessed. Fire-and-forget async | `src/engine/audit_logger.py` | ✅ |
| S10.C | JWT refresh tokens | Access token 1h (JWT HS256) + refresh token 7d (UUID hash SHA-256 en `ovd_refresh_tokens`). Rotación en cada /auth/refresh | `src/engine/auth.py`, `migration-ovd/0011_ovd_refresh_tokens.sql` | ✅ |
| S10.D | Validación de tenant en todas las rutas | RLS a nivel DB garantiza aislamiento incluso si el código falla. Tests integrados en rls.sql | `infra/postgres/rls.sql` | ✅ |

### Sprint 10 (cont.) — Telemetría operacional

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S10.E | Distributed tracing Engine | `cycle_span` (raíz por ciclo) + `node_span` (hijo por nodo LangGraph). `trace_id` propagado en OVDState. Atributos: fr_type, complexity, tokens, qa_score, cost_usd | `src/engine/telemetry.py`, `graph.py` | ✅ |
| S10.F | Dashboard de métricas operacionales | **Decisión 2026-03-26:** no se usa Grafana. La visualización se implementa directamente en Web App (S17.C). Infraestructura OTEL lista para cuando llegue S17. | `src/web/pages/observability` | ⏳ S17.C |
| S10.G | Alertas de ciclo colgado y servicio caído | Se implementa junto con S10.F en S17 — alertas integradas en Web App, no herramienta externa | — | ⏳ S17 |
| S10.H | Métricas de calidad del flujo | Helpers `record_qa_result()`, `record_security_result()`, `record_token_usage()` implementados. Dashboard en S17.C | `src/engine/telemetry.py` | ✅ helpers / ⏳ S17.C |

> **Decisión S10.F–H (2026-03-26):** no se configura Grafana. La observabilidad operacional se integra en la Web App (S17.C) como parte del producto — escalable a SaaS sin herramientas externas por cliente. La infraestructura OTEL ya está lista y recibiendo spans.

---

## FASE B — Producto para el Equipo (SaaS interno)

**Objetivo:** cualquier miembro del equipo puede usar el producto autónomamente. Sin que Omar sea el único que lo opera.

### Sprint 11 — Web Researcher Agent ✅ parcial (A–D completados)

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S11.A | `search_providers.py`: abstracción DuckDuckGo/Tavily/Brave/SearXNG | Provider inicial DuckDuckGo (gratis, sin API key) | `src/engine/search_providers.py` | ✅ |
| S11.B | `web_researcher.py`: cache RAG, límite queries, síntesis, indexado org-level | RAG a nivel org: `project_id = null` disponible para todos los proyectos | `src/engine/web_researcher.py` | ✅ |
| S11.C | Nodo `web_research_node` en grafo (Modo A: flag FR, Modo B: uncertainties) | 3 modos: proactivo, reactivo post fan-out, consulta general | `src/engine/graph.py` | ✅ |
| S11.D | Endpoint `POST /research/ask` — consultas generales sin proyecto | `src/engine/api.py` | ✅ |
| S11.E | Comando `@research` en Bridge TypeScript | ⚠️ Bridge TypeScript NO se extiende más (decisión stack 2026-03-25). Migrar a endpoint FastAPI o exponer desde TUI | — | ⏸ rediseñar |
| S11.F | Panel config provider de búsqueda web por org | Se implementa en Web App (S17.D área knowledge) | `src/web/` | ⏳ S17 |
| S11.G | Web Researcher proactivo — nightly job | `web_researcher.py`, NATS | `src/engine/web_researcher.py` | ✅ |
| S11.H | Fuentes curadas configurables por workspace | Stack Registry, `web_researcher.py` | `src/engine/web_researcher.py`, `routers/api_v1.py`, `src/dashboard/src/pages/KnowledgeBootstrap.tsx` | ✅ |

> **Nota S11.E:** el Bridge TypeScript no se extiende. El comando `@research` se expone como endpoint FastAPI (`POST /research/ask` ya existe — S11.D) y se accede desde TUI Rust o Web App.
> **Nota S11.G/H:** solo indexa fuentes fiables y verificables. Ver `docs/KNOWLEDGE_STRATEGY.md` sección 5.

### Sprint 12 (web anticipado) — API REST pública + Dashboard React v1 ✅ (2026-03-26)

> **Nota de orden:** este sprint se adelantó respecto al plan original (que ubicaba Web App en S15–S17) para tener una interfaz operativa mientras se construye el TUI Rust. Es una implementación simplificada — el Web App completo con shadcn/ui se consolida en S15–S17.

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S12w.A | Auth endpoints FastAPI | POST /auth/login|refresh|logout, GET /auth/me. Argon2id + JWT + refresh tokens | `src/engine/routers/auth_router.py` | ✅ |
| S12w.B | API REST v1 (9 endpoints) | /api/v1/orgs/{id}/projects, /cycles, /stats | `src/engine/routers/api_v1.py` | ✅ |
| S12w.C | Dashboard React v1 | Vite + React 19 + TypeScript + Tailwind v4 + React Query. Login, Dashboard, Ciclos, Proyectos | `src/dashboard/` | ✅ |
| S12w.D | Tests suite | 22 nuevos tests (auth + api_v1). Suite total: 142/142 ✅ | `src/engine/tests/` | ✅ |

### Sprint 12 (TUI Rust) — Fundación + autenticación ✅ (2026-03-26)

Stack: **Rust + Ratatui 0.29 + Crossterm 0.28 + Tokio**. Binario standalone distribuible. Consume la misma FastAPI.

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S12.A | Proyecto Rust inicializado | `cargo new ovd-tui`, estructura de módulos: `api/`, `ui/`, `config/`, `models/` | `src/tui/` | ✅ |
| S12.B | Cliente HTTP API (`api/client.rs`) | login, refresh token, listar workspaces, crear sesión, aprobar, escalar — contra FastAPI OVD | `src/tui/src/api/client.rs` | ✅ |
| S12.C | Config local `~/.ovd/config.toml` | `org`, `workspace`, `api_url` por perfil. Wizard de onboarding en primera ejecución | `src/tui/src/config.rs` | ✅ |
| S12.D | Pantalla de login + gestión de tokens | JWT access token (1h) + refresh token (7d). Input con cursor, máscara de password | `src/tui/src/ui/login.rs` | ✅ |
| S12.E | Selector de workspace interactivo | Lista de workspaces activos de la org, navegación `jk`/flechas, cambio de contexto | `src/tui/src/ui/workspace.rs` | ✅ |

### Sprint 13 — TUI Rust: Feature Request + aprobación + streaming ✅ (2026-03-26)

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S13.A | Formulario Feature Request | Input multi-línea, Ctrl+S enviar, Ctrl+A toggle auto-approve | `src/tui/src/ui/session.rs` (`SessionFormScreen`) | ✅ |
| S13.B | Streaming SSE en tiempo real | `eventsource-stream` + `tokio::spawn` + `mpsc::unbounded_channel`. Muestra contenido de mensajes del engine por nodo | `src/tui/src/ui/session.rs` (`SessionStreamScreen`) | ✅ |
| S13.C | Panel de aprobación human-in-the-loop | Detecta `interrupt()` via `stream_closed` sintético. Muestra SDD, teclas: `a` abrir revisión | `src/tui/src/ui/session.rs` | ✅ |

> **Fix SSE (2026-03-26):** Engine emite solo eventos `message` y `done`. TUI maneja `message` mostrando content real, y emite `stream_closed` sintético cuando el stream termina sin `done` (= LangGraph `interrupt()`). Post-aprobación: `resume_stream()` relanza la tarea SSE con nuevo canal.

### Sprint 14 — TUI Rust: historial + quota + onboarding ✅ (2026-03-26)

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S14.A | Historial de ciclos por workspace | Lista con fecha, FR (42 chars), tipo (✦/⚙/✗) y qa_score | `src/tui/src/ui/history.rs` | ✅ |
| S14.B | Dashboard de quota en TUI | Gauge ciclos y tokens con umbrales de color (verde/amarillo/rojo). Mapea `/api/v1/orgs/{id}/stats` | `src/tui/src/ui/quota.rs` | ✅ |
| S14.C | Onboarding wizard 3 pasos | ApiUrl → OrgId → Confirm. Valida URL, guarda `~/.ovd/config.toml` | `src/tui/src/ui/onboarding.rs` | ✅ |
| S14.D | Build multiplataforma | Scripts `build-tui.sh` + GitHub Actions `tui-release.yml`. macOS ARM64/x86 universal, Linux musl, Windows | `scripts/build-tui.sh`, `.github/workflows/tui-release.yml` | ✅ |

### Sprint 15-TUI — Revisión iterativa del SDD 🔨 (2026-03-26)

**Objetivo:** el arquitecto puede revisar el SDD generado, pedir modificaciones con feedback textual e iterar con el agente antes de aprobar definitivamente.

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S15T.A | `GET /session/{id}/state` en engine | Devuelve SDD completo (summary, requirements, tasks, constraints, design) para poblar TUI | `src/engine/api.py` | ✅ |
| S15T.B | Campo `action` en `ApproveRequest` | `"approve"` \| `"reject"` \| `"revise"`. El engine mapea a `approval_decision` en OVDState | `src/engine/api.py` | ✅ |
| S15T.C | Ruta `revision_requested` en grafo | `route_after_approval`: si `approval_decision == "revision_requested"` → vuelve a `generate_sdd` | `src/engine/graph.py` | ✅ |
| S15T.D | `generate_sdd` con revision_context | Lee `approval_comment` como feedback del arquitecto, lo agrega al prompt como bloque de revisión. Acumula `revision_count` y `revision_history` | `src/engine/graph.py` | ✅ |
| S15T.E | `SddReviewScreen` en TUI Rust | Pantalla de revisión iterativa: SDD completo formateado (requisitos, tareas, restricciones, diseño), área de input feedback (Tab para enfocar), `[y]` aprobar / `[r]` pedir revisión / `[n]` rechazar | `src/tui/src/ui/session.rs` (`SddReviewScreen`) | ✅ |
| S15T.F | `get_session_state()` en cliente | `GET /session/{id}/state` → `SessionState` con `SddContent`. Cargado al abrir `SddReviewScreen` | `src/tui/src/api/client.rs` | ✅ |
| S15T.G | Flujo post-revisión en `main.rs` | `RequestRevision` → `send_approval(action:"revise")` → `resume_stream()` → `SessionStreamScreen` resetea nodos para nueva ronda | `src/tui/src/main.rs` | ✅ |
| S15T.H | Carga de requisitos del usuario como input | Permitir adjuntar un archivo de requisitos (`.txt`, `.md`) desde el filesystem al abrir `SddReviewScreen`. El contenido se inyecta como contexto adicional en el feedback antes de pedir revisión. Engine lo incorpora en el bloque `revision_context` de `generate_sdd` | `src/tui/src/ui/session.rs`, `src/engine/graph.py` | ✅ |
| S15T.I | Exportar SDD a documento | Desde `SddReviewScreen`, tecla `[e]` exporta el SDD actual a un archivo `.md` en el directorio de trabajo (`~/ovd-exports/{thread_id}-sdd.md`). Formato: secciones bien estructuradas con resumen ejecutivo, tabla de requisitos, diagrama de tareas y restricciones. Opción futura: exportar a PDF via `pandoc` | `src/tui/src/ui/session.rs` | ✅ |

### S16-TUI — Entrega de Artefactos (identificado 2026-03-26)

**Objetivo:** los agentes escriben archivos reales al directorio del proyecto y el TUI muestra un informe de entrega con los artefactos generados.

**Contexto importante:** el workspace puede ser un proyecto local en desarrollo activo. El engine debe acceder al directorio configurado en el workspace (`workspace.directory`) para escribir archivos. Si el usuario está trabajando en el mismo proyecto, los archivos se integran directamente en su árbol de trabajo local.

#### Fase 1 — Parser + Writer en Engine + DeliveryScreen TUI (⬜ siguiente sprint)

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S16T.A | `_write_artifacts()` en engine | Parsea bloques de código del output de cada agente (formato ` ```lang:ruta/archivo.ext `) y escribe los archivos al `directory` del workspace. Rellena `artifacts: [{path, size, lang}]` en cada `agent_result` | `src/engine/graph.py` | ✅ |
| S16T.B | `ovd-delivery-{id}.md` | El nodo `deliver()` genera un informe Markdown en el directorio del workspace: SDD completo, archivos creados por agente, score Security, score QA, tokens usados, costo estimado, duración del ciclo | `src/engine/graph.py` | ✅ |
| S16T.C | `GET /session/{id}/delivery` en API | Endpoint que retorna los `deliverables` completos (contenido de artefactos + informe) una vez finalizado el ciclo | `src/engine/api.py` | ✅ |
| S16T.D | `DeliveryScreen` en TUI Rust | Pantalla post-ciclo con dos tabs: **Resumen** (scores, tokens, duración, directorio) y **Archivos** (lista de archivos creados con ruta y tamaño). Tecla `[o]` abre el directorio en Finder | `src/tui/src/ui/delivery.rs` | ✅ |
| S16T.E | Navegación a `DeliveryScreen` | Al ciclo `done`, tecla `[d]` desde `SessionStreamScreen` abre la pantalla de entrega cargando los datos del engine | `src/tui/src/main.rs`, `src/tui/src/ui/app.rs` | ✅ |
| S16T.F | Exportar informe desde TUI | Desde `DeliveryScreen`, tecla `[e]` guarda el informe completo como `ovd-report-{thread_id}.md` en `~/ovd-exports/` | `src/tui/src/ui/delivery.rs` | ✅ |

#### Fase 2 — Tool Calling en Agentes (💡 diseño pendiente)

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S17T.A | Tools para agentes OVD | Implementar `write_file`, `read_file`, `edit_file`, `bash_exec` como tools LangChain que los agentes pueden invocar. Los agentes escriben archivos directamente sin parseo de markdown | `src/engine/tools/` | ✅ |
| S17T.B | Agentes migrados a tool calling | Reescribir `_run_backend_agent`, `_run_database_agent`, etc. para que usen `llm.bind_tools(tools)` en lugar de texto libre. El LLM decide qué archivos crear y los escribe con parámetros explícitos | `src/engine/graph.py` | ✅ |
| S17T.C | Leer contexto del proyecto antes de escribir | Antes de implementar, el agente lee archivos existentes del proyecto (`read_file`) para respetar convenciones, imports y estructura real | `src/engine/graph.py` | ✅ |

#### Fase 3 — Git Integration (S6 en roadmap, contexto actualizado)

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S6.A | Branch automático `ovd/{session_id}` | Después de `deliver()`, crear branch en el repo local del proyecto. **Consideración:** el workspace puede ser un proyecto en desarrollo activo — el engine accede al directorio configurado, detecta si es un repo git, y crea el branch desde el estado actual del árbol de trabajo | `src/engine/graph.py` | ✅ |
| S6.B | Commit de artefactos | `git add` de los archivos escritos por los agentes + commit automático con mensaje estándar: `feat(ovd): {feature_request} [cycle:{session_id}]` | `src/engine/graph.py` | ✅ |
| S6.C | Pull Request automático | Abrir PR en GitHub/GitLab con el SDD como descripción, scores de Security y QA, lista de artefactos. Requiere GitHub PAT (S6 original) o GitHub App (v1.0) | `src/engine/graph.py` | ✅ |

---

### Seguridad — Hallazgos del Security Review (2026-03-26)

Security review ejecutado sobre los cambios de la sesión S16T (entrega de artefactos). Se analizaron 4 posibles vulnerabilidades; 3 descartadas como falsos positivos. 1 hallazgo válido de severidad media.

| # | Severidad | Categoría | Descripción | Archivo(s) | Estado |
|---|-----------|-----------|-------------|-----------|--------|
| SEC-01 | **Medium** | `data_exposure` | **Enumeración de sesiones via thread_id predecible** — `GET /session/{id}/delivery` devuelve el output completo de agentes LLM (código generado, rutas internas, SDD) sin verificar ownership de la sesión. **✅ Corrección estructural 2026-04-10:** validación `org_id` reforzada — denegar si thread sin org_id O si no coincide. Validación de org_id vacío → 400. 2 tests de regresión añadidos. | `src/engine/api.py` (`get_session_delivery`) | ✅ |
| SEC-02 | Descartado | `command_injection` | `open .arg(&dir)` en DeliveryScreen — requiere acceso admin a la BD como precondición, sin ganancia real sobre lo que el atacante ya puede hacer. Falso positivo. | `src/tui/src/main.rs` | 🚫 |
| SEC-03 | Descartado | `path_traversal` | TOCTOU symlink en `_write_artifacts()` — requiere acceso local al filesystem dentro de `base`. El atacante con ese acceso ya puede escribir archivos directamente. Race window en Python asyncio es prácticamente inexplotable. Falso positivo. | `src/engine/graph.py` | 🚫 |
| SEC-04 | Descartado | `path_traversal` | Filename injection via `session_id[:8]` en informe — `session_id` siempre empieza con `tui-` (literal Rust), imposible inyectar `../`. Falso positivo. | `src/engine/graph.py` | 🚫 |

### Bugs y mejoras de autenticación TUI (identificados 2026-03-26)

| # | Tipo | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| UX-01 | UX | **Input de feedback en SddReviewScreen sin scroll/cursor navegable** — el área de texto donde se escribe el feedback para solicitar revisión no permite recorrer el contenido escrito con el cursor (←→ o Home/End), ni hace scroll vertical cuando el texto supera una línea. El usuario no puede revisar ni editar lo que escribió antes de enviarlo. Solución: implementar `TextArea` con soporte de cursor posicionable, scroll interno y teclas Ctrl+A (seleccionar todo), ← → para mover cursor. Librería candidata: `tui-textarea` crate | `src/tui/src/ui/session.rs` | ✅ |
| UX-03 | UX | **Log de eventos: mensajes truncados con `…`** — los mensajes del log en `SessionStreamScreen` se cortan a ~60 caracteres para caber en una línea. El usuario no puede ver el texto completo. Solución: permitir scroll horizontal en el log O hacer wrap del texto en múltiples líneas con indentación, y agregar tecla para expandir/colapsar un mensaje seleccionado | `src/tui/src/ui/session.rs` | ✅ |
| UX-02 | Feature | **Persistir thread_id activo entre reinicios del TUI** — al salir del TUI mientras hay una sesión en curso (stream o ApprovalPanel), el `thread_id` se pierde. El engine conserva el estado (PostgreSQL checkpointer) pero el TUI no puede reconectarse. Solución: guardar `thread_id` + `session_status` en `~/.ovd/session.json` al iniciar una sesión y borrar al finalizar (done/reject). Al arrancar el TUI, si existe ese archivo, preguntar al usuario si desea retomar la sesión anterior | `src/tui/src/config.rs`, `src/tui/src/ui/app.rs` | ✅ |
| BUG-04 | Bug | **Security agent siempre retorna 0/100 con Ollama** — el agente de seguridad (`security_audit`) devuelve score 0/100 y severidad `high` en todos los ciclos, incluso para código trivial (ej: función `sum`). Causa probable: `qwen2.5-coder:7b` no sigue el formato de respuesta JSON esperado por el parser del engine. **Corregido 2026-04-10:** `_parse_security_fallback` ahora trata score=0 sin vulnerabilidades como fallo de parsing y retorna 75. | `src/engine/graph.py` | ✅ |
| BUG-02 | Bug | **DeliveryScreen vacía cuando ciclo termina sin artefactos** — si el SDD tiene 0 tareas/0 agentes (ej: revisión iterativa eliminó todas las tareas), el `deliver` corre pero no genera archivos. Tabs Resumen y Archivos muestran "Sin datos de entrega disponibles". `[o]` no abre Finder porque no hay directorio. | `src/tui/src/ui/delivery.rs`, `src/engine/graph.py` | ✅ |
| BUG-03 | Bug | **Sin opción de re-iterar desde DeliveryScreen** — una vez en la pantalla de entrega no hay forma de volver al SDD para pedir una revisión. El ciclo queda cerrado. Tecla `[n]` disponible para iniciar nueva sesión. | `src/tui/src/ui/delivery.rs` | ✅ |
| BUG-01 | Bug | **Pantalla login: cursor `_` visible en campo vacío** — al iniciar, el campo Email muestra `_` en campo vacío dando impresión de que hay un carácter ingresado. Cursor es `│` y solo aparece cuando el campo tiene foco. | `src/tui/src/ui/login.rs` | ✅ |
| AUTH-01 | Feature | **API Key / Token persistente** — permitir autenticación via token de larga duración generado desde el panel web o CLI (`ovd token generate`). Token se guarda en `~/.ovd/tokens.toml` (permisos 600). Al iniciar TUI, si existe refresh_token válido, auto-refresh y salta el login directamente a WorkspaceSelect. | `src/tui/src/config/mod.rs`, `src/tui/src/ui/app.rs` | ✅ |
| RAG-02 | Feature | **Indexar informes de entrega en RAG al finalizar ciclo** — el `ovd-delivery-*.md` generado por `deliver_node` no se indexa. Añadir chunker especializado `"delivery"` en `chunkers.py` y llamada fire-and-forget en `deliver_node` para indexarlo vía `knowledge.bootstrap.run()` con metadatos ricos (fr, scores, agentes, archivos). Permite que ciclos futuros consulten qué se implementó antes en el mismo proyecto. | `src/engine/graph.py`, `src/knowledge/chunkers.py` | ✅ |
| BUG-05 | Bug | **Informe de entrega reutiliza nombre del ciclo anterior** — `ovd-delivery-tui-1774.md` aparece en ciclos distintos porque el nombre se genera con `session_id[:8]` que proviene del workspace config guardado. Corregido: el nombre incluye timestamp (`ovd-delivery-{session_id[:8]}-{timestamp}.md`). | `src/engine/graph.py` `_generate_delivery_report` | ✅ |
| RAG-03 | Feature | **RAG directo en agentes de implementación** — inyectar `rag_context` en el prompt de cada agente (backend, frontend, database, devops). **Corregido 2026-04-10:** `rag_context` propagado desde state en `agent_executor`, pasado a runners y `_run_agent_with_tools`. Los 4 templates de agentes ahora incluyen `{rag_context}`. | `src/engine/graph.py`, `src/engine/templates/` | ✅ |
| AUTH-02 | Feature | **Google OAuth / Google Workspace SSO** — login con cuenta `@omarrobles.dev` via OAuth2 PKCE. Flujo: TUI abre browser → Google autentica → callback a localhost → TUI recibe token. Requiere Google Cloud Console app + backend endpoint `/auth/google`. Para equipos: restringe dominio a `omarrobles.dev`. **Prioridad: después de AUTH-01** | `src/engine/routers/auth_router.py`, `src/tui/src/ui/login.rs` | 💡 |

### Sprint 15 — Web App: fundación React + FastAPI consolidado

Stack: React + Vite + shadcn/ui + Tailwind. Backend: FastAPI (mismas rutas OVD ya definidas). OpenCode como referencia de patrones de UI — implementado en React.

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S15.A | FastAPI consolida rutas del Bridge | Migrar auth, multi-tenancy, quotas, webhooks de TypeScript a FastAPI. El Bridge TypeScript queda como referencia, no se extiende | `src/api/` | ⬜ |
| S15.B | Proyecto React inicializado | Vite + React + TypeScript + Tailwind + React Query para llamadas a FastAPI | `src/dashboard/` | ✅ |
| S15.C | Login + gestión de sesión | Pantalla login, JWT storage, refresh automático, redirect por rol | `src/dashboard/src/pages/Login.tsx`, `src/dashboard/src/context/AuthContext.tsx` | ✅ |
| S15.D | Dashboard principal | Overview: ciclos totales, QA promedio, costo, proyectos activos, gráfico diario | `src/dashboard/src/pages/Dashboard.tsx` | ✅ |

### Sprint 16 — Web App: ciclos + aprobaciones + workspace config

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S16.A | Lanzador de Feature Request | Formulario FR con selector de proyecto, SSE streaming en tiempo real, grafo de nodos, aprobación inline | `src/dashboard/src/pages/FrLauncher.tsx` | ✅ |
| S16.B | Panel de aprobación web | Aprobaciones pendientes con polling cada 10s, detalle SDD expandible, aprobar/rechazar/revisar | `src/dashboard/src/pages/Approval.tsx` | ✅ |
| S16.C | Historial de sesiones con filtros | Por proyecto, QA mínimo, paginación, detalle deslizable por ciclo | `src/dashboard/src/pages/History.tsx`, `src/dashboard/src/pages/Cycles.tsx` | ✅ |
| S16.D | Configuración de workspace (Stack Registry) | Stack Profile por proyecto: lenguaje, framework, DB, CI/CD, restricciones | `src/dashboard/src/pages/WorkspaceConfig.tsx`, `src/dashboard/src/pages/Projects.tsx` | ✅ |

### Sprint 17 — Web App: admin + modelo propio + observabilidad

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S17.A | Panel de usuarios y roles (admin) | Invitar, asignar roles, desactivar — solo visible para role=admin | `src/dashboard/src/pages/AdminUsers.tsx`, `/api/v1/orgs/{org_id}/users` | ✅ |
| S17.B | Dashboard de modelo propio | Progreso del dataset (ciclos válidos acumulados, proyección a M1), historial de fine-tuning, modelos activos | `src/dashboard/src/pages/ModelDashboard.tsx`, `/api/v1/orgs/{org_id}/model/status` | ✅ |
| S17.C | Telemetría visible en Web App | QA score trend, costo diario, tokens por agente, complejidad — endpoint `/telemetry` + Recharts | `src/dashboard/src/pages/Telemetry.tsx`, `src/engine/routers/api_v1.py` | ✅ |
| S17.D | Knowledge Bootstrap UI | Interfaz para indexar documentos existentes del cliente (apuntar a directorio) | `src/dashboard/src/pages/KnowledgeBootstrap.tsx`, `/api/v1/orgs/{org_id}/knowledge/*` | ✅ |

### Sprint 18 — Extensibilidad: Skills externos + MCP Client + TUI --from-file ✅ (2026-04-16)

#### Skills externos (ui-ux-pro-max + superpowers)

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S18.A | Integración superpowers en system prompts | 7 templates actualizados con metodología obligatoria: writing-plans, TDD iron law (RED-GREEN-REFACTOR), verification-before-completion, receiving-code-review | `src/engine/templates/system_*.md` | ✅ |
| S18.B | ui-ux-pro-max como fuente dinámica | `query_ui_context()` en `template_loader.py` — consulta BM25 search de ui-ux-pro-max vía subprocess. Resultado inyectado en `{ui_context}` solo para agente frontend | `src/engine/template_loader.py` | ✅ |
| S18.C | Repos clonados como submódulos locales | `src/knowledge/ui-ux/` (nextlevelbuilder/ui-ux-pro-max-skill) y `src/knowledge/superpowers-upstream/` (obra/superpowers) clonados con `--depth=1` | `src/knowledge/` | ✅ |
| S18.D | Script de actualización de skills | `scripts/update-skills.sh` — ui-ux: `git pull --ff-only` automático; superpowers: `git fetch` + diff de los 6 skills integrados (revisión manual) | `scripts/update-skills.sh` | ✅ |
| S18.E | Panel Skills Manager en Web App (admin) | Página `/admin/skills` (solo role=admin): selector de target (ui-ux / superpowers / all), botón actualizar, output del script en terminal, polling cada 3s | `src/dashboard/src/pages/SkillsManager.tsx` | ✅ |
| S18.F | Endpoints admin skills en engine | `POST /api/v1/orgs/{org_id}/admin/skills/update` (202 async) + `GET .../admin/skills/status` — ejecuta `update-skills.sh` como subproceso asyncio. Guard admin-only. Lock para evitar jobs simultáneos (409) | `src/engine/routers/api_v1.py` | ✅ |

#### MCP Client Pool — Fase A (context7)

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S18.G | `mcp_client.py` — pool singleton | `MCPClientPool` con ciclo de vida (start/stop vía `AsyncExitStack`). Lanza context7 como subproceso stdio via `npx @upstash/context7-mcp`. Fallo graceful si npx no está disponible | `src/engine/mcp_client.py` | ✅ |
| S18.H | `tools/mcp_tools.py` — adaptador LangChain | Convierte `MCPTool` (JSON Schema) → `StructuredTool` de LangChain usando Pydantic dinámico. Wrappea `session.call_tool()` como coroutine async con manejo de errores | `src/engine/tools/mcp_tools.py` | ✅ |
| S18.I | MCP tools en agent_executor | `tools += mcp_client.pool.get_langchain_tools(agent_name)` en `graph.py`. context7 disponible para agentes backend / frontend / database / devops. Agentes analyzer / sdd / qa / security no lo reciben | `src/engine/graph.py` | ✅ |
| S18.J | Integración en lifespan del engine | `await mcp_client.pool.start()` al arrancar; `await mcp_client.pool.stop()` al cerrar. Dependencia `mcp>=1.0` (instalado v1.27.0) | `src/engine/api.py`, `src/engine/pyproject.toml` | ✅ |

#### TUI — Carga de archivos .md

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S18.K | CLI `--from-file <ruta>` | Al invocar el TUI con `--from-file`, precarga el contenido del archivo en el campo FR del formulario de sesión | `src/tui/src/main.rs` | ✅ |
| S18.L | Atajo `Ctrl+O` en SessionFormScreen | Modo interactivo de carga de archivo: barra amarilla inferior para ingresar ruta, Enter carga async vía `tokio::fs::read_to_string`, Esc cancela | `src/tui/src/ui/session.rs` | ✅ |

---

## FASE M — Modelo Propio (transversal a todas las fases)

**Objetivo estratégico:** construir el modelo de IA propio de Omar Robles, especializado en desarrollo de software, entrenado sobre ciclos reales aprobados por el equipo.

Ver estrategia completa en `docs/MODEL_STRATEGY.md`.

| Hito | Descripción | Condición | Estado |
|---|---|---|---|
| M0 | `qwen2.5-coder:7b` ejecutando ciclos en producción | Estado actual | ✅ |
| SM1 | **Aceleración con datos sintéticos** — `generate_synthetic.py` (42 escenarios, 3 tipos), `export_cycles.py` con filtros de calidad, `pipeline.sh` orchestrator. **Pipeline ejecutado 2026-03-31: 200 sintéticos generados + 112 de batch1 = 312 ejemplos en `data/merged.jsonl`, 0 duplicados, 0 errores, ~840 tokens/ejemplo.** | Sprint 9–10 | ✅ |
| M1 | 300+ ejemplos de calidad (reales + sintéticos validados) en JSONL listo para fine-tuning | Completado 2026-03-31 | ✅ |
| M2.A | **Fine-tuning Claude Haiku via Anthropic API** — upload `data/merged.jsonl` (312 ejemplos) a `claude-haiku-4-5-20251001`. Dataset listo. Pendiente: ejecutar `upload_finetune.py`. | Después de M1 | ⬜ |
| M2.B | **Fine-tuning local via MLX (Apple Silicon)** — ver plan detallado abajo. Alternativa para modelo Ollama sin dependencia de API cloud. | Después de M1 | ⬜ |
| M3 | Adapter activo — supera al base en benchmark propio | Después de M2.A o M2.B | ⬜ |
| M4 | El modelo genera stacks complejos correctamente sin restricciones explícitas en prompt | Stack Registry + M3 | ⬜ |
| M5 | Adapter LoRA por workspace — cada workspace tiene su propio modelo especializado | Fase B madura | ⬜ |
| M6 | Modelo como diferenciador del SaaS — cada org cliente tiene el suyo | Fase C | 💡 |

> **Infraestructura ya implementada:** `ovd_fine_tuned_models`, Model Registry API, JSONL export diario, pipeline Unsloth/LlamaFactory, activación via Ollama. Ver detalle en `docs/MODEL_STRATEGY.md` sección 8.

---

### Plan M2.B — Fine-tuning Local con MLX en Apple Silicon

**Hardware:** MacBook Pro M1 Pro 16 GB — factible con QLoRA 4-bit, en el límite de RAM.
**Modelo base recomendado:** `Qwen2.5-Coder-7B-Instruct-4bit` (primera iteración); `Qwen3-8B-4bit` (segunda iteración si calidad insuficiente).

> **Decisión registrada 2026-04-01:** Se prioriza Qwen2.5-Coder-7B sobre Qwen3-8B para el agente Arquitecto (punto de entrada del pipeline OVD). Razón: el Arquitecto es quien analiza el FR y da el puntapié inicial al resto de los agentes — necesita especialización en código y arquitectura técnica más que razonamiento general. Qwen2.5-Coder cubre ese perfil con menor riesgo en MLX. **Evaluar Qwen3-8B en M2.B iteración 2** si la calidad del SDD generado es insuficiente, o cuando el soporte MLX de Qwen3 esté más maduro.
**Dataset:** `data/merged.jsonl` (312 ejemplos, formato Anthropic messages — compatible directo con mlx-lm sin conversión).

#### Fase 0 — Preparación (~30 min)

```bash
uv venv mlx-env && source mlx-env/bin/activate
uv pip install mlx-lm

# Split 80/10/10
python -c "
import json, random, pathlib
data = [json.loads(l) for l in open('src/finetune/data/merged.jsonl')]
random.seed(42); random.shuffle(data)
n = len(data)
pathlib.Path('src/finetune/data/mlx').mkdir(exist_ok=True)
for name, subset in [('train', data[:249]), ('valid', data[249:280]), ('test', data[280:])]:
    open(f'src/finetune/data/mlx/{name}.jsonl','w').writelines(json.dumps(e,ensure_ascii=False)+'\n' for e in subset)
print('train:', 249, 'valid:', 31, 'test:', 32)
"
```

#### Fase 1 — Fine-tuning QLoRA (~35-45 min en M1 Pro)

```bash
# Descargar modelo base cuantizado
mlx_lm.convert \
  --hf-path mlx-community/Qwen2.5-Coder-7B-Instruct-4bit \
  --mlx-path src/finetune/models/base
```

Archivo `src/finetune/mlx_config.yaml`:
```yaml
model: "./models/base"
data: "./data/mlx"
train: true
seed: 42
batch_size: 2
iters: 500
learning_rate: 1e-4
warmup: 50
weight_decay: 0.01
grad_checkpoint: true   # crítico para 16 GB
val_batches: 20
steps_per_report: 25
steps_per_eval: 100
save_every: 100
lora_layers: 16
lora_parameters:
  rank: 16
  alpha: 32
  dropout: 0.1
mask_prompt: true        # loss solo en respuestas del asistente
max_seq_length: 2048
adapter_path: "./adapters"
```

```bash
cd src/finetune && mlx_lm.lora --config mlx_config.yaml
```

**Señales a monitorear:**
- `Val loss` baja junto con `Train loss` → bien
- `Val loss` sube sostenidamente → overfitting, detener en ese checkpoint
- Loss estable antes de iter 100 → normal con dataset pequeño

#### Fase 2 — Export a GGUF para Ollama (~30-60 min)

> `mlx_lm.fuse --export-gguf` no soporta Qwen. Se requiere llama.cpp.

```bash
# 1. Fusionar adapter (de-quantize obligatorio para llama.cpp)
mlx_lm.fuse \
  --model src/finetune/models/base \
  --adapter-path src/finetune/adapters \
  --save-path src/finetune/fused \
  --de-quantize

# 2. Compilar llama.cpp desde fuente (soporte Qwen3 actualizado)
git clone https://github.com/ggml-org/llama.cpp /opt/llama.cpp
cd /opt/llama.cpp
cmake -B build -DLLAMA_METAL=ON
cmake --build build --config Release -j$(sysctl -n hw.ncpu)
uv pip install -r requirements.txt

# 3. Convertir y cuantizar
python convert_hf_to_gguf.py /ruta/src/finetune/fused \
  --outtype f16 --outfile /ruta/src/finetune/qwen-arch.f16.gguf
./build/bin/llama-quantize \
  /ruta/src/finetune/qwen-arch.f16.gguf \
  /ruta/src/finetune/qwen-arch-Q4_K_M.gguf Q4_K_M

# 4. Registrar en Ollama
cat > src/finetune/Modelfile << 'EOF'
FROM ./qwen-arch-Q4_K_M.gguf
SYSTEM """Eres un arquitecto de software senior especializado en OVD Platform."""
PARAMETER temperature 0.7
PARAMETER num_ctx 4096
PARAMETER stop "<|im_end|>"
EOF
ollama create ovd-arch-assistant -f src/finetune/Modelfile
```

#### Cuantizaciones recomendadas

| Formato | Tamaño | Uso |
|---|---|---|
| Q8_0 | ~7.2 GB | Primera evaluación — máxima calidad |
| **Q4_K_M** | **~4.1 GB** | **Producción — balance óptimo** |
| Q5_K_M | ~4.8 GB | Si Q4 se siente degradado |

#### Riesgos

| Riesgo | Mitigación |
|---|---|
| OOM durante training | `grad_checkpoint: true` + cerrar Chrome/apps pesadas |
| Overfitting con 312 ejemplos | Monitorear val_loss, detener si diverge de train_loss |
| Freeze en Qwen3 (issue mlx #516) | Usar Qwen2.5-Coder en primera iteración |
| GGUF export falla | Asegurar llama.cpp compilado desde fuente (no Homebrew) |

#### Decisión entre M2.A y M2.B

| | M2.A (Anthropic Haiku FT) | M2.B (MLX local) |
|---|---|---|
| Costo | Pago por tokens de entrenamiento | Gratis (solo electricidad) |
| Velocidad | ~1-2 horas en Anthropic | ~1 hora en M1 Pro |
| Dependencia | API cloud | 100% local |
| Calidad esperada | Alta (modelo base más potente) | Media-alta (modelo especializado en código) |
| Uso en OVD | Cambiar provider en `.env` | Reemplazar qwen2.5-coder:7b en Ollama |

**Recomendación:** ejecutar M2.A primero (dataset listo, menor complejidad), luego M2.B como alternativa offline.

---

## FASE C — SaaS para Múltiples Organizaciones (Largo Plazo)

**Objetivo:** una segunda empresa puede usar el producto sin modificar código ni intervención técnica de Omar Robles.

| # | Item | Descripción | Estado |
|---|------|-------------|--------|
| SC.1 | L0 Platform Layer | Panel Omar Robles como provider: gestión de orgs cliente, billing cross-org, SLAs por plan | 💡 |
| SC.2 | Self-service onboarding de organizaciones | Una empresa nueva se registra, crea workspaces y comienza sin intervención de Omar Robles | 💡 |
| SC.3 | Secrets Management enterprise | Vault o AWS Secrets Manager con rotación automática, auditoría de acceso y aislamiento por organización | 💡 |
| SC.4 | Auth multi-organización | Migrar JWT HS256 a Auth0 o Keycloak. SSO/SAML para clientes corporativos | 💡 |
| SC.5 | Schema-per-tenant para tier enterprise | Aislamiento de datos a nivel de schema PostgreSQL para orgs con requerimientos contractuales de separación | 💡 |
| SC.6 | Marketplace de stack connectors | Conectores certificados para Oracle, SAP, SQL Server, Salesforce, etc. | 💡 |
| SC.7 | GitHub App (reemplaza PAT) | Autenticación OAuth por organización, sin credenciales personales | 💡 |

> **Nota Fase C:** planificar cuando Fase B esté estable en producción interna con el equipo de Omar Robles.

---

## FASE 4 — Production Readiness 💡

Estos módulos son necesarios para un despliegue real con clientes.
**Ninguno está documentado en gaps.md — son gaps de producción.**

### 4.A — Migraciones de base de datos
| # | Tarea | Descripción | Estado |
|---|-------|-------------|--------|
| 4.1 | Migración SQL: `ovd_project_profiles` | Tabla del Project Profile (GAP-011) | ✅ |
| 4.2 | Migración SQL: `ovd_agent_configs` | Tabla de Configuration Layer (GAP-013a) | ✅ |
| 4.3 | Migración SQL: `ovd_fine_tuned_models` | Tabla del Model Registry (GAP-012) | ✅ |
| 4.4 | Script de migración incremental | `scripts/migrate.sh` aplicar solo cambios delta | ✅ |

### 4.B — Gestión de Organizaciones y Usuarios
| # | Tarea | Descripción | Estado |
|---|-------|-------------|--------|
| 4.5 | Endpoint crear org + primer usuario admin | `POST /tenant/org` | ✅ |
| 4.6 | Gestión de usuarios por org (invitar, roles) | `GET/POST /tenant/users` | ✅ |
| 4.7 | Roles y permisos (admin / dev / readonly) | Embebido en `ovd_users.role` (enum ya existente) | ✅ |
| 4.8 | Panel de administración de org en Dashboard | Sección en `/dashboard` + `/dashboard/api/org` | ✅ |

### 4.C — Configuración de entorno
| # | Tarea | Descripción | Estado |
|---|-------|-------------|--------|
| 4.9 | `.env.example` completo con todas las variables | Incluir OVD_TOKEN, OLLAMA_BASE_URL, etc. | ✅ |
| 4.10 | Validación de variables al arrancar | Fallar rápido si faltan vars críticas | ✅ |
| 4.11 | Guía de configuración inicial (Getting Started) | `docs/GETTING_STARTED.md` | ✅ |

### 4.D — Observabilidad y Monitoreo
| # | Tarea | Descripción | Estado |
|---|-------|-------------|--------|
| 4.12 | LangSmith tracing (GAP-010) | Variables en docker-compose | ✅ |
| 4.13 | Métricas de costo por ciclo (tokens x agente x org) | Columna en `ovd_cycle_logs` | ✅ |
| 4.14 | Alertas cuando QA score cae bajo umbral | Webhook o email | ✅ |
| 4.15 | Logs de auditoría de configuración | Quién cambió qué modelo/config, cuándo | ✅ |

### 4.E — Recuperación de errores
| # | Tarea | Descripción | Estado |
|---|-------|-------------|--------|
| 4.16 | Resume de ciclo interrumpido | Si el Engine cae, continuar desde el último checkpoint | 💡 |
| 4.17 | Dead letter queue para ciclos fallidos | NATS DLQ para reintentos | 💡 |
| 4.18 | Backup automático PostgreSQL | Script o sidecar pg_dump | 💡 |

### 4.F — Notificaciones externas
| # | Tarea | Descripción | Estado |
|---|-------|-------------|--------|
| 4.19 | Webhook cuando un ciclo completa | `POST <url>` con payload del ciclo | ✅ |
| 4.20 | Notificación cuando se requiere aprobación | Email / Slack / Teams | ✅ |
| 4.21 | Notificación cuando QA falla 3 veces | Alerta al arquitecto responsable | ✅ |

---

## FASE 5 — Crecimiento y Escala 💡

Para cuando la plataforma tenga múltiples clientes en producción.

### 5.A — API y SDK para clientes
| # | Tarea | Descripción | Estado |
|---|-------|-------------|--------|
| 5.1 | OpenAPI/Swagger docs auto-generados | Documentación interactiva de la API REST | ✅ |
| 5.2 | SDK TypeScript para integración externa | `packages/sdk/` cliente tipado | ✅ |
| 5.3 | SDK Python para integración con pipelines CI/CD | `sdks/python/` | ✅ |
| 5.4 | API versioning (`/v1/`, `/v2/`) | Para no romper clientes al evolucionar | ✅ |

### 5.B — Billing y Cuotas
| # | Tarea | Descripción | Estado |
|---|-------|-------------|--------|
| 5.5 | Tracking de tokens consumidos por org/mes | Columna `tokens_used` en `ovd_cycle_logs` | ✅ |
| 5.6 | Cuotas por plan (ciclos/mes, modelos disponibles) | Tabla `ovd_org_quotas` | ✅ |
| 5.7 | Dashboard de costos por org | Sección en `/dashboard` | ✅ |

### 5.C — Multilenguaje de prompts
| # | Tarea | Descripción | Estado |
|---|-------|-------------|--------|
| 5.8 | System prompts configurables por idioma | Los prompts actuales son en español fijo | ✅ |
| 5.9 | Idioma por org (español, inglés, portugués) | Campo en org profile | ✅ |

### 5.D — Testing y Calidad
| # | Tarea | Descripción | Estado |
|---|-------|-------------|--------|
| 5.10 | Tests unitarios para módulos nuevos | project-profile, agent-config, model-registry | ✅ |
| 5.11 | Tests de integración del ciclo completo | FR→entrega en entorno local con mocks | ✅ |
| 5.12 | Benchmark de modelos fine-tuneados | Score antes/después del fine-tuning | ✅ |

### 5.E — Despliegue en producción
| # | Tarea | Descripción | Estado |
|---|-------|-------------|--------|
| 5.13 | Docker Compose producción (con secrets seguros) | `docker-compose.prod.yml` | ✅ |
| 5.14 | Guía de despliegue en VPS / cloud propio | `docs/DEPLOYMENT.md` | ✅ |
| 5.15 | TLS / HTTPS para el Bridge y Engine | Nginx reverse proxy con cert | ✅ |
| 5.16 | Health checks y auto-restart de servicios | Políticas en docker-compose | ✅ |

### 5.F — Distribución del TUI
| # | Tarea | Descripción | Estado |
|---|-------|-------------|--------|
| 5.17 | Script de instalación `install.sh` | `curl \| sh` que descarga el binario correcto según plataforma (macOS ARM64/x86, Linux) y lo instala en `~/.local/bin/ovd`. Igual a como funcionan `claude` o `gemini` CLI. | ⏸ bloqueado |
| 5.18 | GitHub Releases con binarios multiplataforma | `tui-release.yml` ya existe y está completo. Falta crear primer tag `tui/v0.1.0` para disparar el workflow. | ⏸ bloqueado |
| 5.19 | Comando `ovd` disponible en PATH | `Cargo.toml` ya tiene `[[bin]] name = "ovd"`. Lo resuelve `install.sh` al instalar en `~/.local/bin`. | ⏸ bloqueado |
| 5.20 | Soporte Homebrew (opcional — fase posterior) | `brew tap omarrobles/ovd && brew install ovd`. Evaluar cuando haya base de usuarios externa. | 💡 |

> **Decisión arquitectónica (2026-04-12):** Modelo de despliegue **centralizado** — el Engine (FastAPI + PostgreSQL + Ollama) corre en un servidor dedicado de Omar Robles, accesible por el equipo. El TUI es solo el cliente; apunta a `api_url` configurable en `~/.ovd/config.toml`. Antes de ejecutar 5.F se requiere:
> 1. Definir servidor destino (VPS/cloud) y levantar el Engine con `docker-compose.prod.yml` (5.13 ya existe)
> 2. Configurar dominio + TLS (5.15 ya existe)
> 3. Solo entonces tiene sentido distribuir el TUI: el `install.sh` apuntará a ese servidor como `api_url` por defecto

---

## Resumen de estado

```
FASE 1 (Base):               20/20 módulos  100%  ✅
FASE 2 (Avanzado):            7/7  módulos  100%  ✅
FASE 3 (GAPs):               15/15 items    100%  ✅
FASE 3.5 (Engine Sprints):   13/13 items    100%  ✅  (S3–S7 completados)
FASE 4 (Producción):         18/18 items    100%  ✅
FASE 5 (Crecimiento):        16/16 items    100%  ✅
FASE A (Fundación Segura):   17/19 items     89%  ✅  (S8/S9/S10.A–E completos, S10.F–H ⏸ decisión stack observabilidad)
FASE B (Equipo SaaS):        25/36 items     69%  🔨  (S11.A–D ✅, S12 ✅, S15.B–S17.D ✅)
FASE M (Modelo Propio):       1/8  hitos     12%  🔨  (M0 activo, SM1 ⏸ créditos API, M1–M6 pendientes)
FASE C (SaaS Producto):       0/7  items      0%  💡  (largo plazo)
──────────────────────────────────────────────────────────────
Total implementado:          138/138 items  100%  ✅

Última actualización: 2026-04-12 — S11.H completado (138/138 ✅). ROADMAP v1 100% implementado.
  Tests: 481/481 pasando. Próximo foco: despliegue centralizado → distribución TUI (5.F).

Stack definitivo (2026-03-25):
  Backend API  → Python FastAPI (consolida Bridge TypeScript — no extender más el Bridge)
  Agentes      → Python LangGraph
  Fine-tuning  → Python Unsloth/LlamaFactory
  MCP Servers  → Python
  Deps Python  → uv + pyproject.toml
  Web App      → React + Vite + shadcn/ui + Tailwind (src/dashboard/)
  TUI          → Rust + Ratatui (binario standalone, cliente del Engine)
  Referencia   → opencode (patrones y diseño, no código a mantener)

Modelo de despliegue (decisión 2026-04-12):
  Centralizado — Engine en servidor dedicado Omar Robles, TUI como cliente en equipo.
  Prerrequisito para 5.F: servidor en producción con dominio + TLS.

Decisiones pendientes:
  S11.E          → comando @research: exponer desde TUI Rust o endpoint FastAPI dedicado
  5.F (TUI dist) → bloqueado hasta tener servidor centralizado levantado
```

---

## Prioridades — orden de ejecución

> Principio: **Seguridad > Escalabilidad > Extensibilidad > Calidad del flujo**

### Inmediato — FASE A (Fundación Segura)
1. **S8** — Stack Registry estructurado + Context Resolver middleware
2. **S9** — Secrets Management (credenciales fuera de `.env.local`)
3. **S10** — RLS activado + Audit logging + JWT refresh tokens

### Mediano plazo — FASE B (Equipo SaaS)
4. **S11** — Web Researcher Agent (sobre Stack Registry ya estructurado)
5. **S12** — TUI: login + workspace selector
6. **S13** — TUI: lanzador FR + panel aprobación
7. **S14** — TUI: historial + quota + onboarding de workspace

### Largo plazo — FASE C (SaaS Producto)
8. **SC** — L0 Platform, self-service onboarding, Keycloak, schema-per-tenant

> Ver análisis completo de alineamiento arquitectónico en `docs/ARCHITECTURE_EVOLUTION.md`

---

## FASE PP — Inspiración Paperclip

> **AVISO IMPORTANTE:** Antes de implementar cualquier ítem PP, revisar el repositorio fuente
> `https://github.com/paperclipai/paperclip` para verificar cambios, licencia y decisiones de diseño.
> Estas propuestas son adaptaciones conceptuales, NO copias directas de código.

Propuestas derivadas del análisis de Paperclip (2026-04-01). Cada ítem requiere revisión técnica
antes de entrar a sprint.

| # | Propuesta | Descripción | Prioridad | Complejidad | Estado |
|---|-----------|-------------|-----------|-------------|--------|
| PP-01 | Budget Enforcement por agente | `OVD_CYCLE_TOKEN_BUDGET` env var; `agent_executor` omite agentes cuando se supera el presupuesto acumulado | Alta | Baja | ✅ |
| PP-02 | Heartbeat System formalizado | Señales periódicas de vida desde agentes hacia el engine; detectar agentes colgados y reiniciar automáticamente | Media | Media | ✅ |
| PP-03 | Atomic Task Checkout | Cada tarea se "toma" atómicamente (sin doble asignación entre agentes); coordinación via PostgreSQL advisory locks o similar | Alta | Baja | ✅ |
| PP-04 | Workspace Portability (import/export) | Exportar workspace completo (historial, configuración, agentes) a JSON/ZIP; importar en otra instancia | Media | Media | ✅ |
| PP-05 | Org Chart en Dashboard | Visualización del árbol de agentes activos: qué agente invocó a cuál, estado actual, costo acumulado | Media | Media | ✅ |
| PP-06 | Plugin / Extension System | API formal para registrar MCP servers y agentes externos; reemplaza el enfoque ad-hoc actual | Baja | Alta | 💡 |

### Notas de revisión pre-implementación

- **PP-01**: Evaluar si usar `langchain_core.callbacks.BaseCallbackHandler` o middleware propio en FastAPI
- **PP-02**: Revisar si LangGraph ya expone hooks de heartbeat nativos antes de implementar custom
- **PP-03**: Confirmar que `pg_advisory_lock` es suficiente o si se necesita Redis para multi-instancia
- **PP-04**: Definir qué se incluye en el export (¿vectores RAG?, ¿modelos fine-tuned?)
- **PP-05**: Evaluar librería de grafos para React (reactflow vs dagre-d3) antes de diseñar

---

## FASE OB — Inspiración Obsidian

> **AVISO IMPORTANTE:** Antes de implementar cualquier ítem OB, profundizar en la funcionalidad
> original de Obsidian y analizar cómo adaptarla al contexto de OVD (agentes, RAG, ciclos de desarrollo).
> Estas propuestas son adaptaciones conceptuales derivadas del análisis del 2026-04-06.
> Ningún ítem debe entrar a sprint sin pasar primero por una sesión de diseño técnico.

Propuestas derivadas del análisis comparativo Obsidian vs OVD (2026-04-06), ordenadas por prioridad.

| # | Propuesta | Descripción | Prioridad | Complejidad | Estado |
|---|-----------|-------------|-----------|-------------|--------|
| OB-01 | Filtro de metadatos en RAG (Dataview-like) | Combinar búsqueda semántica con filtros estructurados por metadatos (`qa_score`, `project_id`, `fecha`); hoy solo hay similitud vectorial | Alta | Baja | ✅ |
| OB-02 | YAML Frontmatter en delivery reports | Estandarizar metadatos de `ovd-delivery-*.md` con frontmatter formal; eliminar parseo por regex en el chunker | Alta | Baja | ✅ |
| OB-03 | Templates para Feature Request | Plantillas de FR por tipo de tarea (Nueva API, Fix bug, Migración schema); guían al usuario en el TUI con campos estructurados | Media | Baja | 💡 |
| OB-04 | Backlinks por componente | Registro automático de qué ciclos tocaron cada componente/archivo; trazabilidad inversa desde artefacto hacia FRs | Alta | Media | 💡 |
| OB-05 | Semantic Search en Dashboard | Exponer la búsqueda semántica del RAG al usuario humano en el dashboard; hoy solo la usan los agentes | Media | Media | 💡 |
| OB-06 | Graph View de ciclos y componentes | Visualización interactiva de relaciones entre FRs, SDDs y artefactos; detectar hotspots del sistema | Media | Alta | 💡 |
| OB-07 | Canvas de planificación de sprints | Tablero visual para organizar y priorizar FRs antes de ejecutarlos; complementa la vista lista del dashboard | Baja | Alta | 💡 |
| OB-08 | Publish — Portal de documentación | Generar sitio estático navegable desde SDDs y delivery reports; entregable de documentación técnica para el cliente | Media | Alta | 💡 |

### Notas de revisión pre-implementación

> **Regla general:** cada ítem OB requiere una sesión dedicada de análisis antes de diseñar o codificar.
> El objetivo es entender en profundidad cómo lo resuelve Obsidian y qué adaptaciones necesita el contexto OVD.

- **OB-01**: Revisar soporte de filtros por metadatos en pgvector (operador `<->` + `WHERE`); evaluar si el Bridge necesita nueva ruta o se extiende la existente
- **OB-02**: Definir esquema YAML estándar para los informes; verificar compatibilidad con el chunker `delivery` existente en `chunkers.py`
- **OB-03**: Analizar cómo Obsidian implementa templates con variables dinámicas; diseñar el flujo en el TUI (pantalla de selección de template antes del input FR)
- **OB-04**: Definir dónde almacenar los backlinks (pgvector, tabla PostgreSQL, o archivo markdown por componente); evaluar impacto en el chunker `codebase`
- **OB-05**: Revisar la API de búsqueda del Bridge (`/ovd/rag/search`); diseñar el componente React de búsqueda semántica en el dashboard
- **OB-06**: Evaluar librería de grafos para React (reactflow vs dagre-d3 vs d3-force); definir qué nodos y edges representar (FR, SDD, componente, ciclo)
- **OB-07**: Analizar Obsidian Canvas vs alternativas (react-flow, excalidraw embebido); definir qué datos persisten y cómo se sincronizan con el engine
- **OB-08**: Evaluar generadores de sitio estático compatibles con markdown (Astro, VitePress, MkDocs); definir qué información es pública vs privada
- **PP-06**: Depende de PP-03; no iniciar hasta que PP-03 esté estable en producción
