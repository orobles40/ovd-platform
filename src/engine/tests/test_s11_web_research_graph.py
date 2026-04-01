"""
OVD Platform — Tests: web_research_node triggers y queries (Sprint 11)
No requiere LLM ni conexión real.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from graph import _should_run_web_research, _build_research_queries


def _state(**kwargs):
    """Construye un estado mínimo del grafo para los tests."""
    base = {
        "feature_request": "",
        "research_enabled": False,
        "fr_analysis": {},
        "stack_db_engine": "",
        "stack_db_version": "",
        "project_context": "",
        "org_id": "org1",
        "project_id": "proj1",
        "jwt_token": "",
        "stack_routing": "auto",
        "session_id": "s1",
        "trace_id": "",
    }
    base.update(kwargs)
    return base


class TestShouldRunWebResearch:
    def test_trigger_por_corchetes_en_fr(self):
        state = _state(feature_request="Implementar login [research]")
        assert _should_run_web_research(state) is True

    def test_trigger_por_arroba_en_fr(self):
        state = _state(feature_request="@research vulnerabilidades en FastAPI")
        assert _should_run_web_research(state) is True

    def test_trigger_por_research_enabled_true(self):
        state = _state(research_enabled=True)
        assert _should_run_web_research(state) is True

    def test_trigger_por_fr_type_security(self):
        state = _state(fr_analysis={"fr_type": "security", "complexity": "low"})
        assert _should_run_web_research(state) is True

    def test_trigger_por_oracle_alta_complejidad(self):
        state = _state(fr_analysis={
            "oracle_involved": True, "complexity": "high", "fr_type": "feature"
        })
        assert _should_run_web_research(state) is True

    def test_no_trigger_oracle_baja_complejidad(self):
        state = _state(fr_analysis={
            "oracle_involved": True, "complexity": "low", "fr_type": "feature"
        })
        assert _should_run_web_research(state) is False

    def test_no_trigger_fr_normal(self):
        state = _state(
            feature_request="Agregar campo apellido al formulario",
            fr_analysis={"fr_type": "feature", "complexity": "low", "oracle_involved": False},
        )
        assert _should_run_web_research(state) is False

    def test_trigger_case_insensitive_research(self):
        state = _state(feature_request="mejorar rendimiento [RESEARCH]")
        assert _should_run_web_research(state) is True


class TestBuildResearchQueries:
    def test_genera_al_menos_una_query(self):
        state = _state(
            feature_request="Implementar auth JWT",
            fr_analysis={
                "fr_type": "security",
                "components": ["auth", "middleware"],
                "risks": ["token exposure"],
                "summary": "Implementar autenticación JWT segura",
            },
        )
        queries = _build_research_queries(state)
        assert len(queries) >= 1

    def test_incluye_componentes_del_analisis(self):
        state = _state(
            fr_analysis={
                "fr_type": "feature",
                "components": ["FastAPI", "PostgreSQL"],
                "risks": [],
                "summary": "Agregar endpoint",
            },
        )
        queries = _build_research_queries(state)
        combined = " ".join(queries).lower()
        assert "fastapi" in combined or "postgresql" in combined

    def test_incluye_stack_oracle_si_disponible(self):
        state = _state(
            stack_db_engine="oracle",
            stack_db_version="12c",
            fr_analysis={
                "fr_type": "security",
                "components": ["database"],
                "risks": [],
                "summary": "Auditoría de seguridad",
                "oracle_involved": True,
            },
        )
        queries = _build_research_queries(state)
        combined = " ".join(queries).lower()
        assert "oracle" in combined or "12c" in combined

    def test_maximo_4_queries(self):
        state = _state(
            fr_analysis={
                "fr_type": "security",
                "components": ["a", "b", "c", "d", "e"],
                "risks": ["risk1", "risk2", "risk3"],
                "summary": "resumen largo " * 10,
            },
        )
        queries = _build_research_queries(state)
        assert len(queries) <= 4
