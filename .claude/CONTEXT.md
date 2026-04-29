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

## Última sesión (2026-04-29 — sesión 4)

**Completado:**
- S97-A: `qa_score_history` + early stopping por estancamiento (delta < 5)
- S97-B: file ownership — devops no escribe .py ni tests/
- S97-C: feedback prescriptivo `[ISSUE-N]` + instrucciones 5 pasos
- S97-D: FR explícita BD > perfil proyecto (PostgreSQL override Oracle)
- S97-E: `temperature_override=0.1` en retry QA
- S97-F (hallazgo crítico): `think=False` → `reasoning=False` en ChatOllama
- ADR-002: addendum S97-F (think=False ignorado silenciosamente desde S22)
- ADR-004: nuevo — 4 opciones paralelismo real (filtrado, modelos mixtos, multi-instancia, Claude API)
- INFORME_PRUEBA_S97.md: telemetría ciclos f02d1e03 (70 min) y 4793c5e1 (124 min)
- 35/35 tests S97 PASS | 0 regresiones

**Resultado de validación S97 (Ollama):**
- Ninguno de los 2 ciclos completó — cuello de botella Ollama serializado
- Ciclo 1 (f02d1e03): bloqueado en qa_review 68 min (thinking mode ON — S97-F)
- Ciclo 2 (4793c5e1): bloqueado en fan-out 8 agentes × ~7 min = ~56 min (Ollama serial)
- S97-F es el hallazgo más importante: think=False ignorado desde S22, impacto 10×-15× por nodo

---

## Próxima sesión

**Primera tarea:** S98 — Telemetría por nodo + validación S97 con Claude API
- Opción rápida: `OVD_MODEL=claude-sonnet-4-5` para validar 5 fixes S97 (~$0.20, ~15 min)
- S98-A: logging duración + tokens por nodo en graph.py (prerequisito para ADR-004)
- S98-B: Opción A ADR-004 — filtrar agentes a 3-4 para FR tipo "API REST + PostgreSQL"
- S47: Background task + event queue (SSE log no actualiza — GAP-S47-A pendiente)

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
