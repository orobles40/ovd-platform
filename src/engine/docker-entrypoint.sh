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

load_secret anthropic_api_key ANTHROPIC_API_KEY
load_secret ovd_engine_secret  OVD_ENGINE_SECRET

# Reconstruir DATABASE_URL con la password del secret
if [ -f /run/secrets/db_password ]; then
    DB_PASS="$(cat /run/secrets/db_password)"
    # Reemplaza "PLACEHOLDER" en DATABASE_URL con la password real
    export DATABASE_URL="${DATABASE_URL/PLACEHOLDER/$DB_PASS}"
fi

exec "$@"
