-- OVD Platform — RAG pgvector schema
-- Copyright 2026 Omar Robles
--
-- Requiere: postgres con extension pgvector instalada
-- docker-compose.yml ya usa postgres+pgvector como imagen base.
--
-- Aplicar DESPUES de la migracion principal de Drizzle:
--   psql $DATABASE_URL < infra/postgres/rag.sql

-- Activar extension pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Agregar columna embedding a la tabla (si no existe)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'ovd_rag_documents'
      AND column_name = 'embedding'
  ) THEN
    ALTER TABLE ovd_rag_documents
      ADD COLUMN embedding vector(1536);
  END IF;
END $$;

-- Indice HNSW para busqueda semantica eficiente (cosine similarity)
-- HNSW es mas rapido que IVFFlat para colecciones pequenas/medianas
CREATE INDEX IF NOT EXISTS ovd_rag_embedding_hnsw_idx
  ON ovd_rag_documents
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- RLS: solo puede ver documentos de su org
ALTER TABLE ovd_rag_documents ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'ovd_rag_documents'
      AND policyname = 'ovd_rag_tenant_isolation'
  ) THEN
    CREATE POLICY ovd_rag_tenant_isolation
      ON ovd_rag_documents
      USING (org_id = current_setting('app.current_org_id', true));
  END IF;
END $$;
