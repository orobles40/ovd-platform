# Sprint activo — S112 (Despliegue DigitalOcean)

> Última actualización: 2026-05-05 | Rama: `dev`
> Skills Fase 1 activos: session-start, session-close, run-tests, pre-push

---

## Objetivo del sprint

Resolver todos los gaps críticos y altos que bloquean el despliegue en DigitalOcean App Platform,
y tener la URL pública `ovd.omarrobles.dev` operativa antes de la demo del 2026-05-18.

**Arquitectura de producción decidida:** Opción A — App Platform + Managed PostgreSQL + GenAI Platform.
Cambios de código mínimos: solo variables de entorno (`OVD_RAG_EMBEDDING_PROVIDER`, `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY` apuntando al endpoint DO GenAI).

---

## Deadline: Demo 2026-05-18

| Sprint | Contenido | Fecha |
|--------|-----------|-------|
| **S112** | Gaps DO críticos + despliegue App Platform + dominio | 11–16 mayo |
| **S113** | Dry run, seed demo neutro, guion presentación | 17 mayo |
| **Demo** | Presentación al cliente | 18 mayo |

**Scope demo en vivo:** modo greenfield (Sistema de Turnos) desde URL pública.
**Fuera del demo:** Modo 5 (bug fixing), Modo 2 Incremental, Modo 3 Migración.

---

## Tareas S112

### Gaps CRÍTICOS (bloquean el deploy)

| ID | Tarea | Estado |
|----|-------|--------|
| C1 | NATS en producción: `nats:2.10-alpine` en `docker-compose.prod.yml` ✅. En `.do/app.yaml` debe declararse como **`service`** (no `worker`) — los workers en DO App Platform no tienen hostname interno ni pueden recibir conexiones TCP. Usar `http_port: 8222` (monitoring, para health check) + `internal_ports: [4222]` (client port, solo interno) + sin `routes` (no expuesto al exterior). El engine conecta igual vía `nats://ovd-nats:4222`. Costo sin cambio (`basic-xxs`). | ⬜ Pendiente |
| C2 | Crear migración Alembic `0004_ovd_cycles_status.py`: columna `status TEXT NOT NULL DEFAULT 'started'` + índice único `idx_ovd_cycles_thread_id` en `ovd_cycles`. Ambos existen en dev (agregados manualmente en S47-B) pero no tienen migración formal. Sin esto la BD de prod arranca sin `status` y el engine falla al guardar ciclos. | ⬜ Pendiente |
| C3 | Crear `src/engine/migrations/grant-readonly.sql` (dentro del build context del Dockerfile): `GRANT SELECT ON ALL TABLES/SEQUENCES IN SCHEMA public TO ovd_readonly` + `ALTER DEFAULT PRIVILEGES`. Agregar llamada en `docker-entrypoint.sh` después de `alembic upgrade head` apuntando a `/app/migrations/grant-readonly.sql`. Nota: `infra/postgres/` queda fuera del build context (`src/engine/`) — por eso el archivo va en `migrations/`. El rol `ovd_readonly` existe pero sin permisos de lectura el MCP PostgreSQL no puede consultar datos en producción. | ⬜ Pendiente |
| C4 | `OVD_ENGINE_SECRET` — naming verificado consistente en entrypoint, settings.py y docker-compose.prod.yml. No requiere cambios. | ✅ Resuelto |
| C5 | Reescribir `seed_prod.sql` con datos demo neutros: org "OVD Demo", usuario `admin@codigonet.cloud` (hash generado dinámicamente desde env var `OVD_ADMIN_PASSWORD` en el entrypoint), proyecto "Sistema de Turnos Médicos" (FastAPI + React + PostgreSQL, directorio `/srv/projects/turnos-demo`). Agregar `OVD_ADMIN_PASSWORD` como secret en `.do/app.yaml` y documentar en `docs/DEPLOY.md`. | ⬜ Pendiente |
| C6 | Dominio `ovd-platform.codigonet.cloud` (registrado en AWS Route 53). Al crear el App en DO obtener URL `*.ondigitalocean.app` → crear CNAME en Route 53 apuntando a esa URL → DO emite TLS automáticamente. Actualizar `.do/app.yaml` y `OVD_CORS_ORIGINS` con el dominio correcto `codigonet.cloud`. | ⬜ Pendiente |
| C8 | `JWT_SECRET` falta en `.do/app.yaml`: está declarado en `settings.py` como requerido en producción (`jwt_secret: str = ""`) pero no aparece en la sección `envs` del engine. Sin esta variable el endpoint `POST /auth/login` retorna 500 y el dashboard queda inutilizable. Agregar como `type: SECRET` en `app.yaml` y configurar en el panel DO antes del primer deploy. | ⬜ Pendiente |
| C9 | `pg_trgm` falta en migración Alembic: la extensión existe en `infra/postgres/init_prod.sql` pero ese archivo no se ejecuta en DO Managed PostgreSQL (no hay `docker-entrypoint-initdb.d`). Si alguna consulta usa trigram similarity fallará silenciosamente en producción. Agregar `op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')` a la migración `20260101_0000_initial_schema.py` junto a las extensiones `vector` y `uuid-ossp` ya presentes. | ⬜ Pendiente |
| C10 | **Engine no accesible públicamente** — `ovd-engine` en `app.yaml` tiene `http_port: 8001` pero **sin `routes` definido**: el dashboard captura todo el tráfico en `/` y el engine solo existe en la red interna. El browser no puede alcanzar `/auth/login`, `/session`, etc. Fix: agregar sección `routes` al engine con los prefijos API: `/health`, `/auth`, `/session`, `/orgs`, `/projects`, `/config`, `/admin`. DO evalúa rutas de más a menos específica — el engine responde a sus prefijos, el dashboard captura el resto (`/`). Sin cambios en el código del engine. | ⬜ Pendiente |
| C7 | **Provider configurable para roles de análisis** (`analyzer`, `sdd`, `qa`): hoy estos roles tienen `_DEFAULT_PROVIDER` hardcodeado a `"ollama"` en `model_router.py` — ignoran `OVD_AGENT_PROVIDER`. En DO no hay Ollama → el ciclo falla en `analyze_fr`. Fix: agregar `ovd_analysis_provider: str = ""` en `settings.py` + `_ANALYSIS_PROVIDER = ovd_analysis_provider or ovd_agent_provider or "ollama"` en `model_router.py`. Dev local: sin cambios (vacío → Ollama). Producción: setear `OVD_AGENT_PROVIDER=openai` (o `claude`) en `app.yaml` → todos los roles usan DO GenAI Platform. Permite además elegir modelo por rol vía `OVD_MODEL_ANALYZER`, `OVD_MODEL_SDD`, `OVD_MODEL_QA` en env vars. | ⬜ Pendiente |

### Gaps ALTOS (antes del go-live)

| ID | Tarea | Estado |
|----|-------|--------|
| A1 | ADR-004: corregir contradicción — Option D (Claude API) es producción, no Option A | ⬜ Pendiente |
| A2 | ADR-005: crear — decisión DigitalOcean vs AWS/GCP/Fly.io | ⬜ Pendiente |
| A3 | Password admin: cubierta por C5 — `OVD_ADMIN_PASSWORD` se define como secret en DO antes del primer deploy. No hay password hardcodeada en git. | ✅ Resuelto por C5 |
| A4 | RAG producción: BGE-M3 disponible en DO GenAI ($0.02/1M tokens). Sin cambios de código — `OpenAIEmbeddings` lee `OPENAI_BASE_URL` del entorno automáticamente. Solo actualizar en `app.yaml`: `OPENAI_BASE_URL=https://inference.do-ai.run/v1` (hoy apunta a `api.openai.com`). No hay problema de compatibilidad vectorial porque la BD de prod es nueva y pgvector crea la colección con la dimensión de BGE-M3 desde el inicio. | ⬜ Pendiente |

### Deploy

| ID | Tarea | Estado |
|----|-------|--------|
| D1 | Crear App Platform: `doctl apps create --spec .do/app.yaml`. Prerequisito: repo GitHub `orobles40/ovd-platform` conectado a la cuenta DO (panel DO → Apps → GitHub). La BD Managed PostgreSQL se provisiona automáticamente desde la sección `databases:` del spec. pgvector y uuid-ossp se activan via Alembic migration 0000. | ⬜ Pendiente |
| D2 | Se crea automáticamente como parte de D1. **Cambiar `production: false` en la sección `databases:` del `app.yaml`** — `production: true` provisiona cluster HA con réplica standby ($50/mes innecesario para demo). Con `false` queda single-node ($15/mes, ahorro $35/mes). Upgrade a producción real desde el panel DO sin downtime cuando haya clientes. Post-creación: crear rol `ovd_readonly` manualmente con psql si se necesita MCP PostgreSQL (no crítico para demo). | ⬜ Pendiente |
| D3 | Configurar secrets en panel DO (App → Settings → Environment Variables) antes del primer deploy: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OVD_ENGINE_SECRET`, `OVD_ADMIN_PASSWORD`, `JWT_SECRET` (cubierto por C8). Variables no-secretas ya están en `app.yaml`. | ⬜ Pendiente |
| D4 | Orden: D1 → D3 → C6 (CNAME Route 53) → deploy automático. Verificar: `curl https://ovd-platform.codigonet.cloud/health`. Esperar mínimo 2 min (Alembic corre en startup, `initial_delay_seconds: 60` en health check). | ⬜ Pendiente |
| D5 | Bootstrap RAG producción: ejecutar `rag_bootstrap.py` localmente contra la prod DB (DO Managed PostgreSQL permite conexiones externas agregando la IP local a fuentes confiables en el panel DO). Comando: `DATABASE_URL=<prod_url> OPENAI_API_KEY=<dop_token> OPENAI_BASE_URL=https://inference.do-ai.run/v1 OVD_RAG_EMBEDDING_PROVIDER=openai OVD_EMBED_MODEL=bge-m3 python scripts/rag_bootstrap.py --org-id ORG_OVD_DEMO --project-id ovd-platform --clear`. El `--clear` limpia vectores residuales del setup inicial. Indexar: `src/engine/` (codebase) + `docs/` (docs). | ⬜ Pendiente |

---

## Métricas objetivo S112

- Engine respondiendo en `https://ovd-platform.codigonet.cloud/health`
- Ciclo greenfield completo desde dashboard web en producción
- QA ≥ 85 en ciclo de demo (mismo nivel que S109)
- Costo por ciclo documentado (basado en tokens Claude Sonnet 4.6)

---

## Backlog post-demo (orden de prioridad sugerido)

### Infraestructura — Pay-per-use

DO App Platform (S112) es siempre-activo (~$70/mes fijo). Para operar en modo pay-per-use real post-demo, evaluar migración a **Fly.io**:
- Scale-to-zero nativo: el engine duerme sin tráfico, despierta automáticamente en ~10s ante la primera petición
- PostgreSQL en Fly Postgres o Neon (serverless) — $5–10/mes fijo
- Costo estimado: $0 cuando inactivo, ~$0.02/hora cuando activo — vs $70/mes fijo en DO
- Requiere `fly.toml` en lugar de `app.yaml`; código del engine sin cambios
- Relevante cuando OVD tenga clientes reales y el uso sea esporádico entre demos

### Deuda técnica inmediata

| Item | Descripción | Prioridad |
|------|-------------|-----------|
| test_s63b | RuntimeError por S94-fix — suite no 100% limpia | Alta |
| test_s31 | Timing flaky | Baja |

### ÉPICA-1 — Modos de operación (diseño completo, cero código)

> Referencia: `docs/ROADMAP.md` línea ~3324

OVD opera hoy solo en modo **Greenfield**. Los modos restantes están diseñados pero no implementados:

| Modo | Descripción | Trabajo técnico principal |
|------|-------------|--------------------------|
| **Modo 2 — Incremental** | Proyecto con código existente → OVD agrega solo lo nuevo, sin tocar lo que funciona | Nodo `read_existing_codebase` + `write_artifacts` selectivo (no sobreescribir) |
| **Modo 3 — Migración tecnológica** | WL12→WL14, Struts→SpringBoot, Oracle 12c→19c — el código existente es el input de transformación | Agentes especializados por par de stacks + variantes "origen/destino" en templates |
| **Modo 4 — Reutilización** | Ciclo con QA ≥ 90 como plantilla base para un sistema nuevo similar | Detección de similitud + copia de artefactos validados |
| **Modo 5 — Bug fixing** | Corrección puntual en código existente sin regenerar el proyecto | `read_existing_codebase` + instrucción "solo corregir X, no tocar el resto" |

Casos de uso reales ya identificados (en ROADMAP): HHMM nuevo módulo de liquidaciones (Incremental),
HHMM migración WL12→WL14 (Migración), Oracle 12c→19c PL/SQL (Migración), Sistema licitaciones
basado en ciclo S103 QA=90 (Reutilización).

**Fases de implementación:** A (config proyecto + UI) → B (selector modo en FR) →
C (`read_existing_codebase`) → D (agentes migración) → E (`write_artifacts` selectivo)

### Calidad del engine

| Item | Descripción | Prioridad |
|------|-------------|-----------|
| Sprint 41 — RAG Learning | Indexación automática de errores QA/tests/security por ciclo + inyección como lecciones en agentes del mismo proyecto. Base para M4. | Alta post-demo |
| S96-I | Indexar código generado por agentes post-ciclo en RAG (doc_type=codebase) | Media |
| Sprint 47 — Sequential dispatch | Frontend espera a que server-side (backend+database+devops) termine — ya implementado en graph.py (`_SERVER_SIDE_AGENTS`, `pending_agents`) | ✅ Implementado |
| Sprint 46 — Design Quality System | UI profesional en código generado: shadcn/ui, Tailwind, estados de formulario, responsive | Post-demo |
| Sprint 44 — MCP Server Manager | Admin dinámico de servidores MCP desde dashboard (context7 hardcodeado hoy) | Post-demo |

### FASE M — Modelo propio (fine-tuning, transversal)

> Referencia: `docs/ROADMAP.md` línea ~2710 | `docs/MODEL_STRATEGY.md`

Infraestructura implementada. Pendiente ejecutar los hitos:

| Hito | Descripción | Prerequisito |
|------|-------------|-------------|
| M1.5 | Enriquecer dataset — exportar ciclos S36-S42 (QA ≥ 80) y hacer merge | — |
| M2.arch | Validar `ovd-arch-assistant` (GGUF ya generado, pendiente benchmark) | M1.5 |
| M2.analyzer | Fine-tuning `deepseek-r1:14b` → `ovd-analyzer` para `analyze_fr` | M1.5 |
| M3 | Benchmark: modelos fine-tuneados superan base en rol específico | M2.arch + M2.analyzer |
| M4 | Fine-tuning `qwen3-coder:30b` para agentes de implementación | Sprint 41 maduro + M3 |

### FASE F — Flutter (cliente unificado, largo plazo)

Reemplaza TUI Rust + Dashboard React por una sola app Flutter (web + macOS + Linux + Windows).
**Bloqueado** hasta que VPS (S112) esté operativo. 0% implementado.

### Decisiones pendientes (sin sprint asignado)

| Decisión | Contexto |
|----------|---------|
| `S11.E` — @research en TUI | Exponer desde TUI Rust o como endpoint FastAPI dedicado |
| `5.F` — Distribución TUI | Bloqueado hasta servidor centralizado operativo |
| `FASE F` — Iniciar | Después de VPS operativo (S112) |

---

## Fallos pre-existentes (no investigar salvo /fix-test)

| Test | Causa | Prioridad |
|------|-------|-----------|
| `test_s31::test_cycle_start_ts_reciente` | Flaky por timing | Baja |
| `test_s63::test_s63b_cleanup_not_in_run_tests` | RuntimeError por S94-fix | Alta |

---

## Referencias

- `docs/ROADMAP.md` → ÉPICA-2 DigitalOcean (línea ~3603)
- `docs/CLOUD_ALTERNATIVES.md` → análisis completo de opciones
- `docs/adr/ADR-003-model-selection-criteria.md` — criterios modelos LLM
- `CONTEXT.md` → estado dinámico del proyecto
