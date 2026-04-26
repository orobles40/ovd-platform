# OVD Platform — Roadmap Completo
**Última actualización:** 2026-04-26
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
| 11 | **S57** — QA score reducer + collection errors fix | QA reporta último score, no el mejor; tests fallan en retry por collection error | Bajo (~2h) |
| 12 | **S58** — Stack transversality | Fixes S40–S56 con sesgo Python/pytest no aplican correctamente a TypeScript/Rust | Medio (~1 día) |
| 13 | **S44** — MCP Server Manager | context7 hardcodeado; no se pueden agregar otros servidores MCP desde UI | Medio (~1 día) |

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

## S58 — Stack Transversality (pendiente)

**Motivación:** Auditoría 2026-04-26 reveló que el 40% de los fixes implementados en S40–S56 tienen sesgo Python/pytest. Se validaron siempre con el mismo FR de IMC en Python — nunca se probó TypeScript ni Rust. Los bugs de sesgo son silenciosos hasta que se usa otro stack.

**Hallazgos de auditoría:**

| Tag | Problema | Riesgo en otros stacks |
|-----|---------|----------------------|
| **S51-A** | Instrucción hardcodea `tests/test_<paquete>.py` | Si tarea es Vitest, LLM recibe instrucción Python incorrecta |
| **S55-C** | Instrucción `round()` — sintaxis Python pura | TypeScript: `toFixed(2)`, Rust: `.round()` |
| **S27-A** | `conftest.py` injection | Solo existe en pytest — no aplica a Vitest ni Cargo |
| **S31-C** | Filtra por `test_*.py` hardcoded | Vitest usa `*.test.ts`, Rust usa `*.rs` |
| **S32-C** | Diagnóstico basado en exit codes pytest | Vitest y Cargo tienen códigos distintos |

**Plan de S58:**

| Item | Descripción | Archivo(s) | Estado |
|------|-------------|-----------|--------|
| S58-A | S51-A condicional por `stack_language`: Python→pytest hint, TypeScript→Vitest hint, Rust→cargo test hint | `graph.py` | ⬜ |
| S58-B | S55-C condicional por stack: Python→`round()`, TypeScript→`toFixed(2)`, Rust→`.round()` | `graph.py` | ⬜ |
| S58-C | S27-A condicional: solo inyectar `conftest.py` si runner=pytest; para Vitest inyectar `vitest.config.ts` si falta | `graph.py` | ⬜ |
| S58-D | S31-C patrón por runner: `test_*.py` para pytest, `*.test.ts` para Vitest, `*.rs` para Cargo | `graph.py` | ⬜ |
| S58-E | S32-C tabla de exit codes por runner — pytest/Vitest/Cargo | `graph.py` | ⬜ |
| S58-F | Ciclo de validación TypeScript: FR con React + Vitest | Ciclo end-to-end | ⬜ |
| S58-G | Ciclo de validación Rust: FR con función + `#[cfg(test)]` | Ciclo end-to-end | ⬜ |

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
