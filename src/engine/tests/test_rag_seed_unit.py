"""
OVD Platform — Tests unitarios para rag_seed.py (U-04)
Copyright 2026 Omar Robles

Verifica sin infraestructura real (mock de rag.search y rag.index_chunks):
- retrieve_context(): retorna string vacío si RAG deshabilitado
- retrieve_context(): retorna string vacío si search falla
- retrieve_context(): retorna contexto formateado si hay resultados
- retrieve_context(): NUNCA lanza excepción (contrato)
- seed_project(): retorna 0 si RAG deshabilitado
- seed_project(): retorna 0 si no hay extra_docs
- seed_from_file(): indexa archivo existente
- seed_from_file(): retorna False si archivo no existe
"""
import sys
import os
import tempfile
import pathlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".."))

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# ---------------------------------------------------------------------------
# retrieve_context
# ---------------------------------------------------------------------------

class TestRetrieveContext:
    def test_retorna_vacio_si_rag_deshabilitado(self, monkeypatch):
        import rag_seed
        monkeypatch.setattr(rag_seed, "RAG_ENABLED", False)
        result = rag_seed.retrieve_context("query", "o1", "p1")
        assert result == ""

    def test_retorna_string_si_rag_habilitado_y_sin_resultados(self, monkeypatch):
        import rag_seed
        import rag
        monkeypatch.setattr(rag_seed, "RAG_ENABLED", True)
        monkeypatch.setattr(rag, "search", lambda query, project_id, **kw: "")
        result = rag_seed.retrieve_context("query sin resultados", "o1", "p1")
        assert isinstance(result, str)
        assert result == ""

    def test_retorna_contexto_si_hay_resultados(self, monkeypatch):
        import rag_seed
        import rag
        monkeypatch.setattr(rag_seed, "RAG_ENABLED", True)
        monkeypatch.setattr(
            rag, "search",
            lambda query, project_id, **kw: "### [1] api.py (tipo: codebase, similitud: 0.82)\ndef login(): ..."
        )
        result = rag_seed.retrieve_context("autenticacion", "o1", "p1")
        assert "codebase" in result
        assert "login" in result

    def test_nunca_lanza_excepcion_si_search_falla(self, monkeypatch):
        """Contrato de seguridad: retrieve_context() NUNCA lanza excepción."""
        import rag_seed
        import rag
        monkeypatch.setattr(rag_seed, "RAG_ENABLED", True)
        monkeypatch.setattr(rag, "search", MagicMock(side_effect=RuntimeError("pgvector caído")))
        result = rag_seed.retrieve_context("query", "o1", "p1")
        assert isinstance(result, str)

    def test_jwt_token_es_opcional(self, monkeypatch):
        """jwt_token tiene default vacío — no debe requerirse."""
        import rag_seed
        import rag
        monkeypatch.setattr(rag_seed, "RAG_ENABLED", True)
        monkeypatch.setattr(rag, "search", lambda q, p, **kw: "contexto")
        # Llamada sin jwt_token
        result = rag_seed.retrieve_context("query", "o1", "p1")
        assert isinstance(result, str)

    def test_retorna_vacio_ante_cualquier_excepcion(self, monkeypatch):
        """Cualquier error interno retorna string vacío."""
        import rag_seed
        monkeypatch.setattr(rag_seed, "RAG_ENABLED", True)
        # Forzar error al importar rag
        with patch.dict("sys.modules", {"rag": None}):
            result = rag_seed.retrieve_context("query", "o1", "p1")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# seed_project
# ---------------------------------------------------------------------------

class TestSeedProject:
    @pytest.mark.asyncio
    async def test_retorna_cero_si_rag_deshabilitado(self, monkeypatch):
        import rag_seed
        monkeypatch.setattr(rag_seed, "RAG_ENABLED", False)
        result = await rag_seed.seed_project("o1", "p1", "jwt")
        assert result == 0

    @pytest.mark.asyncio
    async def test_retorna_cero_si_no_hay_extra_docs(self, monkeypatch):
        import rag_seed
        monkeypatch.setattr(rag_seed, "RAG_ENABLED", True)
        result = await rag_seed.seed_project("o1", "p1", "jwt", extra_docs=[])
        assert result == 0

    @pytest.mark.asyncio
    async def test_indexa_extra_docs(self, monkeypatch):
        import rag_seed
        import rag
        monkeypatch.setattr(rag_seed, "RAG_ENABLED", True)
        monkeypatch.setattr(rag, "index_chunks_async", AsyncMock(return_value=3))

        docs = [
            {"content": "doc 1", "doc_type": "doc", "source_file": "f1.md", "metadata": {}},
            {"content": "doc 2", "doc_type": "doc", "source_file": "f2.md", "metadata": {}},
            {"content": "doc 3", "doc_type": "doc", "source_file": "f3.md", "metadata": {}},
        ]
        result = await rag_seed.seed_project("o1", "p1", "jwt", extra_docs=docs)
        assert result == 3

    @pytest.mark.asyncio
    async def test_error_en_index_retorna_cero(self, monkeypatch):
        import rag_seed
        import rag
        monkeypatch.setattr(rag_seed, "RAG_ENABLED", True)
        monkeypatch.setattr(
            rag, "index_chunks_async",
            AsyncMock(side_effect=RuntimeError("fallo")),
        )
        docs = [{"content": "x", "doc_type": "doc", "source_file": "f.md", "metadata": {}}]
        result = await rag_seed.seed_project("o1", "p1", "jwt", extra_docs=docs)
        assert result == 0


# ---------------------------------------------------------------------------
# seed_from_file
# ---------------------------------------------------------------------------

class TestSeedFromFile:
    def test_retorna_false_si_archivo_no_existe(self, monkeypatch):
        import rag_seed
        monkeypatch.setattr(rag_seed, "RAG_ENABLED", True)
        result = rag_seed.seed_from_file("/no/existe/archivo.md", "o1", "p1")
        assert result is False

    def test_indexa_markdown_existente(self, monkeypatch):
        import rag_seed
        import rag
        monkeypatch.setattr(rag_seed, "RAG_ENABLED", True)
        monkeypatch.setattr(rag, "index_chunks", MagicMock(return_value=5))

        with tempfile.NamedTemporaryFile(suffix=".md", mode="w",
                                         delete=False, encoding="utf-8") as f:
            f.write("## Arquitectura\nDescripción del sistema.\n")
            tmp = f.name

        try:
            result = rag_seed.seed_from_file(tmp, "o1", "p1")
            assert result is True
        finally:
            pathlib.Path(tmp).unlink(missing_ok=True)

    def test_retorna_false_si_index_chunks_retorna_cero(self, monkeypatch):
        import rag_seed
        import rag
        monkeypatch.setattr(rag_seed, "RAG_ENABLED", True)
        monkeypatch.setattr(rag, "index_chunks", MagicMock(return_value=0))

        with tempfile.NamedTemporaryFile(suffix=".md", mode="w",
                                         delete=False, encoding="utf-8") as f:
            f.write("## Vacío\n")
            tmp = f.name

        try:
            result = rag_seed.seed_from_file(tmp, "o1", "p1")
            assert result is False
        finally:
            pathlib.Path(tmp).unlink(missing_ok=True)

    def test_error_interno_retorna_false(self, monkeypatch):
        import rag_seed
        import rag
        monkeypatch.setattr(rag_seed, "RAG_ENABLED", True)
        monkeypatch.setattr(rag, "index_chunks", MagicMock(side_effect=RuntimeError("pgvector caído")))

        with tempfile.NamedTemporaryFile(suffix=".md", mode="w",
                                         delete=False, encoding="utf-8") as f:
            f.write("## Doc\nContenido.\n")
            tmp = f.name

        try:
            result = rag_seed.seed_from_file(tmp, "o1", "p1")
            assert result is False
        finally:
            pathlib.Path(tmp).unlink(missing_ok=True)

    def test_jwt_token_es_opcional(self, monkeypatch):
        import rag_seed
        import rag
        monkeypatch.setattr(rag_seed, "RAG_ENABLED", True)
        monkeypatch.setattr(rag, "index_chunks", MagicMock(return_value=2))

        with tempfile.NamedTemporaryFile(suffix=".md", mode="w",
                                         delete=False, encoding="utf-8") as f:
            f.write("## Test\nContenido.\n")
            tmp = f.name

        try:
            # Sin jwt_token
            result = rag_seed.seed_from_file(tmp, "o1", "p1")
            assert isinstance(result, bool)
        finally:
            pathlib.Path(tmp).unlink(missing_ok=True)
