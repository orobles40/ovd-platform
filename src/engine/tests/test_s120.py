"""Tests S120 — Fix directory fallback + org de validación en producción.

S120-A: session_create asigna /srv/projects/{slug} cuando directory='' después del lookup en BD.
S120-B: migración y seed_prod.sql incluyen org '01KMK160F1TJ807Z0BDSJD504D' para ciclos de validación.
"""

import pathlib
import re

_API_SRC = (pathlib.Path(".") / "api.py").read_text(encoding="utf-8")
_SEED_SQL = (pathlib.Path(".") / "migrations" / "seed_prod.sql").read_text(
    encoding="utf-8"
)
_MIGRATION = (
    pathlib.Path(".")
    / "migrations"
    / "versions"
    / "20260509_0008_seed_validation_org.py"
).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# S120-A — directorio fallback en session_create
# ---------------------------------------------------------------------------


def test_s120a_fallback_present_in_api():
    """api.py debe tener el bloque S120-A de directorio fallback."""
    assert "S120-A" in _API_SRC, "S120-A: falta comentario de trazabilidad en api.py"


def test_s120a_uses_srv_projects_path():
    """El fallback debe construir la ruta /srv/projects/{slug}."""
    assert "/srv/projects/" in _API_SRC, (
        "S120-A: el fallback debe usar /srv/projects/ como base"
    )


def test_s120a_normalizes_project_id_to_slug():
    """El fallback debe normalizar project_id a lowercase con guiones."""
    assert ".lower().replace" in _API_SRC, (
        "S120-A: debe normalizar project_id a slug (lower + replace _ → -)"
    )


def test_s120a_fallback_only_when_project_id_present():
    """El fallback solo se activa cuando project_id está presente."""
    # La condición debe ser: not resolved_directory AND body.project_id
    snippet = _API_SRC[_API_SRC.find("S120-A") - 200 : _API_SRC.find("S120-A") + 50]
    assert "body.project_id" in snippet, (
        "S120-A: el fallback debe estar condicionado a que project_id no esté vacío"
    )


def test_s120a_fires_before_tmpdir_fallback():
    """El bloque S120-A debe aparecer antes del fallback tmpdir (desktop sin project_id)."""
    idx_s120 = _API_SRC.find("S120-A")
    idx_tmpdir = _API_SRC.find("tmpdir creado")
    assert idx_s120 != -1, "S120-A: el bloque de fallback /srv/projects debe existir en api.py"
    assert idx_tmpdir != -1, "api.py debe crear tmpdir cuando directory no se provee (caso desktop)"
    assert idx_s120 < idx_tmpdir, (
        "S120-A: el fallback /srv/projects debe preceder al fallback tmpdir"
    )


# ---------------------------------------------------------------------------
# S120-B — org de validación en migración y seed
# ---------------------------------------------------------------------------

_VAL_ORG = "01KMK160F1TJ807Z0BDSJD504D"
_VAL_PRJ = "PRJ_TURNOS_VAL"


def test_s120b_migration_inserts_validation_org():
    """La migración 0008 debe insertar la org de validación en ovd_orgs."""
    assert _VAL_ORG in _MIGRATION, (
        f"S120-B: migración 0008 debe incluir INSERT de org '{_VAL_ORG}'"
    )
    assert "ovd_orgs" in _MIGRATION, "S120-B: migración debe insertar en tabla ovd_orgs"


def test_s120b_migration_inserts_validation_project():
    """La migración 0008 debe insertar el proyecto de validación en ovd_projects."""
    assert _VAL_PRJ in _MIGRATION, (
        f"S120-B: migración 0008 debe incluir INSERT del proyecto '{_VAL_PRJ}'"
    )
    assert "/srv/projects/turnos-demo" in _MIGRATION, (
        "S120-B: el proyecto de validación debe apuntar a /srv/projects/turnos-demo"
    )


def test_s120b_migration_inserts_stack_profile():
    """La migración 0008 debe insertar el stack profile para el proyecto de validación."""
    assert "STACK_TURNOS_VAL" in _MIGRATION, (
        "S120-B: migración debe incluir INSERT de stack profile STACK_TURNOS_VAL"
    )


def test_s120b_migration_is_idempotent():
    """La migración debe usar ON CONFLICT DO NOTHING para ser idempotente."""
    count = _MIGRATION.count("ON CONFLICT (id) DO NOTHING")
    assert count >= 3, (
        f"S120-B: migración debe tener ON CONFLICT DO NOTHING en los 3 INSERTs (encontrados: {count})"
    )


def test_s120b_migration_revision_chain():
    """La migración 0008 debe referenciar 0007 como down_revision."""
    assert "20260509_0007" in _MIGRATION, (
        "S120-B: down_revision debe apuntar a la migración 0007"
    )


def test_s120b_seed_sql_includes_validation_org():
    """seed_prod.sql debe incluir el INSERT de la org de validación."""
    assert _VAL_ORG in _SEED_SQL, (
        f"S120-B: seed_prod.sql debe incluir INSERT de org '{_VAL_ORG}'"
    )


def test_s120b_seed_sql_includes_validation_project():
    """seed_prod.sql debe incluir el INSERT del proyecto de validación."""
    assert _VAL_PRJ in _SEED_SQL, (
        f"S120-B: seed_prod.sql debe incluir INSERT de proyecto '{_VAL_PRJ}'"
    )


def test_s120b_seed_sql_is_idempotent():
    """seed_prod.sql debe usar ON CONFLICT DO NOTHING para todos los nuevos INSERTs."""
    # Verificar que los nuevos INSERTs del bloque de validación tienen ON CONFLICT
    val_block_start = _SEED_SQL.find(_VAL_ORG)
    val_block = _SEED_SQL[val_block_start:]
    conflicts = val_block.count("ON CONFLICT (id) DO NOTHING")
    assert conflicts >= 3, (
        f"S120-B: seed_prod.sql debe tener ON CONFLICT DO NOTHING para org, proyecto y stack (encontrados: {conflicts})"
    )
