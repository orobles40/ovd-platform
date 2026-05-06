-- OVD Platform — Datos iniciales de producción (demo neutro)
-- Uso: psql "$DATABASE_URL" -f seed_prod.sql -v admin_password_hash='<hash>'
--
-- El hash argon2id se genera en docker-entrypoint.sh desde OVD_ADMIN_PASSWORD.
-- Para generarlo manualmente:
--   python3 -c "from passlib.hash import argon2; print(argon2.hash('TU_PASSWORD'))"
--
-- Idempotente: usa INSERT ... ON CONFLICT DO NOTHING
-- No destruye datos existentes.
--
-- Historial:
--   2026-05-05  S112 — datos demo neutros (org OVD Demo + proyecto Sistema de Turnos)

-- ---------------------------------------------------------------------------
-- Organización demo
-- ---------------------------------------------------------------------------
INSERT INTO ovd_orgs (id, name, plan, active)
VALUES (
    'ORG_OVD_DEMO',
    'OVD Demo',
    'starter',
    TRUE
)
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Usuario administrador demo
-- El hash se inyecta como variable psql desde docker-entrypoint.sh.
-- Configurar OVD_ADMIN_PASSWORD como secret en DO antes del primer deploy.
-- ---------------------------------------------------------------------------
INSERT INTO ovd_users (id, org_id, email, password_hash, role, active)
VALUES (
    'USR_ADMIN_DEMO',
    'ORG_OVD_DEMO',
    'admin@codigonet.cloud',
    :'admin_password_hash',
    'admin',
    TRUE
)
ON CONFLICT (id) DO UPDATE SET
    password_hash = EXCLUDED.password_hash
WHERE ovd_users.password_hash = 'CHANGE_ME_BEFORE_USE';

-- ---------------------------------------------------------------------------
-- Proyecto demo — Sistema de Turnos Médicos
-- Stack: FastAPI + React + PostgreSQL (greenfield, modo demo)
-- ---------------------------------------------------------------------------
INSERT INTO ovd_projects (id, org_id, name, description, directory, active)
VALUES (
    'PRJ_TURNOS_DEMO',
    'ORG_OVD_DEMO',
    'Sistema de Turnos Médicos',
    'Sistema de gestión de turnos médicos — demo OVD Platform (FastAPI + React + PostgreSQL)',
    '/srv/projects/turnos-demo',
    TRUE
)
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Stack profile del proyecto demo
-- ---------------------------------------------------------------------------
INSERT INTO ovd_stack_profiles (id, project_id, language, framework, database, active)
VALUES (
    'STACK_TURNOS_DEMO',
    'PRJ_TURNOS_DEMO',
    'Python',
    'FastAPI',
    'PostgreSQL',
    TRUE
)
ON CONFLICT (id) DO NOTHING;
