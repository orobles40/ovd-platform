"""
OVD Platform — Tests para el nodo analyze_fr
Sprint: S6+
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))  # para factories

import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from factories import make_state
from graph import analyze_fr, FRAnalysisOutput

# analyze_fr llama nats_client.publish_started → mockear para unit tests
pytestmark = pytest.mark.usefixtures("mock_nats")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def make_llm_mock(return_value):
    structured = MagicMock()
    structured.ainvoke = AsyncMock(return_value=return_value)
    llm = MagicMock()
    llm.with_structured_output = MagicMock(return_value=structured)
    return llm


def _make_fr_output(fr_type="feature", complexity="medium"):
    return FRAnalysisOutput(
        fr_type=fr_type,
        complexity=complexity,
        components=["api", "database"],
        oracle_involved=False,
        risks=[],
        summary="FR analizado correctamente",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyze_fr_retorna_analisis_correcto():
    """El nodo retorna fr_analysis con el tipo y complejidad del LLM."""
    llm = make_llm_mock(_make_fr_output(fr_type="feature", complexity="medium"))

    with patch("model_router.get_llm_with_context", new=AsyncMock(return_value=llm)):
        state = make_state(feature_request="Agregar endpoint de login")
        result = await analyze_fr(state)

    assert result["fr_analysis"]["type"] == "feature"
    assert result["fr_analysis"]["complexity"] == "medium"
    assert result["status"] == "analyzed"


@pytest.mark.asyncio
async def test_analyze_fr_calcula_constraints_version():
    """constraints_version es un hash de 8 chars cuando hay project_context;
    'no-profile' cuando el contexto está vacío."""
    llm = make_llm_mock(_make_fr_output())

    # Con project_context
    with patch("model_router.get_llm_with_context", new=AsyncMock(return_value=llm)):
        state_with = make_state(project_context="## Stack\nPython / FastAPI")
        result_with = await analyze_fr(state_with)

    cv = result_with["constraints_version"]
    assert len(cv) == 8, f"Se esperaban 8 chars hexadecimales, se obtuvo: {cv!r}"
    # Verificar que es hex válido
    int(cv, 16)

    # Sin project_context
    with patch("model_router.get_llm_with_context", new=AsyncMock(return_value=llm)):
        state_empty = make_state(project_context="")
        result_empty = await analyze_fr(state_empty)

    assert result_empty["constraints_version"] == "no-profile"


@pytest.mark.asyncio
async def test_analyze_fr_inicializa_contadores():
    """El nodo inicializa security_retry_count=0, qa_retry_count=0 y retry_feedback=""."""
    llm = make_llm_mock(_make_fr_output())

    with patch("model_router.get_llm_with_context", new=AsyncMock(return_value=llm)):
        state = make_state()
        result = await analyze_fr(state)

    assert result["security_retry_count"] == 0
    assert result["qa_retry_count"] == 0
    assert result["retry_feedback"] == ""


@pytest.mark.asyncio
async def test_analyze_fr_agrega_mensaje():
    """El nodo agrega al menos un mensaje con role='agent' en result['messages']."""
    llm = make_llm_mock(_make_fr_output())

    with patch("model_router.get_llm_with_context", new=AsyncMock(return_value=llm)):
        state = make_state(messages=[])
        result = await analyze_fr(state)

    msgs = result["messages"]
    assert len(msgs) >= 1
    agent_msgs = [m for m in msgs if m.get("role") == "agent"]
    assert len(agent_msgs) >= 1, "Debe haber al menos un mensaje con role='agent'"


@pytest.mark.asyncio
async def test_analyze_fr_registra_cycle_start_ts():
    """El nodo registra cycle_start_ts como un timestamp positivo."""
    llm = make_llm_mock(_make_fr_output())
    before = time.time()

    with patch("model_router.get_llm_with_context", new=AsyncMock(return_value=llm)):
        state = make_state()
        result = await analyze_fr(state)

    after = time.time()
    ts = result["cycle_start_ts"]
    assert ts > 0, "cycle_start_ts debe ser positivo"
    assert before <= ts <= after + 1, "cycle_start_ts debe ser cercano al momento de ejecución"
