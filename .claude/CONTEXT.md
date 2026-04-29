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
- **Cobertura baseline:** 88% TOTAL (2026-04-28)

---

## Última sesión (2026-04-28)

**Completado:**
- Fase 2 plan mantenibilidad: ruff + Makefile + CI configurados
- Fase 3-A: settings.py centralizado (Pydantic BaseSettings)
- Fase 3-C: exceptions.py con jerarquía OVD
- Migración de 8 módulos a get_settings() (model_router, rag, nightly_researcher, audit_logger, nats_client, task_checkout, routers/api_v1, routers/auth_router)
- Baseline pytest-cov establecido: 88% TOTAL
- Propuesta de skills Claude Code v1.0 documentada y aprobada
- Skills Fase 1 implementados: session-start, session-close, run-tests, pre-push
- CLAUDE.md dividido en CLAUDE.md (permanente) + CONTEXT.md (dinámico)

**Decisiones tomadas:**
- Separar CLAUDE.md en CLAUDE.md + CONTEXT.md → APROBADO
- Sesión dedicada a 5 fallos pre-existentes → APROBADO (planificada en S96-G)
- Fix /auth/login 500 → PRIORIDAD S96 (S96-F, antes de S96-D y S96-E)

---

## Próxima sesión

**Primera tarea sugerida:** S96-F — Fix POST /auth/login retorna 500
- Causa probable: error en `_get_user_by_email()` o en emisión de tokens
- Workaround actual: curl + OVD_SECRET
- Bloquea: dashboard web completo

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
| `POST /auth/login` → 500 | Bloquea dashboard web | PRIORITARIO | S96-F |
| `test_s63b_cleanup_in_retry_round_zero` | Suite no limpia | Pendiente | S96-D |

---

## Ciclos de referencia

| Sprint | Hash | QA | pytest | Duración |
|--------|------|----|--------|----------|
| S76 | c0e2e71e | **93** | collection_error | 13 min |
| S84 | e98bf96e | — | exit 2 | 5m 38s |
| S94 | 5a17c6a2 | — | **9 items / 1 error** | — |
| S95 | 65ab6e7b | — | bloquea S65-A | — |

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
