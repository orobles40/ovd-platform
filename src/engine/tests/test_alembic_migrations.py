"""
OVD Platform — Tests de integración: migraciones Alembic (Bloque B)
Requiere: PostgreSQL real en TEST_DATABASE_URL (o ovd_dev local)

Cubre:
  - upgrade head crea todas las tablas esperadas
  - downgrade base elimina todas las tablas
  - re-upgrade después de downgrade es idempotente
  - la migración web_sources (20260412_0001) crea tabla ovd_web_sources

Para ejecutar:
    pytest tests/test_alembic_migrations.py -m integration -v
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import subprocess
import pytest
import psycopg

# BD de test aislada — se usa ovd_dev que ya existe en el entorno local
_TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://ovd_dev:changeme@localhost:5432/ovd_dev",
)

# Tablas que debe crear la migración inicial (20260101_0000)
_EXPECTED_TABLES = {
    "ovd_orgs",
    "ovd_users",
    "ovd_projects",
    "ovd_stack_profiles",
    "ovd_cycles",
    "ovd_refresh_tokens",
    "ovd_rag_embeddings",
    "ovd_audit_log",
}


def _alembic(cmd: list[str]) -> subprocess.CompletedProcess:
    """Ejecuta un comando alembic apuntando a _TEST_DB_URL."""
    env = {**os.environ, "DATABASE_URL": _TEST_DB_URL}
    # Ejecutar desde el directorio engine donde vive alembic.ini
    engine_dir = os.path.join(os.path.dirname(__file__), "..")
    return subprocess.run(
        [sys.executable, "-m", "alembic"] + cmd,
        cwd=engine_dir,
        env=env,
        capture_output=True,
        text=True,
    )


def _existing_tables() -> set[str]:
    """Retorna el conjunto de tablas ovd_* que existen actualmente en la BD."""
    with psycopg.connect(_TEST_DB_URL) as conn:
        rows = conn.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name LIKE 'ovd_%'
            """,
        ).fetchall()
    return {r[0] for r in rows}


def _alembic_current_revision() -> str:
    """Retorna la revisión actual del alembic_version."""
    try:
        with psycopg.connect(_TEST_DB_URL) as conn:
            row = conn.execute("SELECT version_num FROM alembic_version LIMIT 1").fetchone()
        return row[0] if row else ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestAlembicUpgrade:
    def test_upgrade_head_exitoso(self):
        """alembic upgrade head debe retornar exit code 0."""
        result = _alembic(["upgrade", "head"])
        assert result.returncode == 0, (
            f"alembic upgrade head falló:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )

    def test_tablas_principales_existen_post_upgrade(self):
        """Después de upgrade head, todas las tablas base deben existir."""
        _alembic(["upgrade", "head"])
        tables = _existing_tables()
        missing = _EXPECTED_TABLES - tables
        assert not missing, f"Tablas faltantes después de upgrade: {missing}"

    def test_revision_actual_es_head(self):
        """La revisión alembic debe ser la más reciente (web_sources)."""
        _alembic(["upgrade", "head"])
        rev = _alembic_current_revision()
        assert rev == "20260412_0001", (
            f"Se esperaba revisión '20260412_0001', se obtuvo '{rev}'"
        )

    def test_upgrade_idempotente_segunda_vez(self):
        """Ejecutar upgrade head dos veces no debe fallar."""
        r1 = _alembic(["upgrade", "head"])
        r2 = _alembic(["upgrade", "head"])
        assert r1.returncode == 0
        assert r2.returncode == 0

    def test_tabla_web_sources_existe(self):
        """La migración 20260412_0001 debe crear ovd_web_sources."""
        _alembic(["upgrade", "head"])
        tables = _existing_tables()
        assert "ovd_web_sources" in tables, (
            "ovd_web_sources no fue creada por la migración 20260412_0001"
        )


@pytest.mark.integration
class TestAlembicDowngrade:
    def test_downgrade_a_base_exitoso(self):
        """alembic downgrade base debe retornar exit code 0."""
        _alembic(["upgrade", "head"])
        result = _alembic(["downgrade", "base"])
        assert result.returncode == 0, (
            f"alembic downgrade base falló:\nSTDERR: {result.stderr}"
        )

    def test_tablas_eliminadas_post_downgrade(self):
        """Después de downgrade base, las tablas creadas por la migración no deben existir."""
        _alembic(["upgrade", "head"])
        _alembic(["downgrade", "base"])
        tables = _existing_tables()
        # Solo verificar tablas que el downgrade() de la migración elimina explícitamente
        migration_tables = _EXPECTED_TABLES | {"ovd_web_sources"}
        remaining = migration_tables & tables
        assert not remaining, (
            f"Tablas de la migración que debieron eliminarse siguen existiendo: {remaining}"
        )

    def test_re_upgrade_despues_de_downgrade(self):
        """upgrade → downgrade → upgrade debe dejar las tablas completas."""
        _alembic(["upgrade", "head"])
        _alembic(["downgrade", "base"])
        result = _alembic(["upgrade", "head"])
        assert result.returncode == 0

        tables = _existing_tables()
        missing = _EXPECTED_TABLES - tables
        assert not missing, f"Re-upgrade incompleto, tablas faltantes: {missing}"

    def test_revision_vacia_post_downgrade(self):
        """Después de downgrade base, alembic_version no debe tener filas."""
        _alembic(["upgrade", "head"])
        _alembic(["downgrade", "base"])
        # Puede que alembic_version ni exista, o exista vacía
        try:
            with psycopg.connect(_TEST_DB_URL) as conn:
                row = conn.execute("SELECT COUNT(*) FROM alembic_version").fetchone()
            assert row[0] == 0
        except psycopg.errors.UndefinedTable:
            pass  # tabla eliminada — también correcto


@pytest.mark.integration
class TestSeedIdempotencia:
    """
    Verifica que seed_prod.sql es idempotente:
    ejecutado múltiples veces no falla ni duplica datos.
    """

    def _run_seed(self) -> subprocess.CompletedProcess:
        seed_path = os.path.join(
            os.path.dirname(__file__), "..", "migrations", "seed_prod.sql"
        )
        return subprocess.run(
            ["psql", _TEST_DB_URL, "-f", seed_path, "-v", "ON_ERROR_STOP=1"],
            capture_output=True,
            text=True,
        )

    def test_seed_primera_vez_exitoso(self):
        _alembic(["upgrade", "head"])
        result = self._run_seed()
        assert result.returncode == 0, (
            f"seed_prod.sql falló en primera ejecución:\n{result.stderr}"
        )

    def test_seed_segunda_vez_idempotente(self):
        _alembic(["upgrade", "head"])
        self._run_seed()
        result = self._run_seed()
        assert result.returncode == 0, (
            f"seed_prod.sql no es idempotente (falló en segunda ejecución):\n{result.stderr}"
        )

    def test_seed_no_duplica_org(self):
        _alembic(["upgrade", "head"])
        self._run_seed()
        self._run_seed()
        with psycopg.connect(_TEST_DB_URL) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM ovd_orgs WHERE id = 'ORG_OMAR_ROBLES'"
            ).fetchone()[0]
        assert count == 1, f"seed duplicó ovd_orgs — se encontraron {count} filas"

    def test_seed_no_duplica_usuario_admin(self):
        _alembic(["upgrade", "head"])
        self._run_seed()
        self._run_seed()
        with psycopg.connect(_TEST_DB_URL) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM ovd_users WHERE id = 'USR_OMAR_01'"
            ).fetchone()[0]
        assert count == 1, f"seed duplicó ovd_users — se encontraron {count} filas"

    def test_seed_no_duplica_proyecto(self):
        _alembic(["upgrade", "head"])
        self._run_seed()
        self._run_seed()
        with psycopg.connect(_TEST_DB_URL) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM ovd_projects WHERE id = '58D83075CED34A57B22EAFACC1'"
            ).fetchone()[0]
        assert count == 1, f"seed duplicó ovd_projects — se encontraron {count} filas"
