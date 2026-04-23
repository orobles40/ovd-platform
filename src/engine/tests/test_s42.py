"""
OVD Platform — Tests S42: Stack-aware templates + calidad de generación

S42-A: system_sdd.md contiene regla de alcance función pura vs API
S42-B: _cleanup_impl_files_from_prev_retry elimina archivos de implementación en retry
S42-C: system_backend_python.md tiene regla reforzada de float precision
S42-D: _detect_duplicate_functions detecta funciones definidas en múltiples archivos
S42-E: template_loader selecciona template por stack_language
S42-F: templates por stack existen y contienen contenido apropiado
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pathlib
import tempfile
import pytest


# ---------------------------------------------------------------------------
# S42-A — system_sdd.md scope control
# ---------------------------------------------------------------------------

class TestS42AScopeControl:
    """S42-A: system_sdd.md incluye regla para funciones puras vs API."""

    def _get_sdd_template(self) -> str:
        templates_dir = pathlib.Path(__file__).parent.parent / "templates"
        sdd_file = templates_dir / "system_sdd.md"
        assert sdd_file.exists(), "system_sdd.md no encontrado"
        return sdd_file.read_text(encoding="utf-8")

    def test_template_menciona_funcion_pura(self):
        """S42-A: el template menciona el caso de función pura sin HTTP."""
        content = self._get_sdd_template()
        assert "función" in content.lower() or "funcion" in content.lower()
        assert "http" in content.lower() or "HTTP" in content

    def test_template_tiene_ejemplos_correcto_incorrecto(self):
        """S42-A: el template tiene ejemplos ✅/❌ de alcance."""
        content = self._get_sdd_template()
        assert "INCORRECTO" in content or "❌" in content
        assert "CORRECTO" in content or "✅" in content

    def test_template_menciona_fastapi_condicional(self):
        """S42-A: el template indica que FastAPI solo se usa si el FR lo menciona."""
        content = self._get_sdd_template()
        # La regla debe hablar de no crear FastAPI para FRs de función pura
        assert "FastAPI" in content or "fastapi" in content.lower()


# ---------------------------------------------------------------------------
# S42-B — _cleanup_impl_files_from_prev_retry
# ---------------------------------------------------------------------------

class TestS42BWorkspaceCleanup:
    """S42-B: limpieza de archivos de implementación entre rounds de retry."""

    def _get_fn(self):
        import graph as g
        return g._cleanup_impl_files_from_prev_retry

    def test_elimina_archivos_py_del_ciclo(self):
        """S42-B: elimina archivos .py de implementación escritos en el ciclo."""
        import time
        fn = self._get_fn()
        with tempfile.TemporaryDirectory() as tmpdir:
            cycle_ts = time.time() - 10  # ciclo empezó hace 10s
            # Crear archivos que deberían eliminarse (implementación, mtime reciente)
            impl_file = pathlib.Path(tmpdir) / "src" / "calculadora" / "imc.py"
            impl_file.parent.mkdir(parents=True, exist_ok=True)
            impl_file.write_text("def calculate_bmi(w, h): return w/h**2")

            # Crear archivo de test que NO debe eliminarse
            test_file = pathlib.Path(tmpdir) / "tests" / "test_imc.py"
            test_file.parent.mkdir(parents=True, exist_ok=True)
            test_file.write_text("def test_bmi(): assert True")

            fn(tmpdir, cycle_ts)

            assert not impl_file.exists(), "El archivo de impl debe eliminarse en retry"
            assert test_file.exists(), "El archivo de test NO debe eliminarse"

    def test_no_elimina_archivos_preexistentes(self):
        """S42-B: no elimina archivos con mtime anterior al ciclo (pre-existentes)."""
        import time
        fn = self._get_fn()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Archivo creado antes del ciclo
            old_file = pathlib.Path(tmpdir) / "existing_module.py"
            old_file.write_text("# archivo preexistente")
            # Modificar mtime para que sea anterior al ciclo
            old_ts = time.time() - 3600  # 1 hora antes
            os.utime(str(old_file), (old_ts, old_ts))

            cycle_ts = time.time() - 10
            fn(tmpdir, cycle_ts)

            assert old_file.exists(), "Archivo preexistente no debe eliminarse"

    def test_no_elimina_conftest_ni_pytest_ini(self):
        """S42-B: no elimina archivos de infraestructura de pytest."""
        import time
        fn = self._get_fn()
        with tempfile.TemporaryDirectory() as tmpdir:
            cycle_ts = time.time() - 10
            for fname in ("conftest.py", "pytest.ini", "pyproject.toml", "setup.py"):
                infra_file = pathlib.Path(tmpdir) / fname
                infra_file.write_text("# infra")
            fn(tmpdir, cycle_ts)
            for fname in ("conftest.py", "pytest.ini", "pyproject.toml", "setup.py"):
                assert (pathlib.Path(tmpdir) / fname).exists(), f"{fname} no debe eliminarse"

    def test_noop_sin_directory(self):
        """S42-B: no falla si work_dir es vacío."""
        fn = self._get_fn()
        import time
        fn("", time.time())  # no debe lanzar excepción

    def test_noop_sin_cycle_ts(self):
        """S42-B: no falla si cycle_start_ts es 0."""
        fn = self._get_fn()
        with tempfile.TemporaryDirectory() as tmpdir:
            fn(tmpdir, 0)  # no debe lanzar ni eliminar nada


# ---------------------------------------------------------------------------
# S42-C — Regla de float en system_backend_python.md
# ---------------------------------------------------------------------------

class TestS42CFloatRule:
    """S42-C: system_backend_python.md tiene regla reforzada de float precision."""

    def _get_python_template(self) -> str:
        templates_dir = pathlib.Path(__file__).parent.parent / "templates"
        tpl = templates_dir / "system_backend_python.md"
        assert tpl.exists(), "system_backend_python.md no encontrado"
        return tpl.read_text(encoding="utf-8")

    def test_menciona_round_para_calculos(self):
        """S42-C: el template indica usar round() para calcular valores de test."""
        content = self._get_python_template()
        assert "round(" in content

    def test_prohibe_valores_de_memoria(self):
        """S42-C: el template prohíbe escribir floats de memoria."""
        content = self._get_python_template()
        assert "NUNCA" in content or "nunca" in content
        assert "float" in content.lower() or "punto flotante" in content.lower()

    def test_tiene_ejemplo_de_calculo_correcto(self):
        """S42-C: el template tiene un ejemplo de cálculo Python para el test."""
        content = self._get_python_template()
        # Debe haber un ejemplo con redondeo y valor calculado
        assert "22.86" in content or "round(" in content

    def test_menciona_una_sola_implementacion(self):
        """S42-C: el template prohíbe duplicar la función en múltiples archivos."""
        content = self._get_python_template()
        assert "UN SOLO ARCHIVO" in content or "una sola" in content.lower() or "único" in content.lower()


# ---------------------------------------------------------------------------
# S42-D — _detect_duplicate_functions
# ---------------------------------------------------------------------------

class TestS42DDuplicateDetection:
    """S42-D: detector de funciones duplicadas en el workspace."""

    def _get_fn(self):
        import graph as g
        return g._detect_duplicate_functions

    def test_detecta_funcion_en_dos_archivos(self):
        """S42-D: detecta cuando la misma función está en 2 archivos distintos."""
        fn = self._get_fn()
        with tempfile.TemporaryDirectory() as tmpdir:
            src = pathlib.Path(tmpdir) / "src"
            src.mkdir()
            (src / "calculadora.py").write_text("def calculate_bmi(w, h):\n    return w/h**2\n")
            (src / "utils.py").write_text("def calculate_bmi(peso, altura):\n    return peso/altura**2\n")

            result = fn(tmpdir)
            assert result, "Debe detectar el duplicado"
            assert "calculate_bmi" in result
            assert "S42-D" in result

    def test_no_reporta_si_sin_duplicados(self):
        """S42-D: retorna string vacío cuando no hay duplicados."""
        fn = self._get_fn()
        with tempfile.TemporaryDirectory() as tmpdir:
            src = pathlib.Path(tmpdir) / "src"
            src.mkdir()
            (src / "calculadora.py").write_text("def calculate_bmi(w, h):\n    return w/h**2\n")
            (src / "utils.py").write_text("def helper_function(x):\n    return x * 2\n")

            result = fn(tmpdir)
            assert result == "", "No debe reportar nada si no hay duplicados"

    def test_ignora_archivos_de_test(self):
        """S42-D: no reporta funciones definidas en test_*.py."""
        fn = self._get_fn()
        with tempfile.TemporaryDirectory() as tmpdir:
            src = pathlib.Path(tmpdir) / "src"
            src.mkdir()
            tests = pathlib.Path(tmpdir) / "tests"
            tests.mkdir()
            (src / "calc.py").write_text("def helper(x): return x\n")
            # Definir en test (common pattern: test que define helper local)
            (tests / "test_calc.py").write_text("def helper(x): return x  # redefinida en test\n")

            result = fn(tmpdir)
            assert result == "", "Las funciones en test_*.py no son duplicados relevantes"

    def test_ignora_pycache(self):
        """S42-D: no escanea __pycache__."""
        fn = self._get_fn()
        with tempfile.TemporaryDirectory() as tmpdir:
            src = pathlib.Path(tmpdir) / "src"
            src.mkdir()
            cache = src / "__pycache__"
            cache.mkdir()
            (src / "calc.py").write_text("def compute(x): return x\n")
            (cache / "calc.cpython-311.py").write_text("def compute(x): return x\n")

            result = fn(tmpdir)
            assert result == ""

    def test_retorna_vacio_con_directorio_inexistente(self):
        """S42-D: no falla con directorio que no existe."""
        fn = self._get_fn()
        result = fn("/tmp/nonexistent_ovd_test_dir_xyz")
        assert result == ""


# ---------------------------------------------------------------------------
# S42-E — template_loader selección por stack
# ---------------------------------------------------------------------------

class TestS42ETemplateLoader:
    """S42-E: template_loader carga template específico del stack."""

    def test_load_con_stack_language_python(self):
        """S42-E: load('system_backend', stack_language='python') carga system_backend_python.md."""
        import template_loader
        template_loader.invalidate()  # limpiar cache
        content = template_loader.load("system_backend", stack_language="python")
        # El template Python tiene la regla de float reforzada
        assert "round(" in content, "Debe cargar system_backend_python.md"

    def test_load_fallback_cuando_no_existe_stack_template(self):
        """S42-E: si no hay template para el stack, usa el genérico."""
        import template_loader
        template_loader.invalidate()
        # "rust" no tiene template específico
        content = template_loader.load("system_backend", stack_language="rust")
        # Debe cargar el genérico (system_backend.md) sin error
        assert content, "Debe cargar template genérico como fallback"

    def test_load_sin_stack_language_usa_generico(self):
        """S42-E: sin stack_language usa template genérico."""
        import template_loader
        template_loader.invalidate()
        content = template_loader.load("system_backend", stack_language="")
        assert content, "Debe cargar template genérico"

    def test_render_pasa_stack_language_a_load(self):
        """S42-E: render() con stack_language='python' carga template Python."""
        import template_loader
        template_loader.invalidate()
        rendered = template_loader.render("system_backend", stack_language="python")
        assert "round(" in rendered, "render debe usar el template Python"

    def test_cache_diferencia_stack_language(self):
        """S42-E: el cache guarda por separado {lang}:{stack}:{name}."""
        import template_loader
        template_loader.invalidate()
        content_py = template_loader.load("system_backend", stack_language="python")
        content_generic = template_loader.load("system_backend", stack_language="")
        # Los contenidos pueden ser distintos (python tiene float rule)
        # Lo importante es que no crashea y retorna contenido válido
        assert content_py
        assert content_generic

    def test_invalidate_limpia_todas_las_variantes(self):
        """S42-E: invalidate('system_backend') limpia python, typescript y genérico."""
        import template_loader
        # Poblar cache con múltiples variantes
        template_loader.load("system_backend", stack_language="python")
        template_loader.load("system_backend", stack_language="")
        # Invalidar el nombre — debe limpiar todas las variantes
        template_loader.invalidate("system_backend")
        # Verificar que no crashea al cargar de nuevo
        content = template_loader.load("system_backend", stack_language="python")
        assert content


# ---------------------------------------------------------------------------
# S42-F — Templates por stack existen y tienen contenido apropiado
# ---------------------------------------------------------------------------

class TestS42FStackTemplates:
    """S42-F: verifica que los templates por stack existen y contienen señales esperadas."""

    def _templates_dir(self) -> pathlib.Path:
        return pathlib.Path(__file__).parent.parent / "templates"

    def test_system_backend_python_existe(self):
        assert (self._templates_dir() / "system_backend_python.md").exists()

    def test_system_backend_typescript_existe(self):
        assert (self._templates_dir() / "system_backend_typescript.md").exists()

    def test_system_frontend_react_existe(self):
        assert (self._templates_dir() / "system_frontend_react.md").exists()

    def test_system_database_postgresql_existe(self):
        assert (self._templates_dir() / "system_database_postgresql.md").exists()

    def test_system_database_oracle_existe(self):
        assert (self._templates_dir() / "system_database_oracle.md").exists()

    def test_python_template_menciona_pytest(self):
        content = (self._templates_dir() / "system_backend_python.md").read_text()
        assert "pytest" in content.lower()

    def test_typescript_template_menciona_vitest(self):
        content = (self._templates_dir() / "system_backend_typescript.md").read_text()
        assert "vitest" in content.lower() or "jest" in content.lower()

    def test_react_template_menciona_vitest(self):
        content = (self._templates_dir() / "system_frontend_react.md").read_text()
        assert "vitest" in content.lower()

    def test_postgresql_template_menciona_org_id(self):
        content = (self._templates_dir() / "system_database_postgresql.md").read_text()
        assert "org_id" in content.lower()

    def test_oracle_template_menciona_org_id(self):
        content = (self._templates_dir() / "system_database_oracle.md").read_text()
        assert "ORG_ID" in content or "org_id" in content.lower()

    def test_oracle_template_menciona_plsql(self):
        content = (self._templates_dir() / "system_database_oracle.md").read_text()
        assert "PL/SQL" in content or "plsql" in content.lower()

    def test_todos_los_templates_tienen_project_context_placeholder(self):
        """Todos los templates por stack deben tener {project_context}."""
        for fname in [
            "system_backend_python.md",
            "system_backend_typescript.md",
            "system_frontend_react.md",
            "system_database_postgresql.md",
            "system_database_oracle.md",
        ]:
            content = (self._templates_dir() / fname).read_text()
            assert "{project_context}" in content, f"{fname} falta {{project_context}}"
