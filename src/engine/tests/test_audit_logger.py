"""
OVD Platform — Tests para audit_logger.py
Unit tests sin BD real.

Estrategia:
  - El conftest.py global mockea AuditLogger con autouse=True.
  - En estos tests se DESACTIVA ese mock para probar la lógica real del módulo.
  - Se mockea _write_audit_log (la capa de escritura a BD) con AsyncMock.
  - Se forza DATABASE_URL="" para probar el path de "sin BD".
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import logging
from unittest.mock import AsyncMock, patch, MagicMock

from audit_logger import AuditLogger, AUDIT_EVENTS


# ---------------------------------------------------------------------------
# TestAuditEvents — verificaciones básicas del conjunto de eventos
# ---------------------------------------------------------------------------

class TestAuditEvents:

    def test_audit_events_contiene_session_created(self):
        """AUDIT_EVENTS debe contener 'session_created'."""
        assert "session_created" in AUDIT_EVENTS

    def test_audit_events_contiene_cycle_completed(self):
        assert "cycle_completed" in AUDIT_EVENTS

    def test_audit_events_es_un_set_o_iterable(self):
        """AUDIT_EVENTS debe ser iterable (set, frozenset, o similar)."""
        assert hasattr(AUDIT_EVENTS, "__iter__")

    def test_audit_events_tiene_eventos_de_auth(self):
        """Deben existir eventos de autenticación."""
        assert "login" in AUDIT_EVENTS or "session_created" in AUDIT_EVENTS


# ---------------------------------------------------------------------------
# TestAuditLoggerDirecto — prueba la lógica real desactivando el mock del conftest
# ---------------------------------------------------------------------------

class TestAuditLoggerDirecto:
    # mock_audit_logger NO es autouse → los métodos reales están disponibles aquí.
    # Solo forzamos DATABASE_URL="" para aislar de BD real.

    @pytest.fixture(autouse=True)
    def force_empty_db_url(self, monkeypatch):
        """Fuerza DATABASE_URL="" para que log() retorne sin intentar conectar."""
        import audit_logger
        monkeypatch.setattr(audit_logger, "_DATABASE_URL", "")

    @pytest.mark.asyncio
    async def test_sin_database_url_no_lanza(self):
        """
        Cuando DATABASE_URL="" → AuditLogger.log() retorna None sin lanzar excepción.
        Solo loguea a nivel DEBUG.
        """
        # No debe lanzar excepción
        result = await AuditLogger.log(
            event="session_created",
            org_id="org-test",
            resource_type="session",
            summary="Test sin BD",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_sin_database_url_registra_debug(self, caplog):
        """Con DATABASE_URL="" debe aparecer un mensaje de debug en los logs."""
        with caplog.at_level(logging.DEBUG, logger="audit_logger"):
            await AuditLogger.log(
                event="cycle_completed",
                org_id="org-test",
                resource_type="cycle",
                summary="Test debug log",
            )
        debug_msgs = [r for r in caplog.records if r.levelno == logging.DEBUG]
        assert len(debug_msgs) > 0

    @pytest.mark.asyncio
    async def test_evento_desconocido_no_falla(self):
        """
        Un evento que no está en AUDIT_EVENTS → log warning pero no lanza excepción.
        Con DATABASE_URL="" retorna None inmediatamente antes de llegar al warning.
        """
        result = await AuditLogger.log(
            event="evento_que_no_existe_xyz",
            org_id="org-test",
            resource_type="test",
            summary="Evento desconocido",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_session_created_llama_log_con_evento_correcto(self, monkeypatch):
        """
        AuditLogger.session_created() debe llamar a AuditLogger.log con
        event='session_created'.
        """
        import audit_logger

        # Capturar la llamada a log con un AsyncMock
        captured_calls = []

        async def fake_log(event, org_id, resource_type, summary, **kwargs):
            captured_calls.append({
                "event": event,
                "org_id": org_id,
                "resource_type": resource_type,
                "summary": summary,
            })

        monkeypatch.setattr(audit_logger.AuditLogger, "log", fake_log)

        await AuditLogger.session_created(
            org_id="org-test-001",
            project_id="proj-test-001",
            session_id="sess-abc",
            thread_id="thread-xyz",
            feature_request="Agregar login con JWT",
        )

        assert len(captured_calls) == 1
        assert captured_calls[0]["event"] == "session_created"
        assert captured_calls[0]["org_id"] == "org-test-001"

    @pytest.mark.asyncio
    async def test_session_created_incluye_project_id_en_summary(self, monkeypatch):
        """El summary de session_created debe incluir el project_id."""
        import audit_logger

        summaries = []

        async def fake_log(event, org_id, resource_type, summary, **kwargs):
            summaries.append(summary)

        monkeypatch.setattr(audit_logger.AuditLogger, "log", fake_log)

        await AuditLogger.session_created(
            org_id="org1",
            project_id="mi-proyecto",
            session_id="sess-1",
            thread_id="thread-1",
            feature_request="Implementar búsqueda",
        )

        assert len(summaries) == 1
        assert "mi-proyecto" in summaries[0]

    @pytest.mark.asyncio
    async def test_write_audit_log_es_llamado_con_database_url(self, monkeypatch):
        """
        Cuando DATABASE_URL está configurado, _write_audit_log debe ser invocado.
        Mockear _write_audit_log con AsyncMock para verificar la llamada.
        """
        import audit_logger

        mock_write = AsyncMock()
        monkeypatch.setattr(audit_logger, "_DATABASE_URL", "postgresql://fake:5432/db")
        monkeypatch.setattr(audit_logger, "_write_audit_log", mock_write)

        await AuditLogger.log(
            event="session_created",
            org_id="org-test",
            resource_type="session",
            summary="Test con BD mockeada",
        )

        mock_write.assert_called_once()
        call_kwargs = mock_write.call_args
        # Verificar que el evento correcto fue pasado
        assert call_kwargs.kwargs.get("event") == "session_created" or \
               call_kwargs.args[0] == "session_created"

    @pytest.mark.asyncio
    async def test_error_en_write_no_propaga(self, monkeypatch):
        """
        Si _write_audit_log lanza excepción (fire-and-forget):
        AuditLogger.log NO debe propagar el error.
        """
        import audit_logger

        mock_write = AsyncMock(side_effect=Exception("Conexión rechazada"))
        monkeypatch.setattr(audit_logger, "_DATABASE_URL", "postgresql://fake:5432/db")
        monkeypatch.setattr(audit_logger, "_write_audit_log", mock_write)

        # No debe propagar la excepción
        result = await AuditLogger.log(
            event="cycle_completed",
            org_id="org-test",
            resource_type="cycle",
            summary="Test fire-and-forget",
        )
        assert result is None
