"""
OVD Platform — Tests para el nodo deliver
Sprint: S6+
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))  # para factories

import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from factories import make_state, make_sdd, make_agent_result, make_security_result, make_qa_result
from graph import deliver
from model_router import ResolvedConfig

# deliver llama nats_client.publish_done y AuditLogger.cycle_completed
pytestmark = pytest.mark.usefixtures("mock_nats", "mock_audit_logger")


# ---------------------------------------------------------------------------
# Fixture: ResolvedConfig por defecto (Ollama — sin costo)
# ---------------------------------------------------------------------------

_DEFAULT_RESOLVED = ResolvedConfig(
    provider="ollama",
    model="qwen2.5-coder:7b",
    base_url=None,
    api_key_env=None,
    extra_instructions=None,
    constraints=None,
    code_style=None,
    resolved_from="default",
    temperature=0.0,
)


def _make_deliver_state(**overrides):
    """State mínimo válido para ejecutar deliver."""
    defaults = dict(
        sdd=make_sdd(),
        agent_results=[make_agent_result("backend")],
        security_result=make_security_result(),
        qa_result=make_qa_result(),
        token_usage={"backend": {"input": 100, "output": 200}},
        cycle_start_ts=time.time() - 10.0,
        messages=[],
    )
    defaults.update(overrides)
    return make_state(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deliver_incluye_sdd_como_artefacto():
    """El deliverable de tipo 'sdd' está presente cuando hay sdd en el state."""
    with patch("model_router.resolve", new=AsyncMock(return_value=_DEFAULT_RESOLVED)):
        state = _make_deliver_state()
        result = await deliver(state)

    types = [d["type"] for d in result["deliverables"]]
    assert "sdd" in types, f"Se esperaba 'sdd' en deliverables. Tipos: {types}"
    sdd_artifact = next(d for d in result["deliverables"] if d["type"] == "sdd")
    assert sdd_artifact["agent"] == "architect"


@pytest.mark.asyncio
async def test_deliver_incluye_resultados_agentes():
    """Los resultados de cada agente se incluyen como deliverables de tipo 'implementation'."""
    with patch("model_router.resolve", new=AsyncMock(return_value=_DEFAULT_RESOLVED)):
        state = _make_deliver_state(
            agent_results=[make_agent_result("backend"), make_agent_result("frontend")]
        )
        result = await deliver(state)

    impl_deliverables = [d for d in result["deliverables"] if d["type"] == "implementation"]
    assert len(impl_deliverables) == 2
    agents_in_deliverables = {d["agent"] for d in impl_deliverables}
    assert "backend" in agents_in_deliverables
    assert "frontend" in agents_in_deliverables


@pytest.mark.asyncio
async def test_deliver_retorna_status_done():
    """El nodo finaliza el ciclo con status='done'."""
    with patch("model_router.resolve", new=AsyncMock(return_value=_DEFAULT_RESOLVED)):
        state = _make_deliver_state()
        result = await deliver(state)

    assert result["status"] == "done"


@pytest.mark.asyncio
async def test_deliver_sin_github_pr_vacio():
    """Sin github_token configurado, github_pr permanece vacío (no se modifica en deliver)."""
    with patch("model_router.resolve", new=AsyncMock(return_value=_DEFAULT_RESOLVED)):
        state = _make_deliver_state(github_token="", github_repo="", github_pr={})
        result = await deliver(state)

    # deliver no establece github_pr — eso lo hace create_pr
    # Verificar que deliver no crea un PR donde no debería
    assert "github_pr" not in result or result.get("github_pr") == {}


@pytest.mark.asyncio
async def test_deliver_agrega_mensaje_final():
    """El nodo agrega al menos un mensaje que menciona 'Ciclo completado' o entrega."""
    with patch("model_router.resolve", new=AsyncMock(return_value=_DEFAULT_RESOLVED)):
        state = _make_deliver_state(messages=[])
        result = await deliver(state)

    msgs = result["messages"]
    assert len(msgs) >= 1
    combined = " ".join(m.get("content", "") for m in msgs)
    # El mensaje de deliver menciona "Entrega completada" o variantes
    entrega_keywords = ["Entrega completada", "artefacto", "Ciclo completado"]
    found = any(kw in combined for kw in entrega_keywords)
    assert found, f"El mensaje debería mencionar la entrega. Contenido: {combined[:200]}"
