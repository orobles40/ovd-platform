"""
Tests S73
  S73-A: _fix_sqlalchemy_v1 — convierte declarative_base() → DeclarativeBase class
  S73-B: conftest.py retry preserva mock oracledb con import sys
  S73-E: template incluye validate_rut con formato puntos
"""

import pathlib
import sys

import pytest

_ENGINE_DIR = pathlib.Path(__file__).parent.parent
_TEMPLATES_DIR = _ENGINE_DIR / "templates"
_BACKEND_PY = _TEMPLATES_DIR / "system_backend_python.md"

sys.path.insert(0, str(_ENGINE_DIR))


# ---------------------------------------------------------------------------
# S73-A: _fix_sqlalchemy_v1
# ---------------------------------------------------------------------------


class TestS73A:
    def test_replaces_declarative_base_import(self):
        from code_postprocessor import postprocess_python_file

        code = "from sqlalchemy.ext.declarative import declarative_base\n"
        result = postprocess_python_file(code, "src/database.py")
        assert "DeclarativeBase" in result
        assert "declarative_base" not in result

    def test_converts_base_assignment_to_class(self):
        from code_postprocessor import postprocess_python_file

        code = (
            "from sqlalchemy.ext.declarative import declarative_base\n"
            "Base = declarative_base()\n"
        )
        result = postprocess_python_file(code, "src/database.py")
        assert "class Base(DeclarativeBase):" in result
        assert "declarative_base()" not in result

    def test_no_op_if_already_v2(self):
        from code_postprocessor import postprocess_python_file

        code = (
            "from sqlalchemy.orm import DeclarativeBase\n\n"
            "class Base(DeclarativeBase):\n    pass\n"
        )
        result = postprocess_python_file(code, "src/database.py")
        # ast.unparse normaliza whitespace — verificar contenido, no formato exacto
        assert "DeclarativeBase" in result
        assert "declarative_base" not in result
        assert "class Base(DeclarativeBase)" in result

    def test_no_op_without_declarative_base(self):
        from code_postprocessor import postprocess_python_file

        code = "from sqlalchemy.orm import Session\n\nengine = create_engine(url)\n"
        result = postprocess_python_file(code, "src/database.py")
        # sin declarative_base — no debe agregar DeclarativeBase
        assert "DeclarativeBase" not in result
        assert "declarative_base" not in result

    def test_full_database_py_conversion(self):
        from code_postprocessor import postprocess_python_file

        code = (
            "import os\n"
            "from sqlalchemy import create_engine\n"
            "from sqlalchemy.orm import Session\n"
            "from sqlalchemy.ext.declarative import declarative_base\n\n"
            "engine = create_engine(os.environ['DATABASE_URL'])\n"
            "Base = declarative_base()\n\n"
            "def get_session():\n"
            "    with Session(engine) as s:\n"
            "        yield s\n"
        )
        result = postprocess_python_file(code, "src/database.py")
        assert "class Base(DeclarativeBase):" in result
        assert "from sqlalchemy.orm import DeclarativeBase" in result
        assert "declarative_base()" not in result
        assert "from sqlalchemy.ext.declarative" not in result

    def test_skip_non_python_file(self):
        from code_postprocessor import postprocess_python_file

        content = "Base = declarative_base()"
        result = postprocess_python_file(content, "config.yml")
        assert result == content


# ---------------------------------------------------------------------------
# S73-E: template validate_rut formato puntos
# ---------------------------------------------------------------------------


class TestS73E:
    def test_template_includes_dots_format_as_valid(self):
        """S73-E: template indica que 12.345.678-5 con puntos es VÁLIDO."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert (
            "validate_rut('12.345.678-5') == True" in content
            or 'validate_rut("12.345.678-5") == True' in content
        )

    def test_template_does_not_mark_dots_format_as_invalid(self):
        """S73-E: template NO debe tener assert con puntos == False."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        # No debe existir este patrón incorrecto
        assert (
            "validate_rut('12.345.678" not in content
            or "== False" not in content.split("validate_rut('12.345.678")[1][:30]
            if "validate_rut('12.345.678" in content
            else True
        )

    def test_template_includes_without_dots_format(self):
        """S73-E: template también incluye formato sin puntos."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert (
            "validate_rut('12345678" in content or 'validate_rut("12345678' in content
        )
