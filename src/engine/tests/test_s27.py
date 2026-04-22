"""
S27 — Tests para los fixes de calidad post-S26:
  S27-A: run_tests inyecta conftest.py si está vacío o no existe
  S27-B: audit_logger serializa metadata dict como JSON string
  S27-C: _index_delivery_report agrega sys.path antes de importar 'knowledge'
  S27-D: system_qa.md tiene cláusula de infraestructura en criterio de aprobación
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import pathlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from tests.factories import make_state


# ────────────────────────────────────────────────────────────────────────────
# S27-A — run_tests inyecta conftest.py
# ────────────────────────────────────────────────────────────────────────────

def _make_state_with_tests(tmp_path: pathlib.Path) -> dict:
    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tests" / "test_foo.py").write_text("def test_pass(): assert True")
    return make_state(
        agent_results=[{
            "agent": "backend",
            "output": "",
            "artifacts": [{"path": "tests/test_foo.py", "size": 30, "lang": "python"}],
        }],
        directory=str(tmp_path),
        test_retry_count=0,
    )


class TestConfTestInjection:
    """run_tests inyecta conftest.py con sys.path cuando está vacío o no existe."""

    @pytest.mark.asyncio
    async def test_injects_conftest_when_empty(self, tmp_path):
        """conftest.py existente pero vacío → se sobreescribe con sys.path.insert."""
        (tmp_path / "conftest.py").write_text("")  # vacío
        state = _make_state_with_tests(tmp_path)

        async def fake_exec(*args, **kwargs):
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(b"1 passed", None))
            proc.returncode = 0
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            import graph as g
            await g.run_tests(state)

        content = (tmp_path / "conftest.py").read_text()
        assert "sys.path.insert" in content
        assert "src" in content

    @pytest.mark.asyncio
    async def test_creates_conftest_when_missing(self, tmp_path):
        """conftest.py no existe → se crea con sys.path.insert."""
        assert not (tmp_path / "conftest.py").exists()
        state = _make_state_with_tests(tmp_path)

        async def fake_exec(*args, **kwargs):
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(b"1 passed", None))
            proc.returncode = 0
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            import graph as g
            await g.run_tests(state)

        assert (tmp_path / "conftest.py").exists()
        content = (tmp_path / "conftest.py").read_text()
        assert "sys.path.insert" in content

    @pytest.mark.asyncio
    async def test_does_not_overwrite_existing_conftest(self, tmp_path):
        """conftest.py con contenido propio → no se sobreescribe."""
        custom_content = "# custom conftest\nimport sys\nsys.path.insert(0, 'custom')\n"
        (tmp_path / "conftest.py").write_text(custom_content)
        state = _make_state_with_tests(tmp_path)

        async def fake_exec(*args, **kwargs):
            proc = MagicMock()
            proc.communicate = AsyncMock(return_value=(b"1 passed", None))
            proc.returncode = 0
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            import graph as g
            await g.run_tests(state)

        assert (tmp_path / "conftest.py").read_text() == custom_content


# ────────────────────────────────────────────────────────────────────────────
# S27-B — audit_logger serializa metadata como JSON string
# ────────────────────────────────────────────────────────────────────────────

class TestAuditLoggerMetadata:
    """audit_logger pasa metadata como JSON string, no como dict Python."""

    @pytest.mark.asyncio
    async def test_metadata_is_json_string_not_dict(self):
        """El INSERT recibe un str JSON para la columna metadata, no un dict."""
        import audit_logger as al

        captured_params: list = []

        class FakeConn:
            async def execute(self, query, params):
                captured_params.extend(params)

            async def commit(self):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        with patch("psycopg.AsyncConnection.connect", return_value=FakeConn()):
            await al._write_audit_log(
                event="test_event",
                org_id="org-1",
                user_id="usr-1",
                resource_type="session",
                resource_id="sess-1",
                summary="Test summary",
                old_value=None,
                new_value=None,
            )

        # El parámetro metadata (índice 5 tras S37-A: sin id) debe ser un str JSON, no un dict
        metadata_param = captured_params[5]
        assert isinstance(metadata_param, str), (
            f"metadata debe ser str JSON, recibido: {type(metadata_param)}"
        )
        parsed = json.loads(metadata_param)
        assert parsed["summary"] == "Test summary"

    def test_json_dumps_produces_valid_json(self):
        """Verificar que json.dumps del dict produce JSON parseable."""
        summary = "Ciclo completado"
        old_val = None
        new_val = '{"files": 6}'
        result = json.dumps({"summary": summary, "old_value": old_val, "new_value": new_val})
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["summary"] == summary


# ────────────────────────────────────────────────────────────────────────────
# S27-C — _index_delivery_report resuelve el módulo 'knowledge'
# ────────────────────────────────────────────────────────────────────────────

class TestIndexDeliveryReport:
    """_index_delivery_report configura sys.path antes de importar 'knowledge'."""

    @pytest.mark.asyncio
    async def test_knowledge_path_added_to_syspath_before_import(self, tmp_path):
        """sys.path incluye src/ (parent de knowledge) antes del import."""
        import graph as g

        report_file = str(tmp_path / "delivery.md")
        (tmp_path / "delivery.md").write_text("# Report")

        state = {
            "org_id": "org-1",
            "project_id": "proj-1",
            "jwt_token": "",
        }

        captured_paths: list[str] = []
        original_insert = list.__class__  # dummy

        bootstrap_mock = MagicMock()
        bootstrap_mock.run = AsyncMock()

        # Patch knowledge.bootstrap para evitar import real
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "knowledge":
                # Capturar sys.path en el momento del import
                import sys
                captured_paths.extend(sys.path[:])
                mod = MagicMock()
                mod.bootstrap = bootstrap_mock
                return mod
            return real_import(name, *args, **kwargs)

        with patch.dict(os.environ, {"OVD_RAG_ENABLED": "true"}), \
             patch("builtins.__import__", side_effect=mock_import):
            try:
                await g._index_delivery_report(state, report_file)
            except Exception:
                pass  # El import real puede fallar, nos interesa solo el sys.path

        # Verificar que el directorio src/ (parent de engine/) está en sys.path
        engine_dir = pathlib.Path(g.__file__).parent
        expected_parent = str(engine_dir.parent)
        assert any(expected_parent in p for p in captured_paths), (
            f"src/ ({expected_parent}) debe estar en sys.path antes del import knowledge. "
            f"sys.path capturado: {captured_paths[:5]}"
        )

    @pytest.mark.asyncio
    async def test_rag_disabled_skips_import(self, tmp_path):
        """Con OVD_RAG_ENABLED=false, no intenta importar knowledge."""
        import graph as g

        report_file = str(tmp_path / "delivery.md")
        (tmp_path / "delivery.md").write_text("# Report")

        with patch.dict(os.environ, {"OVD_RAG_ENABLED": "false"}):
            # No debe lanzar ImportError aunque knowledge no exista
            await g._index_delivery_report({}, report_file)
        # Si llegamos aquí sin excepción, el test pasa


# ────────────────────────────────────────────────────────────────────────────
# S27-D — system_qa.md cláusula de infraestructura
# ────────────────────────────────────────────────────────────────────────────

class TestQaTemplateInfra:
    """system_qa.md contiene las cláusulas de infraestructura en criterio de aprobación."""

    def _read_template(self) -> str:
        templates_dir = pathlib.Path(__file__).parent.parent / "templates"
        return (templates_dir / "system_qa.md").read_text(encoding="utf-8")

    def test_template_allows_minor_conftest_differences(self):
        """El template indica que conftest.py vacío no invalida sdd_compliance."""
        content = self._read_template()
        # Debe mencionar que infraestructura se evalúa por presencia, no contenido exacto
        assert "Infraestructura" in content or "infraestructura" in content
        assert "conftest" in content
        # Debe aclarar que no marca sdd_compliance=False solo por esto
        assert "sdd_compliance=False" in content or "compliance" in content

    def test_template_allows_more_tests_than_sdd(self):
        """El template indica que más tests que los del SDD es correcto."""
        content = self._read_template()
        # Debe mencionar que mayor cobertura no es fallo
        assert "cobertura" in content or "tests" in content.lower()
        assert ">= N" in content or "mayor cobertura" in content or "M >= N" in content
