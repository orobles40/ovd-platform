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
| C1 | NATS en producción: verificar si `task_checkout.py` funciona con `USE_NATS=false` o agregar servicio en `docker-compose.prod.yml` | ⬜ Pendiente |
| C2 | Alembic: auditar migraciones hasta S109 — verificar columnas nuevas tienen su migración | ⬜ Pendiente |
| C3 | `infra/postgres/grant-readonly.sql` — verificar existencia o crear el archivo | ⬜ Pendiente |
| C4 | `OVD_SECRET` vs `OVD_ENGINE_SECRET` — corregir naming inconsistente entrypoint/código | ⬜ Pendiente |
| C5 | `seed_prod.sql` — reemplazar datos HHMM por proyecto demo neutro (Sistema de Turnos) | ⬜ Pendiente |
| C6 | Dominio `ovd.omarrobles.dev` — registrar en DO y apuntar a App Platform | ⬜ Pendiente |

### Gaps ALTOS (antes del go-live)

| ID | Tarea | Estado |
|----|-------|--------|
| A1 | ADR-004: corregir contradicción — Option D (Claude API) es producción, no Option A | ⬜ Pendiente |
| A2 | ADR-005: crear — decisión DigitalOcean vs AWS/GCP/Fly.io | ⬜ Pendiente |
| A3 | Password admin: cambiar `ovd-dev-2026` antes de exponer URL pública | ⬜ Pendiente |
| A4 | RAG producción: confirmar BGE-M3 vía DO GenAI Platform reemplaza Ollama correctamente | ⬜ Pendiente |

### Deploy

| ID | Tarea | Estado |
|----|-------|--------|
| D1 | Crear App Platform en DO (2 vCPU / 4 GiB / $50/mes) conectado al repo GitHub | ⬜ Pendiente |
| D2 | Crear Managed PostgreSQL 16 ($30/mes) con extensión pgvector habilitada | ⬜ Pendiente |
| D3 | Configurar variables de entorno de producción en App Platform | ⬜ Pendiente |
| D4 | Primer deploy — verificar health check `GET /health` desde URL pública | ⬜ Pendiente |
| D5 | Bootstrap RAG producción con BGE-M3 (Sistema de Turnos como proyecto demo) | ⬜ Pendiente |

---

## Métricas objetivo S112

- Engine respondiendo en `https://ovd.omarrobles.dev/health`
- Ciclo greenfield completo desde dashboard web en producción
- QA ≥ 85 en ciclo de demo (mismo nivel que S109)
- Costo por ciclo documentado (basado en tokens Claude Sonnet 4.6)

---

## Backlog no urgente (post-demo)

| Item | Descripción | Prioridad |
|------|-------------|-----------|
| test_s63b | RuntimeError por S94-fix | Alta |
| S96-I | Indexar artefactos generados post-ciclo en RAG | Media |
| Modo 5 | Bug fixing en código existente (read_existing_codebase) | Media |
| test_s31 | Timing flaky | Baja |
| Sprint 46 | Design Quality System — UI profesional en código generado | Post-demo |
| Sprint 44 | MCP Server Manager | Post-demo |

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
