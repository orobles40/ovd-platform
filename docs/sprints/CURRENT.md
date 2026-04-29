# Sprint activo — S96

> Última actualización: 2026-04-28 | Rama: `dev`
> Skills Fase 1 implementados: session-start, session-close, run-tests, pre-push

## Estado del ciclo de validación

| Ciclo | Hash | S65-A | pytest | Bloqueador |
|-------|------|-------|--------|------------|
| S94 | 5a17c6a2 | **pasa** | **9 items / 1 error** | S63-B borraba src/ — **RESUELTO** |
| S95 | 65ab6e7b | bloquea | no ejecuta | `prime_validator` import espurio |

**Hito alcanzado:** S94 fue el primer ciclo con `collected 9 items / 1 error` — pytest ejecutó código real.

**Bloqueador actual:** `from src.utils.prime_validator import is_prime` en `contracts/service.py` — el LLM contamina con contexto del proyecto IMC anterior. Fix: S96-B.

---

## Roadmap S96

### S96-A — Auto-generador general de stubs (CRÍTICO)

En `_validate_artifacts_imports`, reemplazar los casos individuales S89-A/S90-A/S91-A por un mecanismo general: cuando S65-A detecta `src.X.Y ← módulo no existe`, generar automáticamente un stub mínimo `src/X/Y.py` con exports vacíos derivados del import statement.

**Impacto esperado:** cualquier módulo local faltante se auto-genera sin código adicional.

### S96-B — Filtro de imports espurios de proyectos anteriores (CRÍTICO)

En `code_postprocessor.py`, agregar `_fix_spurious_utility_imports()` que elimina imports de módulos que no pertenecen al dominio actual:
- `src.utils.prime_validator`
- `src.utils.imc_validator`
- `src.calculadora.*`

**Causa raíz:** el LLM mezcla contexto de proyectos anteriores (calculadora IMC) con el proyecto actual (contratos).
**Fix:** regex que elimina esas líneas de import de `service.py` y `router.py`.

### S96-C — Postprocessor ORM naming español→inglés (ALTO)

`_fix_orm_class_names_es_to_en()` en `code_postprocessor.py`:

| Nombre español (prohibido) | Nombre inglés (correcto) |
|---------------------------|--------------------------|
| `ContratoORM` | `ContractORM` |
| `BeneficioORM` | `BenefitORM` |
| `UsuarioORM` | `UserORM` |

S79-B (template) no es suficiente — el LLM sigue generando nombres en español. El postprocessor lo corrige determinísticamente con `re.sub()`.

### S96-F — Fix POST /auth/login → 500 (CRÍTICO — PRIORIDAD S96)

**Decisión 2026-04-28:** Priorizado antes de S96-D y S96-E por bloquear el dashboard web completo.

`POST /auth/login` retorna 500 desde ciclo S75. Workaround actual: acceso vía curl + OVD_SECRET.

**Diagnóstico a realizar:**
1. Revisar `routers/auth_router.py → _get_user_by_email()` — posible error en query o en retorno
2. Revisar `auth.py → issue_tokens()` — posible error al generar el par access/refresh
3. Verificar que `ovd_users` tiene el usuario `omar@omarrobles.dev` activo en BD
4. Verificar que `DATABASE_URL` está correctamente configurada en settings

**Comando de diagnóstico rápido:**
```bash
SECRET=$(grep '^OVD_SECRET=' src/engine/.env | head -1 | sed 's/.*=//' | tr -d ' \r')
curl -v -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"omar@omarrobles.dev","password":"ovd-dev-2026"}'
```

**Criterio de aceptación:** `POST /auth/login` retorna 200 con `access_token` y `refresh_token`.

---

### S96-G — Sesión dedicada: corregir 5 fallos pre-existentes (MEDIO)

**Decisión 2026-04-28:** Asignar sesión dedicada exclusiva para estos 5 fallos. No mezclar con features.

| Test | Causa | Esfuerzo estimado |
|---|---|---|
| `test_s39::test_usa_cap_800_en_truncate` | Actualizar valor cap a post-S61-B | 15 min |
| `test_s47::test_dispatch_frontend_despacha_pendientes` | Actualizar test a lógica S94 | 30 min |
| `test_s55::test_write_artifacts_overwrites_when_new_content_larger` | Actualizar test a write_artifacts actual | 30 min |
| `test_s63::test_s63b_cleanup_not_in_run_tests` | RuntimeError — coordinar con S96-D | 45 min |
| `test_s31::test_cycle_start_ts_reciente` | Fix timing o marcar con `@pytest.mark.flaky` | 20 min |

Usar `/fix-test [nombre]` para abordar cada uno con contexto precargado.

---

### S96-D — Fix test_s63.py regresión (MEDIO)

`test_s63b_cleanup_in_retry_round_zero` espera el comportamiento pre-S94 (borra todos los archivos). Actualizar el test para reflejar la nueva lógica: si `collected \d+ items` en el error → preserva `src/`.

### S96-E — Verificación post-auto-gen (MEDIO)

Después de auto-generar archivos (S89-A/S90-A/S91-A), re-ejecutar `_validate_artifacts_imports` para verificar que los nuevos archivos resuelven los imports rotos. Actualmente se filtra el broken-list pero no se re-valida.

---

## Ciclo de validación S96

```bash
rm -rf /Users/omarrobles/Workspace/mis-entregas/contratos-beneficios/src/ \
       /Users/omarrobles/Workspace/mis-entregas/contratos-beneficios/tests/ \
       /Users/omarrobles/Workspace/mis-entregas/contratos-beneficios/conftest.py \
       /Users/omarrobles/Workspace/mis-entregas/contratos-beneficios/pytest.ini \
       /Users/omarrobles/Workspace/mis-entregas/contratos-beneficios/requirements.txt

SECRET=$(grep '^OVD_SECRET=' src/engine/.env | head -1 | sed 's/.*=//' | tr -d ' \r')
curl -s -X POST http://localhost:8001/session \
  -H "Content-Type: application/json" \
  -H "X-OVD-Secret: $SECRET" \
  -d '{
    "org_id": "ORG_OMAR_ROBLES",
    "project_id": "PROJ_CONTRATOS_BENEFICIOS",
    "feature_request": "Sistema de contratos con autenticación JWT usando RUT chileno. API REST FastAPI: login RUT+contraseña, CRUD contratos por empleado, listado de beneficios. PostgreSQL + SQLAlchemy ORM.",
    "auto_approve": true
  }'
```

**Métricas objetivo:**
- S65-A no bloquea (0 imports rotos en round 0)
- pytest ejecuta real (exit 0 o exit 1 con fallos lógicos)
- QA ≥ 70

---

## Issues abiertos

| Issue | Descripción | Estado | Sprint |
|-------|-------------|--------|--------|
| Login dashboard 500 | `POST /auth/login` retorna 500 | **PRIORITARIO** | S96-F |
| test_s63b regresión | `test_s63b_cleanup_in_retry_round_zero` roto por S94-fix | Pendiente | S96-D |

## Fallos pre-existentes — pendientes de corrección en S96-G

> Estos fallos tienen sesión dedicada asignada (S96-G). No son permanentes.
> Usar `/fix-test [nombre]` con contexto precargado.

| Test | Causa | Prioridad |
|---|---|---|
| `test_s31::test_cycle_start_ts_reciente` | Flaky por timing | Media |
| `test_s39::test_usa_cap_800_en_truncate` | Cap obsoleto desde S61-B | Alta (fácil) |
| `test_s47::test_dispatch_frontend_despacha_pendientes` | Roto por S94-fix | Alta |
| `test_s55::test_write_artifacts_overwrites_when_new_content_larger` | write_artifacts cambió post-S55 | Alta |
| `test_s63::test_s63b_cleanup_not_in_run_tests` | RuntimeError por S94-fix | Alta |

## Skills Claude Code

| Fase | Skills | Estado | Fecha |
|---|---|---|---|
| Fase 1 | session-start, session-close, run-tests, pre-push | ✅ Implementados | 2026-04-28 |
| Fase 2 | tdd-cycle, tdd-green, cycle-debug, fix-test | ⏳ Evaluar en 2026-05-12 | — |

> **Nota:** Evaluar impacto de Fase 1 el **2026-05-12** (2 semanas). Si los 4 skills reducen
> fricción mediblemente, proceder con Fase 2. Criterio: ¿sesiones inician más rápido?
> ¿CI falla menos post-push? ¿CONTEXT.md se mantiene actualizado?
