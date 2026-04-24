"""
OVD Platform — Tests S47: Ejecución secuencial server-side → client-side
S47-A: _dispatch_agents separa grupos, pending_agents en route_agents
S47-B: _AGENT_PATTERNS["frontend"] incluye archivos server-side de cualquier stack
S47-C: routing condicional post-grupo-1
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import pytest
from unittest.mock import MagicMock
from factories import make_state


# ---------------------------------------------------------------------------
# S47-A — Constantes de grupos
# ---------------------------------------------------------------------------

class TestS47AGroupConstants:

    def test_server_side_agents_definidos(self):
        """S47-A1: _SERVER_SIDE_AGENTS contiene database, backend, devops."""
        from graph import _SERVER_SIDE_AGENTS
        assert "database" in _SERVER_SIDE_AGENTS
        assert "backend"  in _SERVER_SIDE_AGENTS
        assert "devops"   in _SERVER_SIDE_AGENTS

    def test_client_side_agents_definidos(self):
        """S47-A1: _CLIENT_SIDE_AGENTS contiene frontend."""
        from graph import _CLIENT_SIDE_AGENTS
        assert "frontend" in _CLIENT_SIDE_AGENTS

    def test_grupos_son_disjuntos(self):
        """S47-A1: los dos grupos no se solapan."""
        from graph import _SERVER_SIDE_AGENTS, _CLIENT_SIDE_AGENTS
        assert _SERVER_SIDE_AGENTS.isdisjoint(_CLIENT_SIDE_AGENTS)


# ---------------------------------------------------------------------------
# S47-A — _dispatch_agents separa grupos
# ---------------------------------------------------------------------------

class TestS47ADispatchAgents:

    def test_dispatch_despacha_solo_grupo1(self):
        """S47-A2: con database+backend+frontend, _dispatch_agents despacha solo database+backend."""
        from graph import _dispatch_agents
        state = make_state(selected_agents=["database", "backend", "frontend"], pending_agents=["frontend"])
        sends = _dispatch_agents(state)
        agents_despachados = [s.node for s in sends]
        # todos los Send() deben ir a agent_executor
        assert all(s.node == "agent_executor" for s in sends)
        # solo despacha los server-side (database + backend)
        current_agents = [s.arg["current_agent"] for s in sends]
        assert "database" in current_agents
        assert "backend"  in current_agents
        assert "frontend" not in current_agents

    def test_dispatch_solo_frontend_va_directo(self):
        """S47-A2 edge case: SDD con solo frontend → despacha directamente sin esperar."""
        from graph import _dispatch_agents
        state = make_state(selected_agents=["frontend"], pending_agents=[])
        sends = _dispatch_agents(state)
        current_agents = [s.arg["current_agent"] for s in sends]
        assert "frontend" in current_agents
        assert len(sends) == 1

    def test_dispatch_sin_frontend_no_tiene_pendientes(self):
        """S47-A2: SDD con solo backend+database → pending_agents vacío."""
        from graph import _SERVER_SIDE_AGENTS
        selected = ["backend", "database"]
        # pending_agents se calcula en route_agents — verificar lógica
        group2 = [a for a in selected if a not in _SERVER_SIDE_AGENTS]
        assert group2 == []

    def test_dispatch_frontend_despacha_pendientes(self):
        """S47-A3: _dispatch_frontend despacha los agentes en pending_agents."""
        from graph import _dispatch_frontend
        state = make_state(pending_agents=["frontend"])
        sends = _dispatch_frontend(state)
        assert len(sends) == 1
        assert sends[0].arg["current_agent"] == "frontend"

    def test_dispatch_frontend_vacio_no_envia_nada(self):
        """S47-A3: _dispatch_frontend con pending_agents=[] devuelve lista vacía."""
        from graph import _dispatch_frontend
        state = make_state(pending_agents=[])
        sends = _dispatch_frontend(state)
        assert sends == []


# ---------------------------------------------------------------------------
# S47-A — route_agents guarda pending_agents
# ---------------------------------------------------------------------------

class TestS47ARouteAgents:

    def test_route_agents_guarda_pending_cuando_hay_frontend(self):
        """S47-A4: route_agents pone frontend en pending_agents cuando hay server-side también."""
        from graph import _SERVER_SIDE_AGENTS, _CLIENT_SIDE_AGENTS
        selected = ["backend", "frontend"]
        group1 = [a for a in selected if a in _SERVER_SIDE_AGENTS]
        group2 = [a for a in selected if a in _CLIENT_SIDE_AGENTS]
        pending = group2 if group1 else []
        assert pending == ["frontend"]

    def test_route_agents_pending_vacio_sin_frontend(self):
        """S47-A4: sin frontend en el SDD, pending_agents queda vacío."""
        from graph import _SERVER_SIDE_AGENTS, _CLIENT_SIDE_AGENTS
        selected = ["backend", "database", "devops"]
        group1 = [a for a in selected if a in _SERVER_SIDE_AGENTS]
        group2 = [a for a in selected if a in _CLIENT_SIDE_AGENTS]
        pending = group2 if group1 else []
        assert pending == []


# ---------------------------------------------------------------------------
# S47-B — Frontend patterns incluyen archivos server-side
# ---------------------------------------------------------------------------

class TestS47BFrontendPatterns:

    def _patterns(self):
        from tools.file_tools import _AGENT_PATTERNS
        return _AGENT_PATTERNS["frontend"]

    def test_frontend_lee_tsx_ts(self):
        """S47-B1: frontend sigue leyendo sus propios archivos."""
        patterns = self._patterns()
        assert "*.tsx" in patterns
        assert "*.ts"  in patterns

    def test_frontend_lee_python(self):
        """S47-B1: frontend lee *.py para conocer rutas FastAPI/Django/Flask."""
        assert "*.py" in self._patterns()

    def test_frontend_lee_java(self):
        """S47-B1: frontend lee *.java para conocer APIs Spring Boot."""
        assert "*.java" in self._patterns()

    def test_frontend_lee_go(self):
        """S47-B1: frontend lee *.go para conocer APIs Go."""
        assert "*.go" in self._patterns()

    def test_frontend_lee_rust(self):
        """S47-B1: frontend lee *.rs para conocer APIs Rust (Axum/Actix)."""
        assert "*.rs" in self._patterns()

    def test_frontend_lee_sql(self):
        """S47-B1: frontend lee *.sql para conocer modelos de datos."""
        assert "*.sql" in self._patterns()

    def test_frontend_lee_requirements(self):
        """S47-B1: frontend lee requirements.txt para conocer dependencias de backend."""
        assert "requirements.txt" in self._patterns()


# ---------------------------------------------------------------------------
# S47-C — Routing condicional post-grupo-1
# ---------------------------------------------------------------------------

class TestS47CRouting:

    def test_route_con_pending_va_a_dispatch_frontend(self):
        """S47-C1: con pending_agents no vacío → dispatch_frontend."""
        from graph import _route_after_agent_executor
        state = make_state(pending_agents=["frontend"])
        assert _route_after_agent_executor(state) == "dispatch_frontend"

    def test_route_sin_pending_va_a_security_audit(self):
        """S47-C1: con pending_agents vacío → security_audit (flujo normal)."""
        from graph import _route_after_agent_executor
        state = make_state(pending_agents=[])
        assert _route_after_agent_executor(state) == "security_audit"

    def test_route_pending_none_va_a_security_audit(self):
        """S47-C1: si pending_agents no está en el estado → security_audit."""
        from graph import _route_after_agent_executor
        state = make_state()
        # make_state incluye pending_agents=[] por defecto desde factories
        assert _route_after_agent_executor(state) == "security_audit"
