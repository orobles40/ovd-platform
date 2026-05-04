# OVD Platform — Contexto dinámico del proyecto

> Este archivo contiene el estado vivo del proyecto.
> Se actualiza automáticamente con `/session-close` al final de cada sesión.
> Para las reglas permanentes del proyecto, ver `CLAUDE.md`.

---

## Estado actual

- **Sprint activo:** S106 (completado) / Ciclo validación pendiente
- **Rama de trabajo:** `dev`
- **Sprints completados:** S3 → S106
- **Tests:** 1801 pass (unit) | 14 integration | 5 docker | 34 frontend (Vitest) | 26 Rust inline  
  *(5 pre-existentes siguen fallando: test_s31, test_s39, test_s47, test_s55, test_s63b)*
- **Cobertura baseline:** 88% TOTAL (2026-04-28)

---

## Última sesión (2026-05-04 — S106)

**Completado (S106-P1):**
- Auto-generación schemas Pydantic (Create/Update/Response) en `_build_type_contract()` desde clases ORM en models.py
- `_S106_CLASS_IN_DESC_RE` + `_S106_PASCAL_IN_DESC_RE` — detección de entidades ORM en task descriptions
- `system_sdd.md` — nueva sección "Schemas Pydantic — OBLIGATORIO en models.py (S106-P1)"

**Completado (S106-P2):**
- `system_sdd.md` — [S106-P2] prohíbe `validate_rut_format`, marca `validate_rut` como nombre canónico
- `_S106_P2_ALIASES` dict + auto-corrección en disco en `_check_undefined_import_names()`
- Cuando se detecta `validate_rut_format` importado y `validate_rut` existe → reescribe el archivo

**Completado (S106-P3):**
- `_ORACLE_INFRA_KEYWORDS` — filtra `xepdb1`, `:1521`, `oracle+cx_oracle`, `oracle-xe`, etc.
- `_strip_db_restrictions()` extendido — aplica filtro infra Oracle cuando `oracle_involved=False`

**Completado (S106-P4):**
- Guard en `_fix_sdd_agent_assignments()`: si `agent=devops` y no hay `output_file`, no aplica S102-B keywords
- Previene que docker-compose sin output_file sea reasignado a frontend por mencionar "dashboard"

**Completado (S106-P5):**
- `_calc_naming_mismatch_penalty(last_test_error) -> int` — -2 pts por mismatch S103-P2, máx 30
- Integrado en bloque S62-B de `qa_review` — ajusta score antes del early return

**Completado (S106-P6):**
- `_build_type_contract()` — escanea tareas de service.py/services.py y auto-añade `list_{entity}s(db: Session)`
- Strip de sufijos ORM/Model/DB para nombre de función

**Suite:** test_s106.py — 43/43 PASS (15 P1 + 5 P2A + 3 P2B + 5 P3 + 3 P4 + 6 P5 + 6 P6)
**Total:** **1801 passed** (0 regresiones)

**Ciclo validación S104** (078f18ca): QA **52/100 ❌** (2 retries), 27m 51s
**Ciclo validación S105** (69ba0b13): QA **40/100 ❌** (2 retries), 21m 49s

---

## Próxima sesión

**Primera tarea: Ciclo validación S106**
- Limpiar workspace `/Users/omarrobles/Workspace/mis-entregas/contratos-beneficios/` y lanzar ciclo fresco
- Target: QA ≥ 80, 0 naming mismatches, docker-compose → devops con PostgreSQL (no Oracle XE)
- Verificar que `validate_rut` (no `validate_rut_format`) se usa en todo el código generado
- Si QA < 70: analizar causa raíz y proponer S107

**Posibles S107 si QA sigue bajo:**
- S107-P1: Inyección del type contract más temprano (antes del SDD, no solo en execute_agents)
- S107-P2: Validación de schemas Pydantic en QA review (verificar que Create/Update/Response existen en models.py)
- S107-P3: RAG filter by embedding score para chunks Oracle (threshold más alto para infraestructura)

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
| S106 | — | pendiente | — | — |

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
