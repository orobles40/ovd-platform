-- OVD Platform — Permisos de lectura para el rol ovd_readonly
-- Uso: psql "$DATABASE_URL" -f grant-readonly.sql
--
-- Se ejecuta desde docker-entrypoint.sh después de `alembic upgrade head`.
-- El rol ovd_readonly es usado por el MCP PostgreSQL para consultas de solo lectura.
-- Idempotente: GRANT no falla si los permisos ya existen.

GRANT USAGE ON SCHEMA public TO ovd_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO ovd_readonly;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO ovd_readonly;

-- Aplica permisos automáticamente a tablas creadas por futuras migraciones
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO ovd_readonly;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON SEQUENCES TO ovd_readonly;
