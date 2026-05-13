# OVD Platform — Contexto dinámico del proyecto

> Este archivo contiene el estado vivo del proyecto.
> Se actualiza automáticamente con `/session-close` al final de cada sesión.
> Para las reglas permanentes del proyecto, ver `CLAUDE.md`.

---

## Estado actual

- **Sprint activo:** S129 ✅ (full-stack SDD coverage — COMPLETADO)
- **Rama de trabajo:** `main`
- **Sprints completados:** S3 → S128
- **Tests:** 2171 pass (unit, +20 S129) | 14 integration | 5 docker | 74 frontend (Vitest) | 26 Rust inline
- **RAG:** 5235 chunks activos (3630 codebase + 1605 docs) — re-bootstrap S96-H completo 2026-05-04
- **Cobertura baseline:** 88% TOTAL (2026-04-28)

---

## Última sesión (2026-05-12 — S024: S128 — Post-ciclo correctivos + ciclo validación)

**S128 — Correctivos post-ciclo 92c6641f — COMPLETADO:**

- **S128-A** (`system_sdd.md`): Sección "EXPORTS explícitos por tarea de servicios" — cada tarea de servicios debe incluir bloque EXPORTS con funciones que exporta.
- **S128-A2** (`graph.py` `_p2_infer_signature`): Sugerencias de firma al detectar imports de funciones no definidas en S103-P2. 8 patrones: get_by, get_, list_, create_, update_, delete_, cancel_, fallback genérico.
- **S128-B** (`system_sdd.md`): Sección "Módulo primario obligatorio" — el módulo primario de un agente NUNCA puede quedar como stub, aunque el cap lo limite.
- **S128-C1** (`system_frontend_react.md`): Sección App.tsx obligatorio para entregas multi-componente (≥2 componentes), con ejemplo BrowserRouter + Routes.
- **S128-C2** (`graph.py` `_s128_c2_ensure_app_tsx`): Nueva función que se llama desde `deliver()` — genera App.tsx automáticamente si hay ≥2 archivos `.tsx` y no existe App.tsx.
- **S128-D1** (`api.py`): Timeout adaptativo en `_run_graph_background` — lee `test_retry_count` del checkpoint y aplica: `_adaptive_timeout = _SSE_STREAM_TIMEOUT + (retry_round × 900)`.
- **S128-E3** (`graph.py`): Cap duro reducido: `{"low": 3, "medium": 5, "high": 5, "critical": 7}` (antes: 5/8/8/10).
- **28 tests** (`test_s128.py`) — 28/28 PASS. Suite completa: PASS.
- **Commit:** `025b87ef2` (S128 + tests). **Push:** origin/main ✓

**Ciclo validación `7bfecf37` (2026-05-12 16:05–16:36):**
- FR: "Implementar módulo de agendamiento de turnos médicos"
- Resultado: ERROR (timeout adaptativo 1800s con retry_round=1)
- QA: 55/100 | Security: 100/100 | Deliverables: 0 | Tokens: 246K in / 148K out
- Mejora vs 92c6641f: llegó a qa_review (92c6641f abortó en security_audit)
- Issues: SDD generó solo backend (sin frontend tasks) → frontend ausente → QA falla REQ-005
- Informe: `docs/INFORME_S128_CICLO_7bfecf37.md`

## Última sesión (2026-05-12 — S025: S129 — Full-Stack SDD Coverage)

**S129 — COMPLETADO:**

- **S129-A** (`graph.py`): `FRAnalysisOutput.frontend_required: bool = False` + `system_analyzer.md` instrucción para emitirlo
- **S129-B** (`system_sdd.md`): Checklist full-stack obligatorio — "NO generes solo tareas backend para FR full-stack"
- **S129-C** (`graph.py`): `_ensure_frontend_tasks_if_fullstack()` + `_infer_entity_name_from_fr()` — injector determinístico de tareas frontend
- **S129-D** (`api.py`): Timeout adaptativo suma `test_retry_count + qa_retry_count`
- **S129-E** (`templates/stack/backend_python.md`): Patrón SQLAlchemy async con `async with db.begin()` + commit/rollback
- **20 tests** (`test_s129.py`) — 20/20 PASS. Regresión: 2171 pass, 0 nuevas regresiones.
- **Commit:** `acb6a38f4` | **Push:** origin/main ✓ | **Deploy DO:** ACTIVE

**Ciclo validación `732d6b91` (2026-05-12 18:17–18:34):**
- FR: "Implementar módulo de agendamiento de turnos médicos"
- Resultado: **DONE** ✅ (vs S128: ERROR timeout)
- QA: 75/100 | Security: 100/100 | Artefactos: 8 | Duración: 881s (14m41s)
- Agentes: devops + backend + **frontend** (3 — vs S128: 1 solo backend)
- Retries: 2 test retries (naming clash `TurnoORM` vs `Turno`)
- Informe: `docs/INFORME_S129_CICLO_732d6b91.md`

## Próxima sesión: S130 — Naming consistency cross-agent

**Prioridad S130-A:** Naming clash entre agentes — `models.py` genera `TurnoORM` pero `services.py` importa `Turno`. Causa 2 test retries sin resolución. Fix: `_ensure_orm_name_consistency()` post-execute que detecta y corrige discrepancias de nombre entre archivos del mismo módulo.

**Prioridad S130-B:** QA 75→90 — reforzar import consistency entre agentes. El SDD debe declarar el nombre canónico de cada clase ORM para que todos los agentes lo usen.

**Prioridad S130-C:** `frontend_required` no emitido por LLM — falta ejemplo concreto en `system_analyzer.md`.

## Última sesión (2026-05-13 — S026: S130+S131 — Retry overwrite semántics)

**S130 — ORM Naming + Custom Exceptions + frontend_required — COMPLETADO:**
- S130-A/A2/B/C/C2/D: 14 tests PASS. Ciclo `071ce4f4` incompleto por re-deploy DO mid-cycle.
- Informe: `docs/INFORME_S130_CICLO_071ce4f4.md`
- Commits: `ed468b326`, `7d193ee8c`

**S131 — Retry Overwrite Semántics — COMPLETADO:**
- **S131-A** (`graph.py` `_write_artifacts`): eliminada protección < 50% (S55-B). Solo protege output vacío (`strip()==0`). Root cause del QA stuck en 62.
- **S131-B** (`graph.py` `agent_executor`): preamble retry extiende S97-C con `ARCHIVOS A SOBRESCRIBIR` — lista rutas canónicas del agente. LLM sabe exactamente qué sobrescribir.
- **S131-C** (`code_postprocessor.py` `deduplicate_module_files`): elimina copias en rutas no canónicas. Llamado en `run_tests` antes de `sync_service_imports`.
- **S131-D** (`code_postprocessor.py` `_build_service_alias_map`): 14 patrones ES/EN: `crear_→create_`, `obtener_→get_`, `eliminar_→delete_`, `actualizar_→update_`, etc.
- **S131-E** (`graph.py` `_run_agent_with_tools`): escribe `debug_frontend_initial.txt`/`debug_frontend_retry.txt` cuando frontend entrega 0 artefactos.
- **16 tests** (`test_s131.py`) — 16/16 PASS.

## Próxima sesión: Ciclo de validación S131

Lanzar ciclo "Implementar módulo de agendamiento de turnos médicos" y verificar si QA supera 75 (baseline S129). Objetivo: ≥80/100. Foco en "múltiples versiones no consolidadas" que no debe aparecer en QA issues.

## Última sesión (2026-05-12 — S023: OVD Desktop S126 — Telemetría T3+T4+T6)

**S126 — Telemetría OVD Desktop COMPLETO (T3+T4+T6):**

- **T3 — `db.rs`** (nuevo módulo Rust): tablas SQLite `cycle_history` + `error_log` en `config.db`. Comandos Tauri: `db_save_cycle`, `db_list_project_cycles`, `db_list_errors`. Wrappers TypeScript en `tauri.ts` con interfaces `CycleEntry` + `ErrorLogEntry`.
- **T4 — endpoint `POST /telemetry/client-event`** (api.py): acepta `{thread_id, event, client}`, auth con `X-OVD-Secret`, retorna 204. FrLauncher.tsx lo llama fire-and-forget con `reportClientEvent()` tras completar ciclo. `ovd.ts` exporta `reportClientEvent`.
- **T6 — Panic hook** (`main.rs`): `std::panic::set_hook` persiste crashes en `error_log` via `db::log_error` antes de que el proceso muera.
- `lib.rs`: módulo `pub mod db` registrado, `db::init_db()` en setup, 3 nuevos comandos en `invoke_handler![]`.
- **28 tests Python** (`test_s126.py`) — PASS. **74 tests vitest** — PASS (4 nuevos en `db.test.ts`).

## Última sesión anterior (2026-05-12 — S022: OVD Desktop S126 — Telemetría T1+T2+T5)

**S126 — Telemetría OVD Desktop (T1+T2+T5) — COMPLETADO:**

- **`lib/ovd.ts`** (nuevo): `fetchDelivery`, `fetchOrgStats`, `fetchOrgCycles`, `loadCycleHistory`, `saveCycleEntry`, `fmtTokens`, `fmtSecs`.
- **T2 — TelemetryCard** (`FrLauncher.tsx`): al completar ciclo llama `GET /session/{thread_id}/delivery`, muestra QA, seguridad, tokens entrada/salida y duración dentro de la card de entrega. Ciclo guardado en `localStorage["ovd_cycle_history"]` via `saveCycleEntry`.
- **T1 — Historial por proyecto** (`Workspace.tsx`): botón `History` por tarjeta expande panel inline con últimos ciclos (fecha, FR, QA, tokens, duración, archivos). Lee de localStorage.
- **T5 — OrgStatsBar** (`Workspace.tsx`): al cargar, fetcha `/api/v1/orgs/{id}/stats` (JWT fresco) y muestra ciclos totales, QA promedio y costo USD últimos 30 días. Fallo silencioso.

## Última sesión (2026-05-11 — S021: OVD Desktop UI — NavSidebar + Workspace enriquecido + vitest)

**S125 (continuación) — OVD Desktop UI completo — COMPLETADO:**

- **Fix refresh token rotation** (`auth.rs`): `_auth_refresh_token` ahora lee `Set-Cookie` ANTES de consumir el body con `.json()`. El nuevo `refresh_token` rotado se persiste en Keychain. Antes se descartaba → SSE fallaba en reconexión.
- **NavSidebar flotante** (`NavSidebar.tsx`): sidebar colapsable (48px icons / 192px expandido), flecha toggle, ítems Lanzar FR + Workspace. Iniciales del avatar desde email. Persistencia en `localStorage["ovd_nav_collapsed"]`.
- **App.tsx reescrito**: `AppShell` con estado `collapsed`, sidebar solo visible cuando autenticado y fuera de `/login`.
- **Workspace enriquecido** (`Workspace.tsx`): tarjetas con Stack, Tooling, Descripción, Knowledge Bases, badge Engine (verde/rojo), botón editar, eliminación con confirmación inline. `EditProjectModal` completo: 13 opciones de stack, campo tooling CI/CD, campo descripción, KBs con path/label/stack opcionales. Botón "Guardar y lanzar FR".
- **FrLauncher.tsx**: textarea redimensionable desde borde superior, altura persistida en localStorage. Controles "Auto-aprobar" + "Enviar" centrados fuera del contenedor con `overflow-hidden` (fix botón cortado). `enrichedCtx` construye `[Metadatos del proyecto]` con stack/tooling/descripción/KBs y lo prepende al `project_context` del engine.
- **Vitest setup** (`vitest.config.ts`, `vitest.setup.ts`): jsdom, mocks Tauri globales, `localStorage.clear()` en `beforeEach`. 47 tests en 6 archivos — todos PASS.
- **Fix test_s125h_frlauncher_fallback_to_directory**: aserción actualizada para coincidir con implementación refactorizada (`||` en lugar de `??`).
- **Suite:** 2065 passed (unit). 47 vitest (desktop).
- **Tag:** `s125-desktop-ui` pusheado.

## Última sesión (2026-05-09 — S020: OVD Desktop Opción C — outputDirectory + cleanup endpoint)

**S125 — OVD Desktop: extracción automática de artefactos — COMPLETADO:**

- **`Workspace.tsx`**: `Project` exportada con `outputDirectory?: string`; botón lápiz por proyecto; modal para elegir carpeta de salida con `workspacePickFolder`.
- **`FrLauncher.tsx`**: importa `Project` de Workspace; `handleDeliver()` usa `outputDirectory ?? directory`; banner post-entrega con contador de archivos + botón "Abrir"; estado `writtenFiles`; llama `DELETE /session/{id}` para cleanup (best-effort).
- **`tauri.ts`**: export `workspaceOpenFolder(folder)`.
- **`workspace.rs`**: comando `workspace_open_folder` — usa `open`/`explorer`/`xdg-open` según SO. Registrado en `lib.rs`.
- **`api.py`**: endpoint `DELETE /session/{thread_id}` — elimina tmpdir del engine solo si está bajo `gettempdir()` (preserva directorios de proyecto). Verificado: `{"ok":true,"removed":true}` con tmpdir real.
- **RAG Bootstrap producción (D5):** codebase (3914 chunks) + docs (1930 chunks) indexados en DO PostgreSQL con bge-m3. Documentado en `docs/RAG_BOOTSTRAP.md`.
- **20 tests** `test_s125.py` — 20/20 PASS. Suite total: 2065 passed.
- **Ciclos de validación:** 2 ciclos locales OK — seguridad 100/100, entrega ✓, cleanup tmpdir ✓.
- **Lint fix:** import sorting en `knowledge/bootstrap.py` y `knowledge/cli.py` (pre-existentes en S018).

## Última sesión (2026-05-09 — S019: OVD Desktop F7 smoke test + fix write_artifacts + tag desktop-v0.1.1)

**OVD Desktop F7 — COMPLETADO:**

- **Fix write_artifacts (2 bugs):**
  - `FrLauncher.tsx`: `threadIdRef` para evitar stale closure en `handleDeliver` — usaba `session_id` en vez de `thread_id` en la llamada a `/artifacts/download`
  - `FrLauncher.tsx`: `directory: ""` en POST /session — path local no existe en DO
  - `api.py`: `tempfile.mkdtemp()` automático cuando `directory` no se provee — caso desktop sin `project_id`
- **Smoke test completo:** Login ✅ → Workspace ✅ → FR ✅ → tests PASS 5/5 ✅ → 5 archivos escritos en carpeta local ✅
- **Tag `desktop-v0.1.1`** pusheado — CI `Desktop Release` disparado en GitHub Actions (macOS aarch64 + x86_64)
- **Fix test_s120:** `test_s120a_fires_before_empty_directory_warning` → `test_s120a_fires_before_tmpdir_fallback` — refleja el nuevo comportamiento
- **Rebuild DO:** `5c493ce6` ACTIVE — engine con fix tmpdir en producción
- **Commits:** `984558487` (messages reducer), `85cf76b34` (write_artifacts fix)
- **Suite:** 2044 passed (unit)

## Próxima sesión: Bootstrap RAG producción (D5) + verificar GitHub Release desktop-v0.1.1

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

**S126 Desktop — Telemetría (pendiente):**
- **T3:** SQLite local en Rust (`db.rs`) — historial offline por proyecto
- **T4:** `POST /api/v1/telemetry/client-event` en engine + fire-and-forget desde FrLauncher
- **T6:** Panic hook en `main.rs` + tabla `error_log` en SQLite

**Deploy DO (demo 2026-05-18):**
- Rebuild fue lanzado en sesión S022: deployment `ffeefb17` (monitorear estado)
- Compilar release `desktop-v0.2.0`

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
