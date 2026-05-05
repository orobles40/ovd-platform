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
| C1 | NATS en producción: desplegar `nats:2-alpine` como servicio adicional en DO App Platform (mismo App que el engine, hostname interno). NATS es parte del proyecto y debe estar presente. Verificar configuración `NATS_URL` en variables de entorno. | ⬜ Pendiente |
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

## Backlog post-demo (orden de prioridad sugerido)

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
