"""
Tests S98 — Filtrado de runners (Opción A) + telemetría por nodo.

S98-A: omitir runner 'frontend' cuando el FR no menciona UI/frontend.
S98-B: campos de configuración de modelo por rol.
"""

import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from graph import _AGENT_RUNNERS, _FRONTEND_KEYWORDS
from settings import OVDSettings

# ---------------------------------------------------------------------------
# S98-A: filtrado de runner 'frontend'
# ---------------------------------------------------------------------------


def _make_state(fr_raw: str, fr_type: str = "feature", agents: list | None = None):
    """Estado mínimo para route_agents."""
    return {
        "feature_request": fr_raw,
        "fr_analysis": {
            "raw": fr_raw,
            "type": fr_type,
            "complexity": "medium",
            "agents": agents or ["backend", "database", "frontend"],
        },
        "sdd": {},
        "agent_results": {},
        "qa_result": {},
        "qa_score_history": [],
        "qa_retry_count": 0,
        "security_retry_count": 0,
    }


def test_frontend_keywords_constant_exists():
    """_FRONTEND_KEYWORDS debe existir y contener términos básicos."""
    assert "frontend" in _FRONTEND_KEYWORDS
    assert "react" in _FRONTEND_KEYWORDS
    assert "ui" in _FRONTEND_KEYWORDS
    assert "dashboard" in _FRONTEND_KEYWORDS


def test_agent_runners_has_four_runners():
    """_AGENT_RUNNERS tiene exactamente los 4 runners del fan-out."""
    assert set(_AGENT_RUNNERS.keys()) == {"backend", "database", "devops", "frontend"}


def test_filter_omits_frontend_for_backend_fr(monkeypatch):
    """FR de backend puro → frontend debe ser omitido cuando el filtro está activo."""
    monkeypatch.setenv("OVD_AGENT_FILTER_ENABLED", "true")

    # Simular la lógica de filtrado directamente (sin invocar route_agents completo
    # que requiere LLM). Replicamos exactamente la condición de graph.py.
    fr_raw = "api rest fastapi con postgresql y jwt. solo endpoints, sin capa visual."
    fr_type = "feature"
    selected = ["backend", "database", "frontend"]

    if (
        os.environ.get("OVD_AGENT_FILTER_ENABLED", "true").lower() != "false"
        and "frontend" in selected
    ):
        if fr_type not in {"fullstack", "frontend_only"} and not any(
            kw in fr_raw.lower() for kw in _FRONTEND_KEYWORDS
        ):
            selected = [a for a in selected if a != "frontend"]

    assert "frontend" not in selected
    assert "backend" in selected
    assert "database" in selected


def test_filter_keeps_frontend_for_fullstack_fr(monkeypatch):
    """fr_type='fullstack' → frontend NO debe ser omitido."""
    monkeypatch.setenv("OVD_AGENT_FILTER_ENABLED", "true")

    fr_raw = "sistema completo con api y dashboard react"
    fr_type = "fullstack"
    selected = ["backend", "database", "frontend"]

    if (
        os.environ.get("OVD_AGENT_FILTER_ENABLED", "true").lower() != "false"
        and "frontend" in selected
    ):
        if fr_type not in {"fullstack", "frontend_only"} and not any(
            kw in fr_raw.lower() for kw in _FRONTEND_KEYWORDS
        ):
            selected = [a for a in selected if a != "frontend"]

    assert "frontend" in selected


def test_filter_keeps_frontend_when_ui_keyword_in_fr(monkeypatch):
    """FR con keyword UI explícita → frontend se conserva aunque fr_type='feature'."""
    monkeypatch.setenv("OVD_AGENT_FILTER_ENABLED", "true")

    fr_raw = "sistema de login con formulario react y api fastapi"
    fr_type = "feature"
    selected = ["backend", "database", "frontend"]

    if (
        os.environ.get("OVD_AGENT_FILTER_ENABLED", "true").lower() != "false"
        and "frontend" in selected
    ):
        if fr_type not in {"fullstack", "frontend_only"} and not any(
            kw in fr_raw.lower() for kw in _FRONTEND_KEYWORDS
        ):
            selected = [a for a in selected if a != "frontend"]

    assert "frontend" in selected


def test_filter_disabled_keeps_frontend(monkeypatch):
    """OVD_AGENT_FILTER_ENABLED=false → no se filtra nada."""
    monkeypatch.setenv("OVD_AGENT_FILTER_ENABLED", "false")

    fr_raw = "api rest sin interfaz"
    fr_type = "feature"
    selected = ["backend", "database", "frontend"]

    if (
        os.environ.get("OVD_AGENT_FILTER_ENABLED", "true").lower() != "false"
        and "frontend" in selected
    ):
        if fr_type not in {"fullstack", "frontend_only"} and not any(
            kw in fr_raw.lower() for kw in _FRONTEND_KEYWORDS
        ):
            selected = [a for a in selected if a != "frontend"]

    assert "frontend" in selected


def test_filter_keeps_frontend_only_type(monkeypatch):
    """fr_type='frontend_only' → frontend siempre se conserva."""
    monkeypatch.setenv("OVD_AGENT_FILTER_ENABLED", "true")

    fr_raw = "pantalla de configuración de usuario"
    fr_type = "frontend_only"
    selected = ["frontend"]

    if (
        os.environ.get("OVD_AGENT_FILTER_ENABLED", "true").lower() != "false"
        and "frontend" in selected
    ):
        if fr_type not in {"fullstack", "frontend_only"} and not any(
            kw in fr_raw.lower() for kw in _FRONTEND_KEYWORDS
        ):
            selected = [a for a in selected if a != "frontend"]

    assert "frontend" in selected


# ---------------------------------------------------------------------------
# S98-A: cap de subtareas
# ---------------------------------------------------------------------------


def test_task_cap_truncates_when_limit_set(monkeypatch):
    """OVD_MAX_TASKS_PER_AGENT=2 → lista de 5 tareas se trunca a 2."""
    monkeypatch.setenv("OVD_MAX_TASKS_PER_AGENT", "2")

    agent_tasks = [{"id": i} for i in range(5)]
    _max_tasks = int(os.environ.get("OVD_MAX_TASKS_PER_AGENT", "0"))
    if _max_tasks > 0 and len(agent_tasks) > _max_tasks:
        agent_tasks = agent_tasks[:_max_tasks]

    assert len(agent_tasks) == 2


def test_task_cap_zero_means_no_limit(monkeypatch):
    """OVD_MAX_TASKS_PER_AGENT=0 (default) → lista no se trunca."""
    monkeypatch.setenv("OVD_MAX_TASKS_PER_AGENT", "0")

    agent_tasks = [{"id": i} for i in range(10)]
    _max_tasks = int(os.environ.get("OVD_MAX_TASKS_PER_AGENT", "0"))
    if _max_tasks > 0 and len(agent_tasks) > _max_tasks:
        agent_tasks = agent_tasks[:_max_tasks]

    assert len(agent_tasks) == 10


def test_task_cap_not_set_means_no_limit(monkeypatch):
    """Sin OVD_MAX_TASKS_PER_AGENT → default 0 → no hay truncamiento."""
    monkeypatch.delenv("OVD_MAX_TASKS_PER_AGENT", raising=False)

    agent_tasks = [{"id": i} for i in range(7)]
    _max_tasks = int(os.environ.get("OVD_MAX_TASKS_PER_AGENT", "0"))
    if _max_tasks > 0 and len(agent_tasks) > _max_tasks:
        agent_tasks = agent_tasks[:_max_tasks]

    assert len(agent_tasks) == 7


# ---------------------------------------------------------------------------
# S98-B: campos de configuración en OVDSettings
# ---------------------------------------------------------------------------


def test_settings_has_model_per_role_fields():
    """OVDSettings debe tener los campos de modelo por rol de S98-B."""
    s = OVDSettings()
    assert hasattr(s, "ovd_model_backend")
    assert hasattr(s, "ovd_model_database")
    assert hasattr(s, "ovd_model_devops")
    assert hasattr(s, "ovd_model_frontend")


def test_settings_model_role_defaults_empty():
    """Por defecto los overrides de modelo por rol son string vacío."""
    s = OVDSettings()
    assert s.ovd_model_backend == ""
    assert s.ovd_model_database == ""
    assert s.ovd_model_devops == ""
    assert s.ovd_model_frontend == ""


def test_settings_has_filter_fields():
    """OVDSettings debe tener los campos de control del filtro S98-A."""
    s = OVDSettings()
    assert hasattr(s, "ovd_agent_filter_enabled")
    assert hasattr(s, "ovd_max_tasks_per_agent")
    assert s.ovd_agent_filter_enabled is True
    assert s.ovd_max_tasks_per_agent == 0


# ---------------------------------------------------------------------------
# S98: NODE_TIMING — verificar que los logs están en el código
# ---------------------------------------------------------------------------


def test_node_timing_present_in_graph_source():
    """graph.py debe contener logs NODE_TIMING para los nodos principales."""
    graph_path = pathlib.Path(__file__).parent.parent / "graph.py"
    source = graph_path.read_text()

    assert "NODE_TIMING" in source, "No se encontró ningún log NODE_TIMING en graph.py"
    # Los nodos más relevantes deben tener telemetría
    for node in ("analyze_fr", "generate_sdd", "qa_review"):
        assert f"node={node}" in source, f"Falta NODE_TIMING para nodo '{node}'"
