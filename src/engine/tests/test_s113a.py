"""
OVD Platform — Tests S113-A: estandarización services.py (plural)

Verifica que:
  1. system_sdd.md no contenga referencias a `service.py` (singular)
  2. backend_python.md tenga la regla de naming services.py
  3. _build_architecture_contract_text normalice service.py → services.py
  4. El contrato generado usa src.*.services en import_as
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Fix A — system_sdd.md no debe tener service.py (singular)
# ---------------------------------------------------------------------------


class TestSddTemplateSingularAusente:
    def test_system_sdd_no_tiene_service_py_singular(self):
        """system_sdd.md no debe referenciar service.py (singular)."""
        template_path = os.path.join(
            os.path.dirname(__file__), "..", "templates", "system_sdd.md"
        )
        content = open(template_path, encoding="utf-8").read()
        # Buscar 'service.py' que NO sea 'services.py'
        import re

        matches = re.findall(r"(?<![s])service\.py", content)
        assert matches == [], (
            f"system_sdd.md contiene {len(matches)} referencias a service.py (singular): {matches}"
        )

    def test_system_sdd_usa_services_py_plural(self):
        """system_sdd.md debe contener al menos una referencia a services.py (plural)."""
        template_path = os.path.join(
            os.path.dirname(__file__), "..", "templates", "system_sdd.md"
        )
        content = open(template_path, encoding="utf-8").read()
        assert "services.py" in content, (
            "system_sdd.md no contiene services.py (plural)"
        )

    def test_system_sdd_import_usa_services_plural(self):
        """system_sdd.md debe usar src.*.services en el ejemplo de imports."""
        template_path = os.path.join(
            os.path.dirname(__file__), "..", "templates", "system_sdd.md"
        )
        content = open(template_path, encoding="utf-8").read()
        # El ejemplo de importación debe referenciar services (plural)
        assert "src.auth.services." in content, (
            "system_sdd.md debería usar src.auth.services en el ejemplo de imports"
        )


# ---------------------------------------------------------------------------
# Fix B — backend_python.md tiene regla de naming
# ---------------------------------------------------------------------------


class TestBackendTemplateNamingRule:
    def test_backend_python_tiene_regla_services(self):
        """backend_python.md debe contener la regla de naming services.py."""
        template_path = os.path.join(
            os.path.dirname(__file__), "..", "templates", "stack", "backend_python.md"
        )
        content = open(template_path, encoding="utf-8").read()
        assert "services.py" in content and "service.py" in content, (
            "backend_python.md debe mencionar la distinción service.py vs services.py"
        )

    def test_backend_python_prohibe_service_singular(self):
        """backend_python.md debe marcar service.py como PROHIBIDO."""
        template_path = os.path.join(
            os.path.dirname(__file__), "..", "templates", "stack", "backend_python.md"
        )
        content = open(template_path, encoding="utf-8").read()
        assert "PROHIBIDO" in content and "service.py" in content, (
            "backend_python.md debe marcar service.py (singular) como PROHIBIDO"
        )


# ---------------------------------------------------------------------------
# Fix C — _build_architecture_contract_text normaliza service.py → services.py
# ---------------------------------------------------------------------------


class TestArchitectureContractNormalization:
    def _make_sdd_with_service_singular(self) -> dict:
        return {
            "tasks": [
                {
                    "id": "TASK-001",
                    "agent": "backend",
                    "title": "Crear módulo de contratos",
                    "output_file": "src/contracts/service.py",
                    "description": "Implementar create_contract y get_contract_by_id",
                    "estimated_complexity": "medium",
                }
            ]
        }

    def _make_sdd_with_services_plural(self) -> dict:
        return {
            "tasks": [
                {
                    "id": "TASK-001",
                    "agent": "backend",
                    "title": "Crear módulo de contratos",
                    "output_file": "src/contracts/services.py",
                    "description": "Implementar create_contract y get_contract_by_id",
                    "estimated_complexity": "medium",
                }
            ]
        }

    def test_contrato_normaliza_service_singular_a_services_plural(self):
        """_build_architecture_contract_text debe normalizar service.py → services.py."""
        from graph import _build_architecture_contract_text

        contract_text = _build_architecture_contract_text(
            self._make_sdd_with_service_singular()
        )
        # El contrato no debe exponer service.py al agente
        assert "service.py" not in contract_text or "services.py" in contract_text, (
            "El contrato no normalizó service.py a services.py"
        )
        assert "services.py" in contract_text, (
            "El contrato debe contener services.py (plural)"
        )

    def test_contrato_import_as_usa_services_plural(self):
        """El campo import_as del contrato debe usar src.*.services (plural)."""
        from graph import _build_architecture_contract_text

        contract_text = _build_architecture_contract_text(
            self._make_sdd_with_service_singular()
        )
        # Extraer el JSON del contrato
        import re

        json_match = re.search(r"```json\n(.+?)\n```", contract_text, re.DOTALL)
        assert json_match, "No se encontró bloque JSON en el contrato"
        contract_data = json.loads(json_match.group(1))
        entities = contract_data.get("architecture_contract", [])
        assert entities, "El contrato no tiene entities"
        import_as = entities[0].get("import_as", "")
        assert import_as.endswith(".services"), (
            f"import_as debe terminar en .services, pero es: {import_as!r}"
        )

    def test_contrato_ya_plural_no_se_modifica(self):
        """Si el SDD ya usa services.py (plural), el contrato no debe modificarlo."""
        from graph import _build_architecture_contract_text

        contract_text = _build_architecture_contract_text(
            self._make_sdd_with_services_plural()
        )
        assert "services.py" in contract_text
        assert contract_text.count("services.py") >= 1
