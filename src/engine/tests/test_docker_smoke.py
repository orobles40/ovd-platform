# OVD Platform — Block D: Docker smoke tests
# Verifica que la imagen del engine:
#   1. Se construye sin errores
#   2. El container arranca, ejecuta migraciones y responde /health → 200
#   3. Las tablas de migración existen en la BD
#
# Requiere: Docker daemon corriendo + imagen construible desde Dockerfile
# Ejecutar: pytest -m docker src/engine/tests/test_docker_smoke.py
#
# Marcador: @pytest.mark.docker
# Estos tests NO corren en suite normal (pytest -m "not docker")

import os
import shutil
import subprocess
import time
import urllib.request
import urllib.error
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _docker_available() -> bool:
    return shutil.which("docker") is not None and _cmd_ok(["docker", "info"])


def _cmd_ok(cmd: list[str]) -> bool:
    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=10)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120, **kwargs)


# ---------------------------------------------------------------------------
# Skip si Docker no disponible
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.docker

SKIP_NO_DOCKER = pytest.mark.skipif(
    not _docker_available(),
    reason="Docker daemon no disponible"
)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

IMAGE_TAG   = "ovd-engine:smoke-test"
NET_NAME    = "ovd-smoke-net"
PG_NAME     = "ovd-smoke-pg"
ENGINE_NAME = "ovd-smoke-engine"
PG_PORT     = "15432"   # evitar conflicto con postgres dev (5432)
ENGINE_PORT = "18001"   # evitar conflicto con engine dev (8001)
HEALTH_URL  = f"http://localhost:{ENGINE_PORT}/health"

# Dir raíz del engine (relativo a este archivo)
ENGINE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# ---------------------------------------------------------------------------
# Fixture: ciclo de vida del entorno Docker
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def docker_env():
    """
    Levanta:
      1. Red Docker aislada
      2. Contenedor postgres:16 limpio
      3. Imagen ovd-engine:smoke-test construida desde Dockerfile actual
      4. Contenedor engine con DATABASE_URL apuntando al postgres de smoke

    Yield: dict con info útil para los tests.
    Teardown: destruye todos los recursos creados.
    """
    created: list[str] = []  # recursos a limpiar (en orden inverso)

    def cleanup():
        for name in reversed(created):
            if name.startswith("net:"):
                _run(["docker", "network", "rm", name[4:]])
            elif name.startswith("container:"):
                _run(["docker", "rm", "-f", name[10:]])
            elif name.startswith("image:"):
                _run(["docker", "rmi", "-f", name[6:]])

    try:
        # ── Red ──────────────────────────────────────────────────────────────
        r = _run(["docker", "network", "create", NET_NAME])
        assert r.returncode == 0, f"No se pudo crear la red: {r.stderr}"
        created.append(f"net:{NET_NAME}")

        # ── Postgres ─────────────────────────────────────────────────────────
        r = _run([
            "docker", "run", "-d",
            "--name", PG_NAME,
            "--network", NET_NAME,
            "-e", "POSTGRES_USER=ovd_test",
            "-e", "POSTGRES_PASSWORD=ovd_test_pw",
            "-e", "POSTGRES_DB=ovd_test",
            "-p", f"{PG_PORT}:5432",
            "postgres:16",
        ])
        assert r.returncode == 0, f"No se pudo iniciar postgres: {r.stderr}"
        created.append(f"container:{PG_NAME}")

        # Esperar a que postgres esté listo
        _wait_for_postgres()

        # ── Build engine ─────────────────────────────────────────────────────
        r = _run(
            ["docker", "build", "-t", IMAGE_TAG, "."],
            cwd=ENGINE_DIR,
            timeout=300,
        )
        assert r.returncode == 0, f"Build falló:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}"
        created.append(f"image:{IMAGE_TAG}")

        # ── Engine ───────────────────────────────────────────────────────────
        db_url = f"postgresql://ovd_test:ovd_test_pw@{PG_NAME}:5432/ovd_test"
        r = _run([
            "docker", "run", "-d",
            "--name", ENGINE_NAME,
            "--network", NET_NAME,
            "-e", f"DATABASE_URL={db_url}",
            "-e", "JWT_SECRET=" + ("x" * 64),
            "-e", "ANTHROPIC_API_KEY=sk-ant-smoke-fake",
            "-e", "OVD_ENGINE_SECRET=smoke-secret",
            "-e", "OVD_RAG_ENABLED=false",
            "-p", f"{ENGINE_PORT}:8001",
            IMAGE_TAG,
        ])
        assert r.returncode == 0, f"No se pudo iniciar engine: {r.stderr}"
        created.append(f"container:{ENGINE_NAME}")

        # Esperar /health
        ready = _wait_for_health(HEALTH_URL, timeout=60)
        if not ready:
            logs = _run(["docker", "logs", ENGINE_NAME]).stdout
            pytest.fail(f"Engine no levantó en 60 s. Logs:\n{logs[-3000:]}")

        yield {
            "db_url": db_url,
            "health_url": HEALTH_URL,
            "pg_port": PG_PORT,
        }

    finally:
        cleanup()


# ---------------------------------------------------------------------------
# Utilidades de espera
# ---------------------------------------------------------------------------

def _wait_for_postgres(timeout: int = 30) -> None:
    """Espera hasta que el postgres de smoke acepte conexiones."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = _run([
            "docker", "exec", PG_NAME,
            "pg_isready", "-U", "ovd_test",
        ])
        if r.returncode == 0:
            return
        time.sleep(1)
    raise RuntimeError("Postgres smoke no levantó en tiempo")


def _wait_for_health(url: str, timeout: int = 60) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(2)
    return False


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@SKIP_NO_DOCKER
class TestDockerSmoke:
    def test_health_returns_200(self, docker_env):
        """/health responde HTTP 200."""
        with urllib.request.urlopen(docker_env["health_url"], timeout=5) as resp:
            assert resp.status == 200

    def test_health_json_payload(self, docker_env):
        """/health devuelve status=ok y engine=ovd-engine."""
        import json
        with urllib.request.urlopen(docker_env["health_url"], timeout=5) as resp:
            data = json.loads(resp.read())
        assert data["status"] == "ok"
        assert data["engine"] == "ovd-engine"

    def test_alembic_tables_exist(self, docker_env):
        """Las tablas creadas por las migraciones Alembic existen en la BD."""
        expected = {
            "ovd_orgs",
            "ovd_users",
            "ovd_projects",
            "ovd_stacks",
            "ovd_web_sources",
            "alembic_version",
        }
        existing = _get_pg_tables(docker_env["pg_port"])
        missing = expected - existing
        assert not missing, f"Tablas no encontradas post-migración: {missing}"

    def test_alembic_version_set(self, docker_env):
        """alembic_version contiene la revisión esperada."""
        rev = _get_alembic_revision(docker_env["pg_port"])
        assert rev is not None, "alembic_version está vacía — migraciones no corrieron"
        # Revisión de la primera migración del proyecto
        assert "20260" in rev, f"Revisión inesperada: {rev}"

    def test_container_still_running(self, docker_env):
        """El contenedor engine sigue corriendo (no crasheó tras arrancar)."""
        r = _run(["docker", "inspect", "--format={{.State.Status}}", ENGINE_NAME])
        assert r.returncode == 0
        assert r.stdout.strip() == "running", f"Estado inesperado: {r.stdout.strip()}"


# ---------------------------------------------------------------------------
# Helpers de postgres (conexión directa desde el host vía psql en contenedor)
# ---------------------------------------------------------------------------

def _pg_query(pg_port: str, sql: str) -> str:
    """Ejecuta una consulta SQL y devuelve stdout."""
    r = _run([
        "docker", "exec", PG_NAME,
        "psql", "-U", "ovd_test", "-d", "ovd_test",
        "-t", "-c", sql,
    ])
    return r.stdout.strip()


def _get_pg_tables(pg_port: str) -> set[str]:
    raw = _pg_query(
        pg_port,
        "SELECT tablename FROM pg_tables WHERE schemaname='public';"
    )
    return {line.strip() for line in raw.splitlines() if line.strip()}


def _get_alembic_revision(pg_port: str) -> str | None:
    raw = _pg_query(pg_port, "SELECT version_num FROM alembic_version LIMIT 1;")
    return raw if raw else None
