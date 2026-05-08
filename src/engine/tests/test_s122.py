"""Tests S122 — Postprocessor lazy engine + detección mejorada conftest ImportError.

S122-A: _fix_database_module_level_engine reescribe engine module-level a lazy factory en database.py.
S122-B: update_test_retry detecta ImportError conftest→src.main (no solo 'database' en output).
"""

import pathlib
import re
import sys

_ENGINE_ROOT = pathlib.Path(".")
_GRAPH_SRC = (_ENGINE_ROOT / "graph.py").read_text(encoding="utf-8")

sys.path.insert(0, str(_ENGINE_ROOT))
from code_postprocessor import _fix_database_module_level_engine  # noqa: I001


# ---------------------------------------------------------------------------
# Fixtures: contenido típico de database.py generado por el modelo
# ---------------------------------------------------------------------------

_DB_CLASSIC = """\
import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.environ.get("DATABASE_URL", "")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
"""

_DB_WITH_FUTURE = """\
import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.environ.get("DATABASE_URL", "")

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session
"""

_DB_ALREADY_LAZY = """\
import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.environ.get("DATABASE_URL", "")

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(DATABASE_URL, echo=False)
    return _engine


class Base(DeclarativeBase):
    pass
"""


def _get_function_body(src: str, func_name: str) -> str:
    pattern = rf"(?:async )?def {re.escape(func_name)}\b.*?(?=\n(?:async )?def [a-z_]|\Z)"
    m = re.search(pattern, src, re.DOTALL)
    return m.group(0) if m else ""


# ---------------------------------------------------------------------------
# S122-A — _fix_database_module_level_engine
# ---------------------------------------------------------------------------


def test_s122a_rewrites_engine_to_lazy_factory():
    """El postprocessor debe eliminar engine = create_async_engine(...) de nivel módulo."""
    result = _fix_database_module_level_engine(_DB_CLASSIC, "src/database.py")
    assert "engine = create_async_engine(" not in result or "_engine = None" in result
    assert "def get_engine():" in result
    assert "_engine = None" in result


def test_s122a_get_engine_contains_original_call():
    """get_engine() debe contener la llamada original a create_async_engine."""
    result = _fix_database_module_level_engine(_DB_CLASSIC, "src/database.py")
    assert "create_async_engine(DATABASE_URL, echo=False)" in result


def test_s122a_engine_call_inside_function_only():
    """create_async_engine() debe aparecer solo dentro de get_engine(), no a nivel de módulo."""
    result = _fix_database_module_level_engine(_DB_CLASSIC, "src/database.py")
    lines = result.split("\n")
    for i, line in enumerate(lines):
        if "create_async_engine(" in line and not line.strip().startswith("#"):
            # La línea debe estar indentada (dentro de una función)
            assert line.startswith("    ") or line.startswith("\t"), (
                f"create_async_engine encontrado a nivel de módulo en línea {i + 1}: {line!r}"
            )


def test_s122a_rewrites_asyncsessionlocal_to_lazy():
    """AsyncSessionLocal = async_sessionmaker(engine, ...) debe ser reemplazado por lazy factory."""
    result = _fix_database_module_level_engine(_DB_CLASSIC, "src/database.py")
    # No debe quedar la asignación directa a nivel de módulo con engine
    assert "AsyncSessionLocal = async_sessionmaker(engine" not in result
    # Debe haber un lazy pattern para session factory
    assert "_session_factory = None" in result or "get_session_factory" in result


def test_s122a_get_session_uses_lazy_factory():
    """get_session() debe usar la factory lazy, no AsyncSessionLocal() directamente."""
    result = _fix_database_module_level_engine(_DB_CLASSIC, "src/database.py")
    # AsyncSessionLocal() directo debe ser reemplazado
    assert "async with AsyncSessionLocal()" not in result
    # La sesión se crea via factory
    assert "get_session_factory()()" in result or "async_sessionmaker(get_engine()" in result


def test_s122a_preserves_base_class():
    """Base(DeclarativeBase) debe permanecer intacto."""
    result = _fix_database_module_level_engine(_DB_CLASSIC, "src/database.py")
    assert "class Base(DeclarativeBase):" in result


def test_s122a_handles_future_true_variant():
    """Funciona con create_async_engine(DATABASE_URL, echo=False, future=True)."""
    result = _fix_database_module_level_engine(_DB_WITH_FUTURE, "src/database.py")
    assert "def get_engine():" in result
    assert "create_async_engine(DATABASE_URL, echo=False, future=True)" in result


def test_s122a_does_not_apply_to_non_database_files():
    """No debe modificar archivos que no se llamen database.py."""
    result = _fix_database_module_level_engine(_DB_CLASSIC, "src/models.py")
    assert result == _DB_CLASSIC


def test_s122a_does_not_apply_to_already_lazy():
    """No modifica database.py que ya usa patrón lazy."""
    result = _fix_database_module_level_engine(_DB_ALREADY_LAZY, "src/database.py")
    # Si ya tiene get_engine() sin engine module-level, no debe cambiar nada relevante
    assert "def get_engine():" in result


def test_s122a_function_present_in_postprocessor():
    """_fix_database_module_level_engine debe estar definida en code_postprocessor.py."""
    src = (_ENGINE_ROOT / "code_postprocessor.py").read_text(encoding="utf-8")
    assert "_fix_database_module_level_engine" in src, (
        "S122-A: falta _fix_database_module_level_engine en code_postprocessor.py"
    )
    assert "S122-A" in src, "S122-A: falta referencia S122-A en code_postprocessor.py"


def test_s122a_called_from_postprocess_python_file():
    """postprocess_python_file debe llamar a _fix_database_module_level_engine."""
    src = (_ENGINE_ROOT / "code_postprocessor.py").read_text(encoding="utf-8")
    # Buscar dentro de postprocess_python_file
    idx = src.find("def postprocess_python_file(")
    assert idx != -1
    fn_body = src[idx : idx + 6000]
    assert "_fix_database_module_level_engine" in fn_body, (
        "S122-A: postprocess_python_file no llama a _fix_database_module_level_engine"
    )


# ---------------------------------------------------------------------------
# S122-B — Detección mejorada en update_test_retry (src.main en test_output)
# ---------------------------------------------------------------------------


def test_s122b_detection_includes_src_main():
    """update_test_retry debe detectar conftest ImportError cuando 'src.main' está en test_output."""
    body = _get_function_body(_GRAPH_SRC, "update_test_retry")
    assert body, "update_test_retry no encontrada en graph.py"
    assert "src.main" in body or "src/main" in body, (
        "S122-B: falta detección de 'src.main' en _is_conftest_importerror"
    )


def test_s122b_detection_includes_create_async_engine():
    """La detección S122-B también cubre 'create_async_engine' en test_output."""
    body = _get_function_body(_GRAPH_SRC, "update_test_retry")
    assert "create_async_engine" in body, (
        "S122-B: falta 'create_async_engine' como trigger en _is_conftest_importerror"
    )


def test_s122b_hint_mentions_lazy_pattern():
    """El hint S122-B debe mencionar get_engine() y get_session_factory()."""
    body = _get_function_body(_GRAPH_SRC, "update_test_retry")
    idx = body.find("_conftest_import_hint =")
    assert idx != -1, "S122-B: no se encontró asignación de _conftest_import_hint"
    hint_block = body[idx : idx + 1500]
    assert "get_engine" in hint_block, "S122-B: hint debe mencionar get_engine()"
    assert "get_session_factory" in hint_block or "lazy" in hint_block, (
        "S122-B: hint debe mencionar get_session_factory() o lazy factory"
    )


def test_s122b_traceability_comment():
    """El código S122-B debe tener comentario de trazabilidad."""
    body = _get_function_body(_GRAPH_SRC, "update_test_retry")
    assert "S122-B" in body, (
        "S122-B: falta comentario de trazabilidad S122-B en update_test_retry"
    )
