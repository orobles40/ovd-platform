"""S104 — Tests de regresión para fixes de determinismo y anti-circular-import."""

from __future__ import annotations

import inspect
import pathlib
import shutil
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from graph import (
    _classify_test_error,
    _detect_circular_self_imports,
)
from model_router import _STRUCTURED_ROLES, _resolve_temperature

# ---------------------------------------------------------------------------
# S104-A — temperature=0 + seed=42 para agentes implementadores
# ---------------------------------------------------------------------------


class TestS104A:
    def test_implementer_roles_in_structured_roles(self):
        assert "backend" in _STRUCTURED_ROLES
        assert "frontend" in _STRUCTURED_ROLES
        assert "database" in _STRUCTURED_ROLES
        assert "devops" in _STRUCTURED_ROLES

    def test_original_roles_still_in_structured_roles(self):
        for role in ("analyzer", "sdd", "qa", "security", "router"):
            assert role in _STRUCTURED_ROLES

    def test_backend_gets_temperature_zero(self):
        assert _resolve_temperature("backend", "ollama") == 0.0

    def test_frontend_gets_temperature_zero(self):
        assert _resolve_temperature("frontend", "ollama") == 0.0

    def test_database_gets_temperature_zero(self):
        assert _resolve_temperature("database", "ollama") == 0.0

    def test_devops_gets_temperature_zero(self):
        assert _resolve_temperature("devops", "ollama") == 0.0

    def test_chat_ollama_has_seed(self):
        """Verifica que el source de model_router incluye seed=42 en ChatOllama."""
        import model_router as mr

        src = inspect.getsource(mr)
        assert "seed=42" in src, "ChatOllama debe incluir seed=42 (S104-A)"


# ---------------------------------------------------------------------------
# S104-B — Detección de circular self-imports
# ---------------------------------------------------------------------------


class TestS104B:
    def test_detects_from_self_import(self, tmp_path):
        pkg = tmp_path / "src" / "auth"
        pkg.mkdir(parents=True)
        (tmp_path / "src" / "__init__.py").write_text("")
        (pkg / "__init__.py").write_text("")
        (pkg / "services.py").write_text(
            "from src.auth.services import verify_password\n\n"
            "def verify_password(rut, pw): pass\n"
        )
        ok, feedback = _detect_circular_self_imports(str(tmp_path))
        assert not ok
        assert "src.auth.services" in feedback
        assert "[S104-B]" in feedback

    def test_detects_import_self(self, tmp_path):
        pkg = tmp_path / "src" / "contracts"
        pkg.mkdir(parents=True)
        (tmp_path / "src" / "__init__.py").write_text("")
        (pkg / "__init__.py").write_text("")
        (pkg / "services.py").write_text("import src.contracts.services\n")
        ok, feedback = _detect_circular_self_imports(str(tmp_path))
        assert not ok
        assert "src.contracts.services" in feedback

    def test_clean_code_passes(self, tmp_path):
        pkg = tmp_path / "src" / "auth"
        pkg.mkdir(parents=True)
        (tmp_path / "src" / "__init__.py").write_text("")
        (pkg / "__init__.py").write_text("")
        (pkg / "services.py").write_text(
            "from src.core.utils import hash_pw\n\ndef verify_password(rut, pw): pass\n"
        )
        ok, _ = _detect_circular_self_imports(str(tmp_path))
        assert ok

    def test_skips_pycache(self, tmp_path):
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "services.cpython-312.pyc").write_bytes(b"fake")
        ok, _ = _detect_circular_self_imports(str(tmp_path))
        assert ok

    def test_empty_directory_passes(self, tmp_path):
        ok, feedback = _detect_circular_self_imports(str(tmp_path))
        assert ok
        assert feedback == ""

    def test_nonexistent_directory_passes(self):
        ok, feedback = _detect_circular_self_imports("/nonexistent/path/xyz")
        assert ok
        assert feedback == ""


# ---------------------------------------------------------------------------
# S104-C — Limpieza __pycache__ en session_create
# ---------------------------------------------------------------------------


class TestS104C:
    def test_pycache_cleanup_code_exists_in_api(self):
        import api

        src = inspect.getsource(api)
        assert "S104-C" in src
        assert "__pycache__" in src
        assert "rmtree" in src

    def test_pycache_cleanup_removes_dirs(self, tmp_path):
        pkg = tmp_path / "src" / "auth"
        pkg.mkdir(parents=True)
        cache = pkg / "__pycache__"
        cache.mkdir()
        (cache / "services.cpython-312.pyc").write_bytes(b"fake bytecode")

        assert cache.exists()
        for cache_dir in tmp_path.rglob("__pycache__"):
            shutil.rmtree(cache_dir, ignore_errors=True)
        assert not cache.exists()


# ---------------------------------------------------------------------------
# S105-P1 — Limpieza de test_*.py del ciclo anterior en session_create
# ---------------------------------------------------------------------------


class TestS105P1:
    def test_old_tests_removed_before_new_cycle(self, tmp_path):
        """Simula la limpieza S105-P1: test_*.py del ciclo anterior deben eliminarse."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        old_test = tests_dir / "test_contracts_service.py"
        old_test.write_text(
            "from src.contracts.services import validate_contract_type\n"
        )
        assert old_test.exists()
        # simular lo que hace session_create S105-P1
        removed = []
        for f in tests_dir.glob("test_*.py"):
            f.unlink()
            removed.append(f.name)
        assert not old_test.exists()
        assert "test_contracts_service.py" in removed

    def test_only_test_star_files_removed(self, tmp_path):
        """S105-P1 solo borra test_*.py — conftest.py y otros deben preservarse."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_old.py").write_text("# old")
        conftest = tests_dir / "conftest.py"
        conftest.write_text("# conftest")
        helper = tests_dir / "helpers.py"
        helper.write_text("# helpers")
        for f in tests_dir.glob("test_*.py"):
            f.unlink()
        assert not (tests_dir / "test_old.py").exists()
        assert conftest.exists()
        assert helper.exists()

    def test_s105p1_code_exists_in_api(self):
        import api

        src = inspect.getsource(api)
        assert "S105-P1" in src
        assert "test_*.py" in src or 'glob("test_*.py")' in src

    def test_no_tests_dir_is_safe(self, tmp_path):
        """Si no existe tests/, S105-P1 no falla."""
        workspace = tmp_path / "workspace_sin_tests"
        workspace.mkdir()
        tests_dir = workspace / "tests"
        assert not tests_dir.exists()
        if tests_dir.exists():
            for f in tests_dir.glob("test_*.py"):
                f.unlink()
        # no debe lanzar excepción


# ---------------------------------------------------------------------------
# S104-D — Restricción SDD docker-compose → devops
# ---------------------------------------------------------------------------


class TestS104D:
    def _template_content(self) -> str:
        template_path = (
            pathlib.Path(__file__).parent.parent / "templates" / "system_sdd.md"
        )
        return template_path.read_text(encoding="utf-8")

    def test_sdd_template_has_s104d_restriction(self):
        content = self._template_content()
        assert "S104-D" in content
        assert "RESTRICCIÓN ABSOLUTA" in content

    def test_sdd_template_lists_docker_compose(self):
        content = self._template_content()
        assert "docker-compose.yml" in content
        assert "NUNCA asignar estos artefactos a `backend` o `frontend`" in content

    def test_sdd_template_lists_dockerfile(self):
        content = self._template_content()
        assert "Dockerfile" in content


# ---------------------------------------------------------------------------
# S104-E — Error taxonomy para retry strategy
# ---------------------------------------------------------------------------


class TestS104E:
    def test_classify_circular_import(self):
        assert (
            _classify_test_error("ImportError: partially initialized module")
            == "circular_import"
        )
        assert _classify_test_error("circular import detected") == "circular_import"

    def test_classify_naming_mismatch(self):
        assert (
            _classify_test_error("ImportError: cannot import name 'list_contracts'")
            == "naming_mismatch"
        )

    def test_classify_import_error(self):
        assert (
            _classify_test_error("ModuleNotFoundError: No module named 'src.auth'")
            == "import_error"
        )
        assert (
            _classify_test_error("ImportError: No module named 'missing'")
            == "import_error"
        )

    def test_classify_syntax_error(self):
        assert (
            _classify_test_error("SyntaxError: invalid syntax (file.py, line 42)")
            == "syntax_error"
        )

    def test_classify_assertion_error(self):
        assert (
            _classify_test_error("AssertionError: assert 1 == 2") == "assertion_error"
        )

    def test_classify_generic(self):
        assert _classify_test_error("Some unknown error occurred") == "generic"

    def test_classify_function_exists(self):
        assert callable(_classify_test_error)

    def test_naming_mismatch_takes_priority_over_import_error(self):
        output = (
            "ImportError: cannot import name 'verify_password' from 'src.auth.services'"
        )
        result = _classify_test_error(output)
        assert result == "naming_mismatch"
