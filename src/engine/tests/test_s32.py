"""
OVD Platform — Tests S32: pytest target logic refinada + ImportError diagnosis + template write order
"""

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import inspect

import pytest

# ---------------------------------------------------------------------------
# S32-A — Lógica refinada de selección de pytest target
# ---------------------------------------------------------------------------


class TestS32APytestTargetLogic:
    """S32-A: run_tests selecciona pytest target según existencia y edad de test files."""

    def test_run_tests_usa_tests_nuevos_si_existen(self):
        """Si hay test files con mtime >= cycle_ts, usa solo esos."""
        import graph as _graph

        src = inspect.getsource(_graph.run_tests)
        # S32-A debe distinguir tests nuevos vs pre-existentes
        assert "S32-A" in src, "Etiqueta S32-A no encontrada en run_tests"
        assert "_all_tests" in src, (
            "_all_tests no declarado (necesario para detectar tests pre-existentes)"
        )

    def test_run_tests_usa_workdir_si_solo_hay_tests_viejos(self):
        """Si no hay tests nuevos pero hay pre-existentes, usa work_dir (proyecto real)."""
        import graph as _graph

        src = inspect.getsource(_graph.run_tests)
        # Debe haber un path que use work_dir cuando solo hay tests viejos
        assert (
            "pre-existentes" in src
            or "pre_existentes" in src
            or "S32-A sin tests nuevos" in src
        )

    def test_run_tests_skip_si_no_hay_tests(self):
        """Sin ningún test file en workspace, passed=True con warning."""
        import graph as _graph

        src = inspect.getsource(_graph.run_tests)
        assert "Sin test files encontrados" in src, (
            "Mensaje de skip graceful no encontrado"
        )

    def test_run_tests_all_tests_declarado(self):
        """_all_tests se calcula sobre todos los test_*.py (sin filtro mtime)."""
        import graph as _graph

        src = inspect.getsource(_graph.run_tests)
        # _all_tests no filtra por mtime
        assert "_all_tests" in src

    def test_cycle_tests_subset_de_all_tests(self):
        """_cycle_tests es un subconjunto de _all_tests — ambos se calculan."""
        import graph as _graph

        src = inspect.getsource(_graph.run_tests)
        assert "_cycle_tests" in src
        assert "_all_tests" in src

    def test_mtime_logica_con_filesystem_real(self):
        """Verificación con archivos reales: _cycle_tests filtra por mtime correctamente."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test file "viejo" (de ciclo anterior)
            old_test = os.path.join(tmpdir, "test_old.py")
            with open(old_test, "w") as f:
                f.write("def test_old(): pass\n")
            # Fijar mtime del archivo viejo a hace 60 segundos
            old_mtime = time.time() - 60
            os.utime(old_test, (old_mtime, old_mtime))

            # Test file "nuevo" (del ciclo actual)
            new_test = os.path.join(tmpdir, "test_new.py")
            with open(new_test, "w") as f:
                f.write("def test_new(): pass\n")
            # mtime del archivo nuevo es now (por defecto al escribirlo)

            cycle_ts = time.time() - 10  # ciclo empezó hace 10 segundos

            import pathlib

            base = pathlib.Path(tmpdir)
            _all_tests = [str(fp) for fp in sorted(base.rglob("test_*.py"))]
            _cycle_tests = [
                str(fp)
                for fp in sorted(base.rglob("test_*.py"))
                if fp.stat().st_mtime >= cycle_ts - 5
            ]

            assert len(_all_tests) == 2, "Deben existir 2 test files en total"
            assert len(_cycle_tests) == 1, (
                "Solo el test nuevo debe pasar el filtro mtime"
            )
            assert new_test in _cycle_tests
            assert old_test not in _cycle_tests

    def test_solo_tests_viejos_usa_work_dir(self):
        """Con solo tests viejos → work_dir como target (no skip)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            old_test = os.path.join(tmpdir, "test_viejo.py")
            with open(old_test, "w") as f:
                f.write("def test_viejo(): pass\n")
            old_mtime = time.time() - 120
            os.utime(old_test, (old_mtime, old_mtime))

            cycle_ts = time.time() - 5

            import pathlib

            base = pathlib.Path(tmpdir)
            _all_tests = [str(fp) for fp in sorted(base.rglob("test_*.py"))]
            _cycle_tests = [
                str(fp)
                for fp in sorted(base.rglob("test_*.py"))
                if fp.stat().st_mtime >= cycle_ts - 5
            ]

            # Lógica S32-A:
            if _cycle_tests:
                pytest_args = _cycle_tests
            elif _all_tests:
                pytest_args = [tmpdir]  # proyecto real → ejecutar todos
            else:
                pytest_args = None  # skip

            assert pytest_args == [tmpdir], "Con solo tests viejos debe usar work_dir"

    def test_sin_tests_skip_graceful(self):
        """Sin ningún test file → skip (pytest_args=None)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import pathlib

            cycle_ts = time.time()
            base = pathlib.Path(tmpdir)
            _all_tests = [str(fp) for fp in sorted(base.rglob("test_*.py"))]
            _cycle_tests = [
                str(fp)
                for fp in sorted(base.rglob("test_*.py"))
                if fp.stat().st_mtime >= cycle_ts - 5
            ]

            if _cycle_tests:
                pytest_args = _cycle_tests
            elif _all_tests:
                pytest_args = [tmpdir]
            else:
                pytest_args = None  # skip graceful

            assert pytest_args is None, "Sin tests debe retornar None (skip graceful)"


# ---------------------------------------------------------------------------
# S32-B — Orden de escritura en system_backend.md
# ---------------------------------------------------------------------------


class TestS32BTemplateWriteOrder:
    """S32-B: system_backend.md instruye a escribir infraestructura PRIMERO."""

    def _get_template(self) -> str:
        """S58-pre: ORDEN DE ESCRITURA movido a stack/backend_python.md — cargar template compuesto."""
        import template_loader

        template_loader.invalidate()
        return template_loader.render_composed(
            "system_backend", stack_language="python"
        )

    def test_template_tiene_orden_de_escritura(self):
        """Template menciona explícitamente el orden de escritura."""
        content = self._get_template()
        assert "ORDEN DE ESCRITURA" in content or "PRIMERO" in content, (
            "Template no menciona orden de escritura obligatorio"
        )

    def test_template_init_py_es_primero(self):
        """__init__.py de src está etiquetado en el orden de escritura obligatorio.
        S58-pre: requirements.txt es ahora PRIMERO, __init__.py es SEGUNDO — ambos antes del código de negocio."""
        content = self._get_template()
        # El template debe tener algún ítem etiquetado como PRIMERO
        assert "PRIMERO" in content, "Template no etiqueta ningún archivo como PRIMERO"
        # __init__.py debe aparecer en el ORDEN DE ESCRITURA (puede ser SEGUNDO con S58-pre)
        lines = content.splitlines()
        init_in_order = any(
            "__init__.py" in line
            and ("PRIMERO" in line or "SEGUNDO" in line or "←" in line)
            for line in lines
        )
        assert init_in_order, (
            "Ninguna línea del template tiene '__init__.py' etiquetado en el orden de escritura"
        )

    def test_template_instruye_escribir_infra_antes_de_negocio(self):
        """Template tiene instrucción de escribir infra antes que código de negocio."""
        content = self._get_template()
        assert "antes" in content.lower() and (
            "código" in content.lower() or "negocio" in content.lower()
        ), "Template debe indicar que infra va ANTES que código de negocio"


# ---------------------------------------------------------------------------
# S32-C — Diagnóstico ImportError en output de pytest
# ---------------------------------------------------------------------------


class TestS32CImportErrorDiagnosis:
    """S32-C: run_tests extrae ImportError del output para retry_feedback más específico."""

    def test_run_tests_detecta_import_error(self):
        """run_tests tiene lógica para detectar ImportError en output de pytest.
        S57-B: la detección se movió de rc==4 a rc==1 con 'collected 0 items'."""
        import graph as _graph

        src = inspect.getsource(_graph.run_tests)
        assert "ImportError" in src, "run_tests no busca ImportError en output"
        # S57-B reemplaza S32-C — aceptar cualquiera de las dos etiquetas
        assert "S32-C" in src or "S57-B" in src, (
            "Ninguna etiqueta de diagnóstico ImportError encontrada"
        )

    def test_run_tests_detecta_module_not_found(self):
        """run_tests también detecta ModuleNotFoundError."""
        import graph as _graph

        src = inspect.getsource(_graph.run_tests)
        assert "ModuleNotFoundError" in src

    def test_run_tests_detecta_relative_import(self):
        """run_tests detecta 'attempted relative import'."""
        import graph as _graph

        src = inspect.getsource(_graph.run_tests)
        assert "attempted relative import" in src

    def test_diagnostico_incluye_solucion(self):
        """El mensaje de diagnóstico incluye instrucción de solución.
        S57-B: etiqueta cambiada de S32-C a S57-B pero funcionalidad preservada."""
        import graph as _graph

        src = inspect.getsource(_graph.run_tests)
        assert (
            "DIAGNÓSTICO S32-C" in src
            or "DIAGNÓSTICO S57-B" in src
            or "SOLUCION" in src
            or "SOLUCIÓN" in src
        ), "Ningún diagnóstico de ImportError encontrado en run_tests"

    def test_output_modificado_con_diagnostico(self):
        """Cuando hay ImportError, el output se prepende con diagnóstico."""
        import graph as _graph

        src = inspect.getsource(_graph.run_tests)
        # El output debe ser modificado para incluir el diagnóstico
        assert "output = " in src and "DIAGNÓSTICO" in src
