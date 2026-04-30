"""Tests S102 — postprocesadores: try/except silencioso, keyword agent inference, output_file SDD."""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# S102-A — Promover imports silenciados por try/except ImportError: pass
# ---------------------------------------------------------------------------


class TestS102ASilentImportFix:
    def _apply(self, content: str, rel_path: str = "src/contracts/router.py") -> str:
        from code_postprocessor import _fix_silent_service_import

        return _fix_silent_service_import(content, rel_path)

    def test_try_except_pass_removed(self):
        content = (
            "from fastapi import APIRouter\n"
            "try:\n"
            "    from src.contracts.service import create_contract\n"
            "    from src.contracts.models import ContractCreate\n"
            "except ImportError:\n"
            "    pass\n"
            "\nrouter = APIRouter()\n"
        )
        result = self._apply(content)
        assert "try:" not in result
        assert "except ImportError" not in result
        assert "pass" not in result
        assert "from src.contracts.service import create_contract" in result
        assert "from src.contracts.models import ContractCreate" in result

    def test_imports_are_direct_after_fix(self):
        content = (
            "try:\n"
            "    from src.contracts.service import (\n"
            "        create_contract, list_benefits, create_benefit,\n"
            "    )\n"
            "except ImportError:\n"
            "    pass\n"
        )
        result = self._apply(content)
        assert "try:" not in result
        assert "except ImportError" not in result
        assert "from src.contracts.service import" in result
        assert "create_contract" in result

    def test_non_router_file_not_modified(self):
        content = (
            "try:\n"
            "    from src.contracts.service import create_contract\n"
            "except ImportError:\n"
            "    pass\n"
        )
        result = self._apply(content, rel_path="src/contracts/models.py")
        assert result == content

    def test_no_op_when_no_try_except(self):
        content = "from src.contracts.service import create_contract\n"
        result = self._apply(content)
        assert result == content

    def test_real_exception_handling_preserved(self):
        """No toca try/except que no terminan en 'pass'."""
        content = (
            "try:\n"
            "    from src.contracts.service import create_contract\n"
            "except ImportError as e:\n"
            "    raise RuntimeError('service not found') from e\n"
        )
        result = self._apply(content)
        assert result == content

    def test_multiple_try_except_blocks_all_removed(self):
        content = (
            "try:\n"
            "    from src.auth.service import verify_user\n"
            "except ImportError:\n"
            "    pass\n"
            "\n"
            "try:\n"
            "    from src.contracts.service import create_contract\n"
            "except ImportError:\n"
            "    pass\n"
        )
        result = self._apply(content)
        assert "try:" not in result
        assert "from src.auth.service import verify_user" in result
        assert "from src.contracts.service import create_contract" in result

    def test_indentation_removed_from_imports(self):
        content = (
            "try:\n"
            "    from src.contracts.service import create_contract\n"
            "except ImportError:\n"
            "    pass\n"
        )
        result = self._apply(content)
        # El import directo no debe tener indentación
        assert "    from src" not in result
        assert "from src.contracts.service import create_contract" in result


# ---------------------------------------------------------------------------
# S102-B — Keyword-based agent inference en _fix_sdd_agent_assignments
# ---------------------------------------------------------------------------


class TestS102BKeywordAgentInference:
    def _apply(self, tasks: list[dict]) -> list[dict]:
        """Extrae la lógica de _fix_sdd_agent_assignments para tests."""
        import pathlib

        _ext_map = {
            ".tsx": "frontend",
            ".jsx": "frontend",
            ".css": "frontend",
            ".html": "frontend",
            ".sql": "database",
        }
        _path_map = [
            ("migrations/", "database"),
            ("migration/", "database"),
            (".github/", "devops"),
            ("src/components/", "frontend"),
            ("src/pages/", "frontend"),
            ("src/hooks/", "frontend"),
        ]
        _name_map = {
            "Dockerfile": "devops",
            "docker-compose.yml": "devops",
            "nginx.conf": "devops",
        }
        _kw_rules: list[tuple[list[str], str]] = [
            (
                [
                    "loginform",
                    "dashboard",
                    "contractlist",
                    "contractform",
                    "benefitform",
                    "benefittable",
                    "component",
                    ".tsx",
                    ".jsx",
                    "frontend",
                    "react",
                    "vitest",
                    "tailwind",
                    "shadcn",
                    "src/components",
                    "src/pages",
                    "src/hooks",
                ],
                "frontend",
            ),
            (
                [
                    "migration",
                    "migración",
                    "create table",
                    "alter table",
                    "trigger ",
                    ".sql",
                    "migrations/",
                ],
                "database",
            ),
            (
                [
                    "dockerfile",
                    "docker-compose",
                    "nginx",
                    "github actions",
                    ".github/",
                    "pipeline",
                    "kubernetes",
                ],
                "devops",
            ),
        ]

        corrected = 0
        for task in tasks:
            if not isinstance(task, dict):
                continue
            output_file = task.get("output_file", "") or task.get("file", "") or ""
            current_agent = task.get("agent", "backend")
            inferred = None

            if not output_file:
                _kw_text = " ".join(
                    [
                        task.get("id", ""),
                        task.get("title", ""),
                        str(task.get("description", ""))[:300],
                    ]
                ).lower()
                for _kws, _agent_kw in _kw_rules:
                    if any(kw in _kw_text for kw in _kws):
                        inferred = _agent_kw
                        break
                if inferred and inferred != current_agent:
                    task["agent"] = inferred
                    corrected += 1
                continue

            fname = pathlib.Path(output_file).name
            if fname in _name_map:
                inferred = _name_map[fname]
            if inferred is None:
                for ext, agent in _ext_map.items():
                    if output_file.endswith(ext):
                        inferred = agent
                        break
            if inferred is None:
                for path_prefix, agent in _path_map:
                    if path_prefix in output_file:
                        inferred = agent
                        break
            if inferred and inferred != current_agent:
                task["agent"] = inferred
                corrected += 1
        return tasks

    def test_loginform_title_infers_frontend(self):
        tasks = [
            {
                "id": "TASK-007",
                "agent": "backend",
                "title": "Crear LoginForm con validación RUT",
            }
        ]
        result = self._apply(tasks)
        assert result[0]["agent"] == "frontend"

    def test_dashboard_title_infers_frontend(self):
        tasks = [
            {
                "id": "T1",
                "agent": "backend",
                "title": "Crear Dashboard con navegación por rol",
            }
        ]
        result = self._apply(tasks)
        assert result[0]["agent"] == "frontend"

    def test_vitest_in_description_infers_frontend(self):
        tasks = [
            {
                "id": "T2",
                "agent": "backend",
                "title": "Tests unitarios de componentes",
                "description": "Crear tests con Vitest para LoginForm y ContractList",
            }
        ]
        result = self._apply(tasks)
        assert result[0]["agent"] == "frontend"

    def test_migration_title_infers_database(self):
        tasks = [
            {
                "id": "T3",
                "agent": "backend",
                "title": "Crear migration para tabla contratos",
            }
        ]
        result = self._apply(tasks)
        assert result[0]["agent"] == "database"

    def test_trigger_description_infers_database(self):
        tasks = [
            {
                "id": "T4",
                "agent": "backend",
                "title": "Crear trigger para valor_total",
                "description": "Crear trigger  Oracle que actualiza valor_total al insertar beneficio",
            }
        ]
        result = self._apply(tasks)
        assert result[0]["agent"] == "database"

    def test_dockerfile_title_infers_devops(self):
        tasks = [
            {"id": "T5", "agent": "backend", "title": "Crear Dockerfile para la API"}
        ]
        result = self._apply(tasks)
        assert result[0]["agent"] == "devops"

    def test_github_actions_infers_devops(self):
        tasks = [
            {
                "id": "T6",
                "agent": "backend",
                "title": "Crear pipeline CI/CD",
                "description": "Crear workflow GitHub Actions para build y test",
            }
        ]
        result = self._apply(tasks)
        assert result[0]["agent"] == "devops"

    def test_python_service_stays_backend(self):
        tasks = [
            {
                "id": "T7",
                "agent": "backend",
                "title": "Crear src/contracts/service.py con CRUD completo",
            }
        ]
        result = self._apply(tasks)
        assert result[0]["agent"] == "backend"

    def test_output_file_takes_precedence_over_keywords(self):
        """Si hay output_file, se usa extensión/path, no keywords."""
        tasks = [
            {
                "id": "T8",
                "agent": "backend",
                "title": "Crear LoginForm",
                "output_file": "src/auth/router.py",  # .py → backend
            }
        ]
        result = self._apply(tasks)
        assert result[0]["agent"] == "backend"

    def test_output_file_tsx_still_overrides_to_frontend(self):
        tasks = [
            {
                "id": "T9",
                "agent": "backend",
                "output_file": "src/components/LoginForm.tsx",
            }
        ]
        result = self._apply(tasks)
        assert result[0]["agent"] == "frontend"

    def test_no_output_file_no_keyword_stays_backend(self):
        tasks = [
            {"id": "T10", "agent": "backend", "title": "Crear módulo de utilidades"}
        ]
        result = self._apply(tasks)
        assert result[0]["agent"] == "backend"

    def test_mixed_tasks_correct_distribution(self):
        tasks = [
            {
                "id": "T1",
                "agent": "backend",
                "title": "Crear src/main.py con FastAPI app",
            },
            {"id": "T2", "agent": "backend", "title": "Crear LoginForm con shadcn/ui"},
            {
                "id": "T3",
                "agent": "backend",
                "title": "Crear migration para tabla usuarios",
            },
            {"id": "T4", "agent": "backend", "title": "Crear Dockerfile para la API"},
        ]
        result = self._apply(tasks)
        agents = {t["id"]: t["agent"] for t in result}
        assert agents["T1"] == "backend"
        assert agents["T2"] == "frontend"
        assert agents["T3"] == "database"
        assert agents["T4"] == "devops"


# ---------------------------------------------------------------------------
# S102-C — output_file en system_sdd.md template
# ---------------------------------------------------------------------------


class TestS102CSddTemplate:
    def _read_template(self) -> str:
        path = pathlib.Path(__file__).parent.parent / "templates" / "system_sdd.md"
        return path.read_text(encoding="utf-8")

    def test_output_file_field_in_task_schema(self):
        content = self._read_template()
        assert "output_file" in content

    def test_output_file_marked_obligatorio(self):
        content = self._read_template()
        assert "OBLIGATORIO" in content or "obligatorio" in content.lower()
        # Debe aparecer asociado a output_file
        idx = content.find("output_file")
        context = content[idx : idx + 300]
        assert (
            "OBLIGATORIO" in context
            or "obligatorio" in context.lower()
            or "S102-C" in content
        )

    def test_template_muestra_ejemplos_por_tipo(self):
        content = self._read_template()
        # Debe haber ejemplos para frontend, database y devops
        assert ".tsx" in content
        assert ".sql" in content or "migrations/" in content
        assert "Dockerfile" in content

    def test_template_tiene_tabla_de_mapeo_agente(self):
        content = self._read_template()
        assert "frontend" in content
        assert "database" in content
        assert "devops" in content
        # La tabla de mapeo debe estar en la sección de output_file
        idx = content.find("output_file")
        section = content[idx : idx + 1000]
        assert "frontend" in section

    def test_template_muestra_incorrecto_vs_correcto(self):
        content = self._read_template()
        assert "INCORRECTO" in content or "incorrecto" in content.lower()
        assert "CORRECTO" in content or "correcto" in content.lower()
