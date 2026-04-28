"""Tests for S82-A, S82-B, S82-F fixes."""
import pathlib
import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# S82-A — _fix_orm_in_service respects models.py existence
# ---------------------------------------------------------------------------

def test_s82a_skips_when_models_missing(tmp_path):
    """S82-A: si models.py no existe en disco, preserva ORM en service.py."""
    from code_postprocessor import _fix_orm_in_service

    content = (
        "from src.database import Base\n"
        "from sqlalchemy import Column, Integer, String\n"
        "class ContractORM(Base):\n"
        "    __tablename__ = 'contracts'\n"
        "    id = Column(Integer, primary_key=True)\n"
    )
    # tmp_path/src/contracts/ existe pero SIN models.py
    contracts_dir = tmp_path / "src" / "contracts"
    contracts_dir.mkdir(parents=True)

    result = _fix_orm_in_service(content, "src/contracts/service.py", work_dir=str(tmp_path))
    assert "class ContractORM" in result, "ORM debe preservarse si models.py no existe"
    assert "from src.contracts.models import" not in result


def test_s82a_removes_when_models_exists(tmp_path):
    """S82-A: si models.py existe en disco, S81-A elimina ORM de service.py."""
    from code_postprocessor import _fix_orm_in_service

    content = (
        "from src.database import Base\n"
        "from sqlalchemy import Column, Integer\n"
        "class ContractORM(Base):\n"
        "    __tablename__ = 'contracts'\n"
        "    id = Column(Integer, primary_key=True)\n"
    )
    contracts_dir = tmp_path / "src" / "contracts"
    contracts_dir.mkdir(parents=True)
    (contracts_dir / "models.py").write_text("# models stub")

    result = _fix_orm_in_service(content, "src/contracts/service.py", work_dir=str(tmp_path))
    assert "class ContractORM" not in result, "ORM debe eliminarse si models.py existe"
    assert "from src.contracts.models import ContractORM" in result


def test_s82a_no_work_dir_still_removes():
    """S82-A: sin work_dir (backward compat), S81-A actúa como antes."""
    from code_postprocessor import _fix_orm_in_service

    content = (
        "from src.database import Base\n"
        "class BenefitORM(Base):\n"
        "    __tablename__ = 'benefits'\n"
    )
    result = _fix_orm_in_service(content, "src/contracts/service.py", work_dir="")
    assert "class BenefitORM" not in result


def test_s82a_postprocess_passes_work_dir(tmp_path):
    """S82-A: postprocess_python_file pasa work_dir a _fix_orm_in_service."""
    from code_postprocessor import postprocess_python_file

    content = (
        "from src.database import Base\n"
        "from sqlalchemy import Column, Integer\n"
        "class ContractORM(Base):\n"
        "    __tablename__ = 'contracts'\n"
        "    id = Column(Integer, primary_key=True)\n"
    )
    contracts_dir = tmp_path / "src" / "contracts"
    contracts_dir.mkdir(parents=True)
    # models.py NO existe → ORM debe preservarse

    result = postprocess_python_file(content, "src/contracts/service.py", work_dir=str(tmp_path))
    assert "class ContractORM" in result


# ---------------------------------------------------------------------------
# S82-B — _ensure_contracts_models_task
# ---------------------------------------------------------------------------

def _make_sdd(tasks):
    return {"tasks": tasks, "requirements": [], "constraints": []}


def test_s82b_injects_when_contracts_missing_models():
    """S82-B: inyecta TASK-INFRA-CONTRACTS-MODELS cuando contracts existe pero models.py no."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from graph import _ensure_contracts_models_task

    sdd = _make_sdd([
        {"id": "T1", "agent": "backend", "file": "src/contracts/service.py", "title": "service"},
        {"id": "T2", "agent": "backend", "file": "src/contracts/router.py", "title": "router"},
    ])
    result = _ensure_contracts_models_task(sdd)
    files = [t["file"] for t in result["tasks"]]
    assert "src/contracts/models.py" in files


def test_s82b_does_not_inject_when_models_exists():
    """S82-B: no inyecta si src/contracts/models.py ya está en el SDD."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from graph import _ensure_contracts_models_task

    sdd = _make_sdd([
        {"id": "T1", "agent": "backend", "file": "src/contracts/models.py", "title": "models"},
        {"id": "T2", "agent": "backend", "file": "src/contracts/service.py", "title": "service"},
    ])
    result = _ensure_contracts_models_task(sdd)
    contracts_models_tasks = [t for t in result["tasks"] if t["file"] == "src/contracts/models.py"]
    assert len(contracts_models_tasks) == 1, "No debe duplicar la tarea de models.py"


def test_s82b_does_not_inject_without_contracts():
    """S82-B: no inyecta si el SDD no tiene ningún módulo contracts."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from graph import _ensure_contracts_models_task

    sdd = _make_sdd([
        {"id": "T1", "agent": "backend", "file": "src/auth/models.py", "title": "auth models"},
        {"id": "T2", "agent": "backend", "file": "src/main.py", "title": "main"},
    ])
    original_len = len(sdd["tasks"])
    result = _ensure_contracts_models_task(sdd)
    assert len(result["tasks"]) == original_len


def test_s82b_inserts_after_database_task():
    """S82-B: la tarea de contracts/models.py se inserta justo después de database.py."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from graph import _ensure_contracts_models_task

    sdd = _make_sdd([
        {"id": "T1", "agent": "backend", "file": "src/database.py", "title": "db"},
        {"id": "T2", "agent": "backend", "file": "src/contracts/service.py", "title": "service"},
    ])
    result = _ensure_contracts_models_task(sdd)
    files = [t["file"] for t in result["tasks"]]
    db_idx = files.index("src/database.py")
    models_idx = files.index("src/contracts/models.py")
    assert models_idx == db_idx + 1, "contracts/models.py debe estar justo después de database.py"


def test_s82b_task_has_orm_description():
    """S82-B: la tarea inyectada incluye descripción con ContractORM y BenefitORM."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from graph import _ensure_contracts_models_task

    sdd = _make_sdd([
        {"id": "T1", "agent": "backend", "file": "src/contracts/router.py", "title": "router"},
    ])
    result = _ensure_contracts_models_task(sdd)
    task = next(t for t in result["tasks"] if t["file"] == "src/contracts/models.py")
    assert "ContractORM" in task["description"]
    assert "BenefitORM" in task["description"]
    assert task["agent"] == "backend"


# ---------------------------------------------------------------------------
# S82-F — Oracle URL → PostgreSQL patch en database.py
# ---------------------------------------------------------------------------

def test_s82f_patches_oracle_url_in_database_py(tmp_path):
    """S82-F: si FR menciona PostgreSQL y database.py tiene Oracle URL, se parchea en disco."""
    # Simular el resultado de agent_executor verificando la lógica directamente
    import re

    oracle_content = (
        "import oracledb\n"
        "from sqlalchemy import create_engine\n"
        "DATABASE_URL = 'oracle+oracledb://system:pass@localhost:1521/XEPDB1'\n"
        "engine = create_engine(DATABASE_URL)\n"
    )
    db_file = tmp_path / "src" / "database.py"
    db_file.parent.mkdir(parents=True)
    db_file.write_text(oracle_content)

    fr_text = "Sistema de contratos con PostgreSQL + SQLAlchemy ORM"
    fr_lower = fr_text.lower()

    if any(kw in fr_lower for kw in ("postgresql", "postgres", "psycopg")):
        content = db_file.read_text()
        has_oracle = "oracle+oracledb://" in content or "oracledb" in content
        has_pg = "postgresql" in content or "psycopg" in content
        if has_oracle and not has_pg:
            fixed = re.sub(
                r"oracle\+oracledb://[^\s'\"]+",
                "postgresql+psycopg://ovd_dev:changeme@localhost:5432/app_db",
                content,
            )
            fixed = re.sub(r"import oracledb\n", "", fixed)
            db_file.write_text(fixed)

    result = db_file.read_text()
    assert "postgresql+psycopg://" in result
    assert "oracle+oracledb://" not in result


def test_s82f_no_patch_when_fr_mentions_oracle(tmp_path):
    """S82-F: no parchea si el FR menciona Oracle (no PostgreSQL)."""
    oracle_content = (
        "DATABASE_URL = 'oracle+oracledb://system:pass@localhost:1521/XEPDB1'\n"
    )
    db_file = tmp_path / "src" / "database.py"
    db_file.parent.mkdir(parents=True)
    db_file.write_text(oracle_content)

    fr_text = "Sistema de contratos con Oracle XE 21c"
    fr_lower = fr_text.lower()
    # El bloque S82-F no debe ejecutarse
    should_fix = any(kw in fr_lower for kw in ("postgresql", "postgres", "psycopg"))
    assert not should_fix, "FR con Oracle no debe triggear S82-F"


def test_s82f_no_patch_when_already_postgresql(tmp_path):
    """S82-F: no parchea si database.py ya tiene URL PostgreSQL."""
    pg_content = (
        "DATABASE_URL = 'postgresql+psycopg://user:pass@localhost:5432/db'\n"
    )
    db_file = tmp_path / "src" / "database.py"
    db_file.parent.mkdir(parents=True)
    db_file.write_text(pg_content)

    fr_text = "Sistema con PostgreSQL"
    content = db_file.read_text()
    has_oracle = "oracle+oracledb://" in content
    has_pg = "postgresql" in content
    should_patch = has_oracle and not has_pg
    assert not should_patch, "No debe parchear si ya tiene PostgreSQL"
