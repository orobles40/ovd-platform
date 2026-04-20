"""
S20 — GAP-R7: Tests de NATS retry y dead letter queue.
"""
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(autouse=True)
def reset_nats_connection():
    """Resetea la conexión NATS global entre tests."""
    import nats_client as nc
    original = nc._nc
    nc._nc = None
    yield
    nc._nc = original


@pytest.mark.asyncio
async def test_publish_retries_on_transient_failure():
    """publish reintenta si el primer intento falla pero el segundo tiene éxito."""
    import nats_client as nc

    call_count = 0

    async def _flaky_publish(subject, data):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise Exception("transient error")

    mock_conn = MagicMock()
    mock_conn.is_connected = True
    mock_conn.publish = _flaky_publish

    with (
        patch.dict("os.environ", {"NATS_URL": "nats://localhost:4222"}),
        patch.object(nc, "_nc", mock_conn),
        patch.object(nc, "_NATS_MAX_RETRIES", 2),
        patch.object(nc, "_get_connection", AsyncMock(return_value=mock_conn)),
        patch.object(nc, "_send_to_dlq", AsyncMock()),
    ):
        nc.NATS_URL = "nats://localhost:4222"
        await nc.publish("ovd.org1.session.done", {"test": True})

    assert call_count == 2


@pytest.mark.asyncio
async def test_publish_sends_to_dlq_after_retries_exhausted():
    """publish envía a DLQ cuando todos los reintentos fallan."""
    import nats_client as nc

    mock_conn = MagicMock()
    mock_conn.is_connected = True
    mock_conn.publish = AsyncMock(side_effect=Exception("always fails"))

    mock_dlq = AsyncMock()

    with (
        patch.object(nc, "_get_connection", AsyncMock(return_value=mock_conn)),
        patch.object(nc, "_send_to_dlq", mock_dlq),
        patch.object(nc, "NATS_URL", "nats://localhost:4222"),
    ):
        await nc.publish("ovd.org1.session.done", {"test": True})

    mock_dlq.assert_called_once()
    subject, payload, error = mock_dlq.call_args[0]
    assert subject == "ovd.org1.session.done"
    assert payload == {"test": True}
    assert "always fails" in error


@pytest.mark.asyncio
async def test_publish_remains_fire_and_forget():
    """publish no lanza excepción aunque DLQ también falle."""
    import nats_client as nc

    mock_conn = MagicMock()
    mock_conn.is_connected = True
    mock_conn.publish = AsyncMock(side_effect=Exception("nats down"))

    with (
        patch.object(nc, "_get_connection", AsyncMock(return_value=mock_conn)),
        patch.object(nc, "_send_to_dlq", AsyncMock(side_effect=Exception("dlq also down"))),
        patch.object(nc, "NATS_URL", "nats://localhost:4222"),
    ):
        # No debe lanzar excepción
        await nc.publish("ovd.org1.session.error", {"error": "test"})


@pytest.mark.asyncio
async def test_dlq_insert_failure_does_not_propagate():
    """_send_to_dlq loguea el error pero no propaga si el INSERT falla."""
    import nats_client as nc

    with patch("psycopg.AsyncConnection.connect", AsyncMock(side_effect=Exception("db down"))):
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://localhost/test"}):
            # No debe lanzar
            await nc._send_to_dlq("ovd.org1.test", {"x": 1}, "some error")
