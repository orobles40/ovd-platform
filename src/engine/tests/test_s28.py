"""
S28 — Tests para los fixes de routing de agentes y diagnóstico de pytest:
  S28-A: system_sdd.md prohíbe asignar agente devops a features de código puro
  S28-C: run_tests distingue exit codes de pytest (0/1/4/5) y los loguea claramente
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pathlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.factories import make_state

# ────────────────────────────────────────────────────────────────────────────
# S28-A — system_sdd.md regla de agentes
# ────────────────────────────────────────────────────────────────────────────


class TestSddTemplateAgentRule:
    """system_sdd.md contiene la regla que prohíbe devops para código puro."""

    def _read_template(self) -> str:
        templates_dir = pathlib.Path(__file__).parent.parent / "templates"
        return (templates_dir / "system_sdd.md").read_text(encoding="utf-8")

    def test_template_prohibits_devops_for_python_only(self):
        """El template dice que devops es solo para Docker/CI/CD/infraestructura."""
        content = self._read_template()
        assert "devops" in content
        # Debe mencionar restricción explícita
        assert (
            "EXCLUSIVAMENTE" in content or "SOLO" in content or "PROHIBIDO" in content
        )

    def test_template_maps_python_to_backend(self):
        """El template mapea funciones Python al agente backend."""
        content = self._read_template()
        assert "backend" in content
        # Debe indicar que Python puro → backend
        assert "Python" in content
        lower = content.lower()
        assert "backend" in lower and "python" in lower

    def test_template_lists_devops_only_for_infra(self):
        """El template limita devops a Dockerfile/CI/K8s/despliegue."""
        content = self._read_template()
        # Debe mencionar al menos uno de los contextos válidos para devops
        infra_keywords = [
            "Dockerfile",
            "docker-compose",
            "CI/CD",
            "Kubernetes",
            "despliegue",
        ]
        assert any(kw in content for kw in infra_keywords), (
            f"Template debe mencionar contextos válidos para devops: {infra_keywords}"
        )

    def test_template_prohibits_devops_for_pure_feature(self):
        """El template incluye prohibición explícita para FR sin infra."""
        content = self._read_template()
        # Debe decir algo como "si no menciona Docker/CI no incluyas devops"
        assert (
            "NO incluyas" in content
            or "no incluyas" in content
            or "PROHIBIDO" in content
        )


# ────────────────────────────────────────────────────────────────────────────
# S28-C — run_tests exit codes de pytest
# ────────────────────────────────────────────────────────────────────────────


def _make_test_state(tmp_path: pathlib.Path) -> dict:
    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests" / "test_foo.py").write_text("def test_pass(): assert True")
    return make_state(
        agent_results=[
            {
                "agent": "backend",
                "output": "",
                "artifacts": [
                    {"path": "tests/test_foo.py", "size": 30, "lang": "python"}
                ],
            }
        ],
        directory=str(tmp_path),
        test_retry_count=0,
    )


class TestRunTestsExitCodes:
    """run_tests diagnostica correctamente los exit codes de pytest."""

    @pytest.mark.asyncio
    async def test_exit_0_marks_passed(self, tmp_path):
        """Exit code 0 → passed=True."""
        import graph as g

        state = _make_test_state(tmp_path)

        async def fake_exec(*args, **kwargs):
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(b"1 passed", None))
            proc.returncode = 0
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            result = await g.run_tests(state)

        assert result["test_results"]["passed"] is True

    @pytest.mark.asyncio
    async def test_exit_1_marks_failed(self, tmp_path):
        """Exit code 1 (test failures) → passed=False."""
        import graph as g

        state = _make_test_state(tmp_path)

        async def fake_exec(*args, **kwargs):
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(b"1 failed", None))
            proc.returncode = 1
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            result = await g.run_tests(state)

        assert result["test_results"]["passed"] is False

    @pytest.mark.asyncio
    async def test_exit_5_logs_warning_no_tests_found(self, tmp_path, caplog):
        """Exit code 5 (0 tests found) → passed=False + warning con diagnóstico."""
        import logging

        import graph as g

        state = _make_test_state(tmp_path)

        async def fake_exec(*args, **kwargs):
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(b"no tests ran", None))
            proc.returncode = 5
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            with caplog.at_level(logging.WARNING):
                result = await g.run_tests(state)

        assert result["test_results"]["passed"] is False
        # Debe haber un warning con diagnóstico de exit 5
        warning_msgs = [
            r.message for r in caplog.records if r.levelno >= logging.WARNING
        ]
        assert any("exit 5" in m or "0 tests" in m for m in warning_msgs), (
            f"Se esperaba warning sobre exit 5. Warnings encontrados: {warning_msgs}"
        )

    @pytest.mark.asyncio
    async def test_exit_4_logs_collection_error(self, tmp_path, caplog):
        """Exit code 4 (collection error) → passed=False + warning con SyntaxError/ImportError."""
        import logging

        import graph as g

        state = _make_test_state(tmp_path)

        async def fake_exec(*args, **kwargs):
            proc = MagicMock()
            proc.communicate = AsyncMock(
                return_value=(b"ERROR collecting tests/test_foo.py\nSyntaxError", None)
            )
            proc.returncode = 4
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            with caplog.at_level(logging.WARNING):
                result = await g.run_tests(state)

        assert result["test_results"]["passed"] is False
        warning_msgs = [
            r.message for r in caplog.records if r.levelno >= logging.WARNING
        ]
        assert any(
            "exit 4" in m or "colección" in m or "collection" in m.lower()
            for m in warning_msgs
        ), f"Se esperaba warning sobre exit 4. Warnings encontrados: {warning_msgs}"

    @pytest.mark.asyncio
    async def test_pytest_cmd_has_no_conflicting_flags(self, tmp_path):
        """El comando pytest no tiene -v y -q simultáneamente (se anulan)."""
        import graph as g

        state = _make_test_state(tmp_path)
        captured_args: list = []

        async def fake_exec(*args, **kwargs):
            captured_args.extend(args)
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(b"1 passed", None))
            proc.returncode = 0
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await g.run_tests(state)

        cmd_str = " ".join(str(a) for a in captured_args)
        # No deben aparecer -v y -q juntos
        has_v = " -v " in cmd_str or cmd_str.endswith(" -v")
        has_q = " -q " in cmd_str or cmd_str.endswith(" -q")
        assert not (has_v and has_q), (
            f"El comando pytest tiene -v y -q simultáneamente, se anulan: {cmd_str}"
        )
