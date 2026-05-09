"""Tests S124 — Fix postprocessor test DB imports.

Cubre:
  B1: _UNSAFE_DB_NAMES no incluye get_engine / get_session_factory
  B2: _fix_test_session_usage reemplaza usos residuales + inyecta preamble
  A1: system_backend_python.md no usa create_engine sync en Ejemplo 2
  A2: stack/backend_python.md D6 incluye dependency_override + get_session
"""

import re

import pytest


# ---------------------------------------------------------------------------
# B1 — _UNSAFE_DB_NAMES no debe incluir API público post-S122-A
# ---------------------------------------------------------------------------


def test_unsafe_db_names_excludes_get_engine():
    from code_postprocessor import _UNSAFE_DB_NAMES

    assert "get_engine" not in _UNSAFE_DB_NAMES, (
        "get_engine es API público de src.database post-S122-A y no debe eliminarse de imports"
    )


def test_unsafe_db_names_excludes_get_session_factory():
    from code_postprocessor import _UNSAFE_DB_NAMES

    assert "get_session_factory" not in _UNSAFE_DB_NAMES, (
        "get_session_factory es API público de src.database post-S122-A y no debe eliminarse"
    )


def test_unsafe_db_names_still_blocks_engine_variable():
    from code_postprocessor import _UNSAFE_DB_NAMES

    assert "engine" in _UNSAFE_DB_NAMES
    assert "AsyncSessionLocal" in _UNSAFE_DB_NAMES
    assert "async_session_maker" in _UNSAFE_DB_NAMES
    assert "SessionLocal" in _UNSAFE_DB_NAMES


# ---------------------------------------------------------------------------
# B2 — _fix_test_session_usage
# ---------------------------------------------------------------------------


def _run_session_fix(content: str, rel_path: str = "tests/test_foo.py") -> str:
    from code_postprocessor import _fix_test_session_usage

    return _fix_test_session_usage(content, rel_path)


def test_fix_session_usage_replaces_async_session_local():
    src = (
        "from src.main import app\n"
        "\n"
        "async def test_create(client):\n"
        "    async with AsyncSessionLocal() as session:\n"
        "        result = await session.execute(select(User))\n"
    )
    result = _run_session_fix(src)
    assert "AsyncSessionLocal()" not in result
    assert "_TestSessionFactory()" in result


def test_fix_session_usage_replaces_async_session_maker():
    src = (
        "async def test_foo():\n"
        "    async with async_session_maker() as s:\n"
        "        pass\n"
    )
    result = _run_session_fix(src)
    assert "async_session_maker()" not in result
    assert "_TestSessionFactory()" in result


def test_fix_session_usage_replaces_session_local():
    src = "session = SessionLocal()\n"
    result = _run_session_fix(src)
    assert "SessionLocal()" not in result
    assert "_TestSessionFactory()" in result


def test_fix_session_usage_injects_preamble_when_no_engine():
    src = (
        "from src.main import app\n"
        "\n"
        "async def test_foo():\n"
        "    async with AsyncSessionLocal() as s:\n"
        "        pass\n"
    )
    result = _run_session_fix(src)
    assert "create_async_engine" in result
    assert "_TestSessionFactory" in result
    assert "sqlite+aiosqlite" in result


def test_fix_session_usage_no_preamble_when_engine_present():
    src = (
        "from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker\n"
        "_test_engine = create_async_engine('sqlite+aiosqlite://')\n"
        "_TestSessionFactory = async_sessionmaker(_test_engine)\n"
        "\n"
        "async def test_foo():\n"
        "    async with AsyncSessionLocal() as s:\n"
        "        pass\n"
    )
    original_count = src.count("create_async_engine")
    result = _run_session_fix(src)
    # create_async_engine ya está — no debe inyectarse el preamble (conteo igual)
    assert result.count("create_async_engine") == original_count, (
        "El preamble fue inyectado aunque create_async_engine ya estaba presente"
    )
    assert "_TestSessionFactory()" in result
    assert "# S124-B: engine SQLite" not in result


def test_fix_session_usage_no_change_when_no_residual():
    src = (
        "from src.main import app\n"
        "\n"
        "async def test_foo(client):\n"
        "    resp = await client.get('/health')\n"
        "    assert resp.status_code == 200\n"
    )
    result = _run_session_fix(src)
    assert result == src


def test_fix_session_usage_skips_non_test_file():
    src = "async with AsyncSessionLocal() as s:\n    pass\n"
    result = _run_session_fix(src, rel_path="src/services.py")
    assert result == src


def test_fix_session_usage_called_from_postprocess_python_file():
    """B2 está integrado en el pipeline principal."""
    from code_postprocessor import postprocess_python_file

    src = (
        "from src.database import Base\n"
        "from src.main import app\n"
        "\n"
        "async def test_create():\n"
        "    async with AsyncSessionLocal() as s:\n"
        "        pass\n"
    )
    result = postprocess_python_file(src, "tests/test_foo.py")
    assert "AsyncSessionLocal()" not in result
    assert "_TestSessionFactory()" in result


# ---------------------------------------------------------------------------
# A1 — system_backend_python.md no usa patrón sync en Ejemplo 2
# ---------------------------------------------------------------------------


def _load_system_backend() -> str:
    import os

    path = os.path.join(
        os.path.dirname(__file__),
        "../templates/system_backend_python.md",
    )
    with open(path, encoding="utf-8") as f:
        return f.read()


def test_system_backend_ejemplo2_no_sync_create_engine():
    content = _load_system_backend()
    # Buscar el bloque Ejemplo 2 y verificar que NO usa create_engine (sync)
    m = re.search(r"Ejemplo 2.*?```python(.*?)```", content, re.DOTALL)
    assert m, "Ejemplo 2 no encontrado en system_backend_python.md"
    example_code = m.group(1)
    assert "create_engine(" not in example_code, (
        "Ejemplo 2 usa create_engine sync — debe usar create_async_engine"
    )
    assert "create_async_engine" in example_code


def test_system_backend_ejemplo2_no_from_database_get_db():
    content = _load_system_backend()
    m = re.search(r"Ejemplo 2.*?```python(.*?)```", content, re.DOTALL)
    assert m
    example_code = m.group(1)
    assert "from src.database import Base, get_db" not in example_code, (
        "Ejemplo 2 importa get_db de src.database — contradice D6"
    )


def test_system_backend_ejemplo2_uses_async_client():
    content = _load_system_backend()
    m = re.search(r"Ejemplo 2.*?```python(.*?)```", content, re.DOTALL)
    assert m
    example_code = m.group(1)
    assert "AsyncClient" in example_code
    assert "ASGITransport" in example_code


# ---------------------------------------------------------------------------
# A2 — stack/backend_python.md D6 incluye dependency_override
# ---------------------------------------------------------------------------


def _load_stack_backend() -> str:
    import os

    path = os.path.join(
        os.path.dirname(__file__),
        "../templates/stack/backend_python.md",
    )
    with open(path, encoding="utf-8") as f:
        return f.read()


def test_d6_includes_dependency_override():
    content = _load_stack_backend()
    assert "dependency_overrides" in content, (
        "D6 debe mostrar app.dependency_overrides para conectar engine de test con la app"
    )


def test_d6_includes_get_session_import():
    content = _load_stack_backend()
    assert "get_session" in content, (
        "D6 debe mostrar que get_session (función generadora) es importable desde src.database"
    )


def test_d6_includes_override_clear():
    content = _load_stack_backend()
    assert "dependency_overrides.clear()" in content, (
        "D6 debe incluir dependency_overrides.clear() para no contaminar otros tests"
    )


def test_d6_mentions_dispose():
    content = _load_stack_backend()
    assert "dispose()" in content, (
        "D6 debe llamar await engine.dispose() al teardown para liberar conexiones"
    )
