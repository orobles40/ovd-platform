"""Tests for S86: contracts/service.py injection, __init__.py fix."""
import os
import sys
import pytest

_ENGINE_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, _ENGINE_DIR)


# ---------------------------------------------------------------------------
# S86-A — _ensure_contracts_service_task
# ---------------------------------------------------------------------------

def _make_sdd(*files):
    return {"tasks": [{"id": f"T{i}", "agent": "backend", "file": f, "title": f, "description": "", "depends_on": []} for i, f in enumerate(files)]}


def test_s86a_injects_service_when_missing():
    """S86-A: inyecta contracts/service.py cuando contracts/models.py existe pero no service.py."""
    from graph import _ensure_contracts_service_task
    sdd = _make_sdd("src/contracts/models.py", "tests/test_contracts.py")
    result = _ensure_contracts_service_task(sdd)
    files = [t["file"] for t in result["tasks"]]
    assert "src/contracts/service.py" in files


def test_s86a_no_inject_if_service_exists():
    """S86-A: no inyecta si contracts/service.py ya existe."""
    from graph import _ensure_contracts_service_task
    sdd = _make_sdd("src/contracts/models.py", "src/contracts/service.py")
    result = _ensure_contracts_service_task(sdd)
    service_count = sum(1 for t in result["tasks"] if "contracts/service" in t["file"])
    assert service_count == 1


def test_s86a_no_inject_without_contracts_module():
    """S86-A: no inyecta si no hay módulo contracts en el SDD."""
    from graph import _ensure_contracts_service_task
    sdd = _make_sdd("src/auth/models.py", "src/database.py")
    result = _ensure_contracts_service_task(sdd)
    files = [t["file"] for t in result["tasks"]]
    assert "src/contracts/service.py" not in files


def test_s86a_injected_after_models():
    """S86-A: contracts/service.py se inserta inmediatamente después de contracts/models.py."""
    from graph import _ensure_contracts_service_task
    sdd = _make_sdd("src/database.py", "src/contracts/models.py", "src/main.py")
    result = _ensure_contracts_service_task(sdd)
    files = [t["file"] for t in result["tasks"]]
    models_idx = files.index("src/contracts/models.py")
    service_idx = files.index("src/contracts/service.py")
    assert service_idx == models_idx + 1


def test_s86a_injected_task_has_required_fields():
    """S86-A: la tarea inyectada tiene todos los campos requeridos."""
    from graph import _ensure_contracts_service_task
    sdd = _make_sdd("src/contracts/models.py")
    result = _ensure_contracts_service_task(sdd)
    task = next(t for t in result["tasks"] if "contracts/service" in t.get("file", ""))
    assert task["id"] == "TASK-INFRA-CONTRACTS-SERVICE"
    assert task["agent"] == "backend"
    assert "create_contract" in task["description"]
    assert "list_benefits" in task["description"]
    assert "create_benefit" in task["description"]


def test_s86a_description_mentions_orm_import():
    """S86-A: la descripción indica que ContractORM viene de contracts/models.py."""
    from graph import _ensure_contracts_service_task
    sdd = _make_sdd("src/contracts/models.py")
    result = _ensure_contracts_service_task(sdd)
    task = next(t for t in result["tasks"] if "contracts/service" in t.get("file", ""))
    assert "contracts/models.py" in task["description"] or "contracts.models" in task["description"]


def test_s86a_wired_in_generate_sdd():
    """S86-A: _ensure_contracts_service_task está referenciada en graph.py."""
    import pathlib
    graph_path = pathlib.Path(_ENGINE_DIR) / "graph.py"
    src = graph_path.read_text()
    assert "_ensure_contracts_service_task" in src


def test_s86a_called_after_contracts_models():
    """S86-A: la llamada a _ensure_contracts_service_task va después de _ensure_contracts_models_task."""
    import pathlib
    graph_path = pathlib.Path(_ENGINE_DIR) / "graph.py"
    src = graph_path.read_text()
    idx_models = src.index("_ensure_contracts_models_task(sdd)")
    idx_service = src.index("_ensure_contracts_service_task(sdd)")
    assert idx_service > idx_models


# ---------------------------------------------------------------------------
# S86-C — __init__.py vacío recibe comentario mínimo
# ---------------------------------------------------------------------------

def test_s86c_empty_init_gets_placeholder():
    """S86-C: __init__.py vacío después del postprocessor recibe '# src package'."""
    from code_postprocessor import postprocess_python_file
    result = postprocess_python_file("", "src/__init__.py")
    assert result.strip(), "S86-C: __init__.py no debe quedar vacío"
    assert result.startswith("# ")


def test_s86c_nonempty_init_unchanged():
    """S86-C: __init__.py con contenido real no se modifica."""
    from code_postprocessor import postprocess_python_file
    content = "from src.models import Base\n"
    result = postprocess_python_file(content, "src/__init__.py")
    assert "from src.models import Base" in result


def test_s86c_subdirectory_init_placeholder():
    """S86-C: __init__.py en subdirectorio también recibe placeholder."""
    from code_postprocessor import postprocess_python_file
    result = postprocess_python_file("", "src/contracts/__init__.py")
    assert result.strip()


def test_s86c_non_init_empty_unchanged():
    """S86-C: archivos .py vacíos que no son __init__.py no reciben placeholder."""
    from code_postprocessor import postprocess_python_file
    result = postprocess_python_file("", "src/contracts/service.py")
    assert result == ""


# ---------------------------------------------------------------------------
# S86-B — _ensure_contracts_router_task
# ---------------------------------------------------------------------------

def test_s86b_injects_router_when_missing():
    """S86-B: inyecta contracts/router.py cuando contracts/service.py existe pero no router.py."""
    from graph import _ensure_contracts_router_task
    sdd = _make_sdd("src/contracts/service.py", "src/main.py")
    result = _ensure_contracts_router_task(sdd)
    files = [t["file"] for t in result["tasks"]]
    assert "src/contracts/router.py" in files


def test_s86b_no_inject_if_router_exists():
    """S86-B: no inyecta si contracts/router.py ya existe."""
    from graph import _ensure_contracts_router_task
    sdd = _make_sdd("src/contracts/service.py", "src/contracts/router.py")
    result = _ensure_contracts_router_task(sdd)
    router_count = sum(1 for t in result["tasks"] if "contracts/router" in t["file"])
    assert router_count == 1


def test_s86b_no_inject_without_contracts_service():
    """S86-B: no inyecta si no hay contracts/service.py en el SDD."""
    from graph import _ensure_contracts_router_task
    sdd = _make_sdd("src/auth/service.py", "src/main.py")
    result = _ensure_contracts_router_task(sdd)
    files = [t["file"] for t in result["tasks"]]
    assert "src/contracts/router.py" not in files


def test_s86b_injected_after_service():
    """S86-B: contracts/router.py se inserta después de contracts/service.py."""
    from graph import _ensure_contracts_router_task
    sdd = _make_sdd("src/contracts/models.py", "src/contracts/service.py", "src/main.py")
    result = _ensure_contracts_router_task(sdd)
    files = [t["file"] for t in result["tasks"]]
    service_idx = files.index("src/contracts/service.py")
    router_idx = files.index("src/contracts/router.py")
    assert router_idx == service_idx + 1


def test_s86b_description_mentions_crud_endpoints():
    """S86-B: la descripción incluye los endpoints CRUD principales."""
    from graph import _ensure_contracts_router_task
    sdd = _make_sdd("src/contracts/service.py")
    result = _ensure_contracts_router_task(sdd)
    task = next(t for t in result["tasks"] if "contracts/router" in t.get("file", ""))
    assert "create_contract" in task["description"]
    assert "list_benefits" in task["description"]


def test_s86b_wired_in_generate_sdd():
    """S86-B: _ensure_contracts_router_task está referenciada en graph.py."""
    import pathlib
    graph_path = pathlib.Path(_ENGINE_DIR) / "graph.py"
    src = graph_path.read_text()
    assert "_ensure_contracts_router_task" in src
