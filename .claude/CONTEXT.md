# OVD Platform — Contexto dinámico del proyecto

> Este archivo contiene el estado vivo del proyecto.
> Se actualiza automáticamente con `/session-close` al final de cada sesión.
> Para las reglas permanentes del proyecto, ver `CLAUDE.md`.

---

## Estado actual

- **Sprint activo:** S105 (completado) / S106 (planificación)
- **Rama de trabajo:** `dev`
- **Sprints completados:** S3 → S105
- **Tests:** 1754 pass (unit) | 14 integration | 5 docker | 34 frontend (Vitest) | 26 Rust inline  
  *(5 pre-existentes siguen fallando: test_s31, test_s39, test_s47, test_s55, test_s63b)*
- **Cobertura baseline:** 88% TOTAL (2026-04-28)

---

## Última sesión (2026-04-30 — S105)

**Completado (S104):**
- S104-A: `_STRUCTURED_ROLES` ampliado (backend/frontend/database/devops) + `seed=42` en ChatOllama
- S104-B: `_detect_circular_self_imports()` agregado a graph.py + llamada en run_tests
- S104-C: limpieza `__pycache__` recursiva en `session_create` de api.py
- S104-D: restricción absoluta en `system_sdd.md` — docker-compose/Dockerfile → siempre devops
- S104-E: `_classify_test_error()` + hints de taxonomía inyectados al output en run_tests
- test_s104.py: 30/30 PASS (6 clases, incluye TestS105P1) | test_model_router.py actualizado
- Suite completa: **1754 passed** (0 regresiones)

**Completado (S105):**
- S105-P1: limpieza `tests/test_*.py` del ciclo anterior en `session_create` de api.py
- test_s104.py: clase TestS105P1 (4 tests) integrada y pasando

**Ciclo validación S104** (078f18ca — workspace persistente):
- QA: **52/100 ❌** (2 retries), **27m 51s**, tokens: 301K / 64K

**Ciclo validación S105** (69ba0b13 — workspace persistente, BD registrado: ORG_OMAR_ROBLES):
- QA: **40/100 ❌** (2 retries), **21m 49s**, tokens: 183K entrada / 54K salida
- S105-P1 confirmado: 6 old tests eliminados antes del ciclo ✅
- Naming mismatches: 18 (ronda 0) → 15 (ronda 1) → 15 (ronda 2) — sin convergencia
- Contaminación RAG Oracle detectada: docker-compose.yml generado con Oracle XE en lugar de PostgreSQL ❌
- S104-D sigue fallando: TASK-011 (docker-compose) → frontend vía S102-B override ❌
- **Causa raíz QA=40:** models.py sin schemas Pydantic + validate_rut vs validate_rut_format + RAG Oracle

---

## Próxima sesión

**Primera tarea S106 (prioridades):**
1. **S106-P1 (CRÍTICO)** — Schemas Pydantic obligatorios en models.py — task SDD explícita para ContratoCreate/Response/etc.
2. **S106-P2 (CRÍTICO)** — Fix `validate_rut_format` → `validate_rut` en SDD template + auto-corrección en `_check_undefined_import_names()`
3. **S106-P3 (CRÍTICO)** — Filtro RAG por `db_engine` — excluir chunks Oracle al indexar y recuperar en proyectos PostgreSQL
4. **S106-P4 (ALTA)** — Fix S102-B postprocessor: guard `_INFRA_ARTIFACTS` para no reasignar docker-compose/Dockerfile
5. **S106-P5 (ALTA)** — QA penaliza naming_mismatch: `-2 pts por mismatch` si S103-P2 detecta nombres no definidos
6. **S106-P6 (MEDIA)** — Type contract incluye `list_{entity}s(db)` automáticamente para cada entidad del SDD
7. **Ciclo validación S106**: target QA ≥ 80, 0 naming mismatches, docker-compose → devops con PostgreSQL

---

## Fallos pre-existentes a corregir (S96-G)

> Sesión dedicada planificada. No investigar en sesiones de features.
> Usar `/fix-test` para abordarlos sistemáticamente.

| Test | Causa conocida | Prioridad |
|---|---|---|
| `test_s31::test_cycle_start_ts_reciente` | Flaky por timing — race condition | Media |
| `test_s39::test_usa_cap_800_en_truncate` | Cap obsoleto desde S61-B | Alta (fácil) |
| `test_s47::test_dispatch_frontend_despacha_pendientes` | Roto por S94-fix | Alta |
| `test_s55::test_write_artifacts_overwrites_when_new_content_larger` | write_artifacts cambió post-S55 | Alta |
| `test_s63::test_s63b_cleanup_not_in_run_tests` | RuntimeError por S94-fix | Alta |

---

## Issues abiertos

| Issue | Impacto | Estado | Sprint |
|---|---|---|---|
| `POST /auth/login` → 500 | Bloquea dashboard web | ✅ RESUELTO | S96-F |
| `test_s63b_cleanup_in_retry_round_zero` | Suite no limpia | Pendiente | S96-D |
| QA score ≤ 50 en ciclos con 2 agentes | Conflicto BD perfil/FR | Pendiente | S97-A |
| devops sobrescribe tests del backend | write_artifacts sin protección | Pendiente | S97-B |

---

## Ciclos de referencia

| Sprint | Hash | QA | pytest | Duración |
|--------|------|----|--------|----------|
| S76 | c0e2e71e | **93** | collection_error | 13 min |
| S84 | e98bf96e | — | exit 2 | 5m 38s |
| S99 | — | **60** | — | 18m |
| S100 | — | **65** | — | 21m |
| S101 | 1b359097 | **90** (PASS) | 3 passed | 10m 41s |
| S102 | 77a54e0c | **60** | exit 2 × 3 (3 retries) | 30m 35s |
| S103 | d2d92f15 | **90** (PASS) | 0 retries | 10m 4s |
| S104 | 078f18ca | **52** | P2: 2 retries | 27m 51s |
| S105 | 69ba0b13 | **40** | P2: 2 retries | 21m 49s |

---

## Skills activos (Fase 1 — desde 2026-04-28)

| Skill | Comando | Estado |
|---|---|---|
| `session-start` | `/session-start` | ✅ Activo |
| `session-close` | `/session-close "resumen"` | ✅ Activo |
| `run-tests` | `/run-tests [marker]` | ✅ Activo |
| `pre-push` | `/pre-push` | ✅ Activo |

**Fase 2 — Evaluar impacto en:** 2026-05-12 (2 semanas)
Skills candidatos Fase 2: `tdd-cycle`, `tdd-green`, `cycle-debug`, `fix-test`
