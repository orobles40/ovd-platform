"""
OVD Platform — Tests S58-pre: Template Stack Transversality

TP-10: Tests de contenido — instrucciones críticas en los archivos correctos
TP-11: Tests de composición — render_composed() produce output correcto por stack
TP-12: Tests de regresión — sistema base sin degradación vs S57
"""

import os
import pathlib
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

import template_loader

TEMPLATES_DIR = pathlib.Path(__file__).parent.parent / "templates"
STACK_DIR = TEMPLATES_DIR / "stack"


# ---------------------------------------------------------------------------
# TP-10-A: Verificar que stack/ existe y tiene los archivos esperados
# ---------------------------------------------------------------------------


class TestTP10StackDirectoryContent:
    """TP-10-A: archivos de stack existen en el directorio correcto."""

    def test_stack_directory_exists(self):
        assert STACK_DIR.exists(), f"Directorio stack/ no encontrado en {STACK_DIR}"

    def test_backend_python_exists(self):
        assert (STACK_DIR / "backend_python.md").exists()

    def test_backend_typescript_exists(self):
        assert (STACK_DIR / "backend_typescript.md").exists()

    def test_backend_rust_exists(self):
        assert (STACK_DIR / "backend_rust.md").exists()

    def test_backend_java_exists(self):
        assert (STACK_DIR / "backend_java.md").exists()

    def test_backend_go_exists(self):
        assert (STACK_DIR / "backend_go.md").exists()

    def test_frontend_react_exists(self):
        assert (STACK_DIR / "frontend_react.md").exists()

    def test_database_oracle_exists(self):
        assert (STACK_DIR / "database_oracle.md").exists()


# ---------------------------------------------------------------------------
# TP-10-B: system_backend.md base solo tiene reglas universales
# ---------------------------------------------------------------------------


class TestTP10BackendBaseIsUniversal:
    """TP-10-B: system_backend.md no contiene instrucciones Python-specific."""

    def _load_base(self) -> str:
        path = TEMPLATES_DIR / "system_backend.md"
        return path.read_text(encoding="utf-8")

    def test_base_has_security_rules(self):
        """Reglas de seguridad universales presentes."""
        content = self._load_base()
        assert "Multi-tenancy" in content
        assert "org_id" in content

    def test_base_has_output_format(self):
        """Formato de salida con fences presente."""
        content = self._load_base()
        assert "```lang:ruta" in content or "Formato de salida" in content

    def test_base_has_tdd_methodology(self):
        """Metodología TDD presente en base."""
        content = self._load_base()
        assert "TDD" in content or "RED" in content

    def test_base_does_not_have_pydantic(self):
        """Pydantic v2 es Python-specific — no debe estar en la base universal."""
        content = self._load_base()
        assert "Pydantic" not in content, (
            "system_backend.md base no debe contener instrucciones de Pydantic (Python-specific)"
        )

    def test_base_does_not_have_pytest_ini(self):
        """pytest.ini es Python-specific — no debe estar en la base universal."""
        content = self._load_base()
        assert "pytest.ini" not in content, (
            "system_backend.md base no debe contener pytest.ini (Python-specific)"
        )

    def test_base_does_not_have_conftest(self):
        """conftest.py es Python-specific — no debe estar en la base universal."""
        content = self._load_base()
        assert "conftest.py" not in content, (
            "system_backend.md base no debe contener conftest.py (Python-specific)"
        )


# ---------------------------------------------------------------------------
# TP-10-C: stack/backend_python.md tiene todas las instrucciones críticas
# ---------------------------------------------------------------------------


class TestTP10PythonStackHasCriticalInstructions:
    """TP-10-C: instrucciones críticas migradas correctamente a stack/backend_python.md."""

    def _load_stack(self) -> str:
        return (STACK_DIR / "backend_python.md").read_text(encoding="utf-8")

    def test_python_stack_has_orden_escritura(self):
        """ORDEN DE ESCRITURA presente — S32-B crítico para pytest."""
        content = self._load_stack()
        assert "ORDEN DE ESCRITURA" in content

    def test_python_stack_has_conftest(self):
        """conftest.py obligatorio presente."""
        content = self._load_stack()
        assert "conftest.py" in content
        assert "sys.path.insert" in content

    def test_python_stack_has_pytest_ini(self):
        """pytest.ini presente."""
        content = self._load_stack()
        assert "pytest.ini" in content

    def test_python_stack_has_pydantic_v2(self):
        """Pydantic v2 con @field_validator presente — S50-C."""
        content = self._load_stack()
        assert "field_validator" in content
        assert "Pydantic v2" in content

    def test_python_stack_has_float_rule_s53a(self):
        """Regla S53-A: round() en asserts, no float literals."""
        content = self._load_stack()
        assert "S53-A" in content or "round(" in content

    def test_python_stack_has_rut_validation(self):
        """Validación de RUT chileno con módulo 11 presente."""
        content = self._load_stack()
        assert "validate_rut" in content
        assert (
            "módulo 11" in content or "module 11" in content or "remainder" in content
        )

    def test_python_stack_has_rut_test_table(self):
        """Tabla de RUTs válidos para tests presente — S43-F."""
        content = self._load_stack()
        assert "12.345.678-5" in content  # DV correcto para body 12345678

    def test_python_stack_has_s45b_priority_rule(self):
        """Regla S45-B: prioridad al project_context para RUTs."""
        content = self._load_stack()
        assert "project_context" in content or "S45-B" in content

    def test_python_stack_has_prohibicion_init_raiz(self):
        """Prohibición de __init__.py en raíz presente."""
        content = self._load_stack()
        assert "__init__.py" in content
        assert "RAÍZ" in content or "raíz" in content or "NUNCA" in content

    def test_python_stack_has_host_docker_internal(self):
        """Regla de conexión Oracle vía host.docker.internal — S45-E."""
        content = self._load_stack()
        assert "host.docker.internal" in content


# ---------------------------------------------------------------------------
# TP-11: Tests de composición — render_composed() produce output correcto
# ---------------------------------------------------------------------------


class TestTP11RenderComposed:
    """TP-11: render_composed() combina base + stack correctamente."""

    def setup_method(self):
        """Invalidar cache antes de cada test para evitar interferencia."""
        template_loader.invalidate()

    def test_render_composed_returns_string(self):
        """render_composed() retorna string no vacío."""
        result = template_loader.render_composed(
            "system_backend", stack_language="python"
        )
        assert isinstance(result, str)
        assert len(result) > 100

    def test_render_composed_python_includes_base(self):
        """Con stack=python, el resultado incluye reglas de la base universal."""
        result = template_loader.render_composed(
            "system_backend", stack_language="python"
        )
        # Reglas universales de la base
        assert "Multi-tenancy" in result
        assert "TDD" in result

    def test_render_composed_python_includes_stack_section(self):
        """Con stack=python, el resultado incluye la sección de stack Python."""
        result = template_loader.render_composed(
            "system_backend", stack_language="python"
        )
        # Contenido específico de stack/backend_python.md
        assert "conftest.py" in result
        assert "field_validator" in result

    def test_render_composed_no_stack_returns_base_only(self):
        """Sin stack_language, retorna solo la base (sin sección stack)."""
        result = template_loader.render_composed("system_backend", stack_language="")
        assert "conftest.py" not in result  # No tiene Python-specific
        assert "Convenciones del stack" not in result

    def test_render_composed_typescript_includes_ts_section(self):
        """Con stack=typescript, incluye sección TypeScript."""
        result = template_loader.render_composed(
            "system_backend", stack_language="typescript"
        )
        assert "Convenciones del stack (typescript)" in result
        assert "tsconfig.json" in result

    def test_render_composed_rust_includes_rust_section(self):
        """Con stack=rust, incluye sección Rust."""
        result = template_loader.render_composed(
            "system_backend", stack_language="rust"
        )
        assert "Convenciones del stack (rust)" in result
        assert "Cargo.toml" in result

    def test_render_composed_unknown_stack_returns_base(self):
        """Con stack desconocido (sin archivo), retorna solo la base sin error."""
        result = template_loader.render_composed(
            "system_backend", stack_language="cobol"
        )
        assert len(result) > 50
        assert "Convenciones del stack" not in result

    def test_render_composed_with_variables(self):
        """Variables de sustitución funcionan en el template compuesto."""
        result = template_loader.render_composed(
            "system_backend",
            stack_language="python",
            project_context="## Proyecto X\n- Oracle 19c\n- FastAPI",
            retry_feedback="Error en test_imc.py",
        )
        assert "Proyecto X" in result
        assert "Error en test_imc.py" in result

    def test_render_composed_frontend_react(self):
        """Frontend con stack=react incluye Tailwind/shadcn sección."""
        result = template_loader.render_composed(
            "system_frontend", stack_language="react"
        )
        assert "Convenciones del stack (react)" in result
        assert "shadcn" in result.lower() or "tailwind" in result.lower()

    def test_render_composed_database_oracle(self):
        """Database con stack=oracle incluye host.docker.internal."""
        result = template_loader.render_composed(
            "system_database", stack_language="oracle"
        )
        assert "Convenciones del stack (oracle)" in result
        assert "host.docker.internal" in result

    def test_render_composed_is_longer_than_base(self):
        """El template compuesto es más largo que la base sola."""
        base = template_loader.render("system_backend", stack_language="")
        composed = template_loader.render_composed(
            "system_backend", stack_language="python"
        )
        assert len(composed) > len(base), (
            "render_composed() debe ser más largo que el base solo"
        )

    def test_render_composed_contains_separator(self):
        """El template compuesto tiene el separador --- entre base y stack."""
        result = template_loader.render_composed(
            "system_backend", stack_language="python"
        )
        assert "---" in result
        assert "Convenciones del stack" in result


# ---------------------------------------------------------------------------
# TP-12: Tests de regresión — sistema sin degradación vs S57
# ---------------------------------------------------------------------------


class TestTP12Regression:
    """TP-12: tests de regresión para verificar cero degradación vs S57."""

    def setup_method(self):
        template_loader.invalidate()

    def test_render_function_still_works(self):
        """render() original sigue funcionando sin cambios de comportamiento."""
        result = template_loader.render("system_backend", stack_language="python")
        assert isinstance(result, str)
        assert len(result) > 100

    def test_load_function_still_works(self):
        """load() original sigue funcionando."""
        result = template_loader.load("system_backend")
        assert isinstance(result, str)
        assert len(result) > 50

    def test_invalidate_clears_cache(self):
        """invalidate() sigue limpiando cache correctamente."""
        template_loader.render("system_backend")
        template_loader.invalidate("system_backend")
        # El cache para system_backend debe estar vacío ahora
        result = template_loader.render("system_backend")
        assert result  # debe cargar de nuevo sin error

    def test_invalidate_all_clears_everything(self):
        """invalidate() sin args limpia todo el cache."""
        template_loader.render("system_backend")
        template_loader.render("system_sdd")
        template_loader.invalidate()
        # Ambos se deben poder recargar sin error
        assert template_loader.render("system_backend")
        assert template_loader.render("system_sdd")

    def test_system_sdd_template_intact(self):
        """system_sdd.md no fue modificado por S58-pre."""
        result = template_loader.render("system_sdd")
        assert (
            "SDD" in result
            or "Spec-Driven" in result
            or "especificacion" in result.lower()
        )

    def test_system_qa_template_intact(self):
        """system_qa.md no fue modificado por S58-pre."""
        result = template_loader.render("system_qa")
        assert "QA" in result or "qa" in result.lower() or "calidad" in result.lower()

    def test_system_security_template_intact(self):
        """system_security.md no fue modificado por S58-pre."""
        result = template_loader.render("system_security")
        assert (
            "seguridad" in result.lower()
            or "security" in result.lower()
            or "OWASP" in result
        )

    def test_python_composed_has_orden_escritura_s32b(self):
        """S32-B: ORDEN DE ESCRITURA presente en el template compuesto Python."""
        result = template_loader.render_composed(
            "system_backend", stack_language="python"
        )
        assert "ORDEN DE ESCRITURA" in result, (
            "S32-B: ORDEN DE ESCRITURA debe estar en el template compuesto Python"
        )

    def test_python_composed_has_round_asserts_s53a(self):
        """S53-A: instrucción de round() en asserts presente en template compuesto Python."""
        result = template_loader.render_composed(
            "system_backend", stack_language="python"
        )
        assert "S53-A" in result or "round(" in result, (
            "S53-A: instrucción de round() debe estar en el template compuesto Python"
        )

    def test_python_composed_has_rut_valid_table(self):
        """Tabla de RUTs válidos presente en template compuesto Python (S43-F)."""
        result = template_loader.render_composed(
            "system_backend", stack_language="python"
        )
        assert "12.345.678-5" in result, (
            "Tabla de RUTs válidos debe estar en el template compuesto Python"
        )

    def test_thread_safety_lock_exists(self):
        """S58-pre: _cache_lock existe en template_loader."""
        import template_loader as tl

        assert hasattr(tl, "_cache_lock"), (
            "_cache_lock no encontrado en template_loader"
        )
        import threading

        assert isinstance(tl._cache_lock, type(threading.Lock())), (
            "_cache_lock debe ser un threading.Lock"
        )

    def test_render_composed_exported(self):
        """render_composed() es accesible desde template_loader."""
        assert hasattr(template_loader, "render_composed"), (
            "render_composed no está exportada desde template_loader"
        )
        assert callable(template_loader.render_composed)
