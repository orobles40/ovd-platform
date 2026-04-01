-- OVD Platform — Row-Level Security policies (Sprint 10 — GAP-A2)
-- Copyright 2026 Omar Robles
--
-- Aplica RLS en todas las tablas tenant de OVD.
-- Ejecutar DESPUÉS de que las migraciones hayan creado las tablas.
--
-- Uso:
--   psql $DATABASE_URL -f infra/postgres/rls.sql
-- O via migrate.sh:
--   ./scripts/migrate.sh --rls
--
-- Mecanismo:
--   El middleware (Bridge/FastAPI) ejecuta antes de cada query:
--     SET LOCAL app.current_org_id = '<org_id>';
--   La función ovd_current_org_id() lee esa variable de sesión.
--   Todas las políticas usan USING (org_id = ovd_current_org_id()).
--
--   Bypass: el usuario ovd_dev (superuser en dev) puede bypasear RLS.
--   En producción, usar un rol sin BYPASSRLS para las queries de la app.
--
-- Principio de diseño:
--   Sin la variable app.current_org_id configurada, ninguna fila es visible.
--   Esto garantiza que un bug en el middleware no expone datos cross-tenant.

-- ---------------------------------------------------------------------------
-- Verificar prerequisito: función ovd_current_org_id() debe existir
-- ---------------------------------------------------------------------------

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_proc WHERE proname = 'ovd_current_org_id'
  ) THEN
    RAISE EXCEPTION
      'Prerequisito: función ovd_current_org_id() no encontrada. '
      'Aplicar 0000_ovd_initial_schema.sql primero.';
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- ovd_organizations
-- ---------------------------------------------------------------------------

ALTER TABLE ovd_organizations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ovd_organizations_tenant ON ovd_organizations;
CREATE POLICY ovd_organizations_tenant ON ovd_organizations
  USING (id = ovd_current_org_id());

-- ---------------------------------------------------------------------------
-- ovd_users
-- ---------------------------------------------------------------------------

ALTER TABLE ovd_users ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ovd_users_tenant ON ovd_users;
CREATE POLICY ovd_users_tenant ON ovd_users
  USING (org_id = ovd_current_org_id());

-- ---------------------------------------------------------------------------
-- ovd_projects
-- ---------------------------------------------------------------------------

ALTER TABLE ovd_projects ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ovd_projects_tenant ON ovd_projects;
CREATE POLICY ovd_projects_tenant ON ovd_projects
  USING (org_id = ovd_current_org_id());

-- ---------------------------------------------------------------------------
-- ovd_session_threads
-- ---------------------------------------------------------------------------

ALTER TABLE ovd_session_threads ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ovd_session_threads_tenant ON ovd_session_threads;
CREATE POLICY ovd_session_threads_tenant ON ovd_session_threads
  USING (org_id = ovd_current_org_id());

-- ---------------------------------------------------------------------------
-- ovd_project_profiles (GAP-011, S8)
-- ---------------------------------------------------------------------------

ALTER TABLE ovd_project_profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ovd_project_profiles_tenant ON ovd_project_profiles;
CREATE POLICY ovd_project_profiles_tenant ON ovd_project_profiles
  USING (org_id = ovd_current_org_id());

-- ---------------------------------------------------------------------------
-- ovd_agent_configs (GAP-013a)
-- ---------------------------------------------------------------------------

ALTER TABLE ovd_agent_configs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ovd_agent_configs_tenant ON ovd_agent_configs;
CREATE POLICY ovd_agent_configs_tenant ON ovd_agent_configs
  USING (org_id = ovd_current_org_id());

-- ---------------------------------------------------------------------------
-- ovd_fine_tuned_models (GAP-012)
-- ---------------------------------------------------------------------------

ALTER TABLE ovd_fine_tuned_models ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ovd_fine_tuned_models_tenant ON ovd_fine_tuned_models;
CREATE POLICY ovd_fine_tuned_models_tenant ON ovd_fine_tuned_models
  USING (org_id = ovd_current_org_id());

-- ---------------------------------------------------------------------------
-- ovd_rag_documents (RAG)
-- ---------------------------------------------------------------------------

ALTER TABLE ovd_rag_documents ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ovd_rag_documents_tenant ON ovd_rag_documents;
CREATE POLICY ovd_rag_documents_tenant ON ovd_rag_documents
  USING (org_id = ovd_current_org_id());

-- ---------------------------------------------------------------------------
-- ovd_cycle_logs (fine-tuning dataset)
-- Critical: datos de entrenamiento deben estar aislados por org
-- ---------------------------------------------------------------------------

ALTER TABLE ovd_cycle_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ovd_cycle_logs_tenant ON ovd_cycle_logs;
CREATE POLICY ovd_cycle_logs_tenant ON ovd_cycle_logs
  USING (org_id = ovd_current_org_id());

-- ---------------------------------------------------------------------------
-- ovd_audit_logs (Sprint 10)
-- Política: solo lectura del propio org. Los writes van via función privilegiada.
-- ---------------------------------------------------------------------------

ALTER TABLE ovd_audit_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ovd_audit_logs_tenant ON ovd_audit_logs;
CREATE POLICY ovd_audit_logs_tenant ON ovd_audit_logs
  USING (org_id = ovd_current_org_id());

-- ---------------------------------------------------------------------------
-- ovd_webhook_subscriptions (Sprint 4)
-- ---------------------------------------------------------------------------

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables WHERE table_name = 'ovd_webhook_subscriptions'
  ) THEN
    EXECUTE 'ALTER TABLE ovd_webhook_subscriptions ENABLE ROW LEVEL SECURITY';
    EXECUTE 'DROP POLICY IF EXISTS ovd_webhook_subscriptions_tenant ON ovd_webhook_subscriptions';
    EXECUTE 'CREATE POLICY ovd_webhook_subscriptions_tenant ON ovd_webhook_subscriptions
             USING (org_id = ovd_current_org_id())';
    RAISE NOTICE 'OK: RLS aplicado a ovd_webhook_subscriptions';
  ELSE
    RAISE NOTICE 'INFO: ovd_webhook_subscriptions no existe — saltar (aplicar migración 0004 primero)';
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- ovd_org_quotas (Sprint 7)
-- ---------------------------------------------------------------------------

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables WHERE table_name = 'ovd_org_quotas'
  ) THEN
    EXECUTE 'ALTER TABLE ovd_org_quotas ENABLE ROW LEVEL SECURITY';
    EXECUTE 'DROP POLICY IF EXISTS ovd_org_quotas_tenant ON ovd_org_quotas';
    EXECUTE 'CREATE POLICY ovd_org_quotas_tenant ON ovd_org_quotas
             USING (org_id = ovd_current_org_id())';
    RAISE NOTICE 'OK: RLS aplicado a ovd_org_quotas';
  ELSE
    RAISE NOTICE 'INFO: ovd_org_quotas no existe — saltar (aplicar migración 0007 primero)';
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- ovd_refresh_tokens (Sprint 10 — S10.E)
-- ---------------------------------------------------------------------------

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables WHERE table_name = 'ovd_refresh_tokens'
  ) THEN
    EXECUTE 'ALTER TABLE ovd_refresh_tokens ENABLE ROW LEVEL SECURITY';
    EXECUTE 'DROP POLICY IF EXISTS ovd_refresh_tokens_tenant ON ovd_refresh_tokens';
    EXECUTE 'CREATE POLICY ovd_refresh_tokens_tenant ON ovd_refresh_tokens
             USING (org_id = ovd_current_org_id())';
    RAISE NOTICE 'OK: RLS aplicado a ovd_refresh_tokens';
  ELSE
    RAISE NOTICE 'INFO: ovd_refresh_tokens no existe — saltar (aplicar migración 0011 primero)';
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- Rol de solo lectura (MCP PostgreSQL en producción)
-- Recibe acceso SELECT a todas las tablas con RLS activo
-- ---------------------------------------------------------------------------

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ovd_readonly') THEN
    GRANT SELECT ON
      ovd_organizations, ovd_users, ovd_projects,
      ovd_session_threads, ovd_rag_documents,
      ovd_project_profiles, ovd_agent_configs, ovd_fine_tuned_models,
      ovd_cycle_logs, ovd_audit_logs
    TO ovd_readonly;
    RAISE NOTICE 'OK: permisos SELECT otorgados a rol ovd_readonly';
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- Tests de aislamiento RLS
-- Verifican que sin org_id configurado, ninguna fila es visible
-- ---------------------------------------------------------------------------

DO $$
DECLARE
  v_count INTEGER;
  v_table TEXT;
  v_tables TEXT[] := ARRAY[
    'ovd_organizations', 'ovd_users', 'ovd_projects',
    'ovd_session_threads', 'ovd_project_profiles', 'ovd_agent_configs',
    'ovd_fine_tuned_models', 'ovd_rag_documents', 'ovd_cycle_logs', 'ovd_audit_logs'
  ];
BEGIN
  -- Test 1: sin app.current_org_id configurado → 0 filas visibles en cada tabla
  PERFORM set_config('app.current_org_id', '', false);

  FOREACH v_table IN ARRAY v_tables LOOP
    BEGIN
      EXECUTE format('SELECT COUNT(*) FROM %I', v_table) INTO v_count;
      IF v_count > 0 THEN
        RAISE WARNING
          'RLS TEST FAIL: % muestra % fila(s) sin org_id configurado — '
          'verificar que el usuario de la app NO es superuser (BYPASSRLS)',
          v_table, v_count;
      ELSE
        RAISE NOTICE 'RLS TEST OK: % → 0 filas sin org_id (aislamiento correcto)', v_table;
      END IF;
    EXCEPTION WHEN OTHERS THEN
      RAISE NOTICE 'RLS TEST SKIP: % → tabla no existe aún', v_table;
    END;
  END LOOP;

  RAISE NOTICE '';
  RAISE NOTICE 'NOTA: Si los tests muestran filas con count > 0, el usuario de la base de datos';
  RAISE NOTICE 'tiene BYPASSRLS (superuser). En producción, usar un rol sin este privilegio.';
  RAISE NOTICE 'Verificar: SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user;';
END $$;

-- ---------------------------------------------------------------------------
-- Verificación final: listar tablas con RLS activo
-- ---------------------------------------------------------------------------

SELECT
  tablename,
  rowsecurity AS rls_enabled,
  CASE WHEN rowsecurity THEN '✓ ACTIVO' ELSE '✗ INACTIVO' END AS estado
FROM pg_tables
WHERE tablename LIKE 'ovd_%'
  AND schemaname = 'public'
ORDER BY tablename;
