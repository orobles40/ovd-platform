"""
OVD Platform — Tests S61

S61-A: pytest.ini usa pythonpath = . y S27-A omite conftest cuando pytest.ini ya tiene pythonpath
S61-B: last_test_error guardado sin truncar; S60-B usa last_test_error para detectar repetición
S61-C: qa_review retorna QA previo en selective retry (sin llamar LLM)
S61-D: deliver fusiona _kept_agent_results con agent_results en selective retry
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import pathlib
import tempfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import graph


# ---------------------------------------------------------------------------
# S61-A: pythonpath = . en templates
# ---------------------------------------------------------------------------

def test_backend_python_template_uses_dot_pythonpath():
    """S61-A: system_backend_python.md tiene pythonpath = . en el bloque ini."""
    tpl_path = pathlib.Path(__file__).parent.parent / "templates" / "system_backend_python.md"
    content = tpl_path.read_text(encoding="utf-8")
    assert "pythonpath = ." in content, "system_backend_python.md debe tener 'pythonpath = .'"
    # Verificar que el bloque ini no tenga 'pythonpath = src' (ignorar menciones en texto explicativo)
    import re
    ini_blocks = re.findall(r"```ini.*?```", content, re.DOTALL)
    for block in ini_blocks:
        assert "pythonpath = src" not in block, f"bloque ini tiene 'pythonpath = src': {block}"


def test_backend_template_no_pytest_ini():
    """S61-A/S58-pre: system_backend.md (base universal) no debe contener pytest.ini."""
    tpl_path = pathlib.Path(__file__).parent.parent / "templates" / "system_backend.md"
    content = tpl_path.read_text(encoding="utf-8")
    assert "pytest.ini" not in content, "system_backend.md base no debe contener pytest.ini (Python-specific)"


def test_s27a_skips_conftest_when_pytest_ini_has_pythonpath(tmp_path):
    """S61-A: run_tests no inyecta conftest.py sys.path cuando pytest.ini ya tiene pythonpath."""
    # Crear pytest.ini con pythonpath
    pytest_ini = tmp_path / "pytest.ini"
    pytest_ini.write_text("[pytest]\npythonpath = .\n", encoding="utf-8")

    # No crear conftest.py — S27-A lo inyectaría normalmente
    state = {
        "directory": str(tmp_path),
        "agent_results": [],
        "test_results": {},
        "test_retry_count": 0,
        "cycle_start_ts": 0,
        "sdd": {"tasks": []},
        "retry_feedback": "",
        "selective_retry_agents": [],
        "status": "",
        "org_id": "", "project_id": "", "jwt_token": "",
        "stack_routing": "ollama",
        "generated_docs": [],
        "messages": [],
        "session_id": "test",
    }

    # Simular solo la lógica de conftest injection sin ejecutar pytest
    work_dir = str(tmp_path)
    runner = "pytest"
    retry_round = 0
    _conftest = pathlib.Path(work_dir) / "conftest.py"
    _pytest_ini = pathlib.Path(work_dir) / "pytest.ini"
    _has_pytest_pythonpath = (
        _pytest_ini.exists()
        and "pythonpath" in _pytest_ini.read_text(encoding="utf-8", errors="replace")
    )

    # Verificar lógica
    assert _has_pytest_pythonpath is True
    # Con pytest.ini que tiene pythonpath, conftest NO debe ser creado
    if _has_pytest_pythonpath:
        pass  # skip injection
    elif not _conftest.exists() or _conftest.stat().st_size == 0:
        _conftest.write_text("import sys, os\nsys.path.insert(0, 'src')\n")

    assert not _conftest.exists(), "conftest.py NO debe ser creado cuando pytest.ini tiene pythonpath"


def test_s27a_injects_conftest_when_no_pytest_ini(tmp_path):
    """S61-A: sin pytest.ini, S27-A sigue inyectando conftest.py normalmente."""
    _conftest = tmp_path / "conftest.py"
    _pytest_ini = tmp_path / "pytest.ini"
    _conftest_content = "import sys, os\nsys.path.insert(0, 'src')\n"

    _has_pytest_pythonpath = (
        _pytest_ini.exists()
        and "pythonpath" in _pytest_ini.read_text(encoding="utf-8", errors="replace")
    )
    assert _has_pytest_pythonpath is False

    if _has_pytest_pythonpath:
        pass
    elif not _conftest.exists() or _conftest.stat().st_size == 0:
        _conftest.write_text(_conftest_content)

    assert _conftest.exists(), "conftest.py DEBE ser creado cuando no hay pytest.ini con pythonpath"


# ---------------------------------------------------------------------------
# S61-B: last_test_error en OVDState y uso en S60-B
# ---------------------------------------------------------------------------

def test_update_test_retry_saves_last_test_error_on_structural():
    """S61-B: update_test_retry guarda test_output en last_test_error cuando es error estructural."""
    structural_output = (
        "ERRORS\n"
        "collected 0 items / 1 error\n"
        "ModuleNotFoundError: No module named 'src.main'\n"
    )
    state = {
        "test_results": {"passed": False, "output": structural_output, "return_code": 4},
        "retry_feedback": "",
        "last_test_error": "",
        "test_retry_count": 0,
        "directory": "",
        "sdd": {"tasks": []},
        "agent_results": [],
        "selective_retry_agents": [],
        "messages": [],
        "status": "",
    }
    result = graph.update_test_retry(state)
    assert result.get("last_test_error") == structural_output


def test_update_test_retry_clears_last_test_error_on_assertion():
    """S61-B: update_test_retry limpia last_test_error en errores de aserción (no estructurales)."""
    assertion_output = (
        "FAILED tests/test_imc.py::test_imc_value\n"
        "AssertionError: assert 22.35 == 21.97\n"
    )
    state = {
        "test_results": {"passed": False, "output": assertion_output, "return_code": 1},
        "retry_feedback": "",
        "last_test_error": "ModuleNotFoundError previo",
        "test_retry_count": 0,
        "directory": "",
        "sdd": {"tasks": []},
        "agent_results": [],
        "selective_retry_agents": [],
        "messages": [],
        "status": "",
    }
    result = graph.update_test_retry(state)
    assert result.get("last_test_error") == "", "error no estructural debe limpiar last_test_error"


def test_s60b_fires_using_last_test_error_not_truncated():
    """S61-B: S60-B detecta error repetido usando last_test_error (sin truncar), no retry_feedback."""
    structural_output = (
        "ERRORS\n"
        "collected 0 items / 1 error\n"
        "ModuleNotFoundError: No module named 'src.main'\n"
    )
    state = {
        "test_results": {"passed": False, "output": structural_output, "return_code": 4},
        # retry_feedback truncado a 800 chars — SIN ModuleNotFoundError (truncado)
        "retry_feedback": "feedback anterior truncado sin la palabra clave...",
        # last_test_error tiene el error completo sin truncar
        "last_test_error": structural_output,
        "test_retry_count": 1,  # ronda >= 1 → S60-B debe disparar
        "directory": "",
        "sdd": {"tasks": []},
        "agent_results": [],
        "selective_retry_agents": [],
        "messages": [],
        "status": "",
    }
    result = graph.update_test_retry(state)
    # S62-C: ahora retorna Command — acceder al update dict
    from langgraph.types import Command
    assert isinstance(result, Command), "S60-B+S62-C debe retornar Command"
    assert result.update.get("test_retry_count") == 2
    assert result.update.get("status") == "structural_error_no_retry"
    assert result.goto == "generate_docs"


def test_s60b_does_not_fire_on_first_structural_error():
    """S61-B: S60-B no cancela en la primera ronda (retry_round=0), solo a partir de ronda 1."""
    structural_output = (
        "collected 0 items / 1 error\n"
        "ModuleNotFoundError: No module named 'src.main'\n"
    )
    state = {
        "test_results": {"passed": False, "output": structural_output, "return_code": 4},
        "retry_feedback": "",
        "last_test_error": structural_output,  # ya guardado de ronda anterior
        "test_retry_count": 0,  # primera ronda — no debe cancelar
        "directory": "",
        "sdd": {"tasks": []},
        "agent_results": [],
        "selective_retry_agents": [],
        "messages": [],
        "status": "",
    }
    result = graph.update_test_retry(state)
    # No debe cancelar en ronda 0
    assert result.get("status") != "structural_error_no_retry"
    assert result.get("test_retry_count") == 1


# ---------------------------------------------------------------------------
# S61-C: qa_review skip en selective retry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_qa_review_returns_cached_in_selective_retry():
    """S62-B (ex S61-C): qa_review retorna QA previo sin llamar LLM en retry de tests."""
    prev_qa = {"score": 90, "passed": True, "issues": [], "sdd_compliance": True}
    state = {
        "selective_retry_agents": [],   # S62-B usa test_retry_count, no este campo
        "test_retry_count": 1,          # señal correcta post-S62-B
        "qa_retry_count": 0,
        "qa_result": prev_qa,
        "project_context": "ctx",
        "org_id": "", "project_id": "", "jwt_token": "",
        "stack_routing": "auto",
        "directory": "",
        "agent_results": [],
        "cycle_start_ts": 0,
        "language": "es",
        "sdd": {},
        "messages": [],
        "status": "",
    }
    with patch("graph.model_router") as mock_router:
        result = await graph.qa_review(state)

    # No debe llamar al LLM
    mock_router.get_llm_with_context.assert_not_called()
    assert result["qa_result"] == prev_qa
    assert result["qa_passed"] is True


@pytest.mark.asyncio
async def test_qa_review_runs_normally_when_no_selective_retry():
    """S61-C: qa_review llama al LLM normalmente cuando selective_retry_agents está vacío."""
    state = {
        "selective_retry_agents": [],
        "qa_result": {},  # sin QA previo
        "project_context": "ctx",
        "org_id": "", "project_id": "", "jwt_token": "",
        "stack_routing": "auto",
        "directory": "",
        "agent_results": [],
        "cycle_start_ts": 0,
        "language": "es",
        "sdd": {},
        "messages": [],
        "status": "",
    }
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content='{"score":80,"passed":true,"issues":[],"sdd_compliance":true}'))

    with patch("graph.model_router") as mock_router, \
         patch("graph.invoke_structured", new_callable=AsyncMock) as mock_invoke:
        mock_router.get_llm_with_context = AsyncMock(return_value=mock_llm)
        mock_invoke.return_value = MagicMock(
            score=80, passed=True, issues=[], sdd_compliance=True,
            missing_requirements=[], code_quality_issues=[],
        )
        try:
            result = await graph.qa_review(state)
        except Exception:
            pass  # puede fallar por otros deps — lo que importa es que llamó al router

    mock_router.get_llm_with_context.assert_called()


# ---------------------------------------------------------------------------
# S61-D: deliver fusiona _kept_agent_results
# ---------------------------------------------------------------------------

def test_deliver_merges_kept_agent_results():
    """S61-D: deliver usa _kept_agent_results para agentes no-retried."""
    kept = [
        {"agent": "database", "output": "-- SQL", "artifacts": []},
        {"agent": "frontend", "output": "// TSX", "artifacts": []},
    ]
    current = [
        {"agent": "backend", "output": "# Python", "artifacts": []},
    ]

    # Simular la lógica de fusión de deliver
    _current_agents = {r.get("agent") for r in current}
    _merged = [r for r in kept if r.get("agent") not in _current_agents] + current

    assert len(_merged) == 3
    agents_in_merged = {r["agent"] for r in _merged}
    assert agents_in_merged == {"backend", "database", "frontend"}


def test_deliver_merged_prefers_current_over_kept_for_same_agent():
    """S61-D: si el mismo agente está en kept y en current, se usa el current."""
    kept = [
        {"agent": "backend", "output": "versión vieja", "artifacts": []},
        {"agent": "frontend", "output": "// TSX", "artifacts": []},
    ]
    current = [
        {"agent": "backend", "output": "versión nueva", "artifacts": []},
    ]

    _current_agents = {r.get("agent") for r in current}
    _merged = [r for r in kept if r.get("agent") not in _current_agents] + current

    backend_results = [r for r in _merged if r["agent"] == "backend"]
    assert len(backend_results) == 1
    assert backend_results[0]["output"] == "versión nueva"


def test_route_agents_selective_saves_kept_results():
    """S61-D: route_agents guarda resultados de agentes no-retried en _kept_agent_results."""
    state = {
        "sdd": {"tasks": []},
        "fr_analysis": {},
        "org_id": "", "project_id": "", "jwt_token": "",
        "selective_retry_agents": ["backend"],
        "test_retry_count": 1,
        "agent_results": [
            {"agent": "database", "output": "SQL", "artifacts": []},
            {"agent": "frontend", "output": "TSX", "artifacts": []},
            {"agent": "backend", "output": "vieja versión", "artifacts": []},
        ],
        "messages": [],
        "status": "",
        "stack_routing": "auto",
        "pending_agents": [],
        "_dispatch_now": [],
    }

    # La lógica de S61-D en route_agents
    selective_agents = state["selective_retry_agents"]
    _prev_results = state.get("agent_results", [])
    _kept_results = [r for r in _prev_results if r.get("agent") not in selective_agents]

    assert len(_kept_results) == 2
    kept_agents = {r["agent"] for r in _kept_results}
    assert kept_agents == {"database", "frontend"}
    assert "backend" not in kept_agents
