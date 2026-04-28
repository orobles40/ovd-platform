"""
OVD Platform — Tests S41.PRE: Timeouts diferenciados por nodo
S41P.A: constantes de timeout por tipo de nodo + aplicadas en analyze_fr, generate_sdd, web_research
S41P.B: OVD_HEARTBEAT_TIMEOUT_SECS configurable (ya en .env)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import asyncio
import inspect
import pathlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from factories import make_state

# ---------------------------------------------------------------------------
# S41P.A — Constantes de timeout definidas
# ---------------------------------------------------------------------------


class TestS41PATimeoutConstants:
    def test_analyze_timeout_definido(self):
        """S41P.A: _ANALYZE_TIMEOUT existe y es menor que _SDD_TIMEOUT."""
        from graph import _ANALYZE_TIMEOUT, _SDD_TIMEOUT

        assert _ANALYZE_TIMEOUT > 0
        assert _ANALYZE_TIMEOUT < _SDD_TIMEOUT

    def test_sdd_timeout_definido(self):
        """S41P.A: _SDD_TIMEOUT existe y tiene valor razonable (>= 60s)."""
        from graph import _SDD_TIMEOUT

        assert _SDD_TIMEOUT >= 60
        # SDD debe tener más margen que analyze (output más grande)
        from graph import _ANALYZE_TIMEOUT

        assert _SDD_TIMEOUT >= _ANALYZE_TIMEOUT

    def test_research_timeout_definido(self):
        """S41P.A: _RESEARCH_TIMEOUT existe y es el más corto de los LLM."""
        from graph import _ANALYZE_TIMEOUT, _RESEARCH_TIMEOUT

        assert _RESEARCH_TIMEOUT > 0
        assert _RESEARCH_TIMEOUT <= _ANALYZE_TIMEOUT

    def test_agents_timeout_definido(self):
        """S41P.A: _AGENTS_TIMEOUT existe."""
        from graph import _AGENTS_TIMEOUT

        assert _AGENTS_TIMEOUT > 0

    def test_security_timeout_mayor_que_qa(self):
        """S41P.A: security_audit tiene más margen que qa_review."""
        from graph import _QA_TIMEOUT, _SECURITY_TIMEOUT

        assert _SECURITY_TIMEOUT >= _QA_TIMEOUT

    def test_tests_timeout_es_io_puro(self):
        """S41P.A: run_tests es I/O puro — su timeout es menor que los LLM."""
        from graph import _QA_TIMEOUT, _TESTS_TIMEOUT

        assert _TESTS_TIMEOUT < _QA_TIMEOUT

    def test_todos_configurables_por_env(self):
        """S41P.A: todas las constantes de timeout respetan variable de entorno."""
        import importlib

        import graph as g

        # Verificar que los nombres de env var están en el source
        src = inspect.getsource(g)
        for env_var in [
            "OVD_ANALYZE_TIMEOUT_SECS",
            "OVD_SDD_TIMEOUT_SECS",
            "OVD_RESEARCH_TIMEOUT_SECS",
            "OVD_AGENTS_TIMEOUT_SECS",
            "OVD_SECURITY_TIMEOUT_SECS",
            "OVD_QA_TIMEOUT_SECS",
            "OVD_TESTS_TIMEOUT_SECS",
            "OVD_DOCS_TIMEOUT_SECS",
        ]:
            assert env_var in src, (
                f"{env_var} no encontrado como variable de entorno en graph.py"
            )


# ---------------------------------------------------------------------------
# S41P.A — analyze_fr usa asyncio.wait_for
# ---------------------------------------------------------------------------


class TestS41PAAnalyzeFr:
    def test_analyze_fr_tiene_wait_for(self):
        """S41P.A: analyze_fr usa asyncio.wait_for con _ANALYZE_TIMEOUT."""
        import inspect

        import graph as g

        src = inspect.getsource(g.analyze_fr)
        assert "asyncio.wait_for" in src
        assert "_ANALYZE_TIMEOUT" in src

    def test_analyze_fr_tiene_fallback_timeout(self):
        """S41P.A: analyze_fr captura TimeoutError y retorna resultado mínimo."""
        import inspect

        import graph as g

        src = inspect.getsource(g.analyze_fr)
        assert "TimeoutError" in src
        assert "Timeout" in src

    @pytest.mark.asyncio
    async def test_analyze_fr_timeout_retorna_resultado_minimo(self):
        """S41P.A: cuando el LLM excede el timeout, analyze_fr retorna sin romper el ciclo."""
        from graph import analyze_fr

        state = make_state(
            feature_request="Implementar módulo de pagos",
            project_context="Python / FastAPI",
        )

        async def _slow(*args, **kwargs):
            await asyncio.sleep(999)

        with (
            patch("graph.invoke_structured", side_effect=_slow),
            patch("graph._ANALYZE_TIMEOUT", 0.05),
            patch("graph.model_router") as mock_router,
            patch("graph.telemetry") as mock_tel,
        ):
            mock_router.get_llm_with_context = AsyncMock(return_value=MagicMock())
            mock_tel.node_span = MagicMock()
            mock_tel.node_span.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock()
            )
            mock_tel.node_span.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await analyze_fr(state)

        # El ciclo no rompe — retorna análisis mínimo con mensaje de timeout
        assert "fr_analysis" in result
        assert "Timeout" in result["fr_analysis"].get(
            "summary", ""
        ) or "Timeout" in result["fr_analysis"].get("raw", "")


# ---------------------------------------------------------------------------
# S41P.A — generate_sdd usa asyncio.wait_for
# ---------------------------------------------------------------------------


class TestS41PAGenerateSdd:
    def test_generate_sdd_tiene_wait_for(self):
        """S41P.A: generate_sdd usa asyncio.wait_for con _SDD_TIMEOUT."""
        import inspect

        import graph as g

        src = inspect.getsource(g.generate_sdd)
        assert "asyncio.wait_for" in src
        assert "_SDD_TIMEOUT" in src

    def test_generate_sdd_tiene_fallback_timeout(self):
        """S41P.A: generate_sdd captura TimeoutError y retorna SDD mínimo."""
        import inspect

        import graph as g

        src = inspect.getsource(g.generate_sdd)
        assert "TimeoutError" in src
        assert "Timeout" in src


# ---------------------------------------------------------------------------
# S41P.A — web_research_node usa asyncio.wait_for
# ---------------------------------------------------------------------------


class TestS41PAWebResearch:
    def test_web_research_tiene_wait_for(self):
        """S41P.A: web_research_node usa asyncio.wait_for con _RESEARCH_TIMEOUT."""
        import inspect

        import graph as g

        src = inspect.getsource(g.web_research_node)
        assert "asyncio.wait_for" in src
        assert "_RESEARCH_TIMEOUT" in src

    def test_web_research_tiene_fallback_timeout(self):
        """S41P.A: web_research_node captura TimeoutError y retorna no-op."""
        import inspect

        import graph as g

        src = inspect.getsource(g.web_research_node)
        assert "TimeoutError" in src


# ---------------------------------------------------------------------------
# S41P.B — OVD_HEARTBEAT_TIMEOUT_SECS en task_checkout.py
# ---------------------------------------------------------------------------


class TestS41PBHeartbeat:
    def test_heartbeat_timeout_configurable_por_env(self):
        """S41P.B: _STALE_THRESHOLD_MINUTES usa OVD_HEARTBEAT_TIMEOUT_SECS del entorno."""
        import inspect

        import task_checkout

        src = inspect.getsource(task_checkout)
        assert "OVD_HEARTBEAT_TIMEOUT_SECS" in src

    def test_heartbeat_timeout_en_env_file(self):
        """S41P.B: .env contiene OVD_HEARTBEAT_TIMEOUT_SECS."""
        env_path = pathlib.Path(__file__).parent.parent / ".env"
        if not env_path.exists():
            pytest.skip(".env no encontrado")
        content = env_path.read_text(encoding="utf-8")
        assert "OVD_HEARTBEAT_TIMEOUT_SECS" in content

    def test_env_tiene_timeouts_diferenciados(self):
        """S41P.A: .env contiene las variables de timeout diferenciadas."""
        env_path = pathlib.Path(__file__).parent.parent / ".env"
        if not env_path.exists():
            pytest.skip(".env no encontrado")
        content = env_path.read_text(encoding="utf-8")
        for var in [
            "OVD_AGENTS_TIMEOUT_SECS",
            "OVD_ANALYZE_TIMEOUT_SECS",
            "OVD_SDD_TIMEOUT_SECS",
            "OVD_TESTS_TIMEOUT_SECS",
        ]:
            assert var in content, f"{var} no encontrado en .env"
