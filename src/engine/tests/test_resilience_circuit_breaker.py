"""
S20 — GAP-R4, GAP-R8: Tests del circuit breaker por provider y retry en _fetch_resolved.
"""
from __future__ import annotations
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx


# ---------------------------------------------------------------------------
# Tests del CircuitBreaker
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_circuit_breaker():
    """Limpia el estado del circuit breaker entre tests."""
    from model_router import _cb
    _cb.reset()
    yield
    _cb.reset()


def test_circuit_opens_after_n_failures():
    """El circuito se abre tras N fallos consecutivos."""
    from model_router import _cb, CircuitOpenError
    _cb._threshold = 3

    assert not _cb.is_open("ollama")
    _cb.record_failure("ollama")
    _cb.record_failure("ollama")
    assert not _cb.is_open("ollama")  # aún no llega al umbral
    _cb.record_failure("ollama")
    assert _cb.is_open("ollama")      # umbral alcanzado


def test_circuit_closes_on_success():
    """El circuito vuelve a closed tras un éxito."""
    from model_router import _cb
    _cb._threshold = 2

    _cb.record_failure("claude")
    _cb.record_failure("claude")
    assert _cb.is_open("claude")

    _cb.record_success("claude")
    assert not _cb.is_open("claude")


def test_circuit_half_open_after_recovery():
    """Tras recovery_secs, el circuito permite una llamada de prueba (half-open)."""
    import time
    from model_router import _cb

    _cb._threshold = 1
    _cb._recovery = 0.05  # 50ms para test
    _cb.record_failure("openai")
    assert _cb.is_open("openai")

    # Avanzar el tiempo simulado
    _cb._open_since["openai"] -= 0.1  # forzar expiración
    assert not _cb.is_open("openai")  # half-open: permite prueba


def test_build_llm_raises_circuit_open_error():
    """build_llm lanza CircuitOpenError cuando el circuito está abierto."""
    from model_router import _cb, build_llm, CircuitOpenError, ResolvedConfig
    _cb._threshold = 1
    _cb.record_failure("ollama")

    config = ResolvedConfig(
        provider="ollama", model="qwen3-coder-next",
        base_url=None, api_key_env=None, extra_instructions=None,
        constraints=None, code_style=None, resolved_from="default",
    )
    with pytest.raises(CircuitOpenError):
        build_llm(config)


# ---------------------------------------------------------------------------
# Tests del retry en _fetch_resolved
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_resolved_retries_before_defaults():
    """_fetch_resolved reintenta si el Bridge falla la primera vez."""
    from model_router import _fetch_resolved

    call_count = 0

    async def _mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise httpx.ConnectError("connection refused")
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json.return_value = {
            "resolved": {
                "backend": {"provider": "ollama", "model": "qwen3-coder-next", "resolvedFrom": "project"}
            }
        }
        return mock_resp

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = _mock_get
        mock_client_cls.return_value = mock_client

        result = await _fetch_resolved("org1", "proj1", "backend", "token")

    assert result is not None
    assert result.model == "qwen3-coder-next"
    assert call_count == 2


@pytest.mark.asyncio
async def test_fetch_resolved_returns_none_after_all_retries():
    """_fetch_resolved retorna None (cae a defaults) tras agotar todos los reintentos."""
    from model_router import _fetch_resolved

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("always fails"))
        mock_client_cls.return_value = mock_client

        result = await _fetch_resolved("org1", "proj1", "backend", "token")

    assert result is None
