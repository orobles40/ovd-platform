"""Tests S123 — Fix test files que importan desde src.database.

S123-A: backend_python.md prohíbe from src.database import <sesiones/engine> en tests.
S123-B: _fix_test_database_imports elimina esos imports automáticamente (excepto Base).
"""

import pathlib
import sys

_ENGINE_ROOT = pathlib.Path(".")
_BACKEND_PY_MD = (_ENGINE_ROOT / "templates" / "stack" / "backend_python.md").read_text(
    encoding="utf-8"
)

sys.path.insert(0, str(_ENGINE_ROOT))
from code_postprocessor import _fix_test_database_imports  # noqa: I001


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TEST_WITH_SESSION_FACTORY = """\
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import Base, async_session_maker
from src.main import app

@pytest.fixture
async def client():
    pass
"""

_TEST_WITH_ASYNCSESSIONLOCAL = """\
import pytest
from src.database import Base, AsyncSessionLocal
from httpx import AsyncClient, ASGITransport
from src.main import app

async def test_foo(client):
    async with AsyncSessionLocal() as session:
        pass
"""

_TEST_WITH_ENGINE = """\
import pytest
from src.database import engine, Base
from src.main import app
"""

_TEST_ONLY_BASE = """\
import pytest
from src.database import Base
from src.main import app
"""

_TEST_MULTIPLE_UNSAFE = """\
from src.database import Base, AsyncSessionLocal, async_session_factory, engine
from src.main import app
"""

_NON_TEST_FILE = """\
from src.database import AsyncSessionLocal
from src.main import app
"""


# ---------------------------------------------------------------------------
# S123-A — Regla en backend_python.md
# ---------------------------------------------------------------------------


def test_s123a_rule_present_in_backend_python_md():
    """backend_python.md debe tener sección S123-A."""
    assert "S123-A" in _BACKEND_PY_MD, (
        "S123-A: falta referencia S123-A en backend_python.md"
    )


def test_s123a_prohibits_session_factory_import():
    """backend_python.md debe prohibir async_session_maker/AsyncSessionLocal en tests."""
    assert (
        "async_session_maker" in _BACKEND_PY_MD or "AsyncSessionLocal" in _BACKEND_PY_MD
    ), "S123-A: debe mostrar los imports prohibidos"
    assert "PROHIBIDO" in _BACKEND_PY_MD or "NUNCA" in _BACKEND_PY_MD


def test_s123a_shows_sqlite_inmemory_pattern():
    """backend_python.md debe mostrar SQLite in-memory como patrón correcto."""
    assert "sqlite+aiosqlite://" in _BACKEND_PY_MD, (
        "S123-A: debe mostrar sqlite+aiosqlite:// como URL de test"
    )


def test_s123a_shows_own_engine_fixture():
    """backend_python.md debe mostrar fixture con engine propio para tests."""
    assert "create_async_engine" in _BACKEND_PY_MD
    assert "setup_db" in _BACKEND_PY_MD or "TEST_DATABASE_URL" in _BACKEND_PY_MD, (
        "S123-A: debe mostrar patrón de fixture con engine propio"
    )


def test_s123a_base_import_allowed():
    """backend_python.md debe indicar que Base sí puede importarse de src.database."""
    assert "from src.database import Base" in _BACKEND_PY_MD, (
        "S123-A: debe mostrar que Base es el único import permitido"
    )


# ---------------------------------------------------------------------------
# S123-B — _fix_test_database_imports
# ---------------------------------------------------------------------------


def test_s123b_removes_async_session_maker():
    """Elimina async_session_maker de imports src.database en test files."""
    result = _fix_test_database_imports(_TEST_WITH_SESSION_FACTORY, "tests/test_foo.py")
    assert "async_session_maker" not in result
    assert "from src.database import Base" in result


def test_s123b_removes_asyncsessionlocal():
    """Elimina AsyncSessionLocal del import de src.database en test files."""
    result = _fix_test_database_imports(
        _TEST_WITH_ASYNCSESSIONLOCAL, "tests/test_foo.py"
    )
    # El import debe eliminarse (no debe quedar la línea from src.database import ... AsyncSessionLocal)
    assert (
        "from src.database import" not in result
        or "AsyncSessionLocal"
        not in result.split("from src.database import")[-1].split("\n")[0]
    )
    assert "from src.database import Base" in result


def test_s123b_removes_engine():
    """Elimina engine de imports src.database en test files."""
    result = _fix_test_database_imports(_TEST_WITH_ENGINE, "tests/test_foo.py")
    assert "from src.database import engine" not in result
    assert "from src.database import Base" in result


def test_s123b_keeps_base_import():
    """Mantiene 'from src.database import Base' intacto."""
    result = _fix_test_database_imports(_TEST_ONLY_BASE, "tests/test_foo.py")
    assert "from src.database import Base" in result
    assert result == _TEST_ONLY_BASE


def test_s123b_removes_multiple_unsafe_keeps_base():
    """Elimina todos los imports no seguros y mantiene Base."""
    result = _fix_test_database_imports(_TEST_MULTIPLE_UNSAFE, "tests/test_foo.py")
    assert "AsyncSessionLocal" not in result
    assert "async_session_factory" not in result
    assert "engine" not in result
    assert "from src.database import Base" in result


def test_s123b_does_not_apply_to_non_test_files():
    """No modifica archivos fuera de tests/ ni con nombre test_*."""
    result = _fix_test_database_imports(_NON_TEST_FILE, "src/services.py")
    assert result == _NON_TEST_FILE


def test_s123b_applies_to_test_prefix_files():
    """Se aplica a archivos con prefijo test_ aunque no estén en tests/."""
    result = _fix_test_database_imports(_TEST_WITH_SESSION_FACTORY, "test_foo.py")
    assert "async_session_maker" not in result


def test_s123b_function_present_in_postprocessor():
    """_fix_test_database_imports debe estar definida en code_postprocessor.py."""
    src = (_ENGINE_ROOT / "code_postprocessor.py").read_text(encoding="utf-8")
    assert "_fix_test_database_imports" in src, (
        "S123-B: falta _fix_test_database_imports en code_postprocessor.py"
    )
    assert "S123-B" in src, "S123-B: falta referencia S123-B en code_postprocessor.py"


def test_s123b_called_from_postprocess_python_file():
    """postprocess_python_file debe llamar a _fix_test_database_imports."""
    src = (_ENGINE_ROOT / "code_postprocessor.py").read_text(encoding="utf-8")
    idx = src.find("def postprocess_python_file(")
    assert idx != -1
    fn_body = src[idx : idx + 6000]
    assert "_fix_test_database_imports" in fn_body, (
        "S123-B: postprocess_python_file no llama a _fix_test_database_imports"
    )
