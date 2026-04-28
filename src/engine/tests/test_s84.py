"""Tests for S84: content in artifacts, Oracle init fix, auth/models.py injection."""

import os
import pathlib
import sys

import pytest

_ENGINE_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, _ENGINE_DIR)


# ---------------------------------------------------------------------------
# S84-B — _write_artifacts devuelve 'content' en cada artifact
# ---------------------------------------------------------------------------


def test_s84b_write_artifacts_returns_content(tmp_path):
    """S84-B: _write_artifacts debe incluir 'content' en cada dict del resultado."""
    from graph import _write_artifacts

    agent_output = "```python:src/models.py\nclass Foo:\n    pass\n```"
    result = _write_artifacts(agent_output, str(tmp_path), agent="backend")
    assert len(result) == 1
    art = result[0]
    assert "content" in art, "S84-B: artifact debe tener campo 'content'"
    assert "class Foo" in art["content"]


def test_s84b_content_not_empty(tmp_path):
    """S84-B: el campo content no debe estar vacío."""
    from graph import _write_artifacts

    agent_output = (
        "```python:src/contracts/models.py\nclass ContractORM:\n    id = 1\n```"
    )
    result = _write_artifacts(agent_output, str(tmp_path), agent="backend")
    assert result[0]["content"].strip() != ""


def test_s84b_content_enables_dependency_context(tmp_path):
    """S84-B: _build_dependency_context recibe content de artifacts y lo inyecta."""
    from graph import _build_dependency_context, _write_artifacts

    agent_output = (
        "```python:src/contracts/models.py\nclass ContractORM:\n    pass\n```"
    )
    written = _write_artifacts(agent_output, str(tmp_path), agent="backend")
    written_context = {
        art["path"]: art["content"] for art in written if art.get("content")
    }
    assert "src/contracts/models.py" in written_context

    task = {"file": "src/contracts/service.py", "depends_on": [], "id": "T2"}
    ctx = _build_dependency_context(task, written_context)
    assert "ContractORM" in ctx


# ---------------------------------------------------------------------------
# S84-A — _fix_oracle_init_in_postgres_db
# ---------------------------------------------------------------------------


def test_s84a_removes_oracle_init_when_postgres_url():
    """S84-A: elimina oracledb.init_oracle_client() cuando DATABASE_URL es PostgreSQL."""
    from code_postprocessor import _fix_oracle_init_in_postgres_db

    code = (
        "from sqlalchemy import create_engine\n"
        "oracledb.init_oracle_client(lib_dir='/usr/lib/oracle/21/client/lib')\n"
        "DATABASE_URL = 'postgresql+psycopg://ovd_dev:changeme@localhost:5432/app_db'\n"
        "engine = create_engine(DATABASE_URL)\n"
    )
    result = _fix_oracle_init_in_postgres_db(code, "src/database.py")
    assert "oracledb.init_oracle_client" not in result
    assert "postgresql+psycopg" in result


def test_s84a_keeps_oracle_init_when_oracle_url():
    """S84-A: NO elimina init cuando DATABASE_URL es Oracle."""
    from code_postprocessor import _fix_oracle_init_in_postgres_db

    code = (
        "import oracledb\n"
        "oracledb.init_oracle_client(lib_dir='/usr/lib/oracle/21/client/lib')\n"
        "DATABASE_URL = 'oracle+oracledb://user:pass@localhost:1521/?service_name=XE'\n"
    )
    result = _fix_oracle_init_in_postgres_db(code, "src/database.py")
    assert "oracledb.init_oracle_client" in result


def test_s84a_only_acts_on_database_py():
    """S84-A: no modifica archivos que no son database.py."""
    from code_postprocessor import _fix_oracle_init_in_postgres_db

    code = (
        "oracledb.init_oracle_client(lib_dir='/usr/lib')\n"
        "DATABASE_URL = 'postgresql+psycopg://...'\n"
    )
    result = _fix_oracle_init_in_postgres_db(code, "src/utils/helper.py")
    assert result == code


def test_s84a_also_removes_import_oracledb():
    """S84-A: elimina también 'import oracledb' cuando Oracle init se elimina."""
    from code_postprocessor import _fix_oracle_init_in_postgres_db

    code = (
        "import oracledb\n"
        "oracledb.init_oracle_client(lib_dir='/usr/lib/oracle/21/client/lib')\n"
        "DATABASE_URL = 'postgresql+psycopg://ovd_dev:changeme@localhost:5432/app_db'\n"
    )
    result = _fix_oracle_init_in_postgres_db(code, "src/database.py")
    assert "import oracledb" not in result
    assert "oracledb.init_oracle_client" not in result


def test_s84a_wired_in_postprocess_python_file():
    """S84-A: postprocess_python_file llama _fix_oracle_init_in_postgres_db."""
    src = pathlib.Path(_ENGINE_DIR) / "code_postprocessor.py"
    content = src.read_text()
    assert "_fix_oracle_init_in_postgres_db" in content
    assert "S84-A" in content


# ---------------------------------------------------------------------------
# S84-C — template auth/models.py
# ---------------------------------------------------------------------------


def test_s84c_template_has_user_orm():
    """S84-C: system_backend_python.md debe incluir UserORM con campo rut."""
    tpl = pathlib.Path(_ENGINE_DIR) / "templates" / "system_backend_python.md"
    content = tpl.read_text()
    assert "UserORM" in content
    assert "S84-C" in content
    assert "password_hash" in content


def test_s84c_template_has_token_response():
    """S84-C: template debe incluir TokenResponse en auth/models.py."""
    tpl = pathlib.Path(_ENGINE_DIR) / "templates" / "system_backend_python.md"
    content = tpl.read_text()
    assert "TokenResponse" in content
    assert "auth/models.py" in content


def test_s84c_template_has_login_request():
    """S84-C: template debe incluir LoginRequest en auth/models.py."""
    tpl = pathlib.Path(_ENGINE_DIR) / "templates" / "system_backend_python.md"
    content = tpl.read_text()
    assert "LoginRequest" in content


# ---------------------------------------------------------------------------
# S84-F — _ensure_auth_models_task
# ---------------------------------------------------------------------------


def test_s84f_injects_when_router_present_no_models():
    """S84-F: inyecta auth/models.py cuando hay auth/router.py pero no auth/models.py."""
    from graph import _ensure_auth_models_task

    sdd = {
        "tasks": [
            {
                "id": "T1",
                "file": "src/auth/router.py",
                "agent": "backend",
                "title": "auth router",
            },
        ]
    }
    result = _ensure_auth_models_task(sdd)
    files = [t["file"] for t in result["tasks"]]
    assert "src/auth/models.py" in files


def test_s84f_no_inject_when_models_exists():
    """S84-F: no duplica si auth/models.py ya está en el SDD."""
    from graph import _ensure_auth_models_task

    sdd = {
        "tasks": [
            {
                "id": "T1",
                "file": "src/auth/models.py",
                "agent": "backend",
                "title": "auth models",
            },
            {
                "id": "T2",
                "file": "src/auth/router.py",
                "agent": "backend",
                "title": "auth router",
            },
        ]
    }
    result = _ensure_auth_models_task(sdd)
    auth_model_tasks = [
        t for t in result["tasks"] if "auth/models" in t.get("file", "")
    ]
    assert len(auth_model_tasks) == 1


def test_s84f_no_inject_when_no_auth_router():
    """S84-F: no inyecta si no hay auth/router.py."""
    from graph import _ensure_auth_models_task

    sdd = {
        "tasks": [
            {
                "id": "T1",
                "file": "src/contracts/models.py",
                "agent": "backend",
                "title": "contracts",
            },
        ]
    }
    result = _ensure_auth_models_task(sdd)
    auth_model_tasks = [
        t for t in result["tasks"] if "auth/models" in t.get("file", "")
    ]
    assert len(auth_model_tasks) == 0


def test_s84f_models_inserted_before_router():
    """S84-F: auth/models.py debe insertarse ANTES de auth/router.py."""
    from graph import _ensure_auth_models_task

    sdd = {
        "tasks": [
            {"id": "T1", "file": "src/database.py", "agent": "backend", "title": "db"},
            {
                "id": "T2",
                "file": "src/auth/router.py",
                "agent": "backend",
                "title": "router",
            },
        ]
    }
    result = _ensure_auth_models_task(sdd)
    files = [t["file"] for t in result["tasks"]]
    models_idx = files.index("src/auth/models.py")
    router_idx = files.index("src/auth/router.py")
    assert models_idx < router_idx


def test_s84f_wired_in_generate_sdd():
    """S84-F: graph.py debe llamar _ensure_auth_models_task en generate_sdd."""
    src = pathlib.Path(_ENGINE_DIR) / "graph.py"
    content = src.read_text()
    assert "_ensure_auth_models_task" in content
    assert "S84-F" in content
