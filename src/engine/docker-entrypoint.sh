#!/bin/sh
# OVD Engine — Docker entrypoint
# Lee Docker Secrets y los exporta como variables de entorno antes de lanzar la app.
# Secrets esperados en /run/secrets/:
#   anthropic_api_key, db_password, ovd_engine_secret

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
    # Reemplaza "PLACEHOLDER" en DATABASE_URL con la password real
    export DATABASE_URL="${DATABASE_URL/PLACEHOLDER/$DB_PASS}"
fi

# S112-C9: PostgreSQL 15+ revocó CREATE en schema public por defecto.
if [ -n "$DATABASE_URL" ]; then
    echo "[entrypoint] Verificando permisos schema public..."
    python3 - << 'PYEOF'
import asyncio, os, sys
import psycopg

async def main():
    url = os.environ.get('DATABASE_URL', '')
    if not url:
        return
    try:
        conn = await psycopg.AsyncConnection.connect(url)
        cur = await conn.execute(
            "SELECT current_user, current_database(), "
            "has_schema_privilege(current_user, 'public', 'CREATE'), "
            "has_schema_privilege(current_user, 'public', 'USAGE')"
        )
        row = await cur.fetchone()
        print(f'[entrypoint] user={row[0]} db={row[1]} can_create={row[2]} usage={row[3]}')
        if not row[2]:
            print('[entrypoint] Aplicando GRANT CREATE ON SCHEMA public...')
            await conn.execute('GRANT CREATE ON SCHEMA public TO PUBLIC')
            await conn.commit()
            print('[entrypoint] GRANT aplicado')
        await conn.close()
    except Exception as e:
        print(f'[entrypoint] WARN schema check: {e}', file=sys.stderr)

asyncio.run(main())
PYEOF
fi

# Ejecutar migraciones Alembic antes de arrancar el engine
# Si la migración falla, el container no arranca (set -e lo garantiza)
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

# Generar hash argon2 del password admin si se proveyó OVD_ADMIN_PASSWORD
ADMIN_PASSWORD_HASH=""
if [ -n "$OVD_ADMIN_PASSWORD" ]; then
    ADMIN_PASSWORD_HASH=$(python3 -c "
from passlib.hash import argon2
import sys
print(argon2.hash('$OVD_ADMIN_PASSWORD'))
" 2>/dev/null) || true
fi

# Aplicar datos iniciales (idempotente — ON CONFLICT DO NOTHING)
SEED_FILE="/app/migrations/seed_prod.sql"
if [ -f "$SEED_FILE" ] && [ -n "$DATABASE_URL" ]; then
    echo "[entrypoint] Aplicando seed_prod.sql..."
    HASH_VAR="${ADMIN_PASSWORD_HASH:-CHANGE_ME_BEFORE_USE}"
    psql "$DATABASE_URL" -f "$SEED_FILE" \
        -v ON_ERROR_STOP=1 \
        -v admin_password_hash="$HASH_VAR" \
        && echo "[entrypoint] Seed completado." \
        || echo "[entrypoint] WARN: seed_prod.sql falló (tabla ya poblada o error ignorado)"
fi

exec "$@"
