"""ovd_cycles — columna status + índice único thread_id (S47-B / S112-C2)

Revision ID: 20260505_0004
Revises: 20260428_0003
Create Date: 2026-05-05 00:00:00.000000

Agrega:
  - columna `status TEXT NOT NULL DEFAULT 'started'` en ovd_cycles
  - índice único `idx_ovd_cycles_thread_id` en ovd_cycles(thread_id)
    (permite UPSERT ON CONFLICT en el nodo deliver y en early registration)

Motivo: los ciclos se registran al crear la sesión ('started') y se actualizan
al completar ('completed') o fallar ('failed') vía ON CONFLICT (thread_id).
Sin el índice único el UPSERT no tiene clave de conflicto.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "20260505_0004"
down_revision: Union[str, None] = "20260428_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE ovd_cycles
        ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'started'
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_ovd_cycles_thread_id
        ON ovd_cycles (thread_id)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_ovd_cycles_thread_id")
    op.execute("ALTER TABLE ovd_cycles DROP COLUMN IF EXISTS status")
