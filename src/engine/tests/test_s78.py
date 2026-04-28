"""
Tests S78 — Template login JWT + stub verifier + naming rules + retry selectivo.

S78-A: system_backend_python.md contiene implementación completa de login (no stub) — 4 tests
S78-B: _verify_no_stub_endpoints — detecta endpoints con pass/... — 6 tests
S78-C: tabla canónica de módulos CRUD de beneficios en template — 4 tests
S78-D: extracción de archivos fallidos de output pytest — 4 tests
"""
import pathlib
import re
import textwrap

import pytest

_ENGINE_DIR = pathlib.Path(__file__).parent.parent
_TEMPLATES_DIR = _ENGINE_DIR / "templates"
_BACKEND_PY = _TEMPLATES_DIR / "system_backend_python.md"


# ---------------------------------------------------------------------------
# S78-A — Template login JWT completo
# ---------------------------------------------------------------------------

class TestS78A:
    def test_template_contiene_jwt_encode(self):
        """S78-A: template debe incluir jwt.encode() para generar tokens."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "jwt.encode" in content

    def test_template_contiene_create_access_token(self):
        """S78-A: template debe definir función _create_access_token o create_access_token."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "create_access_token" in content

    def test_template_prohibe_stub_login(self):
        """S78-A: template debe mencionar prohibición de stub pass/... en login."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "PROHIBIDO" in content or "prohibido" in content
        # El template debe mencionar explícitamente que pass no es válido
        assert "pass" in content or "stub" in content.lower()

    def test_template_contiene_validacion_rut_en_login(self):
        """S78-A: el ejemplo de login debe usar validate_rut para RUT chileno."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "validate_rut" in content
        # La sección de login debe estar cerca de validate_rut
        login_idx = content.find("async def login")
        rut_idx = content.find("validate_rut", login_idx) if login_idx != -1 else -1
        assert login_idx != -1, "No se encontró async def login en el template"
        assert rut_idx != -1, "validate_rut no aparece después de la definición de login"


# ---------------------------------------------------------------------------
# S78-B — _verify_no_stub_endpoints
# ---------------------------------------------------------------------------

class TestS78B:
    def test_detecta_stub_pass_en_login(self, tmp_path):
        """S78-B: detecta async def login(): pass en main.py."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text(
            "from fastapi import FastAPI\napp = FastAPI()\n\n"
            "@app.post('/auth/login')\nasync def login():\n    pass\n",
            encoding="utf-8",
        )
        from graph import _verify_no_stub_endpoints
        ok, feedback = _verify_no_stub_endpoints(str(tmp_path))
        assert not ok
        assert "login" in feedback
        assert "S78-B" in feedback

    def test_detecta_stub_puntos_suspensivos(self, tmp_path):
        """S78-B: detecta async def register(): ... en router.py."""
        (tmp_path / "src" / "auth").mkdir(parents=True)
        (tmp_path / "src" / "auth" / "router.py").write_text(
            "from fastapi import APIRouter\nrouter = APIRouter()\n\n"
            "@router.post('/register')\nasync def register():\n    ...\n",
            encoding="utf-8",
        )
        from graph import _verify_no_stub_endpoints
        ok, feedback = _verify_no_stub_endpoints(str(tmp_path))
        assert not ok
        assert "register" in feedback

    def test_no_op_con_implementacion_real(self, tmp_path):
        """S78-B: no reporta stub cuando el endpoint tiene implementación real."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text(
            "from fastapi import FastAPI\napp = FastAPI()\n\n"
            "@app.post('/auth/login')\nasync def login(body):\n"
            "    user = db.query(User).first()\n"
            "    return {'token': 'jwt'}\n",
            encoding="utf-8",
        )
        from graph import _verify_no_stub_endpoints
        ok, feedback = _verify_no_stub_endpoints(str(tmp_path))
        assert ok
        assert feedback == ""

    def test_no_op_sin_main_py(self, tmp_path):
        """S78-B: retorna ok=True cuando no hay main.py ni router.py."""
        (tmp_path / "src").mkdir()
        from graph import _verify_no_stub_endpoints
        ok, feedback = _verify_no_stub_endpoints(str(tmp_path))
        assert ok

    def test_detecta_multiples_stubs(self, tmp_path):
        """S78-B: detecta múltiples endpoints stub en el mismo archivo."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text(
            "@app.post('/login')\nasync def login():\n    pass\n\n"
            "@app.post('/register')\nasync def register():\n    pass\n",
            encoding="utf-8",
        )
        from graph import _verify_no_stub_endpoints
        ok, feedback = _verify_no_stub_endpoints(str(tmp_path))
        assert not ok
        assert "login" in feedback or "register" in feedback

    def test_feedback_incluye_instruccion_jwt(self, tmp_path):
        """S78-B: el feedback menciona jwt.encode() para orientar la corrección."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text(
            "@app.post('/auth/login')\nasync def login():\n    pass\n",
            encoding="utf-8",
        )
        from graph import _verify_no_stub_endpoints
        ok, feedback = _verify_no_stub_endpoints(str(tmp_path))
        assert not ok
        assert "jwt" in feedback.lower() or "JWT" in feedback


# ---------------------------------------------------------------------------
# S78-C — Tabla canónica de módulos CRUD beneficios en template
# ---------------------------------------------------------------------------

class TestS78C:
    def test_template_incluye_create_benefit_en_service(self):
        """S78-C: template debe mapear create_benefit → src/services/contract_service.py."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "create_benefit" in content
        # Debe aparecer asociado a service, no a models
        idx = content.find("create_benefit")
        context = content[idx:idx + 200]
        assert "service" in context.lower(), f"create_benefit no está asociado a service: {context}"

    def test_template_incluye_list_benefits_en_service(self):
        """S78-C: template debe mapear list_benefits → src/services/contract_service.py."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "list_benefits" in content

    def test_template_prohibe_crud_en_models(self):
        """S78-C: template debe mencionar que CRUD NO va en models.py."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        # Debe haber una regla explícita que prohíba CRUD en models.py
        assert "models.py" in content
        # La regla debe mencionar que CRUD va en service.py
        service_idx = content.find("service.py")
        models_idx = content.find("models.py", service_idx) if service_idx != -1 else -1
        assert models_idx != -1

    def test_template_importacion_correcta_tests(self):
        """S78-C: template debe indicar que tests importan desde services/, no models/."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        # Buscar la regla de import correcto en tests
        assert "from src.services" in content or "services/" in content


# ---------------------------------------------------------------------------
# S78-D — Extracción de archivos fallidos del output pytest
# ---------------------------------------------------------------------------

def _extract_failing_files_s78d(test_output: str) -> list[str]:
    """Mismo patrón que usa update_test_retry S78-D."""
    pattern = re.compile(r'(?:FAILED|ERROR)\s+((?:src|tests)/[\w/]+\.py)')
    return list(set(pattern.findall(test_output)))


class TestS78D:
    def test_extrae_archivo_de_FAILED(self):
        output = "FAILED tests/test_contracts.py::test_create_benefit - AssertionError"
        files = _extract_failing_files_s78d(output)
        assert "tests/test_contracts.py" in files

    def test_extrae_archivo_de_ERROR_coleccion(self):
        output = "ERROR tests/test_auth.py - ImportError: cannot import name 'login'"
        files = _extract_failing_files_s78d(output)
        assert "tests/test_auth.py" in files

    def test_extrae_multiples_archivos(self):
        output = (
            "FAILED tests/test_contracts.py::test_create - AssertionError\n"
            "FAILED tests/test_auth.py::test_login - ImportError\n"
            "ERROR src/services/contract_service.py - SyntaxError\n"
        )
        files = _extract_failing_files_s78d(output)
        assert "tests/test_contracts.py" in files
        assert "tests/test_auth.py" in files
        assert "src/services/contract_service.py" in files

    def test_no_op_sin_archivos_en_output(self):
        output = "E   AssertionError: assert 1 == 2\nSome other line without paths"
        files = _extract_failing_files_s78d(output)
        assert files == []
