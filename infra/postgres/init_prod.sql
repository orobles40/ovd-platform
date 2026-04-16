-- OVD Platform — PostgreSQL init producción
-- Se ejecuta una sola vez al crear el volumen postgres_data.
-- Crea extensiones y rol de solo lectura.
-- Las tablas las crea Alembic en el entrypoint del engine.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Rol de solo lectura (para MCP PostgreSQL e inspección)
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ovd_readonly') THEN
    CREATE ROLE ovd_readonly LOGIN PASSWORD 'readonly_changeme';
  END IF;
END
$$;

GRANT CONNECT ON DATABASE ovd_prod TO ovd_readonly;
GRANT USAGE ON SCHEMA public TO ovd_readonly;
-- GRANT SELECT se aplica post-migración: psql -f infra/postgres/grant-readonly.sql
