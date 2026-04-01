"""
OVD Platform — Builders de objetos para tests.
Centraliza la construcción de OVDState y objetos relacionados
para evitar duplicación y facilitar el mantenimiento.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
from typing import Any

# ─── OVDState builder ────────────────────────────────────────────────────────

_STATE_DEFAULTS: dict[str, Any] = {
    # Input
    "session_id":    "test-session-001",
    "org_id":        "org-test-001",
    "project_id":    "proj-test-001",
    "directory":     "/tmp/test-repo",
    "feature_request": "Agregar endpoint de login con JWT",
    "project_context": "## Stack\nPython / FastAPI / PostgreSQL",
    "jwt_token":     "",
    "language":      "es",
    "auto_approve":  False,
    # Stack routing (S8)
    "stack_routing":     "auto",
    "stack_db_engine":   "postgresql",
    "stack_db_version":  "16",
    "stack_restrictions": [],
    # GitHub (S6)
    "github_token":  "",
    "github_repo":   "",
    "github_branch": "main",
    "github_pr":     {},
    # RAG / Research (S11)
    "rag_context":         "",
    "research_enabled":    False,
    "web_research_results": [],
    # Trace (S10)
    "trace_id": "0" * 32,
    # GAP-004
    "constraints_version": "no-profile",
    "uncertainty_register": [],
    # Intermedios
    "fr_analysis":     {},
    "sdd":             {},
    "approval_decision": "",
    "approval_comment":  "",
    # GAP-002 fan-out
    "selected_agents": ["backend"],
    "current_agent":   "backend",
    "agent_results":   [],
    # GAP-001/005
    "security_result":     {},
    "qa_result":           {},
    "security_retry_count": 0,
    "qa_retry_count":       0,
    "retry_feedback":       "",
    "escalation_resolution": "",
    # Tokens / timing
    "token_usage":    {},
    "cycle_start_ts": time.time() - 5.0,
    # Output
    "deliverables": [],
    "status":       "idle",
    "messages":     [],
}


def make_state(**overrides) -> dict:
    """
    Retorna un OVDState mínimo válido con los campos necesarios.
    Aplica los overrides encima de los defaults.

    Uso:
        state = make_state(feature_request="Fix bug en login", auto_approve=True)
    """
    return {**_STATE_DEFAULTS, **overrides}


def make_fr_analysis(
    fr_type: str = "feature",
    complexity: str = "medium",
    oracle_involved: bool = False,
    components: list | None = None,
    risks: list | None = None,
    summary: str = "FR analizado correctamente",
) -> dict:
    return {
        "raw":            summary,
        "type":           fr_type,
        "complexity":     complexity,
        "components":     components or ["api", "database"],
        "oracle_involved": oracle_involved,
        "risks":          risks or [],
        "summary":        summary,
    }


def make_sdd(
    agents: list | None = None,
    summary: str = "SDD de prueba",
) -> dict:
    agents = agents or ["backend"]
    tasks = [
        {"agent": a, "description": f"Tarea de {a}", "priority": "high"}
        for a in agents
    ]
    return {
        "summary":      summary,
        "requirements": [{"id": "R1", "text": "El sistema debe autenticar usuarios"}],
        "design":       {"architecture": "REST API", "components": agents},
        "constraints":  [{"type": "security", "text": "Usar HTTPS"}],
        "tasks":        tasks,
    }


def make_agent_result(
    agent: str = "backend",
    output: str = "```python\ndef login():\n    pass\n```",
    passed: bool = True,
) -> dict:
    return {
        "agent":     agent,
        "output":    output,
        "artifacts": [{"name": f"{agent}_impl.py", "content": output}],
        "passed":    passed,
    }


def make_security_result(
    passed: bool = True,
    score: int = 90,
    severity: str = "none",
    vulnerabilities: list | None = None,
) -> dict:
    return {
        "passed":            passed,
        "score":             score,
        "severity":          severity,
        "vulnerabilities":   vulnerabilities or [],
        "secrets_found":     [],
        "insecure_patterns": [],
        "rls_compliant":     True,
        "remediation":       [],
        "summary":           "Sin vulnerabilidades críticas",
    }


def make_qa_result(
    passed: bool = True,
    score: int = 85,
    sdd_compliance: int = 90,
    issues: list | None = None,
) -> dict:
    return {
        "passed":              passed,
        "score":               score,
        "issues":              issues or [],
        "sdd_compliance":      sdd_compliance,
        "missing_requirements": [],
        "code_quality_issues": [],
        "summary":             "Calidad aceptable",
    }
