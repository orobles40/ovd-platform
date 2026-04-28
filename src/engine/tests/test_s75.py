"""
Tests S75
  S75-A: _fix_function_import_shadowing — elimina FunctionDef de módulo que
         redefine un import con wrapper trivial (previene RecursionError).
  S75-B: template system_backend_python.md incluye requirements completo.
  S75-C: template prohíbe imports de .models que no existen en el SDD.
"""
import pathlib
import sys

_ENGINE_DIR = pathlib.Path(__file__).parent.parent
_TEMPLATES_DIR = _ENGINE_DIR / "templates"
_BACKEND_PY = _TEMPLATES_DIR / "system_backend_python.md"

sys.path.insert(0, str(_ENGINE_DIR))


# ---------------------------------------------------------------------------
# S75-A: _fix_function_import_shadowing
# ---------------------------------------------------------------------------

class TestS75A:
    def _fix(self, code: str) -> str:
        from code_postprocessor import _fix_function_import_shadowing
        return _fix_function_import_shadowing(code)

    def test_removes_trivial_wrapper(self):
        """def validate_rut(): return validate_rut() debe eliminarse — usa import directo."""
        code = (
            "from src.utils.rut_validator import validate_rut\n\n"
            "def validate_rut(rut: str) -> bool:\n"
            "    return validate_rut(rut)\n"
        )
        result = self._fix(code)
        assert "def validate_rut" not in result
        assert "from src.utils.rut_validator import validate_rut" in result

    def test_removes_multiple_wrappers(self):
        """Múltiples wrappers triviales en el mismo módulo deben eliminarse."""
        code = (
            "from src.utils.rut_validator import validate_rut\n"
            "from src.utils.prime_validator import is_prime\n\n"
            "def validate_rut(rut: str) -> bool:\n"
            "    return validate_rut(rut)\n\n"
            "def is_prime(n: int) -> bool:\n"
            "    return is_prime(n)\n\n"
            "def create_contract(data): pass\n"
        )
        result = self._fix(code)
        assert "def validate_rut" not in result
        assert "def is_prime" not in result
        assert "def create_contract" in result  # función no-wrapper se preserva

    def test_preserves_nontrivial_function(self):
        """Función con lógica adicional no debe eliminarse."""
        code = (
            "from src.utils.rut_validator import validate_rut\n\n"
            "def validate_rut(rut: str) -> bool:\n"
            "    if not rut:\n"
            "        return False\n"
            "    return validate_rut(rut)\n"
        )
        result = self._fix(code)
        assert "def validate_rut" in result  # tiene lógica adicional → preservar

    def test_preserves_function_with_different_name(self):
        """Función con nombre distinto al import no se toca."""
        code = (
            "from src.utils.rut_validator import validate_rut\n\n"
            "def check_rut(rut: str) -> bool:\n"
            "    return validate_rut(rut)\n"
        )
        result = self._fix(code)
        assert "def check_rut" in result

    def test_removes_async_wrapper(self):
        """Wrapper async trivial también se elimina."""
        code = (
            "from src.utils.helper import helper_fn\n\n"
            "async def helper_fn(x):\n"
            "    return helper_fn(x)\n"
        )
        result = self._fix(code)
        assert "async def helper_fn" not in result
        assert "from src.utils.helper import helper_fn" in result

    def test_no_op_without_shadow(self):
        """Sin shadowing — código no cambia."""
        code = (
            "from src.utils.rut_validator import validate_rut\n\n"
            "def format_rut(rut: str) -> str:\n"
            "    return rut.replace('.', '')\n"
        )
        result = self._fix(code)
        assert result == code

    def test_syntax_error_returns_original(self):
        """Código con SyntaxError se retorna sin cambios."""
        code = "esto no es python válido !!!"
        result = self._fix(code)
        assert result == code

    def test_integration_service_py_pattern(self):
        """Simula el patrón exacto de contracts/service.py del ciclo S74."""
        code = (
            "from typing import Dict, Any\n"
            "from sqlalchemy.orm import Session\n"
            "from src.utils.rut_validator import validate_rut\n"
            "from src.utils.prime_validator import is_prime\n\n"
            "def validate_rut(rut: str) -> bool:\n"
            "    return validate_rut(rut)\n\n"
            "def is_prime(n: int) -> bool:\n"
            "    return is_prime(n)\n\n"
            "def create_contract(data: Dict, user: Dict, db: Session):\n"
            "    if not validate_rut(data['rut']):\n"
            "        raise ValueError('RUT inválido')\n"
            "    return {}\n"
        )
        result = self._fix(code)
        assert "def validate_rut" not in result
        assert "def is_prime" not in result
        assert "def create_contract" in result  # función real preservada
        assert "from src.utils.rut_validator import validate_rut" in result
        assert "from src.utils.prime_validator import is_prime" in result

    def test_wrapper_with_type_annotations(self):
        """Wrapper con anotaciones de tipo también se detecta y elimina."""
        code = (
            "from utils import compute\n\n"
            "def compute(x: int) -> int:\n"
            "    return compute(x)\n"
        )
        result = self._fix(code)
        assert "def compute" not in result

    def test_no_false_positive_when_no_imports(self):
        """Sin imports, funciones se preservan aunque sean recursivas."""
        code = (
            "def fibonacci(n: int) -> int:\n"
            "    if n <= 1:\n"
            "        return n\n"
            "    return fibonacci(n - 1) + fibonacci(n - 2)\n"
        )
        result = self._fix(code)
        assert "def fibonacci" in result  # recursión legítima, no shadowing


# ---------------------------------------------------------------------------
# S75-B: requirements.txt completo en template
# ---------------------------------------------------------------------------

class TestS75B:
    def test_template_has_passlib_requirement(self):
        """S75-B: template menciona passlib[bcrypt] en requirements.txt."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "passlib[bcrypt]" in content

    def test_template_has_python_jose_requirement(self):
        """S75-B: template menciona python-jose[cryptography] en requirements."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "python-jose[cryptography]" in content

    def test_template_has_httpx_requirement(self):
        """S75-B: template menciona httpx (requerido para TestClient async)."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "httpx" in content

    def test_template_has_pytest_asyncio(self):
        """S75-B: template menciona pytest-asyncio."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "pytest-asyncio" in content


# ---------------------------------------------------------------------------
# S75-C: regla imports .models en template
# ---------------------------------------------------------------------------

class TestS75C:
    def test_template_prohibits_phantom_models_import(self):
        """S75-C: template advierte sobre from src.X.models import sin models.py en SDD."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "models.py" in content
        assert "SDD" in content
        # La regla debe mencionar la prohibición
        assert "PROHIBIDO" in content or "prohibido" in content.lower() or "solo si" in content.lower()

    def test_template_shows_correct_import_pattern(self):
        """S75-C: template muestra alternativa correcta para imports desde __init__.py."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        # Debe mostrar el patrón correcto: from src.contracts import X
        assert "from src.contracts import" in content or "from src.<paquete> import" in content.lower()

    def test_template_has_s75a_antipattern_warning(self):
        """S75-A: template advierte contra def fn(): return fn() (RecursionError)."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "RecursionError" in content
        assert "S75-A" in content
