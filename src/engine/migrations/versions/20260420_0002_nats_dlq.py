"""S20 — tabla ovd_nats_dlq (dead letter queue para mensajes NATS fallidos)

Revision ID: 20260420_0002
Revises: 20260412_0001
Create Date: 2026-04-20 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "20260420_0002"
down_revision: Union[str, None] = "20260412_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS ovd_nats_dlq (
            id           BIGSERIAL PRIMARY KEY,
            subject      TEXT        NOT NULL,
            payload      JSONB       NOT NULL,
            error        TEXT,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            processed_at TIMESTAMPTZ
        );

        CREATE INDEX IF NOT EXISTS idx_nats_dlq_unprocessed
            ON ovd_nats_dlq (created_at)
            WHERE processed_at IS NULL;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ovd_nats_dlq;")
