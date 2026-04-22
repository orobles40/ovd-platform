"""
S22 — Tests del nodo run_tests, helper _detect_test_runner y routing _route_after_tests.
"""
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.factories import make_state


# ---------------------------------------------------------------------------
# _detect_test_runner
# ---------------------------------------------------------------------------

def _make_agent_results(paths: list[str]) -> list[dict]:
    """Genera agent_results con bloques de código en los paths indicados."""
    blocks = "\n".join(f"```python:{p}\n# code\n```" for p in paths)
    return [{"agent": "backend", "output": blocks}]


def test_detect_test_runner_pytest():
    import graph as g
    results = _make_agent_results(["src/api.py", "tests/test_login.py"])
    assert g._detect_test_runner(results) == "pytest"


def test_detect_test_runner_vitest():
    import graph as g
    results = _make_agent_results(["src/Login.tsx", "src/Login.test.tsx"])
    assert g._detect_test_runner(results) == "vitest"


def test_detect_test_runner_no_tests():
    import graph as g
    results = _make_agent_results(["src/api.py", "src/models.py"])
    assert g._detect_test_runner(results) is None


def test_detect_test_runner_empty():
    import graph as g
    assert g._detect_test_runner([]) is None


# ---------------------------------------------------------------------------
# _route_after_tests
# ---------------------------------------------------------------------------

def test_route_after_tests_passed():
    import graph as g
    state = make_state(test_results={"passed": True, "runner": "pytest"}, test_retry_count=0)
    assert g._route_after_tests(state) == "generate_docs"


def test_route_after_tests_failed_first_retry():
    import graph as g
    state = make_state(test_results={"passed": False, "runner": "pytest"}, test_retry_count=0)
    assert g._route_after_tests(state) == "test_retry"


def test_route_after_tests_failed_second_retry():
    import graph as g
    state = make_state(test_results={"passed": False, "runner": "pytest"}, test_retry_count=1)
    assert g._route_after_tests(state) == "test_retry"


def test_route_after_tests_max_retries_reached():
    """Con test_retry_count >= 2, siempre va a generate_docs (no bloquea)."""
    import graph as g
    state = make_state(test_results={"passed": False, "runner": "pytest"}, test_retry_count=2)
    assert g._route_after_tests(state) == "generate_docs"


def test_route_after_tests_no_results_defaults_to_generate_docs():
    """Sin test_results, passed=True por defecto (no bloquea)."""
    import graph as g
    state = make_state(test_results={}, test_retry_count=0)
    assert g._route_after_tests(state) == "generate_docs"


# ---------------------------------------------------------------------------
# run_tests — no-op sin archivos de test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_tests_noop_without_test_files():
    import graph as g
    state = make_state(
        agent_results=[{"agent": "backend", "output": "```python:src/api.py\n# code\n```"}],
        directory="",
        test_retry_count=0,
    )
    result = await g.run_tests(state)
    assert result["test_results"]["passed"] is True
    assert result["test_results"]["runner"] == "none"
    assert result["status"] == "tests_skipped"


@pytest.mark.asyncio
async def test_run_tests_timeout_returns_failed():
    """Si el proceso de tests excede el timeout, retorna passed=False con mensaje de timeout."""
    import asyncio, tempfile, os
    import graph as g

    # S32-A: necesita test files en el directorio para que pytest se ejecute
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test_sample.py")
        with open(test_file, "w") as f:
            f.write("def test_ok(): pass\n")

        state = make_state(
            agent_results=_make_agent_results(["tests/test_api.py"]),
            directory=tmpdir,
            test_retry_count=0,
        )

        mock_proc = MagicMock()
        mock_proc.kill = MagicMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", None))

        # Simular timeout en wait_for: el primer call lanza TimeoutError, communicate() retorna normal
        async def fake_wait_for(coro, timeout):
            raise asyncio.TimeoutError()

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
            patch("asyncio.wait_for", side_effect=fake_wait_for),
        ):
            result = await g.run_tests(state)

    assert result["test_results"]["passed"] is False
    assert "timeout" in result["test_results"]["output"].lower()


@pytest.mark.asyncio
async def test_run_tests_runner_not_installed():
    """Si el runner no está instalado, retorna passed=True (no bloquear)."""
    import tempfile, os
    import graph as g

    # S32-A: necesita test files en el directorio para que llegue al subprocess
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test_sample.py")
        with open(test_file, "w") as f:
            f.write("def test_ok(): pass\n")

        state = make_state(
            agent_results=_make_agent_results(["tests/test_api.py"]),
            directory=tmpdir,
            test_retry_count=0,
        )

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError("pytest not found")):
            result = await g.run_tests(state)

    assert result["test_results"]["passed"] is True
    assert "no está instalado" in result["test_results"]["output"]
