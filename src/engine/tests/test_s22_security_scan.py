"""
S22 — Tests del security scanning CLI (_run_security_scans, _exec_scan_tool)
y su integración con security_audit.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.factories import make_state

# ---------------------------------------------------------------------------
# _exec_scan_tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exec_scan_tool_tool_not_installed():
    """Si el tool no existe, retorna string vacío sin propagar excepción."""
    import graph as g

    with patch(
        "asyncio.create_subprocess_exec", side_effect=FileNotFoundError("semgrep")
    ):
        result = await g._exec_scan_tool(["semgrep", "--version"])
    assert result == ""


@pytest.mark.asyncio
async def test_exec_scan_tool_captures_output():
    """Output del proceso es capturado correctamente."""
    import graph as g

    mock_proc = MagicMock()
    mock_proc.communicate = AsyncMock(return_value=(b"scan output ok", None))
    mock_proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with patch("asyncio.wait_for", return_value=(b"scan output ok", None)):
            result = await g._exec_scan_tool(["semgrep", "--version"])
    assert "scan output ok" in result


# ---------------------------------------------------------------------------
# _run_security_scans — comportamiento cuando herramientas no están instaladas
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_security_scans_missing_tools_returns_empty():
    """Con todas las tools ausentes, retorna dict vacío sin blocked=True."""
    import graph as g

    with patch.object(g, "_exec_scan_tool", new=AsyncMock(return_value="")):
        result = await g._run_security_scans([], "/tmp/nonexistent")

    assert result["blocked"] is False
    assert result["findings"] == []


@pytest.mark.asyncio
async def test_run_security_scans_gitleaks_secret_blocks():
    """Si gitleaks detecta un secreto, blocked=True."""
    import json

    import graph as g

    gitleaks_output = json.dumps(
        [
            {
                "Description": "AWS Access Key",
                "File": "src/config.py",
                "StartLine": 42,
            }
        ]
    )

    async def mock_scan_tool(cmd, timeout=30):
        if cmd[0] == "gitleaks":
            return gitleaks_output
        return ""

    with patch.object(g, "_exec_scan_tool", new=mock_scan_tool):
        result = await g._run_security_scans(
            [
                {
                    "agent": "backend",
                    "output": "```python:src/config.py\nAWS_KEY='AKIA...'\n```",
                }
            ],
            "/tmp",
        )

    assert result["blocked"] is True
    assert any(f["tool"] == "gitleaks" for f in result["findings"])
    assert any("AWS Access Key" in f["message"] for f in result["findings"])


@pytest.mark.asyncio
async def test_run_security_scans_no_findings_no_block():
    """Sin findings, blocked permanece False."""
    import graph as g

    with patch.object(
        g, "_exec_scan_tool", new=AsyncMock(return_value='{"results": []}')
    ):
        result = await g._run_security_scans([], "/tmp")

    assert result["blocked"] is False


# ---------------------------------------------------------------------------
# security_audit — integración con scan (OVD_SECURITY_SCAN_ENABLED)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_security_audit_scan_disabled_by_default():
    """Con OVD_SECURITY_SCAN_ENABLED no seteado, _run_security_scans no se llama."""
    import graph as g

    state = make_state(
        agent_results=[{"agent": "backend", "output": "def login(): pass"}],
    )

    mock_scan = AsyncMock(
        return_value={"tools_run": [], "findings": [], "blocked": False}
    )
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content=""))

    with (
        patch.object(g, "_run_security_scans", mock_scan),
        patch("graph.model_router") as mock_router,
        patch("graph.invoke_structured") as mock_invoke,
    ):
        mock_router.get_llm_with_context = AsyncMock(return_value=mock_llm)
        from graph import SecurityAuditOutput

        mock_invoke.return_value = SecurityAuditOutput(
            passed=True,
            score=90,
            severity="none",
            vulnerabilities=[],
            secrets_found=[],
            insecure_patterns=[],
            rls_compliant=True,
            remediation=[],
            summary="OK",
        )
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OVD_SECURITY_SCAN_ENABLED", None)
            await g.security_audit(state)

    mock_scan.assert_not_called()
