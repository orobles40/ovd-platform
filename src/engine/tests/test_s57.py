"""
OVD Platform — Tests S57

S57-A: _keep_best_qa reducer preserva el mejor score QA del ciclo
S57-B: run_tests distingue exit 4 (USAGE_ERROR) de collection errors reales (rc=1)
S57-C: conftest.py se regenera en rounds de retry
S57-D: _write_artifacts(preserve_nonempty=True) en fallback de tool calling
"""
import sys, os, pathlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import logging
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

import graph


# ---------------------------------------------------------------------------
# S57-A: _keep_best_qa reducer
# ---------------------------------------------------------------------------

def test_keep_best_qa_prefers_higher_score():
    """S57-A: con score mayor en update, reemplaza el existente."""
    existing = {"score": 65, "passed": False, "sdd_compliance": False}
    update   = {"score": 95, "passed": True,  "sdd_compliance": True}
    result = graph._keep_best_qa(existing, update)
    assert result["score"] == 95
    assert result["sdd_compliance"] is True


def test_keep_best_qa_preserves_existing_when_update_lower():
    """S57-A: si update tiene score menor, preserva el existente."""
    existing = {"score": 95, "passed": True,  "sdd_compliance": True}
    update   = {"score": 65, "passed": False, "sdd_compliance": False}
    result = graph._keep_best_qa(existing, update)
    assert result["score"] == 95
    assert result["sdd_compliance"] is True


def test_keep_best_qa_empty_existing_returns_update():
    """S57-A: estado inicial vacío → retorna el primer update."""
    result = graph._keep_best_qa({}, {"score": 65, "passed": False})
    assert result["score"] == 65


def test_keep_best_qa_empty_update_returns_existing():
    """S57-A: update vacío → preserva existente."""
    existing = {"score": 80, "passed": True}
    result = graph._keep_best_qa(existing, {})
    assert result["score"] == 80


def test_keep_best_qa_equal_scores_preserves_existing():
    """S57-A: scores iguales → no reemplaza (semantica estable)."""
    existing = {"score": 75, "passed": True,  "sdd_compliance": True}
    update   = {"score": 75, "passed": False, "sdd_compliance": False}
    result = graph._keep_best_qa(existing, update)
    # Con scores iguales, >= preserva el existente
    assert result["sdd_compliance"] is True


def test_keep_best_qa_cycle_simulation():
    """S57-A: simulación del ciclo S56 — 65→95→65 debe reportar 95."""
    state = {}
    state = graph._keep_best_qa(state, {"score": 65, "passed": False, "sdd_compliance": False})
    state = graph._keep_best_qa(state, {"score": 95, "passed": True,  "sdd_compliance": True})
    state = graph._keep_best_qa(state, {"score": 65, "passed": False, "sdd_compliance": False})
    assert state["score"] == 95, f"Esperado 95, got {state['score']}"
    assert state["sdd_compliance"] is True


# ---------------------------------------------------------------------------
# S57-B: corrección exit codes pytest
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_tests_exit4_logs_usage_error(tmp_path, caplog):
    """S57-B: pytest exit 4 se registra como USAGE_ERROR, no collection error."""
    # Crear estructura mínima con test file
    test_file = tmp_path / "tests" / "test_dummy.py"
    test_file.parent.mkdir()
    test_file.write_text("def test_ok(): assert True\n")

    state = {
        "test_results": {},
        "agent_results": [{"agent": "backend", "artifacts": [], "output": ""}],
        "directory": str(tmp_path),
        "retry_feedback": "",
        "test_retry_count": 0,
        "cycle_start_ts": 0,
        "selective_retry_agents": [],
        "language": "es",
        "stack_language": "python",
        "org_id": "",
        "project_id": "",
        "jwt_token": "",
        "stack_routing": "auto",
    }

    # Simular un proceso que retorna exit 4
    mock_proc = AsyncMock()
    mock_proc.returncode = 4
    mock_proc.communicate = AsyncMock(return_value=(b"ERROR: unrecognized arguments: --bad-flag", None))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with caplog.at_level(logging.WARNING, logger="ovd-graph"):
            await graph.run_tests(state)

    warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("S57-B" in m and "USAGE_ERROR" in m for m in warning_msgs), \
        f"No se encontró WARNING S57-B USAGE_ERROR. Mensajes: {warning_msgs}"
    # No debe mencionar "collection error" en exit 4
    assert not any("collection error" in m.lower() and "exit 4" in m for m in warning_msgs), \
        "Exit 4 sigue siendo descrito como collection error"


@pytest.mark.asyncio
async def test_run_tests_exit1_zero_items_detected_as_collection_error(tmp_path, caplog):
    """S57-B: rc=1 con 'collected 0 items' + ImportError → detection de collection error."""
    test_file = tmp_path / "tests" / "test_dummy.py"
    test_file.parent.mkdir()
    test_file.write_text("def test_ok(): assert True\n")

    state = {
        "test_results": {},
        "agent_results": [{"agent": "backend", "artifacts": [], "output": ""}],
        "directory": str(tmp_path),
        "retry_feedback": "",
        "test_retry_count": 0,
        "cycle_start_ts": 0,
        "selective_retry_agents": [],
        "language": "es",
        "stack_language": "python",
        "org_id": "",
        "project_id": "",
        "jwt_token": "",
        "stack_routing": "auto",
    }

    collection_error_output = (
        b"collected 0 items / 1 error\n"
        b"ImportError: cannot import name 'calcular_imc' from 'src.imc.service'\n"
    )
    mock_proc = AsyncMock()
    mock_proc.returncode = 1
    mock_proc.communicate = AsyncMock(return_value=(collection_error_output, None))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with caplog.at_level(logging.WARNING, logger="ovd-graph"):
            await graph.run_tests(state)

    warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("S57-B" in m and "collection error" in m.lower() for m in warning_msgs), \
        f"No se detectó collection error S57-B. Mensajes: {warning_msgs}"


# ---------------------------------------------------------------------------
# S57-C: conftest.py regenerado en retry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_conftest_regenerated_in_retry_round(tmp_path, caplog):
    """S57-C: en retry_round>0, conftest.py se regenera aunque ya exista."""
    # Crear conftest con contenido viejo (apunta a ruta que ya no existe)
    conftest = tmp_path / "conftest.py"
    conftest.write_text("import sys\nsys.path.insert(0, 'old/path')\n")
    old_content = conftest.read_text()

    test_file = tmp_path / "tests" / "test_dummy.py"
    test_file.parent.mkdir()
    test_file.write_text("def test_ok(): assert True\n")

    state = {
        "test_results": {},
        "agent_results": [{"agent": "backend", "artifacts": [], "output": ""}],
        "directory": str(tmp_path),
        "retry_feedback": "retry round anterior falló con ImportError",
        "test_retry_count": 1,
        "cycle_start_ts": 0,
        "selective_retry_agents": [],
        "language": "es",
        "stack_language": "python",
        "org_id": "",
        "project_id": "",
        "jwt_token": "",
        "stack_routing": "auto",
    }

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"1 passed", None))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with caplog.at_level(logging.WARNING, logger="ovd-graph"):
            await graph.run_tests(state)

    # El conftest debe haber sido regenerado (contenido diferente al viejo)
    new_content = conftest.read_text()
    assert new_content != old_content, "conftest.py no fue regenerado en retry"
    assert "src" in new_content, "conftest.py regenerado no apunta a src/"

    warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("S57-C" in m for m in warning_msgs), \
        f"No se encontró WARNING S57-C. Mensajes: {warning_msgs}"


@pytest.mark.asyncio
async def test_conftest_not_regenerated_in_first_round(tmp_path):
    """S57-C: en retry_round=0, conftest.py existente NO se toca."""
    conftest = tmp_path / "conftest.py"
    conftest.write_text("# conftest personalizado\nimport sys\n")
    original = conftest.read_text()

    test_file = tmp_path / "tests" / "test_dummy.py"
    test_file.parent.mkdir()
    test_file.write_text("def test_ok(): assert True\n")

    state = {
        "test_results": {},
        "agent_results": [{"agent": "backend", "artifacts": [], "output": ""}],
        "directory": str(tmp_path),
        "retry_feedback": "",
        "test_retry_count": 0,
        "cycle_start_ts": 0,
        "selective_retry_agents": [],
        "language": "es",
        "stack_language": "python",
        "org_id": "",
        "project_id": "",
        "jwt_token": "",
        "stack_routing": "auto",
    }

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"1 passed", None))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        await graph.run_tests(state)

    assert conftest.read_text() == original, "conftest.py fue modificado en round 0 (no debe serlo)"


# ---------------------------------------------------------------------------
# S57-D: preserve_nonempty en fallback de tool calling
# ---------------------------------------------------------------------------

def test_write_artifacts_fallback_preserves_with_retry_feedback(tmp_path):
    """S57-D: fallback _write_artifacts usa preserve_nonempty=True cuando hay retry_feedback."""
    # Archivo existente con contenido válido
    target = tmp_path / "src" / "imc" / "service.py"
    target.parent.mkdir(parents=True)
    original = "def calcular_imc(peso, altura):\n    return round(peso/altura**2, 2), 'Normal'\n"
    target.write_text(original)

    # Nuevo output con contenido vacío (LLM truncado)
    output_truncado = "```python:src/imc/service.py\n\n```"

    result = graph._write_artifacts(output_truncado, str(tmp_path), "backend", preserve_nonempty=True)

    assert target.read_text() == original, "Archivo fue sobreescrito con contenido vacío (no debe)"
    assert len(result) == 1
