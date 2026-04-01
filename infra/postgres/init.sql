-- OVD Platform — PostgreSQL init script
-- Se ejecuta automaticamente al crear el contenedor por primera vez

-- Extensiones requeridas
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";   -- busqueda full-text eficiente

-- Rol de solo lectura para MCP PostgreSQL en dev
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ovd_readonly') THEN
    CREATE ROLE ovd_readonly LOGIN PASSWORD 'readonly_changeme';
  END IF;
END
$$;

GRANT CONNECT ON DATABASE ovd_dev TO ovd_readonly;
GRANT USAGE ON SCHEMA public TO ovd_readonly;

-- Los GRANT SELECT se aplican despues de que las migraciones Drizzle creen las tablas
-- Ver infra/postgres/grant-readonly.sql para ejecutar post-migracion

-- Verificacion
SELECT extname, extversion FROM pg_extension ORDER BY extname;
