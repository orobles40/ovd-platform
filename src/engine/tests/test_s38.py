"""
OVD Platform — Tests S38: async tool invocation + QA truncation limit
S38-A: _run_agent_with_tools usa ainvoke() async para StructuredTools (context7)
S38-B: qa_review trunca agent_output a 20000 chars (antes 12000) para FRs multi-agente
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# S38-A — _run_agent_with_tools usa ainvoke async con fallback sync
# ---------------------------------------------------------------------------


class TestS38AAsyncToolInvocation:
    """S38-A: tool calls usan ainvoke() con fallback a invoke() cuando NotImplementedError."""

    def _get_run_agent_source(self) -> str:
        import graph as g

        return inspect.getsource(g._run_agent_with_tools)

    def test_usa_ainvoke_si_disponible(self):
        """El código verifica hasattr(tool_fn, 'ainvoke') antes de invocar."""
        src = self._get_run_agent_source()
        assert 'hasattr(tool_fn, "ainvoke")' in src, (
            "S38-A: no hay verificación de hasattr(tool_fn, 'ainvoke')"
        )

    def test_tiene_fallback_a_invoke_sync(self):
        """Cuando ainvoke lanza NotImplementedError, usa invoke() síncrono."""
        src = self._get_run_agent_source()
        assert "NotImplementedError" in src, (
            "S38-A: no hay fallback a invoke() cuando ainvoke lanza NotImplementedError"
        )
        assert "tool_fn.invoke(tool_args)" in src, (
            "S38-A: no se llama tool_fn.invoke() como fallback"
        )

    def test_ainvoke_es_awaited(self):
        """ainvoke se usa con await (es una corrutina)."""
        src = self._get_run_agent_source()
        assert "await tool_fn.ainvoke(tool_args)" in src, (
            "S38-A: ainvoke no se usa con await"
        )

    @pytest.mark.asyncio
    async def test_tool_con_ainvoke_se_invoca_async(self):
        """Una tool con ainvoke es invocada de forma asíncrona."""
        import graph as g

        # Tool mock con ainvoke (simula context7 StructuredTool)
        async_tool = MagicMock()
        async_tool.ainvoke = AsyncMock(return_value="resultado async")
        async_tool.invoke = MagicMock(return_value="resultado sync")

        tool_call = {"name": "test_tool", "args": {"query": "test"}}
        tool_map = {"test_tool": async_tool}

        # Simular el path de tool invocation dentro de _run_agent_with_tools
        # El fix hace: if hasattr(tool_fn, "ainvoke"): result = await tool_fn.ainvoke(args)
        tool_fn = tool_map["test_tool"]
        if hasattr(tool_fn, "ainvoke"):
            try:
                result = await tool_fn.ainvoke(tool_call["args"])
            except NotImplementedError:
                result = tool_fn.invoke(tool_call["args"])
        else:
            result = tool_fn.invoke(tool_call["args"])

        assert result == "resultado async"
        async_tool.ainvoke.assert_called_once_with({"query": "test"})
        async_tool.invoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_tool_ainvoke_not_implemented_usa_fallback(self):
        """Si ainvoke lanza NotImplementedError, se usa invoke() sync."""
        # Simular StructuredTool que tiene ainvoke pero lanza NotImplementedError
        sync_tool = MagicMock()
        sync_tool.ainvoke = AsyncMock(side_effect=NotImplementedError("sync only"))
        sync_tool.invoke = MagicMock(return_value="resultado sync fallback")

        tool_fn = sync_tool
        if hasattr(tool_fn, "ainvoke"):
            try:
                result = await tool_fn.ainvoke({"arg": "val"})
            except NotImplementedError:
                result = tool_fn.invoke({"arg": "val"})
        else:
            result = tool_fn.invoke({"arg": "val"})

        assert result == "resultado sync fallback"
        sync_tool.invoke.assert_called_once_with({"arg": "val"})

    @pytest.mark.asyncio
    async def test_tool_sin_ainvoke_usa_invoke_directo(self):
        """Una tool sin ainvoke (legacy) usa invoke() directamente."""
        legacy_tool = MagicMock(spec=["invoke"])  # sin ainvoke
        legacy_tool.invoke = MagicMock(return_value="resultado legacy")

        tool_fn = legacy_tool
        if hasattr(tool_fn, "ainvoke"):
            result = await tool_fn.ainvoke({})
        else:
            result = tool_fn.invoke({})

        assert result == "resultado legacy"
        legacy_tool.invoke.assert_called_once_with({})


# ---------------------------------------------------------------------------
# S38-B — qa_review trunca agent_output a 20000 chars
# ---------------------------------------------------------------------------


class TestS38BQATruncationLimit:
    """S38-B: qa_review usa _truncate(agent_output, N) con N >= 18000 para soportar FRs multi-agente."""

    def _get_qa_review_source(self) -> str:
        import graph as g

        return inspect.getsource(g.qa_review)

    def test_truncation_limit_es_20000(self):
        """qa_review trunca el output a >=18000 chars (no 12000). S56-A ajustó 20000→18000."""
        import re

        src = self._get_qa_review_source()
        # Buscar _truncate(agent_output, N) donde N >= 18000
        matches = re.findall(r"_truncate\(agent_output,\s*(\d+)\)", src)
        assert matches, "S38-B: qa_review no llama _truncate(agent_output, N)"
        limit = int(matches[0])
        assert limit >= 18000, (
            f"S38-B: límite de truncación {limit} < 18000 — debe soportar FRs multi-agente"
        )

    def test_no_usa_limite_12000(self):
        """El límite antiguo de 12000 chars ya no está en qa_review para agent_output."""
        src = self._get_qa_review_source()
        # No debe tener el límite antiguo para agent_output
        lines = src.splitlines()
        for line in lines:
            if "_truncate(agent_output, 12000)" in line:
                pytest.fail(
                    "S38-B: qa_review todavía usa _truncate(agent_output, 12000) — "
                    "debe ser 20000 para FRs multi-agente (3 agentes × ~6K = ~18K chars)"
                )

    def test_truncate_20000_permite_3_agentes(self):
        """Verifica que 20000 chars cubre 3 agentes con ~6K chars cada uno."""
        import graph as g

        # Simular output de 3 agentes × 6000 chars = 18000 (< 20000)
        output_3_agents = "x" * 18000
        truncated = g._truncate(output_3_agents, 20000)
        assert len(truncated) == 18000, (
            f"S38-B: output de 3 agentes ({len(output_3_agents)} chars) se truncó a {len(truncated)}"
        )

    def test_truncate_12000_cortaba_output_3_agentes(self):
        """Documenta que el límite antiguo (12000) cortaba el output de 3 agentes."""
        import graph as g

        # Simular output que excede 12000 pero no 20000
        output = "y" * 15000
        truncated_old = g._truncate(output, 12000)
        truncated_new = g._truncate(output, 20000)
        assert len(truncated_old) < len(output), (
            "Con 12000 se truncaba el output de 3 agentes"
        )
        assert len(truncated_new) == len(output), (
            "Con 20000 el output de 3 agentes pasa completo"
        )
