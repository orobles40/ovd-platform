"""Seed org y proyecto de validación para ciclos de producción (S120-B)

Revision ID: 20260509_0008
Revises: 20260509_0007
Create Date: 2026-05-09 00:00:00.000000

Los ciclos de validación se lanzan con org_id='01KMK160F1TJ807Z0BDSJD504D'
(org RAG interno). Sin este seed, `deliver` falla con FK constraint en ovd_cycles.

Idempotente: INSERT ... ON CONFLICT DO NOTHING.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260509_0008"
down_revision: Union[str, None] = "20260509_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORG_ID = "01KMK160F1TJ807Z0BDSJD504D"
_PRJ_ID = "PRJ_TURNOS_VAL"


def upgrade() -> None:
    op.execute(f"""
        INSERT INTO ovd_orgs (id, name, plan, active)
        VALUES ('{_ORG_ID}', 'OVD Validación Prod', 'starter', TRUE)
        ON CONFLICT (id) DO NOTHING
    """)
    op.execute(f"""
        INSERT INTO ovd_projects (id, org_id, name, description, directory, active)
        VALUES (
            '{_PRJ_ID}',
            '{_ORG_ID}',
            'Sistema de Turnos Médicos (Validación)',
            'Proyecto de validación de ciclos OVD en producción',
            '/srv/projects/turnos-demo',
            TRUE
        )
        ON CONFLICT (id) DO NOTHING
    """)
    op.execute(f"""
        INSERT INTO ovd_stack_profiles (id, project_id, language, framework, database, active)
        VALUES (
            'STACK_TURNOS_VAL',
            '{_PRJ_ID}',
            'Python',
            'FastAPI',
            'PostgreSQL',
            TRUE
        )
        ON CONFLICT (id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute(f"DELETE FROM ovd_stack_profiles WHERE id = 'STACK_TURNOS_VAL'")
    op.execute(f"DELETE FROM ovd_projects WHERE id = '{_PRJ_ID}'")
    op.execute(f"DELETE FROM ovd_orgs WHERE id = '{_ORG_ID}'")
