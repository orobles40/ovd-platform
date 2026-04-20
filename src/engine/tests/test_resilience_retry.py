"""
S20 — GAP-R2, GAP-R6: Tests de invoke_structured con backoff exponencial y MAX_RETRIES configurable.
"""
from __future__ import annotations
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import BaseModel


class _DummyOutput(BaseModel):
    value: str = "ok"


@pytest.fixture
def dummy_llm():
    """LLM mock con with_structured_output."""
    llm = MagicMock()
    structured = MagicMock()
    llm.with_structured_output.return_value = structured
    return llm, structured


# ---------------------------------------------------------------------------
# Importar invoke_structured con env vars limpias
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invoke_structured_succeeds_on_first_attempt(dummy_llm):
    """Camino feliz: retorna resultado en el primer intento."""
    from graph import invoke_structured
    llm, structured = dummy_llm
    structured.ainvoke = AsyncMock(return_value=_DummyOutput(value="resultado"))

    result = await invoke_structured(llm, [MagicMock()], _DummyOutput)
    assert result.value == "resultado"
    assert structured.ainvoke.call_count == 1


@pytest.mark.asyncio
async def test_invoke_structured_retries_after_failure(dummy_llm):
    """Reintenta tras fallo y triunfa en el segundo intento."""
    from graph import invoke_structured
    llm, structured = dummy_llm
    structured.ainvoke = AsyncMock(
        side_effect=[ValueError("parse error"), _DummyOutput(value="ok")]
    )

    with patch("graph.wait_exponential", return_value=MagicMock(sleep=AsyncMock())):
        result = await invoke_structured(llm, [MagicMock()], _DummyOutput, max_retries=2)

    assert result.value == "ok"
    assert structured.ainvoke.call_count == 2


@pytest.mark.asyncio
async def test_invoke_structured_raises_after_all_retries_exhausted(dummy_llm):
    """Propaga la excepción cuando se agotan todos los intentos."""
    from graph import invoke_structured
    llm, structured = dummy_llm
    structured.ainvoke = AsyncMock(side_effect=ValueError("siempre falla"))

    with pytest.raises(ValueError, match="siempre falla"):
        await invoke_structured(llm, [MagicMock()], _DummyOutput, max_retries=1)

    assert structured.ainvoke.call_count == 2  # 1 original + 1 retry


@pytest.mark.asyncio
async def test_max_retries_reads_from_env():
    """MAX_RETRIES se lee de OVD_MAX_RETRIES."""
    import importlib
    with patch.dict(os.environ, {"OVD_MAX_RETRIES": "7"}):
        import graph as g
        importlib.reload(g)
        assert g.MAX_RETRIES == 7
        assert g._INVOKE_MAX_RETRIES == 7
    # Restaurar
    importlib.reload(g)
