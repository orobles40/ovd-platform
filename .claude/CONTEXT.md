# OVD Platform — Contexto dinámico del proyecto

> Este archivo contiene el estado vivo del proyecto.
> Se actualiza automáticamente con `/session-close` al final de cada sesión.
> Para las reglas permanentes del proyecto, ver `CLAUDE.md`.

---

## Estado actual

- **Sprint activo:** S111 (completado)
- **Rama de trabajo:** `dev`
- **Sprints completados:** S3 → S111
- **Tests:** 1908 pass (unit) | 14 integration | 5 docker | 34 frontend (Vitest) | 26 Rust inline  
  *(suite 100% limpia — 0 fallos pre-existentes pendientes)*
- **RAG:** 5235 chunks activos (3630 codebase + 1605 docs) — re-bootstrap S96-H completo 2026-05-04
- **Cobertura baseline:** 88% TOTAL (2026-04-28)

---

## Última sesión (2026-05-04 — S111)

**S111 — Frontend ejecutable + CORS + ORM safety — COMPLETADO:**
- S111-A (OVD-FE-001+FE-002): `ensure_frontend_scaffold(work_dir)` en `code_postprocessor.py` — detecta `frontend/` con `.tsx` sin `package.json`, crea automáticamente `package.json`, `vite.config.ts` (Tailwind v4 + `@tailwindcss/vite`), `index.html`, `tsconfig.json/app/node`, `src/main.tsx`, `src/index.css`, `src/vite-env.d.ts`; actualiza v3→v4 si ya existe
- S111-A: Llamado desde `deliver()` en `graph.py` cuando el agente frontend estuvo presente
- S111-A: `system_frontend_react.md` actualizado con sección "Scaffolding obligatorio" + hooks de dominio
- S111-B (OVD-BE-003): `_inject_cors_middleware(content, rel_path)` — inyecta `CORSMiddleware` en `main.py` si falta; template `system_backend_python.md` actualizado con nota S111-B obligatoria
- S111-C (OVD-BE-004): `_fix_back_populates_orphan(content, rel_path, work_dir)` — elimina `, back_populates='X'` cuando `X` no existe en ningún `models.py` del workspace
- S111-D (OVD-BE-005): template anti-stubs extendido a todos los routers (no solo auth)
- Tests: `test_s111.py` — 24/24 PASS | Suite: **1908 passed** (0 regresiones)
- Ciclo de validación S111 pendiente (lanzar con `/session-start` próxima sesión)

---

## Última sesión (2026-05-04 — S110 / S96-H)

**S96-H — RAG actualizado (ALTO) — COMPLETADO:**
- H1: `rag.clear_project_chunks(project_id)` en `rag.py` — elimina chunks stale de pgvector
- H1: `scripts/rag_bootstrap.py` — CLI con `--clear`, `--dry-run`, `--path`, `load_dotenv` automático
- H1 fix: psycopg3 requiere `postgresql://` nativo (no `postgresql+psycopg2://` de SQLAlchemy)
- H2: `_index_sdd_for_rag()` fire-and-forget en `deliver` — SDD de cada ciclo indexado como `delivery`
- H3: `session-close` SKILL.md Paso 9 actualizado — usa `rag_bootstrap.py` sin JWT
- Re-bootstrap ejecutado: **5235 chunks** frescos (3630 codebase + 1605 docs), 0 fallidos
- Tests: `test_s96h.py` — 11/11 PASS | Suite: **1886 passed** (0 regresiones)

---

## Última sesión (2026-05-04 — S109)

**Ciclo validación S109 (thread 5931bd36):** QA **90/100** ✅ en 11m 53s. S108-B fix confirmado. 3 agentes: devops + backend + frontend.

**S96-G (parcial) — Fix tests pre-existentes:**
- `test_s39::test_usa_cap_800_en_truncate` → renombrado y aserción actualizada al patrón invariante (S61-B cambió cap 800→2000)
- `test_s47::test_dispatch_frontend_despacha_pendientes` → `pending_agents` → `_dispatch_now` (S59-B cambió la clave)
- `test_s55::test_write_artifacts_overwrites_when_new_content_larger` → `calcular_imc` → `calculate_bmi` (S72-B renombra)

Suite: **1873 passed** (era 1869). Restan: test_s31 (race condition) y test_s63b (RuntimeError S94-fix).

---

## Última sesión (2026-05-04 — S108 cierre + fix post-ciclo)

**Contexto:** S107 alcanzó QA 94/100. Pytest falla por dos causas confirmadas en ciclo de validación.

**Completado (S108-P1) — Fix S79-C falso positivo:**
- `analyze_fr` S101-D: ahora usa regex negation-aware `(?:no|sin|not|without)[^\w\n]{0,6}oracle` para no activar `oracle_involved=True` cuando el FR dice "NO Oracle"
- `_verify_db_url_matches_fr(work_dir, fr_text, oracle_involved=None)`: nuevo parámetro. Si `oracle_involved` es provisto (del `fr_analysis`), lo usa en lugar de keyword matching sobre el texto crudo
- Call site en `run_tests`: pasa `state.fr_analysis.oracle_involved` a la verificación

**Completado (S108-P2) — Fix Pydantic Date TypeError:**
- `system_backend_python.md`: nueva sección `SEPARACIÓN CRÍTICA — ORM vs schemas Pydantic` con tabla de equivalencias SQLAlchemy→Python
- `_fix_sqlalchemy_date_in_pydantic_schemas(content, rel_path)`: postprocesador que detecta `from sqlalchemy import ... Date` en archivos con `BaseModel`, remueve `Date`/`DateTime` del import SQLAlchemy y agrega `from datetime import date/datetime`
- Registrado en `postprocess_python_file()` (solo archivos no-conftest)

**Completado (S108-P3) — Cleanup service.py/services.py:**
- `_remove_duplicate_service_files(work_dir)`: si `service.py` y `services.py` coexisten en el mismo directorio, elimina `service.py` si es idéntico o stub vacío (<50 chars); preserva `services.py` como canónico
- Llamado como primer paso en `sync_service_imports()` (S107-P3)

**Completado (S108-P4) — Clasificación de fallos pytest:**
- `_classify_pytest_failures(output)`: clasifica errores en 5 categorías (import_errors, type_errors, name_errors, assertion_errors, fixture_errors)
- `_build_typed_retry_feedback(classified)`: genera feedback diferenciado por tipo — type_error menciona fix Pydantic Date, import_error menciona naming mismatch
- Integrado en `update_test_retry()` antes de componer `new_feedback`

**Suite:** test_s108.py — 22/22 PASS (se agregó test_archivo_mixto_orm_pydantic_no_tocado post-ciclo)
**Total:** **1869 passed** (0 regresiones, +21 respecto a S107/1848)

**Fix post-ciclo S108-B (commit a2a57398a):**
- Regresión detectada: `_fix_sqlalchemy_date_in_pydantic_schemas` removía `Date` del import en archivos ORM+Pydantic mixtos → `NameError: name 'Date' is not defined`
- Guard agregado: `if re.search(r"Column\s*\(\s*Date\b", content): return content`
- Ciclo S108: QA 60/100 (degradado por el NameError). S109 validará recovery.

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

**S112 — Opciones:**
1. **Ciclo validación S111**: confirmar que los 5 fixes (scaffolding, CORS, back_populates, stubs, hooks) resuelven los issues documentados en el ciclo c2aa9c6c
2. **S96-I — OB-02**: indexar artefactos generados (código de cada agente) post-ciclo como doc_type=codebase
3. **S112 — DigitalOcean deployment gaps** (para demo 2026-05-18)

---

## Fallos pre-existentes a corregir (S96-G)

> Sesión dedicada planificada. No investigar en sesiones de features.
> Usar `/fix-test` para abordarlos sistemáticamente.

| Test | Causa conocida | Prioridad |
|---|---|---|
| `test_s31::test_cycle_start_ts_reciente` | Flaky por timing — race condition | Media |
| `test_s63::test_s63b_cleanup_not_in_run_tests` | RuntimeError por S94-fix | Alta |

*(test_s39, test_s47, test_s55 corregidos en S109 — ver commit 9fb5f97f0)*

---

## Issues abiertos

| Issue | Impacto | Estado | Sprint |
|---|---|---|---|
| `POST /auth/login` → 500 | Bloquea dashboard web | ✅ RESUELTO | S96-F |
| `test_s63b_cleanup_in_retry_round_zero` | Suite no limpia | Pendiente | S96-D |
| QA score ≤ 50 en ciclos con 2 agentes | Conflicto BD perfil/FR | Pendiente | S97-A |
| devops sobrescribe tests del backend | write_artifacts sin protección | Pendiente | S97-B |
| **OVD-FE-001** — Agente frontend no genera proyecto Vite completo | App no ejecutable sin scaffolding manual (`package.json`, `vite.config`, `main.tsx`, `index.html`) | ✅ RESUELTO S111-A | S111 |
| **OVD-FE-002** — Hooks custom no generados | Componentes importan `useTurnos`, `useMedicos`, etc. que no existen en la entrega | ✅ RESUELTO S111-A | S111 |
| **OVD-BE-003** — CORS no configurado en `main.py` | Frontend en distinto puerto falla con "Failed to fetch" | ✅ RESUELTO S111-B | S111 |
| **OVD-BE-004** — `back_populates` ORM sin relación inversa | `TurnoORM` define `back_populates='turnos'` pero `PacienteORM`/`MedicoORM` no tienen esa propiedad — `InvalidRequestError` al instanciar | ✅ RESUELTO S111-C | S111 |
| **OVD-BE-005** — Stubs S96-A no reemplazados | `auth/router.py` y `turnos/router.py` quedaron como `# stub auto-generado` — app no arranca | ✅ RESUELTO S111-D | S111 |

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
| S107 | 0426dd25 | **94** ✅ | 1 retry (S79-C+Pydantic Date) | 13m 45s |
| S108 | 3fbfc62d | **60** ❌ | 0 retries (NameError S108-B regresión) | 14m 50s |
| S109 | 5931bd36 | **90** ✅ | 0 retries (S108-B guard activo) | 11m 53s |

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
