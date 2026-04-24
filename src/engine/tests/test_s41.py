"""
OVD Platform — Tests S41: RAG Learning — lecciones por proyecto y agente

S41.A: Indexación automática de errores (QA, security, tests, postmortem)
S41.B: Consulta de lecciones filtrada por agente y proyecto
S41.C: Integración con agent_executor y template_loader
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import asyncio
import inspect
import pytest
from unittest.mock import AsyncMock, patch, MagicMock, call
from factories import make_state


# ---------------------------------------------------------------------------
# S41.A — Módulo de lecciones: estructura y funciones exportadas
# ---------------------------------------------------------------------------

class TestS41AModule:

    def test_lessons_module_importa(self):
        """S41.A: lessons.py importa sin errores."""
        import lessons
        assert lessons is not None

    def test_funciones_exportadas(self):
        """S41.A: el módulo exporta las 5 funciones requeridas."""
        import lessons
        for fn in [
            "index_qa_finding",
            "index_security_finding",
            "index_test_failure",
            "index_cycle_postmortem",
            "query_lessons_context",
        ]:
            assert hasattr(lessons, fn), f"lessons.{fn} no existe"
            assert asyncio.iscoroutinefunction(getattr(lessons, fn)), f"lessons.{fn} debe ser async"

    def test_doc_type_por_agente(self):
        """S41.A: _lesson_doc_type retorna el doc_type correcto por agente."""
        from lessons import _lesson_doc_type
        assert _lesson_doc_type("backend") == "lesson_backend"
        assert _lesson_doc_type("frontend") == "lesson_frontend"
        assert _lesson_doc_type("database") == "lesson_database"
        assert _lesson_doc_type("devops") == "lesson_devops"
        assert _lesson_doc_type("unknown") == "lesson_general"
        assert _lesson_doc_type("general") == "lesson_general"

    def test_known_agents_set(self):
        """S41.A: _KNOWN_AGENTS contiene los 4 agentes implementadores."""
        from lessons import _KNOWN_AGENTS
        assert "backend" in _KNOWN_AGENTS
        assert "frontend" in _KNOWN_AGENTS
        assert "database" in _KNOWN_AGENTS
        assert "devops" in _KNOWN_AGENTS


# ---------------------------------------------------------------------------
# S41.A2 — index_qa_finding
# ---------------------------------------------------------------------------

class TestS41AIndexQAFinding:

    @pytest.mark.asyncio
    async def test_indexa_cuando_hay_issues(self):
        """S41.A2: index_qa_finding llama a rag.index_chunks_async con un chunk por agente."""
        import lessons
        mock_rag = MagicMock()
        mock_rag.index_chunks_async = AsyncMock(return_value=2)

        with patch.dict("sys.modules", {"rag": mock_rag}), \
             patch.dict(os.environ, {"OVD_RAG_ENABLED": "true"}):
            await lessons.index_qa_finding(
                project_id="proj-1",
                org_id="org-1",
                issues=["hook no importado", "validación faltante"],
                score=62,
                cycle_id="abc123",
                agent_names=["backend", "frontend"],
            )

        # Se llama una vez con todos los chunks (2 — uno por agente)
        assert mock_rag.index_chunks_async.call_count == 1
        chunks_pasados = mock_rag.index_chunks_async.call_args[0][0]
        assert len(chunks_pasados) == 2
        doc_types = {c["doc_type"] for c in chunks_pasados}
        assert "lesson_backend" in doc_types
        assert "lesson_frontend" in doc_types

    @pytest.mark.asyncio
    async def test_no_indexa_sin_issues(self):
        """S41.A2: index_qa_finding no indexa cuando issues=[]."""
        import lessons
        mock_rag = MagicMock()
        mock_rag.index_chunks_async = AsyncMock()

        with patch.dict("sys.modules", {"rag": mock_rag}), \
             patch.dict(os.environ, {"OVD_RAG_ENABLED": "true"}):
            await lessons.index_qa_finding(
                project_id="proj-1",
                org_id="org-1",
                issues=[],
                score=95,
                cycle_id="abc123",
                agent_names=["backend"],
            )

        mock_rag.index_chunks_async.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_indexa_con_rag_desactivado(self):
        """S41.A2: no indexa cuando OVD_RAG_ENABLED=false."""
        import lessons
        mock_rag = MagicMock()
        mock_rag.index_chunks_async = AsyncMock()

        with patch.dict("sys.modules", {"rag": mock_rag}), \
             patch.dict(os.environ, {"OVD_RAG_ENABLED": "false"}):
            await lessons.index_qa_finding(
                project_id="proj-1",
                org_id="org-1",
                issues=["bug grave"],
                score=30,
                cycle_id="abc123",
                agent_names=["backend"],
            )

        mock_rag.index_chunks_async.assert_not_called()

    @pytest.mark.asyncio
    async def test_chunk_doc_type_correcto(self):
        """S41.A2: el chunk indexado tiene doc_type=lesson_backend para agente backend."""
        import lessons
        captured_chunks = []

        async def fake_index(chunks, project_id, org_id):
            captured_chunks.extend(chunks)
            return len(chunks)

        mock_rag = MagicMock()
        mock_rag.index_chunks_async = fake_index

        with patch.dict("sys.modules", {"rag": mock_rag}), \
             patch.dict(os.environ, {"OVD_RAG_ENABLED": "true"}):
            await lessons.index_qa_finding(
                project_id="proj-1",
                org_id="org-1",
                issues=["issue 1"],
                score=50,
                cycle_id="aaaaaaaa",
                agent_names=["backend"],
            )

        assert len(captured_chunks) == 1
        assert captured_chunks[0]["doc_type"] == "lesson_backend"
        assert "aaaaaaaa" in captured_chunks[0]["content"]
        assert "issue 1" in captured_chunks[0]["content"]


# ---------------------------------------------------------------------------
# S41.A3 — index_security_finding
# ---------------------------------------------------------------------------

class TestS41AIndexSecurityFinding:

    @pytest.mark.asyncio
    async def test_no_indexa_severity_low(self):
        """S41.A3: no indexa cuando severity=low (no hubo problema real)."""
        import lessons
        mock_rag = MagicMock()
        mock_rag.index_chunks_async = AsyncMock()

        with patch.dict("sys.modules", {"rag": mock_rag}), \
             patch.dict(os.environ, {"OVD_RAG_ENABLED": "true"}):
            await lessons.index_security_finding(
                project_id="proj-1",
                org_id="org-1",
                vulnerabilities=["algo menor"],
                severity="low",
                score=90,
                cycle_id="abc",
                agent_names=["backend"],
            )

        mock_rag.index_chunks_async.assert_not_called()

    @pytest.mark.asyncio
    async def test_indexa_severity_high(self):
        """S41.A3: indexa cuando severity=high."""
        import lessons
        mock_rag = MagicMock()
        mock_rag.index_chunks_async = AsyncMock(return_value=1)

        with patch.dict("sys.modules", {"rag": mock_rag}), \
             patch.dict(os.environ, {"OVD_RAG_ENABLED": "true"}):
            await lessons.index_security_finding(
                project_id="proj-1",
                org_id="org-1",
                vulnerabilities=["SQL injection en búsqueda"],
                severity="high",
                score=30,
                cycle_id="abc",
                agent_names=["backend"],
            )

        assert mock_rag.index_chunks_async.call_count == 1


# ---------------------------------------------------------------------------
# S41.A4 — index_test_failure
# ---------------------------------------------------------------------------

class TestS41AIndexTestFailure:

    @pytest.mark.asyncio
    async def test_indexa_cuando_hay_error(self):
        """S41.A4: index_test_failure indexa cuando hay output de error."""
        import lessons
        mock_rag = MagicMock()
        mock_rag.index_chunks_async = AsyncMock(return_value=1)

        with patch.dict("sys.modules", {"rag": mock_rag}), \
             patch.dict(os.environ, {"OVD_RAG_ENABLED": "true"}):
            await lessons.index_test_failure(
                project_id="proj-1",
                org_id="org-1",
                error_text="AssertionError: assert 18.48 == 18.49",
                runner="pytest",
                cycle_id="abc",
                agent_names=["backend"],
            )

        mock_rag.index_chunks_async.assert_called_once()


# ---------------------------------------------------------------------------
# S41.B1 — query_lessons_context
# ---------------------------------------------------------------------------

class TestS41BQueryLessons:

    @pytest.mark.asyncio
    async def test_retorna_string_vacio_sin_rag(self):
        """S41.B1: retorna '' cuando OVD_RAG_ENABLED=false."""
        import lessons
        with patch.dict(os.environ, {"OVD_RAG_ENABLED": "false"}):
            result = await lessons.query_lessons_context(
                project_id="proj-1",
                agent_name="backend",
                fr_text="Implementar módulo de pagos",
            )
        assert result == ""

    @pytest.mark.asyncio
    async def test_filtra_por_doc_type_agente(self):
        """S41.B1: query usa doc_types=[lesson_frontend] para agente frontend."""
        import lessons
        mock_rag = MagicMock()
        mock_rag.RagFilters = MagicMock()
        mock_rag.search_async = AsyncMock(return_value="## Lección previa")

        rag_filters_instance = MagicMock()
        mock_rag.RagFilters.return_value = rag_filters_instance

        with patch.dict("sys.modules", {"rag": mock_rag}), \
             patch.dict(os.environ, {"OVD_RAG_ENABLED": "true"}):
            result = await lessons.query_lessons_context(
                project_id="proj-1",
                agent_name="frontend",
                fr_text="Implementar pantalla de login",
            )

        # Verifica que se construyó RagFilters con doc_types que incluye lesson_frontend
        call_kwargs = mock_rag.RagFilters.call_args
        doc_types = call_kwargs[1]["doc_types"] if call_kwargs[1] else call_kwargs[0][0]
        assert "lesson_frontend" in doc_types
        assert result == "## Lección previa"

    @pytest.mark.asyncio
    async def test_incluye_lesson_general_para_agentes_conocidos(self):
        """S41.B1: consulta incluye lesson_general además de lesson_{agent}."""
        import lessons
        mock_rag = MagicMock()
        captured_doc_types = []

        def capture_filters(**kwargs):
            captured_doc_types.extend(kwargs.get("doc_types", []))
            return MagicMock()

        mock_rag.RagFilters = MagicMock(side_effect=capture_filters)
        mock_rag.search_async = AsyncMock(return_value="")

        with patch.dict("sys.modules", {"rag": mock_rag}), \
             patch.dict(os.environ, {"OVD_RAG_ENABLED": "true"}):
            await lessons.query_lessons_context(
                project_id="proj-1",
                agent_name="backend",
                fr_text="Módulo de autenticación",
            )

        assert "lesson_backend" in captured_doc_types
        assert "lesson_general" in captured_doc_types

    @pytest.mark.asyncio
    async def test_retorna_vacio_sin_project_id(self):
        """S41.B1: retorna '' cuando project_id está vacío."""
        import lessons
        with patch.dict(os.environ, {"OVD_RAG_ENABLED": "true"}):
            result = await lessons.query_lessons_context(
                project_id="",
                agent_name="backend",
                fr_text="algo",
            )
        assert result == ""


# ---------------------------------------------------------------------------
# S41.C — Integración con template_loader
# ---------------------------------------------------------------------------

class TestS41CTemplateLessonIntegration:

    def test_render_acepta_lessons_context(self):
        """S41.C: template_loader.render() acepta y sustituye {lessons_context}."""
        import template_loader
        template_loader.invalidate()

        rendered = template_loader.render(
            "system_backend",
            lessons_context="[QA finding — ciclo abc12345] hook no importado",
        )
        assert "Lecciones de ciclos anteriores" in rendered
        assert "hook no importado" in rendered

    def test_render_omite_seccion_si_vacio(self):
        """S41.C: {lessons_context} vacío no agrega sección al prompt."""
        import template_loader
        template_loader.invalidate()

        rendered = template_loader.render("system_backend", lessons_context="")
        assert "Lecciones de ciclos anteriores" not in rendered

    def test_templates_md_contienen_placeholder(self):
        """S41.C: los templates .md de agentes contienen {lessons_context}."""
        import pathlib
        templates_dir = pathlib.Path(__file__).parent.parent / "templates"
        for template_name in [
            "system_backend_python.md",
            "system_frontend_react.md",
            "system_database_postgresql.md",
            "system_backend.md",
            "system_frontend.md",
            "system_database.md",
            "system_devops.md",
        ]:
            tp = templates_dir / template_name
            if tp.exists():
                content = tp.read_text(encoding="utf-8")
                assert "{lessons_context}" in content, f"{template_name} no tiene {{lessons_context}}"

    def test_graph_importa_lessons(self):
        """S41.C: graph.py importa el módulo lessons."""
        import inspect, graph as g
        src = inspect.getsource(g)
        assert "import lessons" in src

    def test_agent_executor_llama_query_lessons(self):
        """S41.C: agent_executor llama a lessons.query_lessons_context."""
        import inspect, graph as g
        src = inspect.getsource(g.agent_executor)
        assert "lessons.query_lessons_context" in src

    def test_qa_review_llama_index_qa(self):
        """S41.C: qa_review llama a lessons.index_qa_finding."""
        import inspect, graph as g
        src = inspect.getsource(g.qa_review)
        assert "lessons.index_qa_finding" in src

    def test_security_audit_llama_index_security(self):
        """S41.C: security_audit llama a lessons.index_security_finding."""
        import inspect, graph as g
        src = inspect.getsource(g.security_audit)
        assert "lessons.index_security_finding" in src

    def test_run_tests_llama_index_test_failure(self):
        """S41.C: run_tests llama a lessons.index_test_failure."""
        import inspect, graph as g
        src = inspect.getsource(g.run_tests)
        assert "lessons.index_test_failure" in src

    def test_deliver_llama_index_postmortem(self):
        """S41.C: deliver llama a lessons.index_cycle_postmortem."""
        import inspect, graph as g
        src = inspect.getsource(g.deliver)
        assert "lessons.index_cycle_postmortem" in src
