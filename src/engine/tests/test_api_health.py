"""
OVD Platform — Tests para GET /health (api.py)
Unit tests sin BD real ni LLM real.
El lifespan del app se mockea para evitar conexiones a NATS/checkpointer.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, AsyncMock
from contextlib import asynccontextmanager


# Mockear el lifespan para que no intente conectar a nada
@asynccontextmanager
async def mock_lifespan(app):
    yield


with patch("api.lifespan", mock_lifespan):
    from api import app

from fastapi.testclient import TestClient

client = TestClient(app)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHealthEndpoint:

    def test_health_retorna_200(self):
        """GET /health debe responder con HTTP 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_retorna_json_correcto(self):
        """El body de /health debe contener status=ok y engine=ovd-engine."""
        response = client.get("/health")
        data = response.json()
        assert data.get("status") == "ok"
        assert data.get("engine") == "ovd-engine"

    def test_health_no_requiere_auth(self):
        """
        El endpoint /health no debe requerir cabecera X-OVD-Secret.
        Una request sin autenticación debe retornar 200 OK.
        """
        response = client.get("/health", headers={})
        assert response.status_code == 200

    def test_health_content_type_es_json(self):
        """La respuesta de /health debe ser application/json."""
        response = client.get("/health")
        assert "application/json" in response.headers.get("content-type", "")

    def test_health_responde_con_get(self):
        """Verifica que GET es el método correcto para /health."""
        response = client.get("/health")
        # No debe ser 405 Method Not Allowed
        assert response.status_code != 405
