# OVD Platform — Roadmap Completo
**Última actualización:** 2026-05-04
**Versión actual:** v0.9.5-qa-contextual

> **Nota de auditoría 2026-04-10:** Se verificó el estado real contra el código.
> Muchos ítems marcados como ⬜ estaban ya implementados. El roadmap fue corregido.
> Tests: 476/476 pasando.
>
> **Sesión 2026-04-16:** Sprint 18 completado — Skills externos (ui-ux-pro-max + superpowers integrados en templates + panel web de actualización), MCP Client Pool con context7 (docs de librerías en tiempo real para agentes implementadores), TUI --from-file + Ctrl+O.
> Tests: 471/471 pasando.
>
> **Sesión 2026-04-23 — S43 completado + Prueba end-to-end + S45 planificado:**
> - **Prueba S43+:** Ciclo completo "Sistema Contratos y Beneficios" — 4 agentes, qwen3-coder:30b, ~80 min, QA=65/100, 16/22 tests passed.
> - **6 gaps identificados** (GAP-T1 a GAP-T6): RUT incorrecto en tests, React en vez de Angular, devops en código Python, Oracle mal configurado, import chain roto, sin requirements.txt.
> - **S45 planificado:** Fix `session_create` (cargar `constraints` de BD), refuerzo RUT enforcement, checklist archivos requeridos en template backend.
> - **S44 planificado:** MCP Server Manager — administración dinámica de servidores MCP y credenciales desde dashboard.
> - Tests: 847 (S43 completado, S45 pendiente).
>
> **Sesión 2026-04-22 — S27 + S28 — fixes de calidad y routing de agentes:**
> - **S27-A:** `run_tests` inyecta `conftest.py` con `sys.path.insert` si está vacío o no existe.
> - **S27-B:** `audit_logger` serializa metadata como `json.dumps()` (psycopg3 no adapta dict a JSONB automáticamente).
> - **S27-C:** `_index_delivery_report` agrega `src/` a `sys.path` antes de importar `knowledge` (fix RAG-02).
> - **S27-D:** `system_qa.md` con cláusula de infraestructura en criterio de aprobación (conftest.py vacío no invalida compliance, M≥N tests es correcto).
> - **S28-A:** `system_sdd.md` con tabla de asignación de agentes — prohíbe explícitamente `devops` para FRs sin infraestructura. Fix raíz de contaminación fan-out.
> - **S28-C:** `run_tests` — eliminados flags `-v`/`-q` en conflicto, diagnósticos explícitos de exit codes 4/5/2 de pytest.
> - **C10 documentado** en ROADMAP como bloqueante P0 pre-producción: Stack Profile por proyecto (`test_command`, `build_command`, `lint_command`) para que el engine sea agnóstico al lenguaje.
> - Tests totales: 666 (Python unit ~666 + integration 14 + docker 5 | Frontend Vitest 34 | Rust 26)
>
> **Sesión 2026-04-21 — Visión + Dashboard (S21) + Calidad/Docs planificado (S22):**
> - **S21 Vision:** nodo `describe_image` + `_build_fr_content` + `OVD_VISION_ENABLED`, `OVD_VISION_MODEL`. Drop zone + preview + paste (⌘V) en FrLauncher.tsx. Tests `test_vision.py` (8 tests).
> - **S21 Dashboard SSE fix:** eliminado campo `event:` en `_make_sse_event` — todos los eventos disparan `onmessage`. `stream_mode=["values","updates"]` para emitir `node_end` por nodo completado.
> - **S21 Panel SDD completo:** `pending_approval` muestra requisitos, criterios de aceptación, tareas y `revision_count`. Toggle Ver/Ocultar SDD.
> - **S21 Grafo OVD indicators:** `NODE_ALIAS` + handler `node_end` actualiza nodos waiting→running→done en tiempo real.
> - **S21 Panel aprobación completo:** feedback textarea + `action: "revise"` + adjuntar archivo (FileReader, max 4000 chars, bloquea rutas sensibles) + badge Revisión #N + exportar SDD como .md (client-side).
> - **S22 planificado:** nodo `run_tests` (entre qa_review y request_approval), security scanning CLI (pip-audit/npm audit/gitleaks/semgrep extendiendo security_audit), nodo `generate_docs` (entre request_approval y deliver).
>
> **Sesión 2026-04-17 — Production Readiness (S19):**
> - **Suite de tests A→E completa:** Block A Python unit (77 tests), Block B integration Alembic (14), Block C Vitest frontend (34/34), Block D Docker smoke (5, @docker), Block E Rust inline (26 nuevos, 63/63 total)
> - **CORS:** `CORSMiddleware` en engine con `OVD_CORS_ORIGINS` configurable por env — separa dev (localhost:5173) de prod (dominio real)
> - **RAG multi-provider:** `rag.py` con switch `OVD_RAG_EMBEDDING_PROVIDER=ollama|openai`. OpenAI `text-embedding-3-small` como default en prod — resuelve bloqueante C02 para VPS sin GPU
> - **docker-compose.prod.yml:** servicio `ovd-backup` (pg_dump diario, gzip, retención 30 días), secret `openai_api_key`, vars `OVD_CORS_ORIGINS` + `OVD_EMBED_MODEL`
> - **docker-entrypoint.sh:** carga secret `openai_api_key` → `OPENAI_API_KEY`
> - **README.md:** reescritura completa — guía de onboarding para nuevos integrantes (arquitectura, setup paso a paso, variables de entorno, primer ciclo, troubleshooting)
> - **GAPs de FASE 5 resueltos en código:** C02.B, C03.A, C04.A/B/C, C05.A/B/C, C07.B, C09.D
> - Tests totales: Python unit 548 + integration 14 + docker 5 | Frontend Vitest 34 | Rust 63

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

### Sprint 19 — Production Readiness ✅ (2026-04-17)

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S19.A | Tests Block C — Frontend Vitest | `Approval.test.tsx` y `Telemetry.test.tsx` corregidos — 34/34 pasando | `src/dashboard/src/` | ✅ |
| S19.B | Tests Block D — Docker smoke | `test_docker_smoke.py` — 5 tests `@pytest.mark.docker` con lifecycle completo | `src/engine/tests/test_docker_smoke.py` | ✅ |
| S19.C | Tests Block E — Rust inline | `#[cfg(test)]` en `workspace.rs`, `auth.rs`, `config/mod.rs` — 26 tests, 63/63 total Rust | `src/tui/src/` | ✅ |
| S19.D | CORS configurable | `CORSMiddleware` en engine vía `OVD_CORS_ORIGINS` — separa dev (localhost:5173) de prod (dominio real) | `src/engine/api.py` | ✅ |
| S19.E | RAG multi-provider | Switch `OVD_RAG_EMBEDDING_PROVIDER=ollama\|openai`. OpenAI `text-embedding-3-small` como default en prod | `src/engine/rag.py` | ✅ |
| S19.F | Docker backup | Servicio `ovd-backup` en `docker-compose.prod.yml` — pg_dump diario, gzip, retención 30 días | `docker-compose.prod.yml` | ✅ |
| S19.G | Docker Secrets | `openai_api_key` secret en `docker-compose.prod.yml` + carga en entrypoint | `docker-entrypoint.sh` | ✅ |
| S19.H | README reescrito | Guía de onboarding completa para nuevo integrante: arquitectura, setup, vars, primer ciclo, troubleshooting | `README.md` | ✅ |

---

### Sprint 20 — Resiliencia del Engine ✅ (2026-04-21)

Cierre de 8 gaps de resiliencia detectados en auditoría. El código funcional estaba completo (S19) pero sin protección ante nodos colgados, reintentos sin backoff, sesiones stale ni circuit breaker.

| # | Item | GAP | Descripción | Archivo(s) | Estado |
|---|------|-----|-------------|-----------|--------|
| S20.A | Dependencia `tenacity` + vars de entorno | — | `tenacity>=8.2.0` en `pyproject.toml`. Vars: `OVD_NODE_TIMEOUT_SECS`, `OVD_MAX_RETRIES`, `OVD_CB_FAIL_THRESHOLD`, `OVD_CB_RECOVERY_SECS`, `OVD_SSE_STREAM_TIMEOUT_SECS` | `pyproject.toml`, `.env` | ✅ |
| S20.B | Retries configurables con backoff exponencial | GAP-R6 + R2 | `MAX_RETRIES` configurable vía env. `invoke_structured` usa `@retry` de tenacity con `wait_exponential(1s→10s)` en lugar del loop manual | `src/engine/graph.py` | ✅ |
| S20.C | Timeout por nodo + timeout SSE global | GAP-R1 | `asyncio.wait_for()` en `agent_executor` con `OVD_NODE_TIMEOUT_SECS`. Timeout global en generador SSE con `asyncio.timeout()` | `src/engine/graph.py`, `src/engine/api.py` | ✅ |
| S20.D | Circuit breaker para providers LLM | GAP-R4 + R8 | `_CircuitBreaker` en `model_router.py` (closed→open→half-open). Retry con tenacity en `_fetch_resolved`. `CircuitOpenError` para fallback inmediato | `src/engine/model_router.py` | ✅ |
| S20.E | Fallback para `qa_review` | GAP-R5 | Patrón doble fallback: `invoke_structured` → `_parse_qa_fallback` (regex) → resultado neutro (score=70, passed=True) | `src/engine/graph.py` | ✅ |
| S20.F | Cancelación de sesiones stale | GAP-R3 | `cancel_stale_sessions()` en `task_checkout.py`: cancela `asyncio.Task`, desregistra sesión, publica NATS `session.timeout` | `src/engine/task_checkout.py`, `src/engine/api.py` | ✅ |
| S20.G | NATS retry + dead letter queue | GAP-R7 | `_publish_with_retry` con tenacity (max 2, backoff 1s). `_send_to_dlq` persiste mensajes fallidos en tabla `ovd_nats_dlq` | `src/engine/nats_client.py` | ✅ |
| S20.H | Migración Alembic DLQ | — | `CREATE TABLE ovd_nats_dlq` — id, subject, payload JSONB, error, created_at, processed_at. Índice en mensajes sin procesar | `src/engine/migrations/versions/20260420_0002_nats_dlq.py` | ✅ |
| S20.I | Tests resiliencia (27 nuevos) | — | `test_resilience_retry.py` (4), `test_resilience_timeout.py` (3), `test_resilience_circuit_breaker.py` (6), `test_resilience_qa_fallback.py` (6), `test_resilience_stale_cancel.py` (4), `test_resilience_nats_dlq.py` (4) | `src/engine/tests/` | ✅ |

---

### Sprint 21 — Visión + Dashboard Completo ✅ (2026-04-21)

Integración de visión artificial como pre-procesador de imágenes, fixes SSE críticos, panel SDD completo y panel de aprobación con revisión iterativa en el dashboard.

#### Visión — engine + dashboard

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S21.A | Campos `image_base64` + `image_description` en `StartSessionRequest` | Dos campos opcionales: base64 crudo (engine procesa) o descripción ya procesada | `src/engine/api.py` | ✅ |
| S21.B | Campos nuevos en `OVDState` | `image_base64: str` + `image_description: str` — strings simples, sin impacto en checkpointer | `src/engine/graph.py` | ✅ |
| S21.C | Nodo `describe_image` | Pre-procesador: si hay `image_base64`, llama modelo visión vía Ollama → descripción textual del layout. No-op si no hay imagen o ya hay descripción o `OVD_VISION_ENABLED=false` | `src/engine/graph.py` | ✅ |
| S21.D | `_build_fr_content()` — inyección en `analyze_fr` | Si hay `image_description`, agrega bloque "Descripción visual del diseño adjunto" al prompt | `src/engine/graph.py` | ✅ |
| S21.E | Posición en el grafo | `START → describe_image → analyze_fr` (reemplaza edge directo) | `src/engine/graph.py` | ✅ |
| S21.F | Variables de entorno | `OVD_VISION_MODEL`, `OVD_VISION_OLLAMA_URL`, `OVD_VISION_ENABLED=true` | `.env` | ✅ |
| S21.G | Dashboard: drop zone + preview + paste | FileReader → base64. Drop zone, miniatura, botón remover, paste ⌘V desde portapapeles | `src/dashboard/src/pages/FrLauncher.tsx` | ✅ |
| S21.H | Tests `test_vision.py` (8 tests) | No-op sin imagen, no reprocesa si ya hay descripción, inyección correcta, error no rompe ciclo, limpieza base64 | `src/engine/tests/test_vision.py` | ✅ |

#### SSE + Grafo OVD — fixes críticos

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S21.I | Fix Error 422 en lanzador | `StartSessionRequest`: `session_id`, `project_id`, `directory` opcionales con defaults vacíos | `src/engine/api.py` | ✅ |
| S21.J | Fix SSE named events ignorados | `_make_sse_event` elimina campo `event:` — todos los eventos disparan `onmessage` en el browser | `src/engine/api.py` | ✅ |
| S21.K | Indicadores Grafo OVD en tiempo real | `stream_mode=["values","updates"]` emite `node_end` por nodo. `NODE_ALIAS` + handler actualiza waiting→running→done | `src/engine/api.py`, `src/dashboard/src/pages/FrLauncher.tsx` | ✅ |

#### Panel SDD + aprobación completa — dashboard

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S21.L | Panel SDD completo en aprobación | `pending_approval` muestra: resumen, requisitos con criterios de aceptación, tareas. Toggle Ver/Ocultar SDD | `src/dashboard/src/pages/FrLauncher.tsx` | ✅ |
| S21.M | Feedback + acción `revise` | Textarea de correcciones + botón "Solicitar revisión" (habilitado si hay texto). `handleApproval(action)` unificado para approve/revise/reject | `src/dashboard/src/pages/FrLauncher.tsx` | ✅ |
| S21.N | Adjuntar archivo al feedback | FileReader (max 4000 chars). Bloquea `.env`, `id_rsa`, `.ssh`, `.aws`, `credentials`. Chip con nombre + ✕ para quitar | `src/dashboard/src/pages/FrLauncher.tsx` | ✅ |
| S21.O | Badge Revisión #N | Muestra contador de revisiones del SDD (amarillo → naranja desde #2). Leído desde evento `pending_approval` | `src/dashboard/src/pages/FrLauncher.tsx` | ✅ |
| S21.P | Exportar SDD como markdown | Genera `{threadId}-sdd.md` client-side con resumen, requisitos, criterios y tareas. Sin llamar al engine | `src/dashboard/src/pages/FrLauncher.tsx` | ✅ |
| S21.Q | `openStream()` helper | Reutilizable para approve/revise — evita duplicar lógica SSE. Resetea nodos desde `generate_sdd` al pedir revisión | `src/dashboard/src/pages/FrLauncher.tsx` | ✅ |

**Grafo post-S21:**
```
START → describe_image → analyze_fr → generate_sdd → route_agents
  → agent_executor → security_audit → qa_review → request_approval → deliver
```

---

### Sprint 22 — Calidad y Documentación Automática ⬜ (planificado)

Tres nuevos nodos que cierran los gaps de validación real: tests ejecutados, scanning de artefactos y documentación generada automáticamente en cada entrega.

**Contexto:** el flujo actual genera código y lo entrega en un PR. S22 garantiza que ese PR incluye tests verdes, artefactos scaneados y documentación precisa — sin intervención manual adicional.

#### Nodo `run_tests` — ejecución real de tests generados

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S22.A | Nodo `run_tests` en graph.py | Posición: entre `qa_review` y `request_approval`. Detecta stack por extensión de archivos (.py→pytest, .ts/.tsx→vitest, .rs→cargo test) | `src/engine/graph.py` | ⬜ |
| S22.B | Ejecución en directorio temporal | Escribe código + tests en tmpdir, ejecuta runner con timeout configurable, captura stdout/stderr | `src/engine/graph.py` | ⬜ |
| S22.C | Ciclo de retry ante fallos | Tests fallan → reinyecta error + contexto al agente generador (máx 2 rondas). Si persisten → continúa con reporte de fallos para que el arquitecto decida | `src/engine/graph.py` | ⬜ |
| S22.D | Reporte de tests en panel de aprobación | El SDD que aprueba el arquitecto incluye resultados reales: N/M tests pasando, fallos detallados | `src/dashboard/src/pages/FrLauncher.tsx` | ⬜ |
| S22.E | `run_tests` en Grafo OVD dashboard | Nuevo nodo visible entre QA Review y Aprobación | `src/dashboard/src/pages/FrLauncher.tsx` | ⬜ |
| S22.F | Tests de `run_tests` | No-op sin tests generados, detecta stack correctamente, retry ante fallo, timeout no bloquea ciclo | `src/engine/tests/test_run_tests.py` | ⬜ |

#### Security scanning CLI — artefactos reales

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S22.G | Fase de scanning en `security_audit` | Antes del LLM review: ejecuta herramientas CLI sobre artefactos generados | `src/engine/graph.py` | ⬜ |
| S22.H | Dependencias: `pip-audit` / `npm audit` / `cargo audit` | Detecta CVEs en dependencias declaradas. Resultado se inyecta como contexto al LLM reviewer | `src/engine/graph.py` | ⬜ |
| S22.I | Secretos: `gitleaks` | Detecta tokens, passwords, API keys hardcodeados en el código generado | `src/engine/graph.py` | ⬜ |
| S22.J | SAST: `semgrep` | Detecta SQL injection, XSS, path traversal, command injection en código generado | `src/engine/graph.py` | ⬜ |
| S22.K | Bloqueo automático ante críticos | CVE crítico o secreto detectado → flag en panel de aprobación. El arquitecto ve el hallazgo antes de aprobar | `src/engine/graph.py` | ⬜ |
| S22.L | Herramientas en Dockerfile del engine | `pip install pip-audit gitleaks semgrep` en imagen de producción | `src/engine/Dockerfile` | ⬜ |

#### Nodo `generate_docs` — documentación automática

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S22.M | Nodo `generate_docs` en graph.py | Posición: entre `request_approval` y `deliver`. Recibe estado completo: FR, SDD, código generado, resultados de security y QA | `src/engine/graph.py` | ⬜ |
| S22.N | Lógica condicional por tipo de FR | Frontend component → README + props API. Backend endpoint → OpenAPI spec + curl examples. DB migration → migration guide + rollback. Servicio completo → README + OpenAPI + Mermaid + ADR. Refactor → CHANGELOG + ADR | `src/engine/graph.py` | ⬜ |
| S22.O | Fallo parcial no bloquea entrega | Si la generación falla, entrega lo que puede + warning en descripción del PR. `deliver` recibe siempre un resultado | `src/engine/graph.py` | ⬜ |
| S22.P | Documentos incluidos en el PR | Los artefactos de docs se agregan al commit junto al código generado | `src/engine/graph.py` | ⬜ |
| S22.Q | `generate_docs` en Grafo OVD dashboard | Nuevo nodo visible entre Aprobación y Entregar | `src/dashboard/src/pages/FrLauncher.tsx` | ⬜ |
| S22.R | Tests de `generate_docs` | Lógica condicional por tipo, fallo parcial no bloquea, docs incluidos en artifacts | `src/engine/tests/test_generate_docs.py` | ⬜ |

**Grafo post-S22:**
```
START → describe_image → analyze_fr → generate_sdd → route_agents
  → agent_executor → security_audit → qa_review → run_tests
  → request_approval → generate_docs → deliver
```

**Al terminar S22:** el PR que aprueba el arquitecto habrá pasado por tests ejecutados y verificados, scanner de dependencias + secretos + SAST, y documentación generada según el tipo de FR. Sin intervención manual adicional.

---

### Sprint 42 — Stack-aware templates + calidad de generación ✅

**Identificado:** 2026-04-23
**Motivación:** Ciclo de validación S40 (`22d68d30`) reveló 4 problemas independientes:
1. SDD genera FastAPI completo para un FR de función pura (IMC) → over-engineering
2. Agente backend genera `calculate_bmi` en 4 archivos diferentes → duplicados, tests fallan
3. Valores float de memoria en tests (`23.02 == 22.94`) → fallos de precisión numérica
4. Templates genéricos no tienen reglas específicas de stack → mismo template para Python, TypeScript, Oracle

**Problema raíz:** OVD sirve múltiples stacks tecnológicos pero usa los mismos templates para todos.

#### Items implementados

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S42-A | `system_sdd.md` — scope control | Regla explícita: si el FR describe una función/algoritmo sin mencionar HTTP, NO generar FastAPI ni routers. Ejemplo visual ❌/✅ para FRs de función pura | `src/engine/templates/system_sdd.md` | ✅ |
| S42-B | `run_tests` workspace isolation | Al iniciar un retry round (>0), elimina archivos de implementación Python del ciclo actual (mtime >= cycle_start_ts) para que el agente empiece sin residuos del round anterior. No toca test_*.py ni archivos de infraestructura | `src/engine/graph.py` (`_cleanup_impl_files_from_prev_retry`) | ✅ |
| S42-C | Float precision en template Python | Regla reforzada en `system_backend_python.md`: proceso obligatorio de 3 pasos para calcular valores float antes de escribir el assert. Prohíbe explícitamente valores de memoria | `src/engine/templates/system_backend_python.md` | ✅ |
| S42-D | Detección de duplicados en retry | `_detect_duplicate_functions(work_dir)` escanea archivos Python del workspace y detecta funciones definidas en más de un archivo. El diagnóstico se incluye en `retry_feedback` | `src/engine/graph.py` (`_detect_duplicate_functions`, `update_test_retry`) | ✅ |
| S42-E | Template selection por stack | `template_loader.load(name, stack_language="python")` busca `{name}_{stack_language}.md` antes que `{name}.md`. `api.py` lee `ovd_stack_profiles.language` y lo pasa como `stack_language` en `OVDState`. Los runners de agentes reciben y propagan el parámetro | `src/engine/template_loader.py`, `src/engine/graph.py`, `src/engine/api.py` | ✅ |
| S42-F | Templates por stack (nuevos archivos) | Creados 5 templates específicos. Cada uno tiene reglas y ejemplos del stack correcto sin mezclar Python con TypeScript ni PostgreSQL con Oracle | `src/engine/templates/system_backend_python.md`, `system_backend_typescript.md`, `system_frontend_react.md`, `system_database_postgresql.md`, `system_database_oracle.md` | ✅ |

#### Templates por stack — mapa completo

| Template genérico | Stack `python` | Stack `typescript` | Stack `oracle` | Stack `postgresql` |
|-------------------|---------------|-------------------|----------------|-------------------|
| `system_backend.md` | `system_backend_python.md` ✅ | `system_backend_typescript.md` ✅ | — (usar genérico) | — (usar genérico) |
| `system_frontend.md` | — (usar genérico) | `system_frontend_react.md` ✅ | — | — |
| `system_database.md` | — | — | `system_database_oracle.md` ✅ | `system_database_postgresql.md` ✅ |

**Flujo de selección en `template_loader.load()`:**
```
stack_language="python" + name="system_backend"
  1. ¿existe system_backend_python.md?  → ✅ carga ese
  2. ¿existe {language}/system_backend.md? → fallback idioma
  3. ¿existe system_backend.md? → fallback genérico
  4. Fallback inline hardcodeado
```

#### Stacks futuros (pendiente)

Los siguientes stacks están documentados en el mapa pero aún no tienen templates:

| Stack | `stack_language` | Templates pendientes |
|-------|-----------------|---------------------|
| Java | `java` | `system_backend_java.md` — Spring Boot, Maven/Gradle, JUnit 5 |
| Go | `go` | `system_backend_go.md` — net/http, go test, módulos |
| Vue 3 | `vue` | `system_frontend_vue.md` — Vue 3 Composition API, Vitest |
| Angular | `angular` | `system_frontend_angular.md` — Angular 17+, Jasmine/Karma |

Para agregar un nuevo stack: crear el template en `src/engine/templates/` con nombre `system_{agente}_{stack}.md`, configurar el stack en el proyecto desde el dashboard (ProjectModal → Lenguaje), y el sistema lo usará automáticamente.

#### Tests

- `src/engine/tests/test_s42.py` — 35 tests nuevos
- Cobertura: S42-A (template SDD), S42-B (cleanup), S42-C (float rule), S42-D (duplicados), S42-E (template loader), S42-F (templates por stack)

---

### Sprint 43 — Externalización de instrucciones stack-aware ✅ (2026-04-23)

**Motivación:** Instrucciones hardcodeadas en Python (`graph.py`) para lenguajes específicos rompían la separación de responsabilidades y dificultaban ajustes sin tocar código.

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S43-A | `doc_instructions` → `system_docs.md` | Tabla de documentos requeridos por tipo de FR movida al template | `src/engine/templates/system_docs.md` | ✅ |
| S43-B | `conftest.py` condicional por runner | Inyección de conftest solo cuando `runner == "pytest"`, no para vitest ni cargo | `src/engine/graph.py` | ✅ |
| S43-C | `_get_import_error_diagnosis(runner)` | Diagnóstico de ImportError stack-aware: pytest → `__init__.py`/conftest, vitest → tsconfig, cargo → `mod` | `src/engine/graph.py` | ✅ |
| S43-D | `_RUNNER_FLAGS` dict centralizado | Flags por runner a nivel módulo en vez de hardcodeados en el comando pytest | `src/engine/graph.py` | ✅ |
| S43-E | `_get_retry_no_modify_instruction(runner)` | Feedback de retry stack-aware: `src/` para pytest, `__tests__` para vitest, `#[cfg(test)]` para cargo | `src/engine/graph.py` | ✅ |
| S43-F | RUTs válidos en templates | Tabla de RUTs matemáticamente verificados en `system_backend_python.md` y `system_backend.md` | `src/engine/templates/system_backend_python.md`, `system_backend.md` | ✅ |

**Tests:** 31 tests nuevos en `test_s43.py`. **847 tests totales** pasan (0 fallos).

---

### Prueba end-to-end S43+ — Sistema Contratos y Beneficios (2026-04-23)

**Objetivo:** Validar capacidades OVD con un FR de alta complejidad real: RUT módulo 11, Oracle XE, FastAPI + React, Docker, números primos, roles, valor_total automático.

**Ciclo ejecutado:** `441dbe04-b185-483a-a9bd-8b2e3285f95c`
**Modelo:** `qwen3-coder:30b` + `deepseek-r1:14b` (analyzer)
**Duración estimada:** ~80 minutos (4 agentes, 2 rondas de retry)
**QA Score:** 65/100 | **Tests:** 16/22 passed (6 fallos RUT, 1 import error)
**Archivos generados:** 106

#### Capacidades validadas ✅

| Capacidad | Resultado |
|-----------|-----------|
| Lógica de negocio pura (primos, tipos contrato) | ✅ `is_prime()` correcto, `VALID_CONTRACT_TYPES=[1,2,3,4,10,15]` |
| Validación RUT módulo 11 (implementación) | ✅ Algoritmo módulo 11 correcto en `validate_rut()` y `validateRut()` (TS) |
| Trigger Oracle valor_total | ✅ Script SQL generado en `migrations/` |
| JWT con rol embebido | ✅ Estructura básica generada |
| Componentes frontend con validación en tiempo real | ✅ `LoginForm.tsx` con feedback de RUT al blur |
| `rutValidator.ts` TypeScript | ✅ Implementación correcta e independiente |

#### Gaps identificados 💡

| ID | Descripción | Severidad | Sprint propuesto |
|----|-------------|-----------|-----------------|
| **GAP-T1** | **RUT incorrecto en tests** — S43-F insuficiente. El agente usa `12.345.678-9` (DV=9, correcto es DV=5) en todos los tests. La tabla en `system_backend.md` existe pero el agente la ignora. Fix: inyectar la tabla RUT directamente vía `project_context` desde BD, no solo en template. | Alta | S45 |
| **GAP-T2** | **Frontend React en vez de Angular** — `project_context` de `ovd_project_profiles.constraints` no se carga al iniciar ciclo. `session_create` en `api.py` no hace JOIN con esa tabla. El stack `language='python'` no informa el frontend stack. Fix: cargar `constraints` en `session_create`. | Alta | S45 |
| **GAP-T3** | **devops asignado a código de aplicación** — 4 agentes asignados incluyendo devops para código Python. S28-A mejoró pero no eliminó el problema. Devops generó código que duplicó responsabilidades del agente backend. | Media | S45 |
| **GAP-T4** | **Oracle con servicio interno en vez de `host.docker.internal`** — docker-compose usa `oracle://user:password@oracle:1521/XE` (servicio Docker interno) en vez de `host.docker.internal:1521/XEPDB1`. La URL de conexión debe estar como variable explícita en `project_context`. | Alta | S45 |
| **GAP-T5** | **Import chain roto — módulos referenciados pero no creados** — `auth_service.py` importa `schemas.py` y `jwt.py` que el agente nunca generó. La app no arranca sin parchear. | Alta | S45 |
| **GAP-T6** | **Sin `requirements.txt` ni `package.json`** — El agente no generó los archivos de dependencias. El `docker compose up` no puede funcionar sin ellos. | Alta | S45 |

#### Aprendizajes para templates y engine

1. **S43-F necesita refuerzo (GAP-T1):** Tabla de RUTs en template no es suficiente. El agente necesita el RUT correcto como dato inmutable en el prompt de cada agente, no como referencia en un documento de sistema. Solución: incluir los RUTs de prueba en `project_context` como campo estructurado cargado desde `ovd_project_profiles`.

2. **`session_create` no carga `constraints` (GAP-T2):** Fix de ~10 líneas en `api.py`. Actualmente solo lee `ovd_projects` pero no hace JOIN con `ovd_project_profiles`. Este es el bloqueante principal para que el `project_context` llegue a los agentes.

3. **Broken import chain (GAP-T5/T6):** El agente debe generar los archivos en orden: `schemas.py` → `models.py` → `routers.py`. El template debería exigir una lista de archivos requeridos antes de empezar la implementación.

4. **Tiempo de ciclo con `qwen3-coder:30b`:** ~80 min para FR de alta complejidad con 4 agentes y 2 retry rounds. Con S41.PRE (timeouts diferenciados) y S41 (RAG learning) se podría reducir significativamente en ciclos posteriores del mismo proyecto.

---

### Sprint 45 — Fix gaps de generación: project_context + RUT enforcement + import chain ⬜

**Identificado:** 2026-04-23
**Motivación:** La prueba end-to-end S43+ reveló 6 gaps que impiden que el entregable sea ejecutable. Los 3 más críticos (GAP-T1, GAP-T2, GAP-T5) tienen fixes concretos de alcance reducido.

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S45-A | Cargar `constraints` desde BD en `session_create` | `api.py → session_create`: JOIN con `ovd_project_profiles` para leer `constraints` y agregarlo a `project_context`. Resuelve GAP-T2 (stack frontend no llega a agentes) | `src/engine/api.py` | ⬜ |
| S45-B | RUTs de prueba en `project_context` | En `system_backend_python.md` y `system_sdd.md`, instrucción explícita: "Si el proyecto usa RUT chileno, los RUTs de prueba DEBEN venir del `project_context`. NUNCA inventes RUTs." Resuelve GAP-T1 | `src/engine/templates/` | ⬜ |
| S45-C | Checklist de archivos requeridos en template backend | `system_backend_python.md`: el agente debe listar y crear explícitamente `requirements.txt`, `schemas.py`, todos los módulos referenciados antes de implementarlos. Resuelve GAP-T5/T6 | `src/engine/templates/system_backend_python.md` | ⬜ |
| S45-D | Refuerzo regla devops en `system_sdd.md` | Agregar ejemplos concretos: "FR con Oracle + FastAPI → agentes: database + backend. devops SOLO si el FR menciona explícitamente CI/CD, Kubernetes o pipeline de despliegue." Resuelve GAP-T3 | `src/engine/templates/system_sdd.md` | ⬜ |
| S45-E | URL de conexión BD como variable en `project_context` | Instrucción en template: la URL de conexión a BD externa debe tomarse de `{db_connection_url}` del `project_context`, nunca hardcodeada. Resuelve GAP-T4 | `src/engine/templates/system_backend_python.md` | ⬜ |

**Tests S45:**
- `test_session_create_loads_constraints` — `project_context` contiene constraints de `ovd_project_profiles`
- `test_rut_table_not_in_project_context_fallback` — sin constraints, usa tabla estática del template
- `test_requirements_txt_in_template` — template menciona `requirements.txt` como obligatorio

**Orden:** S45-A (fix api.py) → S45-B/C/D/E (templates) → tests → relanzar ciclo contratos-beneficios

---

### Sprint 46 — Design Quality System: UI profesional en código generado ⬜

**Identificado:** 2026-04-23
**Motivación:** La prueba end-to-end S43+ demostró que el frontend generado es funcional pero visualmente básico: CSS raw sin sistema de diseño, sin layout de aplicación (sidebar/topbar), sin estados de UI consistentes (loading, empty, error), sin biblioteca de componentes. El cliente no puede presentar un entregable así. OVD necesita que el agente frontend produzca UIs de nivel producción por defecto.

**Problema raíz:** `system_frontend_react.md` y `system_frontend.md` definen arquitectura y patrones de código, pero no imponen ningún sistema de diseño. El agente elige libremente entre CSS raw, Tailwind ad-hoc o clases inventadas.

#### S46-A — Design system obligatorio en templates

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S46-A1 | Tailwind CSS como default | Agregar a `system_frontend_react.md`: instrucción explícita de usar Tailwind para todo el CSS. Prohibir CSS-in-JS ad-hoc y clases inventadas sin definición | `src/engine/templates/system_frontend_react.md` | ⬜ |
| S46-A2 | shadcn/ui como biblioteca de componentes | Instrucción de usar componentes shadcn/ui (Button, Input, Card, Table, Dialog, Badge, Toast) en vez de construir primitivos desde cero. Con ejemplos de import y uso | `src/engine/templates/system_frontend_react.md` | ⬜ |
| S46-A3 | App shell obligatorio | Para apps multi-página: generar siempre un layout con sidebar + topbar + área de contenido. Incluir ejemplo estructural en el template | `src/engine/templates/system_frontend_react.md` | ⬜ |
| S46-A4 | Paleta de colores y tipografía | Definir tokens de diseño base en `tailwind.config.ts` generado: primary, secondary, destructive, muted, foreground, background. Tipografía: Inter como font por defecto | `src/engine/templates/system_frontend_react.md` | ⬜ |

#### S46-B — Estados de UI requeridos

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S46-B1 | Estados de formulario completos | Todo `<form>` debe tener: estado normal, focus visible, error con mensaje, disabled, loading (spinner en botón submit). Prohibido botón sin feedback visual | `src/engine/templates/system_frontend_react.md` | ⬜ |
| S46-B2 | Estados de lista obligatorios | Todo componente de lista debe tener: skeleton de carga, estado vacío con ilustración/icono y mensaje, estado de error con retry | `src/engine/templates/system_frontend_react.md` | ⬜ |
| S46-B3 | Feedback de acciones | Toda acción destructiva: confirmation dialog. Toda acción async exitosa: toast de éxito. Todo error de API: toast de error con mensaje legible (no stack trace) | `src/engine/templates/system_frontend_react.md` | ⬜ |

#### S46-C — Biblioteca de patrones UI en knowledge base

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S46-C1 | Patrones de formulario profesionales | Agregar a `src/knowledge/ui-ux/`: guías de floating labels, validación inline, campos con iconos, grupos de campos relacionados | `src/knowledge/ui-ux/` | ⬜ |
| S46-C2 | Patrones de tablas de datos | Data table con sort, filtro, paginación, selección de filas, acciones por fila. Ejemplo completo con shadcn/ui Table | `src/knowledge/ui-ux/` | ⬜ |
| S46-C3 | Patrones de dashboard | Layout de métricas (stat cards), gráficos placeholder, actividad reciente, navegación lateral con items activos | `src/knowledge/ui-ux/` | ⬜ |
| S46-C4 | Patrones de auth | Login card centrado, validación en tiempo real, forgot password flow, indicador de fortaleza de contraseña | `src/knowledge/ui-ux/` | ⬜ |

#### S46-D — Responsive y accesibilidad

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S46-D1 | Breakpoints obligatorios | Toda página debe funcionar en mobile (≥375px), tablet (≥768px) y desktop (≥1280px). Sidebar colapsa a drawer en mobile | `src/engine/templates/system_frontend_react.md` | ⬜ |
| S46-D2 | Accesibilidad mínima | `aria-label` en iconos sin texto, `role` en elementos interactivos custom, contraste AA mínimo, navegación por teclado en modales | `src/engine/templates/system_frontend_react.md` | ⬜ |

**Resultado esperado:** Un ciclo OVD con FR de frontend produce una app con: layout completo, componentes shadcn/ui, Tailwind consistente, estados loading/empty/error, toasts, y responsive básico — sin que el usuario tenga que especificarlo en el FR.

---

### Sprint 44 — MCP Server Manager: administración dinámica + credenciales ⬜

**Identificado:** 2026-04-23
**Motivación:** El `MCPClientPool` actual tiene `context7` hardcodeado en `mcp_client.py`. No hay forma de agregar otros servidores MCP desde el dashboard, ni de manejar credenciales para servers que requieren autenticación (API keys, tokens). El usuario necesita poder registrar servidores MCP como context7, Brave Search, GitHub MCP, etc., y administrar sus credenciales de forma segura desde OVD.

**Estado actual:** `MCPClientPool` singleton con `_connect_context7()` fijo. Sin tabla BD, sin API CRUD, sin UI.

#### S44-A — Modelo de datos

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S44-A | Tabla `ovd_mcp_servers` | `id, org_id, name, transport (stdio/sse/http), command, args (jsonb), env_vars (jsonb), url, enabled, scope (global/project), created_at`. Row-level security por org_id | `migrations/` | ⬜ |
| S44-B | Tabla `ovd_mcp_credentials` | `id, mcp_server_id, key_name, encrypted_value, created_at`. Credenciales cifradas en BD o referencia a Infisical | `migrations/` | ⬜ |
| S44-C | Tabla `ovd_project_mcp_servers` | Asociación M:N entre proyectos y servidores MCP. Permite habilitar/deshabilitar servers por proyecto | `migrations/` | ⬜ |

#### S44-B — API Engine

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S44-D | `GET /api/v1/orgs/{org_id}/mcp-servers` | Listar servidores MCP de la org (globales + del proyecto) | `src/engine/routers/api_v1.py` | ⬜ |
| S44-E | `POST /api/v1/orgs/{org_id}/mcp-servers` | Registrar nuevo servidor MCP (name, transport, command/url, args) | `src/engine/routers/api_v1.py` | ⬜ |
| S44-F | `PUT /api/v1/orgs/{org_id}/mcp-servers/{id}` | Actualizar configuración del servidor | `src/engine/routers/api_v1.py` | ⬜ |
| S44-G | `DELETE /api/v1/orgs/{org_id}/mcp-servers/{id}` | Eliminar servidor MCP | `src/engine/routers/api_v1.py` | ⬜ |
| S44-H | `POST /api/v1/orgs/{org_id}/mcp-servers/{id}/credentials` | Agregar/actualizar credencial (key_name + value cifrado) | `src/engine/routers/api_v1.py` | ⬜ |
| S44-I | `POST /api/v1/orgs/{org_id}/mcp-servers/{id}/test` | Probar conexión al servidor MCP (lanza el proceso, verifica tools disponibles, retorna lista) | `src/engine/routers/api_v1.py` | ⬜ |

#### S44-C — MCPClientPool dinámico

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S44-J | `MCPClientPool.load_from_db()` | Al iniciar el engine, lee `ovd_mcp_servers` (enabled=true) y lanza cada servidor según su transport. Reemplaza el `_connect_context7()` hardcodeado. context7 migrado a un registro en BD | `src/engine/mcp_client.py` | ⬜ |
| S44-K | Soporte transport stdio/sse/http | stdio: lanza subproceso con `command` + `args`. sse: conecta a URL vía SSE. http: conecta a URL HTTP. Actualmente solo existe stdio para context7 | `src/engine/mcp_client.py` | ⬜ |
| S44-L | Credenciales en env del subproceso | Para servers stdio, las credenciales se inyectan como variables de entorno del subproceso (no aparecen en logs ni en el estado del grafo) | `src/engine/mcp_client.py` | ⬜ |
| S44-M | Reload sin restart | `POST /api/v1/orgs/{org_id}/mcp-servers/reload` — cierra y reconecta todos los servers sin reiniciar el engine | `src/engine/mcp_client.py`, `src/engine/routers/api_v1.py` | ⬜ |
| S44-N | Asignación por agente configurable | Cada servidor MCP tiene `agent_scope: list[str]` (e.g. `["backend", "frontend"]`). Por defecto: todos los agentes implementadores | `src/engine/mcp_client.py` | ⬜ |

#### S44-D — Dashboard MCP Manager

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S44-O | Página `/admin/mcp` | Lista de servidores MCP: nombre, transport, estado (conectado/desconectado), tools disponibles, scope. Botones: agregar, editar, eliminar, test | `src/dashboard/src/pages/McpManager.tsx` | ⬜ |
| S44-P | Modal de registro de servidor | Formulario: nombre, transport (stdio/sse/http), command o URL, args (editor JSON), habilitado, scope (global/proyecto) | `src/dashboard/src/pages/McpManager.tsx` | ⬜ |
| S44-Q | Panel de credenciales | Por cada servidor: lista de keys configuradas (nombre visible, valor oculto), agregar/eliminar. Sin mostrar valores en claro | `src/dashboard/src/pages/McpManager.tsx` | ⬜ |
| S44-R | Test de conexión en UI | Botón "Probar conexión" — llama al endpoint S44-I y muestra: tools disponibles, latencia, error si falla | `src/dashboard/src/pages/McpManager.tsx` | ⬜ |
| S44-S | Asignación por proyecto | En la página de configuración del proyecto, selector multi-check de servidores MCP disponibles | `src/dashboard/src/pages/Projects.tsx` | ⬜ |

#### Servidores MCP a soportar (ejemplos)

| Servidor | Transport | Credencial | Uso en OVD |
|----------|-----------|------------|------------|
| `@upstash/context7-mcp` | stdio | ninguna | Docs de librerías para agentes (ya existe) |
| `@modelcontextprotocol/server-brave-search` | stdio | `BRAVE_API_KEY` | Web research para `analyze_fr` |
| `@modelcontextprotocol/server-github` | stdio | `GITHUB_TOKEN` | Leer repos del cliente, crear PRs |
| `@modelcontextprotocol/server-postgres` | stdio | `DATABASE_URL` | Introspección de BD del cliente |
| Servidor MCP custom del cliente | http/sse | token | Integración con sistemas propios |

**Orden de implementación:** S44-A → S44-B/C/D → S44-J/K/L (pool dinámico) → S44-O/P/Q (dashboard) → S44-M/N/R/S

---

### Sprint 41.PRE — Fix timeout security_audit + timeouts diferenciados por nodo ⬜

**Identificado:** 2026-04-23
**Problema:** El nodo `security_audit` usa `OVD_MODEL_QA=qwen3-coder-next` (modelo 80B MoE, ~20 t/s). En ciclos donde los agentes generan mucho código, el LLM de auditoría tarda >30 min y el heartbeat lo cancela antes de terminar. El nodo `run_tests` y `qa_review` tienen el mismo riesgo.

**Síntoma observado:**
- Ciclo `71a68ecd`: cancelado por heartbeat a los 30 min en nodo `security_audit`
- El grafo mostraba Ejecutar agentes ✅ pero Auditoría seguridad nunca completó
- `OVD_NODE_TIMEOUT_SECS=1200` aplica igual a todos los nodos — no diferencia por peso

**Fix propuesto (S39-A revisado):**

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S41P.A | Timeouts diferenciados por nodo | `asyncio.wait_for` con timeout específico: `security_audit=1800s`, `qa_review=1200s`, `agents=1800s`, `run_tests=300s`, `generate_docs=600s` | `src/engine/graph.py` | ⬜ |
| S41P.B | Heartbeat threshold configurable | `OVD_HEARTBEAT_TIMEOUT_SECS=3600` (default 1800) para proyectos con ciclos largos. Actualmente hardcodeado en 30 min | `src/engine/graph.py` | ⬜ |
| S41P.C | Modelo más liviano para security_audit | Evaluar usar `qwen3-coder:30b` en vez de `qwen3-coder-next` para `security_audit` — misma calidad, 3× más rápido | `src/engine/.env` | ⬜ |

**Orden sugerido:** implementar S41P.C primero (cambio de una línea en .env, sin código), luego S41P.A y S41P.B si persiste el problema.

---

### Sprint 41 — RAG Learning: Aprendizaje automático desde ciclos ⬜

**Identificado:** 2026-04-23
**Motivación:** Actualmente el RAG solo indexa el informe de entrega final (`ovd-delivery-*.md`). Los errores intermedios — QA failures, fallos de tests, vulnerabilidades de seguridad, causas de ciclos colgados — se "aprenden" de forma manual editando templates. S41 hace ese aprendizaje automático y acumulativo por proyecto.

**Contexto del problema:**
- RAG actual indexa: qué se construyó (resultado final)
- RAG actual NO indexa: qué falló, por qué, cómo se resolvió
- Hoy se corrigen errores recurrentes editando `system_*.md` manualmente (S26 → S40)
- Con S41, el agente recibe lecciones pasadas del mismo proyecto antes de escribir código

#### Parte A — Indexación de errores intermedios (engine)

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S41.A1 | `lessons.py` — módulo de indexación | Nuevo módulo con funciones: `index_qa_finding()`, `index_security_finding()`, `index_test_failure()`, `index_cycle_postmortem()`. Cada función escribe un chunk en pgvector con metadata: `chunk_type`, `project_id`, `cycle_id`, `severity`, `resolved`, `agent_name` (backend/frontend/database/devops — qué agente originó el error) | `src/engine/knowledge/lessons.py` | ⬜ |
| S41.A2 | Hook en `qa_review` | Al terminar `qa_review`, si hay issues, llamar `index_qa_finding(project_id, issues, score, cycle_id)` | `src/engine/graph.py` | ⬜ |
| S41.A3 | Hook en `security_audit` | Al terminar `security_audit`, si hay findings, llamar `index_security_finding(project_id, findings, score, cycle_id)` | `src/engine/graph.py` | ⬜ |
| S41.A4 | Hook en `run_tests` (fallos) | Si tests fallan, indexar `retry_feedback` con `index_test_failure(project_id, error_text, cycle_id)`. No indexar en runs exitosos | `src/engine/graph.py` | ⬜ |
| S41.A5 | Hook en `deliver` (post-mortem) | Generar y indexar resumen del ciclo: qué agentes fallaron, cuántos retries, qué se resolvió y cómo | `src/engine/graph.py` | ⬜ |
| S41.A6 | Schema metadata en pgvector | Agregar columnas `chunk_type`, `severity`, `resolved` a la tabla de chunks RAG, o usar JSONB metadata existente | `migration-ovd/` | ⬜ |

#### Parte B — Inyección de lecciones en agentes

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S41.B1 | `query_lessons_context()` en template_loader | Consulta pgvector filtrado por `project_id` + `agent_name` + `chunk_type IN (qa_finding, test_failure, security_finding)`. Devuelve top-5 más similares al FR actual. Cada agente recibe solo sus propias lecciones pasadas | `src/engine/template_loader.py` | ⬜ |
| S41.B2 | Placeholder `{lessons_context}` en templates | Agregar bloque "Lecciones de ciclos anteriores" en `system_backend.md`, `system_frontend.md`, `system_sdd.md` | `src/engine/templates/` | ⬜ |
| S41.B3 | Formato de lección en prompt | Ejemplo: `[QA finding — cycle a2c87c99] hook useContractValidation generado pero no importado → bug crítico (-15 pts). Asegúrate de importar todos los hooks generados.` | `src/engine/knowledge/lessons.py` | ⬜ |
| S41.B4 | Scope por proyecto y agente | Las lecciones son exclusivas por `project_id` + `agent_name`. El agente frontend solo recibe lecciones de frontend; el backend solo las suyas. No se cruzan entre proyectos ni entre agentes | `src/engine/template_loader.py` | ⬜ |

#### Parte C — Vista "Memoria del equipo" en dashboard

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S41.C1 | Endpoint `GET /api/v1/orgs/{org}/projects/{id}/lessons` | Devuelve lecciones indexadas para un proyecto: tipo, severidad, texto, ciclo de origen, fecha | `src/engine/api.py` | ⬜ |
| S41.C2 | Página `/projects/{id}/lessons` en dashboard | Lista de lecciones activas por proyecto. Filtros por tipo (QA / Security / Tests). Badge de severidad (crítica / alta / media) | `src/dashboard/src/pages/ProjectLessons.tsx` | ⬜ |
| S41.C3 | Enlace desde sidebar por proyecto | Acceso directo a "Memoria del equipo" desde la vista de proyecto | `src/dashboard/src/components/Sidebar.tsx` | ⬜ |
| S41.C4 | Acción "Marcar como resuelta" | El arquitecto puede archivar una lección si ya fue corregida en un template o ya no aplica | `src/dashboard/src/pages/ProjectLessons.tsx` | ⬜ |
| S41.C5 | Lecciones visibles en panel del ciclo | Durante la ejecución del ciclo, mostrar las lecciones que recibieron los agentes como contexto | `src/dashboard/src/pages/FrLauncher.tsx` | ⬜ |

#### Tests

| # | Test | Valida |
|---|------|--------|
| S41.T1 | `test_index_qa_finding` | Chunk insertado en pgvector con metadata correcta |
| S41.T2 | `test_index_test_failure_solo_en_fallos` | No indexa si tests pasaron |
| S41.T3 | `test_query_lessons_scope_por_proyecto` | Lecciones de proyecto A no aparecen en proyecto B |
| S41.T4 | `test_lessons_en_prompt_de_agente` | `{lessons_context}` poblado cuando hay lecciones; vacío si no hay |
| S41.T5 | `test_endpoint_lessons` | GET devuelve lista paginada con filtros por tipo |

**Impacto esperado:** reducción progresiva de errores recurrentes sin tocar templates. Los agentes "recuerdan" qué falló antes en el mismo proyecto y ajustan su implementación.

---

### Sprint 47 — Ejecución secuencial server-side → client-side ⬜

**Identificado:** 2026-04-24
**Motivación:** Los agentes se ejecutan en paralelo: frontend arranca al mismo tiempo que backend, sin conocer las rutas, schemas ni auth que backend generó. El frontend inventa la API, produce tipos incorrectos y genera retries innecesarios. La solución es ejecutar primero el grupo server-side (database + backend + devops) y luego el grupo client-side (frontend) con acceso al código ya escrito.

**Aplica a cualquier stack:** el criterio de agrupación es por capa, no por lenguaje. Un agente `frontend` en Vue, Angular, Flutter web o cualquier otro framework siempre depende de lo que generaron `backend`, `database` y `devops`.

#### S47-A — Grupos de ejecución en `_dispatch_agents`

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S47-A1 | Constantes de grupos | `_SERVER_SIDE_AGENTS = {"database", "backend", "devops"}` / `_CLIENT_SIDE_AGENTS = {"frontend"}` — extensible para nuevos agentes futuros | `graph.py` | ⬜ |
| S47-A2 | `_dispatch_agents` — solo grupo 1 | Filtra `selected_agents` y despacha solo los server-side. Guarda los client-side en `pending_agents` del estado | `graph.py` | ⬜ |
| S47-A3 | Nodo `dispatch_frontend` | Se activa después de que todos los `agent_executor` del grupo 1 terminan. Genera los `Send()` para los agentes client-side pendientes | `graph.py` | ⬜ |
| S47-A4 | Campo `pending_agents` en `OVDState` | Lista de agentes client-side que esperan al grupo 1. Vacía cuando no hay frontend en el SDD | `graph.py` | ⬜ |

#### S47-B — Frontend lee el código server-side generado

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S47-B1 | `_AGENT_PATTERNS["frontend"]` ampliado | Agrega `*.py`, `*.java`, `*.go`, `*.rs`, `requirements.txt`, `*.sql` — el frontend lee los modelos y rutas que generó backend, independiente del lenguaje del stack | `tools/file_tools.py` | ⬜ |
| S47-B2 | `read_project_context` inyectado en frontend | En `dispatch_frontend`, antes de ejecutar el agente, se llama `read_project_context(directory, "frontend")` para que el LLM reciba el código real de backend como contexto | `graph.py` | ⬜ |

#### S47-C — Edge routing

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S47-C1 | Edge `agent_executor` → `dispatch_frontend` | Condicional: si `pending_agents` no está vacío después del fan-out del grupo 1, ir a `dispatch_frontend`; si está vacío, ir a `security_audit` (flujo actual) | `graph.py` | ⬜ |
| S47-C2 | Edge `dispatch_frontend` → `agent_executor` | Segundo fan-out Send() — igual al primero pero solo para agentes client-side | `graph.py` | ⬜ |
| S47-C3 | Después del fan-out frontend → `security_audit` | El flujo post-grupo-2 continúa igual: `security_audit → qa_review → run_tests → deliver` | `graph.py` | ⬜ |

#### S47-D — Dashboard

| # | Item | Descripción | Archivo(s) | Estado |
|---|------|-------------|-----------|--------|
| S47-D1 | Nodo `dispatch_frontend` en `GRAPH_NODES` | Label: "Agentes client-side". Aparece entre `agents` (grupo 1) y un nuevo nodo visual `agents_frontend` | `FrLauncher.tsx` | ⬜ |
| S47-D2 | Alias SSE para `agents_frontend` | `NODE_ALIAS["dispatch_frontend"] = "agents_frontend"` para que el progreso visual sea correcto | `FrLauncher.tsx` | ⬜ |

#### Tests

| # | Test | Valida |
|---|------|--------|
| S47.T1 | `test_dispatch_agents_separa_grupos` | Con `["database","backend","frontend"]`, grupo 1 = `["database","backend"]`, `pending_agents = ["frontend"]` |
| S47.T2 | `test_dispatch_sin_frontend` | Sin frontend en el SDD, `pending_agents = []`, flujo directo a `security_audit` |
| S47.T3 | `test_dispatch_solo_frontend` | SDD con solo frontend: grupo 1 vacío, frontend se despacha directamente (sin espera) |
| S47.T4 | `test_frontend_patterns_incluye_backend_files` | `_AGENT_PATTERNS["frontend"]` contiene `*.py`, `*.java`, `*.go` |
| S47.T5 | `test_dispatch_frontend_inyecta_project_context` | El estado enviado al agente frontend incluye contexto del código server-side ya escrito |

**Trade-off documentado:**
- Tiempo adicional: +20-30 min por el grupo frontend esperando al grupo server-side
- Beneficio: el frontend no inventa la API → menos retries por imports y tipos incorrectos
- Estimado neto: ciclos con retry de frontend (>100 min) se reducen a ciclos sin retry (~90 min)

---

## Orden de trabajo — Próximos sprints (2026-04-26)

Prioridad basada en impacto sobre calidad del entregable y deuda técnica acumulada:

| Prioridad | Sprint | Qué resuelve | Esfuerzo estimado |
|-----------|--------|-------------|-------------------|
| 1 | ~~**S45**~~ — Fix gaps | ✅ Completado 2026-04-24 | — |
| 2 | ~~**S46**~~ — Design Quality System | ✅ Completado 2026-04-24 | — |
| 3 | ~~**S47**~~ — Background graph task + early cycle registration | ✅ Completado 2026-04-25 | — |
| 4 | ~~**S41.PRE**~~ — Timeouts diferenciados | ✅ Completado 2026-04-24 | — |
| 5 | ~~**S41**~~ — RAG Learning | ✅ Completado 2026-04-24 | — |
| 6 | ~~**S48**~~ — Detección Ollama + task-by-task + Pydantic v2 | ✅ Completado 2026-04-25 (S48/S49/S50) | — |
| 7 | ~~**S51**~~ — Test file generation + S51-C retry automático | ✅ Completado 2026-04-25 | — |
| 8 | ~~**S54**~~ — Fence hints + diagnóstico runner | ✅ Completado 2026-04-26 | — |
| 9 | ~~**S55**~~ — Log visibility + preserve_nonempty + float hint | ✅ Completado 2026-04-26 | — |
| 10 | ~~**S56**~~ — QA contextualizado + logging configurado + Oracle constraints filter | ✅ Completado 2026-04-26 | — |
| 11 | ~~**S57**~~ — QA score reducer + collection errors fix | ✅ Completado 2026-04-26 | — |
| 12 | **S58-pre** — Refactoring arquitectura de templates (prerequisito de S58) | Templates actuales son overrides completos — imposible mantener con N stacks | Medio (~1 día) |
| 13 | **S58** — Stack transversality | Fixes S40–S57 con sesgo Python/pytest no aplican correctamente a TypeScript/Rust | Medio (~1 día) |
| 14 | **S44** — MCP Server Manager | context7 hardcodeado; no se pueden agregar otros servidores MCP desde UI | Medio (~1 día) |

---

## S55 — Log visibility + preserve_nonempty + float hint (2026-04-26) ✅

**Resultado ciclo validación:** `9d939f29` — 1m 35s, pytest exit 0 (primer éxito histórico), 7/7 PASS, 30k tokens, 0 retries.

| Item | Descripción | Archivo(s) | Estado |
|------|-------------|-----------|--------|
| S55-A | `_log_runner_response` eleva diagnóstico a `log.warning` | `graph.py` | ✅ |
| S55-B | `_write_artifacts(preserve_nonempty=True)` — guard de no-sobreescritura en retry | `graph.py` | ✅ |
| S55-C | Float hint en tareas de tests — instrucción `round()` en vez de literales | `graph.py` | ✅ |
| S55-D | `update_test_retry` eleva log de archivos en disco a `log.warning` | `graph.py` | ✅ |

---

## S56 — QA contextualizado + logging + Oracle constraints filter (2026-04-26) ✅

**Motivación:** QA score 65/100 persistente por contaminación de contexto Oracle en FRs sin BD. Logs de nodos invisibles. Constraints Oracle aparecían en SDDs de FRs Python puros.

**Resultado ciclo validación:** `8fc60d00` — 2m 31s, QA ronda 2 = 95/100 sdd_compliance=True (mejor de la historia), pero `deliver` reportó 65 (último round). 17 tests S56 nuevos. 1068 tests pasan.

| Item | Descripción | Archivo(s) | Estado |
|------|-------------|-----------|--------|
| S56-A | `_build_qa_sdd_block()` — antepone requirements completos al HumanMessage de QA | `graph.py` | ✅ |
| S56-A | `system_qa.md` — instrucción crítica: evaluar SOLO contra requisitos del SDD listados | `templates/system_qa.md` | ✅ |
| S56-B | `_configure_app_loggers()` — configura `OVD_LOG_LEVEL` en lifespan antes de `assert_env` | `api.py` | ✅ |
| S56-C | `_strip_db_restrictions()` + `_DB_RESTRICTION_KEYWORDS` — filtra restricciones Oracle cuando `oracle_involved=False` | `graph.py` | ✅ |
| S56-D | `_filter_requirements_for_task()` — filtra requirements por `depends_on` para reducir tokens por tarea | `graph.py` | ✅ |

**Deuda identificada en ciclo S56:**
- `deliver` toma QA del último round, no el mejor → resuelto en S57-A
- Tests fallan con collection error en retries → resuelto en S57-B/C/D
- Incremento de tokens (30k→72k) por 2 retries de agentes → mejorará con S57

---

## S57 — QA score reducer + collection errors fix (pendiente)

**Motivación:** En el ciclo S56, el segundo retry degradó el código y el QA bajó de 95 a 65. `deliver` reportó 65 porque toma el último QA, no el mejor. Adicionalmente, los retries de agentes fallan por collection errors (ImportError, conftest desactualizado).

### S57-A — Reducer `_keep_best_qa` en `OVDState` [CRÍTICO]

**Root cause:** `qa_result: dict[str, Any]` sin reducer → LangGraph sobreescribe en cada ronda.
**Fix:** LangGraph 1.1.3 soporta `Annotated[dict, fn]` en TypedDict. Función nombrada (no lambda) para evitar problemas en serialización de checkpoints.

```python
def _keep_best_qa(a: dict, b: dict) -> dict:
    """S57-A: reducer que preserva el mejor resultado QA del ciclo."""
    return a if a.get("score", 0) >= b.get("score", 0) else b

class OVDState(TypedDict):
    qa_result: Annotated[dict, _keep_best_qa]  # antes: dict[str, Any]
```

Sin cambios en `qa_review` ni en `deliver` — transparente para todos los nodos.

| Item | Descripción | Archivo(s) | Estado |
|------|-------------|-----------|--------|
| S57-A | `_keep_best_qa` reducer en `OVDState.qa_result` | `graph.py` | ⬜ |

### S57-B — Corrección exit codes pytest en `run_tests` [ALTO]

**Root cause confirmado (investigación oficial):** pytest exit 4 = `USAGE_ERROR` (flags inválidos), NO collection error. Los `ImportError` reales producen exit 1 con 0 tests pasados.

```python
# S32-C actual (incorrecto):
if proc.returncode == 4:  # "error de colección" ← WRONG

# S57-B (correcto):
if proc.returncode == 4:  # USAGE_ERROR: flags o directorio inválido
if proc.returncode == 1 and "collected 0 items" in output:  # verdadero collection error
```

| Item | Descripción | Archivo(s) | Estado |
|------|-------------|-----------|--------|
| S57-B | Corrección diagnóstico exit codes en `run_tests` (exit 4 ≠ collection error) | `graph.py` | ⬜ |

### S57-C — `conftest.py` regenerado en rounds de retry [ALTO]

**Root cause:** `conftest.py` se inyecta solo si no existe o está vacío (S27-A). En retry, si el agente reorganizó la estructura de código, el conftest viejo apunta a rutas incorrectas → ImportError inevitable en la siguiente ronda.

| Item | Descripción | Archivo(s) | Estado |
|------|-------------|-----------|--------|
| S57-C | Forzar regeneración de `conftest.py` cuando `retry_feedback` presente | `graph.py` | ⬜ |

### S57-D — `preserve_nonempty` en fallback de tool calling [MEDIO]

**Root cause:** El path fallback de `_write_artifacts` (línea ~2098) no pasa `preserve_nonempty` → archivos con contenido válido pueden sobreescribirse con vacío en retry.

| Item | Descripción | Archivo(s) | Estado |
|------|-------------|-----------|--------|
| S57-D | Pasar `preserve_nonempty=bool(retry_feedback)` en fallback de tool calling | `graph.py` | ⬜ |

### S57-Tests

| Item | Descripción | Archivo(s) | Estado |
|------|-------------|-----------|--------|
| S57-E | `test_s57.py` — 12 tests: reducer best QA, exit codes, conftest retry, preserve fallback | `tests/test_s57.py` | ⬜ |

**Proyección post-S57:**

| Métrica | S56 | S57 objetivo |
|---------|-----|-------------|
| QA score reportado | 65 | **95** (preserva mejor) |
| sdd_compliance | False | **True** |
| Tests | FAIL (collection) | exit 0 |
| Retries | 2 | 0–1 |
| Tokens | 72k | ~30k |
| Duración | 2m 31s | ~1m 40s |

---

## S58-pre — Refactoring arquitectura de templates (prerequisito de S58)

**Última iteración:** 2026-04-26 — implementado y validado con 1127/1128 tests PASS.
**Estado:** ✅ Completado — commit `a05258c31` en rama `dev`.

**Motivación:** El modelo actual de templates usa *overrides completos* por stack. Cada archivo stack-specific (`system_backend_python.md`, `system_backend_typescript.md`) es un template independiente que duplica las reglas universales. Esto genera dos problemas:

1. **Deuda de propagación:** cada fix universal (S32-B, S49-B, S40-A, S55-B...) debe replicarse en N archivos. Con S59, S60, etc. acumulando más fixes, el costo crece linealmente con el número de stacks.
2. **Barrera de entrada por stack nuevo:** agregar Go o Java requiere crear un template completo desde cero en vez de solo las reglas específicas del stack.

**Argumento de diseño:** El LLM (qwen3-coder:30b) ya conoce la sintaxis de Python, TypeScript, Rust, Go y todos sus frameworks de test. No necesita que el template le explique cómo usar pytest — necesita que le explique las **convenciones OVD** para ese stack. Separar ambas responsabilidades es la clave.

---

### Arquitectura objetivo

```
templates/
├── system_backend.md         ← UNIVERSAL: reglas OVD que aplican a cualquier stack
├── system_frontend.md        ← UNIVERSAL
├── system_sdd.md             ← UNIVERSAL
├── system_qa.md              ← UNIVERSAL
├── system_security.md        ← UNIVERSAL
├── system_router.md          ← UNIVERSAL
├── system_docs.md            ← UNIVERSAL
│
└── stack/
    ├── backend_python.md     ← Solo convenciones OVD para Python
    ├── backend_typescript.md ← Solo convenciones OVD para TypeScript
    ├── backend_rust.md       ← Solo convenciones OVD para Rust
    ├── backend_java.md       ← Solo convenciones OVD para Java
    ├── backend_go.md         ← Solo convenciones OVD para Go
    ├── frontend_react.md     ← Solo convenciones OVD para React
    ├── frontend_vue.md       ← Solo convenciones OVD para Vue
    ├── database_oracle.md    ← Solo convenciones OVD para Oracle
    └── database_postgresql.md ← Solo convenciones OVD para PostgreSQL
```

**Composición en `template_loader.render()`:**

```python
base = load("system_backend.md")           # reglas universales
stack_section = load(f"stack/backend_{stack_language}.md", default="")  # reglas del stack
return base + "\n\n---\n## Convenciones del stack\n" + stack_section
```

---

### Separación de responsabilidades

**`system_backend.md` (universal) — qué incluye:**
- Orden de escritura de archivos (S32-B): infraestructura primero, negocio después
- Máximo 5 tareas por agente (S49-B)
- Prohibición de placeholders y código incompleto (S40-A)
- Estructura de directorios (`src/<modulo>/`)
- Tarea de tests obligatoria por agente
- Regla de no modificar tests en retry (S33-A)
- Deduplicación de artefactos

**`stack/backend_python.md` — qué incluye:**
- Tests en `tests/test_<modulo>.py` con pytest
- `__init__.py` es el primer archivo a escribir (S32-B Python-specific)
- `conftest.py` con `sys.path.insert(0, "src")`
- `round()` para assertions de float (S55-C)
- Pydantic v2 con `@field_validator` + `@classmethod` (S50-C)
- `pytest.ini` con `testpaths = tests`

**`stack/backend_typescript.md` — qué incluye:**
- Tests en `tests/<modulo>.test.ts` con Vitest
- `vitest.config.ts` con `globals: true, environment: "node"`
- `toFixed(2)` o `Math.abs(a-b) < 0.01` para float assertions
- Zod para validación de schemas
- `tsconfig.json` paths y `"moduleResolution": "bundler"`

**`stack/backend_rust.md` — qué incluye:**
- Unit tests: `#[cfg(test)] mod tests {}` inline en `src/lib.rs`
- Integration tests: `tests/` directorio independiente
- `assert!((result - expected).abs() < 1e-2)` para float assertions
- `Cargo.toml` con sección `[dev-dependencies]`

---

### Investigación de componentes (2026-04-26)

Investigación exhaustiva realizada antes de implementar. Hallazgos críticos que refinan el plan original:

#### Hallazgo 1 — Templates actuales son 5x más largos que el óptimo

Investigación 2024-2025 establece rango óptimo de 1,000–1,500 tokens para system prompts:

| Template | Líneas | Tokens estimados | Estado |
|----------|--------|-----------------|--------|
| `system_backend.md` | 319 | ~8,000 | ❌ 5x sobre límite |
| `system_frontend_react.md` | 538 | ~13,000 | ❌ 9x sobre límite |
| `system_backend_python.md` | 222 | ~5,500 | ❌ 4x sobre límite |
| `system_backend_typescript.md` | 104 | ~2,500 | ⚠️ 2x sobre límite |
| `system_sdd.md` | 194 | ~4,800 | ❌ 3x sobre límite |

**Causa del impacto:** "Lost in the Middle" afecta al system prompt igual que al contexto. Con prompts de 8K tokens, instrucciones en el medio se atienden menos — explicando por qué el LLM ignora algunas reglas de los templates aunque estén escritas. Reorganizar el orden (crítico al inicio/final) es la corrección segura. Reducir tamaño es una optimización posterior que requiere evidencia empírica.

**Meta de S58-pre:** Separar responsabilidades — reglas universales en base, convenciones de stack en archivos `stack/`. El objetivo es organización y transversalidad, **no reducción de tamaño**. La reducción de tamaño es Fase 2 (post-validación, ver sección "Fase 2" al final de S58-pre).

#### Hallazgo 2 — Patrón de composición correcto: concatenación simple

Tres patrones disponibles en LangChain/LangGraph analizados:

| Patrón | Complejidad | Compatible con OVD | Recomendado |
|--------|-------------|-------------------|-------------|
| A — Concatenación de strings | Mínima | ✅ Sí | ✅ **Usar este** |
| B — ChatPromptTemplate | Media | ⚠️ Requiere `.format()` extra | No |
| C — PipelinePromptTemplate | Alta | ❌ Innecesariamente complejo | No |

LangGraph no tiene límite en `SystemMessage(content: str)`. El prompt caching de Anthropic funciona con strings concatenados. No hay breaking changes.

**Implementación en `template_loader.py`** — nueva función `render_composed()`:

```python
def render_composed(
    name: str,
    language: str = "es",
    stack_language: str = "",
    **variables,
) -> str:
    """S58-pre: carga base universal + sección de stack y compone en string único."""
    # 1. Base universal (reglas OVD que aplican a cualquier stack)
    base = render(name, language=language, **variables)

    # 2. Sección de stack (convenciones OVD específicas del lenguaje)
    stack_key = f"stack/{name.replace('system_', '')}_{stack_language}"
    stack_section = ""
    stack_path = _TEMPLATES_DIR / f"{stack_key}.md"
    if stack_language and stack_path.exists():
        raw = stack_path.read_text(encoding="utf-8")
        stack_section = _interpolate(raw, **variables)

    if stack_section:
        return f"{base}\n\n---\n## Convenciones del stack ({stack_language})\n{stack_section}"
    return base
```

#### Hallazgo 3 — Cache no es thread-safe

El `_cache: dict[str, str]` en `template_loader.py` no tiene locks. Con múltiples ciclos concurrentes (requests simultáneos al engine), hay riesgo de race condition en la primera carga. Solución: `threading.Lock` en la función `load()`.

```python
_cache_lock = threading.Lock()

def load(name, language="es", stack_language="") -> str:
    key = f"{language}:{stack_language}:{name}"
    with _cache_lock:
        if key in _cache:
            return _cache[key]
        # ... carga y guarda en cache
```

#### Hallazgo 4 — Duplicación confirmada entre templates

`system_backend.md` (319 líneas) y `system_backend_python.md` (222 líneas) comparten las primeras ~100 líneas idénticas (seguridad obligatoria, reglas de implementación, multi-tenancy). Las divergencias reales comienzan en línea ~80. `system_frontend_react.md` (538 líneas) es el más candidato a reducción.

#### Hallazgo 5 — Tests actuales no validan contenido

`test_s42.py` verifica que los templates se cargan y cachean correctamente, pero **no hay tests que validen el contenido de los .md**. Esto significa que una instrucción crítica puede eliminarse accidentalmente sin que ningún test falle.

---

### Plan de implementación — refinado

| Item | Descripción | Archivos | Estado |
|------|-------------|---------|--------|
| TP-1 | **Mover (no eliminar)** todo lo Python-specific de `system_backend.md` a `stack/backend_python.md` — el template base queda con reglas verdaderamente universales | `templates/system_backend.md` | ⬜ |
| TP-2 | Crear `stack/backend_python.md` (contenido v1 especificado abajo) | `templates/stack/` | ⬜ |
| TP-3 | Crear `stack/backend_typescript.md` (contenido v1 especificado abajo) | `templates/stack/` | ⬜ |
| TP-4 | Crear `stack/backend_rust.md` (nuevo stack, contenido v1) | `templates/stack/` | ⬜ |
| TP-5 | Crear `stack/backend_java.md` y `stack/backend_go.md` (nuevos stacks) | `templates/stack/` | ⬜ |
| TP-6 | Agregar `render_composed()` a `template_loader.py` + fix thread-safety del cache | `template_loader.py` | ⬜ |
| TP-7 | Actualizar llamadas en `graph.py` de `render()` a `render_composed()` en los 4 agentes de código | `graph.py` líneas 1179, 1203, 1227, 1251 | ⬜ |
| TP-8 | Reducir `system_frontend_react.md` (538 líneas) — extraer a `stack/frontend_react.md` | `templates/` | ⬜ |
| TP-9 | Migrar `system_database_oracle.md` y `system_database_postgresql.md` al esquema `stack/` | `templates/stack/` | ⬜ |
| TP-10 | Tests de contenido: verificar que instrucciones críticas existen en los archivos correctos | `tests/test_s58pre.py` | ⬜ |
| TP-11 | Tests de composición: `render_composed()` produce output correcto por stack | `tests/test_s58pre.py` | ⬜ |
| TP-12 | Tests de regresión: ciclo IMC Python produce mismo resultado antes/después | Ciclo end-to-end | ⬜ |

**Criterio de éxito:**
- **Cero regresión vs S57**: QA score, tests PASS y duración de ciclo IMC Python equivalentes o mejores al baseline S57
- 0 instrucciones críticas perdidas en la migración — todas las reglas del template actual están presentes en el template compuesto (`base + stack`), en el nivel correcto (validado por TP-10)
- `render_composed("system_backend", stack_language="python")` produce el mismo contenido efectivo que `system_backend.md` actual + todo lo específico de Python que estaba en `system_backend_python.md`
- Ciclos con FR TypeScript y Rust completan sin recibir instrucciones Python irrelevantes (validado por TP-12 multi-stack)

> **Nota:** La reducción de tamaño de tokens NO es criterio de éxito de S58-pre. Es un objetivo separado de Fase 2 (ver abajo), que requiere evidencia empírica antes de ejecutarse.

### Fase 2 — Reducción de tamaño (post-validación, sprint futuro S60+)

**Contexto:** S58-pre reorganiza sin reducir. La reducción de tokens es un objetivo válido — pero requiere evidencia empírica para no destruir instrucciones que funcionan.

#### ¿Se puede automatizar la Fase 2?

**Respuesta corta:** semi-automática y data-driven, con trigger manual.

**Por qué no puede ser 100% automática hoy:**
- Eliminar una instrucción y medir si el QA baja requiere ciclos A/B controlados: misma FR, dos versiones del template. OVD no tiene esa infraestructura de testing de templates.
- Riesgo de falso positivo: una instrucción puede no activarse en 5 ciclos de validación y parecer "inútil", pero es crítica para FRs poco frecuentes (validación RUT, Oracle, WebSocket).

**Lo que SÍ se puede automatizar (S60+):**
- OVD ya registra `prompt_eval_count` por ciclo (S55-A). Un script post-ciclo puede generar un reporte de tokens promedio por template y stack.
- Bloques de instrucciones marcados con `# CANDIDATE_REMOVE` en el .md pueden ser excluidos en una variante de template para ciclos de prueba.
- Si N ciclos consecutivos con el bloque removido mantienen QA ≥ baseline S57, el bloque se confirma como candidato real a eliminar.

**Flujo propuesto (S60+):**
```
ciclo → log prompt_eval_count
→ análisis batch (script manual) → identificar bloques candidatos
→ ciclos A/B disparados manualmente → comparar QA + tests PASS
→ si sin regresión: eliminar bloque del template
→ commit + nuevo baseline
```

El **trigger es manual** (Omar ejecuta el análisis), pero la **evidencia es automática** (datos de `ovd_cycles`). Esto garantiza que cada reducción tiene respaldo empírico y no está basada en intuición sobre qué instrucciones son "necesarias".

**Cuándo ejecutar Fase 2:** después de que S58-pre valide con al menos 3 stacks distintos (Python, TypeScript, Rust) y los ciclos sean estables.

---

### Especificación de contenido — templates de stack (v1)

**Contexto:** El plan TP-2 a TP-7 dice "crear el archivo" pero no especifica qué escribir en él. Este bloque define el contenido base de cada template. Es parte integral de la implementación — no es opcional.

**Principio de los archivos v1:** el contenido está derivado de los fixes ya validados en S27–S57. No son templates teóricos — son las instrucciones que se sabe que el LLM necesita porque su ausencia causó bugs documentados. Evolucionan con cada ciclo de validación.

#### `templates/stack/backend_python.md` — v1

```markdown
## Convenciones OVD — Python

### ORDEN DE ESCRITURA (obligatorio, S32-B)
1. `src/<paquete>/__init__.py` ← PRIMERO, aunque esté vacío
2. `src/<paquete>/models.py`
3. `src/<paquete>/service.py`
4. `src/<paquete>/router.py` o `src/main.py`
5. `tests/test_<paquete>.py` ← ÚLTIMO

### Infraestructura obligatoria (S23-D, S27-A)
- `src/<paquete>/__init__.py` — vacío, habilita imports entre módulos
- `conftest.py` en raíz:
  import sys, os
  sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
- `pytest.ini`:
  [pytest]
  testpaths = tests

### Tests (S51-A, S51-B)
- Ruta: `tests/test_<paquete>.py`
- Runner: pytest
- Mínimo 3 casos: happy path, valor límite, error esperado
- NUNCA modificar tests en retry — solo corregir implementación (S33-A)

### Validación de datos (S50-C)
- Pydantic v2 exclusivamente
- Validators: `@field_validator` + `@classmethod`
- PROHIBIDO: `@validator` (deprecado), `dict()` → usar `.model_dump()`

### Assertions de float (S55-C, S36-B)
- NUNCA hardcodear valores float de memoria en asserts
- SIEMPRE calcular con la misma fórmula de la implementación:
  # implementación: return round(peso / altura ** 2, 2)
  # test:           assert calcular_imc(65, 1.72) == round(65 / 1.72 ** 2, 2)

### Frameworks disponibles (usar según {project_context})
- FastAPI, Django, Flask → APIs REST
- SQLAlchemy 2.x, Alembic → ORM + migraciones
- httpx → cliente HTTP async
- Redis-py → caché y colas
```

#### `templates/stack/backend_typescript.md` — v1

```markdown
## Convenciones OVD — TypeScript

### ORDEN DE ESCRITURA (obligatorio)
1. `tsconfig.json` ← PRIMERO
2. `package.json` con scripts: dev, build, test
3. `src/<modulo>/types.ts` — interfaces y tipos
4. `src/<modulo>/<modulo>.ts` — implementación
5. `tests/<modulo>.test.ts` ← ÚLTIMO

### Infraestructura obligatoria
- `tsconfig.json`: { "compilerOptions": { "strict": true, "moduleResolution": "bundler" } }
- `vitest.config.ts`:
  import { defineConfig } from "vitest/config";
  export default defineConfig({ test: { globals: true, environment: "node" } });

### Tests (S58-A)
- Ruta: `tests/<modulo>.test.ts` o `<modulo>.spec.ts`
- Runner: Vitest
- Mínimo 3 casos por función

### Validación de datos
- Zod para schemas de entrada en endpoints
- Tipos explícitos en todas las funciones — sin `any`

### Assertions de float (S58-B)
- expect(Number(calcularImc(65, 1.72).toFixed(2))).toBe(21.97)
- O validar por diferencia: expect(Math.abs(result - 21.97)).toBeLessThan(0.01)

### Frameworks disponibles (usar según {project_context})
- Express, Hono, NestJS → APIs REST
- Prisma, Drizzle, TypeORM → ORM
- Zod → validación de schemas
- tRPC → APIs type-safe
```

#### `templates/stack/backend_rust.md` — v1

```markdown
## Convenciones OVD — Rust

### ORDEN DE ESCRITURA (obligatorio)
1. `Cargo.toml` ← PRIMERO con [dependencies] y [dev-dependencies]
2. `src/lib.rs` — punto de entrada y módulos públicos
3. `src/<modulo>.rs` — implementación por módulo
4. Tests inline al final de cada módulo (S58-A)

### Infraestructura obligatoria
- `Cargo.toml` con sección [dev-dependencies] para dependencias de test
- No se requiere archivo de configuración externo — cargo test funciona nativamente

### Tests (S58-A)
- Unit tests: inline en cada módulo src/
  #[cfg(test)]
  mod tests {
      use super::*;
      #[test]
      fn test_caso() { assert_eq!(funcion(x), esperado); }
  }
- Integration tests: archivos en `tests/` sin #[cfg(test)]
- Runner: cargo test opera sobre el proyecto completo — no archivos individuales

### Assertions de float (S58-B)
- NUNCA comparar floats con ==
- assert!((calcular_imc(65.0, 1.72) - 21.97_f64).abs() < 1e-2)

### Frameworks disponibles (usar según {project_context})
- Actix-web, Axum, Rocket → APIs REST
- SQLx, Diesel → acceso a BD async/sync
- Serde → serialización JSON
- Tokio → runtime async
```

#### `templates/stack/backend_java.md` — v1

```markdown
## Convenciones OVD — Java

### ORDEN DE ESCRITURA (obligatorio)
1. `pom.xml` o `build.gradle` ← PRIMERO
2. `src/main/java/<paquete>/model/` — entidades y DTOs
3. `src/main/java/<paquete>/service/` — lógica de negocio
4. `src/main/java/<paquete>/controller/` — endpoints REST
5. `src/test/java/<paquete>/` — tests ← ÚLTIMO

### Infraestructura obligatoria
- Estructura Maven estándar: src/main/java/ y src/test/java/
- pom.xml con JUnit 5: groupId org.junit.jupiter, artifactId junit-jupiter, scope test

### Tests
- Ruta: `src/test/java/<paquete>/<Modulo>Test.java`
- Runner: JUnit 5 — usar @Test, @BeforeEach, @ParameterizedTest
- Mínimo 3 casos por método

### Assertions de float
- assertEquals(21.97, calcularImc(65.0, 1.72), 0.01);
- El tercer parámetro es el delta permitido

### Frameworks disponibles (usar según {project_context})
- Spring Boot → APIs REST + inyección de dependencias
- Hibernate / JPA → ORM
- Flyway → migraciones de BD
- Lombok → @Data, @Builder, @Slf4j
- MapStruct → mapeo DTO ↔ entidad
```

#### `templates/stack/backend_go.md` — v1

```markdown
## Convenciones OVD — Go

### ORDEN DE ESCRITURA (obligatorio)
1. `go.mod` ← PRIMERO con nombre de módulo y versión Go
2. `internal/<modulo>/<modulo>.go` — implementación
3. `internal/<modulo>/<modulo>_test.go` — tests en mismo paquete
4. `cmd/main.go` — entrypoint

### Infraestructura obligatoria
- `go.mod`: module github.com/<org>/<repo>
- Tests en mismo directorio que el código con sufijo _test.go
- No se requiere configuración adicional — go test funciona nativamente

### Tests
- Archivo: `<modulo>_test.go` en mismo directorio que el código
- Función: func Test<Nombre>(t *testing.T)
- Runner: go test ./... cubre todo el proyecto
- Mínimo 3 casos por función

### Assertions de float
- if math.Abs(resultado - 21.97) > 0.01 { t.Errorf(...) }

### Frameworks disponibles (usar según {project_context})
- Gin, Echo, Fiber → APIs REST
- GORM, sqlx → ORM y acceso a BD
- pgx → PostgreSQL nativo async
```

#### `templates/stack/frontend_react.md` — v1

```markdown
## Convenciones OVD — React / TypeScript

### ORDEN DE ESCRITURA (obligatorio)
1. `vitest.config.ts` ← PRIMERO
2. `src/setupTests.ts` con imports de Testing Library
3. `src/components/<Componente>/<Componente>.tsx`
4. `src/components/<Componente>/<Componente>.test.tsx` ← ÚLTIMO

### Infraestructura obligatoria
- vitest.config.ts:
  import { defineConfig } from "vitest/config";
  export default defineConfig({ test: { globals: true, environment: "jsdom",
    setupFiles: ["./src/setupTests.ts"] } });
- src/setupTests.ts:
  import "@testing-library/jest-dom";

### Tests (S40-C)
- Ruta: `src/components/<Componente>/<Componente>.test.tsx`
- Runner: Vitest + Testing Library
- Mínimo: render sin crash + interacción principal + estado de error
  import { render, screen } from "@testing-library/react";
  it("renders", () => { render(<Componente />); expect(screen.getByRole(...)).toBeInTheDocument(); });

### Convenciones de código
- React 19 — sin class components
- Hooks propios en `src/hooks/use<Nombre>.ts`
- Props tipadas con interface — sin `any`

### Frameworks disponibles (usar según {project_context})
- React Query / SWR → fetching de datos
- Zustand / Jotai → estado global
- React Hook Form + Zod → formularios con validación
- Tailwind CSS → estilos
- React Router v6 → routing client-side
```

---

### Evolución de los templates v1

Cada archivo es un documento vivo. El patrón de evolución es el mismo que S27–S57:

| Disparador | Acción |
|-----------|--------|
| Ciclo de validación revela gap | Agregar instrucción al template del stack afectado |
| Fix nuevo en graph.py requiere instrucción al LLM | Evaluar si va en template universal o en stack section |
| Nuevo stack agregado al proyecto | Crear `stack/backend_<lenguaje>.md` con estructura base |
| Instrucción que aplica a todos los stacks | Mover de stack section a `system_backend.md` |

**No esperar al template perfecto.** v1 entra en producción, los ciclos revelan los gaps, v2 los corrige.

---

### Beneficio para S58

Con esta arquitectura, los items S58-A a S58-F se simplifican:
- S58-A (instrucción test path): ya estará en `stack/backend_{stack}.md` — no necesita lógica condicional en `graph.py`
- S58-B (float hint): ya estará en `stack/backend_{stack}.md`
- S58-F (system_sdd.md): puede usar la misma composición para la sección de tests

Los items S58-C, S58-D, S58-E (lógica en `run_tests`) siguen siendo cambios en `graph.py` — no los afecta este refactoring.

---

### ADR-01 — Templates en filesystem vs PostgreSQL (decisión 2026-04-26)

**Pregunta:** ¿Deberían los archivos `.md` de templates almacenarse en PostgreSQL en vez del repositorio?

**Decisión: mantener templates base en el repositorio. Overrides por proyecto en PostgreSQL.**

#### Argumentos que definen la decisión

Los templates definen el **comportamiento del LLM** en cada nodo del grafo. Cambiar una línea en `system_backend.md` cambia cómo el agente escribe código en todos los proyectos. Eso los hace funcionalmente equivalentes a código fuente — no a datos de usuario.

| Criterio | Filesystem (repo) | PostgreSQL |
|----------|-------------------|-----------|
| Historial de cambios | Git nativo — cada fix tiene commit, mensaje y contexto (S32, S40, S50...) | Requiere implementar auditoría paralela |
| Validación antes de producción | CI/CD automático — tests de contenido corren en cada PR | Manual o sin validación — prompt malo llega a producción directo |
| Tests de contenido | Directos — leen el `.md` desde disco | Requieren seed de BD o mocks — tests más frágiles |
| Latencia de carga | Cero — cache en RAM después del primer load | Query inicial por instancia del engine |
| Dev local sin BD | Funciona sin PostgreSQL | Engine no puede arrancar sin conexión |
| Fallback inline (`_FALLBACK_PROMPTS`) | Una sola fuente de verdad | Tres fuentes en conflicto: BD + disco + inline |

**Lo que PostgreSQL NO resuelve bien para templates base:**
- *Hot reload sin reiniciar* — los templates base cambian cada días/semanas (no en runtime). El costo de reiniciar el engine es mínimo vs el riesgo de edición sin validación.
- *Edición desde dashboard* — un prompt de producción editable desde UI sin tests es equivalente a editar código Python directamente en producción.
- *Multi-organización* — ese es el problema de overrides por proyecto, no de templates base.

#### Arquitectura híbrida resultante

```
FILESYSTEM (git-versioned)              POSTGRESQL
────────────────────────────────        ─────────────────────────────────
Templates base — comportamiento         Overrides por proyecto — configuración
del sistema OVD para todos:            de usuario, sin afectar el sistema base:

  templates/system_backend.md            ovd_project_custom_templates
  templates/stack/backend_python.md        (project_id, template_name,
  templates/stack/backend_typescript.md    content, version, active)
  ...
                                        A/B experiments (futuro):
Código → git → CI/CD → review           ovd_template_experiments
```

El override por proyecto es la capa faltante — actúa **sobre** la base en disco, no la reemplaza. La función `template_loader.render()` quedaría:

```python
def render(name, language, stack_language, **vars):
    # 1. Base universal (disco)
    base = load(f"system_{name}.md")
    # 2. Sección de stack (disco)
    stack_section = load(f"stack/{name}_{stack_language}.md", default="")
    # 3. Override por proyecto (PostgreSQL) — futuro S60/C10
    project_override = db_load(project_id, name, default="")
    return compose(base, stack_section, project_override, **vars)
```

**Pendiente de implementar (S60 o C10):** tabla `ovd_project_custom_templates` + endpoint API + UI en dashboard para editar overrides por proyecto.

---

### ADR-02 — Cómo fluyen frameworks y librerías al LLM (diseño 2026-04-26)

**Pregunta:** ¿Cómo sabe el LLM qué frameworks y librerías usar en cada proyecto? ¿Necesita templates por framework?

#### Principio base

El LLM (qwen3-coder:30b) ya conoce FastAPI, SQLAlchemy, Prisma, Hibernate, Actix-web y el resto — están en su entrenamiento. **No necesita que el template le enseñe el framework.** Solo necesita dos cosas:

1. **Cuál usar** → viene del perfil del proyecto (`{project_context}`)
2. **Cómo estructurarlo en OVD** → viene del template de stack

#### Los tres niveles que se combinan en cada llamada al LLM

```
NIVEL 1 — Template universal (system_backend.md)
  Reglas OVD independientes de lenguaje y framework
  Ej: "escribe infraestructura primero", "máx 5 tareas", "sin placeholders"

NIVEL 2 — Sección de lenguaje (stack/backend_python.md)
  Convenciones OVD para el lenguaje, agnóstico al framework concreto
  Ej: "pytest en tests/test_*.py", "Pydantic v2", "round() en asserts"

NIVEL 3 — {project_context} con framework y librerías específicas
  Qué usa ESTE proyecto — viene de ovd_project_profiles
  Ej: "Framework: FastAPI / Stack: SQLAlchemy, Redis, Alembic"
```

El LLM combina los tres: genera código FastAPI + SQLAlchemy con estructura OVD Python.

#### Cuándo SÍ se necesita un template por framework

Solo cuando el framework impone patrones OVD tan diferentes que el `{project_context}` no es suficiente. Criterio: si dos proyectos del mismo lenguaje tienen convenciones OVD completamente distintas entre sí.

Ejemplos que SÍ justificarían un cuarto nivel (`stack/backend_python_fastapi.md`):
- FastAPI async vs Django sync — estructuras de proyecto radicalmente distintas
- SQLAlchemy Core vs ORM — patrones de query incompatibles

Ejemplos que NO lo justifican (el `{project_context}` es suficiente):
- FastAPI vs Flask — el LLM adapta el estilo solo con saber el framework
- SQLAlchemy vs Peewee — diferencia de librería, no de patrón OVD

**Regla práctica:** empezar con dos niveles (universal + lenguaje). Agregar el cuarto nivel solo cuando un ciclo real falle por ambigüedad de framework — no de forma preventiva.

#### Campos del perfil que alimentan el nivel 3

| Campo | Impacto en el LLM | Estado actual |
|-------|------------------|---------------|
| `framework` | El LLM elige el framework correcto | ✅ En formulario — texto libre |
| `additional_stack` | El LLM incluye las librerías en requirements/package.json | ⚠️ En BD, oculto en formulario |
| `test_framework` | El LLM usa el runner correcto desde el primer ciclo | ❌ No existe — propuesto en S58 |
| `qa_tools` | El LLM incluye ruff/eslint/mypy en la configuración | ⚠️ En BD, oculto en formulario |
| `external_integrations` | El LLM no inventa sistemas de auth o APIs ya existentes | ⚠️ En BD, oculto en formulario |

#### Ejemplo de flujo completo

```
Proyecto: "API contratos" / Python / FastAPI / PostgreSQL

Nivel 1 (universal):  "escribe __init__.py primero, máx 5 tareas"
Nivel 2 (python):     "tests con pytest, Pydantic v2, round() en asserts"
Nivel 3 (proyecto):   "FastAPI, SQLAlchemy, Redis, Alembic, PostgreSQL 16"
+ rag_context:        "ciclo anterior: endpoint /contratos usa JWT Bearer"
        ↓
LLM genera sin instrucciones adicionales:
  src/contratos/models.py     ← SQLAlchemy models (sabe usarlo)
  src/contratos/service.py    ← lógica de negocio
  src/contratos/router.py     ← FastAPI router con JWT (lo infiere del contexto)
  src/contratos/cache.py      ← Redis integration
  tests/test_contratos.py     ← pytest con patrones OVD
```

---

### Contenido de los templates de stack — especificación de implementación

**Aclaración crítica sobre el plan TP-1 a TP-8:** los items TP-2, TP-3 y TP-4 dicen "crear `stack/backend_python.md`" pero no especifican el contenido. Este análisis define qué debe ir en cada archivo. Es parte integral de la implementación de S58-pre — no es opcional.

#### `stack/backend_python.md` — contenido requerido

```markdown
## Convenciones OVD — Python

### Infraestructura (escribir PRIMERO antes que cualquier módulo)
- `src/<paquete>/__init__.py` — archivo vacío, habilita imports
- `conftest.py` en raíz con `sys.path.insert(0, "src")`
- `pytest.ini` con `testpaths = tests`

### Tests
- Archivo: `tests/test_<modulo>.py`
- Runner: pytest
- Mínimo 3 casos por función: happy path, valor límite, error esperado

### Validación de datos
- Usar Pydantic v2 exclusivamente
- Validators: `@field_validator` + `@classmethod` (NO `@validator` — deprecado)
- Nunca usar `dict()` — usar `.model_dump()`

### Assertions de float en tests
- NUNCA hardcodear valores float de memoria
- SIEMPRE calcular con round(): `round(65 / 1.72**2, 2)` → 21.97
- El assert usa el mismo resultado: `assert resultado == 21.97`

### Frameworks disponibles (usar según {project_context})
- FastAPI + Pydantic v2 — APIs REST async
- SQLAlchemy 2.x — ORM (preferir async cuando el proyecto lo requiera)
- Alembic — migraciones de BD
- httpx — cliente HTTP async
- Redis-py — cache y colas
```

#### `stack/backend_typescript.md` — contenido requerido

```markdown
## Convenciones OVD — TypeScript

### Infraestructura (escribir PRIMERO)
- `tsconfig.json` con `"strict": true, "moduleResolution": "bundler"`
- `package.json` con scripts: `dev`, `build`, `test`
- `vitest.config.ts` con `globals: true, environment: "node"`

### Tests
- Archivo: `tests/<modulo>.test.ts` o `<modulo>.spec.ts`
- Runner: Vitest
- Mínimo 3 casos por función

### Validación de datos
- Usar Zod para schemas de entrada en endpoints
- Tipos explícitos en todas las funciones — sin `any`

### Assertions de float en tests
- Usar `expect(Number(value.toFixed(2))).toBe(21.97)`
- O validar con `Math.abs(result - expected) < 0.01`

### Frameworks disponibles (usar según {project_context})
- Express / Hono / NestJS — APIs REST
- Prisma / Drizzle / TypeORM — ORM
- Zod — validación de schemas
- tRPC — APIs type-safe (si el proyecto lo indica)
```

#### `stack/backend_rust.md` — contenido requerido

```markdown
## Convenciones OVD — Rust

### Infraestructura (escribir PRIMERO)
- `Cargo.toml` con secciones `[dependencies]` y `[dev-dependencies]`
- `src/lib.rs` como punto de entrada de la librería

### Tests
- Unit tests: `#[cfg(test)] mod tests {}` inline en cada módulo `src/`
- Integration tests: archivos independientes en `tests/` (sin #[cfg(test)])
- Runner: cargo test — opera sobre el proyecto completo, no archivos individuales

### Assertions de float en tests
- Usar `assert!((result - expected).abs() < 1e-2)`
- Nunca comparar floats con `==`

### Frameworks disponibles (usar según {project_context})
- Actix-web / Axum / Rocket — APIs REST
- SQLx / Diesel — acceso a BD
- Serde — serialización JSON
- Tokio — runtime async
```

#### `stack/backend_java.md` — contenido requerido

```markdown
## Convenciones OVD — Java

### Infraestructura (escribir PRIMERO)
- `pom.xml` (Maven) o `build.gradle` (Gradle) según {project_context}
- Estructura: `src/main/java/` para código, `src/test/java/` para tests

### Tests
- Archivo: `src/test/java/<paquete>/Test<Modulo>.java`
- Runner: JUnit 5 con `@Test`, `@BeforeEach`, `@ParameterizedTest`
- Mínimo 3 casos por método

### Frameworks disponibles (usar según {project_context})
- Spring Boot — APIs REST + inyección de dependencias
- Hibernate / JPA — ORM
- Flyway / Liquibase — migraciones
- MapStruct — mapeo de DTOs
- Lombok — reducción de boilerplate
```

#### `stack/frontend_react.md` — contenido requerido

```markdown
## Convenciones OVD — React / TypeScript

### Infraestructura (escribir PRIMERO)
- `vitest.config.ts` con `globals: true, environment: "jsdom"`
- `src/setupTests.ts` con `import "@testing-library/jest-dom"`

### Tests
- Archivo: `src/components/<Componente>.test.tsx`
- Runner: Vitest + Testing Library
- Mínimo: render sin crash + interacción principal + estado de error

### Librerías disponibles (usar según {project_context})
- React 19 + hooks — sin class components
- React Query / SWR — fetching de datos
- Zustand / Jotai — estado global (preferir sobre Redux para proyectos nuevos)
- React Hook Form + Zod — formularios con validación
- Tailwind CSS — estilos (si el proyecto lo indica)
```

---

### ADR-03 — Arquitectura de conocimiento del LLM (diseño 2026-04-26)

**Pregunta:** Cuando el LLM no tiene el conocimiento necesario para un FR — porque la tecnología es nueva, niche o interna — ¿cómo lo obtiene? ¿MCP servers o web_research?

**Respuesta:** No son alternativas — son capas complementarias. Cada una resuelve un tipo distinto de brecha.

---

#### Las 5 capas de conocimiento

```
┌─────────────────────────────────────────────────────────────────┐
│  CAPA 1 — Entrenamiento del LLM          sin red, siempre       │
│  CAPA 2 — Templates .md                  sin red, estático      │
│  CAPA 3 — RAG / {rag_context}            pgvector, por ciclo    │
│  CAPA 4 — web_research_node              red, runtime           │
│  CAPA 5 — MCP servers                    red, runtime           │
└─────────────────────────────────────────────────────────────────┘
```

---

#### Capa 1 — Entrenamiento del LLM

Lo que el modelo sabe por su entrenamiento (cutoff agosto 2025 para qwen3-coder:30b):

| Cobertura | Ejemplos |
|-----------|---------|
| ✅ Disponible | FastAPI, SQLAlchemy 2.x, Pydantic v2, React 19, Prisma, Axum, pytest, Vitest, JUnit 5, Docker, PostgreSQL, Redis |
| ✅ Disponible | Patrones de código, algoritmos, estructuras de datos en 119 lenguajes |
| ❌ No disponible | Librerías lanzadas después del cutoff |
| ❌ No disponible | Versiones con breaking changes posteriores al cutoff |
| ❌ No disponible | Frameworks internos o propietarios de cada cliente |

> **Nota — pendiente resolver (futuro cercano):** definir proceso para actualizar el cutoff de conocimiento cuando se cambie de modelo LLM. Cada modelo tiene su propia fecha de corte — documentar en el perfil del modelo en `.env` para que los agentes sepan qué pueden asumir sin verificar.

---

#### Capa 2 — Templates .md

Lo que el LLM sabe pero aplica incorrectamente sin instrucción explícita — las convenciones OVD:

| Cobertura | Ejemplos |
|-----------|---------|
| ✅ Resuelve | Pydantic v2 en vez de v1 — el LLM conoce ambas, el template le dice cuál usar (S50-C) |
| ✅ Resuelve | `round()` para float assertions — el LLM no lo haría solo sin instrucción (S55-C) |
| ✅ Resuelve | Orden de escritura de archivos — convención OVD, no estándar del lenguaje (S32-B) |
| ❌ No resuelve | Conocimiento que el LLM no tiene — el template no puede inventar lo que no existe en entrenamiento |
| ❌ No resuelve | Tecnologías post-cutoff — el template puede mencionar el nombre pero no los patrones correctos |

> **Nota — pendiente resolver (S58-pre):** completar los templates v1 de stack con el contenido especificado en este roadmap. Hasta que TP-2 a TP-7 estén implementados, la capa 2 cubre solo Python.

---

#### Capa 3 — RAG / {rag_context} / {lessons_context}

Conocimiento acumulado de ciclos anteriores del mismo proyecto, indexado en pgvector:

| Cobertura | Ejemplos |
|-----------|---------|
| ✅ Resuelve | "En ciclo anterior el endpoint /contratos falló con JWT mal configurado" |
| ✅ Resuelve | "El proyecto usa oracle-thick mode — documentado en 3 ciclos anteriores" |
| ✅ Resuelve | Documentación interna indexada manualmente en pgvector |
| ❌ No resuelve | Tecnologías nuevas que nunca han aparecido en un ciclo OVD anterior |
| ❌ No resuelve | Documentación del cliente no indexada aún |

> **Nota — pendiente resolver (futuro cercano):** hoy la indexación de documentación interna del cliente es manual. Diseñar un mecanismo de indexado batch desde rutas configuradas por proyecto (ej: directorio de docs, URL de Confluence, repositorio de specs). Candidato para S60 o C10.

---

#### Capa 4 — web_research_node

Conocimiento dinámico obtenido en runtime durante el ciclo — documentación actual, changelogs, APIs recientes:

| Cobertura | Ejemplos |
|-----------|---------|
| ✅ Resuelve | Librería reciente posterior al cutoff del LLM |
| ✅ Resuelve | Breaking changes en versión nueva de un framework conocido |
| ✅ Resuelve | Verificar API actual de una librería que puede haber cambiado |
| ❌ No resuelve | Documentación interna no publicada en internet |
| ❌ No resuelve | APIs privadas del cliente |

**Estado actual (documentado en S48):**

| Problema | Impacto |
|----------|---------|
| Activo en <10% de los ciclos | El analizador de FR no detecta cuándo activarlo |
| Un solo proveedor sin fallback | Si falla, el nodo falla silenciosamente |
| Cache definido pero nunca consultado | Cada ciclo refetch aunque ya investigó lo mismo |
| RAG indexing depende del Bridge | Los findings se pierden si el Bridge está caído |

> **Nota — pendiente resolver (S48):** implementar multi-proveedor con failover (Tavily → Brave → SearXNG → DuckDuckGo), cache real con TTL, criterio explícito de activación basado en detección de tecnologías desconocidas en el FR, e indexado robusto independiente del Bridge.

---

#### Capa 5 — MCP servers

Fuentes de conocimiento especializadas o privadas, accesibles en runtime:

| Servidor | Cobertura | Estado |
|----------|-----------|--------|
| **context7** | Documentación live de librerías open source — verifica API actual antes de generar código | ✅ Activo desde S38 |
| **Oracle MCP** | Esquemas, tablas y datos de BD Oracle del cliente | ✅ Activo |
| **MCP custom cliente** | APIs internas, Confluence, Notion, Swagger privado | ❌ Requiere S44 |
| **MCP BD interna** | Documentación técnica del cliente no publicada | ❌ Requiere S44 |

| Cobertura | Ejemplos |
|-----------|---------|
| ✅ Resuelve | Verificar API exacta de una librería en su versión actual (context7) |
| ✅ Resuelve | Acceder a esquemas Oracle del proyecto del cliente (Oracle MCP) |
| ❌ No resuelve (aún) | Documentación interna de la empresa del cliente |
| ❌ No resuelve (aún) | APIs propietarias no expuestas públicamente |

> **Nota — pendiente resolver (S44):** implementar MCP Server Manager — administración dinámica de servidores MCP desde el dashboard. Permitir que cada proyecto configure sus propias fuentes de conocimiento (Confluence, Notion, Swagger interno, repositorio de specs). Sin S44, la capa 5 solo cubre fuentes globales (context7, Oracle).

---

#### Flujo de decisión — cuándo activa cada capa

```
FR recibido: "Implementar auth con Lucia v3 (TypeScript)"
      ↓
Capa 1: ¿Lo sabe el LLM?
  → Lucia v3 es reciente — conocimiento parcial
      ↓
Capa 2: ¿Hay convención OVD en el template?
  → No está en stack/backend_typescript.md aún
      ↓
Capa 3: ¿Hay RAG de ciclos anteriores con Lucia?
  → No — primer ciclo con esta librería
      ↓
Capa 4: web_research activa búsqueda
  → "Lucia v3 TypeScript auth 2025" → docs actuales → {rag_context}
      ↓
Capa 5: context7 MCP verifica API durante ejecución del agente
  → Confirma sintaxis exacta de la versión instalada
      ↓
LLM genera código correcto con docs actuales
      ↓
Informe de entrega indexado en pgvector
  → Próximo ciclo con Lucia ya tiene Capa 3 disponible
```

---

#### Tabla de activación por situación

| Situación | Capa principal | Sprint que lo habilita |
|-----------|---------------|----------------------|
| Framework popular en entrenamiento | Capa 1 + Capa 2 | S58-pre |
| Convención OVD específica del stack | Capa 2 | S58-pre |
| Misma tecnología en ciclos anteriores | Capa 3 RAG | Activo desde S37 |
| Librería conocida, verificar API actual | Capa 5 context7 | Activo desde S38 |
| Librería reciente o post-cutoff | Capa 4 web_research | **S48 — pendiente** |
| API interna / framework propietario | Capa 5 MCP custom | **S44 — pendiente** |
| Docs del cliente no indexadas | Capa 3 batch indexing | **S60/C10 — pendiente** |
| Docs proyecto cliente en Confluence/Notion | Capa 5 MCP custom | **S44 — pendiente** |

---

#### Relación con S58-pre

S58-pre fortalece la **Capa 2** — la más eficiente porque no requiere red ni latencia. Una Capa 2 robusta reduce la necesidad de activar Capas 4 y 5, pero no las elimina. Las brechas que los templates no pueden cubrir por diseño (tecnologías post-cutoff, APIs privadas) requieren Capas 4 y 5 operativas.

**Orden de implementación recomendado:**
```
S58-pre  → Capa 2 robusta (templates v1 por stack)
S48      → Capa 4 confiable (web_research multi-proveedor)
S44      → Capa 5 extensible (MCP Server Manager)
S60/C10  → Capa 3 automatizada (batch indexing docs del cliente)
```

---

## S59 — Diagnóstico de fallos silenciosos + devops scope + reconexión SSE

**Última iteración:** 2026-04-26 — plan detallado tras investigación profunda (LangGraph docs + FastAPI SSE + análisis de código).
**Estado:** ⬜ Pendiente

**Motivación:** El ciclo S58-pre (`839f65d1`) terminó con `status=failed` después de ~17 min sin ningún traceback visible. El agente devops duplicó su primera tarea. La SSE se desconectó a los 10 min. Investigación identificó **3 capas de silenciamiento apiladas** — sin S59-A no es posible diagnosticar ningún otro fallo.

**Ciclo de referencia:** `839f65d1` — backend OK, database OK, devops duplicó Dockerfile.api, frontend nunca arrancó (excepción silenciada post-fan-out).

---

### S59-A — Diagnóstico de fallos silenciosos (CRÍTICO)

**Síntoma:** `status=failed` en BD sin traceback. Ciclos fallan en silencio — imposible distinguir timeout LLM, excepción en tool calling, o error de red.

**Root cause — 3 capas confirmadas en el código:**

**Capa 1 — Logging sin handlers (`api.py:89-97`):**
`_configure_app_loggers()` solo llama `getLogger(name).setLevel(numeric)` sin `addHandler()`. Si uvicorn no configuró previamente un handler para `ovd.api`/`ovd-graph`, los `log.warning()` / `log.error()` se descartan silenciosamente.

**Capa 2 — Exception sin traceback (`graph.py:2091`):**
En `_run_agent_with_tools`, `except Exception as e: log.warning(...)` sin `exc_info=True`. El mensaje aparece pero sin pila de llamadas.

**Capa 3 — `asyncio.create_task()` sin `add_done_callback` (`api.py:708`, `graph.py:2535`):**
Tareas fire-and-forget que fallan solo generan `RuntimeWarning` en el GC — sin thread_id ni contexto.

**Capa adicional (LangGraph):** si `agent_executor` lanza excepción no capturada, LangGraph la propaga al `astream()` dentro de `_stream_graph_events()`, donde un `except BaseException` la silencia — el grafo termina sin log ni traceback.

**Fixes:**

**A1 — `_configure_app_loggers()` con `dictConfig` (`api.py:89`):**
```python
def _configure_app_loggers() -> None:
    import logging.config
    level_str = os.environ.get("OVD_LOG_LEVEL", os.environ.get("LOG_LEVEL", "WARNING")).upper()
    numeric = getattr(logging, level_str, logging.WARNING)
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,   # no silencia loggers ya creados
        "formatters": {"ovd": {"format": "%(asctime)s [%(name)s] %(levelname)s %(message)s"}},
        "handlers": {"stderr": {"class": "logging.StreamHandler", "stream": "ext://sys.stderr", "formatter": "ovd"}},
        "root": {"level": numeric, "handlers": ["stderr"]},
        "loggers": {
            "uvicorn": {"level": numeric, "propagate": True},
            "ovd.api": {"level": numeric, "propagate": True},
            "ovd.graph": {"level": numeric, "propagate": True},
        },
    })
```
`disable_existing_loggers: False` es crítico — preserva los handlers de uvicorn y garantiza que `log.warning()` de `ovd.api` llega al stderr independientemente del `--log-level` de uvicorn.

**A2 — `exc_info=True` en `_run_agent_with_tools` (`graph.py:2091`):**
```python
except Exception as e:
    log.error("S17T tool calling falló para %s — usando fallback sin tools", agent_name, exc_info=True)
```
Cambiar `log.warning` → `log.error` + `exc_info=True` para traceback completo.

**A3 — `add_done_callback` en tareas fire-and-forget:**
```python
# api.py:708
def _log_cleanup_error(t: asyncio.Task) -> None:
    if not t.cancelled() and (exc := t.exception()):
        log.error("_deferred_cleanup error para thread=%s: %s", thread_id[:8], exc)
asyncio.create_task(_deferred_cleanup(thread_id, 600)).add_done_callback(_log_cleanup_error)

# graph.py:2535
def _log_lesson_error(t: asyncio.Task) -> None:
    if not t.cancelled() and (exc := t.exception()):
        log.error("lessons.index_security_finding error: %s", exc, exc_info=exc)
asyncio.create_task(lessons.index_security_finding(...)).add_done_callback(_log_lesson_error)
```

**A4 — `try/except` total en nodo `agent_executor` (`graph.py`):**
Capturar excepción en el nodo → retornar resultado degradado en vez de propagar a LangGraph.
Decisión de diseño: **continuar con resultado de error** (vs abortar) porque los artefactos de otros agentes ya están escritos en disco y el usuario puede ver el error y relanzar solo el agente fallido.
```python
async def agent_executor(state: OVDState) -> dict:
    agent_name = state.get("current_agent", "unknown")
    try:
        # ... código existente ...
    except Exception as exc:
        log.error("agent_executor[%s]: EXCEPCIÓN NO CAPTURADA", agent_name, exc_info=True)
        return {
            "agent_results": [{"agent": agent_name, "output": f"[S59-A ERROR]: {type(exc).__name__}: {exc}",
                               "artifacts": [], "uncertainties": [], "tokens": {"input": 0, "output": 0}}],
            "token_usage": {agent_name: {"input": 0, "output": 0}},
        }
```

**A5 — Migración BD:**
```sql
ALTER TABLE ovd_cycles ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE ovd_cycles ADD COLUMN IF NOT EXISTS failed_at_node TEXT;
```
En `_ensure_cycle_registered`: si `status != 'completed'`, guardar el último error del checkpoint en `error_message` y el nodo activo en `failed_at_node`.

**Tests:**
- `test_s59.py::test_logging_has_handler` — `ovd.api` logger tiene al menos 1 handler post-configure
- `test_s59.py::test_logging_warning_reaches_stderr` — `log.warning()` aparece en stderr capturado
- `test_s59.py::test_tool_call_failure_logs_traceback` — `except Exception` emite `exc_info`
- `test_s59.py::test_create_task_callback_on_error` — `_deferred_cleanup` que lanza excepción es capturada
- `test_s59.py::test_agent_executor_exception_returns_error_dict` — excepción → dict con `[S59-A ERROR]`
- `test_s59.py::test_agent_executor_other_agents_not_lost` — si backend falla, database+frontend siguen en `agent_results`

---

### S59-B — Devops: tarea duplicada (ALTA)

**Síntoma:** TASK-010 (docker-compose) genera `Dockerfile.api` de nuevo en vez de `docker-compose.yml`.

**Root cause:** `system_devops.md` tiene las restricciones correctas pero no tiene un mapping explícito de "nombre de tarea → archivo de salida esperado". El modelo reutiliza el patrón del único ejemplo en contexto (Dockerfile de TASK-009). No hay validación en el engine que detecte paths duplicados entre tareas del mismo agente.

**Fix B1 — Tabla de mapping en `system_devops.md`:**
```markdown
**Mapping obligatorio: nombre de tarea → archivo de salida**
| Si la tarea dice...                                    | Debes generar                        |
|--------------------------------------------------------|--------------------------------------|
| "Dockerfile", "imagen", "build", "containerizar"       | `Dockerfile` o `.docker/Dockerfile.<servicio>` |
| "docker-compose", "orquestar servicios", "stack"       | `docker-compose.yml`                 |
| "CI/CD", "pipeline", "GitHub Actions", "workflow"      | `.github/workflows/<nombre>.yml`     |
| "nginx", "reverse proxy", "routing HTTP"               | `nginx.conf`                         |

Si el SDD asigna MÚLTIPLES tareas al agente devops, cada tarea DEBE generar un archivo DIFERENTE.
NUNCA generes el mismo archivo en dos tareas distintas.
```

**Fix B2 — Detección de paths duplicados en `deliver` (`graph.py`):**
```python
seen_paths: dict[str, str] = {}
for result in agent_results:
    for artifact in result.get("artifacts", []):
        path = artifact.get("path", "")
        agent = result.get("agent", "?")
        if path in seen_paths:
            log.warning("S59-B: path duplicado '%s' — agente '%s' y '%s'", path, seen_paths[path], agent)
        else:
            seen_paths[path] = agent
```

**Tests:**
- `test_s59.py::test_devops_template_has_mapping_table` — `system_devops.md` contiene "Mapping obligatorio"
- `test_s59.py::test_deliver_logs_duplicate_paths` — dos artefactos con mismo path → `log.warning`

---

### S59-C — Reconexión SSE automática (MEDIA)

**Síntoma:** SSE desconecta a ~10 min. Grafo continúa (S47-A) pero UI pierde visibilidad. Dashboard muestra formulario vacío tras reload.

**Root cause:** El servidor no emite campo `id:` en los eventos SSE → el browser `EventSource` reconecta automáticamente (cada 3s por defecto) pero envía `Last-Event-ID` vacío → no hay forma de reproducir eventos perdidos. La queue de S47-A ya entregó los eventos y el stream está vacío para el cliente reconectado.

**Fix C1 — Emitir `id:` en todos los eventos:**
```python
_sse_seq: dict[str, int] = {}

def _make_sse_event(event_type: str, data: dict, thread_id: str = "") -> str:
    if thread_id:
        seq = _sse_seq.get(thread_id, 0) + 1
        _sse_seq[thread_id] = seq
        id_line = f"id: {thread_id[:8]}-{seq}\n"
    else:
        id_line = ""
    return f"{id_line}event: {event_type}\ndata: {json.dumps(data)}\n\n"
```

**Fix C2 — Buffer de eventos por thread (ring buffer ~200 items):**
```python
_event_buffers: dict[str, list[tuple[int, str]]] = {}
_EVENT_BUFFER_SIZE = 200
```
Al poner eventos en la queue, guardarlos también en el buffer. Al reconectar, reproducir desde `Last-Event-ID`.

**Fix C3 — Replay al reconectar en `stream_session`:**
```python
last_event_id = request.headers.get("last-event-id", "")
if last_event_id and thread_id in _event_buffers:
    try:
        last_seq = int(last_event_id.split("-")[-1])
        for seq, event_str in _event_buffers[thread_id]:
            if seq > last_seq:
                yield event_str
    except (ValueError, IndexError):
        pass
```
No requiere cambios en `FrLauncher.tsx` — el `EventSource` nativo del browser maneja la reconexión con `Last-Event-ID` automáticamente. El buffer de 200 eventos cubre ~10 min de ciclo típico.

**Tests:**
- `test_s59.py::test_sse_event_has_id_field` — `_make_sse_event()` retorna string con línea `id:`
- `test_s59.py::test_sse_replay_from_last_event_id` — reconexión con `Last-Event-ID` reproduce eventos perdidos

---

### S59-D — Puerto Oracle en SDD (BAJA)

**Síntoma:** SDD generó `host.docker.internal:1522` (debe ser 1521).

**Root cause:** Los templates ya tienen 1521 correctamente (`stack/database_oracle.md:9`, `system_devops.md:22`). El problema es alucinación del LLM — 1522 aparece en training data de algunas configuraciones de Oracle Application Server. Sin una restricción explícita en `system_sdd.md`, el LLM puede generar el puerto incorrecto.

**Fix — Restricción explícita en `system_sdd.md`:**
```markdown
**Puerto Oracle obligatorio:** Si el SDD define conectividad Oracle, el puerto SIEMPRE es 1521.
El puerto 1522 es incorrecto para Oracle XE/19c estándar. No uses 1522 en ningún connection string.
```

**Tests:**
- `test_s59.py::test_oracle_sdd_template_port_constraint` — `system_sdd.md` menciona "1521" y prohíbe "1522"

---

### Orden de implementación S59

```
Fix A1 (dictConfig)         ← habilita que el resto de los logs sean visibles
Fix A2 (exc_info=True)      ← traceback completo desde el primer restart
Fix A3 (callbacks)          ← tareas fire-and-forget supervisadas
Fix A4 (try/except total)   ← agentes fallidos reportan en vez de silenciar
Fix A5 (migración BD)       ← columnas error_message + failed_at_node
Fix B1 (devops template)    ← independiente, ~15 min
Fix B2 (path duplicados)    ← independiente, ~30 min
Fix C1+C2+C3 (SSE replay)   ← independiente, ~1h
Fix D  (puerto 1521)        ← 1 línea en system_sdd.md
Tests S59                   ← al final, 11 tests
```

### Criterio de éxito S59

```bash
# 1. Migración aplicada
docker exec postgres_db psql -U ovd_dev -d ovd_dev -c "\d ovd_cycles"
# → columnas error_message y failed_at_node presentes

# 2. Tests S59
cd src/engine && .venv/bin/python -m pytest tests/test_s59.py -v

# 3. Regresión
.venv/bin/python -m pytest tests/ -m "not integration and not e2e and not docker" --timeout=60

# 4. Smoke: lanzar ciclo, provocar fallo, verificar
# → log del engine muestra traceback completo
# → SELECT error_message, failed_at_node FROM ovd_cycles ORDER BY created_at DESC LIMIT 1
# → devops genera Dockerfile.api Y docker-compose.yml (archivos distintos)
# → desconectar SSE a los 3 min → reconectar → recibe eventos perdidos
```

---

## S58 — Stack Transversality (pendiente)

**Última iteración:** 2026-04-26 — investigación profunda completada, plan refinado con hallazgos de codebase + LangGraph docs + benchmarks qwen3-coder.

**Motivación:** Auditoría 2026-04-26 reveló que el 40% de los fixes implementados en S40–S57 tienen sesgo Python/pytest. Se validaron siempre con el mismo FR de IMC en Python — nunca se probó TypeScript ni Rust. Los bugs de sesgo son silenciosos hasta que se usa otro stack.

**Argumento clave:** El problema no es el modelo. `qwen3-coder:30b` soporta 119 lenguajes oficialmente (SWE-Bench 69.6%), conoce pytest/Vitest/Jest/cargo test, y tiene un context window de 256K tokens. El problema es que OVD le envía instrucciones con `"```python:tests/test_*.py"` cuando el proyecto es TypeScript. Con la instrucción correcta, el modelo genera el código correcto.

---

### Arquitectura del sistema de templates (investigado 2026-04-26)

El sistema tiene 3 capas. Entender esto es prerequisito para diseñar S58 correctamente.

#### Capa 1 — Perfil del proyecto (`ovd_project_profiles`)

Campos configurables por proyecto que se inyectan en `{project_context}` de todos los templates:

| Campo | Uso | Ejemplo |
|-------|-----|---------|
| `language` | Lenguaje principal | `python`, `typescript` |
| `framework` | Framework | `FastAPI`, `React`, `Hono` |
| `db_engine` + `db_version` | Genera restricciones SQL automáticas via `ContextResolver` | `oracle 19c` → inyecta `FETCH FIRST`, `thick mode`, etc. |
| `constraints` | Texto libre — reglas del proyecto | `"Usar RUT chileno limpio sin puntos ni guión"` |
| `code_style` | Guía de estilo | `"snake_case, type hints obligatorios"` |
| `project_description` | Descripción narrativa | `"Sistema HHMM de honorarios médicos"` |
| `additional_stack` | Librerías extra | `["Redis", "Celery"]` |
| `legacy_stack` | Sistemas legacy | `"Oracle EBS 12.1"` |

`ContextResolver.to_prompt_block()` transforma estos campos en un bloque markdown que recibe el LLM en cada llamada.

#### Capa 2 — Stack del proyecto (`ovd_stack_profiles`)

El campo `language` determina qué archivo `.md` carga `template_loader.render()`:

```
stack_language="python"      → system_backend_python.md  → fallback: system_backend.md
stack_language="typescript"  → system_backend_typescript.md → fallback: system_backend.md
stack_language="oracle"      → system_database_oracle.md → fallback: system_database.md
```

Templates stack-specific disponibles hoy (creados en S42-E):

| Archivo | Stack |
|---------|-------|
| `system_backend_python.md` | Python + FastAPI |
| `system_backend_typescript.md` | TypeScript + Hono |
| `system_frontend_react.md` | React |
| `system_database_oracle.md` | Oracle |
| `system_database_postgresql.md` | PostgreSQL |

#### Capa 3 — Templates en disco (`src/engine/templates/*.md`)

Son globales — todos los proyectos los comparten. Las 5 variables interpolables:

| Variable | Contenido | Quién la rellena |
|----------|-----------|-----------------|
| `{project_context}` | Perfil completo (capas 1+2) | `api.py` desde BD |
| `{rag_context}` | Contexto semántico (pgvector) | `graph.py` antes de cada nodo |
| `{retry_feedback}` | Feedback acumulado de retries | `graph.py` en `update_test_retry` |
| `{lessons_context}` | Lecciones de ciclos anteriores (S41) | `graph.py` — activo |
| `{ui_context}` | Guías UI/UX desde knowledge | Definido pero sin llamadas activas |

**Limitación actual:** No existe mecanismo de templates custom por proyecto. Toda personalización pasa por `constraints`, `code_style` (texto libre en `{project_context}`) o RAG. Si dos proyectos TypeScript tienen convenciones distintas, ambos reciben el mismo `system_backend_typescript.md`.

**Implicación para S58:** Los fixes de S58-A/B/C/D/E van en `graph.py` (lógica inline que ignora `stack_language`), no en los templates `.md`. Los templates ya están correctamente separados por stack. El problema es la lógica dentro de los nodos.

---

### Hallazgos de auditoría del codebase

Investigación exhaustiva de `graph.py` completada 2026-04-26:

| Tag | Ubicación | Problema | Prioridad |
|-----|-----------|----------|-----------|
| **S51-A** | `graph.py:1701` — keywords | Detecta tareas de tests con `("test", "pytest", "unitari", "spec")` — keyword `"pytest"` es Python-specific | CRÍTICA |
| **S51-A** | `graph.py:1704` — instrucción | Inyecta `` ```python:tests/test_<paquete>.py `` hardcodeado | CRÍTICA |
| **S51-C** | `graph.py:1769` — retry | Mismo problema en el segundo intento de generación de tests | CRÍTICA |
| **S55-C** | `graph.py:1410-1417` — float hint | Instrucción `round()` enviada a todos los stacks. TypeScript usa `toFixed(2)`, Rust usa `(a-b).abs() < 1e-2` | ALTA |
| **S31-C** | `graph.py:2934` — filtro mtime | `_base.rglob("test_*.py")` hardcodeado. Vitest usa `*.test.ts`, Rust no tiene patrón de nombre | ALTA |
| **S32-C/S57-B** | `graph.py:3104-3179` — exit codes | Exit 4/5 son códigos pytest. Vitest tiene bug conocido (#5249) — puede retornar 0 sin tests | MEDIA |
| **S27-A** | `graph.py:2902` — conftest | Ya condicional `if runner == "pytest"` ✅. Pero no genera equivalente Vitest (`vitest.config.ts`) | MEDIA |

**Lo que YA es stack-aware (no necesita fix):**
- `_detect_test_runner()` — detecta pytest/vitest/cargo por filesystem ✅
- Comandos de ejecución — en ramas condicionales por runner ✅
- Templates por stack — routing correcto vía `template_loader.render()` ✅
- `system_sdd.md` — nombra pytest/Vitest explícitamente ✅ (parcial)

---

### Hallazgos de documentación oficial (LangGraph + qwen3-coder)

#### LangGraph 1.1.3

- **`add_conditional_edges`** es el patrón estándar para routing por `stack_language`, pero NO es necesario para S58. Los problemas están en lógica *dentro* de nodos, no en routing del grafo.
- **Annotated reducers** (`_keep_best_qa` de S57-A) funcionan igual en async/sync. Sin issues conocidos con `astream()`.
- **Issue #4305:** `Optional[int]` tiene comportamiento inconsistente — usar `int | None` en nuevos campos de OVDState.
- **Issue #4826:** Streaming context leaks en subgrafos anidados. No afecta a OVD (no usa subgrafos).

#### qwen3-coder:30b

- Soporta 119 lenguajes oficialmente.
- SWE-Bench Verified: 69.6% — benchmark mayormente Python.
- Context window: 256K tokens (OVD usa ~30K en promedio — sin problema de tamaño).
- Conoce pytest, Jest, Vitest, JUnit, cargo test — el modelo es capaz, las instrucciones no lo son.
- Debilidad documentada: generics complejos en TypeScript. No afecta a FRs simples de CRUD/API.

#### Exit codes por framework (hallazgo crítico para S58-E)

| Framework | Exit 0 | Exit 1 | Exit 4 | Exit 5 | Issue conocido |
|-----------|--------|--------|--------|--------|---------------|
| pytest | passed | failed | USAGE_ERROR | no tests | — |
| Vitest | passed | failed | — | — | **Bug #5249**: puede retornar 0 sin tests |
| cargo test | passed | failed | — | — | Issue #16558: edge case con `process::exit` |
| Jest | passed | failed | — | — | Issue #9324: puede retornar 1 sin fallos |

Vitest bug #5249 es el más crítico: la lógica de `run_tests` que confía en exit 0 = éxito fallaría silenciosamente para TypeScript.

#### Convenciones de test setup por stack

| Stack | Equivalente a conftest.py | Patrón de archivo de test |
|-------|--------------------------|--------------------------|
| Python/pytest | `conftest.py` + `pytest.ini` | `test_*.py` / `*_test.py` |
| TypeScript/Vitest | `vitest.config.ts` (setupFiles) | `*.test.ts` / `*.spec.ts` / `*.test.tsx` |
| Rust/cargo | No necesita setup — `Cargo.toml` lo maneja | Unit: `#[cfg(test)]` inline en `src/`. Integration: `tests/*.rs` |
| Go | No requiere configuración | `*_test.go` |
| Java/JUnit | `src/test/resources/` | `Test*.java` / `*Test.java` |

---

### Plan de implementación S58

Orden de ejecución: `S58-A → S58-B → S58-C → S58-D → S58-E → S58-F (template) → Tests → S58-G/H (ciclos)`

#### S58-A — S51-A keywords + instrucción stack-aware (CRÍTICO)

**Archivo:** `graph.py` ~línea 1700 — función `execute_agents`

**Cambio:** Keywords de detección y path de archivo condicional por `stack_language`:

```python
_stack = state.get("stack_language", "python")
_test_keywords = {
    "typescript": ("test", "vitest", "jest", "spec", "unitari"),
    "rust":       ("test", "cargo", "spec", "unitari"),
    "python":     ("test", "pytest", "unitari", "spec"),
}.get(_stack, ("test", "pytest", "unitari", "spec"))

if any(kw in _task_desc_lower for kw in _test_keywords):
    _test_path = {
        "typescript": "tests/<modulo>.test.ts",
        "rust":       "tests/integration_test.rs",
    }.get(_stack, "tests/test_<paquete>.py")
    _test_fence = {"typescript": "typescript", "rust": "rust"}.get(_stack, "python")
    task_hint = (
        f"[PRIORIDAD MÁXIMA — S58-A] Esta tarea genera el archivo de tests. "
        f"DEBES incluir el bloque ```{_test_fence}:{_test_path} con al menos 3 casos."
    )
```

Mismo cambio en el retry S51-C (~línea 1769).

#### S58-B — S55-C float hint stack-aware (ALTA)

**Archivo:** `graph.py` ~línea 1408

```python
if _is_test_task:
    if _stack == "python":
        float_hint = "\n\n[S58-B] REGLA FLOAT Python: SIEMPRE usa round(expr, 2). Ej: round(65/1.72**2, 2) → 21.97"
    elif _stack == "typescript":
        float_hint = "\n\n[S58-B] REGLA FLOAT TypeScript: usa Number(value.toFixed(2)) o Math.abs(a-b) < 0.01"
    elif _stack == "rust":
        float_hint = "\n\n[S58-B] REGLA FLOAT Rust: usa assert!((result - expected).abs() < 1e-2)"
    else:
        float_hint = ""  # Stack desconocido: no inyectar hint incorrecto
```

#### S58-C — Setup injection stack-aware (MEDIA)

**Archivo:** `graph.py` ~línea 2902 — nodo `run_tests`

Agregar rama Vitest al bloque `if runner == "pytest"`:

```python
elif runner == "vitest":
    _vite_config = pathlib.Path(work_dir) / "vitest.config.ts"
    if not _vite_config.exists():
        _vite_config.write_text(
            'import { defineConfig } from "vitest/config";\n'
            'export default defineConfig({ test: { globals: true, environment: "node" } });\n'
        )
        log.warning("S58-C: vitest.config.ts inyectado en %s", work_dir)
# cargo: no necesita setup — Cargo.toml lo maneja
```

#### S58-D — Filtro de test files stack-aware (ALTA)

**Archivo:** `graph.py` ~línea 2934 — nodo `run_tests`, código S31-C

```python
if _runner == "pytest":
    _all_tests  = [str(fp) for fp in sorted(base.rglob("test_*.py"))]
    _all_tests += [str(fp) for fp in sorted(base.rglob("*_test.py"))]
elif _runner == "vitest":
    _all_tests  = [str(fp) for fp in sorted(base.rglob("*.test.ts"))]
    _all_tests += [str(fp) for fp in sorted(base.rglob("*.spec.ts"))]
    _all_tests += [str(fp) for fp in sorted(base.rglob("*.test.tsx"))]
elif _runner == "cargo":
    _all_tests = [str(base)]  # cargo test opera sobre el proyecto completo
else:
    _all_tests = []
```

#### S58-E — Exit codes por runner (MEDIA)

**Archivo:** `graph.py` ~línea 3104 — diagnósticos post-ejecución

Tabla de exit codes por runner + workaround Vitest bug #5249:

```python
# Para Vitest: verificar output además del exit code (bug #5249)
if runner == "vitest" and rc == 0:
    if "No test files found" in output or "0 tests" in output:
        log.warning("S58-E: Vitest retornó 0 pero sin tests (bug vitest#5249) — thread=%s", thread_id)
        # No bloquear ciclo, pero documentar en retry_feedback
```

#### S58-F — system_sdd.md stack-aware para tests (MEDIA)

**Archivo:** `src/engine/templates/system_sdd.md` ~línea 96

Reemplazar "pytest" / "Vitest" nombrados explícitamente por tabla por stack:

```markdown
- Agente `backend` → tarea de tests según stack:
  - Python: `tests/test_<modulo>.py` — pytest
  - TypeScript/Node: `tests/<modulo>.test.ts` — Vitest
  - Rust: `#[cfg(test)] mod tests {}` inline en `src/lib.rs` — cargo test
  - Java: `src/test/java/.../Test*.java` — JUnit 5
- Agente `frontend` → `tests/<componente>.test.tsx` — Vitest + Testing Library
```

---

### Tests unitarios S58

| # | Test | Valida |
|---|------|--------|
| 1 | `test_s51a_typescript_injects_vitest_path` | S58-A inyecta `.test.ts` para TypeScript |
| 2 | `test_s51a_rust_injects_cargo_path` | S58-A inyecta `integration_test.rs` para Rust |
| 3 | `test_s51a_python_unchanged` | S58-A no rompe comportamiento Python existente |
| 4 | `test_s55c_typescript_uses_tofixed` | S58-B inyecta `toFixed(2)` para TypeScript |
| 5 | `test_s55c_rust_uses_abs_diff` | S58-B inyecta `abs() < 1e-2` para Rust |
| 6 | `test_s55c_unknown_stack_no_hint` | S58-B retorna `""` para stack desconocido |
| 7 | `test_s27a_vitest_injects_config` | S58-C genera `vitest.config.ts` si no existe |
| 8 | `test_s27a_cargo_no_injection` | S58-C no toca nada para Rust |
| 9 | `test_s31c_vitest_pattern_test_ts` | S58-D busca `*.test.ts` y `*.spec.ts` para Vitest |
| 10 | `test_s31c_cargo_uses_project_dir` | S58-D usa directorio raíz para Cargo |
| 11 | `test_exit_vitest_zero_no_tests_detected` | S58-E detecta Vitest bug #5249 (exit 0 sin tests) |
| 12 | `test_sdd_template_lists_stack_conventions` | `system_sdd.md` menciona pytest/Vitest/cargo por stack |

---

### Ciclos de validación end-to-end

#### S58-G — TypeScript + Vitest
- **FR:** "Implementar función que valida email según RFC 5322, retorna bool, con tests en Vitest"
- **Verificar:** `*.test.ts` en disco, `vitest.config.ts` inyectado, vitest exit 0
- **Métricas objetivo:** QA 80+, pytest exit 0 equivalente, 0 retries

#### S58-H — Rust + cargo test
- **FR:** "Implementar función que calcula distancia Levenshtein entre dos strings, con tests cargo"
- **Verificar:** `#[cfg(test)]` en `src/lib.rs`, cargo test exit 0
- **Métricas objetivo:** QA 80+, cargo exit 0, 0 retries

---

### Impacto esperado

| Métrica | Antes de S58 | Después de S58 |
|---------|-------------|----------------|
| FR Python → pytest | Funciona (validado S49–S57) | Sin cambio |
| FR TypeScript → Vitest | Genera `test_*.py` o falla en colección | Genera `*.test.ts` + `vitest.config.ts` |
| FR Rust → cargo test | Genera `conftest.py` innecesario | Usa cargo test directo |
| Float hints | `round()` para todos los stacks | `round()` / `toFixed(2)` / `abs()` según stack |
| Exit code Vitest | Falso positivo si no hay tests (bug #5249) | Detectado y documentado en retry_feedback |
| QA score TypeScript | Desconocido — nunca validado | Objetivo: 80+ |

---

### Deuda pendiente post-S58 (identificada en iteración)

1. **Templates custom por proyecto** — hoy no existe. Toda personalización va por `constraints` (texto libre) o RAG. Para proyectos con convenciones muy específicas (ej: dos proyectos TypeScript con guías distintas), falta una tabla `ovd_project_custom_templates` que permita sobrescribir un template por `project_id`. Candidato para **S60 o C10**.

2. **`{ui_context}`** — variable definida en `template_loader.py` pero sin llamadas activas en `graph.py`. `query_ui_context()` existe pero nunca se invoca. Candidato para reactivar en el nodo frontend.

3. **Benchmarking por stack en OVD** — no existe benchmarking público desagregado por framework (pytest vs Vitest vs cargo). OVD Platform puede ser caso de estudio. Documentar resultados de S58-G/H en `docs/BENCHMARKS_S58.md`.

---

### Perfil de proyecto — campos para templates (iteración 2026-04-26, posible sprint separado)

**Contexto:** Análisis del formulario de creación de proyectos reveló que hay campos en la BD que no aparecen en el dashboard, y campos nuevos que mejorarían significativamente la calidad del código generado.

#### Estado actual del formulario (`ProjectModal.tsx`)

El dashboard muestra hoy 7 campos de stack:
`language`, `framework`, `db_engine`, `runtime`, `legacy_stack`, `constraints`, `project_description`

#### Campos en BD pero ocultos en el formulario

| Campo | Tabla | Impacto en templates | Prioridad |
|-------|-------|---------------------|-----------|
| `code_style` | `ovd_project_profiles` | **Alto** — el LLM escribe el código según este campo. Ej: `"snake_case obligatorio, type hints, docstrings en español"` | Alta |
| `qa_tools` | `ovd_project_profiles` | **Medio** — el agente backend puede incluirlos en `requirements.txt` / `package.json`. Ej: `"ruff, mypy, pytest-cov"` | Media |
| `external_integrations` | `ovd_project_profiles` | **Medio** — evita que el LLM invente integraciones. Ej: `"Oracle EBS 12.1 (honorarios), Active Directory (auth)"` | Media |
| `ci_cd` | `ovd_project_profiles` | **Medio** — el agente devops genera workflows coherentes. Ej: `"GitHub Actions, deploy vía SSH"` | Media |
| `additional_stack` | `ovd_project_profiles` | **Bajo** — librerías extra. Ej: `["Redis", "Celery"]` | Baja |

**Acción:** Agregar estos campos al formulario `ProjectModal.tsx` (ya existen en la BD — es solo UI).

#### Campos nuevos que habría que crear

| Campo | Tipo | Impacto | Prioridad |
|-------|------|---------|-----------|
| `test_framework` | `str` | **Crítico para S58** — elimina la detección heurística de runner. El proyecto declara explícitamente `"pytest"`, `"vitest"`, `"jest"`, `"cargo"`, `"junit5"`. `_detect_test_runner()` usa esto como primera fuente antes de inspeccionar el filesystem | **Crítica** |
| `min_test_coverage` | `int` (0-100) | **Medio** — el template de QA puede evaluar cobertura declarada. `0` = no requerido | Media |

**`test_framework` es el campo más relevante para S58:** resuelve la ambigüedad de detección de runner en workspaces vacíos (primer ciclo de un proyecto nuevo). Con él, S58-D y S58-E tienen una fuente autoritativa en vez de heurística.

#### Lo que NO agregar (análisis 2026-04-26)

- `team_size` — campo existe en BD pero no tiene uso en ningún template actual
- Templates custom por proyecto — feature de mayor envergadura (requiere tabla nueva + editor UI), documentada en punto 1 de esta deuda

#### Plan de ejecución sugerido

Puede integrarse en S58 como ítem S58-I, o separarse en un sprint de UX/perfil (S59-perfil):

| Item | Descripción | Archivos | Estado |
|------|-------------|---------|--------|
| P-1 | Agregar `code_style`, `qa_tools`, `external_integrations`, `ci_cd` al formulario `ProjectModal.tsx` | `src/dashboard/src/components/ProjectModal.tsx` | ⬜ |
| P-2 | Crear campo `test_framework` en `ovd_project_profiles` (migración) + formulario | `migrations/`, `ProjectModal.tsx`, `api_v1.py` | ⬜ |
| P-3 | Usar `test_framework` como fuente primaria en `_detect_test_runner()` antes del filesystem scan | `graph.py` | ⬜ |
| P-4 | Crear campo `min_test_coverage` en `ovd_project_profiles` + usarlo en template `system_qa.md` | `migrations/`, `system_qa.md` | ⬜ |

---

## S48 — Web Research Intelligence (2026-04-24, pendiente)

**Motivación:** `web_research_node` activa en <10% de los ciclos, usa un único proveedor sin fallback, la cache está definida pero nunca se consulta (código muerto), y el indexado RAG depende del Bridge (si está caído, los findings se pierden). S48 convierte el nodo en una fuente real de contexto técnico para los agentes.

### S48-A — Multi-proveedor con failover automático

| Item | Descripción | Archivo(s) | Estado |
|------|-------------|-----------|--------|
| S48-A1 | Integración Tavily | Proveedor primario — indexación semántica, mejor calidad. Activado si `TAVILY_API_KEY` presente | `src/engine/tools/search_providers.py` | ⬜ |
| S48-A2 | Integración Brave Search | Proveedor secundario — independiente de Google. Activado si `BRAVE_API_KEY` presente | `src/engine/tools/search_providers.py` | ⬜ |
| S48-A3 | Integración SearXNG | Proveedor self-hosted. Activado si `OVD_SEARXNG_URL` configurado | `src/engine/tools/search_providers.py` | ⬜ |
| S48-A4 | Failover automático | Orden: Tavily → Brave → SearXNG → DuckDuckGo. Si un proveedor falla o agota cuota, pasa al siguiente automáticamente | `src/engine/tools/web_researcher.py` | ⬜ |

### S48-B — Gestión de proveedores desde Dashboard

| Item | Descripción | Archivo(s) | Estado |
|------|-------------|-----------|--------|
| S48-B1 | Tabla `ovd_search_providers` | `id, name, type, enabled, priority, api_key, base_url, max_results, timeout_secs, last_success_at, last_error, error_count` | `migrations/` | ⬜ |
| S48-B2 | `GET /api/v1/search-providers` | Lista proveedores con estado actual (último éxito, error_count, cuota) | `src/engine/routers/api_v1.py` | ⬜ |
| S48-B3 | `POST /api/v1/search-providers` | Agregar proveedor (name, type, api_key, base_url) | `src/engine/routers/api_v1.py` | ⬜ |
| S48-B4 | `PUT /api/v1/search-providers/{id}` | Actualizar: habilitar/deshabilitar, cambiar prioridad, rotar API key | `src/engine/routers/api_v1.py` | ⬜ |
| S48-B5 | `DELETE /api/v1/search-providers/{id}` | Eliminar proveedor | `src/engine/routers/api_v1.py` | ⬜ |
| S48-B6 | `POST /api/v1/search-providers/{id}/test` | Probar conectividad — ejecuta búsqueda de prueba, retorna latencia y N resultados | `src/engine/routers/api_v1.py` | ⬜ |
| S48-B7 | Página `/admin/search-providers` en dashboard | Lista con toggle, drag-and-drop prioridad, estado de salud (verde/amarillo/rojo), botón "Probar" | `src/dashboard/src/pages/SearchProviders.tsx` | ⬜ |

### S48-C — Control de cuota y gasto

| Item | Descripción | Archivo(s) | Estado |
|------|-------------|-----------|--------|
| S48-C1 | Campos de cuota en `ovd_search_providers` | `monthly_query_limit, daily_query_limit, queries_this_month, queries_today, cost_per_query_usd, monthly_budget_usd` | `migrations/` | ⬜ |
| S48-C2 | Contador de uso por proveedor | Incrementar `queries_today` y `queries_this_month` en cada búsqueda exitosa. Reset diario automático (cron o check lazy) | `src/engine/tools/search_providers.py` | ⬜ |
| S48-C3 | Skip por cuota agotada | Si `queries_today >= daily_query_limit` o gasto estimado >= `monthly_budget_usd`, el proveedor se salta en el failover | `src/engine/tools/web_researcher.py` | ⬜ |
| S48-C4 | Visualización de cuota en dashboard | Barra de progreso `queries_this_month / monthly_query_limit`, gasto estimado `queries × cost_per_query`, proyección fin de mes | `src/dashboard/src/pages/SearchProviders.tsx` | ⬜ |
| S48-C5 | Alerta de cuota al 80% y 100% | Log warning en engine + badge visual en dashboard cuando proveedor supera umbral | `src/engine/tools/search_providers.py` | ⬜ |

### S48-D — Cache funcional + síntesis contextualizada

| Item | Descripción | Archivo(s) | Estado |
|------|-------------|-----------|--------|
| S48-D1 | Cache en pgvector (fix código muerto) | Consulta pgvector antes de buscar (similitud >= 0.92, max_age=7 días). Si hit, retorna sin consumir cuota del proveedor | `src/engine/tools/web_researcher.py` | ⬜ |
| S48-D2 | Indexar resultados en cache | Después de búsqueda exitosa, indexar query + results en pgvector con metadata `{type: "web_cache", project_id}` | `src/engine/tools/web_researcher.py` | ⬜ |
| S48-D3 | Síntesis contextualizada por tipo de FR | El prompt de síntesis varía según tipo: migración → riesgos y pasos; integración → endpoints y rate limits; feature → mejores prácticas y antipatrones | `src/engine/tools/web_researcher.py` | ⬜ |

### S48-E — Fix RAG indexing sin Bridge

| Item | Descripción | Archivo(s) | Estado |
|------|-------------|-----------|--------|
| S48-E1 | Indexar findings directamente en pgvector | Reemplaza `POST Bridge/ovd/rag/index` por `rag.index_document()` directo. Mismo patrón que S27-C para informes de entrega | `src/engine/tools/web_researcher.py` | ⬜ |
| S48-E2 | Metadata de findings indexados | `{type: "web_research", project_id, fr_summary, queries_used, providers_used, indexed_at}` — recuperable en ciclos futuros del mismo proyecto | `src/engine/tools/web_researcher.py` | ⬜ |

### S48-F — Activación inteligente por tipo de FR (feature flag)

| Item | Descripción | Archivo(s) | Estado |
|------|-------------|-----------|--------|
| S48-F1 | `_classify_research_depth()` | Clasifica FR como `none` / `light` / `full` según tipo, librerías externas mencionadas, integraciones API, tipo de agente | `src/engine/graph.py` | ⬜ |
| S48-F2 | Triggers automáticos | FR con integración API externa → `light`. FR con `performance`/`bottleneck` → `light`. FR con agente frontend → `light` (patrones UI). FR de seguridad → `full`. Explícito `[research]` → `full` | `src/engine/graph.py` | ⬜ |
| S48-F3 | Feature flag `OVD_RESEARCH_AUTO` | `true/false` (default: false en dev, true en prod). Permite validar en producción antes de activar globalmente | `src/engine/.env` | ⬜ |

### S48-T — Tests

| Test | Qué valida |
|------|-----------|
| `test_provider_failover` | Si Tavily falla, cae a Brave; si Brave falla, cae a DuckDuckGo |
| `test_provider_quota_skip` | Proveedor con `queries_today >= limit` se salta en failover |
| `test_cache_hit` | Query ya en pgvector no llama al proveedor externo |
| `test_cache_miss_indexes` | Query nueva se indexa en pgvector después de búsqueda |
| `test_synthesis_by_fr_type` | Prompt de síntesis cambia según tipo de FR |
| `test_rag_indexing_without_bridge` | `index_document` directo funciona con Bridge caído |
| `test_providers_crud_endpoints` | CRUD de proveedores persiste en BD |
| `test_quota_counter_increment` | `queries_today` y `queries_this_month` se incrementan |
| `test_research_auto_flag` | Con `OVD_RESEARCH_AUTO=false`, no se activa sin `[research]` explícito |
| `test_classify_integration_fr` | FR con "Stripe API" → `light` research |

**Orden de implementación:** S48-E (fix Bridge) → S48-D1 (cache) → S48-A (multi-proveedor) → S48-B/C (dashboard + cuotas) → S48-F (activación inteligente) → S48-T (tests)

---

## FASE F — Migración Flutter (cliente unificado web + desktop)

**Objetivo:** reemplazar el TUI Rust y el Dashboard React por una sola aplicación Flutter que compila a web, macOS, Linux y Windows desde el mismo codebase Dart. El engine Python no cambia.

> Ver propuesta completa en `docs/FLUTTER_MIGRATION.md`

**Prerequisito:** despliegue VPS (FASE 5 — C01) operativo antes de iniciar.

### Sprint F1 — Core sin UI ⬜

| # | Item | Descripción | Estado |
|---|------|-------------|--------|
| F1.A | Proyecto Flutter inicializado | `src/flutter_app/` — estructura `core/`, `features/`, `shared/`. Targets: web, macOS, Linux, Windows | ⬜ |
| F1.B | API Client (Dio + interceptors) | `AuthInterceptor`: adjunta Bearer + refresh automático en 401. Base URL configurable por env | ⬜ |
| F1.C | SSE Client (dart:http streams) | `SseClient` sobre `dart:http` raw streams — parser de bloques `event:/data:` con buffer | ⬜ |
| F1.D | Modelos Freezed | `SessionModel`, `SDDModel`, `ProjectModel`, `TokenUsageModel`, `AgentResultModel` | ⬜ |
| F1.E | AuthNotifier + TokenStorage | `flutter_secure_storage`: Keychain (macOS), libsecret (Linux), Credential Manager (Windows), IndexedDB cifrado (web) | ⬜ |
| F1.F | Tests unitarios del core | API client, SSE parser, token refresh flow | ⬜ |

### Sprint F2 — Flujo principal ⬜

| # | Item | Descripción | Estado |
|---|------|-------------|--------|
| F2.A | Login + OnboardingScreen | Equivalente TUI Login + Onboarding wizard | ⬜ |
| F2.B | FrLauncherScreen | Formulario FR + adjuntar imagen (file_picker) + preview visual + envío | ⬜ |
| F2.C | SessionStreamScreen | SSE en tiempo real — nodos con estado, streaming de contenido, indicadores de progreso | ⬜ |
| F2.D | ApprovalScreen | SDD completo + feedback textual + aprobar/revisar/rechazar | ⬜ |
| F2.E | DeliveryScreen | Artefactos generados — listado, copy, download | ⬜ |
| F2.F | DashboardScreen (KPIs básicos) | Ciclos totales, QA promedio, costo, proyectos activos | ⬜ |

### Sprint F3 — Flujo secundario + admin ⬜

| # | Item | Descripción | Estado |
|---|------|-------------|--------|
| F3.A | HistoryScreen + CycleDetail modal | Lista sesiones con filtros, modal de detalle expandible | ⬜ |
| F3.B | CyclesScreen + ProjectsScreen | CRUD proyectos, historial de ciclos por proyecto | ⬜ |
| F3.C | WorkspaceConfigScreen + KnowledgeScreen | Stack Registry config, bootstrap RAG | ⬜ |
| F3.D | AdminUsersScreen + AdminSkillsScreen | CRUD usuarios, gestión repos externos (admin only) | ⬜ |

### Sprint F4 — Funcionalidad avanzada ⬜

| # | Item | Descripción | Estado |
|---|------|-------------|--------|
| F4.A | TelemetryScreen | Gráficos fl_chart: QA trend, costo diario, tokens por agente | ⬜ |
| F4.B | ModelDashboardScreen | Estado circuit breaker, progreso dataset fine-tuning, modelos activos | ⬜ |
| F4.C | OrgChartScreen | Pipeline viewer de agentes (árbol visual del ciclo activo) | ⬜ |

### Sprint F5 — Plataforma + depreciación ⬜

| # | Item | Descripción | Estado |
|---|------|-------------|--------|
| F5.A | AppShell responsivo | Sidebar fijo ≥1024px, NavigationDrawer <1024px. Atajos de teclado nativos | ⬜ |
| F5.B | Build web | `flutter build web --release`. Integrar en `docker-compose.prod.yml` (Nginx sirve estáticos Flutter) | ⬜ |
| F5.C | Build desktop | `flutter build macos/linux/windows`. Reemplaza binario TUI Rust en distribución | ⬜ |
| F5.D | Caddy config actualizada | `/` → Flutter web estáticos. `/api/*` → engine FastAPI (sin cambios) | ⬜ |
| F5.E | Deprecar `src/tui/` y `src/dashboard/` | Eliminar Rust TUI y React Dashboard tras validación en producción | ⬜ |
| F5.F | CI/CD Flutter | GitHub Actions: `flutter build web` + `flutter build macos` en cada push a main | ⬜ |

---

## FASE M — Modelo Propio (transversal a todas las fases)

**Objetivo estratégico:** construir modelos de IA propios especializados por rol, entrenados sobre ciclos reales aprobados por el equipo. Cada modelo corre 100% local en Ollama — sin dependencia de API cloud.

Ver estrategia completa en `docs/MODEL_STRATEGY.md`.

### Modelos en uso y estrategia de fine-tuning por rol

| Modelo Ollama | Rol en OVD | Variable `.env` | Fine-tuning viable | Dataset requerido |
|---|---|---|---|---|
| `deepseek-r1:14b` | Análisis de FR (`analyze_fr`) | `OVD_MODEL_ANALYZER` | Sí — dataset actual aplica directo | `data/merged.jsonl` (312 ejemplos) |
| `qwen2.5-coder:7b` | Arquitecto base | — | Ya fine-tuneado → `ovd-arch-assistant` | — |
| `qwen3-coder:30b` | Agentes de implementación (backend/frontend/DB) | `OVD_MODEL` | Sí — requiere dataset de implementación | Construir con ciclos exitosos via S41 |
| `qwen3-coder-next` (80B MoE) | QA review + security audit | `OVD_MODEL_QA` | Factible pero bajo ROI — el modelo ya es muy bueno en esas tareas | — |
| `qwen2.5vl:7b` | Visión (`describe_image`) | `OVD_MODEL_VISION` | No aplica — dataset incompatible (texto puro) | — |

### Hitos

| Hito | Descripción | Condición | Estado |
|---|---|---|---|
| M0 | Modelos base ejecutando ciclos en producción | Estado actual | ✅ |
| SM1 | **Aceleración con datos sintéticos** — `generate_synthetic.py` (42 escenarios, 3 tipos), `export_cycles.py` con filtros de calidad, `pipeline.sh` orchestrator. **Pipeline ejecutado 2026-03-31: 200 sintéticos generados + 112 de batch1 = 312 ejemplos en `data/merged.jsonl`, 0 duplicados, 0 errores, ~840 tokens/ejemplo.** | Sprint 9–10 | ✅ |
| M1 | 300+ ejemplos de calidad (reales + sintéticos validados) en JSONL listo para fine-tuning | Completado 2026-03-31 | ✅ |
| M1.5 | **Evaluar y enriquecer dataset** — exportar ciclos S36-S42 (QA mejoró de 62 a 95) con `export_cycles.py --min-qa-score 0.80` y hacer merge. Los ciclos recientes tienen mejor calidad de SDD y análisis de FR. | Antes de M2 | ⬜ |
| M2.arch | **Fine-tuning `ovd-arch-assistant`** (Qwen2.5-Coder-7B) — GGUF ya generado (`qwen-arch-ovd-Q4_K_M.gguf`, 4.4 GB), registrado en Ollama. Pendiente: validar con benchmark. | Completado técnicamente | 🔨 |
| M2.analyzer | **Fine-tuning `deepseek-r1:14b`** para `analyze_fr` — dataset actual aplica directo (análisis de FR + generación de SDD). Produce `ovd-analyzer` en Ollama. | Después de M1.5 | ⬜ |
| M3 | Modelos fine-tuneados activos — superan a sus bases en benchmark propio por rol | Después de M2.arch + M2.analyzer | ⬜ |
| M4 | **Fine-tuning `qwen3-coder:30b`** para agentes de implementación — requiere dataset de código generado + aprobado (construido con S41 RAG Learning) | S41 maduro + M3 | ⬜ |
| M5 | Adapter LoRA por workspace — cada workspace tiene su propio modelo especializado | Fase B madura | ⬜ |
| M6 | Modelo como diferenciador del SaaS — cada org cliente tiene el suyo | Fase C | 💡 |

> **Infraestructura ya implementada:** `ovd_fine_tuned_models`, Model Registry API, JSONL export diario, pipeline MLX + llama.cpp, activación via Ollama. Ver detalle en `docs/MODEL_STRATEGY.md` sección 8.

---

### Plan M2.arch — Fine-tuning Arquitecto (ya ejecutado, pendiente validación)

**Estado:** GGUF generado y registrado en Ollama como `ovd-arch-assistant:latest` (4.7 GB).
**Pendiente (M3):** benchmark comparativo contra `qwen2.5-coder:7b` base en tareas de `analyze_fr` y `generate_sdd`.

**Archivos generados:**
- `src/finetune/models/qwen2.5-coder-7b-4bit/` — modelo base descargado
- `src/finetune/adapters/` — adapter LoRA entrenado
- `src/finetune/models/fused/` — adapter fusionado con base
- `src/finetune/models/qwen-arch-ovd.f16.gguf` — GGUF full precision (14.2 GB)
- `src/finetune/models/qwen-arch-ovd-Q4_K_M.gguf` — cuantizado producción (4.4 GB)

---

### Plan M2.analyzer — Fine-tuning DeepSeek-R1:14B para analyze_fr

**Modelo base:** `deepseek-r1:14b` (modelo local, rol `OVD_MODEL_ANALYZER`)
**Dataset:** `data/merged.jsonl` — aplica directo (ejemplos de análisis de FR y generación de SDD)
**Resultado esperado:** `ovd-analyzer` en Ollama, especializado en razonamiento sobre Feature Requests

#### Fase 0 — Preparación

```bash
cd src/finetune
source mlx-env/bin/activate  # mlx-lm ya instalado

# Enriquecer dataset primero (M1.5)
python export_cycles.py --min-qa-score 0.80 --output data/recent_cycles.jsonl
# Merge con dataset existente si hay ciclos nuevos de calidad
```

#### Fase 1 — Descargar y convertir modelo base

```bash
# DeepSeek-R1-14B desde HuggingFace (formato mlx)
mlx_lm.convert \
  --hf-path mlx-community/DeepSeek-R1-Distill-Qwen-14B-4bit \
  --mlx-path src/finetune/models/deepseek-r1-14b-4bit
```

#### Fase 2 — Fine-tuning QLoRA

Archivo `src/finetune/mlx_config_analyzer.yaml`:
```yaml
model: "./models/deepseek-r1-14b-4bit"
data: "./data/mlx"
train: true
seed: 42
batch_size: 4
iters: 600
learning_rate: 5e-5
warmup: 60
weight_decay: 0.01
grad_checkpoint: false
val_batches: 20
steps_per_report: 25
steps_per_eval: 100
save_every: 100
lora_layers: 24
lora_parameters:
  rank: 16
  alpha: 32
  dropout: 0.05
mask_prompt: true
max_seq_length: 4096
adapter_path: "./adapters-analyzer"
```

```bash
cd src/finetune && mlx_lm.lora --config mlx_config_analyzer.yaml
```

#### Fase 3 — Export a GGUF y registro en Ollama

```bash
# Fusionar adapter
mlx_lm.fuse \
  --model src/finetune/models/deepseek-r1-14b-4bit \
  --adapter-path src/finetune/adapters-analyzer \
  --save-path src/finetune/fused-analyzer \
  --de-quantize

# Convertir con llama.cpp
python /opt/llama.cpp/convert_hf_to_gguf.py src/finetune/fused-analyzer \
  --outtype f16 --outfile src/finetune/models/ovd-analyzer.f16.gguf
/opt/llama.cpp/build/bin/llama-quantize \
  src/finetune/models/ovd-analyzer.f16.gguf \
  src/finetune/models/ovd-analyzer-Q4_K_M.gguf Q4_K_M

# Registrar en Ollama
cat > src/finetune/Modelfile-analyzer << 'EOF'
FROM ./models/ovd-analyzer-Q4_K_M.gguf
SYSTEM """Eres un arquitecto de software senior especializado en OVD Platform. Analizas Feature Requests y generas SDDs de alta calidad."""
PARAMETER temperature 0.6
PARAMETER num_ctx 8192
EOF
ollama create ovd-analyzer -f src/finetune/Modelfile-analyzer

# Activar en engine
# OVD_MODEL_ANALYZER=ovd-analyzer  en .env
```

#### Cuantizaciones recomendadas (DeepSeek-R1 14B)

| Formato | Tamaño aprox. | Uso |
|---|---|---|
| Q8_0 | ~14.5 GB | Primera evaluación — máxima calidad |
| **Q4_K_M** | **~8.5 GB** | **Producción — balance óptimo** |
| Q5_K_M | ~10 GB | Si Q4 se siente degradado |

#### Riesgos

| Riesgo | Mitigación |
|---|---|
| Overfitting con 312 ejemplos | Monitorear val_loss; enriquecer dataset con M1.5 antes de entrenar |
| DeepSeek thinking tokens en fine-tuning | Usar `mask_prompt: true`; verificar que `<think>` no contamina el loss |
| GGUF export falla para DeepSeek | Asegurar llama.cpp compilado desde fuente (soporte DeepSeek actualizado) |

---

### Por qué no fine-tunear qwen3-coder-next (80B MoE)

El modelo 80B MoE ya tiene capacidad de razonamiento muy alta para QA review y security audit. Fine-tunearlo requeriría un dataset específico de reviews (no el actual de analyze_fr/SDD) que aún no está construido. Se evalúa en M4 cuando S41 RAG Learning haya acumulado suficientes ejemplos.

### Por qué no fine-tunear qwen3-coder:30b todavía (M4)

El 30B necesita un dataset de implementación — ejemplos de código generado + tests pasando + aprobado por el equipo. Ese dataset se construye naturalmente con el tiempo a medida que los ciclos acumulan entregas exitosas. S41 RAG Learning es el prerrequisito para tener ese dataset de calidad.

---

## FASE 5 — Despliegue Cloud (Prerrequisito FASE C)

**Objetivo:** el engine corre en un servidor accesible por el equipo vía HTTPS. El TUI apunta a la URL cloud. El dashboard web se sirve desde un dominio propio.

**Fecha de identificación:** 2026-04-16
**Estado general:** 🔨 En progreso — P1 completado en código, P0 infraestructura pendiente (VPS/dominio)

---

### GAP-CLOUD-01 — Infraestructura base (BLOQUEANTE P0)

| # | Item | Descripción | Estado |
|---|------|-------------|--------|
| C01.A | Proveedor VPS seleccionado | VPS con mínimo 4 GB RAM, 2 vCPU, 40 GB SSD. Ver `docs/CLOUD_ALTERNATIVES.md` para opciones y costos | ⬜ |
| C01.B | Dominio y DNS | Dominio propio (ej: `ovd.omarrobles.dev`). Registrar y apuntar A-record al IP del VPS | ⬜ |
| C01.C | TLS — certificado Let's Encrypt | nginx como reverse proxy con `certbot --nginx`. Rutas: `api.ovd.omarrobles.dev` → engine:8001, `ovd.omarrobles.dev` → dashboard | ⬜ |
| C01.D | Firewall mínimo | UFW: abrir solo 22 (SSH), 80 (HTTP redirect), 443 (HTTPS). Engine y NATS solo en red interna Docker | ⬜ |

---

### GAP-CLOUD-02 — Ollama en cloud (BLOQUEANTE P0)

| # | Item | Descripción | Estado |
|---|------|-------------|--------|
| C02.A | Decisión: Ollama hosteado vs. API de embeddings | **Decisión tomada 2026-04-17:** Opción B — OpenAI `text-embedding-3-small` como provider default en producción (`OVD_RAG_EMBEDDING_PROVIDER=openai`). Ollama se mantiene como opción dev local. | ✅ |
| C02.B | Configurar `EMBEDDING_PROVIDER` en `rag.py` | `rag.py` refactorizado con `_get_embeddings()`: switch `ollama` / `openai` por `OVD_RAG_EMBEDDING_PROVIDER`. Secret `openai_api_key` en entrypoint y compose. | ✅ |
| C02.C | Modelos LLM para agentes en cloud | Los modelos `qwen2.5-coder:7b` requieren ≥8 GB VRAM. En VPS sin GPU: usar solo Claude/OpenAI. `.env.prod.example` documenta `OVD_MODEL=claude-sonnet-4-6` como default cloud. | ✅ |

---

### GAP-CLOUD-03 — Node.js en Dockerfile del engine

| # | Item | Descripción | Estado |
|---|------|-------------|--------|
| C03.A | Agregar Node.js al Dockerfile del engine | `nodejs npm` en `apt-get install` del `src/engine/Dockerfile`. `npx` disponible en runtime. | ✅ |
| C03.B | Verificar `npx @upstash/context7-mcp` en container | Cubierto por `test_docker_smoke.py` (Block D) — el smoke test confirma que el engine arranca dentro del container con el entrypoint completo. | ✅ |

---

### GAP-CLOUD-04 — Dashboard web: Dockerfile + build pipeline

| # | Item | Descripción | Estado |
|---|------|-------------|--------|
| C04.A | `Dockerfile` para el dashboard React | `src/dashboard/Dockerfile`: multi-stage `oven/bun:1.2-alpine` → `nginx:1.27-alpine`. HEALTHCHECK incluido. | ✅ |
| C04.B | Variable `VITE_API_URL` en build | ARG `VITE_API_URL` en Dockerfile, pasado desde `docker-compose.prod.yml` vía `build.args`. | ✅ |
| C04.C | nginx config para SPA React | `src/dashboard/nginx.conf`: `try_files $uri /index.html`, gzip, caché 1 año para assets con hash, endpoint `/health.txt`. | ✅ |

---

### GAP-CLOUD-05 — Migraciones automáticas en producción

| # | Item | Descripción | Estado |
|---|------|-------------|--------|
| C05.A | Runner de migraciones en `docker-entrypoint.sh` | `alembic upgrade head` + `seed_prod.sql` en el entrypoint. `set -e` garantiza que si falla, el container no arranca. | ✅ |
| C05.B | `alembic.ini` apuntando a `DATABASE_URL` de producción | `sqlalchemy.url` usa `%(DATABASE_URL)s` — lee la env var sin hardcodear. | ✅ |
| C05.C | Migración inicial de datos dev → prod | `src/engine/migrations/seed_prod.sql`: org + usuario admin + proyecto + stack con `ON CONFLICT DO NOTHING` (idempotente). | ✅ |

---

### GAP-CLOUD-06 — TUI: distribución multiplataforma

| # | Item | Descripción | Estado |
|---|------|-------------|--------|
| C06.A | Cross-compilation para Linux/Windows | GitHub Actions `tui-release.yml` (marcado ✅ en S14.D) — verificar que efectivamente compila targets: `x86_64-unknown-linux-musl`, `x86_64-pc-windows-gnu`, `aarch64-apple-darwin` | ⬜ |
| C06.B | GitHub Release automático con binarios | Al hacer tag `v*`, el workflow sube los 4 binarios como assets del release | ⬜ |
| C06.C | `ovd init` — wizard de primera configuración | Crear subcomando CLI que guía al usuario: ingresa URL del engine, org_id, hace login y guarda `~/.ovd/config.toml`. Hoy se hace manualmente | ⬜ |
| C06.D | Documentación de instalación | Script de instalación: `curl -fsSL https://install.ovd.omarrobles.dev | sh`. Descarga el binario correcto según OS/arch | ⬜ |

---

### GAP-CLOUD-07 — PostgreSQL: persistencia y backup

| # | Item | Descripción | Estado |
|---|------|-------------|--------|
| C07.A | `restart: always` en postgres dev | Pendiente. Documentado en README: `docker start postgres_db` tras reinicio. Aplicar con: `docker update --restart always postgres_db` | ⬜ |
| C07.B | Backup diario automatizado en producción | Servicio `ovd-backup` en `docker-compose.prod.yml`: pg_dump diario comprimido en volumen `backup_data`, retención 30 archivos. Pendiente: replicar a S3/Backblaze. | ✅ |
| C07.C | Backup pgvector (embeddings RAG) | El servicio `ovd-backup` incluye todo `ovd_prod` (tablas langchain_pg_*). Pendiente: documentar script de re-indexado como recovery alternativo. | ⬜ |
| C07.D | Test de restore | Procedimiento documentado y probado de restore desde backup. SLA objetivo: < 1 hora de RPO | ⬜ |

---

### GAP-CLOUD-08 — GitHub PAT → GitHub App (P3 largo plazo)

| # | Item | Descripción | Estado |
|---|------|-------------|--------|
| C08.A | GitHub App creada en cuenta `orobles40` | Permisos: Contents (write), Pull Requests (write), Metadata (read). Generar private key | ⬜ |
| C08.B | Autenticación JWT de GitHub App en engine | Reemplazar PAT en `graph.py` Sprint 6 por JWT generado con la private key de la App. Librería: `PyGithub` o `githubkit` | ⬜ |
| C08.C | Instalación de la App por workspace | En el Stack Registry de cada proyecto: campo `github_installation_id` para que el engine use el token correcto por repo | ⬜ |

---

### GAP-CLOUD-09 — Observabilidad operacional

| # | Item | Descripción | Estado |
|---|------|-------------|--------|
| C09.A | Agregador de logs | uvicorn escribe a stdout → `docker logs -f ovd-engine`. Mínimo viable funcional en prod. Loki/journald como mejora futura. | ✅ |
| C09.B | Alertas de ciclo colgado | OTEL + span con timeout: si `cycle_span` dura > 30 min sin evento `done`, emitir alerta. Canal: email o Telegram bot | ⬜ |
| C09.C | Dashboard de métricas (S17.C ya implementado) | S17.C Telemetría en Web App ✅. Funciona con datos reales — verificar en primer deploy. | ✅ |
| C09.D | Health checks en todos los servicios | Engine: `GET /health` ✅. Dashboard nginx: `GET /health.txt` ✅. Caddy: healthcheck en compose ✅. | ✅ |

---

### GAP-CLOUD-10 — Stack Profile por proyecto ⚠️ BLOQUEANTE PRE-PRODUCCIÓN

> **Decisión de diseño (2026-04-22):** El engine detecta el runner de tests automáticamente por extensión de archivo (`.py` → pytest, `.ts` → vitest, `.rs` → cargo). Este enfoque requiere código nuevo en `graph.py` por cada lenguaje adicional y no es agnóstico al stack real del proyecto. La solución correcta es que **cada proyecto declare su propia configuración de comandos** al momento de crearse en la plataforma. Esto debe implementarse antes de salir a producción, ya que sin ello los ciclos multi-lenguaje pueden fallar silenciosamente o ejecutar el runner equivocado.

**Objetivo:** el motor OVD debe ser agnóstico al lenguaje. Los comandos de test, build y lint deben configurarse por proyecto, no estar hardcodeados en el engine.

#### Cambios requeridos

**C10.A — Migración: campos de stack en `ovd_projects`**

```sql
ALTER TABLE ovd_projects
  ADD COLUMN test_command  TEXT,   -- ej: "pytest tests/ -v"
  ADD COLUMN build_command TEXT,   -- ej: "npm run build"
  ADD COLUMN lint_command  TEXT;   -- ej: "ruff check src/"
```

- Columnas opcionales (`NULL` = usar detección automática como fallback)
- Migración Alembic en `src/engine/migrations/`

**C10.B — Dashboard: formulario de creación/edición de proyecto**

Agregar campos al formulario de proyecto (`src/dashboard/src/pages/Projects.tsx`):

| Campo | Placeholder | Descripción |
|-------|-------------|-------------|
| Comando de tests | `pytest tests/ -v` | Se ejecuta en `run_tests` |
| Comando de build | `npm run build` | Opcional — validación pre-entrega |
| Comando de lint | `ruff check src/` | Opcional — calidad de código |
| Lenguaje principal | `python / typescript / rust` | Info para el SDD y los agentes |
| Framework | `fastapi / react / actix` | Contexto adicional para SDD |

**C10.C — Engine: `run_tests` lee configuración del proyecto**

En `src/engine/graph.py`, función `run_tests`:

```python
# Prioridad: 1) project_test_command del estado, 2) detección automática
project_test_command = state.get("project_test_command")
if project_test_command:
    # Ejecutar el comando configurado directamente (split para subprocess)
    cmd = project_test_command.split()
    runner = "custom"
else:
    # Fallback: detección automática actual (pytest/vitest/cargo)
    runner, cmd = _detect_runner_and_cmd(work_dir, sys.executable)
```

La API `/run` debe leer `test_command` de `ovd_projects` y inyectarlo en el estado como `project_test_command`.

**C10.D — Propagación del stack profile al SDD**

El nodo `generate_sdd` debe recibir el stack profile del proyecto (lenguaje, framework, test_command) para que el SDD generado sea coherente con las herramientas reales del workspace. Hoy el perfil se lee vía RAG pero no se pasa directamente.

| # | Item | Descripción | Estado |
|---|------|-------------|--------|
| C10.A | Migración DB: columnas de stack | `ALTER TABLE ovd_projects ADD COLUMN test_command TEXT, build_command TEXT, lint_command TEXT` | ⬜ |
| C10.B | Dashboard: formulario de stack profile | Campos test_command, build_command, lint_command, language, framework en create/edit proyecto | ⬜ |
| C10.C | Engine: `run_tests` lee project_test_command | Prioridad: config del proyecto → fallback: detección automática. Sin cambios de código por cada lenguaje nuevo | ⬜ |
| C10.D | SDD recibe stack profile explícito | `generate_sdd` recibe language/framework/test_command del proyecto para generar tareas coherentes | ⬜ |

> **Impacto de no implementar:** el engine continuará funcionando para proyectos Python (pytest auto-detectado), pero proyectos con stacks no estándar (Gradle, Maven, Go test, Makefile, etc.) requerirán modificaciones manuales en `graph.py` por cada caso. En producción con múltiples clientes esto es un bloqueante operacional.

---

### Resumen de prioridades cloud

| Prioridad | GAP | Bloqueante para | Estado |
|-----------|-----|-----------------|--------|
| **P0** | C01 — VPS + dominio + TLS | Todo lo demás | ⬜ Pendiente (infraestructura) |
| **P0** | C02 — Embeddings cloud | RAG funcional | ✅ Resuelto en código |
| **P0** | C10 — Stack Profile por proyecto | Engine agnóstico al lenguaje — pre-producción | ⬜ Pendiente (debe implementarse antes del go-live) |
| **P1** | C03 — Node.js en Dockerfile | MCP context7 en prod | ✅ Resuelto |
| **P1** | C04 — Dockerfile dashboard | Web App accesible | ✅ Resuelto |
| **P1** | C05 — Migraciones automáticas | Deploy sin intervención manual | ✅ Resuelto |
| **P2** | C06 — TUI distribución | Equipo usa el TUI | ⬜ Pendiente |
| **P2** | C07 — Backup PostgreSQL | Continuidad operacional | 🔨 C07.B hecho, C07.A/C/D pendientes |
| **P3** | C08 — GitHub App | SaaS multi-cliente | ⬜ Pendiente |
| **P3** | C09 — Observabilidad | Diagnóstico en producción | 🔨 Básica lista, alertas pendientes |

**Próximo paso real:** contratar VPS (C01.A) y configurar dominio (C01.B). Todo el código está listo para ese deploy, excepto C10 que debe implementarse antes del go-live.

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
FASE M (Modelo Propio):       4/9  hitos     44%  🔨  (M0/SM1/M1/M2.arch ✅ — ovd-arch-assistant en Ollama. Pendiente: M1.5 dataset, M2.analyzer deepseek-r1:14b, M3 benchmark, M4 qwen3-coder:30b)
FASE C (SaaS Producto):       0/7  items      0%  💡  (largo plazo)
──────────────────────────────────────────────────────────────
Total implementado:          138/138 items  100%  ✅

Última actualización: 2026-04-12 — S11.H completado (138/138 ✅). ROADMAP v1 100% implementado.
  Tests: 481/481 pasando. Próximo foco: despliegue centralizado → distribución TUI (5.F).

Stack definitivo (2026-03-25, revisión 2026-04-21):
  Backend API  → Python FastAPI (consolida Bridge TypeScript — no extender más el Bridge)
  Agentes      → Python LangGraph
  Fine-tuning  → Python Unsloth/LlamaFactory
  MCP Servers  → Python
  Deps Python  → uv + pyproject.toml
  Web App      → React + Vite + shadcn/ui + Tailwind (src/dashboard/) — pendiente migración Flutter
  TUI          → Rust + Ratatui (binario standalone, cliente del Engine) — pendiente migración Flutter
  Cliente fut. → Flutter (web + macOS + Linux + Windows desde un solo codebase Dart) — ver FASE F
  Referencia   → opencode (patrones y diseño, no código a mantener)

Modelo de despliegue (decisión 2026-04-12):
  Centralizado — Engine en servidor dedicado Omar Robles, TUI como cliente en equipo.
  Prerrequisito para 5.F: servidor en producción con dominio + TLS.

Decisiones pendientes:
  S11.E          → comando @research: exponer desde TUI Rust o endpoint FastAPI dedicado
  5.F (TUI dist) → bloqueado hasta tener servidor centralizado levantado
  S21            → verificar que qwen2-vl:7b acepta base64 vía API OpenAI-compatible de Ollama antes de implementar
  FASE F         → iniciar después de que VPS (C01) esté operativo
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

---

## Épicas estratégicas

> Iniciativas de largo plazo que requieren diseño técnico dedicado antes de entrar a sprint.
> Cada épica se descompone en sprints cuando su sesión de diseño esté completa.
> Última actualización: 2026-04-30

---

### ÉPICA-1 — Modos de operación: Greenfield / Incremental / Migración

**Registrada:** 2026-04-30
**Prioridad:** Alta
**Estado:** 💡 Diseño pendiente

#### Contexto

OVD opera hoy exclusivamente en modo **greenfield**: cada ciclo genera el sistema completo desde cero,
sobreescribiendo el directorio de trabajo. Esto limita el uso a proyectos nuevos y hace que los ciclos
de benchmark necesiten limpiar el workspace antes de cada ejecución.

Para ser una herramienta de desarrollo real, OVD debe soportar tres modos de operación distintos:

#### Modo 1 — Greenfield (ya implementado)

El directorio está vacío. OVD genera todos los artefactos desde cero.

```
FR: "Implementar sistema de contratos y beneficios"
→ OVD genera src/, migrations/, tests/, Dockerfile, etc.
```

#### Modo 2 — Incremental (no implementado)

El proyecto ya tiene código existente. OVD lee el estado actual y genera **solo lo nuevo**,
preservando todo lo que ya existe y funciona.

```
FR-1: "Crear sistema de login" → genera auth/
FR-2: "Agregar módulo de contratos" → lee auth/ existente, genera solo contracts/
FR-3: "Agregar reportes PDF" → lee auth/ + contracts/, genera solo reports/
```

**Regla clave:** el código existente es **intocable** — solo se agregan o modifican los artefactos
que el nuevo FR requiere explícitamente.

#### Modo 3 — Migración tecnológica (no implementado)

El proyecto tiene un stack origen que debe transformarse a un stack destino. El código existente
es el **input de transformación**, no una base a preservar.

```
FR: "Migrar este sistema de WebLogic 12 a WebLogic 14"
→ OVD lee descriptores WL12, mapea patrones al equivalente WL14, genera la migración

FR: "Migrar de Struts 1.x a Spring Boot 3"
→ OVD lee Actions/Dispatch, produce Controllers/@RestController equivalentes

FR: "Migrar base de datos de Oracle 12c a Oracle 19c"
→ OVD lee DDL, triggers, packages PL/SQL, genera equivalentes compatibles con 19c
```

**Regla clave:** el código existente es el **origen** — se analiza para entender estructura y lógica,
luego se genera el equivalente en el stack destino.

#### Diferencias críticas entre modos

| Dimensión | Greenfield | Incremental | Migración |
|-----------|-----------|-------------|-----------|
| Código existente | No hay | Intocable | Es el input |
| Qué se genera | Todo | Solo lo nuevo | Equivalente transformado |
| Conflictos de archivos | No aplica | No sobreescribir | Reemplazar controlado |
| Stack origen conocido | No aplica | Mismo stack | Stack origen + destino |
| read_existing_codebase | No necesario | Obligatorio | Obligatorio |

#### Configuración de proyecto en el Workspace

Antes de lanzar cualquier ciclo, el proyecto debe tener configurado su contexto de fuentes y base de
datos. Esta configuración vive en `ovd_projects` y se resuelve en `session_create` antes de generar.

**Fuentes del código existente (tres orígenes posibles):**

| Campo | Descripción | Ejemplo |
|-------|-------------|---------|
| `directory` | Ruta local con los fuentes | `/Users/omar/proyectos/hhmm/src` |
| `github_repo` | Repositorio GitHub (público o privado con token) | `omarrobles/hhmm` |
| `gitlab_repo` | Repositorio GitLab (self-hosted o cloud) | `gitlab.cas.cl/sistemas/hhmm` |

Solo uno de los tres es necesario. Si se especifican varios, el orden de prioridad es:
`directory` > `github_repo` > `gitlab_repo`. El nodo `clone_repo` ya maneja GitHub; GitLab
requiere extensión del mismo nodo.

**Esquema de base de datos (tres variantes):**

| Variante | Descripción | Cuándo aplica |
|----------|-------------|---------------|
| `db_reuse` | El esquema existente se mantiene tal cual | Modo incremental: nueva funcionalidad sobre tablas actuales |
| `db_migrate` | El esquema se transforma (mismas entidades, nuevo motor o nueva versión) | Migración Oracle 12c → 19c, Oracle → PostgreSQL |
| `db_new` | Esquema nuevo desde cero, sin relación con el existente | Modo greenfield o nuevo módulo sin dependencia de tablas anteriores |

Campos en `ovd_projects` para la dimensión BD:

```json
{
  "db_engine_source": "oracle_12c",
  "db_engine_target": "oracle_19c",
  "db_schema_mode": "db_migrate",
  "db_schema_source": "migrations/",
  "db_connection_target": "host.docker.internal:1521/XEPDB1"
}
```

El agente `database` recibe estos campos en su prompt y genera DDL, triggers y migraciones
adecuados al motor destino. En modo `db_reuse`, el agente recibe el DDL actual y genera solo
los `ALTER TABLE` o nuevos objetos necesarios para el FR, sin recrear lo que ya existe.

**Combinaciones válidas modo × BD:**

| Modo | db_schema_mode | Comportamiento del agente database |
|------|---------------|-------------------------------------|
| Greenfield | `db_new` | Genera DDL completo desde cero |
| Incremental | `db_reuse` | Solo agrega objetos nuevos (ALTER, nuevas tablas) |
| Incremental | `db_migrate` | Transforma esquema existente (ej: agregar columnas, cambiar tipos) |
| Migración | `db_migrate` | Traduce DDL origen al dialecto del motor destino |
| Reutilización | `db_reuse` o `db_new` | Copia estructura validada del ciclo base, adapta al nuevo proyecto |

#### Trabajo técnico requerido

**Fase A — Configuración de proyecto extendida:**
- Nuevos campos en `ovd_projects`: `gitlab_repo`, `db_engine_source`, `db_engine_target`,
  `db_schema_mode`, `db_schema_source`, `db_connection_target`
- UI en dashboard: formulario de proyecto con secciones "Fuentes" y "Base de datos"
- Validación en `session_create`: si `db_schema_mode != db_new`, verificar que existe
  esquema origen (archivo DDL o directorio `migrations/`)

**Fase B — Selección de modo en el FR:**
- Campo `mode: greenfield | incremental | migration | reuse` en `StartSessionRequest`
- UI en el dashboard: selector de modo con descripción clara por caso de uso
- Validación: modos `incremental`, `migration`, `reuse` requieren fuente de código configurada

**Fase C — Nodo `read_existing_codebase`:**
- Ejecutar antes de `analyze_fr` cuando `mode != greenfield`
- Clonar repo (GitHub/GitLab) o leer `directory` local
- Indexar: archivos, módulos, funciones exportadas, esquema BD si existe
- Producir `codebase_context` inyectado en los prompts de todos los agentes
- En modo incremental: context indica "esto ya existe, no lo regeneres"
- En modo migración: context es el input a transformar
- En modo reutilización: context es el ejemplo validado a seguir

**Fase D — Agente de migración (modos migration/reuse):**
- Especializado por par de stacks/motores: `wl12→wl14`, `oracle12c→oracle19c`, `struts→springboot`
- Recibe artefacto origen y genera equivalente en stack/motor destino
- Para BD: traduce DDL, triggers, packages PL/SQL al dialecto destino
- Los stack templates (S58) son la base — necesitan variantes "origen" y "destino"

**Fase E — write_artifacts selectivo (modo incremental):**
- Antes de escribir, verificar si el archivo ya existe
- Política de merge: `overwrite` (greenfield) | `append-only` | `merge-smart`
- Para BD en modo `db_reuse`: solo generar scripts `ALTER` o nuevos objetos, nunca `DROP`

#### Casos de uso reales identificados

| Caso | Modo | Fuente | BD origen | BD destino |
|------|------|--------|-----------|-----------|
| HHMM: nuevo módulo de liquidaciones | Incremental | GitLab CAS / directorio local | Oracle 19c (existente) | Oracle 19c (mismas tablas + nuevas) |
| HHMM: migración WL12 → WL14 | Migración | GitLab CAS | Oracle 19c (sin cambio) | Oracle 19c (sin cambio) |
| Migración Oracle 12c → 19c (PL/SQL) | Migración | directorio local | Oracle 12c | Oracle 19c |
| Sistema de licitaciones (base contratos S103) | Reutilización | ciclo S103 QA=90 | Oracle XE (nuevo) | Oracle XE |
| Nuevo proyecto React + FastAPI desde cero | Greenfield | — | — | PostgreSQL o Oracle (nuevo) |

#### Dependencias

- `github_repo` + `clone_repo` ya existen — extender para GitLab
- `ovd_stack_profiles` ya tiene `language` — extender con dimensión BD
- Stack templates (S58) necesitan variantes "origen" para modo migración
- RAG puede indexar el codebase clonado para mejorar contexto de los agentes
- `_build_type_contract()` (S103-P1) es la base para extraer el contrato de tipos del codebase existente

#### Modo 4 — Reutilización de sistemas probados como base

Un sistema que ya alcanzó QA ≥ 90 en ciclos anteriores es **conocimiento validado**. Al desarrollar
un sistema nuevo similar, OVD debe poder reutilizar ese sistema probado como punto de partida en lugar
de regenerar desde cero.

```
Ciclo S103: Sistema Contratos/Beneficios → QA=90 ✅ (validado)

Nuevo FR: "Implementar sistema de gestión de licitaciones con autenticación RUT"
→ OVD detecta similitud con el sistema de contratos validado
→ Usa contratos/S103 como base: rut_validator, auth/, estructura Oracle, patrones React
→ Genera solo lo diferente (licitaciones vs contratos, nuevas reglas de negocio)
```

**Diferencia con modo incremental:** en modo incremental el código existente pertenece al
**mismo proyecto** (misma base de código). En modo reutilización, el código base viene de
**otro proyecto ya validado** — es una plantilla probada, no la misma codebase.

**Casos de uso:**
- Nuevo módulo similar a uno ya validado en otro cliente → usar el ciclo validado como template
- Migración: el sistema origen ha evolucionado en ciclos previos → la versión más reciente y
  con mayor QA es la base de la migración, no la versión original
- Variante de stack: mismo sistema pero en otro lenguaje → el diseño probado (SDD, endpoints,
  entidades) se reutiliza; solo los agentes implementadores cambian

**Trabajo técnico requerido:**

- **Búsqueda semántica en ovd_cycles:** dado un nuevo FR, buscar en ciclos anteriores con
  `qa_score ≥ 85` que tengan FR similar (pgvector similarity sobre `fr_text`)
- **Selección del ciclo base:** proponer al usuario los top-3 ciclos más similares y permitir
  elegir cuál usar como referencia
- **Inyección en prompts:** el SDD y los agentes reciben el `agent_results` del ciclo base
  como contexto de referencia, no como código a copiar sino como ejemplo validado
- **Diferenciación automática:** el type contract del ciclo base (S103-P1) se usa para
  mantener consistencia de nombres en el nuevo sistema

> Esta es la base para el concepto de **librería de sistemas validados** — cada ciclo QA ≥ 90
> se convierte en un activo reutilizable para futuros proyectos del mismo dominio.

---

#### Modo 5 — Corrección de issues en sistemas existentes (no implementado)

**Registrado:** 2026-05-04
**Prioridad:** Alta — caso de uso más frecuente en clientes con sistemas en producción

OVD debe poder recibir un bug report o issue sobre código existente, leer el código afectado,
entender el problema en contexto y generar el fix puntual — sin regenerar el sistema completo.

```
FR: "El endpoint /reservas/cancelar lanza 500 cuando el turno no existe"
→ OVD lee el código de reservas/ (router, servicio, tests)
→ Identifica el path no manejado (None check faltante)
→ Genera fix puntual: solo modifica el archivo afectado
→ Genera o actualiza el test que cubra el caso

FR: "El módulo de liquidaciones de HHMM falla al calcular horas nocturnas"
→ OVD lee liquidaciones/ + el DDL de las tablas relevantes
→ Identifica el error en la lógica de cálculo de tramos horarios
→ Genera el fix + test de regresión
```

**Diferencia con modo incremental:** en modo incremental se agregan features nuevas sin tocar lo
existente. En corrección de issues, el objetivo es **modificar código existente** de forma
quirúrgica para resolver un defecto, preservando el resto del sistema intacto.

**Diferencia con `fr_type='bug'` actual:** hoy el tipo `bug` existe en `FRAnalysisOutput` pero
el flujo no lee el código existente — genera todo desde cero igualmente. Este modo corrige eso.

**Reglas del modo corrección:**

| Regla | Descripción |
|-------|-------------|
| Scope acotado | Solo modificar archivos directamente relacionados con el bug |
| Tests existentes deben pasar | `run_tests` ejecuta la suite existente — ningún test previo puede quebrarse |
| Generar test de regresión | El fix siempre incluye al menos un test que reproduzca el bug y verifique la corrección |
| No regenerar | `write_artifacts` usa política `merge-smart` — nunca sobreescribe el archivo completo |
| Evidencia del fix | QA verifica que el FR describe el bug, el código generado lo corrige y el test falla sin el fix |

**Trabajo técnico requerido:**

- **Fase A (compartida con modos 2-4):** nodo `read_existing_codebase` — lee el directorio o repo
- **Fase B:** detección de archivos relevantes para el bug — a partir del FR + contexto leído,
  identificar qué archivos son el foco del fix (puede ser heurístico + LLM)
- **Fase C:** `write_artifacts` en modo `merge-smart` — modifica solo las líneas afectadas,
  no el archivo completo (puede usar diff/patch approach)
- **Fase D:** `run_tests` ejecuta suite existente completa antes y después del fix
- **Fase E:** QA evalúa con criterio diferenciado: ¿el fix es puntual? ¿los tests previos pasan?

**Casos de uso reales identificados:**

| Caso | Sistema | Descripción |
|------|---------|-------------|
| HHMM — cálculo horas nocturnas | Oracle 19c + Java | Bug en lógica PL/SQL de tramos horarios |
| HHMM — liquidación feriados legales | Oracle 19c + Java | Error en tabla de feriados hard-codeados |
| API contratos — validación RUT | FastAPI + PostgreSQL | 422 en RUTs con dígito verificador `K` |
| Dashboard React — paginación | TypeScript + React 19 | Última página muestra registros duplicados |

---

#### Criterio de entrada a sprint

Una épica entra a sprint cuando:
1. Se completó la sesión de diseño técnico (prototipo en papel del flujo de nodos)
2. Se identificaron los archivos a modificar y las funciones a crear
3. Existe un FR de prueba que valida el modo (ej: FR de migración WL12→WL14 con proyecto real)

---

### ÉPICA-2 — Despliegue DigitalOcean + GenAI Platform

**Registrada:** 2026-05-04
**Prioridad:** Alta — objetivo: demo en vivo el 2026-05-18
**Estado:** 💡 Diseño aprobado — pendiente implementación

#### Contexto

OVD debe ser accesible desde una URL pública para la presentación del 18 de mayo 2026.
La investigación de DigitalOcean (2026-05-04) identificó tres opciones de arquitectura cloud.
La propuesta recomendada elimina la dependencia de Ollama en producción usando el GenAI Platform
de DigitalOcean como proveedor unificado para LLMs y embeddings.

#### Productos DigitalOcean relevantes

| Producto | Descripción | Precio |
|----------|-------------|--------|
| **App Platform** | PaaS container-based — deploya desde Dockerfile/GitHub. Workers persistentes. SSE y WebSockets sin restricciones documentadas. | $50/mes (2 vCPU / 4 GiB) |
| **Managed PostgreSQL** | PostgreSQL 16-18 administrado. **pgvector + pgvectorscale incluidos nativamente**. | $30/mes (2 GiB) |
| **GenAI Platform** | API unificada para modelos Anthropic, OpenAI, Meta, Mistral. Compatible con SDK de cada proveedor. Facturación consolidada DO. | Por token (ver tabla) |
| **Functions** | FaaS Python 3.12/3.13. Timeout máx 15 min, payload 1 MB. **No recomendado** para ciclo principal — payload insuficiente. | Por invocación |
| **GPU Droplets** | NVIDIA RTX 4000 Ada (20 GB VRAM) on-demand. Para self-hosting Ollama. | $0.76/hr |

**Modelos disponibles en GenAI Platform:**

| Modelo | Input | Output | Contexto | Uso en OVD |
|--------|-------|--------|---------|-----------|
| Claude Sonnet 4.6 | $3.00/1M | $15.00/1M | 200K | Agentes principales |
| Claude Haiku 4.5 | $1.00/1M | $5.00/1M | — | FR analysis, QA rápida |
| Claude Opus 4.7 | $5.00/1M | $25.00/1M | — | Ciclos críticos |
| GPT-4o mini | $0.15/1M | $0.60/1M | — | Alternativa costo |
| **BGE-M3** | $0.02/1M | — | — | **Embeddings RAG** |
| all-mini-lm-l6-v2 | $0.009/1M | — | — | Embeddings ligeros |

> Precios GenAI Platform = precios directos Anthropic/OpenAI. Ventaja: tráfico entre servicios
> DO no genera costo de egress (red interna). Facturación unificada en una cuenta DO.

#### Opciones de arquitectura

---

**Opción A — App Platform + GenAI Platform** *(recomendada para presentación 2026-05-18)*

```
[GitHub repo] → [DO App Platform]
                   FastAPI + LangGraph
                   2 vCPU / 4 GiB / $50/mes
                        │
                        ├── [DO Managed PostgreSQL]
                        │    pgvector + pgvectorscale
                        │    2 GiB / $30/mes
                        │
                        └── [DO GenAI Platform]
                             Claude Sonnet 4.6 (agentes)
                             BGE-M3 (embeddings RAG)
                             Variable por uso
```

| Atributo | Valor |
|----------|-------|
| Costo fijo | ~$80/mes |
| Costo variable | ~$5-15/ciclo (Claude Sonnet) + $0.01/bootstrap RAG |
| DevOps | Cero — TLS automático, CI/CD desde GitHub, health checks |
| Escalabilidad | Autoscale horizontal en App Platform (tier Dedicated) |
| Ollama | Eliminado de producción |
| Cambios en código | `OVD_RAG_EMBEDDING_PROVIDER=openai` + endpoint DO GenAI |

**Pros:** Más rápida de desplegar, sin mantenimiento de servidor, TLS gestionado por DO.
**Contras:** Menor control sobre el entorno, mismos precios de LLM que acceso directo.

---

**Opción B — Droplet 4GB + GenAI Platform** *(plan actual actualizado)*

```
[Droplet Basic 4GB / $24/mes]
   FastAPI + LangGraph + Caddy TLS
        │
        ├── [DO Managed PostgreSQL / $30/mes]
        │
        └── [DO GenAI Platform]
             Variable por uso
```

| Atributo | Valor |
|----------|-------|
| Costo fijo | ~$54/mes |
| DevOps | Manual (Caddy, docker-compose.prod.yml, actualizaciones) |
| Escalabilidad | Manual (resize Droplet) |

**Pros:** Más barato en costo fijo, más control del entorno.
**Contras:** Requiere DevOps, sin auto-scaling.

---

**Opción C — App Platform + GPU Droplet on-demand** *(para escala con modelos propios)*

```
[DO App Platform / $50/mes] + [DO Managed PostgreSQL / $30/mes]
        └── [GPU Droplet RTX 4000 Ada / $0.76/hr on-demand]
                   Ollama + Llama 4 / Qwen3
```

| Atributo | Valor |
|----------|-------|
| Costo fijo | $80/mes |
| Costo LLM | $0 por token (self-hosted) |
| GPU costo | $0.76/hr — solo cuando está activo |
| Break-even vs GenAI | ~$550/mes de LLM usage |

**Pros:** Cero costo por token si GPU está activa, control total de modelos.
**Contras:** GPU idle = costo desperdiciado. Setup Ollama manual en cada Droplet.

---

#### Decisión recomendada

**Opción A para el demo del 18 de mayo.** Razones:

1. Tiempo de despliegue: 2-3 días vs 5-7 días (Opción B/C)
2. Sin riesgo de configuración manual de TLS, firewall, docker
3. GenAI Platform es compatible con SDK de Anthropic — **cero cambios en el código de agentes**
4. Embeddings BGE-M3 ($0.02/1M) son comparables en calidad a `text-embedding-3-small` de OpenAI
5. Si el volumen de LLM crece, migrar a Opción C es un cambio de variable de entorno

**Cambio de código necesario para Opción A:**
- `OVD_RAG_EMBEDDING_PROVIDER=openai` (ya soportado en `rag.py`)
- `OVD_EMBED_MODEL=bge-m3` (o `all-mini-lm-l6-v2` para menor costo)
- `OPENAI_API_KEY` → apunta al endpoint DO GenAI Platform en lugar de OpenAI directo
- `ANTHROPIC_API_KEY` → apunta al endpoint DO GenAI Platform en lugar de Anthropic directo
- `OVD_CORS_ORIGINS=https://ovd.omarrobles.dev`

> **Nota:** DigitalOcean GenAI Platform usa endpoints compatibles con los SDKs oficiales.
> Verificar la URL base exacta del endpoint en la documentación de DO al momento de configurar.

#### Gaps a resolver antes del deploy (S112)

**Críticos:**

| Gap | Tarea |
|-----|-------|
| NATS ausente en docker-compose.prod.yml | Verificar si `task_checkout.py` funciona sin NATS (`USE_NATS=false`) o agregar servicio |
| Alembic: migraciones hasta S109 | Auditar que todas las columnas nuevas están en las migraciones |
| `infra/postgres/grant-readonly.sql` | Verificar existencia o crear el archivo referenciado |
| `OVD_SECRET` vs `OVD_ENGINE_SECRET` | Verificar naming consistente en entrypoint vs código |
| `seed_prod.sql` con datos HHMM | Reemplazar con proyecto demo neutro (ej: Sistema de Turnos) |
| Dominio `ovd.omarrobles.dev` | Registrar y apuntar al App Platform o Droplet |

**Altos:**

| Gap | Tarea |
|-----|-------|
| ADR-004 contradicción | Actualizar ADR-004: Option D (Claude API) es la opción de producción |
| ADR-005 inexistente | Crear ADR-005: decisión DigitalOcean vs alternativas (AWS, GCP, Fly.io) |
| Password admin | Cambiar `ovd-dev-2026` antes de producción |
| RAG en producción | Confirmar que BGE-M3 vía GenAI Platform reemplaza Ollama correctamente |

#### Plan de sprints

| Sprint | Contenido | Fecha objetivo |
|--------|-----------|----------------|
| **S111** | Nodo `read_existing_codebase` + Modo 5 básico (bug fixing sobre código existente) | 4-10 mayo |
| **S112** | Resolver gaps DO críticos + despliegue en App Platform + dominio | 11-16 mayo |
| **S113** | Dry run demo, seed demo neutro, guion presentación | 17 mayo |
| **Demo** | Presentación cliente | 18 mayo |

#### Scope del demo 2026-05-18

Lo que se puede mostrar en vivo:

| Demo | Modo | Estado al 18 mayo |
|------|------|------------------|
| Crear sistema de turnos desde cero | Greenfield | ✅ Ya funciona |
| Corregir bug en endpoint existente | Modo 5 | ✅ Si S111 completa |
| URL pública accesible por el cliente | DigitalOcean | ✅ Si S112 completa |

Lo que se presenta como roadmap (no demo en vivo):
- Modo 2 Incremental (agregar features sin romper lo existente)
- Modo 3 Migración tecnológica (WebLogic 12→14, Oracle 12c→19c)
- Modo 4 Reutilización de sistemas validados

---

### Sprint S114 — Model Selector: configuración de modelos por agente desde el dashboard

**Registrado:** 2026-05-07
**Prioridad:** Alta post-demo
**Estado:** ⬜ Pendiente — propuesta aprobada para implementar post S113
**Prerequisito:** S112 y S113 completados (plataforma DO operativa)

#### Contexto y motivación

Con S112 se estableció que DO GenAI Platform expone 60+ modelos bajo un endpoint
OpenAI-compatible (`https://inference.do-ai.run/v1`). El engine ya tiene toda la lógica
de routing por rol en `model_router.py` (variables `OVD_MODEL_BACKEND`, `OVD_MODEL_ANALYZER`,
etc.), pero la configuración solo es posible vía variables de entorno — requiere redeploy.

El objetivo de este sprint es exponer esa configuración en el dashboard para que el
operador pueda cambiar qué modelo usa cada agente sin tocar infraestructura.

#### Catálogo de modelos DO relevantes (verificado 2026-05-07)

| Modelo DO | Equivalente | Caso de uso |
|-----------|-------------|-------------|
| `anthropic-claude-4.6-sonnet` | Claude Sonnet 4.6 | Default todos los agentes — mejor calidad |
| `anthropic-claude-4.5-sonnet` | Claude Sonnet 4.5 | Alternativa económica |
| `anthropic-claude-haiku-4.5` | Claude Haiku 4.5 | Agentes rápidos / análisis liviano |
| `anthropic-claude-opus-4.7` | Claude Opus 4.7 | Máxima calidad en análisis complejos |
| `llama3.3-70b-instruct` | LLaMA 3.3 70B | Open source, codegen general |
| `deepseek-r1-distill-llama-70b` | DeepSeek R1 | Razonamiento / FRs complejos |
| `qwen3-coder-flash` | Qwen3 Coder | Codegen rápido, bajo costo |
| `bge-m3` | BGE-M3 | **Embeddings RAG — no cambiar** |

API para obtener catálogo actualizado:
```bash
GET https://inference.do-ai.run/v1/models
Authorization: Bearer <OPENAI_API_KEY>
```

#### Roles del engine y sus variables actuales

| Rol | Grupo | Variable env override |
|-----|-------|----------------------|
| `analyzer` | Análisis | `OVD_MODEL_ANALYZER` |
| `sdd` | Análisis | `OVD_MODEL_SDD` |
| `qa` | Análisis | `OVD_MODEL_QA` |
| `backend` | Implementación | `OVD_MODEL_BACKEND` |
| `frontend` | Implementación | `OVD_MODEL_FRONTEND` |
| `database` | Implementación | `OVD_MODEL_DATABASE` |
| `devops` | Implementación | `OVD_MODEL_DEVOPS` |
| `security_exec` | Implementación | — (hereda global) |
| *(global)* | — | `OVD_MODEL` + `OVD_AGENT_PROVIDER` |

#### Fase 1 — Configuración en memoria, sin DB (demo / MVP)

Implementar sin nueva tabla de BD. La config se aplica al proceso activo hasta el
próximo restart. Suficiente para demo y operación inicial.

**A. `api_v1.py` — 2 endpoints nuevos**

```
GET  /api/v1/catalog/models
     → llama inference.do-ai.run/v1/models, filtra modelos de texto (excluye imagen/TTS/embedding)
     → retorna [{id, display_name, family, recommended_roles}]

GET  /api/v1/orgs/{org_id}/model-config
     → retorna config activa en el proceso (env vars resueltos por model_router)
     → formato: {global_model, global_provider, by_role: {backend: {...}, analyzer: {...}, ...}}

PUT  /api/v1/orgs/{org_id}/model-config
     → actualiza variables en memoria del model_router (sin reinicio, sin DB)
     → body: {role: "backend", provider: "openai", model: "qwen3-coder-flash"}
     → aplica hasta próximo restart del engine
```

**B. `model_router.py` — soporte de override en memoria**

Agregar dict `_RUNTIME_OVERRIDES: dict[str, tuple[str, str]]` (role → (provider, model))
que la función `resolve()` consulta antes de las env vars.

El endpoint PUT escribe en este dict. Se limpia al reiniciar el proceso.

**C. `ModelDashboard.tsx` — reemplazar por dos tabs**

- **Tab "Configuración"** (nuevo):
  - Tabla con una fila por rol
  - Cada fila tiene un dropdown de modelo poblado desde `GET /catalog/models`
  - Botón "Guardar" llama `PUT /model-config`
  - Badge "en memoria / hasta próximo deploy" para que el operador sepa que no persiste

- **Tab "Fine-tuning"** (existente):
  - Todo el contenido actual de `ModelDashboard.tsx` se mueve aquí sin cambios

**D. `ovd.ts` — 3 métodos nuevos**

```typescript
getCatalogModels(): Promise<ModelEntry[]>
getModelConfig(orgId: string): Promise<ModelConfig>
updateModelConfig(orgId: string, role: string, provider: string, model: string): Promise<void>
```

#### Fase 2 — Persistencia en BD (post-demo, sprint independiente)

**E. Migración `20260601_0006_ovd_model_config.py`**

```sql
CREATE TABLE ovd_model_config (
  id           TEXT PRIMARY KEY,
  org_id       TEXT NOT NULL,
  project_id   TEXT,                    -- NULL = nivel org
  agent_role   TEXT NOT NULL,           -- 'backend' | 'analyzer' | '_global' | etc.
  provider     TEXT NOT NULL DEFAULT 'openai',
  model        TEXT NOT NULL,
  active       BOOLEAN NOT NULL DEFAULT true,
  time_created TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  time_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_ovd_model_config_unique
  ON ovd_model_config (org_id, COALESCE(project_id,''), agent_role)
  WHERE active = true;
```

**F. `model_router.resolve()` — consultar BD antes de env vars**

Nueva jerarquía:
```
1. BD: config (org_id + project_id + agent_role)   ← más específica
2. BD: config (org_id + NULL + agent_role)          ← nivel org
3. Env vars: OVD_MODEL_*, OVD_AGENT_PROVIDER
4. System default: openai + anthropic-claude-4.6-sonnet
```

**G. `PUT /api/v1/orgs/{org_id}/projects/{project_id}/model-config`**
Persiste en BD. Reemplaza el PUT en memoria de Fase 1.

#### Estimación de trabajo

| Fase | Componente | Esfuerzo estimado |
|------|-----------|-------------------|
| 1-A | api_v1.py (3 endpoints) | 2h |
| 1-B | model_router.py (_RUNTIME_OVERRIDES) | 1h |
| 1-C | ModelDashboard.tsx (2 tabs + form) | 3h |
| 1-D | ovd.ts (3 métodos) | 0.5h |
| **Total Fase 1** | | **~6.5h** |
| 2-E | Migración BD | 0.5h |
| 2-F | model_router.py (BD lookup) | 2h |
| 2-G | endpoint PUT persistente | 1h |
| **Total Fase 2** | | **~3.5h** |

#### Wireframe UI (Tab Configuración)

```
┌─────────────────────────────────────────────────────────────────┐
│  Modelo                  [Configuración]  [Fine-tuning]         │
│─────────────────────────────────────────────────────────────────│
│  ⚠ Cambios en memoria — se aplican hasta el próximo deploy      │
│                                                                 │
│  Rol              Modelo activo                                 │
│  ─────────────────────────────────────────────────────          │
│  Global (default) [anthropic-claude-4.6-sonnet         ▼]      │
│  Análisis FR/SDD  [anthropic-claude-4.6-sonnet         ▼]      │
│  QA Review        [anthropic-claude-4.6-sonnet         ▼]      │
│  Backend          [qwen3-coder-flash                   ▼]      │
│  Frontend         [anthropic-claude-4.6-sonnet         ▼]      │
│  Database         [llama3.3-70b-instruct               ▼]      │
│  DevOps           [anthropic-claude-haiku-4.5          ▼]      │
│                                                                 │
│  Dropdowns se cargan desde DO GenAI Platform en tiempo real     │
│                                                    [Guardar]    │
└─────────────────────────────────────────────────────────────────┘
```

---

### Sprint S115 — Parámetros LLM configurables (eliminar hardcoding)

**Motivación:** Los parámetros `max_tokens`, `temperature` y otros estaban hardcodeados en `model_router.py`. Cualquier ajuste requería un redeploy. El objetivo es que todo parámetro LLM sea configurable desde variables de entorno sin cambiar código.

**Prioridad:** Alta post-demo | **Dependencias:** S112, S114-Fase 1

---

#### Contexto y hallazgos (investigación 2026-05-07)

Durante S112 se identificaron los siguientes parámetros hardcodeados:

| Parámetro | Valor anterior | Env var S115 | Relevancia |
|---|---|---|---|
| `max_tokens` | `8192` (todos los providers) | `OVD_LLM_MAX_TOKENS` | DeepSeek V4 Pro soporta hasta 1M output; Qwen3 Flash 65,536 |
| `temperature` structured | `0.0` (Ollama/OpenAI) | `OVD_LLM_TEMPERATURE_STRUCTURED` | Roles: analyzer, sdd, qa, security, router, implementadores |
| `temperature` generation | `0.3` (Ollama/OpenAI) | `OVD_LLM_TEMPERATURE_GENERATION` | Roles: todos los demás |
| `temperature` claude structured | `0.2` (Claude) | hardcoded por diseño (Claude API) | Bajo control |
| `num_ctx` Ollama | `32768` | pendiente S115-A | Ventana de contexto local |
| `seed` Ollama | `42` | pendiente S115-A | Determinismo en dev |
| `request_timeout` | `ovd_llm_timeout_secs` | ya configurable | OK |

**Cambios aplicados en S112 (base para S115):**

En `settings.py`:
```python
ovd_llm_max_tokens: int = 8192                    # env: OVD_LLM_MAX_TOKENS
ovd_llm_temperature_structured: float = 0.0       # env: OVD_LLM_TEMPERATURE_STRUCTURED
ovd_llm_temperature_generation: float = 0.3       # env: OVD_LLM_TEMPERATURE_GENERATION
```

En `model_router.py`:
- `max_tokens` → `get_settings().ovd_llm_max_tokens` en todos los providers (claude, openai, custom, ollama, fallback)
- `_resolve_temperature()` → usa `ovd_llm_temperature_structured` / `ovd_llm_temperature_generation`
- `security_exec` agregado a `_ROLE_MODEL_OVERRIDES` con `ovd_model_security`

En `.do/app.yaml` (producción):
- `OVD_LLM_MAX_TOKENS=16384` (sube de 8192 a 16384 para DeepSeek V4 Pro y Qwen3 Coder Flash)

---

#### Trabajo pendiente en S115

**A. Parámetros Ollama aún hardcodeados**

| Parámetro | Valor | Env var propuesta |
|---|---|---|
| `num_ctx` | `32768` | `OVD_LLM_NUM_CTX` (default: 32768) |
| `seed` | `42` | `OVD_LLM_SEED` (default: 42, 0 = desactivar) |
| `reasoning` | `False` | `OVD_LLM_REASONING_ENABLED` (default: False) |

**B. Temperature por rol (granularidad fina)**

Actualmente hay dos grupos: structured y generation. Para mayor control:

```bash
OVD_LLM_TEMPERATURE_ANALYZER=0.0
OVD_LLM_TEMPERATURE_SDD=0.0
OVD_LLM_TEMPERATURE_QA=0.0
OVD_LLM_TEMPERATURE_BACKEND=0.3
```

Requiere refactor de `_resolve_temperature()` para lookup por rol antes de caer al grupo.

**C. Parámetros por provider**

- `extra_body={"think": False}` en Ollama fallback — debería ser `OVD_LLM_DISABLE_THINKING=true`
- `num_predict` (Ollama) vs `max_tokens` (OpenAI) — actualmente ambos usan `ovd_llm_max_tokens`

**D. Interfaz en dashboard (S114 + S115 integrados)**

La tab "Configuración" de S114 puede extenderse con una sección "Parámetros avanzados":

```
┌─────────────────────────────────────────────────────┐
│  Parámetros avanzados                               │
│  ─────────────────────────────────────────────────  │
│  Max tokens              [16384          ]          │
│  Temperature structured  [0.0            ]          │
│  Temperature generation  [0.3            ]          │
│  Context window (Ollama) [32768          ]          │
└─────────────────────────────────────────────────────┘
```

Aplicados vía `PUT /api/v1/config/llm-params` → `_RUNTIME_OVERRIDES` (S114 Fase 1 en memoria).

---

#### Estimación de trabajo

| Tarea | Esfuerzo |
|---|---|
| A. Parámetros Ollama en settings.py | 0.5h |
| B. Temperature por rol (settings + router) | 2h |
| C. extra_body think configurable | 0.5h |
| D. Endpoint + UI params avanzados (integración S114) | 2h |
| Tests (unit + integración) | 1h |
| **Total** | **~6h** |

---
