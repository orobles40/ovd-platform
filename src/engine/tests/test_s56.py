"""
OVD Platform — Tests S56

S56-A: _build_qa_sdd_block serializa requirements para QA; HumanMessage antepone bloque
S56-B: _configure_app_loggers setea nivel via OVD_LOG_LEVEL
S56-C: _strip_db_restrictions elimina restricciones Oracle cuando oracle_involved=False
S56-D: _filter_requirements_for_task filtra por depends_on (solo req IDs REQ-*)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import logging
from unittest.mock import patch

import pytest

import graph

# ---------------------------------------------------------------------------
# S56-A: _build_qa_sdd_block
# ---------------------------------------------------------------------------


def _make_sdd(requirements: list) -> dict:
    return {
        "summary": "SDD IMC",
        "requirements": requirements,
        "design": {"overview": "Simple"},
        "constraints": [],
        "tasks": [],
    }


def test_build_qa_sdd_block_includes_req_ids():
    """S56-A: el bloque incluye IDs y descripciones de requirements."""
    sdd = _make_sdd(
        [
            {
                "id": "REQ-001",
                "priority": "must",
                "description": "Calcular IMC",
                "acceptance_criteria": [],
            },
            {
                "id": "REQ-002",
                "priority": "should",
                "description": "Validar entradas positivas",
                "acceptance_criteria": [],
            },
        ]
    )
    result = graph._build_qa_sdd_block(sdd)
    assert "REQ-001" in result
    assert "REQ-002" in result
    assert "Calcular IMC" in result
    assert "Validar entradas positivas" in result


def test_build_qa_sdd_block_includes_acceptance_criteria():
    """S56-A: los criterios de aceptación aparecen en el bloque."""
    sdd = _make_sdd(
        [
            {
                "id": "REQ-001",
                "priority": "must",
                "description": "Endpoint POST /imc",
                "acceptance_criteria": [
                    "Devuelve 200 con body JSON",
                    "Rechaza peso negativo con 422",
                ],
            },
        ]
    )
    result = graph._build_qa_sdd_block(sdd)
    assert "Devuelve 200 con body JSON" in result
    assert "Rechaza peso negativo con 422" in result


def test_build_qa_sdd_block_empty_requirements():
    """S56-A: sin requirements, retorna string vacío."""
    sdd = _make_sdd([])
    result = graph._build_qa_sdd_block(sdd)
    assert result == ""


def test_build_qa_sdd_block_header():
    """S56-A: el bloque tiene el header de instrucción para el LLM."""
    sdd = _make_sdd(
        [
            {
                "id": "REQ-001",
                "priority": "must",
                "description": "Calcular IMC",
                "acceptance_criteria": [],
            },
        ]
    )
    result = graph._build_qa_sdd_block(sdd)
    assert "EVALÚA SOLO ESTOS" in result or "Requisitos del SDD a verificar" in result


# ---------------------------------------------------------------------------
# S56-B: _configure_app_loggers
# ---------------------------------------------------------------------------


def test_configure_app_loggers_sets_warning_by_default():
    """S56-B: sin OVD_LOG_LEVEL, el logger ovd-graph queda en WARNING."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("OVD_LOG_LEVEL", None)
        os.environ.pop("LOG_LEVEL", None)
        import api as api_mod

        api_mod._configure_app_loggers()
        lvl = logging.getLogger("ovd-graph").level
        assert lvl == logging.WARNING, f"Esperado WARNING (30), got {lvl}"


def test_configure_app_loggers_sets_info_from_env():
    """S56-B: OVD_LOG_LEVEL=INFO → logger ovd-graph en INFO."""
    with patch.dict(os.environ, {"OVD_LOG_LEVEL": "INFO"}):
        import api as api_mod

        api_mod._configure_app_loggers()
        lvl = logging.getLogger("ovd-graph").level
        assert lvl == logging.INFO, f"Esperado INFO (20), got {lvl}"


def test_configure_app_loggers_sets_debug_from_env():
    """S56-B: OVD_LOG_LEVEL=DEBUG → logger ovd-graph en DEBUG."""
    with patch.dict(os.environ, {"OVD_LOG_LEVEL": "DEBUG"}):
        import api as api_mod

        api_mod._configure_app_loggers()
        lvl = logging.getLogger("ovd-graph").level
        assert lvl == logging.DEBUG, f"Esperado DEBUG (10), got {lvl}"


def test_configure_app_loggers_has_handler():
    """S59-A/A1: _configure_app_loggers instala al menos un handler en el root logger."""
    with patch.dict(os.environ, {"OVD_LOG_LEVEL": "WARNING"}):
        import api as api_mod

        api_mod._configure_app_loggers()
        root = logging.getLogger()
        assert len(root.handlers) > 0, "Root logger sin handlers después de dictConfig"
        ovd_api = logging.getLogger("ovd.api")
        assert ovd_api.level == logging.WARNING, (
            f"ovd.api level inesperado: {ovd_api.level}"
        )


# ---------------------------------------------------------------------------
# S56-C: _strip_db_restrictions
# ---------------------------------------------------------------------------


def test_strip_db_restrictions_removes_oracle_lines():
    """S56-C: líneas con 'oracle' son eliminadas."""
    ctx = "Proyecto de cálculo matemático.\n## Restricciones\nUsa python-oracledb en modo thick.\nPython 3.11 requerido.\n"
    result = graph._strip_db_restrictions(ctx)
    assert "python-oracledb" not in result
    assert "Python 3.11 requerido" in result


def test_strip_db_restrictions_removes_fetch_first():
    """S56-C: restricciones como fetch_first son eliminadas."""
    ctx = "Stack: Python + FastAPI.\nno_fetch_first: no usar fetch_first en Oracle.\nValidar entradas.\n"
    result = graph._strip_db_restrictions(ctx)
    assert "fetch_first" not in result
    assert "Validar entradas" in result


def test_strip_db_restrictions_preserves_non_oracle_context():
    """S56-C: contexto sin restricciones Oracle se preserva íntegro."""
    ctx = "Stack: Python + FastAPI.\nValidar peso y altura positivos.\nRetornar JSON.\n"
    result = graph._strip_db_restrictions(ctx)
    assert result == ctx


def test_strip_db_restrictions_empty_string():
    """S56-C: string vacío retorna vacío sin error."""
    assert graph._strip_db_restrictions("") == ""


def test_strip_db_restrictions_logs_warning(caplog):
    """S56-C: emite WARNING para cada restricción omitida."""
    ctx = "Proyecto Python.\noracle_home=/opt/oracle.\nPython 3.11.\n"
    with caplog.at_level(logging.WARNING, logger="ovd-graph"):
        graph._strip_db_restrictions(ctx)
    warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("S56-C" in m for m in warning_msgs), (
        f"No se encontró WARNING S56-C. Mensajes: {warning_msgs}"
    )


# ---------------------------------------------------------------------------
# S56-D: _filter_requirements_for_task
# ---------------------------------------------------------------------------

_ALL_REQS = [
    {"id": "REQ-001", "priority": "must", "description": "Calcular IMC"},
    {"id": "REQ-002", "priority": "must", "description": "Validar entradas"},
    {"id": "REQ-003", "priority": "should", "description": "Responder en <100ms"},
    {"id": "REQ-004", "priority": "should", "description": "Retornar categoría"},
]


def test_filter_requirements_no_depends_on_returns_all():
    """S56-D: sin depends_on, retorna todos los requirements."""
    task = {"id": "TASK-001", "depends_on": []}
    result = graph._filter_requirements_for_task(_ALL_REQS, task)
    assert len(result) == len(_ALL_REQS)


def test_filter_requirements_with_req_depends_on():
    """S56-D: depends_on con REQ-IDs filtra requirements correspondientes."""
    task = {"id": "TASK-002", "depends_on": ["REQ-003", "REQ-004"]}
    result = graph._filter_requirements_for_task(_ALL_REQS, task)
    ids = {r["id"] for r in result}
    assert "REQ-003" in ids
    assert "REQ-004" in ids
    # REQ-001 y REQ-002 son must, deben seguir presentes
    assert "REQ-001" in ids
    assert "REQ-002" in ids


def test_filter_requirements_with_task_depends_on_only():
    """S56-D: depends_on con TASK-IDs (no REQ-*) retorna todos los requirements."""
    task = {"id": "TASK-003", "depends_on": ["TASK-001", "TASK-002"]}
    result = graph._filter_requirements_for_task(_ALL_REQS, task)
    assert len(result) == len(_ALL_REQS)


def test_filter_requirements_empty_list():
    """S56-D: lista vacía de requirements retorna lista vacía."""
    task = {"id": "TASK-001", "depends_on": ["REQ-001"]}
    result = graph._filter_requirements_for_task([], task)
    assert result == []
