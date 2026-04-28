"""
Tests S74
  S74-A: _fix_local_variable_shadowing — renombra vars locales que shadowean funciones del módulo
  S74-B: _ensure_test_task — inyecta TASK-INFRA-TESTS + few-shot en template
  S74-C: qa_review — context API-only flag
  S74-D: _warn_hardcoded_secrets — detecta secretos hardcoded y SHA-256
  S74-E: template system_backend_python.md incluye passlib/bcrypt
"""
import pathlib
import sys
import logging

_ENGINE_DIR = pathlib.Path(__file__).parent.parent
_TEMPLATES_DIR = _ENGINE_DIR / "templates"
_BACKEND_PY = _TEMPLATES_DIR / "system_backend_python.md"

sys.path.insert(0, str(_ENGINE_DIR))


# ---------------------------------------------------------------------------
# S74-A: _fix_local_variable_shadowing
# ---------------------------------------------------------------------------

class TestS74A:
    def _fix(self, code: str) -> str:
        from code_postprocessor import _fix_local_variable_shadowing
        return _fix_local_variable_shadowing(code)

    def test_fix_shadow_basic(self):
        """clean_rut = clean_rut(rut) debe renombrarse a _clean_rut_val."""
        code = (
            "def clean_rut(rut: str) -> str:\n"
            "    return rut.replace('.', '')\n\n"
            "def validate_rut(rut: str) -> bool:\n"
            "    clean_rut = clean_rut(rut)\n"
            "    return len(clean_rut) > 1\n"
        )
        result = self._fix(code)
        assert "_clean_rut_val" in result
        assert "clean_rut = clean_rut(rut)" not in result

    def test_fix_shadow_multiple(self):
        """Múltiples shadows en el mismo módulo deben corregirse."""
        code = (
            "def helper_a(x): return x\n"
            "def helper_b(x): return x\n\n"
            "def main():\n"
            "    helper_a = helper_a(1)\n"
            "    helper_b = helper_b(2)\n"
            "    return helper_a, helper_b\n"
        )
        result = self._fix(code)
        assert "_helper_a_val" in result
        assert "_helper_b_val" in result

    def test_no_op_without_shadow(self):
        """Sin shadowing — código no cambia en contenido relevante."""
        code = (
            "def clean_rut(rut: str) -> str:\n"
            "    return rut.replace('.', '')\n\n"
            "def validate_rut(rut: str) -> bool:\n"
            "    cleaned = clean_rut(rut)\n"
            "    return len(cleaned) > 1\n"
        )
        result = self._fix(code)
        assert "cleaned = clean_rut(rut)" in result
        assert "_clean_rut_val" not in result

    def test_fix_shadow_async_fn(self):
        """Shadow dentro de función async también se detecta."""
        code = (
            "def helper(x): return x\n\n"
            "async def main():\n"
            "    helper = helper(42)\n"
            "    return helper\n"
        )
        result = self._fix(code)
        assert "_helper_val" in result

    def test_skip_non_python_content(self):
        """Código con SyntaxError se devuelve sin cambios."""
        from code_postprocessor import _fix_local_variable_shadowing
        code = "esto no es python válido !!!"
        result = _fix_local_variable_shadowing(code)
        assert result == code


# ---------------------------------------------------------------------------
# S74-B: _ensure_test_task
# ---------------------------------------------------------------------------

class TestS74B:
    def _build_fr_analysis(self):
        return {"raw": "fastapi crud contratos", "type": "feature"}

    def _make_sdd(self, tasks: list) -> dict:
        return {"requirements": [], "tasks": tasks}

    def test_ensures_test_task_injected(self):
        """Cuando el SDD no tiene tests, debe inyectar TASK-INFRA-TESTS."""
        import graph as g
        sdd = self._make_sdd([
            {"id": "T1", "agent": "backend", "file": "src/auth/router.py",
             "title": "Auth", "description": "auth", "depends_on": [], "estimated_complexity": "low"},
        ])
        result = g._ensure_test_task(sdd, self._build_fr_analysis())
        test_tasks = [t for t in result["tasks"] if "test" in t.get("file", "").lower()
                      or "test" in t.get("title", "").lower()]
        assert len(test_tasks) >= 1

    def test_ensure_test_task_no_op_when_exists(self):
        """Si ya hay tarea de tests, no duplicar."""
        import graph as g
        sdd = self._make_sdd([
            {"id": "T1", "agent": "backend", "file": "src/auth/router.py",
             "title": "Auth", "description": "auth", "depends_on": [], "estimated_complexity": "low"},
            {"id": "T2", "agent": "backend", "file": "tests/test_auth.py",
             "title": "Tests auth", "description": "pytest", "depends_on": ["T1"], "estimated_complexity": "low"},
        ])
        original_count = len(sdd["tasks"])
        result = g._ensure_test_task(sdd, self._build_fr_analysis())
        assert len(result["tasks"]) == original_count

    def test_test_task_has_correct_fields(self):
        """TASK-INFRA-TESTS debe tener id, agent, file, description."""
        import graph as g
        sdd = self._make_sdd([
            {"id": "T1", "agent": "backend", "file": "src/contracts/service.py",
             "title": "Service", "description": "service", "depends_on": [], "estimated_complexity": "medium"},
        ])
        result = g._ensure_test_task(sdd, self._build_fr_analysis())
        test_task = next((t for t in result["tasks"] if t.get("id") == "TASK-INFRA-TESTS"), None)
        assert test_task is not None
        assert test_task["agent"] == "backend"
        assert test_task["file"].startswith("tests/")
        assert "conftest" in test_task["description"].lower() or "pytest" in test_task["description"].lower()

    def test_template_has_fewshot_testclient(self):
        """S74-B1: template contiene ejemplo con TestClient."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "TestClient" in content

    def test_template_has_fewshot_test_rut(self):
        """S74-B1: template contiene ejemplo de tests/test_rut_validator.py."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "test_rut_validator" in content or "test_validate_rut" in content

    def test_template_has_conftest_fixture(self):
        """S74-B1: template muestra fixture db con SQLite."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "sqlite" in content.lower() or "SQLite" in content


# ---------------------------------------------------------------------------
# S74-C: QA context API-only flag (lógica en graph.py)
# ---------------------------------------------------------------------------

class TestS74C:
    def _get_api_only_flag(self, fr_text: str) -> bool:
        """Simula la lógica S74-C de qa_review."""
        fr_lower = fr_text.lower()
        is_api = any(kw in fr_lower for kw in ("api rest", "fastapi", "endpoint", "backend", "crud"))
        has_frontend = any(kw in fr_lower for kw in ("react", "vue", "svelte", "frontend", "angular"))
        return is_api and not has_frontend

    def test_qa_api_only_flag_fastapi(self):
        """FR con FastAPI y sin frontend → api_only=True."""
        assert self._get_api_only_flag("Sistema FastAPI con CRUD de contratos") is True

    def test_qa_api_only_flag_fullstack(self):
        """FR con FastAPI + React → api_only=False."""
        assert self._get_api_only_flag("FastAPI backend + React frontend") is False

    def test_qa_api_only_pure_backend(self):
        """FR con solo 'backend' y 'endpoint' → api_only=True."""
        assert self._get_api_only_flag("API REST con endpoint de autenticación") is True

    def test_qa_api_only_no_flag_general(self):
        """FR genérico sin keywords → api_only=False."""
        assert self._get_api_only_flag("Sistema de notificaciones") is False


# ---------------------------------------------------------------------------
# S74-D: _warn_hardcoded_secrets
# ---------------------------------------------------------------------------

class TestS74D:
    def _warn(self, code: str, caplog) -> str:
        from code_postprocessor import _warn_hardcoded_secrets
        with caplog.at_level(logging.WARNING, logger="code_postprocessor"):
            _warn_hardcoded_secrets(code, "src/auth/router.py")
        return caplog.text

    def test_warn_hardcoded_secret_key(self, caplog):
        """SECRET_KEY con valor literal debe generar warning."""
        code = "SECRET_KEY = 'super-secret-abc123'\nALGORITHM = 'HS256'\n"
        log_text = self._warn(code, caplog)
        assert "S74-D" in log_text
        assert "SECRET_KEY" in log_text

    def test_warn_sha256_password(self, caplog):
        """hashlib.sha256().hexdigest() para password debe generar warning."""
        code = "hashed = hashlib.sha256(password.encode()).hexdigest()\n"
        log_text = self._warn(code, caplog)
        assert "SHA-256" in log_text or "sha256" in log_text.lower()

    def test_no_warn_env_secret(self, caplog):
        """os.environ.get('SECRET_KEY') no debe generar warning."""
        code = "SECRET_KEY = os.environ.get('SECRET_KEY', '')\n"
        from code_postprocessor import _warn_hardcoded_secrets
        with caplog.at_level(logging.WARNING, logger="code_postprocessor"):
            _warn_hardcoded_secrets(code, "src/auth/router.py")
        # No debe haber warning sobre S74-D para SECRET_KEY
        s74_warns = [r for r in caplog.records if "S74-D" in r.message and "SECRET_KEY" in r.message]
        assert len(s74_warns) == 0

    def test_no_warn_placeholder_value(self, caplog):
        """Valor placeholder 'your-secret-key-here' no genera warning."""
        code = "SECRET_KEY = 'your-secret-key-here'\n"
        from code_postprocessor import _warn_hardcoded_secrets
        with caplog.at_level(logging.WARNING, logger="code_postprocessor"):
            _warn_hardcoded_secrets(code, "src/auth.py")
        s74_warns = [r for r in caplog.records if "S74-D" in r.message and "SECRET_KEY" in r.message]
        assert len(s74_warns) == 0


# ---------------------------------------------------------------------------
# S74-E: template system_backend_python.md incluye passlib/bcrypt
# ---------------------------------------------------------------------------

class TestS74E:
    def test_template_has_passlib(self):
        """S74-E: template contiene passlib[bcrypt]."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "passlib" in content.lower()
        assert "bcrypt" in content.lower()

    def test_template_prohibits_sha256_passwords(self):
        """S74-E: template advierte que hashlib.sha256 está prohibido para passwords."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "sha256" in content.lower()
        assert "PROHIBIDO" in content or "prohibido" in content.lower()

    def test_template_has_secret_key_env(self):
        """S74-E: template muestra os.environ.get para SECRET_KEY."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "os.environ.get" in content
        assert "SECRET_KEY" in content
