-- OVD Platform — Datos iniciales de producción
-- Uso: psql "$DATABASE_URL" -f seed_prod.sql
--
-- Idempotente: usa INSERT ... ON CONFLICT DO NOTHING
-- No destruye datos existentes.
--
-- IMPORTANTE antes de desplegar:
--   1. Cambiar el password del admin con el endpoint POST /auth/change-password
--      o regenerar el hash con:
--        python -c "from passlib.hash import argon2; print(argon2.hash('TU_PASSWORD'))"
--   2. Ajustar 'directory' del proyecto al path real en el servidor.
--
-- Historial:
--   2026-04-16  Primera versión — org ORG_OMAR_ROBLES + admin + proyecto HHMM

-- ---------------------------------------------------------------------------
-- Organización principal
-- ---------------------------------------------------------------------------
INSERT INTO ovd_orgs (id, name, plan, active)
VALUES (
    'ORG_OMAR_ROBLES',
    'Omar Robles',
    'starter',
    TRUE
)
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Usuario administrador
-- Password actual: ovd-dev-2026 (argon2id)
-- CAMBIAR DESPUÉS DEL PRIMER DEPLOY
-- ---------------------------------------------------------------------------
INSERT INTO ovd_users (id, org_id, email, password_hash, role, active)
VALUES (
    'USR_OMAR_01',
    'ORG_OMAR_ROBLES',
    'omar@omarrobles.dev',
    '$argon2id$v=19$m=65536,t=3,p=4$fK+VEgJAqBWCkJKS8r5XKg$GZzyRbttfRNdSYzFNVE+aTrJ0hYTtMsZ99txC7Hbo7Q',
    'admin',
    TRUE
)
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Proyecto inicial — Honorarios Médicos CAS
-- Ajustar 'directory' al path real del servidor
-- ---------------------------------------------------------------------------
INSERT INTO ovd_projects (id, org_id, name, description, directory, active)
VALUES (
    '58D83075CED34A57B22EAFACC1',
    'ORG_OMAR_ROBLES',
    'Honorarios Médicos — CAS',
    'Sistema de honorarios médicos Clínica Alemana de Santiago (Oracle 19c + Java)',
    '/srv/projects/hhmm',
    TRUE
)
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Stack profile del proyecto HHMM
-- ---------------------------------------------------------------------------
INSERT INTO ovd_stack_profiles (id, project_id, language, framework, database, active)
VALUES (
    'STACK_HHMM_01',
    '58D83075CED34A57B22EAFACC1',
    'Java',
    'Struts 1.x / iBATIS',
    'Oracle 19c',
    TRUE
)
ON CONFLICT (id) DO NOTHING;
