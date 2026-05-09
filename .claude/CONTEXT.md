# OVD Platform — Contexto dinámico del proyecto

> Este archivo contiene el estado vivo del proyecto.
> Se actualiza automáticamente con `/session-close` al final de cada sesión.
> Para las reglas permanentes del proyecto, ver `CLAUDE.md`.

---

## Estado actual

- **Sprint activo:** S112 (Despliegue DigitalOcean — demo 2026-05-18) + S122 (calidad engine)
- **Rama de trabajo:** `main`
- **Sprints completados:** S3 → S121
- **Tests:** 2013 pass (unit) | 14 integration | 5 docker | 34 frontend (Vitest) | 26 Rust inline
- **RAG:** 5235 chunks activos (3630 codebase + 1605 docs) — re-bootstrap S96-H completo 2026-05-04
- **Cobertura baseline:** 88% TOTAL (2026-04-28)

---

## Última sesión (2026-05-09 — S124: fix postprocessor test DB imports + templates async)

**S124 — Fix generación de tests con bases de datos — COMPLETADO:**

- **B1 — `_UNSAFE_DB_NAMES`**: removidos `get_engine` y `get_session_factory` — son API público post-S122-A, no deben eliminarse de imports de test.
- **B2 — `_fix_test_session_usage`** (`code_postprocessor.py`): cuando S123-B elimina el import de factory, esta función reemplaza los usos residuales (`AsyncSessionLocal()`, `async_session_maker()`, etc.) por `_TestSessionFactory()` en el cuerpo del test. Si `create_async_engine` no estaba presente, inyecta el preamble con engine SQLite in-memory automáticamente. Garantía dura — no depende del modelo.
- **A1 — `system_backend_python.md` Ejemplo 2**: reemplazado patrón sync (`create_engine` + `TestClient` + `from src.database import get_db`) por patrón async correcto (`create_async_engine` + `AsyncClient` + `ASGITransport`). Eliminada contradicción con D6.
- **A2 — `stack/backend_python.md` D6**: agregado `dependency_overrides[get_session]` completo con `override_get_session` async, `clear()` al finalizar, y `dispose()` en teardown.
- **18 tests** en `test_s124.py` — todos PASS. Suite total: 2045 passed.
- **Commit:** `34079d11f`

## Última sesión (2026-05-09 — S123: auth JWT OVD Desktop + fix RLS ovd_cycles)

**S123 — Auth y registro de ciclos en producción — COMPLETADO:**

- **Auth desktop end-to-end:**
  - `config.rs` + `state.rs`: campo `engine_secret` en AppState y SQLite
  - `tauri.ts` + `Login.tsx` + `Workspace.tsx`: UI para configurar Engine URL + secret
  - `FrLauncher.tsx`: `Authorization: Bearer <token>` en POST /session y /approve; `?token=<jwt>` en SSE URL (EventSource no soporta headers custom)
  - `getAccessToken()`: llama `authRefreshToken()` cuando el token es sentinel `"__stored__"` (sesión restaurada sin re-login)
- **Fix RLS ovd_cycles (3 ubicaciones):**
  - `api.py` session_create: `SET app.current_org_id = %s` antes del INSERT `ovd_cycles`
  - `api.py` `_ensure_cycle_registered`: leer `org_id` del checkpoint antes de abrir conexión; SET antes de SELECT/UPDATE
  - `graph.py` deliver: `SET app.current_org_id = %s` antes del INSERT/UPSERT
  - Causa raíz: `doadmin` en DO PostgreSQL NO es superuser real — RLS aplica. La política `ovd_cycles_org_isolation` requiere `app.current_org_id` seteado.
- **Ciclo S113 dry run:** autenticación confirmada end-to-end. 4 rondas QA (45→65→60→68) — fallo de calidad del modelo (deepseek-v4-pro), no de infraestructura.
- **Decisión:** mantener deepseek-v4-pro en producción (no migrar a Claude Sonnet).
- **Suite:** 2027 passed (unit), 0 regresiones.
- **Commit:** `a574a84ec`

## Última sesión (2026-05-08 — S121 + S122: postprocessor lazy engine + fix ciclo validación)

**S121 — Fix ImportError conftest.py — COMPLETADO:**
- S121-A: `backend_python.md` regla D5 — PROHIBIDO `engine = create_async_engine(...)` a nivel módulo en `database.py`. Patrón lazy `_engine=None + def get_engine()` obligatorio.
- S121-B: `backend_python.md` — PROHIBIDO `from src.database import ...` en conftest.py. Patrón correcto: `from src.main import app` + `httpx.AsyncClient`.
- S121-C: `graph.py` `update_test_retry` — detección `_is_conftest_importerror` + inyección hint lazy init cuando conftest ImportError.
- **Ciclo validación `46d2d42a`:** S121-B ✅ validado (3 rondas conftest correcto). S121-A ❌ no efectivo (modelo ignoró la regla). QA máximo 72/100.

**S122 — Postprocessor lazy engine — COMPLETADO:**
- S122-A: `_fix_database_module_level_engine` en `code_postprocessor.py` — reescribe `engine = create_async_engine(...)` y `<var> = async_sessionmaker(engine, ...)` a nivel módulo → lazy `get_engine()` + `get_session_factory()`. Paso 2 generalizado para cualquier nombre de variable (no solo `AsyncSessionLocal`).
- S122-B: `update_test_retry` — detección expandida a `src.main`, `src/main`, `create_async_engine` además de `database`.
- 17 tests en `test_s122.py` — todos PASS incluyendo caso `async_session_factory`.
- **Ciclo validación `7990efb6`:** S122-A ✅ disparado 2 veces en logs. QA 95/100 (mejor histórico). Nuevo fallo: test files importan `async_session_maker` de `src.database` (renombrado por S122-A) → S123.

**Commits:** `d1057cac` (S122 inicial) + `47ab0b7f` (fix paso 2 generalizado)
**Deploy DO:** `417cc98a` ACTIVE

---

## Última sesión (2026-05-07 — S112: S112-D fix directorio DO + SDD→deepseek + ZIP download)

**S112 — Deploy DigitalOcean — EN PROGRESO:**

3 mejoras completadas en esta sesión:

1. **S112-D fix directorio** (`api.py`): `_ws.mkdir(parents=True, exist_ok=True)` en `session_create` — DO App Platform no pre-crea `/srv/projects/{id}/`. Sin esto `run_tests` fallaba con `[Errno 2] No such file or directory`.
2. **OVD_MODEL_SDD=deepseek-v4-pro** (`do_app_spec.yaml`): qwen3-coder-flash agota los 8192 completion tokens en modo thinking al generar el SDD estructurado. deepseek-v4-pro: 15.9s vs 260s anterior (16× más rápido), sin `LengthFinishReasonError`.
3. **S112-E ZIP download** (`api.py` + `ovd.ts` + `FrLauncher.tsx`): nuevo endpoint `GET /session/{thread_id}/artifacts/download` + botón "Descargar código" en estado `phase=done` del Lanzador FR.

**Primer deliver exitoso en DO**: ciclo `180baa45` completó todos los nodos incluyendo `deliver`. Código generado: 10 archivos (turnos-demo/Sistema de Turnos Médicos).

**Bloqueante pendiente**: Merge `dev→main` para deploy en DO (o `doctl apps update`). D3 (secrets en panel DO) ya estaba cubierto por `app.yaml` con tokens DO GenAI.

**Commit**: `2a5c724fb` — feat(s112): ZIP download de artefactos generados desde Lanzador de FR

---

## Última sesión (2026-05-06 — S112 deploy DO: 4 blockers resueltos, DB prod operativa)

**S112 — Deploy DigitalOcean App Platform — EN PROGRESO:**

Infraestructura DO creada y configurada. 4 blockers de build/startup resueltos iterativamente:

1. **`dockerfile_path` relativo al repo raíz** (no a `source_dir`): `Dockerfile` → `src/engine/Dockerfile` y `src/dashboard/Dockerfile`.
2. **`infisical-python` sin wheel Linux x86_64**: eliminado de `pyproject.toml` + `uv.lock` regenerado. El paquete nunca fue importado en Python (solo `httpx` vía `InfisicalAdapter`).
3. **NATS `run_command` incompleto**: `run_command: -js -m 8222` → `run_command: nats-server -js -m 8222` (DO usa `run_command` como exec completo, no como args del entrypoint).
4. **PostgreSQL `db` user sin privilegios CREATE** (`production: false` = BD interna con usuario severamente restringido, REVOKE a nivel plataforma DO — no hay workaround vía GRANT). Fix definitivo: `production: true` + cluster standalone `ovd-postgres-prod` creado via `doctl databases create`. Usuario `doadmin`, `can_create_public=True` ✅, migraciones Alembic completadas ✅, seed aplicado ✅.

**Infraestructura DO activa:**
- App: `ovd-platform` (ID: `f8d2207e-8229-4647-b9ad-5c14dcba4246`)
- PostgreSQL: `ovd-postgres-prod` (ID: `f047cf82-6af0-4d3e-8ae7-15c6e96d785a`, nyc3, online)
- Último deploy: `cae0c11f` — 9/11 ERROR

**Bloqueante actual:** `ANTHROPIC_API_KEY` (tipo SECRET en `app.yaml`) no configurada en panel DO. Engine arranca, corre Alembic y seed, luego valida settings y falla:
```
[REQUIRED] Sin provider LLM — define ANTHROPIC_API_KEY, OLLAMA_BASE_URL u OPENAI_API_KEY
Application startup failed. Exiting.
```
**Acción requerida del usuario:** Ir a panel DO → Apps → ovd-platform → Settings → Environment Variables → configurar los 5 secrets: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OVD_ENGINE_SECRET`, `JWT_SECRET`, `OVD_ADMIN_PASSWORD`.

---

## Última sesión (2026-05-05 — S111 ciclo validación + fix tool-calling bypass)

**S111 ciclo validación — COMPLETADO:**
- Fix tool-calling bypass: en `_run_agent_with_tools` (graph.py) — después de `_build_artifacts_from_files`, aplica `postprocess_python_file`/`postprocess_yaml_file` a cada `.py`/`.yml` escrito via tool calls. Antes, solo `_write_artifacts` (output-parsing) aplicaba los postprocessadores.
- Fix S111-A `deliver()`: se eliminó el guard `any(r.get("agent") == "frontend" ...)` — `ensure_frontend_scaffold` se llama siempre que haya `directory`; la función devuelve `[]` si no detecta tsx.
- 2 tests nuevos en `test_s111.py`: `test_inject_cors_applied_to_disk_file` + `test_ensure_frontend_scaffold_runs_with_src_components_tsx` → **26/26 PASS**
- Ciclo validación thread `4721d06e` (2026-05-05): **S111-B ✅** CORSMiddleware inyectado en `src/main.py` a las 09:09. **S111-A ✅** 9 archivos scaffold creados (package.json, vite.config.ts Tailwind v4, index.html, src/main.tsx…). **S111-C ✅** sin orphan back_populates. QA: 50/100 (tests fallidos — independiente de S111).
- Bug `auto_approve`: diagnosticado — el campo SÍ está en el checkpoint (confirmado en values_keys S48-D), el `/state` endpoint no lo expone. `request_approval` lo lee correctamente (log: `auto_approve=True` a las 09:08).
- Engine requiere `.env` cargado al inicio (no hereda de nohup sin source) — arrancar con `python -c "import dotenv; dotenv.load_dotenv(); os.execv(uvicorn…)"`.

---

## Última sesión (2026-05-04 — S111)

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

**S125 — Ciclo de validación con los fixes acumulados (S121→S124)**

Lanzar ciclo en producción para confirmar que:
- S122-A (lazy engine) se activa correctamente
- S124-B (_fix_test_session_usage) corrige tests con factory residual
- Los tests generados pasan pytest sin ImportError ni NameError
- QA score ≥ 70

**Deploy DO:** rebuild necesario para que fixes S123 (RLS) + S124 (postprocessor) lleguen a producción.
`doctl apps create-deployment f8d2207e-8229-4647-b9ad-5c14dcba4246`

**S112 — Deploy DO (demo 2026-05-18):**
- D4: `curl https://ovd-platform.codigonet.cloud/health` (después de verificar merge)
- D5: RAG bootstrap prod

**Backlog post-demo:** test_s63b, S96-I, Modo 5, Sprint 46, S113 (guion presentación)

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
| S120 | a18c7b32 | — | FAIL | conftest `from src.database import` directo |
| S121 | 46d2d42a | **72** ❌ | FAIL × 3 | conftest correcto ✅ pero database.py engine module-level |
| S122 | 7990efb6 | **95** ✅ | FAIL × 3 | S122-A activado ✅ — nuevo fallo: test imports src.database |

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
