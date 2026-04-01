"""
OVD Platform — Tests unitarios: NATS Client (Sprint 7)
Copyright 2026 Omar Robles

Verifica el comportamiento del cliente NATS:
  N7.1 — publish es no-op cuando NATS_URL no está configurada
  N7.2 — publish no propaga excepciones (fire-and-forget)
  N7.3 — _base_payload extrae los campos correctos del state
  N7.4 — publish_started incluye fr_analysis
  N7.5 — publish_approved incluye sdd_summary, counts y approval_comment
  N7.6 — publish_done trunca agent output > 8192 chars
  N7.7 — publish_done incluye todos los campos del ciclo
  N7.8 — publish_escalated incluye reason y retry counts
  N7.9 — close es seguro si la conexión nunca fue abierta
  N7.10 — _get_connection retorna None sin NATS_URL
"""
import sys
import os
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import nats_client


# ---------------------------------------------------------------------------
# Estado de prueba base
# ---------------------------------------------------------------------------

def _make_state(**overrides) -> dict:
    base = {
        "session_id":       "sess-abc123",
        "org_id":           "org-test",
        "project_id":       "proj-001",
        "feature_request":  "Agregar autenticación OAuth2",
        "fr_analysis":      {"type": "feature", "complexity": "medium"},
        "sdd": {
            "summary":      "Implementar OAuth2 con PKCE",
            "requirements": ["req1", "req2", "req3"],
            "tasks":        ["task1", "task2"],
        },
        "approval_comment": "Aprobado sin observaciones",
        "agent_results": [
            {"agent": "backend",  "output": "def auth(): pass", "tokens": {"input": 100, "output": 50}},
            {"agent": "frontend", "output": "export default Login", "tokens": {"input": 80, "output": 40}},
        ],
        "security_result":        {"passed": True, "score": 88, "vulnerabilities": []},
        "qa_result":              {"passed": True, "score": 91, "issues": []},
        "token_usage": {
            "backend":  {"input": 100, "output": 50},
            "frontend": {"input": 80, "output": 40},
        },
        "github_pr":              {"ok": True, "pr_url": "https://github.com/org/repo/pull/42"},
        "security_retry_count":   0,
        "qa_retry_count":         1,
        "escalation_resolution":  "Resuelto por arquitecto",
    }
    base.update(overrides)
    return base


def run(coro):
    """Ejecuta una coroutine en un nuevo event loop (compatible Python 3.14)."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# N7.1 — publish es no-op sin NATS_URL
# ---------------------------------------------------------------------------

class TestPublishNoOp:
    def test_publish_noop_sin_nats_url(self):
        """Sin NATS_URL configurada, publish no hace nada y no lanza excepción."""
        original = nats_client.NATS_URL
        nats_client.NATS_URL = ""
        try:
            run(nats_client.publish("ovd.org.session.started", {"key": "value"}))
        finally:
            nats_client.NATS_URL = original

    def test_is_enabled_false_sin_nats_url(self):
        original = nats_client.NATS_URL
        nats_client.NATS_URL = ""
        try:
            assert nats_client._is_enabled() is False
        finally:
            nats_client.NATS_URL = original

    def test_is_enabled_true_con_nats_url(self):
        original = nats_client.NATS_URL
        nats_client.NATS_URL = "nats://localhost:4222"
        try:
            assert nats_client._is_enabled() is True
        finally:
            nats_client.NATS_URL = original


# ---------------------------------------------------------------------------
# N7.2 — fire-and-forget: errores no propagan
# ---------------------------------------------------------------------------

class TestFireAndForget:
    def test_publish_no_propaga_excepcion_de_conexion(self):
        """Si _get_connection lanza, publish lo captura y no propaga."""
        original = nats_client.NATS_URL
        nats_client.NATS_URL = "nats://localhost:4222"
        try:
            async def _run():
                with patch.object(nats_client, "_get_connection", side_effect=RuntimeError("conn refused")):
                    await nats_client.publish("ovd.org.session.started", {"k": "v"})
            run(_run())
        finally:
            nats_client.NATS_URL = original

    def test_publish_no_propaga_excepcion_de_publish_nc(self):
        """Si nc.publish lanza, publish captura y no propaga."""
        original = nats_client.NATS_URL
        nats_client.NATS_URL = "nats://localhost:4222"
        try:
            async def _run():
                mock_nc = AsyncMock()
                mock_nc.is_connected = True
                mock_nc.publish = AsyncMock(side_effect=IOError("broken pipe"))
                with patch.object(nats_client, "_get_connection", return_value=mock_nc):
                    await nats_client.publish("ovd.org.session.started", {"k": "v"})
            run(_run())
        finally:
            nats_client.NATS_URL = original


# ---------------------------------------------------------------------------
# N7.3 — _base_payload
# ---------------------------------------------------------------------------

class TestBasePayload:
    def test_extrae_campos_correctos(self):
        state = _make_state()
        payload = nats_client._base_payload(state)
        assert payload["session_id"]      == "sess-abc123"
        assert payload["org_id"]          == "org-test"
        assert payload["project_id"]      == "proj-001"
        assert payload["feature_request"] == "Agregar autenticación OAuth2"

    def test_defaults_para_campos_ausentes(self):
        payload = nats_client._base_payload({})
        assert payload["session_id"]      == ""
        assert payload["org_id"]          == ""
        assert payload["project_id"]      == ""
        assert payload["feature_request"] == ""


# ---------------------------------------------------------------------------
# N7.4 — publish_started
# ---------------------------------------------------------------------------

class TestPublishStarted:
    def test_payload_incluye_fr_analysis(self):
        """publish_started debe publicar en el subject correcto e incluir fr_analysis."""
        state = _make_state()
        captured = {}

        async def _run():
            async def fake_publish(subject, payload):
                captured["subject"] = subject
                captured["payload"] = payload
            with patch.object(nats_client, "publish", side_effect=fake_publish):
                await nats_client.publish_started(state)

        run(_run())

        assert captured["subject"] == "ovd.org-test.session.started"
        assert captured["payload"]["fr_analysis"] == {"type": "feature", "complexity": "medium"}
        assert captured["payload"]["session_id"] == "sess-abc123"

    def test_subject_usa_org_id_del_state(self):
        state = _make_state(org_id="acme-corp")
        captured = {}

        async def _run():
            async def fake_publish(subject, payload):
                captured["subject"] = subject
            with patch.object(nats_client, "publish", side_effect=fake_publish):
                await nats_client.publish_started(state)

        run(_run())
        assert captured["subject"] == "ovd.acme-corp.session.started"


# ---------------------------------------------------------------------------
# N7.5 — publish_approved
# ---------------------------------------------------------------------------

class TestPublishApproved:
    def test_payload_incluye_sdd_fields(self):
        state = _make_state()
        captured = {}

        async def _run():
            async def fake_publish(subject, payload):
                captured["subject"] = subject
                captured["payload"] = payload
            with patch.object(nats_client, "publish", side_effect=fake_publish):
                await nats_client.publish_approved(state)

        run(_run())

        assert captured["subject"] == "ovd.org-test.session.approved"
        p = captured["payload"]
        assert p["sdd_summary"]        == "Implementar OAuth2 con PKCE"
        assert p["requirements_count"] == 3
        assert p["tasks_count"]        == 2
        assert p["approval_comment"]   == "Aprobado sin observaciones"


# ---------------------------------------------------------------------------
# N7.6 — publish_done: truncado de agent output
# ---------------------------------------------------------------------------

class TestPublishDoneTruncation:
    def test_output_mayor_8192_se_trunca(self):
        long_output = "x" * 10_000
        state = _make_state(agent_results=[
            {"agent": "backend", "output": long_output, "tokens": {"input": 10, "output": 5}},
        ])
        captured = {}

        async def _run():
            async def fake_publish(subject, payload):
                captured["payload"] = payload
            with patch.object(nats_client, "publish", side_effect=fake_publish):
                await nats_client.publish_done(state, 120.0, 0.05)

        run(_run())

        result_output = captured["payload"]["agent_results"][0]["output"]
        assert len(result_output) <= 8192 + len("\n... [truncado]")
        assert result_output.endswith("... [truncado]")

    def test_output_menor_8192_no_se_trunca(self):
        short_output = "def foo(): pass"
        state = _make_state(agent_results=[
            {"agent": "backend", "output": short_output, "tokens": {"input": 10, "output": 5}},
        ])
        captured = {}

        async def _run():
            async def fake_publish(subject, payload):
                captured["payload"] = payload
            with patch.object(nats_client, "publish", side_effect=fake_publish):
                await nats_client.publish_done(state, 60.0, 0.01)

        run(_run())

        result_output = captured["payload"]["agent_results"][0]["output"]
        assert result_output == short_output
        assert "truncado" not in result_output


# ---------------------------------------------------------------------------
# N7.7 — publish_done: campos del ciclo
# ---------------------------------------------------------------------------

class TestPublishDoneFields:
    def test_payload_incluye_todos_los_campos(self):
        state = _make_state()
        captured = {}

        async def _run():
            async def fake_publish(subject, payload):
                captured["subject"] = subject
                captured["payload"] = payload
            with patch.object(nats_client, "publish", side_effect=fake_publish):
                await nats_client.publish_done(state, 329.5, 0.0234)

        run(_run())

        assert captured["subject"] == "ovd.org-test.session.done"
        p = captured["payload"]

        # SDD completo para indexar en RAG
        assert p["sdd"]["summary"] == "Implementar OAuth2 con PKCE"
        # Resultados de calidad
        assert p["security_result"]["score"] == 88
        assert p["qa_result"]["score"]       == 91
        # Métricas
        assert p["duration_secs"]  == 329.5
        assert p["cost_usd"]       == 0.0234
        # Tokens agregados (100+80=180 in, 50+40=90 out)
        assert p["token_usage"]["total_input"]  == 180
        assert p["token_usage"]["total_output"] == 90
        # GitHub PR
        assert p["github_pr"]["ok"] is True


# ---------------------------------------------------------------------------
# N7.8 — publish_escalated
# ---------------------------------------------------------------------------

class TestPublishEscalated:
    def test_payload_incluye_reason_y_retry_counts(self):
        state = _make_state()
        captured = {}

        async def _run():
            async def fake_publish(subject, payload):
                captured["subject"] = subject
                captured["payload"] = payload
            with patch.object(nats_client, "publish", side_effect=fake_publish):
                await nats_client.publish_escalated(state, "Max reintentos alcanzado")

        run(_run())

        assert captured["subject"] == "ovd.org-test.session.escalated"
        p = captured["payload"]
        assert p["reason"]               == "Max reintentos alcanzado"
        assert p["security_retry_count"] == 0
        assert p["qa_retry_count"]       == 1
        assert p["escalation_resolution"] == "Resuelto por arquitecto"


# ---------------------------------------------------------------------------
# N7.9 — close es seguro sin conexión abierta
# ---------------------------------------------------------------------------

class TestClose:
    def test_close_sin_conexion_no_lanza(self):
        """close() no debe lanzar si _nc es None."""
        original = nats_client._nc
        nats_client._nc = None
        try:
            run(nats_client.close())
        finally:
            nats_client._nc = original

    def test_close_llama_nc_close_y_limpia(self):
        """close() llama a nc.close() y pone _nc = None."""
        mock_nc = AsyncMock()
        mock_nc.close = AsyncMock()

        original = nats_client._nc
        nats_client._nc = mock_nc
        try:
            run(nats_client.close())
            mock_nc.close.assert_called_once()
            assert nats_client._nc is None
        finally:
            nats_client._nc = original


# ---------------------------------------------------------------------------
# N7.10 — _get_connection retorna None sin NATS_URL
# ---------------------------------------------------------------------------

class TestGetConnection:
    def test_get_connection_retorna_none_sin_url(self):
        original = nats_client.NATS_URL
        nats_client.NATS_URL = ""
        try:
            result = run(nats_client._get_connection())
            assert result is None
        finally:
            nats_client.NATS_URL = original

    def test_get_connection_retorna_existente_si_conectado(self):
        """Si _nc ya está conectado, retorna el mismo objeto sin reconectar."""
        mock_nc = MagicMock()
        mock_nc.is_connected = True

        original_url = nats_client.NATS_URL
        original_nc  = nats_client._nc
        nats_client.NATS_URL = "nats://localhost:4222"
        nats_client._nc = mock_nc
        try:
            result = run(nats_client._get_connection())
            assert result is mock_nc
        finally:
            nats_client.NATS_URL = original_url
            nats_client._nc = original_nc
