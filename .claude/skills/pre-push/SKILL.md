---
name: pre-push
description: >
  Ejecuta la misma validación que CI de GitHub Actions antes de hacer push:
  lint ruff, format check, tests unit, y convenciones OVD (settings.py,
  imports). Solo confirma push si todos los gates pasan. Invocar antes de
  cada git push.
allowed-tools: Bash(ruff *) Bash(python -m pytest *) Bash(git *) Bash(grep *) Read
disable-model-invocation: true
---

# Validación pre-push OVD Platform

> IMPORTANTE: `disable-model-invocation: true`
> Solo el desarrollador invoca este skill. Claude nunca lo dispara solo.
> El push solo se ejecuta si el usuario confirma después de que TODOS los gates pasan.

Ejecuta los 4 gates en orden. El primero que falle detiene la validación.

---

## Gate 1 — Ruff lint (espeja CI job `engine-lint`)

```bash
cd src/engine && .venv/bin/ruff check . --no-fix --output-format=concise
```

**PASS:** Sin errores (exit 0)
**FAIL:** Mostrar errores, detenerse. No ejecutar Gate 2.

---

## Gate 2 — Ruff format check (espeja CI job `engine-lint`)

```bash
cd src/engine && .venv/bin/ruff format --check . 2>&1
```

**PASS:** "All checks passed" o sin output (exit 0)
**FAIL:** Mostrar archivos con diferencias. Ofrecer auto-fix:
```bash
cd src/engine && .venv/bin/ruff format .
```
Después del fix, re-ejecutar Gate 2 para confirmar.

---

## Gate 3 — Tests unit (espeja CI job `engine-test`)

```bash
cd src/engine && .venv/bin/python -m pytest tests/ \
  -m "not integration and not e2e and not docker" \
  -q --tb=line \
  --ignore=tests/test_alembic_migrations.py \
  -k "not test_cycle_start_ts_reciente and not test_usa_cap_800_en_truncate \
      and not test_dispatch_frontend_despacha_pendientes \
      and not test_write_artifacts_overwrites_when_new_content_larger \
      and not test_s63b_cleanup_not_in_run_tests" \
  2>&1 | tail -5
```

**PASS:** "N passed" sin fallos nuevos
**FAIL:** Mostrar traceback completo del fallo nuevo. Detenerse. No continuar al Gate 4.

---

## Gate 4 — Convenciones OVD (verificación específica del proyecto)

### 4A — Sin regresiones en migración settings.py
```bash
grep -rn "os\.environ\.get" src/engine/ \
  --include="*.py" \
  --exclude-dir=tests \
  --exclude-dir=.venv \
  --exclude-dir=migrations \
  | grep -v "api_key_env\|\"PATH\"\|# legacy\|config\.api_key_env" \
  | grep -v "^src/engine/api\.py\|^src/engine/main\.py"
```

**PASS:** Sin output (0 matches)
**WARN:** Mostrar líneas encontradas. Preguntar si es intencional antes de continuar.
Nota: `api.py` y `main.py` tienen usos legítimos de `os.environ.get` — están excluidos.

### 4B — Sin imports directos de exceptions suprimidos incorrectamente
```bash
grep -rn "except Exception:" src/engine/ \
  --include="*.py" \
  --exclude-dir=tests \
  --exclude-dir=.venv \
  | grep -v "# noqa\|# S110\|fallback\|fire-and-forget\|best.effort" \
  | head -10
```

**PASS:** Sin output o solo falsos positivos documentados
**WARN:** Mostrar resultados y recordar usar excepciones específicas de OVD (`OVDTokenError`, `OVDConfigError`, etc.)

---

## Reporte final

Si todos los gates pasan:

```
✓ Gate 1: Ruff lint        PASS
✓ Gate 2: Ruff format      PASS
✓ Gate 3: Tests unit       PASS (1542 passed, 5 known excluded)
✓ Gate 4: OVD conventions  PASS

LISTO PARA PUSH. ¿Confirmas? (responde 'sí' para ejecutar git push origin dev)
```

Si el usuario confirma:
```bash
git push origin dev
```

Si algún gate falla:
```
✗ Gate N: [nombre]  FAIL
[detalle del fallo]

PUSH BLOQUEADO. Corrige los errores antes de continuar.
```

---

## Referencia rápida — comandos CI equivalentes

| Gate pre-push | Job CI GitHub Actions |
|---|---|
| ruff check | `engine-lint` (step 1) |
| ruff format --check | `engine-lint` (step 2) |
| pytest unit | `engine-test` |
| OVD conventions | No tiene equivalente en CI (específico del proyecto) |
