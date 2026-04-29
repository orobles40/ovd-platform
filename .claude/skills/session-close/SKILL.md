---
name: session-close
description: >
  Cierra la sesión de desarrollo: lint, tests unit, actualiza CONTEXT.md y
  CURRENT.md, genera commit siguiendo la convención del proyecto y solicita
  confirmación explícita antes de push. Usar al final de cada sesión.
argument-hint: "[descripción breve del trabajo realizado hoy]"
arguments: [resumen]
allowed-tools: Bash(ruff *) Bash(python -m pytest *) Read Write Edit Bash(git *) Bash(grep *)
disable-model-invocation: true
---

# Cierre de sesión OVD Platform

> IMPORTANTE: Este skill tiene `disable-model-invocation: true`.
> Solo el desarrollador puede invocarlo. Claude nunca lo dispara automáticamente.
> Nunca hacer push sin confirmación explícita del usuario.

Al invocar, ejecuta estos pasos en orden. Detente si alguno falla.

## Paso 1 — Lint

```bash
cd src/engine && .venv/bin/ruff check . --no-fix
```

Si hay errores → mostrarlos y detenerse. No continuar al paso 2.

```bash
cd src/engine && .venv/bin/ruff format --check .
```

Si hay diferencias de formato → ejecutar auto-fix:
```bash
cd src/engine && .venv/bin/ruff format .
```

## Paso 2 — Tests unit rápidos

```bash
cd src/engine && .venv/bin/python -m pytest tests/ \
  -m "not integration and not e2e and not docker" \
  -q --tb=line \
  --ignore=tests/test_alembic_migrations.py \
  -k "not test_cycle_start_ts_reciente and not test_usa_cap_800_en_truncate and not test_dispatch_frontend_despacha_pendientes and not test_write_artifacts_overwrites_when_new_content_larger and not test_s63b_cleanup_not_in_run_tests" \
  2>&1 | tail -10
```

Si hay fallos nuevos (no pre-existentes) → mostrar y detenerse. No commitear con tests rotos.

## Paso 3 — Verificación convenciones OVD

```bash
grep -rn "os\.environ\.get" src/engine/ \
  --include="*.py" \
  --exclude-dir=tests \
  --exclude-dir=.venv \
  | grep -v "api_key_env\|PATH\|# legacy" \
  | grep -v "api\.py\|main\.py"
```

Si hay resultados → advertir: "Posible regresión en migración settings.py". Mostrar las líneas y pedir confirmación para continuar.

## Paso 4 — Actualizar CONTEXT.md

Lee `.claude/CONTEXT.md` actual y actualiza las secciones dinámicas:
- `Última sesión`: fecha de hoy (2026-04-28) + resumen del argumento `$resumen`
- `Próxima sesión`: primera tarea pendiente según CURRENT.md
- Si se corrigió algún fallo pre-existente → removerlo de la lista

Luego actualiza `docs/sprints/CURRENT.md` si hubo cambios de estado en tareas del sprint.

## Paso 5 — Decisión técnica del día (opcional)

Pregunta: "¿Tomaste alguna decisión técnica hoy que deba quedar registrada en docs/DECISIONS.md?"

Si la respuesta es sí → agregar al archivo con formato:
```
## [fecha] [tema breve]
**Decisión:** [qué se decidió]
**Razón:** [por qué]
```

Si no existe `docs/DECISIONS.md` → crearlo con esa primera entrada.

## Paso 6 — Generar commit

```bash
git status --short
git diff --stat
```

Genera el mensaje de commit siguiendo la convención del proyecto:
- Prefijo: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`
- Máximo 72 caracteres en la primera línea
- Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>

Muestra el mensaje propuesto y espera confirmación antes de ejecutar:

```bash
git add [archivos relevantes]
git commit -m "$(cat <<'EOF'
[mensaje generado]

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

## Paso 7 — Push (requiere confirmación explícita)

NO ejecutar push automáticamente. Preguntar:

> "¿Deseas hacer push a origin/dev? (responde 'sí' para confirmar)"

Solo si el usuario confirma explícitamente:
```bash
git push origin dev
```
