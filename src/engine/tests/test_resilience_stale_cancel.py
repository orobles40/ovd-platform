"""
S20 — GAP-R3: Tests de cancelación de sesiones stale.
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(autouse=True)
def clean_state():
    """Limpia el estado compartido entre tests."""
    import task_checkout as tc
    tc._active_sessions.clear()
    tc._stale_sessions.clear()
    tc._running_tasks.clear()
    yield
    tc._active_sessions.clear()
    tc._stale_sessions.clear()
    tc._running_tasks.clear()


def _register_old_session(thread_id: str, minutes_ago: int = 35):
    """Helper: registra una sesión con timestamp antiguo."""
    import task_checkout as tc
    past = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    tc._active_sessions[thread_id] = {
        "org_id": "org1",
        "feature_request": "test FR",
        "started_at": past.isoformat(),
    }


@pytest.mark.asyncio
async def test_stale_detection_cancels_task():
    """cancel_stale_sessions cancela la asyncio.Task asociada al thread_id stale."""
    import task_checkout as tc

    thread_id = "thread-stale-1"
    _register_old_session(thread_id)

    mock_task = MagicMock(spec=asyncio.Task)
    mock_task.done.return_value = False
    tc._running_tasks[thread_id] = mock_task

    cancelled = await tc.cancel_stale_sessions(threshold_minutes=30)

    assert thread_id in cancelled
    mock_task.cancel.assert_called_once()


@pytest.mark.asyncio
async def test_stale_unregisters_session():
    """cancel_stale_sessions elimina la sesión de _active_sessions."""
    import task_checkout as tc

    thread_id = "thread-stale-2"
    _register_old_session(thread_id)

    await tc.cancel_stale_sessions(threshold_minutes=30)

    assert thread_id not in tc._active_sessions
    assert thread_id not in tc._running_tasks


@pytest.mark.asyncio
async def test_stale_publishes_nats_event():
    """cancel_stale_sessions invoca nats_publish_fn con session.timeout."""
    import task_checkout as tc

    thread_id = "thread-stale-3"
    _register_old_session(thread_id)

    mock_publish = AsyncMock()
    await tc.cancel_stale_sessions(threshold_minutes=30, nats_publish_fn=mock_publish)

    mock_publish.assert_called_once()
    subject, payload = mock_publish.call_args[0]
    assert "session.timeout" in subject
    assert payload["thread_id"] == thread_id
    assert payload["reason"] == "stale_session_cancelled"


@pytest.mark.asyncio
async def test_cancel_is_graceful_on_missing_task():
    """cancel_stale_sessions no lanza si no hay tarea registrada para el thread_id."""
    import task_checkout as tc

    thread_id = "thread-stale-4"
    _register_old_session(thread_id)
    # No registramos tarea — simula sesión sin task asociada

    cancelled = await tc.cancel_stale_sessions(threshold_minutes=30)

    # Debe completar sin error y sin cancelados (no había tarea)
    assert thread_id not in cancelled
    assert thread_id not in tc._active_sessions
