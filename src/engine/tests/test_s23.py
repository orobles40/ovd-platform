"""
S23 — Tests para los fixes de calidad en el flujo tool-calling.

Cubre:
  S23-A: deliver usa artifacts[] cuando el agente escribió con tool calling
  S23-B: _detect_test_runner detecta runner desde artifacts[], output y filesystem
  S23-C: qa_review lee archivos del disco cuando hay artifacts + directory
  S23-D: system_backend.md incluye la sección de infraestructura Python
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pathlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from tests.factories import make_state


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

def _import_detect_test_runner():
    from graph import _detect_test_runner
    return _detect_test_runner


# ────────────────────────────────────────────────────────────────────────────
# S23-B — _detect_test_runner
# ────────────────────────────────────────────────────────────────────────────

class TestDetectTestRunner:
    """_detect_test_runner detecta runner desde artifacts[], output y filesystem."""

    def test_detects_pytest_from_artifacts(self):
        """Cuando artifacts[] contiene un archivo test_*.py → pytest."""
        detect = _import_detect_test_runner()
        results = [{"agent": "backend", "output": "", "artifacts": [
            {"path": "tests/test_math_utils.py", "size": 500, "lang": "python"},
        ]}]
        assert detect(results) == "pytest"

    def test_detects_pytest_from_output_fence(self):
        """Cuando output tiene un fence ```python:tests/test_foo.py → pytest."""
        detect = _import_detect_test_runner()
        results = [{"agent": "backend", "output": "```python:tests/test_foo.py\npass\n```", "artifacts": []}]
        assert detect(results) == "pytest"

    def test_detects_vitest_from_artifacts(self):
        """Cuando artifacts[] contiene un archivo *.test.ts → vitest."""
        detect = _import_detect_test_runner()
        results = [{"agent": "frontend", "output": "", "artifacts": [
            {"path": "src/Button.test.tsx", "size": 300, "lang": "typescript"},
        ]}]
        assert detect(results) == "vitest"

    def test_detects_cargo_from_artifacts(self):
        """Cuando artifacts[] contiene un archivo .rs → cargo."""
        detect = _import_detect_test_runner()
        results = [{"agent": "backend", "output": "", "artifacts": [
            {"path": "src/lib.rs", "size": 200, "lang": "rust"},
        ]}]
        assert detect(results) == "cargo"

    def test_returns_none_when_no_test_files(self):
        """Sin archivos de test en ninguna fuente → None."""
        detect = _import_detect_test_runner()
        results = [{"agent": "backend", "output": "", "artifacts": [
            {"path": "src/utils/math_utils.py", "size": 400, "lang": "python"},
        ]}]
        assert detect(results) is None

    def test_detects_pytest_from_filesystem(self, tmp_path):
        """Cuando no hay artifacts ni output, pero hay test_*.py en disco → pytest."""
        detect = _import_detect_test_runner()
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_foo.py").write_text("def test_pass(): pass")
        results = [{"agent": "backend", "output": "", "artifacts": []}]
        assert detect(results, directory=str(tmp_path)) == "pytest"

    def test_filesystem_takes_priority_over_artifacts(self, tmp_path):
        """S24-B: filesystem-first — el filesystem gana sobre artifacts[].
        Si el filesystem tiene test_*.py, retorna pytest aunque artifacts apunte a Rust."""
        detect = _import_detect_test_runner()
        # Filesystem tiene test_*.py, artifacts tiene .rs
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_calc.py").write_text("def test_pass(): pass")
        results = [{"agent": "backend", "output": "", "artifacts": [
            {"path": "src/lib.rs", "size": 100, "lang": "rust"},
        ]}]
        # Filesystem (pytest) gana sobre artifacts (cargo)
        assert detect(results, directory=str(tmp_path)) == "pytest"


# ────────────────────────────────────────────────────────────────────────────
# S23-A — deliver usa artifacts[] del tool calling
# ────────────────────────────────────────────────────────────────────────────

class TestDeliverUsesExistingArtifacts:
    """deliver() usa artifacts[] cuando el agente escribió archivos con tool calling."""

    @pytest.mark.asyncio
    async def test_deliver_uses_existing_artifacts_when_present(self, tmp_path):
        """Si result.artifacts[] no está vacío y directory está seteado → usa artifacts tal cual."""
        # Crear archivos en disco (simulando que el agente los escribió)
        (tmp_path / "src").mkdir(parents=True)
        (tmp_path / "src" / "utils.py").write_text("def add(a, b): return a + b")

        existing_arts = [{"path": "src/utils.py", "size": 30, "lang": "python"}]
        state = make_state(
            directory=str(tmp_path),
            agent_results=[{
                "agent": "backend",
                "output": "",  # vacío — tool calling path
                "artifacts": existing_arts,
            }],
        )

        from graph import deliver
        with patch("graph._write_artifacts") as mock_write:
            result = await deliver(state)

        # _write_artifacts NO debe haber sido llamado para este agente
        mock_write.assert_not_called()

        impl_deliverables = [d for d in result["deliverables"] if d["type"] == "implementation"]
        assert len(impl_deliverables) == 1
        assert impl_deliverables[0]["artifacts"] == existing_arts

    @pytest.mark.asyncio
    async def test_deliver_falls_back_to_write_artifacts_when_no_directory(self, tmp_path):
        """Sin directory, aunque haya artifacts, llama _write_artifacts (no puede verificar)."""
        state = make_state(
            directory="",  # sin directory
            agent_results=[{
                "agent": "backend",
                "output": "```python:src/utils.py\ndef add(a, b): return a + b\n```",
                "artifacts": [{"path": "src/utils.py", "size": 30, "lang": "python"}],
            }],
        )

        from graph import deliver
        with patch("graph._write_artifacts", return_value=[]) as mock_write:
            await deliver(state)

        mock_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_deliver_calls_write_artifacts_when_no_existing_artifacts(self, tmp_path):
        """Sin artifacts[], llama _write_artifacts normalmente (path clásico)."""
        state = make_state(
            directory=str(tmp_path),
            agent_results=[{
                "agent": "backend",
                "output": "```python:src/utils.py\ndef add(a, b): return a + b\n```",
                "artifacts": [],  # vacío — path clásico
            }],
        )

        from graph import deliver
        with patch("graph._write_artifacts", return_value=[]) as mock_write:
            await deliver(state)

        mock_write.assert_called_once()


# ────────────────────────────────────────────────────────────────────────────
# S23-C — qa_review lee archivos del disco
# ────────────────────────────────────────────────────────────────────────────

class TestQaReviewReadsFromDisk:
    """qa_review construye el contexto leyendo archivos del disco cuando hay artifacts."""

    @pytest.mark.asyncio
    async def test_qa_reads_files_from_disk_when_artifacts_present(self, tmp_path):
        """qa_review lee el contenido real de los archivos escritos en disco."""
        (tmp_path / "src").mkdir(parents=True)
        file_content = "def average(nums): return sum(nums) / len(nums)"
        (tmp_path / "src" / "utils.py").write_text(file_content)

        state = make_state(
            directory=str(tmp_path),
            agent_results=[{
                "agent": "backend",
                "output": "",  # vacío — tool calling path
                "artifacts": [{"path": "src/utils.py", "size": 50, "lang": "python"}],
            }],
            sdd={"summary": "Función promedio", "requirements": [], "design": {}, "constraints": [], "tasks": []},
        )

        captured_prompt: list[str] = []

        async def mock_invoke(messages):
            captured_prompt.extend(str(m.content) for m in messages)
            return MagicMock(content='{"passed": true, "score": 80, "issues": [], "sdd_compliance": true, "missing_requirements": [], "code_quality_issues": [], "summary": "OK"}')

        mock_llm = MagicMock()
        mock_llm.ainvoke = mock_invoke
        mock_llm.with_structured_output = MagicMock(return_value=mock_llm)

        with patch("graph.model_router") as mock_router, \
             patch("graph.invoke_structured") as mock_structured:
            mock_router.get_llm_with_context = AsyncMock(return_value=mock_llm)
            mock_structured.side_effect = AsyncMock(side_effect=Exception("force fallback"))

            await __import__("graph").qa_review(state)

        # El prompt debe contener el contenido del archivo, no estar vacío
        full_prompt = "\n".join(captured_prompt)
        assert file_content in full_prompt or "src/utils.py" in full_prompt

    @pytest.mark.asyncio
    async def test_qa_falls_back_to_output_when_no_directory(self):
        """Sin directory, qa_review usa output directamente aunque artifacts no esté vacío."""
        inline_code = "```python:src/utils.py\ndef add(a, b): return a + b\n```"
        state = make_state(
            directory="",
            agent_results=[{
                "agent": "backend",
                "output": inline_code,
                "artifacts": [{"path": "src/utils.py", "size": 30, "lang": "python"}],
            }],
            sdd={"summary": "Test", "requirements": [], "design": {}, "constraints": [], "tasks": []},
        )

        captured_prompt: list[str] = []

        async def mock_invoke(messages):
            captured_prompt.extend(str(m.content) for m in messages)
            return MagicMock(content='{"passed": true, "score": 75, "issues": [], "sdd_compliance": true, "missing_requirements": [], "code_quality_issues": [], "summary": "OK"}')

        mock_llm = MagicMock()
        mock_llm.ainvoke = mock_invoke
        mock_llm.with_structured_output = MagicMock(return_value=mock_llm)

        with patch("graph.model_router") as mock_router, \
             patch("graph.invoke_structured") as mock_structured:
            mock_router.get_llm_with_context = AsyncMock(return_value=mock_llm)
            mock_structured.side_effect = AsyncMock(side_effect=Exception("force fallback"))

            await __import__("graph").qa_review(state)

        full_prompt = "\n".join(captured_prompt)
        assert "def add(a, b)" in full_prompt


# ────────────────────────────────────────────────────────────────────────────
# S23-D — system_backend.md incluye sección infraestructura Python
# ────────────────────────────────────────────────────────────────────────────

class TestSystemBackendTemplate:
    """system_backend.md incluye la sección de infraestructura obligatoria para Python."""

    def test_template_contains_python_infrastructure_section(self):
        templates_dir = pathlib.Path(__file__).parent.parent / "templates"
        template_path = templates_dir / "system_backend.md"
        assert template_path.exists(), "system_backend.md no existe"
        content = template_path.read_text(encoding="utf-8")
        assert "Infraestructura obligatoria" in content
        assert "pytest.ini" in content or "pyproject.toml" in content
        assert "__init__.py" in content
        assert "conftest.py" in content

    def test_template_contains_tdd_section(self):
        """La sección TDD sigue presente (no fue eliminada por S23-D)."""
        templates_dir = pathlib.Path(__file__).parent.parent / "templates"
        content = (templates_dir / "system_backend.md").read_text(encoding="utf-8")
        assert "TDD" in content
        assert "RED" in content
        assert "GREEN" in content
