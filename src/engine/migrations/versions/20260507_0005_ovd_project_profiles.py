"""ovd_project_profiles — tabla de stack profiles enriquecidos (S112-fix)

Revision ID: 20260507_0005
Revises: 20260505_0004
Create Date: 2026-05-07 00:00:00.000000

La tabla ovd_stack_profiles (migración inicial) tiene un schema mínimo
(id, project_id, language, framework, database, active) usado internamente
por el engine para contexto de agentes.

ovd_project_profiles es la versión completa usada por la API REST v1
(list_projects, get_project, import_project, upsert_profile) con todos
los campos de stack que el panel de administración expone.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260507_0005"
down_revision: Union[str, None] = "20260505_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS ovd_project_profiles (
            id              TEXT PRIMARY KEY,
            org_id          TEXT NOT NULL,
            project_id      TEXT NOT NULL REFERENCES ovd_projects(id) ON DELETE CASCADE,
            language        TEXT,
            framework       TEXT,
            db_engine       TEXT,
            runtime         TEXT,
            additional_stack JSONB DEFAULT '[]',
            legacy_stack    TEXT,
            external_integrations TEXT,
            qa_tools        TEXT,
            ci_cd           TEXT,
            constraints     TEXT,
            code_style      TEXT,
            project_description TEXT,
            team_size       TEXT,
            active          BOOLEAN NOT NULL DEFAULT true,
            time_created    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            time_updated    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ovd_project_profiles_project_id
        ON ovd_project_profiles (project_id)
        WHERE active = true
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ovd_project_profiles")
