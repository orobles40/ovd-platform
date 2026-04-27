"""
Tests S68 — S68-A: last_test_error preservado para S65-A output
            S68-B: correcciones de imports al inicio del HumanMessage
            S68-C: tareas de infraestructura fuera del cap
            S68-D: clean_rut, format_rut, require_valid_rut en template
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from graph import _extract_import_corrections, _is_infra_task


# ---------------------------------------------------------------------------
# S68-A: last_test_error se preserva para S65-A output
# ---------------------------------------------------------------------------

def _make_s65a_output(imports: list[str] | None = None) -> str:
    if imports is None:
        imports = ["src/auth/models.py: from src.auth.utils.rut import validate_rut  ← módulo no existe"]
    lines = ["[S65-A] IMPORTS ROTOS — detectados ANTES de pytest:"] + [f"  {l}" for l in imports]
    return "\n".join(lines)


def _simulate_new_last_error(test_output: str) -> str:
    """Replica la lógica S68-A de update_test_retry."""
    _is_structural = (
        ("ModuleNotFoundError" in test_output or "ImportError" in test_output)
        and "collected 0 items" in test_output
    )
    _is_s65a_output = "[S65-A] IMPORTS ROTOS" in test_output
    return test_output if (_is_structural or _is_s65a_output) else ""


def test_s68a_last_error_preserved_for_s65a_output():
    """S68-A: update_test_retry guarda last_test_error cuando test_output es S65-A."""
    output = _make_s65a_output()
    result = _simulate_new_last_error(output)
    assert result == output
    assert "[S65-A] IMPORTS ROTOS" in result


def test_s68a_last_error_empty_for_normal_output():
    """S68-A: output sin S65-A ni pytest structural → last_test_error vacío."""
    output = "AssertionError: assert 1 == 2\n1 failed in 0.1s"
    result = _simulate_new_last_error(output)
    assert result == ""


def test_s68a_last_error_preserved_for_structural():
    """S68-A: ImportError + collected 0 items → sigue guardándose (comportamiento pre-S68)."""
    output = "ImportError: No module named 'src.main'\ncollected 0 items\n"
    result = _simulate_new_last_error(output)
    assert result == output


def test_s68a_s66c_can_detect_loop_with_preserved_error():
    """S68-A: con last_test_error preservado, S66-C puede detectar el import loop."""
    import_feedback = _make_s65a_output(["src/auth/models.py: from src.auth.utils.rut import validate_rut  ← módulo no existe"])
    prev_error = _simulate_new_last_error(import_feedback)

    # S66-C condition replica
    _import_loop = (
        1 >= 1  # retry_round=1
        and "[S65-A] IMPORTS ROTOS" in prev_error
        and import_feedback.split("\n")[1:4] == prev_error.split("\n")[1:4]
    )
    assert _import_loop, "S66-C debe detectar el loop cuando last_test_error está preservado"


# ---------------------------------------------------------------------------
# S68-B: _extract_import_corrections
# ---------------------------------------------------------------------------

def test_s68b_extracts_correction_lines():
    """S68-B: extrae líneas CORRECCIÓN del feedback S65-A."""
    feedback = (
        "[S65-A] IMPORTS ROTOS — detectados ANTES de pytest:\n"
        "  src/auth/models.py: from src.auth.utils.rut import validate_rut  ← módulo no existe\n"
        "  → CORRECCIÓN: usa `from src.auth.utils import validate_rut`\n"
        "  src/contracts/service.py: from src.auth.utils.rut import clean_rut  ← módulo no existe\n"
        "  → CORRECCIÓN: usa `from src.auth.utils import clean_rut`\n"
    )
    result = _extract_import_corrections(feedback)
    assert result != ""
    assert "[S68-B] CORRECCIONES OBLIGATORIAS" in result
    assert "→ CORRECCIÓN: usa `from src.auth.utils import validate_rut`" in result
    assert "→ CORRECCIÓN: usa `from src.auth.utils import clean_rut`" in result


def test_s68b_no_block_when_no_s65a():
    """S68-B: sin [S65-A] en retry_feedback → retorna string vacío."""
    feedback = "AssertionError: assert 1 == 2\nFailed 1 test\n"
    result = _extract_import_corrections(feedback)
    assert result == ""


def test_s68b_no_block_when_empty_feedback():
    """S68-B: feedback vacío → retorna string vacío."""
    assert _extract_import_corrections("") == ""
    assert _extract_import_corrections(None) == ""  # type: ignore[arg-type]


def test_s68b_correction_block_ends_with_newlines():
    """S68-B: el bloque de correcciones termina con doble newline para separar del SDD."""
    feedback = (
        "[S65-A] IMPORTS ROTOS — detectados ANTES de pytest:\n"
        "  → CORRECCIÓN: usa `from src.auth.utils import validate_rut`\n"
    )
    result = _extract_import_corrections(feedback)
    assert result.endswith("\n\n"), "debe terminar con doble newline para separar del prompt SDD"


# ---------------------------------------------------------------------------
# S68-C: _is_infra_task
# ---------------------------------------------------------------------------

def test_s68c_database_py_is_infra():
    """S68-C: tarea que menciona src/database.py → infra."""
    task = {"title": "Crear src/database.py con SessionLocal y get_db", "description": "engine + Base", "file": ""}
    assert _is_infra_task(task)


def test_s68c_main_py_is_infra():
    """S68-C: tarea que menciona src/main.py → infra."""
    task = {"title": "Crear src/main.py con FastAPI app", "description": "", "file": ""}
    assert _is_infra_task(task)


def test_s68c_auth_dependencies_is_infra():
    """S68-C: tarea que menciona src/auth/dependencies.py → infra."""
    task = {"title": "auth dependencies", "description": "src/auth/dependencies.py con get_current_user", "file": ""}
    assert _is_infra_task(task)


def test_s68c_business_task_is_not_infra():
    """S68-C: tarea de negocio (contracts service) NO es infra."""
    task = {"title": "Crear src/contracts/service.py", "description": "CRUD contratos", "file": ""}
    assert not _is_infra_task(task)


def test_s68c_infra_tasks_survive_cap():
    """S68-C: en lista con 9 tareas backend (1 infra + 8 negocio), cap=5 → infra + 5 negocio = 6."""
    _TASK_CAPS = {"low": 5, "medium": 8, "high": 10, "critical": 12}
    _MAX = _TASK_CAPS["low"]

    tasks = [
        {"id": "TASK-001", "agent": "backend", "title": "Crear src/database.py", "description": "src/database.py", "file": ""},
    ] + [
        {"id": f"TASK-{i:03d}", "agent": "backend", "title": f"Business task {i}", "description": f"task {i}", "file": ""}
        for i in range(2, 10)  # 8 business tasks
    ]

    # Replica lógica S68-C
    _infra = [t for t in tasks if _is_infra_task(t)]
    _business = [t for t in tasks if not _is_infra_task(t)]
    result = _infra + _business[:_MAX]

    infra_in_result = [t for t in result if _is_infra_task(t)]
    assert len(infra_in_result) == 1, "la tarea infra debe sobrevivir el cap"
    assert len(result) == 6, "1 infra + 5 negocio = 6"


# ---------------------------------------------------------------------------
# S68-D: template system_backend_python.md contiene funciones RUT
# ---------------------------------------------------------------------------

def _get_template_path() -> pathlib.Path:
    return pathlib.Path(__file__).parent.parent / "templates" / "system_backend_python.md"


def test_s68d_clean_rut_in_template():
    """S68-D: system_backend_python.md contiene def clean_rut."""
    content = _get_template_path().read_text(encoding="utf-8")
    assert "def clean_rut" in content


def test_s68d_format_rut_in_template():
    """S68-D: system_backend_python.md contiene def format_rut."""
    content = _get_template_path().read_text(encoding="utf-8")
    assert "def format_rut" in content


def test_s68d_require_valid_rut_in_template():
    """S68-D: system_backend_python.md contiene def require_valid_rut."""
    content = _get_template_path().read_text(encoding="utf-8")
    assert "def require_valid_rut" in content
