"""ovd_cycles — columna failed_at_node para trazabilidad de nodo de fallo (S117-A)

Revision ID: 20260509_0007
Revises: 20260508_0006
Create Date: 2026-05-09 00:00:00.000000

_ensure_cycle_registered() en api.py escribe failed_at_node con el nodo LangGraph
donde terminó el ciclo cuando no llega a deliver. Sin esta columna el UPDATE
falla silenciosamente con WARNING en cada ciclo no completado.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260509_0007"
down_revision: Union[str, None] = "20260508_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE ovd_cycles
        ADD COLUMN IF NOT EXISTS failed_at_node TEXT
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE ovd_cycles DROP COLUMN IF EXISTS failed_at_node")
