"""
S20 — GAP-R1: Tests de timeout por nodo (agent_executor) y timeout global SSE.
"""
from __future__ import annotations
import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Tests de _NODE_TIMEOUT en agent_executor
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_node_timeout_reads_from_env():
    """_NODE_TIMEOUT se lee de OVD_NODE_TIMEOUT_SECS."""
    import importlib
    with patch.dict(os.environ, {"OVD_NODE_TIMEOUT_SECS": "42"}):
        import graph as g
        importlib.reload(g)
        assert g._NODE_TIMEOUT == 42.0
    importlib.reload(g)


@pytest.mark.asyncio
async def test_agent_executor_returns_error_result_on_timeout():
    """agent_executor captura TimeoutError y retorna resultado de error parcial (no lanza)."""
    import graph as g

    # Estado mínimo para pasar las guards de presupuesto y llegar a la invocación
    state = {
        "current_agent": "backend",
        "sdd": {"backend": {"tasks": []}},
        "org_id": "test-org",
        "project_id": "test-proj",
        "jwt_token": "",
        "project_context": "",
        "retry_feedback": "",
        "approval_comment": "",
        "language": "es",
        "directory": "",
        "github_repo": "",
        "session_id": "s1",
        "stack_routing": "auto",
        "rag_context": "",
        "token_usage": {},
    }

    # Mock del LLM que tarda más que el timeout
    async def _slow_llm(*args, **kwargs):
        await asyncio.sleep(999)

    mock_llm = MagicMock()
    mock_runner = AsyncMock(side_effect=_slow_llm)

    with (
        patch.object(g, "_NODE_TIMEOUT", 0.05),  # 50ms de timeout en test
        patch("model_router.get_llm_with_context", AsyncMock(return_value=mock_llm)),
        patch.object(g, "_AGENT_RUNNERS", {"backend": mock_runner}),
        patch("tools.make_file_tools", return_value=[]),
        patch("mcp_client.pool.get_langchain_tools", return_value=[]),
        patch.object(g, "_build_agent_sdd_content", return_value="sdd content"),
    ):
        result = await g.agent_executor(state)

    # Debe retornar sin lanzar — con resultado de error en agent_results
    assert "agent_results" in result
    agent_result = result["agent_results"][0]
    assert agent_result.get("error") == "timeout"
    assert "backend" in agent_result.get("output", "")


@pytest.mark.asyncio
async def test_agent_executor_succeeds_within_timeout():
    """agent_executor completa normalmente cuando el LLM responde rápido."""
    import graph as g

    state = {
        "current_agent": "backend",
        "sdd": {"backend": {"tasks": []}},
        "org_id": "test-org",
        "project_id": "test-proj",
        "jwt_token": "",
        "project_context": "",
        "retry_feedback": "",
        "approval_comment": "",
        "language": "es",
        "directory": "",
        "github_repo": "",
        "session_id": "s1",
        "stack_routing": "auto",
        "rag_context": "",
        "token_usage": {},
    }

    mock_llm = MagicMock()
    expected = {
        "agent": "backend",
        "output": "código generado",
        "artifacts": [],
        "uncertainties": [],
        "tokens": {"input": 10, "output": 20},
    }
    mock_runner = AsyncMock(return_value=expected)

    with (
        patch.object(g, "_NODE_TIMEOUT", 5.0),
        patch("model_router.get_llm_with_context", AsyncMock(return_value=mock_llm)),
        patch.object(g, "_AGENT_RUNNERS", {"backend": mock_runner}),
        patch("tools.make_file_tools", return_value=[]),
        patch("mcp_client.pool.get_langchain_tools", return_value=[]),
        patch.object(g, "_build_agent_sdd_content", return_value="sdd content"),
    ):
        result = await g.agent_executor(state)

    assert result["agent_results"][0]["output"] == "código generado"
    assert result["agent_results"][0].get("error") is None
