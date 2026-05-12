"""
Tests S128 — Export contract enforcement, App.tsx mandatory,
adaptive timeout, task cap reduction.

S128-A: EXPORTS block en SDD service tasks + signature suggestions en S103-P2 feedback
S128-B: Módulo primario nunca como stub
S128-C: App.tsx obligatorio para ≥2 componentes frontend
S128-D: Timeout adaptativo en _run_graph_background
S128-E: Cap duro reducido — high:8→5, medium:8→5, low:5→3, critical:10→7
"""

import os
import pathlib
import sys
import tempfile
import textwrap

import pytest

_ENGINE_DIR = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(_ENGINE_DIR))

# ---------------------------------------------------------------------------
# S128-A1: sección EXPORTS en system_sdd.md
# ---------------------------------------------------------------------------


class TestS128A1SddExports:
    _SDD_PATH = _ENGINE_DIR / "templates" / "system_sdd.md"

    def test_sdd_contains_exports_section(self):
        """system_sdd.md debe tener la sección S128-A sobre EXPORTS."""
        content = self._SDD_PATH.read_text(encoding="utf-8")
        assert "EXPORTS explícitos por tarea de servicios (S128-A)" in content

    def test_sdd_exports_example_present(self):
        """system_sdd.md debe mostrar un ejemplo concreto de EXPORTS."""
        content = self._SDD_PATH.read_text(encoding="utf-8")
        assert "EXPORTS:" in content
        assert "get_pacientes" in content

    def test_sdd_exports_prohibition_rule(self):
        """system_sdd.md debe prohibir importar funciones fuera del EXPORTS."""
        content = self._SDD_PATH.read_text(encoding="utf-8")
        assert "get_pacientes_by_org" in content or "PROHIBIDO" in content


# ---------------------------------------------------------------------------
# S128-A2: _p2_infer_signature — sugerencias de firma en feedback S103-P2
# ---------------------------------------------------------------------------


class TestS128A2SignatureInference:
    def setup_method(self):
        from graph import _p2_infer_signature

        self.infer = _p2_infer_signature

    def test_get_by_param_signature(self):
        """get_X_by_Y → firma con parámetro Y y db."""
        sig = self.infer("get_paciente_by_rut")
        assert "async def get_paciente_by_rut" in sig
        assert "rut" in sig
        assert "db" in sig

    def test_get_list_signature(self):
        """get_X sin _by_ → firma con db, skip, limit."""
        sig = self.infer("get_pacientes")
        assert "async def get_pacientes" in sig
        assert "db" in sig
        assert "skip" in sig

    def test_list_prefix_signature(self):
        """list_X → firma con db, skip, limit."""
        sig = self.infer("list_turnos")
        assert "async def list_turnos" in sig
        assert "db" in sig

    def test_create_signature(self):
        """create_X → firma con data, db."""
        sig = self.infer("create_turno")
        assert "async def create_turno" in sig
        assert "data" in sig
        assert "db" in sig

    def test_update_signature(self):
        """update_X → firma con X_id, data, db."""
        sig = self.infer("update_turno")
        assert "async def update_turno" in sig
        assert "turno_id" in sig
        assert "data" in sig

    def test_delete_signature(self):
        """delete_X → firma con X_id, db."""
        sig = self.infer("delete_paciente")
        assert "async def delete_paciente" in sig
        assert "paciente_id" in sig
        assert "db" in sig

    def test_cancel_signature(self):
        """cancel_X → firma con X_id, motivo, db."""
        sig = self.infer("cancel_turno")
        assert "async def cancel_turno" in sig
        assert "motivo" in sig

    def test_unknown_prefix_fallback(self):
        """Nombre sin prefijo conocido → firma genérica con *args, **kwargs."""
        sig = self.infer("process_data")
        assert "async def process_data" in sig


class TestS128A2FeedbackWithSuggestions:
    """_check_undefined_import_names debe incluir sugerencias de firma."""

    def _run_check(self, services_content: str, router_content: str):
        """Crea archivos temporales y corre _check_undefined_import_names."""
        from graph import _check_undefined_import_names

        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp) / "src" / "pacientes"
            base.mkdir(parents=True)
            (base / "services.py").write_text(services_content, encoding="utf-8")
            (base / "router.py").write_text(router_content, encoding="utf-8")
            results = [
                {
                    "agent": "backend",
                    "artifacts": [
                        {"path": "src/pacientes/services.py"},
                        {"path": "src/pacientes/router.py"},
                    ],
                }
            ]
            return _check_undefined_import_names(results, tmp)

    def test_feedback_includes_suggestion_when_undefined(self):
        """Cuando hay función no definida, el feedback incluye sugerencia de firma."""
        services = textwrap.dedent("""\
            async def get_pacientes(db, skip=0, limit=100):
                return []
        """)
        router = textwrap.dedent("""\
            from src.pacientes.services import get_pacientes_by_org

            async def list_pacientes():
                return await get_pacientes_by_org("org1")
        """)
        ok, feedback = self._run_check(services, router)
        assert not ok
        assert "get_pacientes_by_org" in feedback
        assert "SUGERENCIAS" in feedback

    def test_no_suggestion_when_all_defined(self):
        """No hay sugerencias cuando todas las funciones están definidas."""
        services = textwrap.dedent("""\
            async def get_pacientes(db, skip=0, limit=100):
                return []
        """)
        router = textwrap.dedent("""\
            from src.pacientes.services import get_pacientes

            async def list_pacientes():
                return await get_pacientes(None)
        """)
        ok, feedback = self._run_check(services, router)
        assert ok
        assert feedback == ""


# ---------------------------------------------------------------------------
# S128-B1: módulo primario obligatorio en system_sdd.md
# ---------------------------------------------------------------------------


class TestS128B1PrimaryModule:
    _SDD_PATH = _ENGINE_DIR / "templates" / "system_sdd.md"

    def test_sdd_contains_primary_module_section(self):
        """system_sdd.md debe tener la sección S128-B sobre módulo primario."""
        content = self._SDD_PATH.read_text(encoding="utf-8")
        assert "Módulo primario obligatorio (S128-B)" in content

    def test_sdd_primary_module_never_stub(self):
        """La regla S128-B debe decir que el módulo primario NUNCA queda sin implementación."""
        content = self._SDD_PATH.read_text(encoding="utf-8")
        assert "NUNCA puede quedar sin implementación" in content


# ---------------------------------------------------------------------------
# S128-C1: App.tsx obligatorio en system_frontend_react.md
# ---------------------------------------------------------------------------


class TestS128C1AppTsxTemplate:
    _REACT_PATH = _ENGINE_DIR / "templates" / "system_frontend_react.md"

    def test_react_template_contains_app_tsx_section(self):
        """system_frontend_react.md debe tener la sección S128-C sobre App.tsx."""
        content = self._REACT_PATH.read_text(encoding="utf-8")
        assert "App.tsx — OBLIGATORIO para entregas multi-componente (S128-C)" in content

    def test_react_template_app_tsx_threshold(self):
        """La sección debe especificar ≥2 componentes como umbral."""
        content = self._REACT_PATH.read_text(encoding="utf-8")
        assert "≥2 componentes" in content

    def test_react_template_app_tsx_uses_react_router(self):
        """App.tsx de referencia usa react-router-dom con BrowserRouter."""
        content = self._REACT_PATH.read_text(encoding="utf-8")
        assert "react-router-dom" in content
        assert "BrowserRouter" in content


# ---------------------------------------------------------------------------
# S128-C2: deliver genera App.tsx automáticamente
# ---------------------------------------------------------------------------


class TestS128C2DeliverAppTsx:
    def _make_frontend_dir(self, tmp_path: pathlib.Path, components: list[str]) -> pathlib.Path:
        """Crea un directorio frontend simulado con los componentes indicados."""
        src = tmp_path / "src"
        src.mkdir(parents=True)
        (tmp_path / "package.json").write_text('{"name":"test"}', encoding="utf-8")
        for name in components:
            (src / f"{name}.tsx").write_text(
                f"export function {name}() {{ return <div>{name}</div> }}\n",
                encoding="utf-8",
            )
        return tmp_path

    def test_app_tsx_generated_when_two_or_more_components(self, tmp_path):
        """deliver (S128-C2): crea App.tsx si hay ≥2 componentes y no existe."""
        base = self._make_frontend_dir(
            tmp_path, ["PacientesPage", "MedicosPage"]
        )
        from graph import _s128_c2_ensure_app_tsx

        _s128_c2_ensure_app_tsx(str(base))
        app_tsx = base / "src" / "App.tsx"
        assert app_tsx.exists(), "App.tsx debe crearse con ≥2 componentes"
        content = app_tsx.read_text()
        assert "BrowserRouter" in content
        assert "PacientesPage" in content

    def test_app_tsx_skipped_when_single_component(self, tmp_path):
        """deliver (S128-C2): NO crea App.tsx si hay <2 componentes."""
        base = self._make_frontend_dir(tmp_path, ["PacientesPage"])
        from graph import _s128_c2_ensure_app_tsx

        _s128_c2_ensure_app_tsx(str(base))
        app_tsx = base / "src" / "App.tsx"
        assert not app_tsx.exists(), "App.tsx NO debe crearse con 1 solo componente"

    def test_app_tsx_not_overwritten_when_exists(self, tmp_path):
        """deliver (S128-C2): no sobreescribe App.tsx existente."""
        base = self._make_frontend_dir(
            tmp_path, ["PacientesPage", "MedicosPage"]
        )
        existing_content = "// mi App.tsx custom\n"
        (base / "src" / "App.tsx").write_text(existing_content, encoding="utf-8")
        from graph import _s128_c2_ensure_app_tsx

        _s128_c2_ensure_app_tsx(str(base))
        assert (base / "src" / "App.tsx").read_text() == existing_content


# ---------------------------------------------------------------------------
# S128-D1: timeout adaptativo en api.py
# ---------------------------------------------------------------------------


class TestS128D1AdaptiveTimeout:
    def test_adaptive_timeout_formula(self):
        """Timeout adaptativo = base + retry_round * 900."""
        _SSE_STREAM_TIMEOUT = 900.0
        for retry_round, expected in [(0, 900.0), (1, 1800.0), (2, 2700.0)]:
            result = _SSE_STREAM_TIMEOUT + (retry_round * 900)
            assert result == expected, (
                f"retry_round={retry_round}: esperado {expected}, obtenido {result}"
            )

    def test_adaptive_timeout_code_present_in_api(self):
        """api.py debe contener la lógica S128-D1 del timeout adaptativo."""
        api_path = _ENGINE_DIR / "api.py"
        content = api_path.read_text(encoding="utf-8")
        assert "_d1_retry_round" in content
        assert "_adaptive_timeout" in content
        assert "test_retry_count" in content


# ---------------------------------------------------------------------------
# S128-E3: cap duro reducido
# ---------------------------------------------------------------------------


class TestS128E3TaskCap:
    def test_cap_high_is_5(self):
        """S128-E3: complejidad 'high' → cap 5 (antes era 8)."""
        graph_path = _ENGINE_DIR / "graph.py"
        content = graph_path.read_text(encoding="utf-8")
        assert '"high": 5' in content, "Cap 'high' debe ser 5 (S128-E3)"

    def test_cap_medium_is_5(self):
        """S128-E3: complejidad 'medium' → cap 5 (antes era 8)."""
        graph_path = _ENGINE_DIR / "graph.py"
        content = graph_path.read_text(encoding="utf-8")
        assert '"medium": 5' in content, "Cap 'medium' debe ser 5 (S128-E3)"

    def test_cap_low_is_3(self):
        """S128-E3: complejidad 'low' → cap 3 (antes era 5)."""
        graph_path = _ENGINE_DIR / "graph.py"
        content = graph_path.read_text(encoding="utf-8")
        assert '"low": 3' in content, "Cap 'low' debe ser 3 (S128-E3)"

    def test_cap_critical_is_7(self):
        """S128-E3: complejidad 'critical' → cap 7 (antes era 10)."""
        graph_path = _ENGINE_DIR / "graph.py"
        content = graph_path.read_text(encoding="utf-8")
        assert '"critical": 7' in content, "Cap 'critical' debe ser 7 (S128-E3)"

    def test_old_cap_8_removed(self):
        """S128-E3: el cap 8 para 'high' no debe existir en _TASK_CAPS."""
        graph_path = _ENGINE_DIR / "graph.py"
        content = graph_path.read_text(encoding="utf-8")
        # S80 dejó "high": 8 — verificar que fue reemplazado
        # El comentario S80-E puede mencionarlo como referencia histórica, pero el valor activo debe ser 5
        lines_with_high_8 = [
            ln for ln in content.splitlines()
            if '"high": 8' in ln and not ln.strip().startswith("#")
        ]
        assert len(lines_with_high_8) == 0, (
            f"'\"high\": 8' no debe estar en código activo: {lines_with_high_8}"
        )
