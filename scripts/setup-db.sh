#!/usr/bin/env bash
# OVD Platform — Setup inicial de la base de datos PostgreSQL
# Copyright 2026 Omar Robles
#
# Aplica las migraciones OVD en orden correcto:
#   1. Schema inicial (tablas tenant + OVD)
#   2. RLS policies
#   3. pgvector + índice HNSW para RAG
#
# Uso:
#   DATABASE_URL=postgresql://user:pass@host:5432/dbname bash scripts/setup-db.sh
#
# O con docker-compose (levanta postgres si no está corriendo):
#   bash scripts/setup-db.sh --docker

set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DATABASE_URL="${DATABASE_URL:-}"
USE_DOCKER=false

for arg in "$@"; do
  case $arg in
    --docker) USE_DOCKER=true ;;
    *) echo "Argumento desconocido: $arg"; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log()  { echo "[OVD setup] $*"; }
ok()   { echo "[OVD setup] ✓ $*"; }
fail() { echo "[OVD setup] ✗ $*" >&2; exit 1; }

psql_exec() {
  if [[ -z "$DATABASE_URL" ]]; then
    fail "DATABASE_URL no configurada"
  fi
  psql "$DATABASE_URL" "$@"
}

# ---------------------------------------------------------------------------
# Opción --docker: levantar postgres con docker-compose
# ---------------------------------------------------------------------------

if $USE_DOCKER; then
  log "Levantando servicio postgres con docker-compose..."
  docker compose -f "$REPO_ROOT/docker-compose.yml" up -d postgres

  log "Esperando a que PostgreSQL esté listo..."
  for i in $(seq 1 30); do
    if docker compose -f "$REPO_ROOT/docker-compose.yml" exec postgres \
        pg_isready -U ovd -d ovd 2>/dev/null; then
      break
    fi
    sleep 1
  done

  # Leer DATABASE_URL del .env.local o usar default del docker-compose
  if [[ -f "$REPO_ROOT/.env.local" ]]; then
    DATABASE_URL="$(grep '^DATABASE_URL=' "$REPO_ROOT/.env.local" | cut -d= -f2-)"
  fi
  DATABASE_URL="${DATABASE_URL:-postgresql://ovd:ovd@localhost:5432/ovd}"
  log "DATABASE_URL: $DATABASE_URL"
fi

# ---------------------------------------------------------------------------
# Verificar conexión
# ---------------------------------------------------------------------------

if [[ -z "$DATABASE_URL" ]]; then
  fail "DATABASE_URL no configurada. Exporta la variable o usa --docker"
fi

log "Verificando conexión a PostgreSQL..."
psql_exec -c "SELECT version();" --no-psqlrc -q 2>/dev/null \
  || fail "No se puede conectar a $DATABASE_URL"
ok "Conexión establecida"

# ---------------------------------------------------------------------------
# Paso 1: Schema inicial
# ---------------------------------------------------------------------------

log "Aplicando schema inicial (tablas OVD)..."
psql_exec -f "$REPO_ROOT/packages/opencode/migration-ovd/0000_ovd_initial_schema.sql" \
  --no-psqlrc -q
ok "Schema inicial aplicado"

# ---------------------------------------------------------------------------
# Paso 2: RLS policies
# ---------------------------------------------------------------------------

log "Aplicando Row-Level Security..."
psql_exec -f "$REPO_ROOT/infra/postgres/rls.sql" --no-psqlrc -q
ok "RLS aplicado"

# ---------------------------------------------------------------------------
# Paso 3: pgvector + RAG
# ---------------------------------------------------------------------------

log "Configurando pgvector para RAG..."
psql_exec -f "$REPO_ROOT/infra/postgres/rag.sql" --no-psqlrc -q 2>/dev/null \
  || log "WARNING: pgvector no disponible — RAG deshabilitado (instalar pgvector si se necesita)"
ok "Configuración RAG completada"

# ---------------------------------------------------------------------------
# Verificación final
# ---------------------------------------------------------------------------

log "Verificando tablas creadas..."
TABLES=$(psql_exec -t -c "
  SELECT string_agg(tablename, ', ' ORDER BY tablename)
  FROM pg_tables
  WHERE tablename LIKE 'ovd_%'
    AND schemaname = 'public';
" --no-psqlrc -q | xargs)

ok "Tablas OVD disponibles: $TABLES"
echo ""
echo "Setup completado. Próximos pasos:"
echo "  1. Copia .env.example → .env.local y configura las variables"
echo "  2. bun install  (en la raíz del repo)"
echo "  3. bun dev      (levanta el servidor OpenCode con módulos OVD)"
echo "  4. docker compose --profile ovd up -d  (levanta el OVD Engine)"
