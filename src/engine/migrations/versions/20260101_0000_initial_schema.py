"""initial schema — todas las tablas OVD (S3→S12)

Revision ID: 20260101_0000
Revises:
Create Date: 2026-01-01 00:00:00.000000

Nota: Este script representa el estado inicial de la BD creado manualmente
durante los sprints S3-S12. A partir de esta revisión, todos los cambios
de esquema se aplican con nuevas migraciones de Alembic.

Para aplicar sobre una BD vacía:
    DATABASE_URL=... alembic upgrade head

Para marcar como aplicado en una BD que ya tiene las tablas:
    DATABASE_URL=... alembic stamp head
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260101_0000"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------------------------------------------------------------------------
    # Extensiones
    # ---------------------------------------------------------------------------
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ---------------------------------------------------------------------------
    # Organizaciones
    # ---------------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS ovd_orgs (
            id           TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            plan         TEXT NOT NULL DEFAULT 'starter',
            active       BOOLEAN NOT NULL DEFAULT TRUE,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # ---------------------------------------------------------------------------
    # Usuarios
    # ---------------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS ovd_users (
            id            TEXT PRIMARY KEY,
            org_id        TEXT NOT NULL REFERENCES ovd_orgs(id),
            email         TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL DEFAULT 'developer',
            active        BOOLEAN NOT NULL DEFAULT TRUE,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # ---------------------------------------------------------------------------
    # Proyectos
    # ---------------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS ovd_projects (
            id          TEXT PRIMARY KEY,
            org_id      TEXT NOT NULL REFERENCES ovd_orgs(id),
            name        TEXT NOT NULL,
            description TEXT,
            directory   TEXT NOT NULL,
            active      BOOLEAN NOT NULL DEFAULT TRUE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # ---------------------------------------------------------------------------
    # Stack Profiles
    # ---------------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS ovd_stack_profiles (
            id          TEXT PRIMARY KEY,
            project_id  TEXT NOT NULL REFERENCES ovd_projects(id),
            language    TEXT,
            framework   TEXT,
            database    TEXT,
            active      BOOLEAN NOT NULL DEFAULT TRUE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # ---------------------------------------------------------------------------
    # Ciclos de desarrollo
    # ---------------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS ovd_cycles (
            id              TEXT PRIMARY KEY,
            org_id          TEXT NOT NULL REFERENCES ovd_orgs(id),
            project_id      TEXT REFERENCES ovd_projects(id),
            session_id      TEXT,
            thread_id       TEXT,
            fr_text         TEXT,
            fr_analysis     JSONB,
            sdd             JSONB,
            agent_results   JSONB,
            qa_result       JSONB,
            qa_score        INTEGER,
            complexity      TEXT,
            fr_type         TEXT,
            auto_approved   BOOLEAN NOT NULL DEFAULT FALSE,
            tokens_input    INTEGER NOT NULL DEFAULT 0,
            tokens_output   INTEGER NOT NULL DEFAULT 0,
            tokens_total    INTEGER NOT NULL DEFAULT 0,
            tokens_by_agent JSONB,
            cost_usd        NUMERIC(10,6) NOT NULL DEFAULT 0,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # ---------------------------------------------------------------------------
    # Refresh tokens (S12 — Auth)
    # ---------------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS ovd_refresh_tokens (
            id          TEXT PRIMARY KEY,
            org_id      TEXT NOT NULL REFERENCES ovd_orgs(id),
            user_id     TEXT NOT NULL REFERENCES ovd_users(id),
            token_hash  TEXT NOT NULL UNIQUE,
            expires_at  TIMESTAMPTZ NOT NULL,
            revoked     BOOLEAN NOT NULL DEFAULT FALSE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # ---------------------------------------------------------------------------
    # Embeddings RAG (S7)
    # ---------------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS ovd_rag_embeddings (
            id          BIGSERIAL PRIMARY KEY,
            org_id      TEXT NOT NULL REFERENCES ovd_orgs(id),
            cycle_id    TEXT REFERENCES ovd_cycles(id),
            content     TEXT NOT NULL,
            embedding   vector(1536),
            metadata    JSONB,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # ---------------------------------------------------------------------------
    # Audit log (S10)
    # ---------------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS ovd_audit_log (
            id          BIGSERIAL PRIMARY KEY,
            org_id      TEXT NOT NULL,
            user_id     TEXT,
            action      TEXT NOT NULL,
            resource    TEXT,
            resource_id TEXT,
            metadata    JSONB,
            ip_address  TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # ---------------------------------------------------------------------------
    # Índices
    # ---------------------------------------------------------------------------
    op.execute("CREATE INDEX IF NOT EXISTS idx_ovd_cycles_org_id ON ovd_cycles(org_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ovd_cycles_project_id ON ovd_cycles(project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ovd_cycles_created_at ON ovd_cycles(created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ovd_projects_org_id ON ovd_projects(org_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ovd_users_org_id ON ovd_users(org_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ovd_refresh_tokens_user_id ON ovd_refresh_tokens(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ovd_rag_org_id ON ovd_rag_embeddings(org_id)")

    # Índice HNSW para búsqueda vectorial
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ovd_rag_embedding_hnsw
        ON ovd_rag_embeddings USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # ---------------------------------------------------------------------------
    # Row-Level Security (S10)
    # ---------------------------------------------------------------------------
    for table in ["ovd_projects", "ovd_cycles", "ovd_rag_embeddings",
                  "ovd_stack_profiles", "ovd_refresh_tokens", "ovd_audit_log"]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY IF NOT EXISTS ovd_projects_org_isolation
        ON ovd_projects USING (org_id = current_setting('app.current_org_id', TRUE))
    """)
    op.execute("""
        CREATE POLICY IF NOT EXISTS ovd_cycles_org_isolation
        ON ovd_cycles USING (org_id = current_setting('app.current_org_id', TRUE))
    """)


def downgrade() -> None:
    for table in ["ovd_audit_log", "ovd_rag_embeddings", "ovd_refresh_tokens",
                  "ovd_cycles", "ovd_stack_profiles", "ovd_projects",
                  "ovd_users", "ovd_orgs"]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
