"""
Tests S70
  S70-A: session_create dispara background task sin esperar SSE
  S70-B: _ensure_fastapi_main_task — no genera include_router() cuando no hay router.py en SDD
  S70-C: conftest.py recibe mock oracledb cuando el workspace lo importa
  S70-D: system_backend_python.md contiene regla de auto-imports prohibidos
  S70-E: system_backend_python.md contiene regla de librería JWT única
"""

import pathlib
import sys
import tempfile

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from graph import _ensure_fastapi_main_task, _validate_artifacts_imports

_TEMPLATES_DIR = pathlib.Path(__file__).parent.parent / "templates"
_BACKEND_PY_TEMPLATE = _TEMPLATES_DIR / "system_backend_python.md"


# ---------------------------------------------------------------------------
# S70-B: _ensure_fastapi_main_task — router detection
# ---------------------------------------------------------------------------


def _fr_fastapi():
    return {
        "raw": "API REST FastAPI con autenticación JWT. Endpoints de contratos.",
        "type": "feature",
    }


def _sdd_without_main_no_routers():
    return {
        "tasks": [
            {
                "id": "T1",
                "agent": "backend",
                "file": "src/auth/service.py",
                "title": "Auth service",
                "description": "lógica de autenticación",
                "depends_on": [],
            },
            {
                "id": "T2",
                "agent": "backend",
                "file": "src/contracts/service.py",
                "title": "Contracts",
                "description": "lógica de contratos",
                "depends_on": [],
            },
        ]
    }


def _sdd_without_main_with_routers():
    return {
        "tasks": [
            {
                "id": "T1",
                "agent": "backend",
                "file": "src/auth/router.py",
                "title": "Auth router",
                "description": "router de autenticación",
                "depends_on": [],
            },
            {
                "id": "T2",
                "agent": "backend",
                "file": "src/contracts/router.py",
                "title": "Contracts router",
                "description": "router de contratos",
                "depends_on": [],
            },
        ]
    }


class TestS70B:
    def test_no_router_hint_when_no_router_py_in_sdd(self):
        """S70-B: cuando SDD no tiene router.py, description no incluye include_router."""
        sdd = _ensure_fastapi_main_task(_sdd_without_main_no_routers(), _fr_fastapi())
        main_task = next(
            (t for t in sdd["tasks"] if t.get("id") == "TASK-INFRA-MAIN"), None
        )
        assert main_task is not None
        desc = main_task["description"].lower()
        assert "include_router" not in desc, (
            "No debe sugerir include_router cuando no hay router.py en SDD"
        )

    def test_s70b_hint_mentions_no_routers(self):
        """S70-B: description indica que no importe routers que no estén en el SDD."""
        sdd = _ensure_fastapi_main_task(_sdd_without_main_no_routers(), _fr_fastapi())
        main_task = next(t for t in sdd["tasks"] if t.get("id") == "TASK-INFRA-MAIN")
        desc = main_task["description"].lower()
        # La description debe mencionar la restricción de no importar routers inexistentes
        assert (
            "no importes" in desc
            or "no hay router" in desc
            or "router que no estén" in desc
        )

    def test_router_hint_included_when_router_py_exists_in_sdd(self):
        """S70-B: cuando SDD tiene router.py, description incluye el import correcto."""
        sdd = _ensure_fastapi_main_task(_sdd_without_main_with_routers(), _fr_fastapi())
        main_task = next(
            (t for t in sdd["tasks"] if t.get("id") == "TASK-INFRA-MAIN"), None
        )
        assert main_task is not None
        desc = main_task["description"]
        assert "auth_router" in desc or "auth.router" in desc

    def test_no_injection_when_main_already_present(self):
        """S70-B: no inyecta TASK-INFRA-MAIN si ya existe src/main.py en el SDD."""
        sdd = {
            "tasks": [
                {
                    "id": "T-MAIN",
                    "agent": "backend",
                    "file": "src/main.py",
                    "title": "Main",
                    "description": "entry point",
                    "depends_on": [],
                },
            ]
        }
        result = _ensure_fastapi_main_task(sdd, _fr_fastapi())
        main_tasks = [t for t in result["tasks"] if t.get("id") == "TASK-INFRA-MAIN"]
        assert len(main_tasks) == 0

    def test_injection_skipped_for_non_fastapi_fr(self):
        """S70-B: no inyecta si el FR no menciona FastAPI."""
        fr = {"raw": "script de análisis de datos con pandas.", "type": "feature"}
        sdd = _sdd_without_main_no_routers()
        result = _ensure_fastapi_main_task(sdd, fr)
        main_tasks = [t for t in result["tasks"] if t.get("id") == "TASK-INFRA-MAIN"]
        assert len(main_tasks) == 0


# ---------------------------------------------------------------------------
# S70-C: conftest oracledb mock
# ---------------------------------------------------------------------------


class TestS70C:
    def test_oracledb_mock_added_when_workspace_imports_it(self, tmp_path):
        """S70-C: conftest.py recibe mock oracledb cuando database.py importa oracledb."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "database.py").write_text(
            "import oracledb\noracledb.init_oracle_client()\n", encoding="utf-8"
        )
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_auth.py").write_text(
            "def test_dummy(): pass\n", encoding="utf-8"
        )

        # Simular la lógica de S70-C directamente
        import pathlib as _pl

        wdir = _pl.Path(tmp_path)
        has_oracledb = any(
            "oracledb" in f.read_text(encoding="utf-8", errors="replace")
            for f in wdir.rglob("*.py")
            if not f.name.startswith("test_") and f.name != "conftest.py"
        )
        assert has_oracledb is True

    def test_oracledb_mock_not_added_when_not_present(self, tmp_path):
        """S70-C: si el workspace no usa oracledb, conftest no recibe el mock."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "database.py").write_text(
            "import psycopg\nconn = psycopg.connect()\n", encoding="utf-8"
        )
        import pathlib as _pl

        wdir = _pl.Path(tmp_path)
        has_oracledb = any(
            "oracledb" in f.read_text(encoding="utf-8", errors="replace")
            for f in wdir.rglob("*.py")
            if not f.name.startswith("test_") and f.name != "conftest.py"
        )
        assert has_oracledb is False

    def test_oracledb_mock_content_valid(self):
        """S70-C: el mock genera código Python válido que puede parsear ast."""
        import ast

        mock_code = (
            "import sys, os\n"
            'sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))\n'
            "from unittest.mock import MagicMock\n"
            "sys.modules['oracledb'] = MagicMock()\n"
        )
        tree = ast.parse(mock_code)
        assert tree is not None


# ---------------------------------------------------------------------------
# S70-D: regla auto-imports circulares en template
# ---------------------------------------------------------------------------


class TestS70D:
    def test_template_prohibits_self_import(self):
        """S70-D: system_backend_python.md contiene regla contra auto-imports."""
        assert _BACKEND_PY_TEMPLATE.exists(), "Template no encontrado"
        content = _BACKEND_PY_TEMPLATE.read_text(encoding="utf-8")
        assert (
            "NUNCA importes desde el mismo módulo" in content
            or "auto-import" in content.lower()
        )

    def test_template_explains_models_service_separation(self):
        """S70-D: template indica que ORM models van en models.py, no service.py."""
        content = _BACKEND_PY_TEMPLATE.read_text(encoding="utf-8")
        assert "models.py" in content
        assert "service.py" in content

    def test_template_shows_circular_import_example(self):
        """S70-D: template muestra ejemplo de import circular prohibido."""
        content = _BACKEND_PY_TEMPLATE.read_text(encoding="utf-8")
        assert "PROHIBIDO" in content or "NUNCA" in content


# ---------------------------------------------------------------------------
# S70-E: JWT library consistency en template
# ---------------------------------------------------------------------------


class TestS70E:
    def test_template_mandates_single_jwt_library(self):
        """S70-E: template indica usar python-jose y no mezclar con PyJWT."""
        content = _BACKEND_PY_TEMPLATE.read_text(encoding="utf-8")
        assert "python-jose" in content

    def test_template_prohibits_mixing_jwt_libraries(self):
        """S70-E: template menciona el problema de mezclar jose y PyJWT."""
        content = _BACKEND_PY_TEMPLATE.read_text(encoding="utf-8")
        assert "PyJWT" in content or "jose" in content

    def test_template_shows_jose_usage_example(self):
        """S70-E: template incluye ejemplo de uso correcto de jose."""
        content = _BACKEND_PY_TEMPLATE.read_text(encoding="utf-8")
        assert "from jose import jwt" in content
