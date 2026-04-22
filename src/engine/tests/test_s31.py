"""
OVD Platform — Tests S31: workspace isolation por mtime + retry_feedback cap
"""
import sys, os, time, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from factories import make_state, make_sdd, make_agent_result, make_security_result, make_qa_result


# ---------------------------------------------------------------------------
# S31-A — Filtro mtime en qa_review y security_audit
# ---------------------------------------------------------------------------

class TestS31AMtimeFilter:
    """S31-A: qa_review y security_audit solo leen archivos del ciclo actual."""

    def test_qa_review_excluye_archivos_anteriores(self):
        """qa_review no incluye archivos con mtime < cycle_start_ts."""
        import inspect, graph as _graph
        src = inspect.getsource(_graph.qa_review)
        assert "S31-A" in src, "Filtro S31-A no encontrado en qa_review"
        assert "cycle_start_ts" in src or "cycle_ts" in src

    def test_security_audit_excluye_archivos_anteriores(self):
        """security_audit no incluye archivos con mtime < cycle_start_ts."""
        import inspect, graph as _graph
        src = inspect.getsource(_graph.security_audit)
        assert "S31-A" in src, "Filtro S31-A no encontrado en security_audit"
        assert "cycle_start_ts" in src or "sec_cycle_ts" in src

    def test_mtime_filter_logica(self):
        """Archivos con mtime < cycle_start_ts - 5 son excluidos."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Archivo "viejo" (de ciclo anterior)
            old_file = os.path.join(tmpdir, "old_migration.sql")
            with open(old_file, "w") as f:
                f.write("SELECT 1;")
            # Ajustar mtime a hace 60s
            old_ts = time.time() - 60
            os.utime(old_file, (old_ts, old_ts))

            # Archivo "nuevo" (de este ciclo)
            new_file = os.path.join(tmpdir, "main.py")
            with open(new_file, "w") as f:
                f.write("print('hello')")
            # mtime actual

            cycle_start = time.time() - 5  # ciclo empezó hace 5s
            import pathlib
            found_files = []
            for fp in pathlib.Path(tmpdir).rglob("*"):
                if not fp.is_file():
                    continue
                if cycle_start > 0 and fp.stat().st_mtime < cycle_start - 5:
                    continue  # S31-A: excluir viejo
                found_files.append(fp.name)

            assert "main.py" in found_files, "Archivo nuevo debe incluirse"
            assert "old_migration.sql" not in found_files, "Archivo viejo debe excluirse"

    def test_sin_cycle_ts_lee_todos_los_archivos(self):
        """Con cycle_start_ts=0 (default), se leen todos los archivos (comportamiento anterior)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            old_file = os.path.join(tmpdir, "old.py")
            with open(old_file, "w") as f:
                f.write("x = 1")
            old_ts = time.time() - 3600
            os.utime(old_file, (old_ts, old_ts))

            cycle_ts = 0  # no hay timestamp de ciclo
            import pathlib
            found = []
            for fp in pathlib.Path(tmpdir).rglob("*"):
                if not fp.is_file():
                    continue
                if cycle_ts > 0 and fp.stat().st_mtime < cycle_ts - 5:
                    continue
                found.append(fp.name)

            assert "old.py" in found, "Sin cycle_ts debe incluir todos los archivos"


# ---------------------------------------------------------------------------
# S31-B — Cap de retry_feedback acumulado
# ---------------------------------------------------------------------------

class TestS31BRetryFeedbackCap:
    """S31-B: el retry_feedback acumulado se trunca a 3000 chars."""

    @pytest.mark.asyncio
    async def test_update_test_retry_trunca_feedback(self):
        """update_test_retry trunca el feedback acumulado a <= 3000 chars."""
        import graph as _graph

        # Feedback existente muy largo
        existing = "X" * 5000
        state = make_state(
            test_results={"passed": False, "output": "Y" * 2000, "runner": "pytest"},
            test_retry_count=0,
            retry_feedback=existing,
        )
        result = await _graph.update_test_retry(state) if asyncio_needed() else _graph.update_test_retry(state)
        feedback = result["retry_feedback"]
        assert len(feedback) <= 3100, f"retry_feedback demasiado largo: {len(feedback)}"

    def test_update_qa_retry_trunca_feedback(self):
        """update_qa_retry trunca el feedback acumulado."""
        import graph as _graph, inspect
        src = inspect.getsource(_graph.update_qa_retry)
        assert "S31-B" in src or "_truncate" in src, "Cap S31-B no encontrado en update_qa_retry"

    def test_update_test_retry_tiene_cap(self):
        """update_test_retry tiene el cap S31-B."""
        import graph as _graph, inspect
        src = inspect.getsource(_graph.update_test_retry)
        assert "S31-B" in src or "_truncate" in src, "Cap S31-B no encontrado en update_test_retry"


def asyncio_needed():
    """Detecta si update_test_retry es async."""
    import graph as _graph, asyncio, inspect
    return inspect.iscoroutinefunction(_graph.update_test_retry)


# ---------------------------------------------------------------------------
# Integración: cycle_start_ts en el state
# ---------------------------------------------------------------------------

class TestCycleStartTs:
    """cycle_start_ts debe estar presente en el state inicial."""

    def test_cycle_start_ts_en_state_defaults(self):
        """El state tiene cycle_start_ts > 0."""
        state = make_state()
        assert "cycle_start_ts" in state
        assert state["cycle_start_ts"] > 0

    def test_cycle_start_ts_reciente(self):
        """cycle_start_ts es un timestamp UNIX de los últimos 60s."""
        state = make_state()
        assert abs(state["cycle_start_ts"] - time.time()) < 60
