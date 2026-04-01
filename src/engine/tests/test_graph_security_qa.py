"""
OVD Platform — Tests para los nodos security_audit y qa_review
Sprint: S6+
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))  # para factories

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from factories import make_state, make_agent_result
from graph import security_audit, qa_review, SecurityAuditOutput, QAReviewOutput


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def make_llm_mock(return_value):
    structured = MagicMock()
    structured.ainvoke = AsyncMock(return_value=return_value)
    llm = MagicMock()
    llm.with_structured_output = MagicMock(return_value=structured)
    return llm


def _make_security_output(passed=True, score=92, severity="none", vulnerabilities=None):
    return SecurityAuditOutput(
        passed=passed,
        score=score,
        severity=severity,
        vulnerabilities=vulnerabilities or [],
        secrets_found=[],
        insecure_patterns=[],
        rls_compliant=True,
        remediation=[],
        summary="Auditoria de seguridad completada",
    )


def _make_qa_output(passed=True, score=88, sdd_compliance=True, issues=None):
    return QAReviewOutput(
        passed=passed,
        score=score,
        issues=issues or [],
        sdd_compliance=sdd_compliance,
        missing_requirements=[],
        code_quality_issues=[],
        summary="Revision QA completada",
    )


# ---------------------------------------------------------------------------
# TestSecurityAudit
# ---------------------------------------------------------------------------

class TestSecurityAudit:

    @pytest.mark.asyncio
    async def test_audit_passed_retorna_resultado_correcto(self):
        """LLM retorna passed=True, score=92 → security_result y status correctos."""
        llm = make_llm_mock(_make_security_output(passed=True, score=92, severity="none"))

        with patch("model_router.get_llm_with_context", new=AsyncMock(return_value=llm)):
            state = make_state(
                agent_results=[make_agent_result("backend")],
                sdd={},
            )
            result = await security_audit(state)

        assert result["security_result"]["passed"] is True
        assert result["security_result"]["score"] == 92
        assert result["status"] == "security_reviewed"

    @pytest.mark.asyncio
    async def test_audit_failed_registra_vulnerabilidades(self):
        """LLM retorna vulnerabilidades → se incluyen en security_result."""
        vulns = ["A01-Broken Access Control"]
        llm = make_llm_mock(
            _make_security_output(passed=False, score=40, severity="high", vulnerabilities=vulns)
        )

        with patch("model_router.get_llm_with_context", new=AsyncMock(return_value=llm)):
            state = make_state(
                agent_results=[make_agent_result("backend", passed=False)],
            )
            result = await security_audit(state)

        assert result["security_result"]["passed"] is False
        assert "A01-Broken Access Control" in result["security_result"]["vulnerabilities"]
        assert result["security_result"]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_audit_agrega_mensaje_con_score(self):
        """El nodo agrega un mensaje en messages que contiene 'Score:'."""
        llm = make_llm_mock(_make_security_output(passed=True, score=85))

        with patch("model_router.get_llm_with_context", new=AsyncMock(return_value=llm)):
            state = make_state(
                agent_results=[make_agent_result("backend")],
                messages=[],
            )
            result = await security_audit(state)

        msgs = result["messages"]
        assert len(msgs) >= 1
        combined = " ".join(m.get("content", "") for m in msgs)
        assert "Score:" in combined, f"Mensaje debería contener 'Score:'. Mensajes: {msgs}"


# ---------------------------------------------------------------------------
# TestQAReview
# ---------------------------------------------------------------------------

class TestQAReview:

    @pytest.mark.asyncio
    async def test_qa_passed_retorna_resultado(self):
        """LLM retorna passed=True, score=88 → qa_result correcto."""
        llm = make_llm_mock(_make_qa_output(passed=True, score=88, sdd_compliance=True))

        with patch("model_router.get_llm_with_context", new=AsyncMock(return_value=llm)):
            state = make_state(
                agent_results=[make_agent_result("backend")],
                sdd={"summary": "SDD de prueba", "requirements": [], "tasks": []},
            )
            result = await qa_review(state)

        assert result["qa_result"]["passed"] is True
        assert result["qa_result"]["score"] == 88

    @pytest.mark.asyncio
    async def test_qa_failed_registra_issues(self):
        """LLM retorna issues → se incluyen en qa_result."""
        issues = ["Falta validación de input"]
        llm = make_llm_mock(
            _make_qa_output(passed=False, score=55, sdd_compliance=False, issues=issues)
        )

        with patch("model_router.get_llm_with_context", new=AsyncMock(return_value=llm)):
            state = make_state(
                agent_results=[make_agent_result("backend", passed=False)],
                sdd={"summary": "SDD de prueba", "requirements": [], "tasks": []},
            )
            result = await qa_review(state)

        assert result["qa_result"]["passed"] is False
        assert "Falta validación de input" in result["qa_result"]["issues"]

    @pytest.mark.asyncio
    async def test_qa_agrega_mensaje(self):
        """El nodo agrega al menos un mensaje que menciona 'QA'."""
        llm = make_llm_mock(_make_qa_output(passed=True, score=90))

        with patch("model_router.get_llm_with_context", new=AsyncMock(return_value=llm)):
            state = make_state(
                agent_results=[make_agent_result("backend")],
                sdd={"summary": "SDD de prueba", "requirements": [], "tasks": []},
                messages=[],
            )
            result = await qa_review(state)

        msgs = result["messages"]
        assert len(msgs) >= 1
        combined = " ".join(m.get("content", "") for m in msgs)
        assert "QA" in combined, f"Mensaje debería mencionar 'QA'. Mensajes: {msgs}"
