# OVD Platform — Contexto dinámico del proyecto

> Este archivo contiene el estado vivo del proyecto.
> Se actualiza automáticamente con `/session-close` al final de cada sesión.
> Para las reglas permanentes del proyecto, ver `CLAUDE.md`.

---

## Estado actual

- **Sprint activo:** S96
- **Rama de trabajo:** `dev`
- **Sprints completados:** S3 → S95
- **Tests:** 1542 pass (unit) | 14 integration | 5 docker | 34 frontend (Vitest) | 26 Rust inline  
  *(5 pre-existentes siguen fallando: test_s31, test_s39, test_s47, test_s55, test_s63b)*
- **Cobertura baseline:** 88% TOTAL (2026-04-28)

---

## Última sesión (2026-04-29 — sesión 3)

**Completado:**
- Fix 4 tests (test_s65a_phantom_import_detected, test_s66a × 3) — assertions movidas dentro del `with tempfile` block
- S96-A validado en ciclo real: auto-generó stub `src/contracts/schemas.py`, ciclo continuó sin abort
- Ciclo prueba S96 ejecutado: thread `124f0b66`, 19m 42s, QA 50/100, 21 archivos, 347k tokens
- INFORME_PRUEBA_S96.md generado con análisis completo + 5 gaps identificados
- S96-F validado: /auth/login funcional, dashboard web operativo

**Resultado del ciclo prueba S96:**
- Security: 100/100 (bypass S48-A), QA: 50/100 (3 rondas sin mejoría)
- GAP-S96-1: Conflicto perfil proyecto (Oracle) vs FR explícita (PostgreSQL) → QA penaliza
- GAP-S96-2: devops sobrescribió tests/test_contracts.py del backend
- GAP-S96-3: QA feedback no produce correcciones concretas en el agente
- GAP-S96-4: SSE log no actualiza tras reconexión (GAP-S47-A pendiente)
- GAP-S96-5: Frontend no asignado con FR que menciona validación frontend

---

## Próxima sesión

**Primera tarea:** S97 — Correcciones para QA > 80
- S97-A: FR explícita BD > perfil proyecto en analyze_fr
- S97-B: Protección write_artifacts entre agentes (no sobrescribir)
- S97-C: Feedback QA con snippets prescriptivos de corrección
- S97-D: Detección keyword "frontend" en FR → asignar agente frontend
- S47: Background task + event queue (SSE log no actualiza)

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
