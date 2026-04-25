"""
OVD Platform — Tests S50

S50-A: _run_agent_with_tools escribe archivos al disco en paths S49-A y S49-C
        para que run_tests pueda detectar test files durante execute_agents
S50-B: deliver deduplica artefactos por path (evita models.py × 2)
S50-C: system_backend.md usa Pydantic v2 @field_validator
S50-D: system_backend.md tiene ejemplos explícitos de floats calculados
"""
import sys, os, pathlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from tests.factories import make_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _backend_template() -> str:
    path = pathlib.Path(__file__).parent.parent / "templates" / "system_backend.md"
    return path.read_text()


def _graph_src() -> str:
    path = pathlib.Path(__file__).parent.parent / "graph.py"
    return path.read_text()


# ---------------------------------------------------------------------------
# S50-A: runner escribe archivos al disco (paths S49-A y S49-C)
# ---------------------------------------------------------------------------

class TestS50AWriteOnRunnerPath:

    @pytest.mark.asyncio
    async def test_s49c_ollama_path_writes_files_to_disk(self, tmp_path):
        """Con stack_routing='ollama', _run_agent_with_tools escribe archivos al disco
        para que run_tests pueda encontrarlos."""
        import graph as g

        code_output = (
            "```python:src/imc/service.py\n"
            "def calculate_imc(peso, altura):\n"
            "    return round(peso / altura**2, 2)\n"
            "```\n\n"
            "```python:tests/test_service.py\n"
            "def test_imc():\n"
            "    assert calculate_imc(70, 1.75) == 22.86\n"
            "```\n"
        )

        async def fake_runner(sdd, comment, llm, ctx, retry, lang, rag, *, stack_language=""):
            return {
                "agent": "backend",
                "output": code_output,
                "artifacts": [],
                "uncertainties": [],
                "tokens": {"input": 10, "output": 50},
            }

        mock_llm = MagicMock()
        mock_llm.model = "qwen3-coder:30b"

        with patch.dict(g._AGENT_RUNNERS, {"backend": fake_runner}):
            result = await g._run_agent_with_tools(
                "backend", "SDD", "comment",
                mock_llm, "ctx", "", "es",
                [MagicMock()],
                str(tmp_path),
                stack_routing="ollama",
            )

        # Archivos deben estar escritos en disco
        service_file = tmp_path / "src" / "imc" / "service.py"
        test_file = tmp_path / "tests" / "test_service.py"
        assert service_file.exists(), "src/imc/service.py debe estar en disco"
        assert test_file.exists(), "tests/test_service.py debe estar en disco"

        # Y en los artifacts del resultado
        art_paths = [a["path"] for a in result.get("artifacts", [])]
        assert any("service.py" in p for p in art_paths), "service.py debe estar en artifacts"
        assert any("test_service.py" in p for p in art_paths), "test_service.py debe estar en artifacts"

    @pytest.mark.asyncio
    async def test_s49a_iter0_path_writes_files_to_disk(self, tmp_path):
        """Cuando iter=0 y sin tool_calls (S49-A), el runner escribe archivos al disco."""
        import graph as g

        code_output = (
            "```python:src/calc.py\n"
            "def add(a, b):\n"
            "    return a + b\n"
            "```\n\n"
            "```python:tests/test_calc.py\n"
            "def test_add():\n"
            "    assert add(1, 2) == 3\n"
            "```\n"
        )

        async def fake_runner(sdd, comment, llm, ctx, retry, lang, rag, *, stack_language=""):
            return {
                "agent": "backend",
                "output": code_output,
                "artifacts": [],
                "uncertainties": [],
                "tokens": {"input": 10, "output": 30},
            }

        mock_llm = MagicMock()
        bound_llm = MagicMock()
        response = MagicMock()
        response.tool_calls = []
        response.content = code_output
        bound_llm.ainvoke = AsyncMock(return_value=response)
        mock_llm.bind_tools = MagicMock(return_value=bound_llm)

        with patch("graph._extract_usage", return_value={"input": 0, "output": 0}), \
             patch.dict(g._AGENT_RUNNERS, {"backend": fake_runner}):
            result = await g._run_agent_with_tools(
                "backend", "SDD", "comment",
                mock_llm, "ctx", "", "es",
                [MagicMock()],
                str(tmp_path),
                stack_routing="auto",  # no Ollama → bind_tools → iter 0 sin tools → S49-A
            )

        # Archivos deben estar en disco
        assert (tmp_path / "src" / "calc.py").exists(), "src/calc.py debe estar en disco"
        assert (tmp_path / "tests" / "test_calc.py").exists(), "tests/test_calc.py debe estar en disco"

        # Y en artifacts
        art_paths = [a["path"] for a in result.get("artifacts", [])]
        assert any("test_calc.py" in p for p in art_paths)

    @pytest.mark.asyncio
    async def test_s50a_no_overwrite_if_artifacts_present(self, tmp_path):
        """Si el runner ya retorna artifacts poblados, S50-A no llama _write_artifacts."""
        import graph as g

        async def fake_runner_with_arts(sdd, comment, llm, ctx, retry, lang, rag, *, stack_language=""):
            return {
                "agent": "backend",
                "output": "código",
                "artifacts": [{"path": "src/main.py", "size": 100, "lang": "python"}],
                "uncertainties": [],
                "tokens": {},
            }

        mock_llm = MagicMock()
        mock_llm.model = "llama3.1:8b"

        write_arts_called = []

        with patch.dict(g._AGENT_RUNNERS, {"backend": fake_runner_with_arts}), \
             patch("graph._write_artifacts", side_effect=lambda *a, **kw: (write_arts_called.append(True) or [])):
            await g._run_agent_with_tools(
                "backend", "SDD", "comment",
                mock_llm, "ctx", "", "es",
                [MagicMock()],
                str(tmp_path),
                stack_routing="ollama",
            )

        assert not write_arts_called, "_write_artifacts NO debe llamarse si el runner ya tiene artifacts"


# ---------------------------------------------------------------------------
# S50-B: deduplicación de artefactos en deliver
# ---------------------------------------------------------------------------

class TestS50BDeduplicateArtifacts:

    @pytest.mark.asyncio
    async def test_deliver_deduplicates_duplicate_artifacts(self, tmp_path):
        """deliver no reporta el mismo archivo dos veces en la lista de artefactos."""
        # Escribir un archivo real para que deliver lo encuentre
        (tmp_path / "src").mkdir(parents=True)
        (tmp_path / "src" / "main.py").write_text("# main")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_main.py").write_text("def test_main(): pass")

        # Simular agent_results con output que genera archivos duplicados
        duplicate_output = (
            "```python:src/main.py\n# main\n```\n\n"
            "```python:src/main.py\n# main v2\n```\n\n"  # duplicado
            "```python:tests/test_main.py\ndef test_main(): pass\n```\n"
        )

        state = make_state(
            directory=str(tmp_path),
            agent_results=[{
                "agent": "backend",
                "output": duplicate_output,
                "artifacts": [],
            }],
            sdd={"summary": "Test", "requirements": [], "design": {}, "constraints": [], "tasks": []},
        )

        import graph as g

        mock_llm_config = MagicMock()
        mock_llm_config.provider = "ollama"

        with patch("graph.model_router") as mock_router, \
             patch("graph.nats_client") as mock_nats, \
             patch("graph._index_delivery_report", return_value=None), \
             patch("graph._generate_delivery_report", return_value=str(tmp_path / "report.md")), \
             patch("graph.lessons") as mock_lessons, \
             patch("graph._export_finetune_record", return_value=None):
            mock_router.resolve = AsyncMock(return_value=mock_llm_config)
            mock_router.get_llm_with_context = AsyncMock(return_value=MagicMock())
            mock_nats.publish_deliver = AsyncMock(return_value=None)
            mock_nats.publish_done = AsyncMock(return_value=None)
            mock_lessons.index_cycle_postmortem = AsyncMock(return_value=None)

            result = await g.deliver(state)

        # Verificar que no hay rutas duplicadas en deliverables
        for deliv in result.get("deliverables", []):
            if deliv.get("type") == "implementation":
                arts = deliv.get("artifacts", [])
                paths = [a["path"] for a in arts]
                assert len(paths) == len(set(paths)), f"Hay rutas duplicadas en artifacts: {paths}"

    def test_deliver_dedup_logic_in_graph_src(self):
        """graph.py tiene el código S50-B de deduplicación."""
        src = _graph_src()
        assert "S50-B" in src
        assert "seen_paths" in src


# ---------------------------------------------------------------------------
# S50-C: Pydantic v2 en template
# ---------------------------------------------------------------------------

class TestS50CPydanticV2Template:

    def test_backend_template_uses_field_validator(self):
        """system_backend.md menciona @field_validator (Pydantic v2)."""
        content = _backend_template()
        assert "field_validator" in content

    def test_backend_template_marks_validator_as_deprecated(self):
        """system_backend.md marca @validator como DEPRECADO."""
        content = _backend_template()
        assert "@validator" in content  # aparece como ejemplo del ❌ incorrecto
        assert "DEPRECADO" in content or "deprecado" in content.lower() or "Deprecated" in content

    def test_backend_template_shows_pydantic_v2_example(self):
        """system_backend.md muestra ejemplo completo de @field_validator con @classmethod."""
        content = _backend_template()
        assert "@classmethod" in content
        assert "field_validator" in content

    def test_backend_template_has_s50c_label(self):
        """system_backend.md tiene la etiqueta S50-C."""
        content = _backend_template()
        assert "S50-C" in content


# ---------------------------------------------------------------------------
# S50-D: floats con ejemplos explícitos
# ---------------------------------------------------------------------------

class TestS50DFloatExamples:

    def test_backend_template_has_imc_float_example(self):
        """system_backend.md tiene el ejemplo del IMC con valor correcto 21.97."""
        content = _backend_template()
        assert "21.97" in content

    def test_backend_template_has_s50d_label(self):
        """system_backend.md tiene la etiqueta S50-D."""
        content = _backend_template()
        assert "S50-D" in content

    def test_backend_template_warns_against_wrong_float(self):
        """system_backend.md advierte contra escribir 22.35 para 65/1.72^2."""
        content = _backend_template()
        assert "22.35" in content  # aparece como el ejemplo ❌ incorrecto
