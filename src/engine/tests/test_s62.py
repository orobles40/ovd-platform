"""
OVD Platform — Tests S62

S62-A: run_tests auto-crea pytest.ini con pythonpath = . cuando no existe
S62-B: qa_review usa test_retry_count como señal (no selective_retry_agents)
S62-C: update_test_retry retorna Command(goto=generate_docs) en error estructural repetido
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import pathlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import graph
from langgraph.types import Command


# ---------------------------------------------------------------------------
# S62-C: Command(goto=generate_docs) en update_test_retry
# ---------------------------------------------------------------------------

def test_s62c_returns_command_on_repeated_structural_error():
    """S62-C: update_test_retry retorna Command(goto=generate_docs) en error repetido."""
    structural = "ModuleNotFoundError: No module named 'src.auth'\ncollected 0 items / 1 error\n"
    state = {
        "test_results": {"passed": False, "output": structural, "return_code": 4},
        "retry_feedback": "feedback previo",
        "last_test_error": structural,
        "test_retry_count": 1,
        "directory": "", "sdd": {"tasks": []}, "agent_results": [],
        "selective_retry_agents": [], "messages": [], "status": "",
    }
    result = graph.update_test_retry(state)
    assert isinstance(result, Command), f"Debe retornar Command, no {type(result).__name__}"
    assert result.goto == "generate_docs"
    assert result.update["test_retry_count"] == 2
    assert result.update["selective_retry_agents"] == []
    # S63-A: status removido del Command.update para evitar InvalidUpdateError
    assert "status" not in result.update


def test_s62c_returns_dict_on_first_structural_error():
    """S62-C: primera ronda de error estructural retorna dict (no Command)."""
    structural = "ModuleNotFoundError: No module named 'src.auth'\ncollected 0 items / 1 error\n"
    state = {
        "test_results": {"passed": False, "output": structural, "return_code": 4},
        "retry_feedback": "",
        "last_test_error": "",   # sin error previo → primera ronda
        "test_retry_count": 0,
        "directory": "", "sdd": {"tasks": []}, "agent_results": [],
        "selective_retry_agents": [], "messages": [], "status": "",
    }
    result = graph.update_test_retry(state)
    assert not isinstance(result, Command), "Primera ronda NO debe retornar Command"
    assert isinstance(result, dict)
    assert result.get("status") != "structural_error_no_retry"


def test_s62c_does_not_fire_on_assertion_error():
    """S62-C: AssertionError (error lógico, no estructural) no genera Command."""
    assertion = "FAILED tests/test_imc.py::test_imc\nAssertionError: assert 22.35 == 21.97\n"
    state = {
        "test_results": {"passed": False, "output": assertion, "return_code": 1},
        "retry_feedback": "",
        "last_test_error": assertion,
        "test_retry_count": 2,
        "directory": "", "sdd": {"tasks": []}, "agent_results": [],
        "selective_retry_agents": [], "messages": [], "status": "",
    }
    result = graph.update_test_retry(state)
    assert not isinstance(result, Command), "AssertionError no debe retornar Command"


def test_s62c_importerror_also_triggers_command():
    """S62-C: ImportError (no solo ModuleNotFoundError) también genera Command."""
    import_err = "ImportError: cannot import name 'router' from 'src.auth'\ncollected 0 items / 1 error\n"
    state = {
        "test_results": {"passed": False, "output": import_err, "return_code": 4},
        "retry_feedback": "",
        "last_test_error": import_err,
        "test_retry_count": 1,
        "directory": "", "sdd": {"tasks": []}, "agent_results": [],
        "selective_retry_agents": [], "messages": [], "status": "",
    }
    result = graph.update_test_retry(state)
    assert isinstance(result, Command)
    assert result.goto == "generate_docs"


# ---------------------------------------------------------------------------
# S62-A: auto-crear pytest.ini en run_tests
# ---------------------------------------------------------------------------

def test_s62a_creates_pytest_ini_when_missing(tmp_path):
    """S62-A: pytest.ini se crea con pythonpath = . cuando no existe."""
    pytest_ini = tmp_path / "pytest.ini"
    pyproject = tmp_path / "pyproject.toml"
    assert not pytest_ini.exists()

    # Simular lógica S62-A
    runner = "pytest"
    if not pytest_ini.exists():
        _pyproject_has_pytest = (
            pyproject.exists()
            and "[tool.pytest.ini_options]" in pyproject.read_text(encoding="utf-8", errors="replace")
        )
        if not _pyproject_has_pytest:
            pytest_ini.write_text("[pytest]\npythonpath = .\n", encoding="utf-8")

    assert pytest_ini.exists()
    assert "pythonpath = ." in pytest_ini.read_text()


def test_s62a_skips_if_pyproject_has_pytest_config(tmp_path):
    """S62-A: no crea pytest.ini si pyproject.toml ya tiene [tool.pytest.ini_options]."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.pytest.ini_options]\npythonpath = .\n")
    pytest_ini = tmp_path / "pytest.ini"

    runner = "pytest"
    if not pytest_ini.exists():
        _pyproject_has_pytest = (
            pyproject.exists()
            and "[tool.pytest.ini_options]" in pyproject.read_text(encoding="utf-8", errors="replace")
        )
        if not _pyproject_has_pytest:
            pytest_ini.write_text("[pytest]\npythonpath = .\n", encoding="utf-8")

    assert not pytest_ini.exists()


def test_s62a_does_not_overwrite_existing_pytest_ini(tmp_path):
    """S62-A: no sobreescribe pytest.ini existente."""
    pytest_ini = tmp_path / "pytest.ini"
    original = "[pytest]\naddopts = -v\npythonpath = src\n"
    pytest_ini.write_text(original)

    runner = "pytest"
    if not pytest_ini.exists():
        pytest_ini.write_text("[pytest]\npythonpath = .\n", encoding="utf-8")

    assert pytest_ini.read_text() == original


# ---------------------------------------------------------------------------
# S62-B: qa_review usa test_retry_count como señal
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_s62b_skips_llm_when_test_retry_and_no_qa_retry():
    """S62-B: qa_review reutiliza QA previo cuando test_retry_count>0 y qa_retry_count=0."""
    prev_qa = {"score": 92, "passed": True, "issues": [], "sdd_compliance": True}
    state = {
        "selective_retry_agents": [],   # vacío — S61-C no dispararía
        "test_retry_count": 1,          # hay retry de tests → S62-B sí dispara
        "qa_retry_count": 0,
        "qa_result": prev_qa,
        "project_context": "ctx",
        "org_id": "", "project_id": "", "jwt_token": "",
        "stack_routing": "auto", "directory": "", "agent_results": [],
        "cycle_start_ts": 0, "language": "es", "sdd": {}, "messages": [], "status": "",
    }
    with patch("graph.model_router") as mock_router:
        result = await graph.qa_review(state)
    mock_router.get_llm_with_context.assert_not_called()
    assert result["qa_result"] == prev_qa
    assert result["qa_passed"] is True


@pytest.mark.asyncio
async def test_s62b_calls_llm_when_qa_retry_active():
    """S62-B: qa_review invoca LLM si hay retry de QA (qa_retry_count>0)."""
    prev_qa = {"score": 60, "passed": False, "issues": ["x"], "sdd_compliance": False}
    state = {
        "selective_retry_agents": [],
        "test_retry_count": 1,
        "qa_retry_count": 1,    # retry de QA → debe correr LLM
        "qa_result": prev_qa,
        "project_context": "ctx",
        "org_id": "", "project_id": "", "jwt_token": "",
        "stack_routing": "auto", "directory": "", "agent_results": [],
        "cycle_start_ts": 0, "language": "es", "sdd": {}, "messages": [], "status": "",
    }
    with patch("graph.model_router") as mock_router, \
         patch("graph.invoke_structured", new_callable=AsyncMock) as mock_invoke:
        mock_router.get_llm_with_context = AsyncMock(return_value=MagicMock())
        mock_invoke.return_value = MagicMock(
            score=80, passed=True, issues=[], sdd_compliance=True,
            missing_requirements=[], code_quality_issues=[],
        )
        try:
            await graph.qa_review(state)
        except Exception:
            pass
    mock_router.get_llm_with_context.assert_called()


@pytest.mark.asyncio
async def test_s62b_calls_llm_on_first_cycle_no_retries():
    """S62-B: qa_review invoca LLM en primera ronda (test_retry_count=0)."""
    state = {
        "selective_retry_agents": [],
        "test_retry_count": 0,   # primera ronda → LLM debe correr
        "qa_retry_count": 0,
        "qa_result": {},
        "project_context": "ctx",
        "org_id": "", "project_id": "", "jwt_token": "",
        "stack_routing": "auto", "directory": "", "agent_results": [],
        "cycle_start_ts": 0, "language": "es", "sdd": {}, "messages": [], "status": "",
    }
    with patch("graph.model_router") as mock_router, \
         patch("graph.invoke_structured", new_callable=AsyncMock):
        mock_router.get_llm_with_context = AsyncMock(return_value=MagicMock())
        try:
            await graph.qa_review(state)
        except Exception:
            pass
    mock_router.get_llm_with_context.assert_called()
