"""
Tests S72
  S72-A: _normalize_task_signatures inyecta firmas canónicas en task descriptions
  S72-B: postprocess_python_file — rename español→inglés + Pydantic v1→v2
  S72-C: _fix_conftest_mock_order — corrige orden mock oracledb en conftest.py
  S72-E: system_backend_python.md usa DeclarativeBase (SQLAlchemy 2.x)
"""
import pathlib
import sys
import pytest

_ENGINE_DIR = pathlib.Path(__file__).parent.parent
_TEMPLATES_DIR = _ENGINE_DIR / "templates"
_BACKEND_PY = _TEMPLATES_DIR / "system_backend_python.md"

sys.path.insert(0, str(_ENGINE_DIR))

# ---------------------------------------------------------------------------
# S72-A: _normalize_task_signatures
# ---------------------------------------------------------------------------

class TestS72A:
    def _make_sdd(self, description: str, title: str = "") -> dict:
        return {"tasks": [{"agent": "backend", "description": description, "title": title}]}

    def test_injects_validate_rut_for_rut_keyword(self):
        from graph import _normalize_task_signatures
        sdd = self._make_sdd("Implementar validación de rut chileno")
        result = _normalize_task_signatures(sdd)
        desc = result["tasks"][0]["description"]
        assert "validate_rut" in desc
        assert "S72-A" in desc

    def test_injects_is_prime_for_primo_keyword(self):
        from graph import _normalize_task_signatures
        sdd = self._make_sdd("Función que verifica si es primo")
        result = _normalize_task_signatures(sdd)
        desc = result["tasks"][0]["description"]
        assert "is_prime" in desc
        assert "S72-A" in desc

    def test_injects_create_contract_for_crear_contrato(self):
        from graph import _normalize_task_signatures
        sdd = self._make_sdd("Crear contrato para empleado")
        result = _normalize_task_signatures(sdd)
        desc = result["tasks"][0]["description"]
        assert "create_contract" in desc

    def test_no_inject_without_keyword(self):
        from graph import _normalize_task_signatures
        sdd = self._make_sdd("Configurar Docker y CI/CD")
        result = _normalize_task_signatures(sdd)
        desc = result["tasks"][0]["description"]
        assert "S72-A" not in desc

    def test_multiple_keywords_multiple_hints(self):
        from graph import _normalize_task_signatures
        sdd = self._make_sdd("Validar rut y verificar si es primo")
        result = _normalize_task_signatures(sdd)
        desc = result["tasks"][0]["description"]
        assert "validate_rut" in desc
        assert "is_prime" in desc

    def test_calcular_imc_hint(self):
        from graph import _normalize_task_signatures
        sdd = self._make_sdd("Calcular IMC del paciente")
        result = _normalize_task_signatures(sdd)
        desc = result["tasks"][0]["description"]
        assert "calculate_bmi" in desc


# ---------------------------------------------------------------------------
# S72-B: postprocess_python_file — rename
# ---------------------------------------------------------------------------

class TestS72B_Rename:
    def test_rename_validar_rut_def(self):
        from code_postprocessor import postprocess_python_file
        code = "def validar_rut(rut: str) -> bool:\n    return True\n"
        result = postprocess_python_file(code, "src/contracts/service.py")
        assert "def validate_rut" in result
        assert "def validar_rut" not in result

    def test_rename_updates_call_sites(self):
        from code_postprocessor import postprocess_python_file
        code = (
            "def validar_rut(rut: str) -> bool:\n    return True\n\n"
            "if not validar_rut(data.rut):\n    raise ValueError\n"
        )
        result = postprocess_python_file(code, "src/service.py")
        assert "validate_rut" in result
        assert "validar_rut" not in result

    def test_rename_es_primo(self):
        from code_postprocessor import postprocess_python_file
        code = "def es_primo(n: int) -> bool:\n    return n > 1\n"
        result = postprocess_python_file(code, "src/utils.py")
        assert "def is_prime" in result
        assert "def es_primo" not in result

    def test_no_rename_valid_english_name(self):
        from code_postprocessor import postprocess_python_file
        code = "def validate_rut(rut: str) -> bool:\n    return True\n"
        result = postprocess_python_file(code, "src/service.py")
        assert "def validate_rut" in result

    def test_skip_non_python_file(self):
        from code_postprocessor import postprocess_python_file
        content = "name: validar_rut\nvalue: es_primo"
        result = postprocess_python_file(content, "config.yml")
        assert result == content

    def test_skip_empty_content(self):
        from code_postprocessor import postprocess_python_file
        result = postprocess_python_file("", "src/service.py")
        assert result == ""


# ---------------------------------------------------------------------------
# S72-B: postprocess_python_file — Pydantic v1 → v2
# ---------------------------------------------------------------------------

class TestS72B_Pydantic:
    def test_validator_to_field_validator(self):
        from code_postprocessor import postprocess_python_file
        code = (
            "from pydantic import BaseModel, validator\n\n"
            "class Foo(BaseModel):\n"
            "    @validator('x')\n"
            "    def check_x(cls, v):\n"
            "        return v\n"
        )
        result = postprocess_python_file(code, "src/models.py")
        assert "@field_validator('x')" in result
        assert "@validator" not in result

    def test_adds_classmethod_after_field_validator(self):
        from code_postprocessor import postprocess_python_file
        code = (
            "class Foo:\n"
            "    @field_validator('x')\n"
            "    def check_x(cls, v):\n"
            "        return v\n"
        )
        result = postprocess_python_file(code, "src/models.py")
        lines = result.split("\n")
        fv_idx = next(i for i, l in enumerate(lines) if "@field_validator" in l)
        assert "@classmethod" in lines[fv_idx - 1]

    def test_root_validator_to_model_validator(self):
        from code_postprocessor import postprocess_python_file
        code = (
            "from pydantic import BaseModel, root_validator\n\n"
            "class Foo(BaseModel):\n"
            "    @root_validator\n"
            "    def check(cls, values):\n"
            "        return values\n"
        )
        result = postprocess_python_file(code, "src/models.py")
        assert "@model_validator" in result
        assert "@root_validator" not in result

    def test_orm_mode_to_from_attributes(self):
        from code_postprocessor import postprocess_python_file
        code = "class Config:\n    orm_mode = True\n"
        result = postprocess_python_file(code, "src/schemas.py")
        assert "from_attributes = True" in result
        assert "orm_mode" not in result

    def test_no_op_on_v2_code(self):
        from code_postprocessor import postprocess_python_file
        code = (
            "from pydantic import BaseModel, field_validator\n\n"
            "class Foo(BaseModel):\n"
            "    @classmethod\n"
            "    @field_validator('x')\n"
            "    def check_x(cls, v):\n"
            "        return v\n"
        )
        result = postprocess_python_file(code, "src/models.py")
        # Should not add another @classmethod
        assert result.count("@classmethod") == 1

    def test_import_validator_replaced(self):
        from code_postprocessor import postprocess_python_file
        code = "from pydantic import BaseModel, validator\n"
        result = postprocess_python_file(code, "src/models.py")
        assert "field_validator" in result


# ---------------------------------------------------------------------------
# S72-C: conftest.py fix
# ---------------------------------------------------------------------------

class TestS72C:
    def test_fixes_import_oracledb_before_mock(self):
        from code_postprocessor import postprocess_python_file
        code = (
            "import sys\n"
            "import os\n"
            "import oracledb\n"  # INCORRECTO: import antes del mock
            "from unittest.mock import MagicMock\n"
            "sys.modules['oracledb'] = MagicMock()\n"
        )
        result = postprocess_python_file(code, "conftest.py")
        lines = result.split("\n")
        mock_idx = next((i for i, l in enumerate(lines) if "sys.modules['oracledb']" in l), None)
        import_idx = next((i for i, l in enumerate(lines) if "import oracledb" in l and "sys.modules" not in l), None)
        assert mock_idx is not None
        # Si hay import oracledb, el mock debe ir antes
        if import_idx is not None:
            assert mock_idx < import_idx

    def test_no_op_if_already_correct_order(self):
        from code_postprocessor import postprocess_python_file
        code = (
            "import sys\n"
            "from unittest.mock import MagicMock\n"
            "sys.modules['oracledb'] = MagicMock()\n"
            "import oracledb\n"
        )
        result = postprocess_python_file(code, "conftest.py")
        # El mock ya está antes — no debería agregar otro
        assert result.count("sys.modules['oracledb']") == 1

    def test_no_op_without_oracledb(self):
        from code_postprocessor import postprocess_python_file
        code = "import pytest\nimport os\n"
        result = postprocess_python_file(code, "conftest.py")
        assert result == code

    def test_adds_import_pytest_if_missing(self):
        from code_postprocessor import postprocess_python_file
        code = "import oracledb\n\n@pytest.fixture\ndef db(): pass\n"
        result = postprocess_python_file(code, "conftest.py")
        assert "import pytest" in result

    def test_mock_injected_at_top(self):
        from code_postprocessor import postprocess_python_file
        code = "import os\nimport oracledb\n\ndef setup(): pass\n"
        result = postprocess_python_file(code, "conftest.py")
        # El mock debe aparecer en las primeras líneas
        first_50_chars = result[:200]
        assert "sys.modules" in first_50_chars or "MagicMock" in first_50_chars


# ---------------------------------------------------------------------------
# S72-E: system_backend_python.md — SQLAlchemy 2.x
# ---------------------------------------------------------------------------

class TestS72E:
    def test_template_uses_declarative_base_class(self):
        """S72-E: template usa DeclarativeBase class (SQLAlchemy 2.x)."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "DeclarativeBase" in content

    def test_template_no_uses_declarative_base_function(self):
        """S72-E: template no usa declarative_base() como función importada."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "from sqlalchemy.ext.declarative import declarative_base" not in content

    def test_template_uses_mapped_column(self):
        """S72-E: template usa Mapped[] + mapped_column() (SQLAlchemy 2.x typed)."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "mapped_column" in content or "Mapped" in content
