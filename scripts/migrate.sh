#!/usr/bin/env bash
# OVD Platform — Script de migracion incremental PostgreSQL
# Copyright 2026 Omar Robles
#
# Aplica las migraciones OVD en orden, saltando las ya aplicadas.
# Registra cada migracion en la tabla ovd_migrations para idempotencia.
#
# Uso:
#   ./scripts/migrate.sh                         # aplica todas las pendientes
#   ./scripts/migrate.sh --dry-run               # muestra que se aplicaria sin ejecutar
#   ./scripts/migrate.sh --rls                   # aplica migraciones + RLS policies
#   ./scripts/migrate.sh --status                # muestra estado de cada migracion
#   DATABASE_URL=postgres://... ./scripts/migrate.sh
#
# Variables de entorno:
#   DATABASE_URL  — URL de conexion PostgreSQL (requerida)
#   PGPASSWORD    — password (alternativa a incluirlo en DATABASE_URL)

set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MIGRATIONS_DIR="${REPO_ROOT}/packages/opencode/migration-ovd"
RLS_FILE="${REPO_ROOT}/infra/postgres/rls.sql"
RAG_FILE="${REPO_ROOT}/infra/postgres/rag.sql"

DRY_RUN=false
APPLY_RLS=false
SHOW_STATUS=false

# ---------------------------------------------------------------------------
# Parse args
# ---------------------------------------------------------------------------

for arg in "$@"; do
  case "$arg" in
    --dry-run)   DRY_RUN=true ;;
    --rls)       APPLY_RLS=true ;;
    --status)    SHOW_STATUS=true ;;
    --help|-h)
      echo "Uso: $0 [--dry-run] [--rls] [--status]"
      exit 0
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Validar DATABASE_URL
# ---------------------------------------------------------------------------

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL no configurada."
  echo "Exporta la variable: export DATABASE_URL=postgres://user:pass@host:5432/dbname"
  exit 1
fi

# ---------------------------------------------------------------------------
# Helper: ejecutar SQL
# ---------------------------------------------------------------------------

run_sql() {
  psql "$DATABASE_URL" --no-psqlrc -v ON_ERROR_STOP=1 "$@"
}

run_sql_file() {
  local file="$1"
  if [[ "$DRY_RUN" == true ]]; then
    echo "  [DRY-RUN] Se aplicaria: $file"
    return 0
  fi
  psql "$DATABASE_URL" --no-psqlrc -v ON_ERROR_STOP=1 -f "$file"
}

# ---------------------------------------------------------------------------
# Crear tabla de control de migraciones (idempotente)
# ---------------------------------------------------------------------------

run_sql <<'SQL'
CREATE TABLE IF NOT EXISTS ovd_migrations (
  id            SERIAL PRIMARY KEY,
  filename      TEXT NOT NULL UNIQUE,
  applied_at    TIMESTAMP NOT NULL DEFAULT NOW(),
  checksum      TEXT
);
COMMENT ON TABLE ovd_migrations IS 'Registro de migraciones OVD aplicadas. Gestionado por scripts/migrate.sh.';
SQL

# ---------------------------------------------------------------------------
# Modo status
# ---------------------------------------------------------------------------

if [[ "$SHOW_STATUS" == true ]]; then
  echo ""
  echo "Estado de migraciones OVD:"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  printf "  %-45s %s\n" "Archivo" "Estado"
  echo "  ─────────────────────────────────────────────────────"

  for migration_file in $(find "$MIGRATIONS_DIR" -name "*.sql" | sort); do
    filename=$(basename "$migration_file")
    applied=$(run_sql -tAc "SELECT COUNT(*) FROM ovd_migrations WHERE filename = '$filename'" 2>/dev/null || echo "0")
    if [[ "$applied" -gt 0 ]]; then
      applied_at=$(run_sql -tAc "SELECT TO_CHAR(applied_at, 'YYYY-MM-DD HH24:MI') FROM ovd_migrations WHERE filename = '$filename'" 2>/dev/null || echo "?")
      printf "  %-45s ✅ Aplicada (%s)\n" "$filename" "$applied_at"
    else
      printf "  %-45s ⬜ Pendiente\n" "$filename"
    fi
  done

  echo ""
  exit 0
fi

# ---------------------------------------------------------------------------
# Aplicar migraciones pendientes
# ---------------------------------------------------------------------------

echo ""
echo "OVD Platform — Migracion incremental"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Base de datos: ${DATABASE_URL%%@*}@..."
echo "  Directorio:    $MIGRATIONS_DIR"
[[ "$DRY_RUN" == true ]] && echo "  Modo:          DRY-RUN (no se aplican cambios)"
echo ""

applied_count=0
skipped_count=0
failed_count=0

for migration_file in $(find "$MIGRATIONS_DIR" -name "*.sql" | sort); do
  filename=$(basename "$migration_file")
  checksum=$(md5 -q "$migration_file" 2>/dev/null || md5sum "$migration_file" | awk '{print $1}')

  # Verificar si ya fue aplicada
  already_applied=$(run_sql -tAc "SELECT COUNT(*) FROM ovd_migrations WHERE filename = '$filename'" 2>/dev/null || echo "0")

  if [[ "$already_applied" -gt 0 ]]; then
    echo "  ✅ Skipping: $filename (ya aplicada)"
    skipped_count=$((skipped_count + 1))
    continue
  fi

  echo "  🔨 Aplicando: $filename"

  if run_sql_file "$migration_file"; then
    if [[ "$DRY_RUN" == false ]]; then
      run_sql -c "INSERT INTO ovd_migrations (filename, checksum) VALUES ('$filename', '$checksum') ON CONFLICT (filename) DO NOTHING"
    fi
    echo "  ✅ OK: $filename"
    applied_count=$((applied_count + 1))
  else
    echo "  ✗ ERROR: $filename falló"
    failed_count=$((failed_count + 1))
    exit 1
  fi
done

# ---------------------------------------------------------------------------
# Aplicar RLS si se solicito
# ---------------------------------------------------------------------------

if [[ "$APPLY_RLS" == true ]]; then
  echo ""
  echo "  🔨 Aplicando RLS policies..."
  if run_sql_file "$RLS_FILE"; then
    echo "  ✅ OK: RLS policies aplicadas"
  else
    echo "  ✗ ERROR: RLS policies fallaron"
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# Resumen
# ---------------------------------------------------------------------------

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Migraciones aplicadas: $applied_count"
echo "  Migraciones skipped:   $skipped_count"
[[ "$failed_count" -gt 0 ]] && echo "  Migraciones fallidas:  $failed_count"
echo ""

if [[ "$DRY_RUN" == true ]]; then
  echo "  (DRY-RUN: ninguna migracion fue aplicada realmente)"
elif [[ "$applied_count" -eq 0 ]]; then
  echo "  La base de datos ya esta actualizada."
else
  echo "  Base de datos actualizada correctamente."
  echo ""
  echo "  Proximos pasos sugeridos:"
  echo "    1. Aplicar RLS:  $0 --rls"
  echo "    2. Verificar:    psql \$DATABASE_URL -c '\dt ovd_*'"
fi
echo ""
