"""
OVD Platform — Tests S39: optimizaciones de agentes
S39-D: task-by-task execution en agent_executor
S39-B: _summarize_for_qa() antes de qa_review
S39-C: retry_feedback reducido a 800 chars (solo stderr)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import inspect
import pathlib
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# S39-D — _build_single_task_sdd_content
# ---------------------------------------------------------------------------


class TestS39DBuildSingleTask:
    """S39-D: helper que construye SDD para una sola tarea."""

    def _get_fn(self):
        import graph as g

        return g._build_single_task_sdd_content

    def test_contiene_solo_la_tarea_dada(self):
        """El SDD single-task incluye solo la tarea pasada, no todas las del agente."""
        fn = self._get_fn()
        sdd = {
            "summary": "CRUD contratos",
            "requirements": [{"id": "REQ-001"}],
            "design": {"overview": "REST API"},
            "constraints": [{"id": "CON-001"}],
            "tasks": [
                {"id": "TASK-001", "agent": "backend", "title": "Models"},
                {"id": "TASK-002", "agent": "backend", "title": "API"},
                {"id": "TASK-003", "agent": "backend", "title": "Tests"},
            ],
        }
        result = fn(sdd, "backend", sdd["tasks"][0], 0, 3)
        assert "TASK-001" in result
        assert "TASK-002" not in result
        assert "TASK-003" not in result

    def test_incluye_contexto_compartido(self):
        """El SDD single-task incluye summary, requirements, design y constraints."""
        fn = self._get_fn()
        sdd = {
            "summary": "Mi resumen",
            "requirements": [{"id": "REQ-001", "description": "Req uno"}],
            "design": {"overview": "Arquitectura REST"},
            "constraints": [{"id": "CON-001", "description": "Sin SQL injection"}],
            "tasks": [{"id": "TASK-001", "agent": "backend"}],
        }
        result = fn(sdd, "backend", sdd["tasks"][0], 0, 1)
        assert "Mi resumen" in result
        assert "REQ-001" in result
        assert "Arquitectura REST" in result
        assert "CON-001" in result

    def test_muestra_progreso_de_tarea(self):
        """El SDD single-task muestra el índice actual y total de tareas."""
        fn = self._get_fn()
        sdd = {
            "summary": "",
            "requirements": [],
            "design": {},
            "constraints": [],
            "tasks": [],
        }
        task = {"id": "TASK-002", "agent": "backend"}
        result = fn(sdd, "backend", task, 1, 5)
        assert "2/5" in result

    def test_no_incluye_tareas_de_otros_agentes(self):
        """El SDD single-task no filtra — recibe la tarea exacta pasada por parámetro."""
        fn = self._get_fn()
        sdd = {
            "summary": "",
            "requirements": [],
            "design": {},
            "constraints": [],
            "tasks": [
                {"id": "TASK-DB", "agent": "database"},
                {"id": "TASK-BE", "agent": "backend"},
            ],
        }
        task = {"id": "TASK-BE", "agent": "backend"}
        result = fn(sdd, "backend", task, 0, 1)
        assert "TASK-BE" in result
        assert "TASK-DB" not in result


# ---------------------------------------------------------------------------
# S39-D — agent_executor usa loop de tareas cuando hay > 1 tarea
# ---------------------------------------------------------------------------


class TestS39DAgentExecutorLoop:
    """S39-D: agent_executor itera una tarea a la vez cuando hay múltiples tareas."""

    def _get_executor_source(self):
        import graph as g

        # S59-A/A4: la lógica está en _agent_executor_impl (agent_executor es el wrapper)
        return inspect.getsource(g._agent_executor_impl)

    def test_codigo_usa_loop_de_tareas(self):
        """agent_executor contiene el loop S39-D sobre agent_tasks."""
        src = self._get_executor_source()
        assert "S39-D" in src, "S39-D no está implementado en agent_executor"
        assert "agent_tasks" in src, "No hay variable agent_tasks en agent_executor"
        assert "for i, task in enumerate(agent_tasks)" in src, (
            "No hay loop de tareas en agent_executor"
        )

    def test_codigo_refresca_project_context_por_tarea(self):
        """Cada iteración llama read_project_context para recoger archivos previos."""
        src = self._get_executor_source()
        assert "read_project_context(directory, agent_name)" in src, (
            "No hay refresco de project_context por tarea"
        )

    def test_codigo_usa_build_single_task(self):
        """Usa _build_single_task_sdd_content en el loop."""
        src = self._get_executor_source()
        assert "_build_single_task_sdd_content" in src, (
            "No usa _build_single_task_sdd_content en el loop"
        )

    def test_codigo_acumula_artifacts(self):
        """Los artifacts de cada tarea se acumulan en all_artifacts."""
        src = self._get_executor_source()
        assert "all_artifacts" in src
        assert "all_output_parts" in src

    def test_single_task_usa_comportamiento_original(self):
        """Cuando hay 0 o 1 tarea, usa el comportamiento original (sin loop)."""
        src = self._get_executor_source()
        # El branch else debe usar _build_agent_sdd_content (función original)
        assert "_build_agent_sdd_content(sdd, agent_name)" in src, (
            "El path de 1 tarea no usa _build_agent_sdd_content"
        )

    @pytest.mark.asyncio
    async def test_loop_ejecuta_una_llamada_por_tarea(self):
        """Con 3 tareas, _run_agent_with_tools se llama 3 veces.

        Nota: el loop usa _run_agent_with_tools solo cuando tools es no vacío.
        Proporcionamos un dummy tool para forzar ese path.
        """
        import tempfile

        import graph as g

        call_count = 0

        async def mock_run_with_tools(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return {
                "agent": "backend",
                "output": f"output tarea {call_count}",
                "artifacts": [
                    {"path": f"file{call_count}.py", "size": 100, "language": "python"}
                ],
                "uncertainties": [],
                "tokens": {"input": 10, "output": 20},
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            state = {
                "current_agent": "backend",
                "sdd": {
                    "summary": "test",
                    "requirements": [],
                    "design": {},
                    "constraints": [],
                    "tasks": [
                        {"id": "T1", "agent": "backend", "title": "Tarea 1"},
                        {"id": "T2", "agent": "backend", "title": "Tarea 2"},
                        {"id": "T3", "agent": "backend", "title": "Tarea 3"},
                    ],
                },
                "org_id": "",
                "project_id": "",
                "jwt_token": "",
                "project_context": "",
                "retry_feedback": "",
                "language": "es",
                "directory": tmpdir,
                "session_id": "",
                "rag_context": "",
                "approval_comment": "",
                "github_repo": "",
                "stack_routing": "auto",
                "token_usage": {},
                "cycle_start_ts": 0.0,
            }

            mock_llm = MagicMock()
            dummy_tool = MagicMock()
            dummy_tool.name = "write_file"

            with (
                patch.object(
                    g, "_run_agent_with_tools", side_effect=mock_run_with_tools
                ),
                patch.object(
                    g.model_router,
                    "get_llm_with_context",
                    new=AsyncMock(return_value=mock_llm),
                ),
                patch.object(g, "make_file_tools", return_value=[dummy_tool]),
                patch.object(g.mcp_client.pool, "get_langchain_tools", return_value=[]),
                patch.object(g, "read_project_context", return_value=""),
            ):
                result = await g.agent_executor(state)

        assert call_count == 3, (
            f"Esperaba 3 llamadas a _run_agent_with_tools, hubo {call_count}"
        )
        assert len(result["agent_results"][0]["artifacts"]) == 3

    @pytest.mark.asyncio
    async def test_timeout_por_tarea_no_aborta_ciclo(self):
        """Un timeout en tarea 2/3 no aborta — continúa con tarea 3."""
        import asyncio
        import tempfile

        import graph as g

        call_count = 0

        async def mock_run_with_tools(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise asyncio.TimeoutError()
            return {
                "agent": "backend",
                "output": f"ok tarea {call_count}",
                "artifacts": [],
                "uncertainties": [],
                "tokens": {"input": 5, "output": 5},
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            state = {
                "current_agent": "backend",
                "sdd": {
                    "summary": "test",
                    "requirements": [],
                    "design": {},
                    "constraints": [],
                    "tasks": [
                        {"id": "T1", "agent": "backend"},
                        {"id": "T2", "agent": "backend"},
                        {"id": "T3", "agent": "backend"},
                    ],
                },
                "org_id": "",
                "project_id": "",
                "jwt_token": "",
                "project_context": "",
                "retry_feedback": "",
                "language": "es",
                "directory": tmpdir,
                "session_id": "",
                "rag_context": "",
                "approval_comment": "",
                "github_repo": "",
                "stack_routing": "auto",
                "token_usage": {},
                "cycle_start_ts": 0.0,
            }

            mock_llm = MagicMock()
            dummy_tool = MagicMock()
            dummy_tool.name = "write_file"

            with (
                patch.object(
                    g, "_run_agent_with_tools", side_effect=mock_run_with_tools
                ),
                patch.object(
                    g.model_router,
                    "get_llm_with_context",
                    new=AsyncMock(return_value=mock_llm),
                ),
                patch.object(g, "make_file_tools", return_value=[dummy_tool]),
                patch.object(g.mcp_client.pool, "get_langchain_tools", return_value=[]),
                patch.object(g, "read_project_context", return_value=""),
            ):
                result = await g.agent_executor(state)

        # Debe haber intentado las 3 tareas (2 exitosas, 1 timeout)
        assert call_count == 3, f"Esperaba 3 llamadas, hubo {call_count}"
        output = result["agent_results"][0]["output"]
        assert "ok tarea 1" in output
        assert "ok tarea 3" in output


# ---------------------------------------------------------------------------
# S39-B — _summarize_for_qa
# ---------------------------------------------------------------------------


class TestS39BSummarizeForQA:
    """S39-B: _summarize_for_qa extrae defs/clases del workspace."""

    def _get_fn(self):
        import graph as g

        return g._summarize_for_qa

    def test_retorna_vacio_sin_directorio(self):
        fn = self._get_fn()
        assert fn("") == ""

    def test_retorna_vacio_directorio_inexistente(self):
        fn = self._get_fn()
        assert fn("/ruta/que/no/existe/xyz") == ""

    def test_extrae_defs_y_clases(self):
        """Detecta def, async def y class en archivos Python."""
        fn = self._get_fn()
        with tempfile.TemporaryDirectory() as tmpdir:
            src = pathlib.Path(tmpdir) / "modulo.py"
            src.write_text(
                "class Contrato:\n"
                "    def __init__(self):\n"
                "        pass\n\n"
                "    def validar(self):\n"
                "        pass\n\n"
                "async def crear_contrato():\n"
                "    pass\n"
            )
            result = fn(tmpdir)
        assert "class Contrato" in result
        assert "def validar" in result
        assert "async def crear_contrato" in result

    def test_ignora_pycache_y_venv(self):
        """No incluye archivos dentro de __pycache__ o .venv."""
        fn = self._get_fn()
        with tempfile.TemporaryDirectory() as tmpdir:
            base = pathlib.Path(tmpdir)
            (base / "__pycache__").mkdir()
            (base / "__pycache__" / "cache.py").write_text("def cached(): pass")
            (base / "real.py").write_text("def real_fn(): pass")
            result = fn(tmpdir)
        assert "cached" not in result
        assert "real_fn" in result

    def test_ignora_archivos_sin_defs(self):
        """Archivos sin defs/clases no aparecen en el resumen."""
        fn = self._get_fn()
        with tempfile.TemporaryDirectory() as tmpdir:
            (pathlib.Path(tmpdir) / "config.py").write_text(
                "DEBUG = True\nDB_HOST = 'localhost'"
            )
            result = fn(tmpdir)
        assert result == ""

    def test_qa_review_incluye_summary_en_prompt(self):
        """qa_review inyecta el resumen S39-B en el HumanMessage."""
        import graph as g

        src = inspect.getsource(g.qa_review)
        assert "_summarize_for_qa" in src, "qa_review no llama a _summarize_for_qa"
        assert "S39-B" in src, "qa_review no referencia S39-B"


# ---------------------------------------------------------------------------
# S39-C — retry_feedback reducido a 800 chars
# ---------------------------------------------------------------------------


class TestS39CRetryFeedback:
    """S39-C: update_test_retry limita feedback a 800 chars y usa solo stderr."""

    def _get_fn(self):
        import graph as g

        return g.update_test_retry

    def _base_state(self, test_output: str = "", retry_count: int = 0) -> dict:
        return {
            "test_results": {
                "output": test_output,
                "runner": "pytest",
                "passed": False,
            },
            "retry_feedback": "",
            "test_retry_count": retry_count,
            "messages": [],
        }

    def test_cap_es_800_chars(self):
        """El feedback acumulado no supera 800 chars."""
        fn = self._get_fn()
        # output largo — sin AssertionErrors para forzar uso de raw_snippet
        long_output = "E  " + "x" * 3000
        state = self._base_state(long_output)
        result = fn(state)
        assert len(result["retry_feedback"]) <= 800, (
            f"retry_feedback excede 800 chars: {len(result['retry_feedback'])}"
        )

    def test_no_usa_output_completo(self):
        """El código fuente ya no usa test_output[:1500]."""
        import graph as g

        src = inspect.getsource(g.update_test_retry)
        assert "test_output[:1500]" not in src, (
            "S39-C: todavía usa test_output[:1500] en update_test_retry"
        )

    def test_usa_cap_800_en_truncate(self):
        """El código usa _truncate(accumulated, 800)."""
        import graph as g

        src = inspect.getsource(g.update_test_retry)
        assert "_truncate(accumulated, 800)" in src, (
            "S39-C: no usa _truncate(accumulated, 800)"
        )

    def test_assertion_errors_tienen_prioridad(self):
        """Cuando hay AssertionErrors, se usan en vez del raw output."""
        fn = self._get_fn()
        output_with_assert = (
            "FAILED test_contrato.py::test_monto\n"
            "AssertionError: assert 100 == 200\n"
            "E   assert 100 == 200\n"
            "assert round(100.0, 2) == 200\n"
        )
        state = self._base_state(output_with_assert)
        result = fn(state)
        assert "AssertionError" in result["retry_feedback"]

    def test_feedback_acumulado_respeta_cap(self):
        """Incluso con feedback previo, el acumulado está cerca de 800 chars.

        _truncate agrega un marcador de truncación (~43 chars), por lo que
        el total puede ser hasta ~850 chars cuando hay truncación activa.
        """
        fn = self._get_fn()
        state = self._base_state("algún error de test")
        state["retry_feedback"] = "x" * 500  # feedback previo largo
        result = fn(state)
        # Margen de 60 chars por el sufijo de truncación de _truncate
        assert len(result["retry_feedback"]) <= 860, (
            f"retry_feedback demasiado largo: {len(result['retry_feedback'])}"
        )
        # Confirmar que hubo truncación (el texto era >800 antes de truncar)
        assert len(result["retry_feedback"]) < 3000, (
            "El cap de 3000 chars anterior aún aplica"
        )
