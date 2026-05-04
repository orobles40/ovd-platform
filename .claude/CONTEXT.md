# OVD Platform — Contexto dinámico del proyecto

> Este archivo contiene el estado vivo del proyecto.
> Se actualiza automáticamente con `/session-close` al final de cada sesión.
> Para las reglas permanentes del proyecto, ver `CLAUDE.md`.

---

## Estado actual

- **Sprint activo:** S107 (completado) / Ciclo validación pendiente
- **Rama de trabajo:** `dev`
- **Sprints completados:** S3 → S107
- **Tests:** 1848 pass (unit) | 14 integration | 5 docker | 34 frontend (Vitest) | 26 Rust inline  
  *(5 pre-existentes siguen fallando: test_s31, test_s39, test_s47, test_s55, test_s63b)*
- **Cobertura baseline:** 88% TOTAL (2026-04-28)

---

## Última sesión (2026-05-04 — S107)

**Completado (S107-P1) — Architecture Gate:**
- Nodo `generate_architecture_contract` — determinístico, corre DESPUÉS de `request_approval` y ANTES de `route_agents`
- Extrae nombres canónicos de funciones del SDD (service.py tasks) y los formatea como JSON `[ARCHITECTURE CONTRACT — VINCULANTE]`
- Inyectado al INICIO del HumanMessage de cada agente (JSON → el modelo lo procesa como datos, no como texto)
- `route_after_approval` ahora devuelve `"generate_architecture_contract"` en lugar de `"route_agents"`

**Completado (S107-P2) — Oracle → PostgreSQL postprocesador:**
- `postprocess_yaml_file(content, rel_path, oracle_involved)` — nuevo entry point para YAML
- `_fix_oracle_in_docker_compose()` — reemplaza `gvenzl/oracle-xe`, `oracle/database` por `postgres:16-alpine`
- `system_devops.md` — sección RESTRICCIÓN ABSOLUTA con imagen obligatoria y ejemplo correcto
- `_write_artifacts` + `_run_agent_with_tools` pasan `oracle_involved` desde `fr_analysis`

**Completado (S107-P3) — Sync service imports:**
- `sync_service_imports(work_dir)` — AST walk post-fan-out, corrige imports de router.py y test_*.py
- `_build_service_alias_map()` — mapea `deactivate_X→delete_X`, `get_Xs→list_Xs`, `calcular_X→calculate_X`
- Llamado en `run_tests` antes de pytest

**Completado (S107-P4) — Naming table en templates:**
- `system_backend_python.md` — tabla REGLA DE NAMING CONSISTENTE: deactivate_X canónico, prohibe delete_X/remove_X

**Completado (S107-P5) — QA verifica contract:**
- En `qa_review`: parsea architecture contract JSON, verifica AST que funciones canónicas existen en services.py
- Penalización -5pt por función ausente, lista de violaciones inyectada en QA HumanMessage

**Suite:** test_s107.py — 47/47 PASS
**Total:** **1848 passed** (0 regresiones)

**Ciclo validación S106** (pendiente lanzar con S107)
**Ciclo validación S104** (078f18ca): QA **52/100 ❌** (2 retries), 27m 51s
**Ciclo validación S105** (69ba0b13): QA **40/100 ❌** (2 retries), 21m 49s

---

## Próxima sesión

**Primera tarea: Ciclo validación S107**
- Limpiar workspace `/Users/omarrobles/Workspace/mis-entregas/contratos-beneficios/` y lanzar ciclo fresco
- Target: QA ≥ 80, 0 naming mismatches, docker-compose → devops con PostgreSQL (no Oracle XE)
- Verificar que architecture contract se inyecta en los agentes (log `[S107-P1]`)
- Verificar que sync_service_imports corrige imports antes de pytest (log `[S107-P3]`)
- Generar `INFORME_PRUEBA_S107.md` con métricas: QA score, naming errors, docker image

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
| S107 | — | pendiente | — | — |

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
