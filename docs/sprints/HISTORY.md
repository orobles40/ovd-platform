# Historial de sprints — OVD Platform

> Novedades S19–S95 en orden cronológico inverso.
> Ver sprint activo en `docs/sprints/CURRENT.md`.

---

## S85–S95 (2026-04-28)

### S95 — Diagnóstico bloqueador final
- **Ciclo `65ab6e7b`:** S65-A detectó 1 import roto: `from src.utils.prime_validator import is_prime` en `contracts/service.py` — el LLM confundió el proyecto contratos con el proyecto calculadora IMC anterior.
- **Diagnóstico:** contaminación de contexto LLM entre proyectos. Fix: S96-B postprocessor.
- **Tests:** ~1477 PASS (regresión `test_s63b_cleanup_in_retry_round_zero` por S94-fix — pendiente S96-D).

### S94 — Fix S63-B borraba src/ cuando pytest ya colectaba tests
- **S63-B fix:** `update_test_retry` verifica `collected \d+ items?` en `last_test_error`. Si pytest colectó ≥1 test, preserva `src/` y solo limpia tests con errores.
- **Hito:** Ciclo `5a17c6a2` alcanzó `collected 9 items / 1 error` — más cercano a pytest exit 0.
- **Commit:** `a0102962c`.

### S93 — Fix `oracledb.init_oracle_client()` residual
- **S82-F extendido:** siempre elimina `oracledb.init_oracle_client()` si aparece, sin importar la URL (resuelve caso PostgreSQL f-string + init_oracle_client).
- **Commit:** `a359b166a`.

### S92 — Fix `DeclarativeBase` sin `class Base(DeclarativeBase)` (SQLAlchemy 2.0)
- **S80-C extendido:** detecta `from sqlalchemy.orm import DeclarativeBase` sin `class Base(DeclarativeBase): pass` → reemplaza con `from src.database import Base`.
- **S84-A f-string:** `_fix_oracle_init_in_postgres_db()` detecta f-strings `f'postgresql+psycopg://...'`. Regex actualizado con `f?`.
- **Commit:** `10ebc69d5`.

### S91 — Auto-gen `contracts/router.py`
- **S91-A:** cuando `src.contracts.router ← no existe`, genera `src/contracts/router.py` con endpoints CRUD: `POST /contratos`, `GET /contratos/{rut}`, `POST /contratos/{id}/beneficios`, `GET /contratos/{id}/beneficios`.
- **Commit:** `01c69cdb1`.

### S90 — Auto-gen `auth/service.py` + fix `src.benefits.*`
- **S90-A:** cuando `src.auth.service ← no existe`, genera `src/auth/service.py` con `verify_password()`, `create_access_token()`, `login_user()`.
- **S90-B — `_fix_benefits_module_import()`:** redirige `from src.benefits.X import` → `from src.contracts.X import`.
- **Commit:** `7d5b38fe7`.

### S89 — Auto-gen `contracts/models.py` + fix `*.repository`
- **S89-A:** cuando `src.contracts.models ← no existe`, genera `src/contracts/models.py` con `ContractORM`, `BenefitORM` + schemas Pydantic.
- **S89-B — `_fix_phantom_repository_import()`:** elimina `from src.X.repository import ...`.
- **Commit:** `73fa1e5bf`.

### S88 — Fix imports `*.orm` (postprocessor)
- **S88-A — `_fix_orm_phantom_module_import()`:** regex `from src.X.orm import` → `from src.X.models import`.
- **S87-diag:** logging explícito de imports rotos en `_validate_artifacts_imports`.
- **Commit:** `c47ef25a0`.

### S85 — Validación del pipeline S84
- **Resultado:** S65-A seguía bloqueando por `import oracledb` en f-strings.
- **Diagnóstico:** S84-A no detectaba f-strings; S82-F no removía `oracledb.init_oracle_client()` cuando URL ya era PostgreSQL.

### Comparativa ciclos S85–S95

| Ciclo | Hash | S65-A | pytest | Bloqueador |
|-------|------|-------|--------|------------|
| S85 | — | bloquea | no ejecuta | oracledb f-string |
| S88 | f8a16d77 | bloquea | no ejecuta | `.orm` suffix |
| S89 | 3c5dad50 | bloquea | no ejecuta | contracts/models.py no existe |
| S90 | fa795201 | bloquea | no ejecuta | auth/service.py + src.benefits.* |
| S91 | 214aef2f | bloquea | no ejecuta | contracts/router.py no existe |
| S92 | 5ab8e3f5 | bloquea | no ejecuta | Base no definido |
| S93 | 2fc0ba7c | bloquea | no ejecuta | oracledb.init sin import |
| S94 | 5a17c6a2 | **pasa** | **9 items / 1 error** | S63-B borraba src/ |
| S95 | 65ab6e7b | bloquea | no ejecuta | prime_validator espurio |

---

## S84 (2026-04-28)

- **S84-B:** `_write_artifacts()` devuelve `content` — habilita S83-F context injection.
- **S84-A:** `_fix_oracle_init_in_postgres_db()` en postprocessor.
- **S84-A-v2:** `_verify_db_url_matches_fr()` reescribe `database.py` en disco (Oracle→PostgreSQL).
- **S84-C:** Template `auth/models.py` con `UserORM` + `TokenResponse` + `LoginRequest`.
- **S84-F:** `_ensure_auth_models_task()` — inyecta `TASK-INFRA-AUTH-MODELS`.
- **S84-G:** S65-A skip `oracledb` (ya mockeado por S70-C en conftest.py).
- 16 tests nuevos en `test_s84.py`. **1505 tests PASS**.
- **Ciclo `e98bf96e`:** 5m 38s, 109k tokens. ORM naming consistente ✅.

## S83 (2026-04-28)

- **S83-E:** `_ensure_auth_login_task()` — inyecta `TASK-INFRA-AUTH-ROUTER`.
- **S83-F:** Topological sort (Kahn's algorithm) + context injection entre tareas dependientes.
- 17 tests nuevos en `test_s83.py`. **1478 tests PASS**.
- **Ciclo `4798c9db`:** 18m 32s, QA 50, 264k tokens.

## S80 (2026-04-28)

- **S80-A:** `_verify_orm_class_names()` — detecta manifest vacío (solo Pydantic, sin ORM).
- **S80-B:** `_verify_db_url_matches_fr()` sin restricción `retry_round==0`.
- **S80-C:** `_fix_declarative_base_import()` — `Base = declarative_base()` → `from src.database import Base`.
- **S80-D:** `auth_router` en `_ensure_fastapi_main_task()`.
- **S80-E:** Caps reducidos: `{"high": 8, "critical": 10}`.
- 20 tests nuevos en `test_s80.py`. **1429 tests PASS**.

## S79 (2026-04-28)

- **S79-A:** `_verify_orm_class_names(work_dir)` — AST manifest + detección de inconsistencias.
- **S79-B:** Template CRUD completo + tabla canónica ORM (`ContractORM`, `BenefitORM`, `UserORM`).
- **S79-C:** `_verify_db_url_matches_fr()` — detecta Oracle URL en FR PostgreSQL.
- **S79-D:** Nota obligatoria login_user consulta BD.
- 19 tests nuevos en `test_s79.py`. **1409 tests PASS**.

## S78 (2026-04-28)

- **S78-A:** Template login JWT completo — JWT real, no stub.
- **S78-B:** `_verify_no_stub_endpoints(work_dir)`.
- **S78-C:** Regla CRUD en service.py — tabla canónica.
- **S78-D:** Extracción de archivos fallidos en retry.
- **Fix S70-C:** `_mock_oracledb.version = '8.3.0'`.
- 18 tests nuevos en `test_s78.py`. **1390 tests PASS**.
- **Ciclo `88d06e0f`:** 13m 18s, QA 67/100, pytest exit 2 × 2 rondas.

## S77 (2026-04-28)

- **S77-A:** `_fix_sqlalchemy_oracle_params()` — elimina `thick=True/False` de `create_engine()`.
- **S77-B:** `_fix_pydantic_decorator_order()` — reordena `@field_validator` antes de `@classmethod`.
- **S77-C:** `_verify_main_includes_routers()`.
- **S77-F:** fix auth BD errors (psycopg.OperationalError, UndefinedColumn).
- 22 tests nuevos en `test_s77.py`. **1372 tests PASS**.
- **Ciclo `fb7bbbd5`:** ~11 min, QA 57/100, pytest exit 2 × 3 rondas.

## S76 (2026-04-28)

- **Cambio de modelo SDD:** `ovd-arch-assistant` → `qwen3-coder:30b`.
- **Causa raíz:** `ovd-arch-assistant` tenía `num_predict=1024` baked-in — un SDD completo necesita ~3,700 tokens.
- **Ciclo `c0e2e71e`:** QA 93/100, SDD compliance True, 12 tareas, 13 archivos, ~13 min, $0.

## S75 (2026-04-27)

- **S75-A:** `_fix_function_import_shadowing()` — elimina wrappers triviales que causan RecursionError.
- **S75-B/C:** Templates: requirements.txt completo + regla imports de submódulos.
- **Ciclo `782bd4b1`:** 6m 3s, QA 50 — expuso bug raíz del modelo con `num_predict=1024`.

## S70 (2026-04-27)

- **S70-A:** `session_create` dispara `asyncio.create_task(_run_graph_background(...))` — grafo inicia sin SSE.
- **S70-B:** `_ensure_fastapi_main_task()` — solo `include_router()` para módulos con `router.py` en SDD.
- **S70-C:** `run_tests` — detecta `import oracledb` → inyecta mock en conftest.py antes de pytest.
- **S70-D/E:** Templates: prohibición auto-import circular + JWT library única.
- 14 tests nuevos en `test_s70.py`. **Ciclo `0209baf4`:** ~10 min, QA 60.

## S69 (2026-04-27)

- **S69-A:** `_ensure_fastapi_main_task()` — inyecta `TASK-INFRA-MAIN` si FR menciona FastAPI.
- **S69-B:** `system_sdd.md` — tabla VERIFICACIÓN OBLIGATORIA al inicio.
- **S69-C:** Auto-genera `src/main.py` mínimo cuando import roto es `src.main`.
- 13 tests nuevos en `test_s69.py`. **1221 tests PASS**.
- **Ciclo `e3888513`:** 6m 54s, QA 95/100 ✅, src/main.py generado ✅.

## S68 (2026-04-27)

- **S68-A:** `_is_s65a_output` — preserva `last_test_error` para S66-C.
- **S68-B:** `_extract_import_corrections()` — inyecta `→ CORRECCIÓN:` al inicio del HumanMessage.
- **S68-C:** `_is_infra_task()` — infra fuera del cap de complejidad.
- **S68-D:** Template RUT: `format_rut()`, `require_valid_rut()`, UNIQUE constraint.
- 16 tests nuevos en `test_s68.py`. **1208 tests PASS**.

## S67 (2026-04-27)

- **S67-B:** Cap dinámico por complejidad: `{low:5, medium:8, high:10, critical:12}`.
- **Ciclo `b3de3b92`:** 22m 4s, QA 60, 12 archivos. Primer ciclo con `directory` correcto.
- S65-A ✅ y S66-A ✅ validados en producción. S66-C ❌ bug fix en S68-A.

## S66 (2026-04-27)

- **S66-A:** `_validate_artifacts_imports()` — mapa `export_name → módulo` + correcciones exactas.
- **S66-B:** Cap post-procesamiento 5 tareas/agente en `generate_sdd`.
- **S66-C:** Loop detection en `run_tests` — si mismo feedback × 2 rondas → `goto=generate_docs`.
- 10 tests nuevos en `test_s66.py`. **1192 tests PASS**.

## S65 (2026-04-27)

- **S65-A:** `_validate_artifacts_imports()` — `ast.parse()` + `importlib.util.find_spec()` antes de pytest.
- **S65-B:** `_validate_orm_patterns()` — detecta `db.add(PydanticModel(...))`.
- **S65-C:** `_check_fastapi_route_ordering()` — detecta rutas parametrizadas antes de estáticas.
- **S65-D:** `_ensure_auth_dependencies()` — auto-genera `src/auth/dependencies.py`.
- **S65-E:** `_ensure_python_infrastructure()` — auto-crea `requirements.txt`.

## S61 (2026-04-26)

- **S61-A:** `pythonpath = .` en templates. S27-A skip si ya existe.
- **S61-B:** `last_test_error: str` sin truncar en `OVDState`.
- **S61-C:** `qa_review` retorna resultado previo en retries selectivos.
- **S61-D:** `_kept_agent_results` — preserva resultados de agentes no-retried.
- 13 tests nuevos en `test_s61.py`. **1138 tests PASS**.

## S55 (2026-04-26)

- **S55-A:** `_log_runner_response()` → `log.warning`.
- **S55-B:** `_write_artifacts()` con `preserve_nonempty=True` — previene sobreescritura destructiva.
- **S55-C:** Hint `round()` en tareas de tests.
- **S55-D:** `update_test_retry` → `log.warning`.
- **Ciclo `9d939f29`:** **1m 35s**, **pytest exit 0** (primer éxito histórico), 30k tokens.

## S51–S52 (2026-04-25)

- **S51-A:** Detección de tarea de tests por keywords + `[PRIORIDAD MÁXIMA]`.
- **S51-B:** Template: `tests/test_<paquete>.py` obligatorio.
- **S51-C:** Retry automático si tarea de tests ausente en artifacts.
- **Fix `.env`:** `ANTHROPIC_API_KEY` separado del comentario inline.
- **Ciclo `8f04d629`:** 5m 04s, `tests/test_imc.py` generado, pytest exit 2.

## S49–S50 (2026-04-25)

- **S49-A:** Switch inmediato a runner cuando `iter=0` y `tool_calls=[]`.
- **S49-B/C:** Cap 5 tareas/agente + detección modelos Ollama.
- **S50-A:** `_write_artifacts()` en paths S49-A/S49-C.
- **S50-B:** Deduplicación de artefactos por path.
- **S50-C/D:** Templates Pydantic v2 + regla floats.
- **Ciclo S49:** **1m 18s** (vs ~56 min en S48).

## S47–S48 (2026-04-25)

- **S47-A:** Background `asyncio.Task` para el grafo — sobrevive desconexión SSE.
- **S47-B:** Registro temprano ciclos: `status='started'` → `'failed'` → `'completed'`.
- **Migración BD:** columna `status` + UNIQUE index en `ovd_cycles(thread_id)`.
- **S48-A:** Security bypass con `OVD_SECURITY_MIN_SCORE=0`.
- **S48-B/C/D:** Templates + logging.
- **Fix DB:** `ALTER TABLE ovd_refresh_tokens ADD COLUMN IF NOT EXISTS revoked_reason TEXT`.

## S40 (2026-04-23)

- **S40-A:** `system_sdd.md` — máx tareas, tests obligatorios, prohibición scaffold-only.
- **S40-B:** `system_backend.md` — validación RUT completa.
- **S40-C:** `system_frontend.md` — tests Vitest + hooks obligatorios.
- **Nivel1-E:** Fix security bypass (`_SECURITY_MIN_SCORE == 0`).
- **`.env`:** `OVD_SSE_STREAM_TIMEOUT_SECS=3600`, `OVD_NODE_TIMEOUT_SECS=1200`.

## S38 (2026-04-22)

- **S38-A:** `await tool_fn.ainvoke(args)` con fallback a sync — fix context7 StructuredTool.
- **S38-B:** `qa_review` trunca a 20k chars (antes 12k).
- 10 tests nuevos. **764 tests PASS**.

## S37 (2026-04-22)

- **S37-A:** `audit_logger` bigint fix — remover `id` del INSERT.
- **S37-B:** `_generate_delivery_report` retorna ruta absoluta.
- 7 tests nuevos. **Ciclo `474f6d72`:** Security 100, QA 68, Tests 28/28 ✅.

## S36 (2026-04-22)

- **S36-A:** `QAReviewOutput` field_validator — convierte `str` → `list[str]` por líneas (no char a char).
- **S36-B:** Template: `round()` en valores float de tests.
- 13 tests nuevos. **747 tests PASS**.

## S35 (2026-04-22)

- **S35:** `FrLauncher.tsx` — persiste proyecto en `localStorage('ovd_last_project')`.
- Warning en API cuando `directory=""`.

## S34 (2026-04-22)

- **S34-A:** Detección de error repetido en `update_test_retry`.
- **S34-B:** `_extract_failed_test_blocks` — bloques `FAILED` al inicio del feedback.
- 14 tests nuevos. **734 tests PASS**.

## S33 (2026-04-22)

- **S33-A:** Instrucción "no modificar tests" en retry feedback.
- **S33-B:** Extracción AssertionError al inicio del feedback.
- **S33-C:** `--tb=long` en rondas de retry.
- 15 tests nuevos. **720 tests PASS**.

## S32 (2026-04-22)

- **S32-A:** `run_tests` — 3 casos por disponibilidad de test files.
- **S32-B:** Template orden de escritura `← PRIMERO / SEGUNDO / TERCERO / CUARTO`.
- **S32-C:** Diagnóstico ImportError → `[DIAGNÓSTICO S32-C]` en feedback.
- 16 tests nuevos. **705 tests PASS**.

## S31 (2026-04-22)

- **S31-A:** Filtro mtime en `qa_review` y `security_audit`.
- **S31-B:** Cap `retry_feedback` a 3000 chars.
- **S31-C:** `run_tests` — target solo archivos del ciclo actual por mtime.
- 9 tests nuevos. **696 tests PASS**.

## S30 (2026-04-22)

- **S30-A:** `write_file` dirname guard.
- **S30-B:** Warning en tool failure.
- **S30-C:** Instrucción de subdirectorios en `human_content`.
- **S30-D:** Compresión de mensajes — últimos 8 (`_MAX_HIST=8`).
- **S30-E:** `cycle_start_ts: float` en `OVDState`.
- 11 tests nuevos. **687 tests PASS**.

## S28 (2026-04-22)

- **S28-A:** `system_sdd.md` — tabla tipo de tarea → agente correcto.
- **S28-C:** Exit codes pytest diferenciados (exit 2/4/5).
- 9 tests nuevos. **666 tests PASS**.

## S27 (2026-04-22)

- **S27-A:** `run_tests` — inyecta conftest.py con `sys.path.insert(0, "src")`.
- **S27-B:** `audit_logger` — `json.dumps({...})` para campo JSONB.
- **S27-C:** `_index_delivery_report` — `sys.path.insert` antes del import knowledge.
- **S27-D:** `system_qa.md` — no penaliza diferencias menores de infraestructura.
- 9 tests nuevos. **657 tests PASS**.

## S26 (2026-04-22)

- **S26-A:** Template prohibición `__init__.py` en raíz del workspace.
- **S26-B:** `run_tests` — `cwd=work_dir` + `--rootdir` + `--import-mode=importlib`.
- **S26-C:** `security_audit` filesystem-first.
- 9 tests nuevos. **648 tests PASS**.

## S25 (2026-04-22)

- **S25-A:** `run_tests` usa `sys.executable` en lugar de `"python"`.
- **Resultado ciclo S25:** Security 100, QA 95, pytest ejecuta real, retry loop funcional.

## S23–S24 (2026-04-22)

- **S24:** `_scan_workspace_artifacts()` + filesystem-first en runner/QA/deliver.
- **S23:** `deliver` S23-A + `_detect_test_runner` S23-B + `qa_review` filesystem-first.
- **Diagnóstico `artifacts=[]`:** `tool_result` no str puro → tracking falla silenciosamente.

## S22 (2026-04-21)

- Nodo `run_tests`: pytest/vitest/cargo, timeout 60s, retry 2 rondas.
- Security scan CLI: semgrep, gitleaks, pip-audit.
- Nodo `generate_docs`: README/OpenAPI/ADR/CHANGELOG.
- Grafo actualizado: `qa_review → run_tests → generate_docs → deliver`.

## S21 (sesión anterior)

- Nodo `describe_image`: visión multimodal para wireframes.
- Dashboard approval panel: feedback, revise, adjunto, exportar SDD.

## S19 (2026-04-17)

- Tests Block C (Vitest, 34 tests), D (Docker smoke, 5), E (Rust inline, 26).
- CORS configurable vía `OVD_CORS_ORIGINS`.
- RAG multi-provider: openai|ollama.
- `docs/ROADMAP.md` → v0.9.0-quality-docs.
