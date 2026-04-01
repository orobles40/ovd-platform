"""
OVD Platform — Tests de integración del grafo completo (smoke tests)
Sprint: S6+

Verifica que el grafo puede construirse con MemorySaver y que los nodos
críticos están registrados. No ejecuta ningún ciclo completo.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from langgraph.checkpoint.memory import MemorySaver

from graph import build_graph, OVDState


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_build_graph_exitoso():
    """build_graph con MemorySaver no lanza excepción y retorna un grafo compilado."""
    checkpointer = MemorySaver()
    compiled = build_graph(checkpointer)
    assert compiled is not None


def test_grafo_tiene_nodos_criticos():
    """El grafo compilado registra todos los nodos del pipeline principal."""
    checkpointer = MemorySaver()
    compiled = build_graph(checkpointer)

    nodos_criticos = [
        "analyze_fr",
        "generate_sdd",
        "request_approval",
        "route_agents",
        "agent_executor",
        "security_audit",
        "qa_review",
        "deliver",
    ]

    # El grafo compilado expone sus nodos en el atributo .nodes (dict-like)
    for nodo in nodos_criticos:
        assert nodo in compiled.nodes, (
            f"El nodo '{nodo}' no está registrado en el grafo. "
            f"Nodos disponibles: {list(compiled.nodes.keys())}"
        )


def test_grafo_tiene_nodos_de_soporte():
    """El grafo incluye los nodos auxiliares: clone_repo, create_pr, retry, escalation."""
    checkpointer = MemorySaver()
    compiled = build_graph(checkpointer)

    nodos_soporte = [
        "clone_repo",
        "create_pr",
        "security_retry",
        "qa_retry",
        "handle_escalation",
    ]

    for nodo in nodos_soporte:
        assert nodo in compiled.nodes, (
            f"El nodo de soporte '{nodo}' no está en el grafo. "
            f"Nodos disponibles: {list(compiled.nodes.keys())}"
        )


def test_build_graph_devuelve_mismo_tipo_con_distintos_checkpointers():
    """Construir el grafo dos veces con checkpointers distintos funciona correctamente."""
    compiled_1 = build_graph(MemorySaver())
    compiled_2 = build_graph(MemorySaver())

    assert compiled_1 is not None
    assert compiled_2 is not None
    # Son instancias independientes
    assert compiled_1 is not compiled_2
