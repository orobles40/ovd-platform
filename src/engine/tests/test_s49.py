"""
OVD Platform — Tests S49

S49-A: _run_agent_with_tools switch inmediato a runner cuando iter 0 y sin tool_calls
S49-B: system_sdd.md tiene límite estricto de 5 tareas por agente
S49-C: _run_agent_with_tools detecta Ollama y salta bind_tools
S49-D: system_sdd.md refuerza límite con texto explícito
"""
import sys, os, pathlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from tests.factories import make_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sdd_template() -> str:
    path = pathlib.Path(__file__).parent.parent / "templates" / "system_sdd.md"
    return path.read_text()


def _graph_src() -> str:
    path = pathlib.Path(__file__).parent.parent / "graph.py"
    return path.read_text()


# ---------------------------------------------------------------------------
# S49-A: switch inmediato a runner cuando iter 0 y sin tool_calls
# ---------------------------------------------------------------------------

class TestS49ARunnerFallbackOnIter0:

    @pytest.mark.asyncio
    async def test_iter0_no_tools_calls_runner(self, tmp_path):
        """Cuando el modelo no produce tool_calls en iter 0, _run_agent_with_tools
        llama al runner tradicional en vez de continuar el loop."""
        import graph as g

        runner_called = []

        async def fake_runner(sdd, comment, llm, ctx, retry, lang, rag, *, stack_language=""):
            runner_called.append(True)
            return {
                "agent": "backend",
                "output": "codigo generado por runner",
                "artifacts": [],
                "uncertainties": [],
                "tokens": {"input": 10, "output": 20},
            }

        mock_llm = MagicMock()
        # bind_tools no lanza excepción — llm acepta tools pero el response no tiene tool_calls
        bound_llm = MagicMock()
        bound_llm.ainvoke = AsyncMock(return_value=MagicMock(
            tool_calls=[],
            content="```python\ndef hello(): pass\n```",
        ))
        mock_llm.bind_tools = MagicMock(return_value=bound_llm)

        with patch.dict(g._AGENT_RUNNERS, {"backend": fake_runner}):
            result = await g._run_agent_with_tools(
                "backend", "SDD content", "comentario",
                mock_llm, "ctx", "", "es",
                [MagicMock(name="write_file")],
                str(tmp_path),
                stack_routing="auto",  # no es ollama → pasa por bind_tools
            )

        assert runner_called, "El runner debe haber sido llamado"
        assert result["output"] == "codigo generado por runner"

    @pytest.mark.asyncio
    async def test_iter0_with_tool_calls_does_not_call_runner(self, tmp_path):
        """Cuando la primera iteración SÍ produce tool_calls, no se llama al runner."""
        import graph as g

        runner_called = []

        async def fake_runner(*args, **kwargs):
            runner_called.append(True)
            return {"agent": "backend", "output": "", "artifacts": [], "uncertainties": [], "tokens": {}}

        # Primera respuesta: tiene tool_calls → segunda respuesta: sin tool_calls (termina loop)
        write_tool = MagicMock()
        write_tool.name = "write_file"
        write_tool.ainvoke = AsyncMock(return_value=str(tmp_path / "src" / "main.py"))
        write_tool.invoke = MagicMock(return_value=str(tmp_path / "src" / "main.py"))
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("def hello(): pass")

        first_response = MagicMock()
        first_response.tool_calls = [{"name": "write_file", "args": {"path": "src/main.py", "content": "def hello(): pass"}, "id": "tc1"}]
        first_response.content = ""

        second_response = MagicMock()
        second_response.tool_calls = []
        second_response.content = "Implementación completada"

        bound_llm = MagicMock()
        bound_llm.ainvoke = AsyncMock(side_effect=[first_response, second_response])
        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=bound_llm)

        # _extract_usage debe retornar dict vacío
        with patch("graph._extract_usage", return_value={"input": 0, "output": 0}), \
             patch.dict(g._AGENT_RUNNERS, {"backend": fake_runner}):
            await g._run_agent_with_tools(
                "backend", "SDD content", "comentario",
                mock_llm, "ctx", "", "es",
                [write_tool],
                str(tmp_path),
                stack_routing="auto",
            )

        assert not runner_called, "El runner NO debe haber sido llamado cuando hay tool_calls en iter 0"


# ---------------------------------------------------------------------------
# S49-B: limit de tareas por agente — máximo 5
# ---------------------------------------------------------------------------

class TestS49BSddTaskLimit:

    def test_sdd_template_says_max_5_tasks(self):
        """system_sdd.md especifica un máximo de 5 tareas por agente."""
        content = _sdd_template()
        assert "5 tareas" in content or "MÁXIMO 5" in content or "máximo 5" in content.lower()

    def test_sdd_template_mentions_performance_reason(self):
        """El template explica la razón del límite (tiempo de ejecución)."""
        content = _sdd_template()
        # Debe mencionar minutos o tiempo o overhead
        assert "minutos" in content or "minuto" in content or "overhead" in content.lower()

    def test_sdd_template_second_limit_reference_updated(self):
        """La segunda referencia al límite también dice 5, no 6-7."""
        content = _sdd_template()
        # Buscar la línea resumen del final del template
        assert "6-7 tareas" not in content


# ---------------------------------------------------------------------------
# S49-C: detección Ollama y skip de bind_tools
# ---------------------------------------------------------------------------

class TestS49COllamaDetection:

    @pytest.mark.asyncio
    async def test_ollama_stack_routing_skips_bind_tools(self, tmp_path):
        """Con stack_routing='ollama', _run_agent_with_tools llama al runner
        sin intentar bind_tools."""
        import graph as g

        runner_called = []
        bind_tools_called = []

        async def fake_runner(sdd, comment, llm, ctx, retry, lang, rag, *, stack_language=""):
            runner_called.append(True)
            return {"agent": "backend", "output": "runner output", "artifacts": [], "uncertainties": [], "tokens": {}}

        mock_llm = MagicMock()

        def track_bind_tools(tools):
            bind_tools_called.append(True)
            return MagicMock()

        mock_llm.bind_tools = track_bind_tools

        with patch.dict(g._AGENT_RUNNERS, {"backend": fake_runner}):
            result = await g._run_agent_with_tools(
                "backend", "SDD", "comment",
                mock_llm, "ctx", "", "es",
                [MagicMock()],
                str(tmp_path),
                stack_routing="ollama",  # ← detectar Ollama
            )

        assert runner_called, "El runner debe haberse llamado"
        assert not bind_tools_called, "bind_tools NO debe llamarse para modelos Ollama"

    def test_looks_like_ollama_model_qwen(self):
        """_looks_like_ollama_model retorna True para qwen3-coder:30b."""
        import graph as g
        assert g._looks_like_ollama_model("qwen3-coder:30b") is True

    def test_looks_like_ollama_model_llama(self):
        """_looks_like_ollama_model retorna True para llama3.1:8b."""
        import graph as g
        assert g._looks_like_ollama_model("llama3.1:8b") is True

    def test_looks_like_ollama_model_claude(self):
        """_looks_like_ollama_model retorna False para claude-sonnet-4-6."""
        import graph as g
        assert g._looks_like_ollama_model("claude-sonnet-4-6") is False

    def test_looks_like_ollama_model_gpt(self):
        """_looks_like_ollama_model retorna False para gpt-4o."""
        import graph as g
        assert g._looks_like_ollama_model("gpt-4o") is False

    @pytest.mark.asyncio
    async def test_model_name_heuristic_skips_bind_tools(self, tmp_path):
        """Si el llm tiene model='qwen3-coder:30b', se detecta como Ollama."""
        import graph as g

        runner_called = []

        async def fake_runner(sdd, comment, llm, ctx, retry, lang, rag, *, stack_language=""):
            runner_called.append(True)
            return {"agent": "backend", "output": "ok", "artifacts": [], "uncertainties": [], "tokens": {}}

        mock_llm = MagicMock()
        mock_llm.model = "qwen3-coder:30b"
        mock_llm.bind_tools = MagicMock()  # no debe llamarse

        with patch.dict(g._AGENT_RUNNERS, {"backend": fake_runner}):
            await g._run_agent_with_tools(
                "backend", "SDD", "comment",
                mock_llm, "ctx", "", "es",
                [MagicMock()],
                str(tmp_path),
                stack_routing="auto",  # auto pero model name es qwen
            )

        assert runner_called
        mock_llm.bind_tools.assert_not_called()


# ---------------------------------------------------------------------------
# S49-D: graph.py contiene los helpers de detección Ollama
# ---------------------------------------------------------------------------

class TestS49DGraphHelpers:

    def test_graph_has_get_chat_ollama_class_helper(self):
        """graph.py define la función _get_chat_ollama_class."""
        src = _graph_src()
        assert "_get_chat_ollama_class" in src

    def test_graph_has_looks_like_ollama_model_helper(self):
        """graph.py define la función _looks_like_ollama_model."""
        src = _graph_src()
        assert "_looks_like_ollama_model" in src

    def test_graph_s49a_log_message_present(self):
        """graph.py contiene el mensaje de log S49-A para el switch a runner."""
        src = _graph_src()
        assert "S49-A" in src

    def test_graph_s49c_log_message_present(self):
        """graph.py contiene el mensaje de log S49-C para detección Ollama."""
        src = _graph_src()
        assert "S49-C" in src
