"""
OVD Platform — Tests para el nodo request_approval
Sprint: S6+

request_approval usa interrupt() de LangGraph, que lanza GraphInterrupt.
Los tests verifican el comportamiento con y sin auto_approve.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))  # para factories

import pytest
from unittest.mock import patch, MagicMock
from langgraph.errors import GraphInterrupt

from factories import make_state, make_sdd, make_fr_analysis
from graph import request_approval


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approval_lanza_interrupt():
    """Sin auto_approve, el nodo llama interrupt().
    interrupt() requiere contexto de LangGraph — lo mockeamos para aislar el nodo.
    """
    state = make_state(
        auto_approve=False,
        sdd=make_sdd(),
        fr_analysis=make_fr_analysis(),
    )

    # interrupt() de langgraph.types necesita contexto de graph — mockearlo
    with patch("graph.interrupt", side_effect=GraphInterrupt([MagicMock(value={"type": "pending_approval", "context": {"sdd_summary": "test"}})])):
        with pytest.raises(GraphInterrupt):
            await request_approval(state)


@pytest.mark.asyncio
async def test_auto_approve_salta_interrupt():
    """Con auto_approve=True, NO lanza interrupt y retorna approval_decision='approved'."""
    state = make_state(
        auto_approve=True,
        sdd=make_sdd(),
        fr_analysis=make_fr_analysis(),
    )

    # No debe lanzar GraphInterrupt
    result = await request_approval(state)

    assert result["approval_decision"] == "approved"
    assert result["status"] == "approved"


@pytest.mark.asyncio
async def test_auto_approve_agrega_mensaje():
    """Con auto_approve=True, el resultado incluye un mensaje de agente."""
    state = make_state(
        auto_approve=True,
        sdd=make_sdd(),
        fr_analysis=make_fr_analysis(),
        messages=[],
    )

    result = await request_approval(state)

    msgs = result["messages"]
    assert len(msgs) >= 1
    agent_msgs = [m for m in msgs if m.get("role") == "agent"]
    assert len(agent_msgs) >= 1


@pytest.mark.asyncio
async def test_approval_payload_incluye_sdd():
    """El interrupt es llamado con un payload que incluye información del SDD."""
    sdd = make_sdd(summary="SDD de prueba para approval")
    state = make_state(
        auto_approve=False,
        sdd=sdd,
        fr_analysis=make_fr_analysis(fr_type="feature", complexity="medium"),
    )

    captured_payload = {}

    def capture_interrupt(payload):
        captured_payload.update(payload)
        raise GraphInterrupt([MagicMock(value=payload)])

    with patch("graph.interrupt", side_effect=capture_interrupt):
        try:
            await request_approval(state)
            pytest.fail("Se esperaba GraphInterrupt pero no se lanzó")
        except GraphInterrupt:
            pass

    assert "type" in captured_payload, f"El payload debe tener 'type'. Payload: {captured_payload}"
    assert captured_payload["type"] == "pending_approval"
    context = captured_payload.get("context", {})
    assert "sdd_summary" in context or "tasks" in context or "sdd" in str(context).lower(), \
        f"El contexto debe incluir info del SDD. Context: {context}"
