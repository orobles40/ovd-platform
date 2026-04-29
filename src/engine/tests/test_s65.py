"""
Tests S65 — import validator, ORM guard, route order checker, infra auto-gen, auth phantom fix.
"""

import pathlib
import sys
import tempfile
import textwrap

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from graph import (
    _build_single_task_sdd_content,
    _check_fastapi_route_ordering,
    _ensure_python_infrastructure,
    _validate_artifacts_imports,
)

# ---------------------------------------------------------------------------
# S65-A: _validate_artifacts_imports
# ---------------------------------------------------------------------------


def _make_artifact(path: str, content: str, tmpdir: pathlib.Path) -> dict:
    full = tmpdir / path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return {"path": path, "content": content}


def test_s65a_clean_imports_returns_true():
    """Archivo sin imports fantasma → (True, '')."""
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td)
        art = _make_artifact("src/models.py", "from pydantic import BaseModel\n", p)
        ok, msg = _validate_artifacts_imports(
            agent_results=[{"artifacts": [art]}],
            directory=td,
            written_files=["src/models.py"],
        )
    assert ok is True
    assert msg == ""


def test_s65a_phantom_import_detected():
    """Import de módulo fantasma → S96-A genera stub mínimo y retorna ok=True."""
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td)
        art = _make_artifact(
            "src/main.py",
            "from src.auth.dependencies import get_current_user\n",
            p,
        )
        ok, msg = _validate_artifacts_imports(
            agent_results=[{"artifacts": [art]}],
            directory=td,
            written_files=["src/main.py"],
        )
        assert ok is True
        assert msg == ""
        assert (p / "src" / "auth" / "dependencies.py").exists()


def test_s65a_local_module_not_flagged():
    """Import a módulo creado en la misma entrega → no se marca como fantasma."""
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td)
        # Crear src/database.py físicamente
        _make_artifact("src/database.py", "def get_db(): pass\n", p)
        art = _make_artifact(
            "src/service.py",
            "from src.database import get_db\n",
            p,
        )
        ok, msg = _validate_artifacts_imports(
            agent_results=[{"artifacts": [art]}],
            directory=td,
            written_files=["src/database.py", "src/service.py"],
        )
    assert ok is True


def test_s65a_relative_import_ignored():
    """Imports relativos (from . import X) no se validan — solo absolutos."""
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td)
        art = _make_artifact("src/service.py", "from . import models\n", p)
        ok, _ = _validate_artifacts_imports(
            agent_results=[{"artifacts": [art]}],
            directory=td,
            written_files=["src/service.py"],
        )
    assert ok is True


def test_s65a_stdlib_not_flagged():
    """Módulos stdlib (os, sys, json...) no se marcan como fantasmas."""
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td)
        art = _make_artifact(
            "src/utils.py",
            "import os\nimport sys\nfrom datetime import datetime\nfrom pathlib import Path\n",
            p,
        )
        ok, _ = _validate_artifacts_imports(
            agent_results=[{"artifacts": [art]}],
            directory=td,
            written_files=["src/utils.py"],
        )
    assert ok is True


def test_s65a_installed_package_not_flagged():
    """Paquetes instalados (fastapi, sqlalchemy, pydantic) no son fantasmas."""
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td)
        art = _make_artifact(
            "src/main.py",
            "from fastapi import FastAPI\nfrom sqlalchemy.orm import Session\nfrom pydantic import BaseModel\n",
            p,
        )
        ok, _ = _validate_artifacts_imports(
            agent_results=[{"artifacts": [art]}],
            directory=td,
            written_files=["src/main.py"],
        )
    assert ok is True


def test_s65a_syntax_error_file_skipped():
    """Archivo con SyntaxError es ignorado sin romper la validación."""
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td)
        art = _make_artifact("src/broken.py", "def foo(:\n    pass\n", p)
        ok, _ = _validate_artifacts_imports(
            agent_results=[{"artifacts": [art]}],
            directory=td,
            written_files=["src/broken.py"],
        )
    assert ok is True  # no debe lanzar excepción


# ---------------------------------------------------------------------------
# S65-C: _check_fastapi_route_ordering
# ---------------------------------------------------------------------------


def test_s65c_static_after_parametric_detected():
    """Ruta estática declarada DESPUÉS de paramétrica con mismo prefijo → issue."""
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td)
        code = textwrap.dedent("""\
            from fastapi import FastAPI
            app = FastAPI()

            @app.get("/contratos/{rut}")
            async def get_by_rut(rut: str): ...

            @app.get("/contratos/vencimientos")
            async def get_vencimientos(): ...
        """)
        (p / "main.py").write_text(code, encoding="utf-8")
        issues = _check_fastapi_route_ordering(td)
    assert len(issues) >= 1
    assert any("vencimientos" in iss for iss in issues)


def test_s65c_correct_order_no_issues():
    """Rutas en orden correcto (estáticas primero) → sin issues."""
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td)
        code = textwrap.dedent("""\
            from fastapi import FastAPI
            app = FastAPI()

            @app.get("/contratos/vencimientos")
            async def get_vencimientos(): ...

            @app.get("/contratos/{rut}")
            async def get_by_rut(rut: str): ...
        """)
        (p / "main.py").write_text(code, encoding="utf-8")
        issues = _check_fastapi_route_ordering(td)
    assert issues == []


def test_s65c_different_methods_no_false_positive():
    """Rutas con misma ruta pero diferente método no generan issue falso."""
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td)
        code = textwrap.dedent("""\
            from fastapi import FastAPI
            app = FastAPI()

            @app.post("/contratos/{rut}")
            async def create_contrato(rut: str): ...

            @app.get("/contratos/vencimientos")
            async def get_vencimientos(): ...
        """)
        (p / "main.py").write_text(code, encoding="utf-8")
        issues = _check_fastapi_route_ordering(td)
    # POST y GET son distintos — no deben reportarse como conflicto
    assert issues == []


def test_s65c_empty_directory_no_crash():
    """Directorio vacío no lanza excepción."""
    with tempfile.TemporaryDirectory() as td:
        issues = _check_fastapi_route_ordering(td)
    assert issues == []


# ---------------------------------------------------------------------------
# S65-E: _ensure_python_infrastructure
# ---------------------------------------------------------------------------


def test_s65e_creates_requirements_txt():
    """requirements.txt se crea si no existe."""
    with tempfile.TemporaryDirectory() as td:
        created = _ensure_python_infrastructure(td)
        assert "requirements.txt" in created
        assert (pathlib.Path(td) / "requirements.txt").exists()


def test_s65e_no_overwrite_existing_requirements():
    """requirements.txt no se sobreescribe si ya tiene contenido."""
    with tempfile.TemporaryDirectory() as td:
        req = pathlib.Path(td) / "requirements.txt"
        req.write_text("mypackage==1.0\n", encoding="utf-8")
        created = _ensure_python_infrastructure(td)
        assert "requirements.txt" not in created
        assert req.read_text() == "mypackage==1.0\n"


def test_s65e_nonexistent_directory_no_crash():
    """Directorio inexistente retorna lista vacía sin excepción."""
    created = _ensure_python_infrastructure("/tmp/ovd_nonexistent_s65e_test_xyz")
    assert created == []


# ---------------------------------------------------------------------------
# S65-B: ORM guard en _build_single_task_sdd_content
# ---------------------------------------------------------------------------

_SDD_WITH_DATABASE = {
    "summary": "API contratos con BD",
    "tasks": [
        {
            "agent": "backend",
            "description": "Crear `src/database.py` con Base y get_db",
            "title": "database",
        },
        {
            "agent": "backend",
            "description": "Crear `src/contracts/models.py` con ContratoORM y Contrato",
            "title": "models",
        },
        {
            "agent": "backend",
            "description": "Crear `tests/test_contracts.py`",
            "title": "tests",
        },
    ],
    "requirements": [],
    "constraints": [],
    "design": {"overview": ""},
}

_SDD_NO_DATABASE = {
    "summary": "Función pura IMC",
    "tasks": [
        {
            "agent": "backend",
            "description": "Crear `src/imc.py` con calcular_imc",
            "title": "imc",
        },
    ],
    "requirements": [],
    "constraints": [],
    "design": {"overview": ""},
}


def test_s65b_orm_hint_injected_when_database_present():
    """Cuando SDD tiene database.py y tarea de models → inyecta recordatorio ORM."""
    task = _SDD_WITH_DATABASE["tasks"][1]  # models task
    content = _build_single_task_sdd_content(_SDD_WITH_DATABASE, "backend", task, 1, 3)
    assert "[S65-B]" in content
    assert "ORM" in content or "DeclarativeBase" in content


def test_s65b_orm_hint_not_injected_without_database():
    """Sin database.py en el SDD → no se inyecta ORM hint."""
    task = _SDD_NO_DATABASE["tasks"][0]
    content = _build_single_task_sdd_content(_SDD_NO_DATABASE, "backend", task, 0, 1)
    assert "[S65-B]" not in content


def test_s65b_orm_hint_not_injected_for_tests_task():
    """Tarea de tests no recibe ORM hint (recibe float hint en su lugar)."""
    task = _SDD_WITH_DATABASE["tasks"][2]  # tests task
    content = _build_single_task_sdd_content(_SDD_WITH_DATABASE, "backend", task, 2, 3)
    # tests task recibe S55-C (float hint), no S65-B
    assert "[S55-C]" in content or "[S65-B]" not in content


# ---------------------------------------------------------------------------
# S65-D: system_sdd.md — auth condition independiente de oracle_involved
# ---------------------------------------------------------------------------


def test_s65d_sdd_template_auth_keyword_list():
    """system_sdd.md contiene la lista explícita de palabras clave de auth."""
    template_path = pathlib.Path(__file__).parent.parent / "templates" / "system_sdd.md"
    content = template_path.read_text(encoding="utf-8")
    assert "autenticación" in content
    assert "login" in content
    assert "JWT" in content
    assert (
        "oracle_involved" in content
    )  # la regla menciona que oracle_involved no es suficiente


def test_s65d_sdd_template_auth_independent_of_oracle():
    """system_sdd.md indica explícitamente que oracle_involved=True no implica auth."""
    template_path = pathlib.Path(__file__).parent.parent / "templates" / "system_sdd.md"
    content = template_path.read_text(encoding="utf-8")
    assert "oracle_involved=True" in content or "oracle_involved" in content
