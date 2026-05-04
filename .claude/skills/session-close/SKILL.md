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

## Paso 8 — Registrar sesión en skills-log.md

Este paso se ejecuta siempre, independientemente de si se hizo push.

### 8a. Calcular duración

```bash
if [ -f .claude/session-active.md ]; then
  source .claude/session-active.md
  END=$(date +%s)
  DURATION_SECS=$((END - START))
  DURATION_MIN=$((DURATION_SECS / 60))
  HOURS=$((DURATION_MIN / 60))
  MINS=$((DURATION_MIN % 60))
  END_TIME=$(date '+%H:%M')
  START_TIME_READABLE=$(date -d "@$START" '+%H:%M' 2>/dev/null || date -r "$START" '+%H:%M')
  echo "Duración: ${HOURS}h ${MINS}m"
fi
```

### 8b. Preguntar fricción

Hacer UNA pregunta al usuario:

> "Fricción percibida hoy (1=mucha fricción, 5=ninguna fricción): ?"

Esperar respuesta numérica (1–5). Si no responde, usar "—".

### 8c. Detectar skills utilizados en la sesión

Revisar si se invocaron los skills en esta sesión (inferir desde el resumen `$resumen` y el contexto):
- `/session-start` — siempre sí si llegamos al cierre
- `/run-tests` — sí si se ejecutaron tests con el skill
- `/pre-push` — sí si se ejecutó el gate pre-push
- `/session-close` — siempre sí (estamos aquí)

### 8d. Obtener estado de gates CI (del Paso 1 y Paso 2)

Usar los resultados de ruff y pytest ya ejecutados arriba.

### 8e. Calcular número de sesión

```bash
SESION_NUM=$(grep -c "^## S[0-9]" .claude/skills-log.md 2>/dev/null || echo 0)
SESION_NUM=$((SESION_NUM + 1))
SESION_ID=$(printf "S%03d" $SESION_NUM)
```

### 8f. Escribir entrada en skills-log.md

Agregar al final de `.claude/skills-log.md` (después de la última entrada):

```markdown
## {SESION_ID} | {DATE}

| Métrica | Valor |
|---|---|
| Inicio | {START_TIME} |
| Cierre | {END_TIME} |
| Duración | ~{HOURS}h {MINS}m |
| Sprint | {SPRINT} |
| Branch | dev |
| Fricción (1=mucha 5=ninguna) | {FRICTION_SCORE} |

### Skills utilizados
- [x] /session-start
- [x/ ] /run-tests ×N
- [x/ ] /pre-push
- [x] /session-close

### Gates CI (pre-push)
- [x/ ] ruff lint: PASS/FAIL
- [x/ ] ruff format: PASS/FAIL
- [x/ ] pytest unit: N passed
- [x/ ] OVD conventions: PASS/FAIL
- Push ejecutado: SÍ/NO | Fallos CI post-push: 0

### Completado hoy
{$resumen}

### Notas

```

### 8g. Limpiar sesión activa

```bash
rm -f .claude/session-active.md
```

## Paso 9 — Re-indexar RAG (archivos modificados)

> Aplica a partir de S96-H. No requiere el engine activo — usa rag.py directamente.

### 9a. Identificar archivos modificados en la sesión

```bash
git diff --name-only HEAD | grep -E "^src/engine/.*\.py$|^docs/.*\.md$"
```

Si no hay archivos modificados → omitir el paso.

### 9b. Re-indexar archivos Python de src/engine/

Por cada archivo `.py` modificado en `src/engine/` (excluyendo `tests/` y `.venv/`):

```bash
cd src/engine && .venv/bin/python scripts/rag_bootstrap.py \
  --org-id 01KMK160F1TJ807Z0BDSJD504D \
  --project-id ovd-platform \
  --path "<ruta-absoluta-del-archivo>" \
  --doc-type codebase
```

### 9c. Re-indexar archivos Markdown de docs/

Por cada archivo `.md` modificado en `docs/`:

```bash
cd src/engine && .venv/bin/python scripts/rag_bootstrap.py \
  --org-id 01KMK160F1TJ807Z0BDSJD504D \
  --project-id ovd-platform \
  --path "<ruta-absoluta-del-archivo>" \
  --doc-type doc
```

Reportar: `RAG actualizado — N archivos re-indexados (M codebase + K docs)`

> **Nota:** Este paso usa re-indexación incremental (archivo a archivo) vía `rag_bootstrap.py`.
> Para re-bootstrap completo: `python scripts/rag_bootstrap.py --org-id ... --project-id ... --clear`
