"""
OVD Platform — Tests S47 (background graph + early cycle registration + templates)

S47-A: Background asyncio.Task separa ejecución del grafo del SSE
S47-B: Registro temprano de ciclos (started → completed/failed)
S47-C: Templates devops/sdd con restricciones explícitas
"""
import sys, os, asyncio, json, pathlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _devops_template() -> str:
    path = pathlib.Path(__file__).parent.parent / "templates" / "system_devops.md"
    return path.read_text()


def _sdd_template() -> str:
    path = pathlib.Path(__file__).parent.parent / "templates" / "system_sdd.md"
    return path.read_text()


# ---------------------------------------------------------------------------
# S47-A — Background graph task
# ---------------------------------------------------------------------------

class TestS47ABackgroundTask:

    def test_global_dicts_exist_in_api(self):
        """S47-A1: _graph_tasks, _event_queues, _stream_done existen en api.py."""
        import api
        assert hasattr(api, "_graph_tasks"), "_graph_tasks no está definido en api"
        assert hasattr(api, "_event_queues"), "_event_queues no está definido en api"
        assert hasattr(api, "_stream_done"), "_stream_done no está definido en api"

    def test_global_dicts_are_correct_types(self):
        """S47-A1: las estructuras globales son dict."""
        import api
        assert isinstance(api._graph_tasks, dict)
        assert isinstance(api._event_queues, dict)
        assert isinstance(api._stream_done, dict)

    @pytest.mark.asyncio
    async def test_deferred_cleanup_removes_queue(self):
        """S47-A2: _deferred_cleanup elimina queue y done_event tras el delay."""
        import api
        thread_id = "test-cleanup-001"
        api._event_queues[thread_id] = asyncio.Queue()
        api._stream_done[thread_id] = asyncio.Event()

        # delay muy pequeño para el test
        await api._deferred_cleanup(thread_id, delay=0.01)

        assert thread_id not in api._event_queues
        assert thread_id not in api._stream_done

    @pytest.mark.asyncio
    async def test_deferred_cleanup_idempotent(self):
        """S47-A2: _deferred_cleanup no falla si thread_id ya fue limpiado."""
        import api
        thread_id = "test-cleanup-002"
        # No agregamos nada — debe ser silencioso
        await api._deferred_cleanup(thread_id, delay=0.0)
        assert thread_id not in api._event_queues

    @pytest.mark.asyncio
    async def test_background_task_puts_error_on_already_running(self):
        """S47-A3: AlreadyRunningError produce evento 'error' en la queue."""
        import api
        from task_checkout import AlreadyRunningError

        thread_id = "test-bg-already-001"
        api._event_queues[thread_id] = asyncio.Queue(maxsize=100)
        api._stream_done[thread_id] = asyncio.Event()

        with patch("api.SessionLock") as mock_lock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(side_effect=AlreadyRunningError("ya corre"))
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_lock_cls.return_value = mock_ctx

            config = {"configurable": {"thread_id": thread_id}}
            await api._run_graph_background(thread_id, config)

        assert not api._event_queues[thread_id].empty()
        event = api._event_queues[thread_id].get_nowait()
        # El evento SSE es bytes — decodificar para inspeccionar
        text = event.decode() if isinstance(event, bytes) else str(event)
        assert "error" in text.lower() or "Ciclo ya en ejecución" in text

        # Limpieza
        api._event_queues.pop(thread_id, None)
        api._stream_done.pop(thread_id, None)


# ---------------------------------------------------------------------------
# S47-B — Early cycle registration
# ---------------------------------------------------------------------------

class TestS47BEarlyCycleRegistration:

    @pytest.mark.asyncio
    async def test_ensure_cycle_registered_skips_when_no_db_url(self):
        """S47-B1: _ensure_cycle_registered no falla si DATABASE_URL está vacía."""
        import api
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            # No debe lanzar excepción
            await api._ensure_cycle_registered("thread-no-db", {"configurable": {"thread_id": "thread-no-db"}})

    @pytest.mark.asyncio
    async def test_ensure_cycle_registered_skips_completed(self):
        """S47-B2: _ensure_cycle_registered no sobrescribe ciclo ya completado."""
        import api

        mock_conn = AsyncMock()
        mock_cur = AsyncMock()
        mock_cur.fetchone = AsyncMock(return_value=("completed",))
        mock_conn.execute = AsyncMock(return_value=mock_cur)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)

        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test"}):
            with patch("api.psycopg") as mock_psycopg:
                mock_psycopg.AsyncConnection.connect = AsyncMock(return_value=mock_conn)
                with patch("api._graph", None):
                    await api._ensure_cycle_registered(
                        "thread-completed",
                        {"configurable": {"thread_id": "thread-completed"}},
                    )

        # Si ya está 'completed', no debe hacer UPDATE
        for call in mock_conn.execute.call_args_list:
            sql = str(call)
            assert "UPDATE ovd_cycles" not in sql or "failed" not in sql, \
                "_ensure_cycle_registered no debe actualizar ciclos completados"

    def test_session_create_has_started_insert(self):
        """S47-B3: api.py contiene INSERT con status='started' en session_create."""
        api_path = pathlib.Path(__file__).parent.parent / "api.py"
        content = api_path.read_text()
        assert "'started'" in content, "Falta INSERT con status='started' en api.py"
        assert "ON CONFLICT (thread_id) DO NOTHING" in content, \
            "Falta ON CONFLICT (thread_id) DO NOTHING en api.py"

    def test_graph_deliver_has_upsert_completed(self):
        """S47-B4: graph.py deliver usa ON CONFLICT (thread_id) DO UPDATE con status='completed'."""
        graph_path = pathlib.Path(__file__).parent.parent / "graph.py"
        content = graph_path.read_text()
        assert "ON CONFLICT (thread_id) DO UPDATE SET" in content, \
            "graph.py deliver debe tener UPSERT con ON CONFLICT (thread_id)"
        assert "status         = 'completed'" in content or "status = 'completed'" in content, \
            "graph.py deliver debe establecer status='completed'"

    def test_graph_deliver_no_conflict_id_only(self):
        """S47-B4: graph.py deliver ya no usa ON CONFLICT (id) DO NOTHING."""
        graph_path = pathlib.Path(__file__).parent.parent / "graph.py"
        content = graph_path.read_text()
        assert "ON CONFLICT (id) DO NOTHING" not in content, \
            "graph.py deliver aún usa el conflicto antiguo por id — debe ser thread_id"


# ---------------------------------------------------------------------------
# S47-C — Templates
# ---------------------------------------------------------------------------

class TestS47CDevopsTemplate:

    def test_devops_prohibits_py_files(self):
        """S47-C1: system_devops.md prohíbe generar archivos .py."""
        content = _devops_template()
        assert ".py" in content and "NUNCA" in content, \
            "system_devops.md debe prohibir explícitamente archivos .py"

    def test_devops_prohibits_oracle_container(self):
        """S47-C2: system_devops.md prohíbe Dockerfile.oracle."""
        content = _devops_template()
        assert "Dockerfile.oracle" in content or "Oracle" in content, \
            "system_devops.md debe mencionar la restricción sobre contenedores Oracle"
        assert "NUNCA" in content

    def test_devops_has_external_db_section(self):
        """S47-C3: system_devops.md tiene sección para BD externas con host.docker.internal."""
        content = _devops_template()
        assert "host.docker.internal" in content, \
            "system_devops.md debe indicar cómo conectar a BD externas"

    def test_devops_defines_exclusive_output(self):
        """S47-C4: system_devops.md especifica que su output es EXCLUSIVAMENTE infraestructura."""
        content = _devops_template()
        assert "EXCLUSIVAMENTE" in content or "exclusivamente" in content, \
            "system_devops.md debe aclarar qué archivos puede generar"

    def test_devops_prohibits_business_logic_scripts(self):
        """S47-C5: system_devops.md prohíbe scripts con lógica de negocio."""
        content = _devops_template()
        assert "lógica de negocio" in content or "logica de negocio" in content, \
            "system_devops.md debe prohibir scripts con lógica de negocio"


class TestS47CSddTemplate:

    def test_sdd_has_prohibited_devops_artifacts(self):
        """S47-C6: system_sdd.md contiene sección de artefactos PROHIBIDOS para devops."""
        content = _sdd_template()
        assert "PROHIBIDOS" in content or "Artefactos PROHIBIDOS" in content, \
            "system_sdd.md debe tener sección de artefactos prohibidos para devops"

    def test_sdd_prohibits_validate_scripts(self):
        """S47-C7: system_sdd.md prohíbe scripts validate-*.sh con lógica de negocio."""
        content = _sdd_template()
        assert "validate" in content.lower() and ("PROHIBIDO" in content or "prohibido" in content.lower()), \
            "system_sdd.md debe prohibir scripts de validación como artefactos devops"

    def test_sdd_prohibits_dockerfile_db(self):
        """S47-C8: system_sdd.md prohíbe Dockerfile.oracle / Dockerfile.db."""
        content = _sdd_template()
        assert "Dockerfile.oracle" in content or "Dockerfile.db" in content, \
            "system_sdd.md debe mencionar Dockerfile.oracle o Dockerfile.db como artefactos prohibidos"

    def test_sdd_clarifies_src_belongs_to_backend_frontend(self):
        """S47-C9: system_sdd.md aclara que src/ es territorio de backend/frontend."""
        content = _sdd_template()
        assert "src/" in content and ("backend" in content or "frontend" in content), \
            "system_sdd.md debe indicar que src/ pertenece a backend/frontend, no a devops"
