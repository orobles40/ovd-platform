"""
OVD Platform — Tests S96-H: RAG actualizado

H1: rag.clear_project_chunks() existe y funciona
H2: _index_sdd_for_rag() existe y se llama en deliver
H3: session-close SKILL.md usa rag_bootstrap.py (no curl con Bearer)
"""

import os
import pathlib
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import graph
import rag

# ---------------------------------------------------------------------------
# H1 — clear_project_chunks
# ---------------------------------------------------------------------------


def test_h1_clear_project_chunks_exists():
    """H1: rag.clear_project_chunks() existe y acepta project_id."""
    assert hasattr(rag, "clear_project_chunks"), (
        "rag.py debe exportar clear_project_chunks (S96-H1)"
    )
    sig = inspect.signature(rag.clear_project_chunks)
    assert "project_id" in sig.parameters


def test_h1_clear_project_chunks_returns_int_on_no_db():
    """H1: retorna 0 cuando DATABASE_URL no está definida."""
    with patch.object(rag, "_DATABASE_URL", ""):
        result = rag.clear_project_chunks("test-project")
    assert result == 0


def test_h1_clear_project_chunks_uses_pgvector_collection():
    """H1: construye el nombre de colección con prefijo ovd_project_."""
    calls = []

    class FakeConn:
        def execute(self, sql, params):
            calls.append((sql, params))
            cur = MagicMock()
            cur.rowcount = 42
            return cur

        def commit(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    with (
        patch.object(rag, "_DATABASE_URL", "postgresql://x:y@localhost/db"),
        patch("psycopg.connect", return_value=FakeConn()),
    ):
        result = rag.clear_project_chunks("mi-proyecto")

    assert result == 42
    assert calls, "debe llamar a execute"
    sql, params = calls[0]
    assert "langchain_pg_embedding" in sql
    assert params == ("ovd_project_mi-proyecto",)


# ---------------------------------------------------------------------------
# H2 — _index_sdd_for_rag en graph.py
# ---------------------------------------------------------------------------


def test_h2_index_sdd_for_rag_exists():
    """H2: graph._index_sdd_for_rag existe y es coroutine."""
    import asyncio

    assert hasattr(graph, "_index_sdd_for_rag"), (
        "graph.py debe exportar _index_sdd_for_rag (S96-H2)"
    )
    assert asyncio.iscoroutinefunction(graph._index_sdd_for_rag), (
        "_index_sdd_for_rag debe ser async"
    )


def test_h2_index_sdd_for_rag_skips_empty_sdd():
    """H2: no indexa si el SDD está vacío."""
    import asyncio

    state = {"sdd": None, "project_id": "proj", "org_id": "org"}
    with patch("rag.index_chunks_async", new_callable=AsyncMock) as mock_index:
        asyncio.run(graph._index_sdd_for_rag(state))
    mock_index.assert_not_called()


def test_h2_index_sdd_for_rag_indexes_valid_sdd():
    """H2: indexa un SDD válido como chunk tipo 'delivery'."""
    import asyncio

    state = {
        "sdd": {"summary": "API REST", "tasks": []},
        "project_id": "proj-001",
        "org_id": "org-001",
        "session_id": "abc12345-def",
        "feature_request": "Crear endpoint de login",
        "qa_result": {"score": 90},
        "fr_analysis": {"type": "feature", "complexity": "medium"},
    }

    with patch(
        "rag.index_chunks_async", new_callable=AsyncMock, return_value=1
    ) as mock_index:
        asyncio.run(graph._index_sdd_for_rag(state))

    mock_index.assert_called_once()
    chunks_arg = mock_index.call_args[0][0]
    assert len(chunks_arg) == 1
    chunk = chunks_arg[0]
    assert chunk["doc_type"] == "delivery"
    assert "API REST" in chunk["content"] or "Crear endpoint" in chunk["content"]
    assert chunk["metadata"]["qa_score"] == 90
    assert chunk["metadata"]["session_id"] == "abc12345-def"


def test_h2_index_sdd_skips_when_rag_disabled():
    """H2: respeta OVD_RAG_ENABLED=false."""
    import asyncio

    state = {
        "sdd": {"summary": "algo"},
        "project_id": "proj",
        "org_id": "org",
        "session_id": "x",
        "feature_request": "test",
    }
    with (
        patch.dict(os.environ, {"OVD_RAG_ENABLED": "false"}),
        patch("rag.index_chunks_async", new_callable=AsyncMock) as mock_index,
    ):
        asyncio.run(graph._index_sdd_for_rag(state))

    mock_index.assert_not_called()


def test_h2_deliver_calls_index_sdd(tmp_path):
    """H2: _index_sdd_for_rag se invoca como task en deliver."""
    # Verificar que deliver crea el task de _index_sdd_for_rag
    # Buscamos la referencia en el código fuente de graph.py
    graph_src = pathlib.Path(__file__).parent.parent / "graph.py"
    content = graph_src.read_text(encoding="utf-8")
    assert "_index_sdd_for_rag" in content, (
        "graph.py debe referenciar _index_sdd_for_rag (S96-H2)"
    )
    assert "asyncio.create_task(_index_sdd_for_rag" in content, (
        "deliver debe lanzar _index_sdd_for_rag como fire-and-forget task"
    )


# ---------------------------------------------------------------------------
# H3 — session-close usa rag_bootstrap.py
# ---------------------------------------------------------------------------


def test_h3_skill_md_uses_rag_bootstrap():
    """H3: SKILL.md del session-close usa rag_bootstrap.py, no curl con Bearer."""
    skill_md = (
        pathlib.Path(__file__).parent.parent.parent.parent
        / ".claude"
        / "skills"
        / "session-close"
        / "SKILL.md"
    )
    assert skill_md.exists(), "SKILL.md debe existir"
    content = skill_md.read_text(encoding="utf-8")

    assert "rag_bootstrap.py" in content, (
        "session-close SKILL.md debe referenciar rag_bootstrap.py (S96-H3)"
    )
    assert "Bearer $TOKEN" not in content, (
        "session-close SKILL.md no debe usar 'Bearer $TOKEN' para RAG — usar rag_bootstrap.py"
    )


def test_h3_rag_bootstrap_script_exists():
    """H3: src/engine/scripts/rag_bootstrap.py existe."""
    script = pathlib.Path(__file__).parent.parent / "scripts" / "rag_bootstrap.py"
    assert script.exists(), "scripts/rag_bootstrap.py debe existir (S96-H)"


def test_h3_rag_bootstrap_has_clear_flag():
    """H3: rag_bootstrap.py acepta --clear y --dry-run como argumentos."""
    script = pathlib.Path(__file__).parent.parent / "scripts" / "rag_bootstrap.py"
    content = script.read_text(encoding="utf-8")
    assert "--clear" in content, "rag_bootstrap.py debe soportar --clear"
    assert "--dry-run" in content, "rag_bootstrap.py debe soportar --dry-run"
    assert "clear_project_chunks" in content, (
        "rag_bootstrap.py debe llamar clear_project_chunks cuando --clear"
    )
