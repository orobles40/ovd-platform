"""
OVD Platform — Tests unitarios para rag.py (U-01)
Copyright 2026 Omar Robles

Verifica sin infraestructura real (sin PostgreSQL, sin Ollama):
- _get_connection_string(): conversión correcta de URL
- index_chunks(): manejo graceful cuando DB no disponible
- search(): retorna string vacío ante errores
- index_chunks_async() / search_async(): wrappers async funcionan
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock, patch, AsyncMock


# ---------------------------------------------------------------------------
# _get_connection_string
# ---------------------------------------------------------------------------

class TestGetConnectionString:
    """U-01.A — Conversión de DATABASE_URL al formato SQLAlchemy + psycopg2."""

    def _call(self, url: str) -> str:
        import rag
        original = rag._DATABASE_URL
        rag._DATABASE_URL = url
        result = rag._get_connection_string()
        rag._DATABASE_URL = original
        return result

    def test_postgresql_scheme_convertido(self):
        result = self._call("postgresql://user:pass@localhost:5432/db")
        assert result.startswith("postgresql+psycopg2://")

    def test_postgres_scheme_convertido(self):
        result = self._call("postgres://user:pass@localhost:5432/db")
        assert result.startswith("postgresql+psycopg2://")

    def test_ya_tiene_psycopg2_no_duplica(self):
        result = self._call("postgresql+psycopg2://user:pass@localhost:5432/db")
        assert result.count("psycopg2") == 1

    def test_preserva_credenciales_y_host(self):
        result = self._call("postgresql://ovd_dev:changeme@localhost:5432/ovd_dev")
        assert "ovd_dev:changeme@localhost:5432/ovd_dev" in result

    def test_string_vacio_no_lanza(self):
        result = self._call("")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# index_chunks — sin DB (DATABASE_URL vacía)
# ---------------------------------------------------------------------------

class TestIndexChunksWithoutDB:
    """U-01.B — index_chunks() no lanza excepción cuando DATABASE_URL no está."""

    def test_retorna_cero_sin_database_url(self, monkeypatch):
        import rag
        monkeypatch.setattr(rag, "_DATABASE_URL", "")
        result = rag.index_chunks(
            [{"content": "test", "doc_type": "doc",
              "source_file": "f.md", "metadata": {}}],
            project_id="p1",
            org_id="o1",
        )
        assert result == 0

    def test_lista_vacia_retorna_cero(self, monkeypatch):
        import rag
        monkeypatch.setattr(rag, "_DATABASE_URL", "postgresql://x@localhost/db")
        result = rag.index_chunks([], project_id="p1", org_id="o1")
        assert result == 0

    def test_error_de_conexion_retorna_cero(self, monkeypatch):
        import rag
        monkeypatch.setattr(rag, "_DATABASE_URL", "postgresql://x@localhost/db")

        def _store_raises(*a, **kw):
            raise RuntimeError("connection refused")

        monkeypatch.setattr(rag, "_get_store", _store_raises)
        result = rag.index_chunks(
            [{"content": "x", "doc_type": "doc", "source_file": "f.md", "metadata": {}}],
            project_id="p1",
            org_id="o1",
        )
        assert result == 0

    def test_chunks_multiples_procesados(self, monkeypatch):
        """Verifica que con mock de store, indexa el número correcto de chunks."""
        import rag
        monkeypatch.setattr(rag, "_DATABASE_URL", "postgresql://x@localhost/db")

        mock_store = MagicMock()
        mock_store.add_documents = MagicMock(return_value=None)
        monkeypatch.setattr(rag, "_get_store", lambda pid: mock_store)

        chunks = [
            {"content": f"chunk {i}", "doc_type": "doc",
             "source_file": "f.md", "metadata": {}}
            for i in range(5)
        ]
        result = rag.index_chunks(chunks, project_id="p1", org_id="o1")
        assert result == 5
        mock_store.add_documents.assert_called_once()

    def test_metadata_org_project_inyectada(self, monkeypatch):
        """Verifica que org_id y project_id se inyectan en los metadatos de cada doc."""
        import rag
        monkeypatch.setattr(rag, "_DATABASE_URL", "postgresql://x@localhost/db")

        docs_capturados = []

        mock_store = MagicMock()
        def _capture_docs(docs):
            docs_capturados.extend(docs)
        mock_store.add_documents = _capture_docs
        monkeypatch.setattr(rag, "_get_store", lambda pid: mock_store)

        rag.index_chunks(
            [{"content": "hola", "doc_type": "codebase",
              "source_file": "api.py", "metadata": {"language": "python"}}],
            project_id="mi-proyecto",
            org_id="mi-org",
        )
        assert len(docs_capturados) == 1
        meta = docs_capturados[0].metadata
        assert meta["org_id"] == "mi-org"
        assert meta["project_id"] == "mi-proyecto"
        assert meta["doc_type"] == "codebase"
        assert meta["source_file"] == "api.py"
        assert meta["language"] == "python"


# ---------------------------------------------------------------------------
# search — sin DB
# ---------------------------------------------------------------------------

class TestSearchWithoutDB:
    """U-01.C — search() retorna string vacío ante errores o sin DB."""

    def test_retorna_vacio_sin_database_url(self, monkeypatch):
        import rag
        monkeypatch.setattr(rag, "_DATABASE_URL", "")
        result = rag.search("query test", project_id="p1")
        assert result == ""

    def test_retorna_vacio_si_store_lanza(self, monkeypatch):
        import rag
        monkeypatch.setattr(rag, "_DATABASE_URL", "postgresql://x@localhost/db")
        monkeypatch.setattr(rag, "_get_store", lambda pid: (_ for _ in ()).throw(RuntimeError("fail")))
        result = rag.search("query", project_id="p1")
        assert result == ""

    def test_retorna_vacio_si_sin_resultados(self, monkeypatch):
        import rag
        monkeypatch.setattr(rag, "_DATABASE_URL", "postgresql://x@localhost/db")

        mock_store = MagicMock()
        mock_store.similarity_search_with_relevance_scores = MagicMock(return_value=[])
        monkeypatch.setattr(rag, "_get_store", lambda pid: mock_store)

        result = rag.search("query sin resultados", project_id="p1")
        assert result == ""

    def test_retorna_vacio_si_score_bajo(self, monkeypatch):
        import rag
        from langchain_core.documents import Document
        monkeypatch.setattr(rag, "_DATABASE_URL", "postgresql://x@localhost/db")
        monkeypatch.setattr(rag, "_MIN_SCORE", 0.65)

        mock_store = MagicMock()
        doc = Document(page_content="contenido", metadata={"doc_type": "doc", "source_file": "f.md"})
        mock_store.similarity_search_with_relevance_scores = MagicMock(
            return_value=[(doc, 0.3)]  # score < MIN_SCORE
        )
        monkeypatch.setattr(rag, "_get_store", lambda pid: mock_store)

        result = rag.search("query", project_id="p1")
        assert result == ""

    def test_retorna_contexto_formateado_si_score_suficiente(self, monkeypatch):
        import rag
        from langchain_core.documents import Document
        monkeypatch.setattr(rag, "_DATABASE_URL", "postgresql://x@localhost/db")
        monkeypatch.setattr(rag, "_MIN_SCORE", 0.65)

        mock_store = MagicMock()
        doc = Document(
            page_content="def factorial(n): ...",
            metadata={"doc_type": "codebase", "source_file": "math.py"},
        )
        mock_store.similarity_search_with_relevance_scores = MagicMock(
            return_value=[(doc, 0.85)]
        )
        monkeypatch.setattr(rag, "_get_store", lambda pid: mock_store)

        result = rag.search("factorial", project_id="p1")
        assert "factorial" in result
        assert "codebase" in result
        assert "math.py" in result
        assert "0.85" in result

    def test_resultado_es_siempre_string(self, monkeypatch):
        """Contrato: search() NUNCA retorna None."""
        import rag
        monkeypatch.setattr(rag, "_DATABASE_URL", "")
        result = rag.search("cualquier cosa", project_id="p1")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Wrappers async
# ---------------------------------------------------------------------------

class TestAsyncWrappers:
    """U-01.D — index_chunks_async y search_async delegan correctamente."""

    @pytest.mark.asyncio
    async def test_index_chunks_async_delega_a_sync(self, monkeypatch):
        import rag
        monkeypatch.setattr(rag, "index_chunks", lambda chunks, project_id, org_id: 7)
        result = await rag.index_chunks_async([], "p1", "o1")
        assert result == 7

    @pytest.mark.asyncio
    async def test_search_async_retorna_string(self, monkeypatch):
        import rag
        monkeypatch.setattr(rag, "_DATABASE_URL", "")
        result = await rag.search_async("test", "p1")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_search_async_retorna_string_ante_error(self, monkeypatch):
        import rag
        monkeypatch.setattr(rag, "_DATABASE_URL", "")
        result = await rag.search_async("test", "p1")
        assert isinstance(result, str)
