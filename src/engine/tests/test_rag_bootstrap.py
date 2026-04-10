"""
OVD Platform — Tests unitarios para knowledge/bootstrap.py (U-03)
Copyright 2026 Omar Robles

Verifica sin infraestructura real (mock de rag.index_chunks_async):
- run(): dry_run no indexa, reporta chunks correctamente
- run(): lotes enviados según batch_size
- run(): errores en lotes se reportan sin propagar
- run(): ruta inexistente lanza FileNotFoundError
- BootstrapResult.summary() tiene el formato esperado
- bridge_url y jwt_token opcionales (compatibilidad)
"""
import sys
import os
import tempfile
import pathlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".."))

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_md(tmp_path):
    """Crea un directorio con un archivo markdown de prueba."""
    f = tmp_path / "doc.md"
    f.write_text("## Sección\nContenido de prueba para bootstrap.\n", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def tmp_py(tmp_path):
    """Crea un directorio con un archivo Python de prueba."""
    f = tmp_path / "mod.py"
    f.write_text("def hola():\n    return 'mundo'\n", encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# BootstrapResult
# ---------------------------------------------------------------------------

class TestBootstrapResult:
    def test_summary_formato(self):
        from knowledge.bootstrap import BootstrapResult
        r = BootstrapResult(
            doc_type="doc",
            source="/tmp/docs",
            total_chunks=10,
            indexed=8,
            failed=2,
            errors=["err1", "err2"],
        )
        s = r.summary()
        assert "8/10" in s
        assert "2 fallidos" in s
        assert "doc" in s


# ---------------------------------------------------------------------------
# run() — dry_run
# ---------------------------------------------------------------------------

class TestBootstrapRunDryRun:
    @pytest.mark.asyncio
    async def test_dry_run_no_indexa(self, tmp_md, monkeypatch):
        from knowledge import bootstrap
        mock_index = AsyncMock(return_value=0)
        monkeypatch.setattr("rag.index_chunks_async", mock_index)

        result = await bootstrap.run(
            org_id="o1", project_id="p1",
            source_path=tmp_md, doc_type="doc",
            dry_run=True,
        )
        mock_index.assert_not_called()
        assert result.indexed == 0
        assert result.total_chunks > 0

    @pytest.mark.asyncio
    async def test_dry_run_reporta_chunks_generados(self, tmp_py, monkeypatch):
        from knowledge import bootstrap
        monkeypatch.setattr("rag.index_chunks_async", AsyncMock(return_value=0))

        result = await bootstrap.run(
            org_id="o1", project_id="p1",
            source_path=tmp_py, doc_type="codebase",
            dry_run=True,
        )
        assert result.total_chunks >= 1
        assert result.failed == 0


# ---------------------------------------------------------------------------
# run() — indexación real (mock de rag)
# ---------------------------------------------------------------------------

class TestBootstrapRunIndexing:
    @pytest.mark.asyncio
    async def test_indexa_chunks_del_directorio(self, tmp_md, monkeypatch):
        from knowledge import bootstrap
        mock_index = AsyncMock(return_value=5)
        monkeypatch.setattr("rag.index_chunks_async", mock_index)

        result = await bootstrap.run(
            org_id="o1", project_id="p1",
            source_path=tmp_md, doc_type="doc",
        )
        assert mock_index.called
        assert result.indexed > 0

    @pytest.mark.asyncio
    async def test_bridge_url_y_jwt_token_opcionales(self, tmp_md, monkeypatch):
        """Compatibilidad: run() funciona sin bridge_url y jwt_token."""
        from knowledge import bootstrap
        monkeypatch.setattr("rag.index_chunks_async", AsyncMock(return_value=3))

        result = await bootstrap.run(
            org_id="o1", project_id="p1",
            source_path=tmp_md, doc_type="doc",
            # Sin bridge_url ni jwt_token
        )
        assert result.failed == 0

    @pytest.mark.asyncio
    async def test_error_en_lote_no_propaga(self, tmp_md, monkeypatch):
        """Error en indexación → se reporta en errors, no lanza excepción."""
        from knowledge import bootstrap
        monkeypatch.setattr(
            "rag.index_chunks_async",
            AsyncMock(side_effect=RuntimeError("pgvector caído")),
        )

        result = await bootstrap.run(
            org_id="o1", project_id="p1",
            source_path=tmp_md, doc_type="doc",
        )
        assert result.failed > 0
        assert len(result.errors) > 0
        assert "pgvector caído" in result.errors[0]
        assert result.indexed == 0

    @pytest.mark.asyncio
    async def test_ruta_inexistente_lanza_file_not_found(self):
        from knowledge import bootstrap
        with pytest.raises(FileNotFoundError):
            await bootstrap.run(
                org_id="o1", project_id="p1",
                source_path="/ruta/que/no/existe-ovd-test",
                doc_type="doc",
            )

    @pytest.mark.asyncio
    async def test_resultado_incluye_doc_type_y_source(self, tmp_md, monkeypatch):
        from knowledge import bootstrap
        monkeypatch.setattr("rag.index_chunks_async", AsyncMock(return_value=2))

        result = await bootstrap.run(
            org_id="o1", project_id="p1",
            source_path=tmp_md, doc_type="doc",
        )
        assert result.doc_type == "doc"
        assert str(tmp_md) in result.source

    @pytest.mark.asyncio
    async def test_batch_size_respetado(self, tmp_path, monkeypatch):
        """Verifica que los chunks se envían en lotes del tamaño indicado."""
        from knowledge import bootstrap

        # Crear múltiples archivos para generar varios chunks
        for i in range(5):
            (tmp_path / f"doc{i}.md").write_text(
                f"## Sección {i}\n{'x' * 500}\n", encoding="utf-8"
            )

        llamadas = []
        async def _mock_index(chunks, project_id, org_id):
            llamadas.append(len(chunks))
            return len(chunks)

        monkeypatch.setattr("rag.index_chunks_async", _mock_index)

        await bootstrap.run(
            org_id="o1", project_id="p1",
            source_path=tmp_path, doc_type="doc",
            batch_size=3,
        )
        # Cada lote debe tener máximo 3 chunks
        assert all(n <= 3 for n in llamadas)

    @pytest.mark.asyncio
    async def test_errores_limitados_a_20(self, tmp_path, monkeypatch):
        """El resultado no debe guardar más de 20 errores."""
        from knowledge import bootstrap

        for i in range(30):
            (tmp_path / f"doc{i}.md").write_text(
                f"## Sección {i}\nContenido {i}.\n", encoding="utf-8"
            )

        monkeypatch.setattr(
            "rag.index_chunks_async",
            AsyncMock(side_effect=RuntimeError("fallo")),
        )

        result = await bootstrap.run(
            org_id="o1", project_id="p1",
            source_path=tmp_path, doc_type="doc",
            batch_size=1,
        )
        assert len(result.errors) <= 20
