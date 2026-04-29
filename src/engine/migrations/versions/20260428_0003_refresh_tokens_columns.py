"""S96-F: agregar columnas faltantes en ovd_refresh_tokens

Revision ID: 20260428_0003
Revises: 20260420_0002
Create Date: 2026-04-28

Las columnas user_agent, ip_address, revoked_at y revoked_reason fueron
implementadas en auth.py (S12) pero nunca se agregaron al schema de BD,
causando HTTP 500 en POST /auth/login desde el ciclo S75.
"""

from alembic import op

revision = "20260428_0003"
down_revision = "20260420_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE ovd_refresh_tokens
          ADD COLUMN IF NOT EXISTS user_agent     TEXT,
          ADD COLUMN IF NOT EXISTS ip_address     TEXT,
          ADD COLUMN IF NOT EXISTS revoked_at     TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS revoked_reason TEXT
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE ovd_refresh_tokens
          DROP COLUMN IF EXISTS user_agent,
          DROP COLUMN IF EXISTS ip_address,
          DROP COLUMN IF EXISTS revoked_at,
          DROP COLUMN IF EXISTS revoked_reason
    """)
