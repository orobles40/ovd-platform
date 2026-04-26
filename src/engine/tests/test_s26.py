"""
S26 — Tests para los fixes de estructura Python: __init__.py raíz + security_audit filesystem.

Cubre:
  S26-A: system_backend.md prohíbe __init__.py en raíz y tiene conftest.py con sys.path
  S26-B: run_tests usa cwd=work_dir y --import-mode=importlib para pytest
  S26-C: security_audit lee archivos del filesystem cuando hay directory (igual que qa_review S24-C)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pathlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from tests.factories import make_state


# ────────────────────────────────────────────────────────────────────────────
# S26-A — Template system_backend.md
# ────────────────────────────────────────────────────────────────────────────

class TestSystemBackendTemplateS26:
    """system_backend.md prohíbe __init__.py en raíz e incluye conftest con sys.path."""

    def _read_template(self) -> str:
        # S58-pre: __init__.py y conftest reglas movidas a stack/backend_python.md
        import template_loader
        template_loader.invalidate()
        return template_loader.render_composed("system_backend", stack_language="python")

    def test_template_prohibits_init_in_root(self):
        """system_backend.md contiene prohibición explícita de __init__.py en raíz."""
        content = self._read_template()
        assert "NUNCA" in content
        assert "__init__.py" in content
        assert "raíz" in content or "raiz" in content.lower()

    def test_template_conftest_has_sys_path(self):
        """El ejemplo de conftest.py en el template inserta src/ en sys.path."""
        content = self._read_template()
        assert "sys.path.insert" in content
        assert "src" in content

    def test_template_shows_valid_structure(self):
        """El template muestra estructura válida con src/<paquete>/."""
        content = self._read_template()
        assert "src/" in content
        # Estructura src/<paquete>/__init__.py debe estar
        assert "src/<paquete>/__init__.py" in content or "src/" in content

    def test_template_shows_invalid_structure(self):
        """El template marca como INCORRECTO poner __init__.py en raíz."""
        content = self._read_template()
        assert "INCORRECTO" in content or "❌" in content


# ────────────────────────────────────────────────────────────────────────────
# S26-B — run_tests cwd + --import-mode=importlib
# ────────────────────────────────────────────────────────────────────────────

def _make_agent_results_with_tests(test_paths: list[str]) -> list[dict]:
    return [{
        "agent": "backend",
        "output": "",
        "artifacts": [{"path": p, "size": 100, "lang": "python"} for p in test_paths],
    }]


class TestRunTestsS26:
    """run_tests usa cwd=work_dir y --import-mode=importlib."""

    @pytest.mark.asyncio
    async def test_run_tests_pytest_uses_workdir_as_cwd(self, tmp_path):
        """pytest se ejecuta con cwd=work_dir (no None)."""
        import graph as g

        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_foo.py").write_text("def test_pass(): assert True")

        state = make_state(
            agent_results=_make_agent_results_with_tests(["tests/test_foo.py"]),
            directory=str(tmp_path),
            test_retry_count=0,
        )

        captured_kwargs: dict = {}

        async def fake_exec(*args, **kwargs):
            captured_kwargs.update(kwargs)
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(b"1 passed", None))
            proc.returncode = 0
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await g.run_tests(state)

        assert captured_kwargs.get("cwd") == str(tmp_path)

    @pytest.mark.asyncio
    async def test_run_tests_pytest_includes_importlib_mode(self, tmp_path):
        """El comando pytest incluye --import-mode=importlib."""
        import graph as g

        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_foo.py").write_text("def test_pass(): assert True")

        state = make_state(
            agent_results=_make_agent_results_with_tests(["tests/test_foo.py"]),
            directory=str(tmp_path),
            test_retry_count=0,
        )

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
        assert "--import-mode=importlib" in cmd_str

    @pytest.mark.asyncio
    async def test_run_tests_pytest_includes_rootdir(self, tmp_path):
        """El comando pytest incluye --rootdir apuntando al workspace."""
        import graph as g

        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_foo.py").write_text("def test_pass(): assert True")

        state = make_state(
            agent_results=_make_agent_results_with_tests(["tests/test_foo.py"]),
            directory=str(tmp_path),
            test_retry_count=0,
        )

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
        assert "--rootdir=" in cmd_str
        assert str(tmp_path) in cmd_str


# ────────────────────────────────────────────────────────────────────────────
# S26-C — security_audit filesystem-first
# ────────────────────────────────────────────────────────────────────────────

class TestSecurityAuditFilesystemFirst:
    """security_audit lee archivos del filesystem cuando directory está disponible."""

    @pytest.mark.asyncio
    async def test_security_audit_reads_files_from_disk(self, tmp_path):
        """Con directory, el prompt de security_audit contiene contenido real de archivos."""
        (tmp_path / "src").mkdir(parents=True)
        file_content = "def login(user, password): return db.query(user)"
        (tmp_path / "src" / "auth.py").write_text(file_content)

        state = make_state(
            directory=str(tmp_path),
            agent_results=[{
                "agent": "backend",
                "output": "",  # vacío — tool calling path
                "artifacts": [{"path": "src/auth.py", "size": 50, "lang": "python"}],
            }],
            sdd={"summary": "Auth service", "requirements": [], "design": {}, "constraints": [], "tasks": []},
        )

        captured_messages: list = []

        from graph import SecurityAuditOutput

        async def mock_invoke_structured(llm, messages, schema):
            captured_messages.extend(messages)
            return SecurityAuditOutput(
                passed=True, score=90, severity="none",
                vulnerabilities=[], secrets_found=[], insecure_patterns=[],
                rls_compliant=True, remediation=[], summary="OK",
            )

        mock_llm = MagicMock()
        # S48-A: OVD_SECURITY_MIN_SCORE=70 para evitar el bypass dev y probar el LLM
        with patch.dict(os.environ, {"OVD_SECURITY_MIN_SCORE": "70"}), \
             patch("graph.model_router") as mock_router, \
             patch("graph.invoke_structured", side_effect=mock_invoke_structured):
            mock_router.get_llm_with_context = AsyncMock(return_value=mock_llm)
            await __import__("graph").security_audit(state)

        full_prompt = "\n".join(str(m.content) for m in captured_messages)
        assert file_content in full_prompt or "src/auth.py" in full_prompt

    @pytest.mark.asyncio
    async def test_security_audit_fallback_to_output_without_directory(self):
        """Sin directory, security_audit usa output de agent_results."""
        inline_code = "def insecure(): return eval(input())"
        state = make_state(
            directory="",
            agent_results=[{
                "agent": "backend",
                "output": inline_code,
                "artifacts": [],
            }],
            sdd={"summary": "Test", "requirements": [], "design": {}, "constraints": [], "tasks": []},
        )

        captured_messages: list = []

        from graph import SecurityAuditOutput

        async def mock_invoke_structured(llm, messages, schema):
            captured_messages.extend(messages)
            return SecurityAuditOutput(
                passed=False, score=20, severity="high",
                vulnerabilities=[], secrets_found=[], insecure_patterns=[],
                rls_compliant=False, remediation=[], summary="Insecure",
            )

        mock_llm = MagicMock()
        # S48-A: OVD_SECURITY_MIN_SCORE=70 para evitar el bypass dev y probar el LLM
        with patch.dict(os.environ, {"OVD_SECURITY_MIN_SCORE": "70"}), \
             patch("graph.model_router") as mock_router, \
             patch("graph.invoke_structured", side_effect=mock_invoke_structured):
            mock_router.get_llm_with_context = AsyncMock(return_value=mock_llm)
            await __import__("graph").security_audit(state)

        full_prompt = "\n".join(str(m.content) for m in captured_messages)
        assert inline_code in full_prompt
