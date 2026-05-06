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
    export DATABASE_URL="${DATABASE_URL/PLACEHOLDER/$DB_PASS}"
fi

# ---------------------------------------------------------------------------
# S112-C9: Resolución de schema para PostgreSQL 15+
#
# DO App Platform crea el usuario 'db' con REVOKE específico en schema public.
# No se puede otorgar CREATE en public desde dentro del app (sin GRANT OPTION).
#
# Estrategia:
#   1. Si el usuario tiene CREATE en public → continuar normalmente (dev local)
#   2. Si no, crear schema 'ovd' (el usuario es owner y tiene ALL PRIVILEGES)
#      y fijar search_path=ovd,public en DATABASE_URL para todas las conexiones
#   3. Si tampoco puede crear schema → fallo fatal con diagnóstico claro
# ---------------------------------------------------------------------------
if [ -n "$DATABASE_URL" ]; then
    echo "[entrypoint] Verificando privilegios de schema PostgreSQL..."
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
        # Dev local o PG sin restricción — no necesita schema alternativo
        await conn.close()
        sys.exit(0)

    # Intentar crear schema propio (requiere CREATE ON DATABASE, no en schema)
    try:
        await conn.execute("CREATE SCHEMA IF NOT EXISTS ovd")
        await conn.commit()

        # Verificar que el schema existe y somos owner
        cur2 = await conn.execute(
            "SELECT schema_owner FROM information_schema.schemata "
            "WHERE schema_name = 'ovd'"
        )
        row2 = await cur2.fetchone()
        if row2:
            print(f'[entrypoint] Schema ovd OK (owner={row2[0]})')
        await conn.close()
        sys.exit(2)  # señal: usar schema ovd

    except Exception as e:
        print(f'[entrypoint] FATAL: no se puede crear schema ovd: {e}', file=sys.stderr)
        await conn.close()
        sys.exit(3)

asyncio.run(main())
PYEOF

    SCHEMA_RESULT=$?

    if [ "$SCHEMA_RESULT" = "2" ]; then
        # Inyectar search_path=ovd,public en DATABASE_URL
        # Todos los consumidores (Alembic, api.py, LangGraph) heredan este URL
        if echo "$DATABASE_URL" | grep -q "?"; then
            export DATABASE_URL="${DATABASE_URL}&options=-csearch_path%3Dovd%2Cpublic"
        else
            export DATABASE_URL="${DATABASE_URL}?options=-csearch_path%3Dovd%2Cpublic"
        fi
        echo "[entrypoint] DATABASE_URL → search_path=ovd,public"
    elif [ "$SCHEMA_RESULT" = "3" ]; then
        echo "[entrypoint] FATAL: usuario DB no puede escribir en public ni crear schemas" >&2
        exit 1
    fi
    # SCHEMA_RESULT=0: public accesible, continuar sin modificar URL
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
