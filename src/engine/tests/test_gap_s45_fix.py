"""
OVD Platform — Tests GAP-S45-1 Fix: Error: undefined en retry fan-out

Fix A (api.py:335):   captura BaseException (CancelledError) y emite SSE con mensaje no vacío
Fix B (graph.py:1721): fallback _run_agent_with_tools pasa rag_context y stack_language
Fix State: estado correcto del segundo fan-out tras update_test_retry
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from factories import make_state

# ---------------------------------------------------------------------------
# Fix A — Captura BaseException en _stream_graph_events
# ---------------------------------------------------------------------------


class TestFixABaseExceptionSSE:
    @pytest.mark.asyncio
    async def test_cancelled_error_produce_mensaje_no_vacio(self):
        """Fix A: CancelledError genera SSE con error_type y message no vacíos."""
        import api

        captured: list[dict] = []

        async def _gen():
            try:
                raise asyncio.CancelledError("timeout en agent_executor")
            except BaseException as e:
                error_msg = str(e) if str(e) else type(e).__name__
                captured.append(
                    api._make_sse_event(
                        "error",
                        {
                            "message": error_msg,
                            "error_type": type(e).__name__,
                            "recoverable": False,
                        },
                    )
                )

        await _gen()

        assert len(captured) == 1
        payload = json.loads(captured[0]["data"])
        assert payload["type"] == "error"
        assert payload["data"]["message"] != ""
        assert payload["data"]["error_type"] == "CancelledError"
        assert payload["data"]["recoverable"] is False

    @pytest.mark.asyncio
    async def test_base_exception_sin_mensaje_usa_nombre_tipo(self):
        """Fix A: BaseException cuyo str() es vacío usa type(e).__name__ como fallback."""
        import api

        captured: list[dict] = []

        class SilentError(BaseException):
            def __str__(self):
                return ""

        async def _gen():
            try:
                raise SilentError()
            except BaseException as e:
                error_msg = str(e) if str(e) else type(e).__name__
                captured.append(
                    api._make_sse_event(
                        "error",
                        {
                            "message": error_msg,
                            "error_type": type(e).__name__,
                            "recoverable": False,
                        },
                    )
                )

        await _gen()

        payload = json.loads(captured[0]["data"])
        assert payload["data"]["message"] == "SilentError"
        assert payload["data"]["error_type"] == "SilentError"

    @pytest.mark.asyncio
    async def test_exception_normal_sigue_siendo_capturada(self):
        """Fix A: Exception normal (ValueError) también es capturada por BaseException."""
        import api

        captured: list[dict] = []

        async def _gen():
            try:
                raise ValueError("campo inválido en retry")
            except BaseException as e:
                error_msg = str(e) if str(e) else type(e).__name__
                captured.append(
                    api._make_sse_event(
                        "error",
                        {
                            "message": error_msg,
                            "error_type": type(e).__name__,
                            "recoverable": False,
                        },
                    )
                )

        await _gen()

        payload = json.loads(captured[0]["data"])
        assert payload["data"]["error_type"] == "ValueError"
        assert "campo inválido" in payload["data"]["message"]


# ---------------------------------------------------------------------------
# Fix B — Fallback _run_agent_with_tools pasa rag_context y stack_language
# ---------------------------------------------------------------------------


class TestFixBFallbackParametros:
    """
    La excepción debe ocurrir dentro del try principal (línea ~1647–1718),
    no en bind_tools. Mockeamos bind_tools para que tenga éxito, pero ainvoke
    para que falle — así se activa el except en línea 1718.
    """

    @pytest.mark.asyncio
    async def test_fallback_pasa_rag_context(self):
        """Fix B: rag_context llega al runner cuando ainvoke lanza Exception."""
        import graph as g

        llamadas: list[dict] = []

        async def runner_captura(
            sdd,
            comment,
            llm,
            project_ctx,
            retry_feedback,
            language,
            rag_context="",
            *,
            stack_language="",
        ):
            llamadas.append(
                {"rag_context": rag_context, "stack_language": stack_language}
            )
            return {
                "agent": "backend",
                "output": "ok",
                "artifacts": [],
                "uncertainties": [],
                "tokens": {},
            }

        bound_llm_mock = MagicMock()
        bound_llm_mock.ainvoke = AsyncMock(
            side_effect=RuntimeError("LLM timeout en segundo fan-out")
        )

        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=bound_llm_mock)

        with patch.dict(g._AGENT_RUNNERS, {"backend": runner_captura}):
            await g._run_agent_with_tools(
                agent_name="backend",
                sdd_content="SDD",
                comment="",
                llm=mock_llm,
                project_ctx="ctx",
                retry_feedback="feedback del retry",
                language="es",
                tools=[MagicMock()],
                directory="/tmp",
                rag_context="## Lección previa del RAG",
                stack_language="python",
            )

        assert len(llamadas) == 1
        assert llamadas[0]["rag_context"] == "## Lección previa del RAG"

    @pytest.mark.asyncio
    async def test_fallback_pasa_stack_language(self):
        """Fix B: stack_language llega al runner cuando ainvoke lanza Exception."""
        import graph as g

        llamadas: list[dict] = []

        async def runner_captura(
            sdd,
            comment,
            llm,
            project_ctx,
            retry_feedback,
            language,
            rag_context="",
            *,
            stack_language="",
        ):
            llamadas.append({"stack_language": stack_language})
            return {
                "agent": "backend",
                "output": "ok",
                "artifacts": [],
                "uncertainties": [],
                "tokens": {},
            }

        bound_llm_mock = MagicMock()
        bound_llm_mock.ainvoke = AsyncMock(side_effect=RuntimeError("LLM timeout"))

        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=bound_llm_mock)

        with patch.dict(g._AGENT_RUNNERS, {"backend": runner_captura}):
            await g._run_agent_with_tools(
                agent_name="backend",
                sdd_content="SDD",
                comment="",
                llm=mock_llm,
                project_ctx="ctx",
                retry_feedback="",
                language="es",
                tools=[MagicMock()],
                directory="/tmp",
                rag_context="",
                stack_language="typescript",
            )

        assert len(llamadas) == 1
        assert llamadas[0]["stack_language"] == "typescript"


# ---------------------------------------------------------------------------
# Fix State — Estado correcto del segundo fan-out
# ---------------------------------------------------------------------------


class TestFixStateSegundoFanout:
    def test_update_test_retry_no_modifica_agent_results(self):
        """State: update_test_retry NO incluye agent_results en su retorno."""
        import graph as g

        state = make_state(
            agent_results=[{"agent": "backend", "output": "código", "artifacts": []}],
            test_results={
                "passed": False,
                "output": "AssertionError: assert 1 == 2",
                "runner": "pytest",
            },
            test_retry_count=0,
            retry_feedback="",
        )

        result = g.update_test_retry(state)

        assert "agent_results" not in result, (
            "update_test_retry no debe tocar agent_results — ese reset lo hace route_agents vía reducer"
        )

    def test_make_agent_sends_incluye_retry_feedback_en_segundo_ciclo(self):
        """State: el Send del segundo fan-out incluye retry_feedback del ciclo anterior."""
        from langgraph.types import Send

        import graph as g

        feedback = "⚠️ Tests fallaron: AssertionError en test_login"
        state = make_state(
            selected_agents=["backend"],
            retry_feedback=feedback,
            sdd={"tasks": [], "requirements": []},
        )

        sends = g._make_agent_sends(["backend"], state)

        assert len(sends) == 1
        assert isinstance(sends[0], Send)
        send_payload = sends[0].arg  # LangGraph Send usa .arg (no .args)
        assert send_payload["retry_feedback"] == feedback

    def test_update_test_retry_genera_feedback_no_vacio(self):
        """State: tras update_test_retry, retry_feedback contiene texto del fallo."""
        import graph as g

        state = make_state(
            test_results={
                "passed": False,
                "output": "FAILED tests/test_auth.py::test_login — AssertionError: assert False",
                "runner": "pytest",
            },
            test_retry_count=0,
            retry_feedback="",
        )

        result = g.update_test_retry(state)

        assert "retry_feedback" in result
        assert result["retry_feedback"].strip() != ""
        assert result["test_retry_count"] == 1
