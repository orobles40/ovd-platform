# OVD Platform — Contexto dinámico del proyecto

> Este archivo contiene el estado vivo del proyecto.
> Se actualiza automáticamente con `/session-close` al final de cada sesión.
> Para las reglas permanentes del proyecto, ver `CLAUDE.md`.

---

## Estado actual

- **Sprint activo:** S101 (completado) / S102 (planificación)
- **Rama de trabajo:** `dev`
- **Sprints completados:** S3 → S101
- **Tests:** 1651 pass (unit) | 14 integration | 5 docker | 34 frontend (Vitest) | 26 Rust inline  
  *(5 pre-existentes siguen fallando: test_s31, test_s39, test_s47, test_s55, test_s63b)*
- **Cobertura baseline:** 88% TOTAL (2026-04-28)

---

## Última sesión (2026-04-29 — S101)

**Completado:**
- S101-A: postprocesador rename `service.py` → `services.py` + actualizar imports (graph.py `run_tests`)
- S101-B: `_fix_sdd_agent_assignments()` — inferencia de agente por extension/path del output_file (graph.py)
- S101-C: `_fix_database_url_hardcoded()` — reemplaza DATABASE_URL literal por os.environ.get() (code_postprocessor.py)
- S101-D: `oracle_involved` forzado a True cuando FR menciona "oracle" (graph.py `analyze_fr`)
- S101-E: ruff I001 fix en test_model_router.py y test_s98.py
- test_s101.py: 30/30 PASS
- INFORME_PRUEBA_S101.md generado

**Ciclo validación S101** (1b359097):
- QA: **90/100** (primer PASS histórico — `qa_passed: true`), Security: 100/100, 10m 41s
- Tokens: 170K entrada / 20.7K salida (-35% vs S100)
- S101-D absorbido: oracle_involved=True automático
- S101-C no activó: engine sin reiniciar (usar código anterior al commit)
- S101-B no absorbido: SDD genera tasks sin `output_file` → inferencia imposible
- GAP-S101-1 (crítico): contracts/router.py importa service.py inexistente con try/except silencioso

---

## Próxima sesión

**Primera tarea S102 (prioridades):**
1. Fix try/except ImportError silencioso en routers — postprocesador S102-A (CRÍTICO)
2. SDD system prompt: `output_file` obligatorio en cada task — desbloquea S101-B (ALTO)
3. Reiniciar engine para activar S101-C (DATABASE_URL) antes del primer ciclo
4. Verificar que GAP-S101-2 (frontend no generado) se resuelve con output_file obligatorio

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
