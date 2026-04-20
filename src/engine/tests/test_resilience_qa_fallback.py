"""
S20 — GAP-R5: Tests del fallback en qa_review y _parse_qa_fallback.
"""
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Tests de _parse_qa_fallback
# ---------------------------------------------------------------------------

def test_parse_qa_fallback_extracts_json_from_text():
    """Extrae campos de un JSON embebido en texto libre."""
    from graph import _parse_qa_fallback

    raw = """
    Aquí está el resultado:
    {"passed": true, "score": 82, "issues": ["falta validación"], "sdd_compliance": true,
     "missing_requirements": [], "code_quality_issues": [], "summary": "Buen trabajo."}
    """
    result = _parse_qa_fallback(raw)
    assert result.passed is True
    assert result.score == 82
    assert result.issues == ["falta validación"]


def test_parse_qa_fallback_extracts_score_via_regex():
    """Extrae score via regex cuando no hay JSON válido."""
    from graph import _parse_qa_fallback

    raw = 'score: 78/100 — calidad aceptable'
    result = _parse_qa_fallback(raw)
    assert result.score == 78
    assert result.passed is True  # 78 >= 60


def test_parse_qa_fallback_returns_neutral_on_unparseable():
    """Retorna resultado neutro cuando no puede extraer nada."""
    from graph import _parse_qa_fallback

    result = _parse_qa_fallback("texto sin información útil")
    assert result.passed is True
    assert result.score == 70
    assert result.issues == []


# ---------------------------------------------------------------------------
# Tests de qa_review con fallback
# ---------------------------------------------------------------------------

def _make_qa_state():
    return {
        "org_id": "org1",
        "project_id": "proj1",
        "jwt_token": "",
        "stack_routing": "auto",
        "language": "es",
        "project_context": "",
        "sdd": {"summary": "SDD de prueba"},
        "agent_results": [{"output": "código generado"}],
    }


@pytest.mark.asyncio
async def test_qa_review_returns_neutral_on_invoke_failure():
    """qa_review retorna resultado neutro si invoke_structured y fallback raw fallan."""
    import graph as g

    state = _make_qa_state()
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM down"))

    with (
        patch("model_router.get_llm_with_context", AsyncMock(return_value=mock_llm)),
        patch.object(g, "invoke_structured", AsyncMock(side_effect=Exception("structured failed"))),
    ):
        result_state = await g.qa_review(state)

    qa = result_state["qa_result"]
    assert qa["passed"] is True
    assert qa["score"] == 70
    assert "fallback" in qa["summary"].lower() or "neutro" in qa["summary"].lower()


@pytest.mark.asyncio
async def test_qa_review_uses_raw_fallback_when_structured_fails():
    """qa_review usa _parse_qa_fallback cuando invoke_structured falla pero llm.ainvoke funciona."""
    import graph as g

    state = _make_qa_state()
    mock_llm = MagicMock()
    raw_mock = MagicMock()
    raw_mock.content = '{"passed": true, "score": 75, "issues": [], "sdd_compliance": true, "missing_requirements": [], "code_quality_issues": [], "summary": "OK via raw"}'
    mock_llm.ainvoke = AsyncMock(return_value=raw_mock)

    with (
        patch("model_router.get_llm_with_context", AsyncMock(return_value=mock_llm)),
        patch.object(g, "invoke_structured", AsyncMock(side_effect=Exception("structured failed"))),
    ):
        result_state = await g.qa_review(state)

    qa = result_state["qa_result"]
    assert qa["score"] == 75


@pytest.mark.asyncio
async def test_qa_review_normal_path_unchanged():
    """qa_review retorna resultado normal cuando invoke_structured funciona."""
    import graph as g
    from graph import QAReviewOutput

    state = _make_qa_state()
    mock_llm = MagicMock()
    expected = QAReviewOutput(
        passed=True,
        score=90,
        issues=[],
        sdd_compliance=True,
        missing_requirements=[],
        code_quality_issues=[],
        summary="Excelente calidad.",
    )

    with (
        patch("model_router.get_llm_with_context", AsyncMock(return_value=mock_llm)),
        patch.object(g, "invoke_structured", AsyncMock(return_value=expected)),
    ):
        result_state = await g.qa_review(state)

    qa = result_state["qa_result"]
    assert qa["score"] == 90
    assert qa["passed"] is True
    assert qa["summary"] == "Excelente calidad."
