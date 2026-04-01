# Plan de Implementación — OVD Platform
## Basado en fork de OpenCode (Apache 2.0)

**Proyecto:** OVD-TUI — Oficina Virtual de Desarrollo
**Lider tecnico:** Omar — Arquitecto de Soluciones
**Organizacion:** Omar Robles
**Version:** 1.0 — Marzo 2026
**Referencia SDD:** SDD_OVD_TUI_v1.5.md

---

## Resumen ejecutivo

| Fase | Semanas | Objetivo | Estado |
|------|---------|----------|--------|
| Fase 0 — Fundacion | 1-4 | Fork funcional + multi-tenancy + MCP Oracle + agentes custom | Por iniciar |
| Fase 1 — Loop completo | 5-9 | Ciclo end-to-end FR → aprobacion → entregables via TUI | Por iniciar |
| Fase 2 — Escalar | 10-16 | Multi-proyecto + fine-tuning + telemetria | Por iniciar |
| Fase 3 — Cloud privado | 17-24 | K8s + SLA + segundo cliente | Por iniciar |
| Fase 4 — SaaS base | 25+ | Web UI + billing + self-service | Futuro |
| Fase 5 — TUI Rust propio | TBD | Cliente Rust standalone sin dependencias | Futuro condicional |

---

## Fase 0 — Fundacion (Semanas 1-4)

**Objetivo:** el equipo puede abrir el fork, seleccionar el proyecto Alemana, escribir un FR con el agente `oracle-dba` y ver como el agente consulta Oracle via MCP.

### Semana 1 — Setup y estructura base

| Dia | Tarea | Owner | Criterio de done |
|-----|-------|-------|-----------------|
| Lun | Fork `anomalyco/opencode` a repo privado Omar Robles | Arquitecto | Fork creado, rama `upstream/dev` configurada |
| Lun | Crear `CREDITS.md` y clause de disassociation en README | Arquitecto | Cumplimiento Apache 2.0 verificado |
| Mar | `bun install` + `bun run dev` del fork sin errores | Dev TS | TUI de OpenCode abre en terminal |
| Mar | Crear carpetas `src/tenant/`, `src/ovd/`, `src/finetune/` con `index.ts` placeholder | Dev TS | Estructura del repo segun SDD 5.2 |
| Mie | Actualizar `docker-compose.yml`: agregar servicios `ovd-engine`, `otel-collector`, `mcp-oracle` | DevOps | `docker compose up` levanta todos los servicios |
| Mie | PostgreSQL 16 + pgvector corriendo con migracion inicial | DevOps | `SELECT * FROM pg_extension` muestra vector |
| Jue | Documentar `.env.example` con todas las variables necesarias | Dev TS | Otro developer puede configurar el entorno en < 30 min |
| Jue | Configurar GitHub Actions: rama protegida `main`, PR obligatorio, CI basico | DevOps | Push directo a main bloqueado |
| Vie | Demo interna: fork corre, Docker Compose levanta, equipo tiene acceso | Todos | Todos los devs pueden arrancar el entorno local |

### Semana 2 — Multi-tenancy + Auth

| Dia | Tarea | Owner | Criterio de done |
|-----|-------|-------|-----------------|
| Lun-Mar | Schema Drizzle: tablas `organizations`, `projects`, `users` con RLS | Dev TS | Migracion ejecuta sin errores |
| Lun-Mar | JWT extendido: login con email/password retorna token con `org_id` y `role` | Dev TS | `POST /auth/login` retorna token valido |
| Mie | Middleware Hono: extrae `org_id` del JWT en cada request | Dev TS | Request sin token retorna 401 |
| Mie-Jue | Rutas Hono: `GET/POST /org`, `GET/POST/PUT/DELETE /project` | Dev TS | CRUD de org y proyecto funciona via curl |
| Jue | Test de aislamiento: queries de org A no retornan datos de org B | Dev TS | `bun test src/tenant/` pasa 100% |
| Vie | Script `create-org.py`: crea org + proyecto Alemana + usuario admin | Dev Python | Ejecutar el script crea la org correctamente |

### Semana 3 — MCP Oracle + Skills + Agentes custom

| Dia | Tarea | Owner | Criterio de done |
|-----|-------|-------|-----------------|
| Lun | `mcp_servers/base/server.py` y `auth.py` (clase base + Oracle Wallet) | Dev Python | Clase base MCP instanciable |
| Lun-Mar | `mcp_servers/oracle/`: tools `query_oracle`, `validate_sql_compat`, `get_table_schema`, `get_ibatis_mapping` | Dev Python + DBA | Cada tool retorna resultado correcto en prueba local |
| Mar | Pool de conexiones por sede: CAS → PSOL7, CAT/CAV → PSOL8 (conexiones a dev) | DBA | Cada sede conecta al pool correcto |
| Mie | `validate_sql_compat` rechaza features 19c para sede CAS | Dev Python | Test: JSON_OBJECT() para CAS → `{ valid: false }` |
| Mie | Dockerfile para `mcp-oracle` + health check | DevOps | `docker compose up mcp-oracle` levanta correctamente |
| Jue | Skills del proyecto Alemana: `consulta-oracle.md`, `fix-legacy.md`, `revision-seguridad.md`, `validar-nats.md`, `nuevo-endpoint.md` | Arquitecto | Cada skill invocable con `/nombre` en una sesion |
| Jue-Vie | `.opencode/opencode.jsonc`: agentes custom `oracle-dba`, `python-backend`, `legacy-java`, `integration` | Arquitecto | Los 4 agentes aparecen en el selector del TUI (Tab) |
| Vie | Demo: agente `oracle-dba` invoca `query_oracle` en CAS dev y retorna resultado | Todos | Demo en vivo exitosa |

### Semana 4 — OVD Bridge v1 + TUI basico

| Dia | Tarea | Owner | Criterio de done |
|-----|-------|-------|-----------------|
| Lun-Mar | `engine/api.py`: FastAPI HTTP wrapper del grafo LangGraph con endpoints `/session`, `/approve`, `/escalate` | Dev Python | `POST /session` arranca el grafo y retorna thread_id |
| Lun-Mar | `src/ovd/bridge.ts`: HTTP client hacia el OVD Engine | Dev TS | `bridge.startSession()` llama al engine y recibe eventos |
| Mie | `src/ovd/session.ts`: mapeo session OpenCode ↔ thread_id LangGraph | Dev TS | Una sesion de OpenCode persiste su thread_id |
| Mie-Jue | `src/ovd/events.ts`: transformacion eventos LangGraph → bus de OpenCode | Dev TS | Eventos del grafo aparecen en el TUI como mensajes del agente |
| Jue | `src/ovd/approval.ts`: interrupts `human_approval` y `handle_escalation` como eventos del bus | Dev TS | El TUI pausa cuando recibe evento de aprobacion |
| Vie | Demo Fase 0 completa: login → proyecto Alemana → FR → agente oracle-dba → MCP Oracle → respuesta | Todos | Demo en vivo end-to-end sin errores criticos |

**Entregable Fase 0:** binario del fork distribuible internamente. El equipo puede usar el producto para consultas Oracle y FRs simples.

**Costo infraestructura:** ~$30-50 USD/mes (PostgreSQL + Docker local)

---

## Fase 1 — Loop completo (Semanas 5-9)

**Objetivo:** el ciclo completo FR → specs SDD → aprobacion humana → agentes LangGraph → QA → Security → entregables funciona end-to-end via TUI.

### Semana 5 — OVD Runner completo

| Tarea | Owner | Criterio de done |
|-------|-------|-----------------|
| `engine/api.py` completo: SSE stream de eventos del grafo | Dev Python | `GET /session/{id}/stream` envia eventos en tiempo real |
| Interrupts LangGraph expuestos como estados HTTP en la DB | Dev Python | `pending_approval` y `escalated` persisten en PostgreSQL |
| `resume_session()` retoma el grafo desde checkpointer PostgreSQL | Dev Python | Sesion interrumpida se retoma correctamente tras reinicio |
| Test end-to-end con grafo LangGraph real (FR simple, no legacy) | Dev Python | FR completa ciclo completo sin intervencion humana |

### Semana 6 — SSE en el fork + pantallas TUI aprobacion

| Tarea | Owner | Criterio de done |
|-------|-------|-----------------|
| SSE consumer en `src/ovd/bridge.ts`: reconexion automatica con Last-Event-ID | Dev TS | Reconexion tras caida de red no pierde eventos |
| Pantalla TUI: progreso del grafo en panel de sesion activa (nombre nodo + estado) | Dev TS | Cada nodo LangGraph visible en tiempo real en el TUI |
| Modal de aprobacion: tabs requirements / design / constraints / tasks scrolleables | Dev TS | [A] aprueba, [R] rechaza con comentario, flujo continua |
| Modal de escalacion: campo de resolucion, envio desbloquea el grafo | Dev TS | Escalacion resuelta, agente continua sin perder estado |

### Semana 7 — Pantalla de entregables + RAG multi-proyecto

| Tarea | Owner | Criterio de done |
|-------|-------|-----------------|
| Pantalla TUI entregables: lista archivos NUEVO/MODIFICADO, diff coloreado, tabs Codigo/QA/Security | Dev TS | Diff verde/rojo visible, [S] guarda al filesystem |
| `engine/rag/store.py` extendido: namespace por `project_id` en pgvector | Dev Python | Seed en proyecto A no visible en queries proyecto B |
| Script `seed-project.py`: carga RAG de Alemana con datos reales | Dev Python | RAG de Alemana cargado y consultable |
| Rutas Hono para RAG: `POST /project/{id}/rag/seed`, `GET /project/{id}/rag/status` | Dev TS | Seed via API retorna job_id y status |

### Semana 8 — Historial de sesiones + MCP NATS

| Tarea | Owner | Criterio de done |
|-------|-------|-----------------|
| Panel izquierdo TUI: historial de sesiones del proyecto activo con status | Dev TS | Lista de sesiones visible, click abre la sesion |
| Retomar sesion interrumpida: el TUI recarga estado desde DB | Dev TS | Sesion en `pending_approval` muestra el modal al retomar |
| `mcp_servers/nats/`: tools `publish_event`, `subscribe_peek`, `get_queue_stats` | Dev Python | Agente `integration` publica evento en NATS dev |
| Config Hono: rate limiting por org (100 req/min por defecto) | Dev TS | 429 al superar el limite |

### Semana 9 — Estabilizacion + Demo Fase 1

| Tarea | Owner | Criterio de done |
|-------|-------|-----------------|
| Test de aislamiento multi-tenant completo en CI | Dev TS | GitHub Actions corre test de aislamiento en cada PR |
| Build del fork como binario standalone (`bun build --compile`) | DevOps | Binario corre en macOS y Linux sin instalar Bun |
| Pipeline CI/CD: tests en PR + build binario en tag + release en GitHub | DevOps | Tag v0.1.0 genera binarios para macOS arm64, x86_64, Linux x86_64 |
| Demo Fase 1: FR de Alemana (fix RUT medico legacy Java) end-to-end | Todos | Demo exitosa con aprobacion humana real y entregables |

**Entregable Fase 1:** ciclo completo funcionando. Binario v0.1.0 distribuido al equipo via GitHub Releases.

**Costo infraestructura:** ~$110-160 USD/mes (+ RunPod para jobs Java legacy)

---

## Fase 2 — Escalar (Semanas 10-16)

**Objetivo:** segundo proyecto onboarded, fine-tuning operativo, telemetria con datos reales.

### Semanas 10-11 — Fine-tuning: collector y curacion

| Tarea | Owner | Criterio de done |
|-------|-------|-----------------|
| `fine_tuning/collector.ts`: captura training samples post-sesion aprobada | Dev TS | Cada sesion completada genera samples en DB |
| `fine_tuning/detector.ts`: deteccion de datos sensibles (RUT, nombre paciente) | Dev TS | Sample con datos de paciente → `has_sensitive = true` |
| Pantalla TUI "Fine-tuning": lista samples pendientes, [A]/[R] con nota | Dev TS | Curador puede revisar y aprobar samples desde el TUI |
| Rutas Hono: `GET/PUT /training-sample`, `GET /training-sample/export` | Dev TS | Export JSONL de samples aprobados descargable |

### Semanas 12-13 — Fine-tuning: trainer y evaluator

| Tarea | Owner | Criterio de done |
|-------|-------|-----------------|
| `fine_tuning/trainer.py`: job con unsloth (GPU local M-series) | Dev Python | Job completo con dataset de prueba en CPU (modo test) |
| SSE del job: loss curve + logs en tiempo real en el TUI | Dev Python | TUI muestra progreso del entrenamiento |
| `fine_tuning/evaluator.py`: benchmark del proyecto Alemana | Arquitecto + Dev Python | `eval_score` calculado automaticamente al terminar job |
| `model_registry`: activar modelo, routing A/B configurable | Dev TS | Modelo activo usado por el agente en nuevas sesiones |

### Semanas 14-15 — Telemetria + segundo proyecto

| Tarea | Owner | Criterio de done |
|-------|-------|-----------------|
| `telemetry/instruments.ts`: spans OpenTelemetry en API Layer y OVD Bridge | Dev TS | Tokens, latencia y costo visibles en DB local |
| Dashboard TUI "Telemetria": tokens/dia, costo estimado, latencia por agente | Dev TS | Datos de al menos una semana de uso reales |
| Onboarding segundo proyecto (stack diferente a Alemana) | Arquitecto | Segundo proyecto corriendo sin interferir con Alemana |
| Seed del RAG del segundo proyecto | Dev Python | RAG del segundo proyecto cargado y aislado |

### Semana 16 — Estabilizacion + Demo Fase 2

| Tarea | Owner | Criterio de done |
|-------|-------|-----------------|
| Primer ciclo fine-tuning completo con datos reales de Alemana | Dev Python + ML | `eval_score` modelo FT > modelo base en benchmark Alemana |
| Demo: dos proyectos, telemetria activa, modelo FT en produccion | Todos | Demo exitosa con metricas reales |
| Binario v0.2.0 distribuido | DevOps | Release con changelog |

**Entregable Fase 2:** plataforma multi-proyecto funcional con fine-tuning y telemetria. v0.2.0.

**Costo infraestructura:** ~$160-240 USD/mes + ~$10-15 por job de fine-tuning

---

## Fase 3 — Cloud privado (Semanas 17-24)

**Objetivo:** servidor dedicado Omar Robles, accesible para el equipo via red privada, SLA 99.5%.

### Semanas 17-18 — Infraestructura K8s

| Tarea | Owner |
|-------|-------|
| Manifests K8s: namespace, deployments para API fork, OVD Engine, PostgreSQL StatefulSet | DevOps |
| Ingress + TLS para el servidor del fork | DevOps |
| Persistent volumes para PostgreSQL, Ollama y modelos fine-tuned | DevOps |
| Secrets management: Oracle Wallet, JWT secret, API keys via K8s Secrets | DevOps |
| Monitoreo: Prometheus + Grafana con el dashboard de telemetria | DevOps |

### Semanas 19-20 — Auth enterprise + admin TUI

| Tarea | Owner |
|-------|-------|
| Keycloak o auth propio: gestion de usuarios, roles, SSO opcional | Dev TS |
| Pantalla admin en TUI: crear orgs, proyectos, usuarios, asignar roles | Dev TS |
| Audit log inmutable de todas las acciones (retencion 90 dias) | Dev TS |

### Semanas 21-22 — Hardening + SLA

| Tarea | Owner |
|-------|-------|
| Tests de carga: 10 sesiones concurrentes sin degradacion | Dev TS + DevOps |
| Backup automatico de PostgreSQL (diario, retencion 30 dias) | DevOps |
| Runbook de operacion: restart, rollback, debug de sesiones colgadas | Arquitecto |
| SLA 99.5% verificado en staging por 2 semanas | DevOps |

### Semanas 23-24 — Lanzamiento cloud privado

| Tarea | Owner |
|-------|-------|
| Migration de datos de dev a produccion | Dev TS + DevOps |
| Capacitacion del equipo en el entorno cloud | Arquitecto |
| Binario v1.0.0: nombre comercial definitivo, sin referencias a "OpenCode" en la UI | Dev TS |
| Compliance check Apache 2.0 completo (checklist SDD 2.6) | Arquitecto |

**Entregable Fase 3:** v1.0.0 corriendo en cloud privado Omar Robles con SLA verificado.

**Costo infraestructura:** ~$240-310 USD/mes

---

## Dependencias criticas entre fases

```
FASE 0                          FASE 1                    FASE 2
Fork setup ─────────────┐
Multi-tenancy ──────────┤       OVD Runner ─────┐
MCP Oracle ─────────────┤       SSE + TUI ───────┤        Fine-tuning
Skills + agentes custom ┘       RAG multi-proyecto┘        Telemetria
                                                           2do proyecto
```

---

## Criterios de avance entre fases

| De → A | Criterio obligatorio antes de continuar |
|--------|----------------------------------------|
| Fase 0 → Fase 1 | Demo en vivo: agente oracle-dba consulta Oracle dev via MCP sin errores |
| Fase 1 → Fase 2 | Demo en vivo: FR Java legacy completa ciclo end-to-end con aprobacion real |
| Fase 2 → Fase 3 | Dos proyectos corriendo, telemetria con datos reales, fine-tuning validado |
| Fase 3 → Fase 4 | Cloud privado con SLA 99.5% verificado por 4 semanas |

---

## Riesgos con mayor probabilidad en Fase 0

| Riesgo | Mitigacion inmediata |
|--------|---------------------|
| Conexion Oracle dev no disponible en ambiente local | Usar mock de `query_oracle` hasta tener acceso confirmado. DBA debe confirmar credenciales en semana 1 |
| Conflictos al hacer merge del fork con upstream de OpenCode | No tocar archivos del core en Fase 0 — solo agregar carpetas nuevas |
| `bun build --compile` no genera binario correcto en Linux | Verificar en CI con runner Ubuntu desde la semana 1 |
| Tiempo de setup del equipo supera lo estimado | Tener `setup-dev.sh` funcionando el dia 1 de la semana 1 |
