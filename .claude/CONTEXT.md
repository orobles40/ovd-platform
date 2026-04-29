# OVD Platform — Contexto dinámico del proyecto

> Este archivo contiene el estado vivo del proyecto.
> Se actualiza automáticamente con `/session-close` al final de cada sesión.
> Para las reglas permanentes del proyecto, ver `CLAUDE.md`.

---

## Estado actual

- **Sprint activo:** S97 (implementado) / S98 (pendiente validación)
- **Rama de trabajo:** `dev`
- **Sprints completados:** S3 → S96
- **Tests:** 1577 pass (unit) | 14 integration | 5 docker | 34 frontend (Vitest) | 26 Rust inline  
  *(5 pre-existentes siguen fallando: test_s31, test_s39, test_s47, test_s55, test_s63b)*
- **Cobertura baseline:** 88% TOTAL (2026-04-28)

---

## Última sesión (2026-04-29 — S100)

**Completado:**
- S100-A: limpieza stubs residuales antes de ronda 0 (graph.py `run_tests`)
- S100-B: py_compile pre-check antes de ejecutar pytest (graph.py)
- S100-C: mandato python-jose, prohibición PyJWT (system_backend_python.md)
- S100-D: prohibición DATABASE_URL hardcodeada (system_backend_python.md)
- S100-E: tabla alineación ORM↔SQL obligatoria (system_sdd.md)
- S100-F: anti-patrones Oracle PL/SQL — CHECK primo→trigger, DV VARCHAR2(1), LENGTH BETWEEN 8 AND 9
- S100-G: implementación TypeScript validateRut (system_frontend_react.md)
- S100-H: patrón require_role() dependency (system_backend_python.md)
- S100-I: services.py plural en tabla canónica (replace_all)
- S100-J: QA check componentes frontend faltantes del SDD (graph.py)
- S100-L: FrLauncher.tsx restoreNodesFromState al reconectar SSE
- S100-M: guía inline validate_rut DV=K
- test_s100.py: 23/23 PASS
- INFORME_PRUEBA_S100.md generado

**Ciclo validación S100** (12c71de5):
- QA: 65/100 (+5 vs S99), Security: 100/100, 21m 1s
- Fixes absorbidos: validate_rut DV=K ✅, jose JWT ✅, NameError auth/router ✅
- No absorbidos: services.py plural, DATABASE_URL env
- Regresión detectada: SDD solo ejecutó agente backend (devops+db+frontend ignorados)
- Tests: 3 rondas fallidas (ImportError — service.py singular)

---

## Próxima sesión

**Primera tarea S101 (prioridades):**
1. Postprocesador: renombrar `service.py` → `services.py` + actualizar imports (CRÍTICO)
2. Validación distribución agentes en SDD — detectar FR con keywords frontend/db/devops (CRÍTICO)
3. Postprocesador DATABASE_URL hardcodeada → os.environ.get() (ALTA)
4. Fix oracle_involved=False en S56-C cuando FR menciona Oracle explícitamente (ALTA)
5. Ruff I001 fix en test_model_router.py y test_s98.py (BAJA)

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
| S94 | 5a17c6a2 | — | **9 items / 1 error** | — |
| S95 | 65ab6e7b | — | bloquea S65-A | — |
| S96 | 124f0b66 | **50** | import_err × 3 | 19m 42s |

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
