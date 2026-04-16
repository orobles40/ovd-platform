"""
PP-03 — Tests unitarios para task_checkout.py
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from task_checkout import _lock_key, AlreadyRunningError, SessionLock


# ---------------------------------------------------------------------------
# _lock_key
# ---------------------------------------------------------------------------

def test_lock_key_deterministic():
    """El mismo thread_id siempre produce el mismo key."""
    tid = "abc123-def456"
    assert _lock_key(tid) == _lock_key(tid)


def test_lock_key_range():
    """El key cae dentro del rango bigint positivo de PostgreSQL."""
    import uuid
    for _ in range(50):
        key = _lock_key(str(uuid.uuid4()))
        assert 0 <= key < 2**63


def test_lock_key_distinct():
    """Thread IDs distintos producen keys distintos (probabilístico)."""
    import uuid
    keys = {_lock_key(str(uuid.uuid4())) for _ in range(100)}
    assert len(keys) == 100


# ---------------------------------------------------------------------------
# SessionLock — sin DATABASE_URL (modo sin lock)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_db_url_passes_through():
    """Sin DATABASE_URL el lock no bloquea y no falla."""
    with patch("task_checkout._DATABASE_URL", ""):
        lock = SessionLock("thread-1")
        async with lock:
            pass  # debe ejecutarse sin error


# ---------------------------------------------------------------------------
# SessionLock — adquiere con éxito
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_acquire_success():
    """Cuando pg_try_advisory_lock retorna True, el lock se adquiere."""
    mock_conn = AsyncMock()
    mock_row  = AsyncMock()
    mock_row.fetchone = AsyncMock(return_value=(True,))
    mock_conn.execute = AsyncMock(return_value=mock_row)
    mock_conn.commit  = AsyncMock()
    mock_conn.close   = AsyncMock()

    with patch("task_checkout._DATABASE_URL", "postgresql://fake"), \
         patch("task_checkout.psycopg.AsyncConnection.connect", AsyncMock(return_value=mock_conn)):
        lock = SessionLock("thread-ok")
        async with lock:
            pass  # sin error

    # pg_advisory_unlock llamado al salir
    calls = [str(c) for c in mock_conn.execute.call_args_list]
    assert any("pg_advisory_unlock" in c for c in calls)


# ---------------------------------------------------------------------------
# SessionLock — ya ocupado
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_acquire_already_running():
    """Cuando pg_try_advisory_lock retorna False, levanta AlreadyRunningError."""
    mock_conn = AsyncMock()
    mock_row  = AsyncMock()
    mock_row.fetchone = AsyncMock(return_value=(False,))
    mock_conn.execute = AsyncMock(return_value=mock_row)
    mock_conn.close   = AsyncMock()

    with patch("task_checkout._DATABASE_URL", "postgresql://fake"), \
         patch("task_checkout.psycopg.AsyncConnection.connect", AsyncMock(return_value=mock_conn)):
        with pytest.raises(AlreadyRunningError):
            async with SessionLock("thread-busy"):
                pass


# ---------------------------------------------------------------------------
# SessionLock — unlock se llama aunque el bloque interno falle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unlock_on_exception():
    """pg_advisory_unlock se llama aunque el bloque interno lance excepción."""
    mock_conn = AsyncMock()
    mock_row  = AsyncMock()
    mock_row.fetchone = AsyncMock(return_value=(True,))
    mock_conn.execute = AsyncMock(return_value=mock_row)
    mock_conn.commit  = AsyncMock()
    mock_conn.close   = AsyncMock()

    with patch("task_checkout._DATABASE_URL", "postgresql://fake"), \
         patch("task_checkout.psycopg.AsyncConnection.connect", AsyncMock(return_value=mock_conn)):
        with pytest.raises(ValueError):
            async with SessionLock("thread-fail"):
                raise ValueError("fallo interno")

    calls = [str(c) for c in mock_conn.execute.call_args_list]
    assert any("pg_advisory_unlock" in c for c in calls)


# ---------------------------------------------------------------------------
# SessionLock — dos locks paralelos para el mismo thread
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_two_concurrent_same_thread():
    """
    Simula dos llamadas concurrentes al mismo thread:
    la primera adquiere, la segunda falla.
    """
    import asyncio

    call_count = 0

    async def fake_connect(*_, **__):
        nonlocal call_count
        call_count += 1
        mock_conn = AsyncMock()
        mock_row  = AsyncMock()
        # Primera llamada: lock disponible; segunda: no disponible
        mock_row.fetchone = AsyncMock(return_value=(call_count == 1,))
        mock_conn.execute = AsyncMock(return_value=mock_row)
        mock_conn.commit  = AsyncMock()
        mock_conn.close   = AsyncMock()
        return mock_conn

    results = []

    async def try_lock(tid):
        try:
            async with SessionLock(tid):
                results.append("acquired")
                await asyncio.sleep(0.01)
        except AlreadyRunningError:
            results.append("blocked")

    with patch("task_checkout._DATABASE_URL", "postgresql://fake"), \
         patch("task_checkout.psycopg.AsyncConnection.connect", fake_connect):
        await asyncio.gather(try_lock("thread-x"), try_lock("thread-x"))

    assert "acquired" in results
    assert "blocked" in results
