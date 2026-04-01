"""
OVD Platform — Tests: Nightly Web Researcher Job (S11.G)
No requiere LLM, NATS ni base de datos real.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

import nightly_researcher


# ---------------------------------------------------------------------------
# Tests: build_stack_queries
# ---------------------------------------------------------------------------

class TestBuildStackQueries:
    def test_queries_con_base_de_datos(self):
        stack = {"database": "Oracle", "db_version": "12c", "language": "Java"}
        queries = nightly_researcher.build_stack_queries(stack)
        assert len(queries) >= 1
        assert any("Oracle 12c" in q for q in queries)

    def test_queries_con_solo_lenguaje(self):
        stack = {"language": "Python"}
        queries = nightly_researcher.build_stack_queries(stack)
        assert len(queries) >= 1
        assert any("Python" in q for q in queries)

    def test_queries_fallback_sin_stack(self):
        queries = nightly_researcher.build_stack_queries({})
        assert len(queries) == 1
        assert "security" in queries[0]

    def test_queries_respeta_max(self, monkeypatch):
        monkeypatch.setattr(nightly_researcher, "_MAX_QUERIES", 2)
        stack = {"database": "PostgreSQL", "language": "Python", "framework": "FastAPI"}
        queries = nightly_researcher.build_stack_queries(stack)
        assert len(queries) <= 2

    def test_queries_incluyen_año_actual(self):
        year = str(datetime.now(timezone.utc).year)
        stack = {"database": "MySQL", "db_version": "8.0"}
        queries = nightly_researcher.build_stack_queries(stack)
        assert any(year in q for q in queries)


# ---------------------------------------------------------------------------
# Tests: has_cve / extract_cve_ids
# ---------------------------------------------------------------------------

class TestCveDetection:
    def test_detecta_keyword_vulnerabilidad(self):
        assert nightly_researcher.has_cve("Se encontró una vulnerabilidad crítica") is True

    def test_detecta_cve_number(self):
        assert nightly_researcher.has_cve("El CVE-2024-1234 afecta a Oracle 12c") is True

    def test_no_detecta_sin_keywords(self):
        assert nightly_researcher.has_cve("Nueva funcionalidad de logging agregada") is False

    def test_extrae_ids_cve(self):
        text = "Los CVE-2024-1234 y CVE-2023-9999 están pendientes de parche"
        ids = nightly_researcher.extract_cve_ids(text)
        assert "CVE-2024-1234" in ids
        assert "CVE-2023-9999" in ids

    def test_extrae_ids_vacio_sin_cves(self):
        ids = nightly_researcher.extract_cve_ids("Sin hallazgos relevantes este mes")
        assert ids == []


# ---------------------------------------------------------------------------
# Tests: get_embedding (mock Ollama)
# ---------------------------------------------------------------------------

class TestGetEmbedding:
    @pytest.mark.asyncio
    async def test_retorna_vector_si_ollama_disponible(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"embedding": [0.1, 0.2, 0.3]}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await nightly_researcher.get_embedding("texto de prueba")

        assert result == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_retorna_none_si_ollama_no_disponible(self):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=Exception("connection refused"))
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await nightly_researcher.get_embedding("texto de prueba")

        assert result is None


# ---------------------------------------------------------------------------
# Tests: scheduler start/stop
# ---------------------------------------------------------------------------

class TestScheduler:
    def test_start_scheduler_desactivado(self, monkeypatch):
        """Si OVD_NIGHTLY_ENABLED=false, start_scheduler no lanza tarea."""
        monkeypatch.setattr(nightly_researcher, "_NIGHTLY_ENABLED", False)
        # Resetear estado interno
        nightly_researcher._scheduler_task = None

        nightly_researcher.start_scheduler()
        assert nightly_researcher._scheduler_task is None

    def test_stop_scheduler_sin_tarea(self):
        """stop_scheduler no falla si no hay tarea activa."""
        nightly_researcher._scheduler_task = None
        # No debe lanzar excepción
        nightly_researcher.stop_scheduler()
