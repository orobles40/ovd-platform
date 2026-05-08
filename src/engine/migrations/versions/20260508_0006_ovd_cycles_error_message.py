"""ovd_cycles — columna error_message para registro de fallos parciales (S116-B)

Revision ID: 20260508_0006
Revises: 20260507_0005
Create Date: 2026-05-08 00:00:00.000000

_ensure_cycle_registered() en api.py escribe error_message cuando el ciclo
no llega a deliver. Sin esta columna genera un WARNING por cada ciclo fallido
e impide registrar la causa de fallo en ovd_cycles.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260508_0006"
down_revision: Union[str, None] = "20260507_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE ovd_cycles
        ADD COLUMN IF NOT EXISTS error_message TEXT
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE ovd_cycles DROP COLUMN IF EXISTS error_message")
