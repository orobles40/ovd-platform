"""
OVD Platform — Tests S51

S51-A: tarea de tests detectada en S39-D loop → instrucción [PRIORIDAD MÁXIMA] inyectada
S51-B: system_backend.md tiene item 5 (tests/test_*.py obligatorio) + prohibición explícita
S51-C: S39-D loop detecta ausencia de test_*.py y reintenta la tarea de tests
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
    # S58-pre: el contenido Python-specific fue movido a stack/backend_python.md
    import template_loader
    template_loader.invalidate()
    return template_loader.render_composed("system_backend", stack_language="python")


def _graph_src() -> str:
    path = pathlib.Path(__file__).parent.parent / "graph.py"
    return path.read_text()


# ---------------------------------------------------------------------------
# S51-B: template tiene item 5 + prohibición
# ---------------------------------------------------------------------------

class TestS51BTemplate:

    def test_backend_template_has_item5_tests(self):
        """system_backend.md lista tests/test_<paquete>.py como ítem 5 obligatorio."""
        content = _backend_template()
        assert "tests/test_" in content
        assert "S51-B" in content

    def test_backend_template_prohibits_delivery_without_tests(self):
        """system_backend.md tiene texto PROHIBIDO entregar sin tests."""
        content = _backend_template()
        assert "PROHIBIDO entregar sin" in content or "PROHIBIDO" in content

    def test_backend_template_marks_tests_as_obligatorio(self):
        """system_backend.md marca tests como OBLIGATORIO."""
        content = _backend_template()
        assert "OBLIGATORIO" in content


# ---------------------------------------------------------------------------
# S51-A: instrucción de prioridad máxima para tareas de tests
# ---------------------------------------------------------------------------

class TestS51ATaskPriority:

    def test_graph_src_has_s51a_label(self):
        """graph.py contiene la etiqueta S51-A."""
        src = _graph_src()
        assert "S51-A" in src

    def test_graph_src_injects_priority_for_test_tasks(self):
        """graph.py inyecta PRIORIDAD MÁXIMA para tareas de tests."""
        src = _graph_src()
        assert "PRIORIDAD MÁXIMA" in src
        assert "pytest" in src or "unitari" in src

    @pytest.mark.asyncio
    async def test_s51a_injects_priority_for_test_task_keyword(self, tmp_path):
        """Cuando la tarea tiene 'test' en la descripción, el runner recibe instrucción de prioridad."""
        import graph as g

        received_sdd_contents = []

        async def capture_runner(sdd, comment, llm, ctx, retry, lang, rag, *, stack_language=""):
            received_sdd_contents.append(sdd)
            # Simular que genera el test file
            return {
                "agent": "backend",
                "output": "```python:tests/test_imc.py\ndef test_imc(): assert True\n```\n",
                "artifacts": [{"path": "tests/test_imc.py", "size": 40, "lang": "python"}],
                "uncertainties": [],
                "tokens": {"input": 10, "output": 20},
            }

        mock_llm = MagicMock()
        mock_llm.model = "qwen3-coder:30b"

        sdd = {
            "summary": "IMC",
            "requirements": [],
            "constraints": [],
            "design": {},
            "tasks": [
                {"id": "TASK-001", "agent": "backend", "description": "Implementar tests pytest para IMC"},
            ],
        }

        state = make_state(
            directory=str(tmp_path),
            sdd=sdd,
        )
        state["stack_routing"] = "ollama"

        with patch.dict(g._AGENT_RUNNERS, {"backend": capture_runner}):
            result = await g._run_agent_with_tools(
                "backend", "SDD TASK-001: tests pytest", "comment",
                mock_llm, "ctx", "", "es",
                [MagicMock()],
                str(tmp_path),
                stack_routing="ollama",
            )

        # El resultado tiene el archivo de tests
        art_paths = [a["path"] for a in result.get("artifacts", [])]
        assert any("test_" in p for p in art_paths), "Debe haber un artifact de tests"

    @pytest.mark.asyncio
    async def test_s51a_no_injection_for_non_test_task(self, tmp_path):
        """Tareas sin 'test' en la descripción no reciben instrucción de prioridad."""
        import graph as g

        received_sdd_contents = []

        async def capture_runner(sdd, comment, llm, ctx, retry, lang, rag, *, stack_language=""):
            received_sdd_contents.append(sdd)
            return {
                "agent": "backend",
                "output": "```python:src/imc/service.py\ndef calc(): pass\n```\n",
                "artifacts": [{"path": "src/imc/service.py", "size": 30, "lang": "python"}],
                "uncertainties": [],
                "tokens": {"input": 5, "output": 15},
            }

        mock_llm = MagicMock()
        mock_llm.model = "qwen3-coder:30b"

        with patch.dict(g._AGENT_RUNNERS, {"backend": capture_runner}):
            await g._run_agent_with_tools(
                "backend", "SDD TASK-001: implementar service.py", "comment",
                mock_llm, "ctx", "", "es",
                [MagicMock()],
                str(tmp_path),
                stack_routing="ollama",
            )

        # El SDD recibido no debe tener PRIORIDAD MÁXIMA
        if received_sdd_contents:
            assert "PRIORIDAD MÁXIMA" not in received_sdd_contents[0]


# ---------------------------------------------------------------------------
# S51-C: retry automático si no hay test_*.py
# ---------------------------------------------------------------------------

class TestS51CRetryMissingTests:

    def test_graph_src_has_s51c_label(self):
        """graph.py contiene la etiqueta S51-C."""
        src = _graph_src()
        assert "S51-C" in src

    def test_graph_src_checks_test_arts(self):
        """graph.py busca archivos test_*.py en los artifacts tras el loop S39-D."""
        src = _graph_src()
        assert "_s51_test_arts" in src
        assert "_s51_test_tasks" in src

    @pytest.mark.asyncio
    async def test_s51c_retries_when_no_test_file_generated(self, tmp_path):
        """Cuando S39-D termina sin test_*.py pero el SDD tenía tarea de tests, S51-C hace retry."""
        import graph as g

        call_count = {"n": 0}

        async def runner_no_tests(sdd, comment, llm, ctx, retry, lang, rag, *, stack_language=""):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # Primera llamada (tarea de producción) — no genera tests
                return {
                    "agent": "backend",
                    "output": "```python:src/imc/service.py\ndef calc(): pass\n```\n",
                    "artifacts": [{"path": "src/imc/service.py", "size": 30, "lang": "python"}],
                    "uncertainties": [],
                    "tokens": {"input": 10, "output": 20},
                }
            else:
                # Segunda llamada (tarea de tests) — tampoco genera tests (para verificar el log)
                return {
                    "agent": "backend",
                    "output": "```python:tests/test_imc.py\ndef test_imc(): assert True\n```\n",
                    "artifacts": [{"path": "tests/test_imc.py", "size": 45, "lang": "python"}],
                    "uncertainties": [],
                    "tokens": {"input": 10, "output": 25},
                }

        mock_llm = MagicMock()
        mock_llm.model = "qwen3-coder:30b"

        sdd = {
            "summary": "IMC endpoint",
            "requirements": [],
            "constraints": [],
            "design": {},
            "tasks": [
                {"id": "TASK-001", "agent": "backend", "description": "Implementar service.py con calculate_imc"},
                {"id": "TASK-002", "agent": "backend", "description": "Implementar tests pytest con 3 casos"},
            ],
        }

        state = make_state(directory=str(tmp_path), sdd=sdd)
        state["stack_routing"] = "ollama"
        state["session_id"] = "test-s51c"
        state["org_id"] = "test-org"

        with patch.dict(g._AGENT_RUNNERS, {"backend": runner_no_tests}), \
             patch("graph.nats_client") as mock_nats, \
             patch("graph.model_router") as mock_router, \
             patch("graph.read_project_context", return_value=""):
            mock_nats.publish_agent_start = AsyncMock(return_value=None)
            mock_nats.publish_agent_end = AsyncMock(return_value=None)
            mock_router.resolve = AsyncMock(return_value=MagicMock(provider="ollama"))
            mock_router.get_llm_with_context = AsyncMock(return_value=mock_llm)

            result = await g.agent_executor(state)

        # S51-C debe haber hecho el retry → call_count >= 3 (1 servicio + 1 tests + 1 retry S51-C)
        assert call_count["n"] >= 2, f"S51-C debe haber invocado el runner al menos 2 veces, fue {call_count['n']}"

        # El resultado final debe incluir tests/test_imc.py
        agent_results = result.get("agent_results", [])
        all_paths = []
        for ar in agent_results:
            for art in ar.get("artifacts", []):
                all_paths.append(art.get("path", ""))
        assert any("test_imc" in p for p in all_paths), f"Debe haber test_imc.py en artifacts. Paths: {all_paths}"

    @pytest.mark.asyncio
    async def test_s51c_no_retry_when_test_file_present(self, tmp_path):
        """Cuando el runner ya generó test_*.py, S51-C no hace retry."""
        import graph as g

        call_count = {"n": 0}

        async def runner_with_tests(sdd, comment, llm, ctx, retry, lang, rag, *, stack_language=""):
            call_count["n"] += 1
            return {
                "agent": "backend",
                "output": (
                    "```python:src/imc/service.py\ndef calc(): pass\n```\n"
                    "```python:tests/test_imc.py\ndef test_imc(): assert True\n```\n"
                ),
                "artifacts": [
                    {"path": "src/imc/service.py", "size": 30, "lang": "python"},
                    {"path": "tests/test_imc.py", "size": 45, "lang": "python"},
                ],
                "uncertainties": [],
                "tokens": {"input": 10, "output": 50},
            }

        mock_llm = MagicMock()
        mock_llm.model = "qwen3-coder:30b"

        sdd = {
            "summary": "IMC",
            "requirements": [],
            "constraints": [],
            "design": {},
            "tasks": [
                {"id": "TASK-001", "agent": "backend", "description": "Implementar todo con tests pytest"},
                {"id": "TASK-002", "agent": "backend", "description": "Agregar más tests unitarios"},
            ],
        }

        state = make_state(directory=str(tmp_path), sdd=sdd)
        state["stack_routing"] = "ollama"
        state["session_id"] = "test-s51c-skip"
        state["org_id"] = "test-org"

        with patch.dict(g._AGENT_RUNNERS, {"backend": runner_with_tests}), \
             patch("graph.nats_client") as mock_nats, \
             patch("graph.model_router") as mock_router, \
             patch("graph.read_project_context", return_value=""):
            mock_nats.publish_agent_start = AsyncMock(return_value=None)
            mock_nats.publish_agent_end = AsyncMock(return_value=None)
            mock_router.resolve = AsyncMock(return_value=MagicMock(provider="ollama"))
            mock_router.get_llm_with_context = AsyncMock(return_value=mock_llm)

            await g.agent_executor(state)

        # No debe haber llamada extra de S51-C (solo 2 tareas normales)
        assert call_count["n"] == 2, f"S51-C no debe reintentar si ya hay tests. Llamadas: {call_count['n']}"
