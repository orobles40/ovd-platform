#!/bin/sh
# OVD Engine — Docker entrypoint
# Lee Docker Secrets y los exporta como variables de entorno antes de lanzar la app.

set -e

load_secret() {
    local name="$1"
    local env_var="$2"
    local path="/run/secrets/${name}"
    if [ -f "$path" ]; then
        export "$env_var"="$(cat "$path")"
    fi
}

load_secret anthropic_api_key    ANTHROPIC_API_KEY
load_secret ovd_engine_secret    OVD_ENGINE_SECRET
load_secret openai_api_key       OPENAI_API_KEY
load_secret ovd_admin_password   OVD_ADMIN_PASSWORD

# Reconstruir DATABASE_URL con la password del secret
if [ -f /run/secrets/db_password ]; then
    DB_PASS="$(cat /run/secrets/db_password)"
    export DATABASE_URL="${DATABASE_URL/PLACEHOLDER/$DB_PASS}"
fi

# ---------------------------------------------------------------------------
# S112-C9: Verificar privilegios de schema PostgreSQL
#
# Con production: true (cluster standalone DO), DATABASE_URL usa doadmin
# que tiene CREATE en public → flujo normal.
#
# Si el usuario no puede crear en public ni crear schemas propios, el
# entrypoint inyecta search_path=ovd para usar un schema alternativo.
# ---------------------------------------------------------------------------
if [ -n "$DATABASE_URL" ]; then
    python3 - << 'PYEOF'
import asyncio, os, sys
import psycopg

async def main():
    url = os.environ.get('DATABASE_URL', '')
    if not url:
        sys.exit(0)

    conn = await psycopg.AsyncConnection.connect(url)
    cur = await conn.execute(
        "SELECT current_user, current_database(), "
        "has_schema_privilege(current_user, 'public', 'CREATE')"
    )
    row = await cur.fetchone()
    username, dbname, can_create_public = row
    print(f'[entrypoint] user={username} db={dbname} can_create_public={can_create_public}')

    if can_create_public:
        await conn.close()
        sys.exit(0)  # normal — doadmin o usuario con privilegios completos

    # Sin CREATE en public: intentar schema alternativo 'ovd'
    try:
        await conn.execute("CREATE SCHEMA IF NOT EXISTS ovd")
        await conn.commit()
        print('[entrypoint] Schema ovd creado — usando search_path=ovd,public')
        await conn.close()
        sys.exit(2)
    except Exception as e:
        print(f'[entrypoint] WARN: no se puede crear schema ovd: {e}', file=sys.stderr)
        print('[entrypoint] Intentando continuar — Alembic reportará el error real')
        await conn.close()
        sys.exit(0)  # dejar que Alembic falle con mensaje claro

asyncio.run(main())
PYEOF

    SCHEMA_RESULT=$?
    if [ "$SCHEMA_RESULT" = "2" ]; then
        if echo "$DATABASE_URL" | grep -q "?"; then
            export DATABASE_URL="${DATABASE_URL}&options=-csearch_path%3Dovd%2Cpublic"
        else
            export DATABASE_URL="${DATABASE_URL}?options=-csearch_path%3Dovd%2Cpublic"
        fi
        echo "[entrypoint] DATABASE_URL → search_path=ovd,public"
    fi
fi

# Ejecutar migraciones Alembic antes de arrancar el engine
echo "[entrypoint] Ejecutando migraciones Alembic..."
alembic upgrade head
echo "[entrypoint] Migraciones completadas."

# Aplicar permisos de lectura para ovd_readonly (MCP PostgreSQL)
GRANT_FILE="/app/migrations/grant-readonly.sql"
if [ -f "$GRANT_FILE" ] && [ -n "$DATABASE_URL" ]; then
    echo "[entrypoint] Aplicando grant-readonly.sql..."
    psql "$DATABASE_URL" -f "$GRANT_FILE" \
        && echo "[entrypoint] Permisos readonly aplicados." \
        || echo "[entrypoint] WARN: grant-readonly.sql falló (el rol ovd_readonly puede no existir)"
fi

# Generar hash argon2 del password admin
ADMIN_PASSWORD_HASH=""
if [ -n "$OVD_ADMIN_PASSWORD" ]; then
    ADMIN_PASSWORD_HASH=$(python3 -c "
from passlib.hash import argon2
import sys
print(argon2.hash('$OVD_ADMIN_PASSWORD'))
" 2>/dev/null) || true
fi

# Aplicar datos iniciales (idempotente)
SEED_FILE="/app/migrations/seed_prod.sql"
if [ -f "$SEED_FILE" ] && [ -n "$DATABASE_URL" ]; then
    echo "[entrypoint] Aplicando seed_prod.sql..."
    HASH_VAR="${ADMIN_PASSWORD_HASH:-CHANGE_ME_BEFORE_USE}"
    psql "$DATABASE_URL" -f "$SEED_FILE" \
        -v ON_ERROR_STOP=1 \
        -v admin_password_hash="$HASH_VAR" \
        && echo "[entrypoint] Seed completado." \
        || echo "[entrypoint] WARN: seed_prod.sql falló"
fi

exec "$@"
