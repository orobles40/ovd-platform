# OVD Platform — Contexto dinámico del proyecto

> Este archivo contiene el estado vivo del proyecto.
> Se actualiza automáticamente con `/session-close` al final de cada sesión.
> Para las reglas permanentes del proyecto, ver `CLAUDE.md`.

---

## Estado actual

- **Sprint activo:** S103 (completado) / S104 (planificación)
- **Rama de trabajo:** `dev`
- **Sprints completados:** S3 → S102
- **Tests:** 1675 pass (unit) | 14 integration | 5 docker | 34 frontend (Vitest) | 26 Rust inline  
  *(5 pre-existentes siguen fallando: test_s31, test_s39, test_s47, test_s55, test_s63b)*
- **Cobertura baseline:** 88% TOTAL (2026-04-28)

---

## Última sesión (2026-04-30 — S103)

**Completado:**
- S103-P1: `_build_type_contract(sdd)` — tabla normalizada de nombres inyectada en cada agente
- S103-P2: `_check_undefined_import_names()` — pre-flight validator en run_tests
- S103-P3: eliminación de "frontend" del keyword list en `_fix_sdd_agent_assignments()`
- S103-P4: propagación rename S101-A — 2 patterns adicionales (`import src.X.service` y `src.X.service.`)
- S103-P5: template S91-A corregido — `services` plural + imports directos sin try/except
- test_s103.py: 53/53 PASS (7 clases)
- INFORME_PRUEBA_S103.md generado (mis-entregas/contratos-beneficios/)

**Ciclo validación S103** (d2d92f15 — tmpdir, BD no registrado: org_id="test" sin FK):
- QA: **90/100 ✅** (0 retries), Security: 100/100, **10m 4s** (−67% vs S102)
- Tokens: 108,071 entrada / 25,858 salida (−68% vs S102)
- **Delta histórico: QA 60→90 (+30 pts), primer PASS en ciclo fullstack Oracle sin retries**
- P1 efectivo: 0 run_tests failures en ronda 0 — list_contracts coherente entre agents
- P3 parcial: postprocessor corregido pero architect LLM asignó docker-compose a frontend (GAP)
- Pendiente: ciclo con org_id real para código inspeccionable

---

## Próxima sesión

**Primera tarea S104 (prioridades):**
1. **P1** — Restricción SDD docker-compose/Dockerfile: agregar en `system_sdd.md` que infra de contenedores SIEMPRE va a devops (ALTO)
2. **P2** — Manejo org_id inválido: rechazar sesión con 400 o usar org default si org_id no existe en ovd_orgs (ALTO)
3. **P3** — Ciclo validación con org_id real: para tener registro en BD y código inspeccionable
4. **P4** — Fix 5 tests pre-existentes (S96-G): test_s31, test_s39, test_s47, test_s55, test_s63b

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
