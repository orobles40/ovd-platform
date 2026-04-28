"""
S22 — Tests del nodo generate_docs y su integración con deliver.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.factories import make_state


def _make_state_with_docs(**kwargs) -> dict:
    return make_state(
        sdd={
            "summary": "Endpoint GET /users que retorna lista paginada",
            "requirements": [],
            "design": {},
            "constraints": [],
            "tasks": [],
        },
        fr_analysis={"type": "endpoint"},
        agent_results=[
            {
                "agent": "backend",
                "output": (
                    "```python:src/api/users.py\n"
                    "from fastapi import APIRouter\n"
                    "router = APIRouter()\n\n"
                    "@router.get('/users')\nasync def list_users(): ...\n"
                    "```"
                ),
            }
        ],
        **kwargs,
    )


# ---------------------------------------------------------------------------
# generate_docs — happy paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_docs_backend_endpoint_generates_openapi():
    """FR tipo 'endpoint' genera spec OpenAPI."""
    import graph as g

    state = _make_state_with_docs()
    openapi_block = (
        "```yaml:docs/openapi.yaml\n"
        "openapi: '3.0.0'\npaths:\n  /users:\n    get:\n      summary: List users\n"
        "```"
    )

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=openapi_block))

    with patch("graph.model_router") as mock_router:
        mock_router.get_llm_with_context = AsyncMock(return_value=mock_llm)
        result = await g.generate_docs(state)

    assert len(result["generated_docs"]) == 1
    assert result["generated_docs"][0]["type"] == "openapi"
    assert result["generated_docs"][0]["path"] == "docs/openapi.yaml"
    assert result["status"] == "docs_done"


@pytest.mark.asyncio
async def test_generate_docs_refactor_generates_changelog():
    """FR tipo 'refactor' genera entrada de CHANGELOG."""
    import graph as g

    state = make_state(
        sdd={
            "summary": "Refactor módulo de pagos",
            "requirements": [],
            "design": {},
            "constraints": [],
            "tasks": [],
        },
        fr_analysis={"type": "refactor"},
        agent_results=[{"agent": "backend", "output": "# refactored code"}],
    )

    changelog_block = (
        "```markdown:CHANGELOG.md\n"
        "## [Unreleased]\n### Changed\n- Refactor módulo de pagos\n"
        "```"
    )

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=changelog_block))

    with patch("graph.model_router") as mock_router:
        mock_router.get_llm_with_context = AsyncMock(return_value=mock_llm)
        result = await g.generate_docs(state)

    assert len(result["generated_docs"]) == 1
    assert result["generated_docs"][0]["type"] == "changelog"


@pytest.mark.asyncio
async def test_generate_docs_frontend_generates_readme():
    """FR tipo 'frontend' genera README de componente."""
    import graph as g

    state = make_state(
        sdd={
            "summary": "Componente LoginForm",
            "requirements": [],
            "design": {},
            "constraints": [],
            "tasks": [],
        },
        fr_analysis={"type": "frontend"},
        agent_results=[{"agent": "frontend", "output": "# LoginForm component"}],
    )

    readme_block = (
        "```markdown:docs/LoginForm.md\n"
        "# LoginForm\nProps: email, password, onSubmit\n"
        "```"
    )

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=readme_block))

    with patch("graph.model_router") as mock_router:
        mock_router.get_llm_with_context = AsyncMock(return_value=mock_llm)
        result = await g.generate_docs(state)

    assert len(result["generated_docs"]) == 1
    assert result["generated_docs"][0]["type"] == "readme"


# ---------------------------------------------------------------------------
# generate_docs — fallo graceful
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_docs_llm_failure_returns_empty_docs():
    """Si el LLM falla, retorna generated_docs=[] sin romper el ciclo."""
    import graph as g

    state = _make_state_with_docs()

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM timeout"))

    with patch("graph.model_router") as mock_router:
        mock_router.get_llm_with_context = AsyncMock(return_value=mock_llm)
        result = await g.generate_docs(state)

    assert result["generated_docs"] == []
    assert result["status"] == "docs_skipped"
    # El mensaje informa del fallo sin propagar excepción
    assert "no se pudo generar" in result["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_generate_docs_no_code_blocks_returns_empty():
    """Si el LLM responde sin bloques de código con ruta, generated_docs=[]."""
    import graph as g

    state = _make_state_with_docs()

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=MagicMock(content="Aquí va la documentación sin bloques.")
    )

    with patch("graph.model_router") as mock_router:
        mock_router.get_llm_with_context = AsyncMock(return_value=mock_llm)
        result = await g.generate_docs(state)

    assert result["generated_docs"] == []
    assert result["status"] == "docs_skipped"
