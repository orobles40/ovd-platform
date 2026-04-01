"""
OVD Platform — Tests para las funciones de routing puro del grafo
Sprint: S6+
Estas funciones son síncronas y no llaman LLM, por lo que no requieren mocks de LLM.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))  # para factories

import pytest
from langgraph.graph import END
from langgraph.types import Send

from factories import make_state
from graph import (
    route_after_approval,
    route_after_security,
    route_after_qa,
    _dispatch_agents,
    update_security_retry,
    update_qa_retry,
    _build_security_feedback,
    _build_qa_feedback,
)


# ---------------------------------------------------------------------------
# TestRouteAfterApproval
# ---------------------------------------------------------------------------

class TestRouteAfterApproval:

    def test_approved_va_a_route_agents(self):
        state = make_state(approval_decision="approved")
        assert route_after_approval(state) == "route_agents"

    def test_rejected_va_a_end(self):
        state = make_state(approval_decision="rejected")
        assert route_after_approval(state) == END

    def test_vacio_va_a_end(self):
        state = make_state(approval_decision="")
        assert route_after_approval(state) == END


# ---------------------------------------------------------------------------
# TestRouteAfterSecurity
# ---------------------------------------------------------------------------

class TestRouteAfterSecurity:

    def test_passed_true_va_a_qa(self):
        state = make_state(
            security_result={"passed": True, "score": 90},
            security_retry_count=0,
        )
        assert route_after_security(state) == "qa_review"

    def test_failed_primer_reintento_va_a_route_agents(self):
        state = make_state(
            security_result={"passed": False, "score": 30, "severity": "high"},
            security_retry_count=0,
        )
        assert route_after_security(state) == "route_agents"

    def test_failed_agota_reintentos_escala(self):
        state = make_state(
            security_result={"passed": False, "score": 20, "severity": "critical"},
            security_retry_count=3,
        )
        assert route_after_security(state) == "handle_escalation"

    def test_score_supera_umbral_pasa(self, monkeypatch):
        """Si passed=False pero score >= _SECURITY_MIN_SCORE, debe pasar a qa_review."""
        import graph
        monkeypatch.setattr(graph, "_SECURITY_MIN_SCORE", 80)
        state = make_state(
            security_result={"passed": False, "score": 85},
            security_retry_count=0,
        )
        assert route_after_security(state) == "qa_review"


# ---------------------------------------------------------------------------
# TestRouteAfterQA
# ---------------------------------------------------------------------------

class TestRouteAfterQA:

    def test_qa_passed_va_a_deliver(self):
        state = make_state(
            qa_result={"passed": True, "score": 85},
            qa_retry_count=0,
        )
        assert route_after_qa(state) == "deliver"

    def test_qa_failed_primer_reintento(self):
        state = make_state(
            qa_result={"passed": False, "score": 50},
            qa_retry_count=0,
        )
        assert route_after_qa(state) == "route_agents"

    def test_qa_failed_agota_reintentos(self):
        state = make_state(
            qa_result={"passed": False, "score": 40},
            qa_retry_count=3,
        )
        assert route_after_qa(state) == "handle_escalation"


# ---------------------------------------------------------------------------
# TestDispatchAgents
# ---------------------------------------------------------------------------

class TestDispatchAgents:

    def test_genera_send_por_agente(self):
        state = make_state(selected_agents=["backend", "frontend"])
        sends = _dispatch_agents(state)
        assert len(sends) == 2

    def test_cada_send_tiene_current_agent(self):
        state = make_state(selected_agents=["backend", "frontend"])
        sends = _dispatch_agents(state)
        agents_in_sends = {s.arg["current_agent"] for s in sends}
        assert "backend" in agents_in_sends
        assert "frontend" in agents_in_sends

    def test_todos_son_instancias_de_send(self):
        state = make_state(selected_agents=["backend", "database"])
        sends = _dispatch_agents(state)
        for s in sends:
            assert isinstance(s, Send)

    def test_lista_vacia_genera_cero_sends(self):
        """selected_agents=[] → lista vacía de Send (no hay fallback implícito en _dispatch_agents)."""
        state = make_state(selected_agents=[])
        sends = _dispatch_agents(state)
        assert len(sends) == 0


# ---------------------------------------------------------------------------
# TestUpdateRetry
# ---------------------------------------------------------------------------

class TestUpdateRetry:

    def test_security_retry_incrementa_contador(self):
        state = make_state(
            security_retry_count=0,
            security_result={
                "passed": False,
                "score": 30,
                "severity": "high",
                "vulnerabilities": [],
                "secrets_found": [],
                "insecure_patterns": [],
                "rls_compliant": True,
                "remediation": [],
                "summary": "Falló",
            },
            retry_feedback="",
        )
        result = update_security_retry(state)
        assert result["security_retry_count"] == 1

    def test_qa_retry_incrementa_contador(self):
        state = make_state(
            qa_retry_count=1,
            qa_result={
                "passed": False,
                "score": 55,
                "issues": ["Falta validación"],
                "sdd_compliance": False,
                "missing_requirements": [],
                "code_quality_issues": [],
                "summary": "Calidad insuficiente",
            },
            retry_feedback="",
        )
        result = update_qa_retry(state)
        assert result["qa_retry_count"] == 2

    def test_security_retry_acumula_feedback(self):
        """El feedback existente y el nuevo se concatenan con newline."""
        state = make_state(
            security_retry_count=0,
            security_result={
                "passed": False,
                "score": 25,
                "severity": "high",
                "vulnerabilities": ["A01-Broken Access Control"],
                "secrets_found": [],
                "insecure_patterns": [],
                "rls_compliant": True,
                "remediation": ["Implementar validación de permisos"],
                "summary": "Falló seguridad",
            },
            retry_feedback="feedback previo del ciclo anterior",
        )
        result = update_security_retry(state)
        feedback = result["retry_feedback"]
        assert "feedback previo" in feedback
        assert "SECURITY AUDIT FAILED" in feedback
        # Deben estar concatenados (newline entre ellos)
        assert "\n" in feedback

    def test_qa_retry_acumula_feedback_cuando_vacio(self):
        """Cuando no hay feedback previo, solo se usa el nuevo."""
        state = make_state(
            qa_retry_count=0,
            qa_result={
                "passed": False,
                "score": 40,
                "issues": ["Falta manejo de errores"],
                "sdd_compliance": False,
                "missing_requirements": ["REQ-002"],
                "code_quality_issues": [],
                "summary": "QA insuficiente",
            },
            retry_feedback="",
        )
        result = update_qa_retry(state)
        feedback = result["retry_feedback"]
        assert "QA REVIEW FAILED" in feedback
