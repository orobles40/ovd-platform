"""S11.H — tabla ovd_web_sources (fuentes curadas por workspace)

Revision ID: 20260412_0001
Revises: 20260101_0000
Create Date: 2026-04-12 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "20260412_0001"
down_revision: Union[str, None] = "20260101_0000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS ovd_web_sources (
            id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
            org_id      TEXT NOT NULL REFERENCES ovd_orgs(id) ON DELETE CASCADE,
            project_id  TEXT REFERENCES ovd_projects(id) ON DELETE CASCADE,
            url         TEXT NOT NULL,
            label       TEXT NOT NULL DEFAULT '',
            active      BOOLEAN NOT NULL DEFAULT TRUE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ovd_web_sources_project "
        "ON ovd_web_sources(org_id, project_id) WHERE active = TRUE"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_ovd_web_sources_uniq "
        "ON ovd_web_sources(org_id, project_id, url) WHERE active = TRUE"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ovd_web_sources")
