"""
OVD Platform — Tests S48

S48-A: security_audit bypass completo cuando OVD_SECURITY_MIN_SCORE=0
S48-B: system_sdd.md contiene sección de contrato de interfaces
S48-C: _run_agent_with_tools loguea iteración 0 sin tool_calls
S48-D: _run_graph_background loguea nodo de fallo (S48-D)
"""

import os
import pathlib
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sdd_template() -> str:
    path = pathlib.Path(__file__).parent.parent / "templates" / "system_sdd.md"
    return path.read_text()


def _graph_py() -> str:
    path = pathlib.Path(__file__).parent.parent / "graph.py"
    return path.read_text()


def _api_py() -> str:
    path = pathlib.Path(__file__).parent.parent / "api.py"
    return path.read_text()


# ---------------------------------------------------------------------------
# S48-A — security_audit bypass
# ---------------------------------------------------------------------------


class TestS48ASecurityAuditBypass:
    def test_security_audit_has_bypass_check(self):
        """S48-A1: graph.py tiene bloque de bypass para OVD_SECURITY_MIN_SCORE=0."""
        content = _graph_py()
        assert "S48-A" in content, "Falta marca S48-A en graph.py"
        assert "OVD_SECURITY_MIN_SCORE" in content, (
            "Falta chequeo de OVD_SECURITY_MIN_SCORE en security_audit"
        )

    def test_security_audit_bypass_before_llm_call(self):
        """S48-A2: el bypass retorna antes de invocar el LLM."""
        content = _graph_py()
        # La línea de bypass debe aparecer ANTES de get_llm_with_context en security_audit
        bypass_pos = content.find("S48-A: OVD_SECURITY_MIN_SCORE=0")
        llm_call_pos = content.find('get_llm_with_context(\n        "security"')
        assert bypass_pos != -1, "No se encontró el bloque de bypass S48-A"
        assert llm_call_pos != -1, "No se encontró get_llm_with_context para security"
        assert bypass_pos < llm_call_pos, (
            "El bypass S48-A debe aparecer ANTES del llamado al LLM en security_audit"
        )

    @pytest.mark.asyncio
    async def test_security_audit_returns_bypass_when_score_zero(self):
        """S48-A3: security_audit retorna score=100/passed=True sin llamar al LLM con MIN_SCORE=0."""
        import graph as g

        fake_state = {
            "project_context": "ctx",
            "org_id": "ORG_TEST",
            "project_id": "PROJ_TEST",
            "jwt_token": "tok",
            "stack_routing": "auto",
            "agent_results": [],
            "directory": "",
            "messages": [],
        }

        with patch.dict(os.environ, {"OVD_SECURITY_MIN_SCORE": "0"}):
            with patch.object(
                g.model_router, "get_llm_with_context", new_callable=AsyncMock
            ) as mock_llm:
                result = await g.security_audit(fake_state)

        # El LLM NO debe haberse llamado
        mock_llm.assert_not_called()

        # El resultado debe tener score=100 y passed=True
        sec = result.get("security_result", {})
        assert sec.get("passed") is True, "El bypass debe retornar passed=True"
        assert sec.get("score") == 100, "El bypass debe retornar score=100"
        assert result.get("status") == "security_reviewed"

    @pytest.mark.asyncio
    async def test_security_audit_runs_llm_when_score_nonzero(self):
        """S48-A4: security_audit SÍ llama al LLM cuando MIN_SCORE > 0 (no bypass)."""
        import graph as g

        fake_state = {
            "project_context": "ctx",
            "org_id": "ORG_TEST",
            "project_id": "PROJ_TEST",
            "jwt_token": "tok",
            "stack_routing": "auto",
            "agent_results": [],
            "directory": "",
            "messages": [],
            "session_id": "sess-001",
        }

        mock_llm_instance = MagicMock()
        mock_llm_instance.with_structured_output = MagicMock(
            return_value=mock_llm_instance
        )
        mock_llm_instance.ainvoke = AsyncMock(side_effect=RuntimeError("test-stop"))

        with patch.dict(
            os.environ,
            {"OVD_SECURITY_MIN_SCORE": "70", "OVD_SECURITY_SCAN_ENABLED": "false"},
        ):
            with patch.object(
                g.model_router, "get_llm_with_context", new_callable=AsyncMock
            ) as mock_router:
                mock_router.return_value = mock_llm_instance
                # security_audit tiene BUG-04 fallback que atrapa el error → no relanza
                # Solo verificamos que get_llm_with_context fue llamado (eso confirma que no hubo bypass)
                await g.security_audit(fake_state)

        mock_router.assert_called_once()  # LLM sí fue solicitado (a diferencia de MIN_SCORE=0)


# ---------------------------------------------------------------------------
# S48-B — SDD interface contract
# ---------------------------------------------------------------------------


class TestS48BSddInterfaceContract:
    def test_sdd_has_interface_contract_section(self):
        """S48-B1: system_sdd.md contiene sección de contrato de interfaces."""
        content = _sdd_template()
        assert "S48-B" in content or "contrato de interfaces" in content.lower(), (
            "system_sdd.md debe tener sección de contrato de interfaces (S48-B)"
        )

    def test_sdd_interface_contract_mentions_import_paths(self):
        """S48-B2: la sección menciona rutas de importación exactas."""
        content = _sdd_template()
        assert "importa" in content.lower() or "import" in content.lower(), (
            "El contrato de interfaces debe mencionar importaciones"
        )

    def test_sdd_interface_contract_prevents_name_mismatch(self):
        """S48-B3: el template advierte sobre inconsistencia de nombres entre agentes."""
        content = _sdd_template()
        assert (
            "ImportError" in content
            or "mismo nombre" in content.lower()
            or "mismas clases" in content.lower()
        ), (
            "El template debe advertir sobre el riesgo de ImportError por nombres inconsistentes"
        )


# ---------------------------------------------------------------------------
# S48-C — Tool calling diagnosis logging
# ---------------------------------------------------------------------------


class TestS48CToolCallingDiagnosis:
    def test_graph_has_s48c_logging(self):
        """S48-C1: graph.py tiene logging de diagnóstico S48-C para tool_calls vacío."""
        content = _graph_py()
        assert "S48-C" in content, "Falta logging S48-C en _run_agent_with_tools"

    def test_graph_logs_iteration_zero_without_tools(self):
        """S48-C2: el log diferencia iter=0 (modelo nunca usó tools) de iter>0."""
        content = _graph_py()
        assert "iteración 0 sin tool_calls" in content or "_iter == 0" in content, (
            "El log debe detectar explícitamente cuándo el modelo no usó tools en la primera iteración"
        )


# ---------------------------------------------------------------------------
# S48-D — Failure node logging
# ---------------------------------------------------------------------------


class TestS48DFailureNodeLogging:
    def test_api_has_s48d_logging(self):
        """S48-D1: api.py tiene bloque S48-D para loguear estado del grafo al terminar."""
        content = _api_py()
        assert "S48-D" in content, "Falta bloque S48-D en api.py"

    def test_api_logs_next_nodes_on_exit(self):
        """S48-D2: el log incluye snap.next para saber qué nodo seguía."""
        content = _api_py()
        assert "snap.next" in content, "S48-D debe loguear snap.next del checkpoint"
