"""
OVD Platform — Fixtures globales de regresión
Disponibles automáticamente en todos los tests sin importar explícito.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager

# ─── JWT ────────────────────────────────────────────────────────────────────

TEST_JWT_SECRET = "a" * 64   # 64 chars, cumple mínimo 32

@pytest.fixture(autouse=True)
def set_jwt_secret(monkeypatch):
    """Inyecta JWT_SECRET en todos los tests para evitar RuntimeError."""
    import auth
    monkeypatch.setattr(auth, "_JWT_SECRET", TEST_JWT_SECRET)

# ─── Telemetría NO-OP ────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_telemetry(monkeypatch):
    """
    Reemplaza node_span y cycle_span con context managers no-op.
    Evita inicializar OTEL en unit tests.
    """
    import telemetry

    fake_span = MagicMock()
    fake_span.set_attribute = MagicMock()
    fake_span.set_attributes = MagicMock()
    fake_span.set_status = MagicMock()

    @asynccontextmanager
    async def _fake_node_span(name, state):
        yield fake_span

    from contextlib import contextmanager

    @contextmanager
    def _fake_cycle_span(**kwargs):
        yield fake_span

    monkeypatch.setattr(telemetry, "node_span", _fake_node_span)
    monkeypatch.setattr(telemetry, "cycle_span", _fake_cycle_span)
    monkeypatch.setattr(telemetry, "get_trace_id", lambda span: "0" * 32)
    monkeypatch.setattr(telemetry, "record_token_usage", MagicMock())
    monkeypatch.setattr(telemetry, "record_qa_result", MagicMock())
    monkeypatch.setattr(telemetry, "record_security_result", MagicMock())

# ─── NATS NO-OP ──────────────────────────────────────────────────────────────
# NO autouse — solo para tests que no prueban nats_client directamente.
# Solicitar explícitamente con @pytest.mark.usefixtures("mock_nats") o como parámetro.

@pytest.fixture()
def mock_nats(monkeypatch):
    """Reemplaza todas las publicaciones NATS con AsyncMock no-op."""
    import nats_client
    monkeypatch.setattr(nats_client, "publish_started",  AsyncMock())
    monkeypatch.setattr(nats_client, "publish_done",     AsyncMock())
    monkeypatch.setattr(nats_client, "publish_approved", AsyncMock())
    monkeypatch.setattr(nats_client, "close",            AsyncMock())

# ─── AuditLogger NO-OP ───────────────────────────────────────────────────────
# NO autouse — solo para tests que no prueban audit_logger directamente.

@pytest.fixture()
def mock_audit_logger(monkeypatch):
    """Reemplaza AuditLogger para que no intente conectar a BD."""
    import audit_logger
    monkeypatch.setattr(audit_logger.AuditLogger, "log",              AsyncMock())
    monkeypatch.setattr(audit_logger.AuditLogger, "session_created",  AsyncMock())
    monkeypatch.setattr(audit_logger.AuditLogger, "cycle_completed",  AsyncMock())
    monkeypatch.setattr(audit_logger.AuditLogger, "secret_accessed",  AsyncMock())

# ─── LLM mock reutilizable ───────────────────────────────────────────────────

def make_llm_mock(return_value):
    """
    Crea un mock de LLM compatible con invoke_structured().
    `return_value` debe ser una instancia del Pydantic model que el nodo espera.

    Uso:
        llm = make_llm_mock(FRAnalysisOutput(fr_type="feature", ...))
    """
    structured = MagicMock()
    structured.ainvoke = AsyncMock(return_value=return_value)
    llm = MagicMock()
    llm.with_structured_output = MagicMock(return_value=structured)
    return llm
