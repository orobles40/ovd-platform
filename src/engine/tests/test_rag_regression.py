"""
OVD Platform — Tests de regresión RAG + S17T (R-01, R-02)
Copyright 2026 Omar Robles

Contratos inmutables que NUNCA deben romperse:
  R-01: retrieve_context() retorna str, nunca lanza, funciona con RAG off
  R-02: make_file_tools() retorna exactamente 4 tools con nombres correctos
  R-03: index_chunks() acepta lista vacía sin error
  R-04: rag.py y rag_seed.py importan sin infraestructura activa
  R-05: bootstrap.run() acepta llamadas sin bridge_url ni jwt_token
"""
import sys
import os
import tempfile
import pathlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".."))

import pytest


# ---------------------------------------------------------------------------
# R-01 — retrieve_context: contrato de estabilidad
# ---------------------------------------------------------------------------

class TestRetrieveContextContract:
    """R-01: retrieve_context() es siempre seguro de llamar."""

    def test_retorna_string_con_rag_off(self, monkeypatch):
        import rag_seed
        monkeypatch.setattr(rag_seed, "RAG_ENABLED", False)
        result = rag_seed.retrieve_context("cualquier query", "o1", "p1")
        assert isinstance(result, str)

    def test_retorna_string_con_rag_on_y_db_caida(self, monkeypatch):
        import rag_seed, rag
        monkeypatch.setattr(rag_seed, "RAG_ENABLED", True)
        monkeypatch.setattr(rag, "_DATABASE_URL", "postgresql://x@localhost:9999/db")
        result = rag_seed.retrieve_context("query", "o1", "p1")
        assert isinstance(result, str)

    def test_nunca_lanza_con_project_id_vacio(self, monkeypatch):
        import rag_seed
        monkeypatch.setattr(rag_seed, "RAG_ENABLED", False)
        result = rag_seed.retrieve_context("query", "o1", "")
        assert isinstance(result, str)

    def test_nunca_lanza_con_query_vacia(self, monkeypatch):
        import rag_seed
        monkeypatch.setattr(rag_seed, "RAG_ENABLED", False)
        result = rag_seed.retrieve_context("", "o1", "p1")
        assert isinstance(result, str)

    def test_acepta_llamada_sin_jwt_token(self, monkeypatch):
        import rag_seed
        monkeypatch.setattr(rag_seed, "RAG_ENABLED", False)
        # Firma: retrieve_context(query, org_id, project_id, jwt_token="")
        result = rag_seed.retrieve_context("query", "o1", "p1")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# R-02 — make_file_tools: contrato S17T
# ---------------------------------------------------------------------------

class TestMakeFileToolsContract:
    """R-02: make_file_tools() retorna exactamente 4 tools con nombres correctos."""

    EXPECTED_NAMES = {"write_file", "read_file", "edit_file", "list_files"}

    def test_retorna_exactamente_4_tools(self):
        from tools.file_tools import make_file_tools
        with tempfile.TemporaryDirectory() as d:
            tools = make_file_tools(d)
        assert len(tools) == 4

    def test_nombres_exactos(self):
        from tools.file_tools import make_file_tools
        with tempfile.TemporaryDirectory() as d:
            tools = make_file_tools(d)
        assert {t.name for t in tools} == self.EXPECTED_NAMES

    def test_directorio_inexistente_retorna_lista_vacia(self):
        from tools.file_tools import make_file_tools
        tools = make_file_tools("/ruta/ovd-regression-test-no-existe")
        assert tools == []

    def test_directorio_vacio_string_retorna_lista_vacia(self):
        from tools.file_tools import make_file_tools
        tools = make_file_tools("")
        assert tools == []

    def test_cada_tool_tiene_descripcion(self):
        from tools.file_tools import make_file_tools
        with tempfile.TemporaryDirectory() as d:
            tools = make_file_tools(d)
        for t in tools:
            assert t.description, f"Tool '{t.name}' sin descripción"


# ---------------------------------------------------------------------------
# R-03 — index_chunks: lista vacía
# ---------------------------------------------------------------------------

class TestIndexChunksEmptyList:
    """R-03: index_chunks() con lista vacía retorna 0 sin error."""

    def test_lista_vacia_retorna_cero(self, monkeypatch):
        import rag
        monkeypatch.setattr(rag, "_DATABASE_URL", "postgresql://x@localhost/db")
        result = rag.index_chunks([], project_id="p1", org_id="o1")
        assert result == 0

    def test_lista_vacia_no_llama_al_store(self, monkeypatch):
        import rag
        monkeypatch.setattr(rag, "_DATABASE_URL", "postgresql://x@localhost/db")
        mock_store = MagicMock()
        monkeypatch.setattr(rag, "_get_store", lambda pid: mock_store)
        rag.index_chunks([], project_id="p1", org_id="o1")
        mock_store.add_documents.assert_not_called()


# ---------------------------------------------------------------------------
# R-04 — Imports sin infraestructura
# ---------------------------------------------------------------------------

class TestImportsWithoutInfra:
    """R-04: Los módulos RAG importan correctamente sin DB ni Ollama activos."""

    def test_rag_importa(self):
        import rag
        assert hasattr(rag, "index_chunks")
        assert hasattr(rag, "search")
        assert hasattr(rag, "index_chunks_async")
        assert hasattr(rag, "search_async")

    def test_rag_seed_importa(self):
        import rag_seed
        assert hasattr(rag_seed, "retrieve_context")
        assert hasattr(rag_seed, "seed_project")
        assert hasattr(rag_seed, "seed_from_file")

    def test_chunkers_importa(self):
        from knowledge.chunkers import get_chunks, chunk_codebase, chunk_doc
        assert callable(get_chunks)
        assert callable(chunk_codebase)
        assert callable(chunk_doc)

    def test_bootstrap_importa(self):
        from knowledge.bootstrap import run, BootstrapResult
        assert callable(run)


# ---------------------------------------------------------------------------
# R-05 — bootstrap.run() sin bridge_url ni jwt_token
# ---------------------------------------------------------------------------

class TestBootstrapBackwardsCompatibility:
    """R-05: bootstrap.run() funciona sin los parámetros legacy del Bridge."""

    @pytest.mark.asyncio
    async def test_run_sin_bridge_url(self, tmp_path, monkeypatch):
        from knowledge import bootstrap
        (tmp_path / "doc.md").write_text("## Test\nContenido.\n", encoding="utf-8")
        monkeypatch.setattr("rag.index_chunks_async", AsyncMock(return_value=1))

        # No pasar bridge_url — debe funcionar igual
        result = await bootstrap.run(
            org_id="o1", project_id="p1",
            source_path=tmp_path, doc_type="doc",
        )
        assert result.failed == 0

    @pytest.mark.asyncio
    async def test_run_con_parametros_legacy_ignorados(self, tmp_path, monkeypatch):
        from knowledge import bootstrap
        (tmp_path / "doc.md").write_text("## Test\nContenido.\n", encoding="utf-8")
        monkeypatch.setattr("rag.index_chunks_async", AsyncMock(return_value=1))

        # Pasar bridge_url y jwt_token (legacy) — deben ignorarse sin error
        result = await bootstrap.run(
            org_id="o1", project_id="p1",
            source_path=tmp_path, doc_type="doc",
            bridge_url="http://localhost:3000",
            jwt_token="eyJfake",
        )
        assert isinstance(result.indexed, int)


# Importar MagicMock aquí porque R-03 lo usa
from unittest.mock import MagicMock, AsyncMock
