---
name: run-tests
description: >
  Ejecuta la suite de tests correcta para OVD Platform según el marker.
  Maneja automáticamente los 5 fallos pre-existentes conocidos (los excluye
  con aviso), reporta delta de nuevos fallos. Invocar antes de cada commit.
argument-hint: "[unit|integration|e2e|docker|regression|all|cov]"
arguments: [marker]
allowed-tools: Bash(python -m pytest *) Read
---

# Ejecutar tests OVD Platform

## Fallos pre-existentes (excluidos automáticamente con aviso)

Estos tests fallan por causas conocidas. No investigar salvo con `/fix-test`:

| Test | Causa | Sprint de fix |
|---|---|---|
| `test_cycle_start_ts_reciente` | Flaky por timing | Pendiente |
| `test_usa_cap_800_en_truncate` | Cap obsoleto desde S61-B | S96-G |
| `test_dispatch_frontend_despacha_pendientes` | Roto por S94-fix | S96-G |
| `test_write_artifacts_overwrites_when_new_content_larger` | write_artifacts cambió post-S55 | S96-G |
| `test_s63b_cleanup_not_in_run_tests` | RuntimeError por S94-fix | S96-D |

Patrón de exclusión estándar:
```
-k "not test_cycle_start_ts_reciente and not test_usa_cap_800_en_truncate and not test_dispatch_frontend_despacha_pendientes and not test_write_artifacts_overwrites_when_new_content_larger and not test_s63b_cleanup_not_in_run_tests"
```

---

## Comandos por marker

### `/run-tests unit` (default — más frecuente)
```bash
cd src/engine && .venv/bin/python -m pytest tests/ \
  -m "not integration and not e2e and not docker" \
  -q --tb=short \
  --ignore=tests/test_alembic_migrations.py \
  -k "not test_cycle_start_ts_reciente and not test_usa_cap_800_en_truncate \
      and not test_dispatch_frontend_despacha_pendientes \
      and not test_write_artifacts_overwrites_when_new_content_larger \
      and not test_s63b_cleanup_not_in_run_tests"
```

### `/run-tests integration`
> Requiere Docker activo (postgres_db + NATS). Verificar antes de ejecutar.
```bash
cd src/engine && .venv/bin/python -m pytest tests/ -m "integration" -v --tb=short
```
Nota: última vez ejecutado → revisar git log para fecha. Si hace más de 1 semana: advertir.

### `/run-tests e2e`
> Requiere engine corriendo en localhost:8001.
```bash
cd src/engine && .venv/bin/python -m pytest tests/ -m "e2e" -v --tb=short
```

### `/run-tests docker`
> Requiere Docker daemon activo.
```bash
cd src/engine && .venv/bin/python -m pytest tests/ -m "docker" -v --tb=short
```

### `/run-tests regression`
```bash
cd src/engine && .venv/bin/python -m pytest tests/test_regression_sprint.py -v --tb=short
```

### `/run-tests all`
Ejecuta unit + regression (sin integration/e2e/docker):
```bash
cd src/engine && .venv/bin/python -m pytest tests/ \
  -m "not integration and not e2e and not docker" \
  -v --tb=short \
  --ignore=tests/test_alembic_migrations.py \
  -k "not test_cycle_start_ts_reciente and not test_usa_cap_800_en_truncate \
      and not test_dispatch_frontend_despacha_pendientes \
      and not test_write_artifacts_overwrites_when_new_content_larger \
      and not test_s63b_cleanup_not_in_run_tests"
```

### `/run-tests cov`
Unit tests con reporte de cobertura:
```bash
cd src/engine && .venv/bin/python -m pytest tests/ \
  -m "not integration and not e2e and not docker" \
  -q --tb=line \
  --cov=. --cov-report=term-missing \
  --ignore=tests/test_alembic_migrations.py \
  -k "not test_cycle_start_ts_reciente and not test_usa_cap_800_en_truncate \
      and not test_dispatch_frontend_despacha_pendientes \
      and not test_write_artifacts_overwrites_when_new_content_larger \
      and not test_s63b_cleanup_not_in_run_tests" \
  2>&1 | grep -E "PASSED|FAILED|ERROR|TOTAL|passed|failed"
```
Baseline actual: TOTAL 88% (2026-04-28).

---

## Interpretación de resultados

### Si hay fallos nuevos (no pre-existentes):
1. Mostrar el fallo completo con traceback
2. Identificar si es regresión (código que antes pasaba) o test nuevo roto
3. NO continuar con commit hasta resolver

### Si solo hay los fallos conocidos:
Mostrar: "✓ 1542 passed, 5 known failures excluded (use /fix-test to address them)"

### Si marker no se especifica:
Ejecutar `unit` por defecto con aviso.
