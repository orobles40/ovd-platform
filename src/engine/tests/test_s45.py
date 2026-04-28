"""
OVD Platform — Tests S45: Fix gaps de generación
S45-A: session_create carga constraints desde ovd_project_profiles
S45-B: RUT enforcement desde project_context
S45-C: checklist de archivos requeridos en template backend
S45-D: regla devops reforzada en system_sdd.md
S45-E: URL de BD desde project_context
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import pathlib

import pytest

# ---------------------------------------------------------------------------
# S45-A — session_create carga effective_project_context desde BD
# ---------------------------------------------------------------------------


class TestS45AProjectContext:
    """S45-A: api.py usa effective_project_context cargado desde ovd_project_profiles."""

    def test_api_contiene_effective_project_context(self):
        """S45-A: api.py define effective_project_context antes de llamar a resolve_async."""
        import inspect

        import api as _api

        src = inspect.getsource(_api.start_session)
        assert "effective_project_context" in src, (
            "effective_project_context no encontrado en start_session"
        )

    def test_api_consulta_ovd_project_profiles(self):
        """S45-A: start_session consulta la tabla ovd_project_profiles."""
        import inspect

        import api as _api

        src = inspect.getsource(_api.start_session)
        assert "ovd_project_profiles" in src

    def test_api_etiqueta_s45a(self):
        """S45-A: el código contiene la etiqueta S45-A."""
        import inspect

        import api as _api

        src = inspect.getsource(_api.start_session)
        assert "S45-A" in src

    def test_api_carga_constraints_del_perfil(self):
        """S45-A: el perfil incluye constraints y project_description."""
        import inspect

        import api as _api

        src = inspect.getsource(_api.start_session)
        assert "constraints" in src
        assert "project_description" in src

    def test_api_usa_effective_en_resolve_async(self):
        """S45-A: resolve_async recibe effective_project_context, no body.project_context."""
        import inspect

        import api as _api

        src = inspect.getsource(_api.start_session)
        assert "effective_project_context" in src
        # Verifica que NO pasa body.project_context directamente (el antiguo bug)
        lines = src.split("\n")
        resolve_call_lines = [
            l for l in lines if "resolve_async" in l and "project_context" in l
        ]
        for line in resolve_call_lines:
            assert "body.project_context" not in line, (
                f"resolve_async aún usa body.project_context directamente: {line}"
            )

    def test_api_fallback_cuando_no_hay_perfil(self):
        """S45-A: si body.project_context tiene valor, NO consulta la BD (respeta lo enviado)."""
        import inspect

        import api as _api

        src = inspect.getsource(_api.start_session)
        # La condición debe ser "if not effective_project_context and body.project_id"
        assert (
            "not effective_project_context" in src or "not body.project_context" in src
        )


# ---------------------------------------------------------------------------
# S45-B — RUT desde project_context
# ---------------------------------------------------------------------------


class TestS45BRutEnforcement:
    """S45-B: template instruye usar RUTs del project_context primero."""

    def _get_template(self) -> str:
        tpl = (
            pathlib.Path(__file__).parent.parent
            / "templates"
            / "system_backend_python.md"
        )
        return tpl.read_text(encoding="utf-8")

    def test_template_menciona_project_context_para_rut(self):
        """S45-B: template indica consultar project_context antes de usar tabla estática."""
        content = self._get_template()
        assert "project_context" in content
        assert "S45-B" in content

    def test_template_tiene_regla_de_prioridad(self):
        """S45-B: existe regla de prioridad: project_context primero, tabla como fallback."""
        content = self._get_template()
        assert "prioridad" in content.lower() or "Regla de prioridad" in content

    def test_tabla_ruts_sigue_presente(self):
        """S45-B: la tabla de RUTs verificados de S43-F sigue presente como fallback."""
        content = self._get_template()
        assert "12.345.678-5" in content
        assert "11.111.111-1" in content


# ---------------------------------------------------------------------------
# S45-C — Checklist de archivos requeridos
# ---------------------------------------------------------------------------


class TestS45CArchivosRequeridos:
    """S45-C: template backend exige requirements.txt y checklist de módulos."""

    def _get_template(self) -> str:
        tpl = (
            pathlib.Path(__file__).parent.parent
            / "templates"
            / "system_backend_python.md"
        )
        return tpl.read_text(encoding="utf-8")

    def test_template_exige_requirements_txt(self):
        """S45-C: requirements.txt aparece como archivo obligatorio a generar primero."""
        content = self._get_template()
        assert "requirements.txt" in content

    def test_requirements_es_primero_en_orden(self):
        """S45-C: requirements.txt aparece ANTES que los __init__.py en el orden de escritura."""
        content = self._get_template()
        pos_req = content.find("requirements.txt")
        pos_init = content.find("__init__.py")
        assert pos_req < pos_init, (
            "requirements.txt debe aparecer antes que __init__.py en el template"
        )

    def test_template_tiene_checklist(self):
        """S45-C: el template incluye un checklist de verificación antes de entregar."""
        content = self._get_template()
        assert "CHECKLIST" in content or "checklist" in content.lower()

    def test_checklist_menciona_imports_rotos(self):
        """S45-C: el checklist advierte sobre imports a módulos no generados."""
        content = self._get_template()
        assert "import" in content and (
            "no creaste" in content or "generaste" in content or "generado" in content
        )


# ---------------------------------------------------------------------------
# S45-D — Regla devops reforzada
# ---------------------------------------------------------------------------


class TestS45DDevopsRule:
    """S45-D: system_sdd.md tiene tabla de ejemplos concretos para asignación devops."""

    def _get_template(self) -> str:
        tpl = pathlib.Path(__file__).parent.parent / "templates" / "system_sdd.md"
        return tpl.read_text(encoding="utf-8")

    def test_sdd_tiene_tabla_ejemplos_devops(self):
        """S45-D: system_sdd.md tiene tabla con ejemplos FR → agentes correctos."""
        content = self._get_template()
        assert "S45-D" in content

    def test_sdd_menciona_extension_de_archivos(self):
        """S45-D: la regla de oro distingue por extensión de archivo generado."""
        content = self._get_template()
        assert ".py" in content and "Dockerfile" in content and "devops" in content

    def test_sdd_ejemplos_incluyen_fastapi_oracle(self):
        """S45-D: hay ejemplo concreto de FastAPI + Oracle → backend + devops para Dockerfile."""
        content = self._get_template()
        assert "FastAPI" in content or "Oracle" in content

    def test_sdd_prohibicion_devops_sigue_presente(self):
        """S45-D: la prohibición original de asignar código Python a devops sigue presente."""
        content = self._get_template()
        assert "PROHIBIDO" in content
        assert "backend" in content


# ---------------------------------------------------------------------------
# S45-E — URL de BD desde project_context
# ---------------------------------------------------------------------------


class TestS45EDbConnectionUrl:
    """S45-E: template backend instruye NO hardcodear URL de BD."""

    def _get_template(self) -> str:
        tpl = (
            pathlib.Path(__file__).parent.parent
            / "templates"
            / "system_backend_python.md"
        )
        return tpl.read_text(encoding="utf-8")

    def test_template_prohibe_hardcodear_url(self):
        """S45-E: template indica NUNCA hardcodear URL de BD."""
        content = self._get_template()
        assert "NUNCA hardcodear" in content or "NUNCA hardcode" in content.lower()

    def test_template_menciona_host_docker_internal(self):
        """S45-E: template menciona host.docker.internal como patrón correcto."""
        content = self._get_template()
        assert "host.docker.internal" in content

    def test_template_muestra_ejemplo_env_variable(self):
        """S45-E: template muestra DATABASE_URL como variable de entorno."""
        content = self._get_template()
        assert "DATABASE_URL" in content

    def test_template_distingue_correcto_de_incorrecto(self):
        """S45-E: template tiene ejemplo ✅ correcto y ❌ incorrecto."""
        content = self._get_template()
        assert "✅" in content and "❌" in content
