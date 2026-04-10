"""
OVD Platform — Tests E2E de endpoints FastAPI (Fase B)

E-01: POST /session — crear nueva sesión con RAG y ContextResolver mockeados.
      Verifica respuesta HTTP, estructura del body y que se invoca el resolver.

E-04: GET /session/{id}/delivery — verificar entrega de artefactos vía HTTP.
      Verifica estructura de respuesta y control de acceso por org_id.

Estrategia: lifespan mockeado (sin BD real), _graph y _checkpointer patcheados
por test. Sin LLM real ni NATS.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Lifespan mock — evita conexión a BD, NATS y Ollama
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _mock_lifespan(app):
    yield


with patch("api.lifespan", _mock_lifespan):
    from api import app
    import api as _api_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_OVD_SECRET = "test-secret"
_ORG_ID     = "org-test-001"
_PROJECT_ID = "proj-test-001"
_SESSION_ID = "tui-1234567890-abcd1234"
_THREAD_ID  = "thread-abc-001"


def _headers():
    return {"X-OVD-Secret": _OVD_SECRET}


def _make_agent_context():
    """AgentContext mínimo válido para ContextResolver.resolve_async."""
    from context_resolver import AgentContext, StackRegistry
    stack = StackRegistry(
        db_engine="postgresql",
        db_version="16",
    )
    return AgentContext(
        org_id=_ORG_ID,
        project_id=_PROJECT_ID,
        stack=stack,
        model_routing="ollama",
        restrictions=[],
        rag_context="",
        language="es",
    )


def _make_checkpointer_mock(existing_state=None):
    """Mock de checkpointer con aget configurable."""
    cp = MagicMock()
    cp.aget = AsyncMock(return_value=existing_state)
    return cp


def _make_graph_mock(state_values: dict | None = None):
    """Mock de grafo compilado con aget_state y aupdate_state configurables."""
    state_mock = MagicMock()
    state_mock.values = state_values or {}
    graph = MagicMock()
    graph.aget_state = AsyncMock(return_value=state_mock if state_values is not None else None)
    graph.aupdate_state = AsyncMock(return_value=None)
    return graph


# ---------------------------------------------------------------------------
# E-01 — POST /session
# ---------------------------------------------------------------------------

class TestE01PostSession:
    """
    E-01: Verificar que POST /session crea una sesión correctamente.
    Cubre: respuesta HTTP 200, campos thread_id/session_id/status,
    invocación de ContextResolver y rag_seed.
    """

    def _patch_env(self, monkeypatch):
        monkeypatch.setenv("OVD_SECRET", _OVD_SECRET)
        monkeypatch.setattr(_api_module, "_checkpointer", _make_checkpointer_mock())
        monkeypatch.setattr(_api_module, "_graph", _make_graph_mock())

    def test_post_session_retorna_201(self, monkeypatch):
        """POST /session con datos válidos retorna HTTP 201."""
        self._patch_env(monkeypatch)
        ctx = _make_agent_context()

        with patch("api.ContextResolver.resolve_async", new=AsyncMock(return_value=ctx)), \
             patch("api.rag_seed.retrieve_context", return_value=""), \
             patch("api.AuditLogger.session_created", new=AsyncMock()), \
             patch("api.AuditLogger.secret_accessed", new=AsyncMock()):

            client = TestClient(app)
            body = {
                "session_id": _SESSION_ID,
                "org_id": _ORG_ID,
                "project_id": _PROJECT_ID,
                "feature_request": "Agregar login con JWT",
                "project_context": "",
                "directory": "/tmp/test",
                "jwt_token": "",
                "auto_approve": False,
            }
            resp = client.post("/session", json=body, headers=_headers())

        assert resp.status_code == 201, f"Esperado 201, got {resp.status_code}: {resp.text}"

    def test_post_session_retorna_thread_id(self, monkeypatch):
        """La respuesta de POST /session incluye thread_id y session_id."""
        self._patch_env(monkeypatch)
        ctx = _make_agent_context()

        with patch("api.ContextResolver.resolve_async", new=AsyncMock(return_value=ctx)), \
             patch("api.rag_seed.retrieve_context", return_value=""), \
             patch("api.AuditLogger.session_created", new=AsyncMock()), \
             patch("api.AuditLogger.secret_accessed", new=AsyncMock()):

            client = TestClient(app)
            body = {
                "session_id": _SESSION_ID,
                "org_id": _ORG_ID,
                "project_id": _PROJECT_ID,
                "feature_request": "Agregar login con JWT",
                "project_context": "",
                "directory": "/tmp/test",
                "jwt_token": "",
                "auto_approve": False,
            }
            resp = client.post("/session", json=body, headers=_headers())
            data = resp.json()

        assert "thread_id" in data, f"Falta thread_id en respuesta: {data}"
        assert "session_id" in data, f"Falta session_id en respuesta: {data}"
        assert data["session_id"] == _SESSION_ID

    def test_post_session_status_es_created(self, monkeypatch):
        """El status en la respuesta debe ser 'created' para nueva sesión."""
        self._patch_env(monkeypatch)
        ctx = _make_agent_context()

        with patch("api.ContextResolver.resolve_async", new=AsyncMock(return_value=ctx)), \
             patch("api.rag_seed.retrieve_context", return_value=""), \
             patch("api.AuditLogger.session_created", new=AsyncMock()), \
             patch("api.AuditLogger.secret_accessed", new=AsyncMock()):

            client = TestClient(app)
            body = {
                "session_id": _SESSION_ID,
                "org_id": _ORG_ID,
                "project_id": _PROJECT_ID,
                "feature_request": "Agregar login con JWT",
                "project_context": "",
                "directory": "/tmp/test",
                "jwt_token": "",
                "auto_approve": False,
            }
            resp = client.post("/session", json=body, headers=_headers())
            data = resp.json()

        assert data.get("status") == "created", f"Status esperado 'created', got: {data}"

    def test_post_session_sin_secret_retorna_401(self, monkeypatch):
        """POST /session sin X-OVD-Secret retorna 401 cuando el engine tiene secret configurado."""
        # OVD_SECRET se lee al importar el módulo — hay que parchear la variable directamente
        monkeypatch.setattr(_api_module, "OVD_SECRET", _OVD_SECRET)

        client = TestClient(app)
        body = {
            "session_id": _SESSION_ID,
            "org_id": _ORG_ID,
            "project_id": _PROJECT_ID,
            "feature_request": "Agregar login",
            "project_context": "",
            "directory": "/tmp/test",
            "jwt_token": "",
            "auto_approve": False,
        }
        resp = client.post("/session", json=body)
        assert resp.status_code == 401

    def test_post_session_resume_si_thread_existe(self, monkeypatch):
        """POST /session con parent_thread_id existente retorna status='resumed'."""
        monkeypatch.setenv("OVD_SECRET", _OVD_SECRET)
        existing = MagicMock()  # simula checkpoint existente
        monkeypatch.setattr(_api_module, "_checkpointer", _make_checkpointer_mock(existing))

        ctx = _make_agent_context()
        with patch("api.ContextResolver.resolve_async", new=AsyncMock(return_value=ctx)), \
             patch("api.rag_seed.retrieve_context", return_value=""), \
             patch("api._graph", MagicMock()):

            client = TestClient(app)
            body = {
                "session_id": _SESSION_ID,
                "org_id": _ORG_ID,
                "project_id": _PROJECT_ID,
                "feature_request": "Agregar login",
                "project_context": "",
                "directory": "/tmp/test",
                "jwt_token": "",
                "auto_approve": False,
                "parent_thread_id": _THREAD_ID,
            }
            resp = client.post("/session", json=body, headers=_headers())
            data = resp.json()

        assert data.get("status") == "resumed", f"Esperado 'resumed', got: {data}"
        assert data.get("thread_id") == _THREAD_ID

    def test_post_session_invoca_context_resolver(self, monkeypatch):
        """POST /session llama a ContextResolver.resolve_async con org_id y project_id."""
        self._patch_env(monkeypatch)
        ctx = _make_agent_context()
        resolver_mock = AsyncMock(return_value=ctx)

        with patch("api.ContextResolver.resolve_async", new=resolver_mock), \
             patch("api.rag_seed.retrieve_context", return_value=""), \
             patch("api.AuditLogger.session_created", new=AsyncMock()), \
             patch("api.AuditLogger.secret_accessed", new=AsyncMock()):

            client = TestClient(app)
            body = {
                "session_id": _SESSION_ID,
                "org_id": _ORG_ID,
                "project_id": _PROJECT_ID,
                "feature_request": "Agregar login",
                "project_context": "",
                "directory": "/tmp/test",
                "jwt_token": "",
                "auto_approve": False,
            }
            client.post("/session", json=body, headers=_headers())

        resolver_mock.assert_called_once()
        call_kwargs = resolver_mock.call_args.kwargs
        assert call_kwargs.get("org_id") == _ORG_ID
        assert call_kwargs.get("project_id") == _PROJECT_ID


# ---------------------------------------------------------------------------
# E-04 — GET /session/{id}/delivery
# ---------------------------------------------------------------------------

class TestE04GetDelivery:
    """
    E-04: Verificar que GET /session/{id}/delivery retorna artefactos correctamente.
    Cubre: estructura de respuesta, scores de seguridad y QA, y control de acceso.
    """

    def _make_full_state(self, org_id: str = _ORG_ID) -> dict:
        return {
            "org_id":    org_id,
            "status":    "done",
            "directory": "/tmp/test-repo",
            "deliverables": [
                {"type": "sdd",            "agent": "architect", "content": "# SDD"},
                {"type": "implementation", "agent": "backend",   "content": "def login(): pass"},
            ],
            "security_result": {
                "passed":   True,
                "score":    90,
                "severity": "none",
            },
            "qa_result": {
                "passed":         True,
                "score":          85,
                "sdd_compliance": 92,
                "issues":         [],
            },
            "token_usage": {
                "backend": {"input": 500, "output": 300},
            },
            "cycle_start_ts": time.time() - 10.0,
        }

    def test_delivery_retorna_200(self, monkeypatch):
        """GET /session/{id}/delivery con thread válido retorna 200."""
        monkeypatch.setenv("OVD_SECRET", _OVD_SECRET)
        graph = _make_graph_mock(self._make_full_state())
        monkeypatch.setattr(_api_module, "_graph", graph)

        client = TestClient(app)
        resp = client.get(
            f"/session/{_THREAD_ID}/delivery",
            params={"org_id": _ORG_ID},
            headers=_headers(),
        )
        assert resp.status_code == 200, f"Esperado 200, got {resp.status_code}: {resp.text}"

    def test_delivery_incluye_entregables(self, monkeypatch):
        """La respuesta incluye la lista de deliverables del ciclo."""
        monkeypatch.setenv("OVD_SECRET", _OVD_SECRET)
        graph = _make_graph_mock(self._make_full_state())
        monkeypatch.setattr(_api_module, "_graph", graph)

        client = TestClient(app)
        resp = client.get(
            f"/session/{_THREAD_ID}/delivery",
            params={"org_id": _ORG_ID},
            headers=_headers(),
        )
        data = resp.json()

        assert "deliverables" in data
        assert len(data["deliverables"]) == 2
        types = [d["type"] for d in data["deliverables"]]
        assert "sdd" in types
        assert "implementation" in types

    def test_delivery_incluye_scores_seguridad_y_qa(self, monkeypatch):
        """La respuesta incluye scores de security y QA."""
        monkeypatch.setenv("OVD_SECRET", _OVD_SECRET)
        graph = _make_graph_mock(self._make_full_state())
        monkeypatch.setattr(_api_module, "_graph", graph)

        client = TestClient(app)
        resp = client.get(
            f"/session/{_THREAD_ID}/delivery",
            params={"org_id": _ORG_ID},
            headers=_headers(),
        )
        data = resp.json()

        assert data["security"]["score"] == 90
        assert data["security"]["passed"] is True
        assert data["qa"]["score"] == 85
        assert data["qa"]["sdd_compliance"] == 92

    def test_delivery_incluye_tokens_y_elapsed(self, monkeypatch):
        """La respuesta incluye métricas de tokens y tiempo transcurrido."""
        monkeypatch.setenv("OVD_SECRET", _OVD_SECRET)
        graph = _make_graph_mock(self._make_full_state())
        monkeypatch.setattr(_api_module, "_graph", graph)

        client = TestClient(app)
        resp = client.get(
            f"/session/{_THREAD_ID}/delivery",
            params={"org_id": _ORG_ID},
            headers=_headers(),
        )
        data = resp.json()

        assert data["tokens_in"] == 500
        assert data["tokens_out"] == 300
        assert data["elapsed_secs"] > 0

    def test_delivery_retorna_404_si_thread_no_existe(self, monkeypatch):
        """GET /session/{id}/delivery retorna 404 si el thread no existe."""
        monkeypatch.setenv("OVD_SECRET", _OVD_SECRET)
        # aget_state retorna None (thread inexistente)
        graph = _make_graph_mock(None)
        monkeypatch.setattr(_api_module, "_graph", graph)

        client = TestClient(app)
        resp = client.get(
            "/session/thread-inexistente/delivery",
            params={"org_id": _ORG_ID},
            headers=_headers(),
        )
        assert resp.status_code == 404

    def test_delivery_retorna_403_si_org_no_coincide(self, monkeypatch):
        """GET /session/{id}/delivery retorna 403 si el org_id del token no coincide."""
        monkeypatch.setenv("OVD_SECRET", _OVD_SECRET)
        # El thread pertenece a ORG-A, pero el caller dice ORG-B
        graph = _make_graph_mock(self._make_full_state(org_id="org-A"))
        monkeypatch.setattr(_api_module, "_graph", graph)

        client = TestClient(app)
        resp = client.get(
            f"/session/{_THREAD_ID}/delivery",
            params={"org_id": "org-B"},
            headers=_headers(),
        )
        assert resp.status_code == 403

    def test_delivery_sin_secret_retorna_401(self, monkeypatch):
        """GET /session/{id}/delivery sin X-OVD-Secret retorna 401 cuando secret está configurado."""
        monkeypatch.setattr(_api_module, "OVD_SECRET", _OVD_SECRET)
        graph = _make_graph_mock(self._make_full_state())
        monkeypatch.setattr(_api_module, "_graph", graph)

        client = TestClient(app)
        resp = client.get(
            f"/session/{_THREAD_ID}/delivery",
            params={"org_id": _ORG_ID},
        )
        assert resp.status_code == 401

    def test_delivery_retorna_503_si_graph_no_inicializado(self, monkeypatch):
        """GET /session/{id}/delivery retorna 503 si el engine no está inicializado."""
        monkeypatch.setenv("OVD_SECRET", _OVD_SECRET)
        monkeypatch.setattr(_api_module, "_graph", None)

        client = TestClient(app)
        resp = client.get(
            f"/session/{_THREAD_ID}/delivery",
            params={"org_id": _ORG_ID},
            headers=_headers(),
        )
        assert resp.status_code == 503
