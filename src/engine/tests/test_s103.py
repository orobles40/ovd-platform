"""Tests S103 — P1 Shared Type Contract + P2 Undefined Import Names validator."""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from graph import (
    _build_single_task_sdd_content,
    _build_type_contract,
    _check_undefined_import_names,
    _fix_sdd_agent_assignments,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sdd_with_tasks(*tasks):
    return {
        "summary": "Test SDD",
        "tasks": list(tasks),
        "requirements": [],
        "design": {},
        "constraints": [],
    }


def _py_task(output_file, description, title=""):
    return {
        "id": "T-001",
        "agent": "backend",
        "output_file": output_file,
        "description": description,
        "title": title,
    }


# ---------------------------------------------------------------------------
# S103-P1 — _build_type_contract
# ---------------------------------------------------------------------------


class TestBuildTypeContractEmpty:
    def test_empty_sdd_returns_empty(self):
        assert _build_type_contract({}) == ""

    def test_no_tasks_returns_empty(self):
        assert _build_type_contract({"tasks": []}) == ""

    def test_only_non_py_tasks_returns_empty(self):
        sdd = _sdd_with_tasks(
            {
                "id": "T-1",
                "output_file": "src/components/Login.tsx",
                "description": "def validate_rut(rut)",
                "title": "",
            },
            {
                "id": "T-2",
                "output_file": "migrations/001.sql",
                "description": "CREATE TABLE users",
                "title": "",
            },
        )
        assert _build_type_contract(sdd) == ""

    def test_py_task_no_functions_returns_empty(self):
        sdd = _sdd_with_tasks(
            _py_task("src/main.py", "Crear archivo de configuración sin funciones")
        )
        # No S72-A, no backtick def, no function list → no entries → empty
        assert _build_type_contract(sdd) == ""


class TestBuildTypeContractS72A:
    def test_s72a_simple_function_extracted(self):
        desc = "[S72-A] USA EXACTAMENTE: `def validate_rut(rut: str) -> bool:` en src/utils/rut_validator.py."
        sdd = _sdd_with_tasks(_py_task("src/utils/rut_validator.py", desc))
        result = _build_type_contract(sdd)
        assert "validate_rut" in result
        assert "S103-P1" in result

    def test_s72a_mandatory_marker_present(self):
        desc = "[S72-A] USA EXACTAMENTE: `def validate_rut(rut: str) -> bool:` NO uses 'validar_rut'."
        sdd = _sdd_with_tasks(_py_task("src/utils/rut_validator.py", desc))
        result = _build_type_contract(sdd)
        assert "OBLIGATORIO (S72-A)" in result

    def test_s72a_two_functions_slash_separated(self):
        desc = "[S72-A] USA EXACTAMENTE: `def list_benefits(contract_id, db)` / `def create_benefit(data, db)`."
        sdd = _sdd_with_tasks(_py_task("src/contracts/services.py", desc))
        result = _build_type_contract(sdd)
        assert "list_benefits" in result
        assert "create_benefit" in result

    def test_s72a_class_hint_extracted(self):
        desc = "[S72-A] USA EXACTAMENTE: `class ContractCreate(BaseModel)` para el schema de creación."
        sdd = _sdd_with_tasks(_py_task("src/contracts/models.py", desc))
        result = _build_type_contract(sdd)
        assert "ContractCreate" in result
        assert "OBLIGATORIO (S72-A)" in result

    def test_s72a_grouped_by_output_file(self):
        desc_rut = "[S72-A] USA EXACTAMENTE: `def validate_rut(rut: str) -> bool:`"
        desc_prime = "[S72-A] USA EXACTAMENTE: `def is_prime(n: int) -> bool:`"
        sdd = _sdd_with_tasks(
            _py_task("src/utils/rut_validator.py", desc_rut),
            _py_task("src/utils/prime_validator.py", desc_prime),
        )
        result = _build_type_contract(sdd)
        assert "src/utils/rut_validator.py" in result
        assert "src/utils/prime_validator.py" in result
        assert "validate_rut" in result
        assert "is_prime" in result
        # prime_validator.py < rut_validator.py alfabéticamente → is_prime aparece primero
        idx_rut = result.index("validate_rut")
        idx_prime = result.index("is_prime")
        assert idx_prime < idx_rut


class TestBuildTypeContractBacktick:
    def test_backtick_def_extracted_without_s72a(self):
        desc = "Crear src/imc/service.py con la función `def calculate_bmi(weight_kg: float, height_m: float)`."
        sdd = _sdd_with_tasks(_py_task("src/imc/service.py", desc))
        result = _build_type_contract(sdd)
        assert "calculate_bmi" in result

    def test_backtick_def_no_mandatory_marker(self):
        desc = "Crear archivo con `def calculate_bmi(weight_kg, height_m)` para el cálculo."
        sdd = _sdd_with_tasks(_py_task("src/imc/service.py", desc))
        result = _build_type_contract(sdd)
        # Backtick def is not S72-A → no OBLIGATORIO marker
        assert "OBLIGATORIO (S72-A)" not in result

    def test_backtick_def_deduplicated_with_s72a(self):
        desc = (
            "[S72-A] USA EXACTAMENTE: `def validate_rut(rut: str) -> bool:` NO uses 'validar_rut'.\n"
            "Implementar `def validate_rut(rut: str) -> bool:` en el módulo."
        )
        sdd = _sdd_with_tasks(_py_task("src/utils/rut_validator.py", desc))
        result = _build_type_contract(sdd)
        # Should appear only once
        assert result.count("validate_rut") == 1
        # S72-A version wins → OBLIGATORIO present
        assert "OBLIGATORIO (S72-A)" in result


class TestBuildTypeContractFuncList:
    def test_function_list_after_funciones_keyword(self):
        desc = "Crear src/contracts/services.py con funciones create_contract(data, user), get_contract_by_id(id, user), update_contract_status(id, status)."
        sdd = _sdd_with_tasks(_py_task("src/contracts/services.py", desc))
        result = _build_type_contract(sdd)
        assert "create_contract" in result
        assert "get_contract_by_id" in result
        assert "update_contract_status" in result

    def test_short_names_excluded_from_func_list(self):
        desc = "Crear src/app.py con funciones app(), run(), go()."
        sdd = _sdd_with_tasks(_py_task("src/app.py", desc))
        result = _build_type_contract(sdd)
        # Names < 5 chars should not appear
        if result:
            assert "def app(...)" not in result
            assert "def run(...)" not in result

    def test_python_builtins_excluded(self):
        desc = "Usar list(), dict(), str() en funciones de utilidad."
        sdd = _sdd_with_tasks(_py_task("src/utils/helpers.py", desc))
        result = _build_type_contract(sdd)
        if result:
            assert "def list(...)" not in result
            assert "def dict(...)" not in result


class TestBuildTypeContractOutput:
    def test_header_present(self):
        desc = "[S72-A] USA EXACTAMENTE: `def validate_rut(rut: str) -> bool:`"
        sdd = _sdd_with_tasks(_py_task("src/utils/rut_validator.py", desc))
        result = _build_type_contract(sdd)
        assert "S103-P1" in result
        assert "CONTRATO DE TIPOS" in result

    def test_footer_prohibition_present(self):
        desc = "[S72-A] USA EXACTAMENTE: `def validate_rut(rut: str) -> bool:`"
        sdd = _sdd_with_tasks(_py_task("src/utils/rut_validator.py", desc))
        result = _build_type_contract(sdd)
        assert "PROHIBIDO" in result

    def test_module_path_in_output(self):
        desc = "[S72-A] USA EXACTAMENTE: `def is_prime(n: int) -> bool:`"
        sdd = _sdd_with_tasks(_py_task("src/utils/prime_validator.py", desc))
        result = _build_type_contract(sdd)
        assert "src/utils/prime_validator.py" in result

    def test_file_field_fallback(self):
        task = {
            "id": "T-1",
            "agent": "backend",
            "file": "src/utils/rut_validator.py",
            "description": "[S72-A] USA EXACTAMENTE: `def validate_rut(rut: str) -> bool:`",
            "title": "",
        }
        sdd = _sdd_with_tasks(task)
        result = _build_type_contract(sdd)
        assert "validate_rut" in result


# ---------------------------------------------------------------------------
# S103-P1 — Inyección en _build_single_task_sdd_content
# ---------------------------------------------------------------------------


class TestTypeContractInjection:
    def _make_sdd(self):
        return {
            "summary": "Sistema de gestión de contratos",
            "requirements": [
                {"id": "REQ-001", "description": "Login con RUT", "priority": "must"}
            ],
            "design": {"overview": "FastAPI + Oracle"},
            "constraints": [],
            "tasks": [
                {
                    "id": "TASK-001",
                    "agent": "backend",
                    "output_file": "src/utils/rut_validator.py",
                    "description": "[S72-A] USA EXACTAMENTE: `def validate_rut(rut: str) -> bool:` NO uses 'validar_rut'.",
                    "title": "Crear validador de RUT",
                    "depends_on": [],
                },
                {
                    "id": "TASK-002",
                    "agent": "backend",
                    "output_file": "src/contracts/services.py",
                    "description": "Crear src/contracts/services.py con funciones create_contract(data, user), get_contract_by_id(id, user).",
                    "title": "Crear servicios de contrato",
                    "depends_on": ["TASK-001"],
                },
            ],
        }

    def test_contract_injected_in_output(self):
        sdd = self._make_sdd()
        task = sdd["tasks"][0]
        result = _build_single_task_sdd_content(sdd, "backend", task, 0, 2)
        assert "S103-P1" in result
        assert "validate_rut" in result

    def test_contract_appears_before_summary(self):
        sdd = self._make_sdd()
        task = sdd["tasks"][0]
        result = _build_single_task_sdd_content(sdd, "backend", task, 0, 2)
        idx_contract = result.find("S103-P1")
        idx_summary = result.find("## Summary")
        assert idx_contract < idx_summary

    def test_no_contract_when_no_py_functions(self):
        sdd = {
            "summary": "SQL only project",
            "requirements": [],
            "design": {},
            "constraints": [],
            "tasks": [
                {
                    "id": "TASK-001",
                    "agent": "database",
                    "output_file": "migrations/001_create_tables.sql",
                    "description": "CREATE TABLE usuarios",
                    "title": "Migración inicial",
                    "depends_on": [],
                }
            ],
        }
        task = sdd["tasks"][0]
        result = _build_single_task_sdd_content(sdd, "database", task, 0, 1)
        assert "S103-P1" not in result

    def test_contract_lists_all_modules(self):
        sdd = self._make_sdd()
        task = sdd["tasks"][1]
        result = _build_single_task_sdd_content(sdd, "backend", task, 1, 2)
        assert "src/utils/rut_validator.py" in result
        assert "src/contracts/services.py" in result

    def test_mandatory_marker_in_injected_content(self):
        sdd = self._make_sdd()
        task = sdd["tasks"][0]
        result = _build_single_task_sdd_content(sdd, "backend", task, 0, 2)
        assert "OBLIGATORIO (S72-A)" in result


# ---------------------------------------------------------------------------
# S103-P2 — _check_undefined_import_names
# ---------------------------------------------------------------------------


class TestCheckUndefinedImportNames:
    def _write(self, tmp_path, rel_path: str, content: str):
        full = tmp_path / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
        return str(rel_path)

    def _make_result(self, *artifact_paths):
        return [
            {"agent": "backend", "artifacts": [{"path": p} for p in artifact_paths]}
        ]

    def test_nonexistent_directory_returns_ok(self):
        ok, _ = _check_undefined_import_names([], "/no/existe")
        assert ok is True

    def test_all_imports_defined_returns_ok(self, tmp_path):
        self._write(
            tmp_path,
            "src/contracts/services.py",
            "def create_contract(data, user): pass\ndef get_contract_by_id(id, user): pass\n",
        )
        self._write(
            tmp_path,
            "tests/test_contracts.py",
            "from src.contracts.services import create_contract, get_contract_by_id\n",
        )
        ok, feedback = _check_undefined_import_names(
            self._make_result("tests/test_contracts.py"), str(tmp_path)
        )
        assert ok is True
        assert feedback == ""

    def test_missing_function_detected(self, tmp_path):
        self._write(
            tmp_path,
            "src/contracts/services.py",
            "def create_contract(data, user): pass\n",
        )
        self._write(
            tmp_path,
            "tests/test_contracts.py",
            "from src.contracts.services import create_contract, list_contracts\n",
        )
        ok, feedback = _check_undefined_import_names(
            self._make_result("tests/test_contracts.py"), str(tmp_path)
        )
        assert ok is False
        assert "list_contracts" in feedback
        assert "S103-P2" in feedback

    def test_defined_function_not_reported(self, tmp_path):
        self._write(
            tmp_path,
            "src/utils/rut_validator.py",
            "def validate_rut(rut: str) -> bool: return True\n",
        )
        self._write(
            tmp_path,
            "tests/test_rut.py",
            "from src.utils.rut_validator import validate_rut\n",
        )
        ok, _ = _check_undefined_import_names([], str(tmp_path))
        assert ok is True

    def test_unknown_module_skipped(self, tmp_path):
        # Si el módulo no existe en disco, S65-A ya lo reporta — P2 lo ignora
        self._write(
            tmp_path,
            "tests/test_x.py",
            "from src.nonexistent.module import something\n",
        )
        ok, feedback = _check_undefined_import_names([], str(tmp_path))
        assert ok is True  # módulo no en module_exports → skip

    def test_multiple_missing_names_all_reported(self, tmp_path):
        self._write(
            tmp_path,
            "src/contracts/services.py",
            "def create_contract(data, user): pass\n",
        )
        self._write(
            tmp_path,
            "tests/test_contracts.py",
            "from src.contracts.services import create_contract, list_contracts, delete_contract\n",
        )
        ok, feedback = _check_undefined_import_names(
            self._make_result("tests/test_contracts.py"), str(tmp_path)
        )
        assert ok is False
        assert "list_contracts" in feedback
        assert "delete_contracts" not in feedback  # delete_contracts wasn't imported
        assert "delete_contract" in feedback

    def test_class_import_validated(self, tmp_path):
        self._write(
            tmp_path,
            "src/contracts/models.py",
            "class ContractCreate: pass\n",
        )
        self._write(
            tmp_path,
            "tests/test_models.py",
            "from src.contracts.models import ContractCreate, ContratoCreate\n",
        )
        ok, feedback = _check_undefined_import_names([], str(tmp_path))
        assert ok is False
        assert "ContratoCreate" in feedback
        assert "ContractCreate" not in feedback  # exists → not reported

    def test_star_import_not_reported(self, tmp_path):
        self._write(
            tmp_path,
            "src/contracts/services.py",
            "def create_contract(data, user): pass\n",
        )
        self._write(
            tmp_path,
            "tests/test_star.py",
            "from src.contracts.services import *\n",
        )
        ok, _ = _check_undefined_import_names([], str(tmp_path))
        assert ok is True  # star imports skip the check

    def test_stdlib_not_checked(self, tmp_path):
        # pathlib, os, etc. are not in module_exports → skip by design
        self._write(
            tmp_path,
            "tests/test_std.py",
            "from pathlib import Path\nfrom os import environ\n",
        )
        ok, _ = _check_undefined_import_names([], str(tmp_path))
        assert ok is True

    def test_test_files_auto_discovered(self, tmp_path):
        # test_*.py en disco deben verificarse aunque no estén en agent_results
        self._write(
            tmp_path,
            "src/auth/services.py",
            "def login(rut, password): pass\n",
        )
        self._write(
            tmp_path,
            "tests/test_auth.py",
            "from src.auth.services import login, logout\n",
        )
        ok, feedback = _check_undefined_import_names([], str(tmp_path))
        assert ok is False
        assert "logout" in feedback

    def test_feedback_contains_module_path(self, tmp_path):
        self._write(
            tmp_path,
            "src/contracts/services.py",
            "def create_contract(data, user): pass\n",
        )
        self._write(
            tmp_path,
            "tests/test_contracts.py",
            "from src.contracts.services import list_contracts\n",
        )
        ok, feedback = _check_undefined_import_names([], str(tmp_path))
        assert "src.contracts.services" in feedback
        assert "CAUSA" in feedback

    def test_async_function_defined(self, tmp_path):
        self._write(
            tmp_path,
            "src/auth/services.py",
            "async def authenticate(rut, password): pass\n",
        )
        self._write(
            tmp_path,
            "tests/test_auth.py",
            "from src.auth.services import authenticate\n",
        )
        ok, _ = _check_undefined_import_names([], str(tmp_path))
        assert ok is True


# ---------------------------------------------------------------------------
# S103-P3 — Refinamiento keywords S102-B: "frontend" eliminado
# ---------------------------------------------------------------------------


class TestS103P3KeywordRefinement:
    """Valida _fix_sdd_agent_assignments real (no copia local) con los keywords de P3."""

    def _task(self, title="", description="", agent="backend", task_id="T-1"):
        return {
            "id": task_id,
            "agent": agent,
            "title": title,
            "description": description,
        }

    def test_frontend_standalone_does_not_reroute_devops_task(self):
        # Bug S102: task con agent=devops, sin output_file, descripción menciona "frontend"
        # como nombre de servicio (no React) → OLD code lo re-ruteaba a frontend.
        # NEW code: "frontend" eliminado de keywords → task permanece en devops.
        tasks = [
            {
                "id": "T-1",
                "agent": "devops",
                "title": "Configurar reverse proxy",
                "description": "Configurar nginx para servir el frontend en puerto 80 y api en 8000",
            }
        ]
        result = _fix_sdd_agent_assignments(tasks)
        assert result[0]["agent"] == "devops"

    def test_tsx_extension_in_description_triggers_frontend(self):
        tasks = [
            self._task(
                title="Crear componente de login",
                description="Crear src/components/Login.tsx con validación de RUT en tiempo real",
            )
        ]
        result = _fix_sdd_agent_assignments(tasks)
        assert result[0]["agent"] == "frontend"

    def test_vitest_still_triggers_frontend(self):
        tasks = [
            self._task(
                title="Tests unitarios",
                description="Crear tests con vitest para ContractList y BenefitForm",
            )
        ]
        result = _fix_sdd_agent_assignments(tasks)
        assert result[0]["agent"] == "frontend"

    def test_loginform_still_triggers_frontend(self):
        tasks = [self._task(title="Crear LoginForm con validación RUT")]
        result = _fix_sdd_agent_assignments(tasks)
        assert result[0]["agent"] == "frontend"

    def test_react_keyword_triggers_frontend(self):
        tasks = [
            self._task(
                title="Componente de Dashboard",
                description="Implementar Dashboard usando React con hooks y context API",
            )
        ]
        result = _fix_sdd_agent_assignments(tasks)
        assert result[0]["agent"] == "frontend"

    def test_output_file_tsx_inferred_as_frontend(self):
        tasks = [
            {
                "id": "T-1",
                "agent": "backend",
                "title": "Crear LoginForm",
                "output_file": "src/components/LoginForm.tsx",
            }
        ]
        result = _fix_sdd_agent_assignments(tasks)
        assert result[0]["agent"] == "frontend"

    def test_devops_with_output_file_not_changed_by_keywords(self):
        tasks = [
            {
                "id": "T-1",
                "agent": "devops",
                "title": "docker-compose",
                "description": "Configurar servicios api y frontend en docker-compose",
                "output_file": "docker-compose.yml",
            }
        ]
        result = _fix_sdd_agent_assignments(tasks)
        assert result[0]["agent"] == "devops"

    def test_ci_yml_with_frontend_mention_stays_devops(self):
        tasks = [
            {
                "id": "T-1",
                "agent": "devops",
                "title": "CI pipeline",
                "description": "Pipeline que construye el frontend y el backend",
                "output_file": ".github/workflows/ci.yml",
            }
        ]
        result = _fix_sdd_agent_assignments(tasks)
        assert result[0]["agent"] == "devops"


# ---------------------------------------------------------------------------
# S103-P4 — S101-A propagación: nuevos patrones de import
# ---------------------------------------------------------------------------


class TestS103P4RenamePropagate:
    """Valida que S101-A actualiza todos los patrones de referencia a service.py."""

    def _workspace(self, tmp_path, files: dict):
        for rel, content in files.items():
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)

    def _run_s101a(self, work_dir: str):
        import pathlib

        for svc_file in pathlib.Path(work_dir).rglob("service.py"):
            if any(
                p in {".venv", "__pycache__", "node_modules", ".git"}
                for p in svc_file.parts
            ):
                continue
            new_path = svc_file.parent / "services.py"
            svc_file.rename(new_path)
            module_dir = svc_file.parent.name
            for imp_file in pathlib.Path(work_dir).rglob("*.py"):
                if any(p in {".venv", "__pycache__"} for p in imp_file.parts):
                    continue
                try:
                    content = imp_file.read_text(encoding="utf-8", errors="ignore")
                    updated = (
                        content.replace(
                            f"from src.{module_dir}.service import",
                            f"from src.{module_dir}.services import",
                        )
                        .replace("from .service import", "from .services import")
                        .replace(
                            f"import src.{module_dir}.service",
                            f"import src.{module_dir}.services",
                        )
                        .replace(
                            f"src.{module_dir}.service.", f"src.{module_dir}.services."
                        )
                    )
                    if updated != content:
                        imp_file.write_text(updated, encoding="utf-8")
                except OSError:
                    pass

    def test_from_import_updated(self, tmp_path):
        self._workspace(
            tmp_path,
            {
                "src/contracts/service.py": "def create_contract(): pass\n",
                "src/main.py": "from src.contracts.service import create_contract\n",
            },
        )
        self._run_s101a(str(tmp_path))
        content = (tmp_path / "src" / "main.py").read_text()
        assert "from src.contracts.services import" in content
        assert "from src.contracts.service import" not in content

    def test_relative_import_updated(self, tmp_path):
        self._workspace(
            tmp_path,
            {
                "src/contracts/service.py": "def create_contract(): pass\n",
                "src/contracts/router.py": "from .service import create_contract\n",
            },
        )
        self._run_s101a(str(tmp_path))
        content = (tmp_path / "src" / "contracts" / "router.py").read_text()
        assert "from .services import" in content
        assert "from .service import" not in content

    def test_direct_import_updated(self, tmp_path):
        self._workspace(
            tmp_path,
            {
                "src/contracts/service.py": "def create_contract(): pass\n",
                "tests/test_contracts.py": "import src.contracts.service\n",
            },
        )
        self._run_s101a(str(tmp_path))
        content = (tmp_path / "tests" / "test_contracts.py").read_text()
        assert "import src.contracts.services" in content
        assert "import src.contracts.service\n" not in content

    def test_module_attr_reference_updated(self, tmp_path):
        self._workspace(
            tmp_path,
            {
                "src/contracts/service.py": "def create_contract(): pass\n",
                "src/main.py": "result = src.contracts.service.create_contract()\n",
            },
        )
        self._run_s101a(str(tmp_path))
        content = (tmp_path / "src" / "main.py").read_text()
        assert "src.contracts.services." in content

    def test_service_py_renamed(self, tmp_path):
        self._workspace(
            tmp_path,
            {
                "src/contracts/service.py": "def create_contract(): pass\n",
            },
        )
        self._run_s101a(str(tmp_path))
        assert (tmp_path / "src" / "contracts" / "services.py").exists()
        assert not (tmp_path / "src" / "contracts" / "service.py").exists()


# ---------------------------------------------------------------------------
# S103-P5 — S91-A sin try/except + services plural
# ---------------------------------------------------------------------------


class TestS103P5S91ATemplate:
    """Verifica el template de S91-A inspeccionando el código fuente de graph.py."""

    def _get_s91a_content(self) -> str:
        import pathlib

        graph_py = pathlib.Path(__file__).parent.parent / "graph.py"
        source = graph_py.read_text(encoding="utf-8")
        # Localizar el bloque de string del template S91-A
        marker = "_contracts_router_content = ("
        start = source.find(marker)
        assert start != -1, "Bloque S91-A no encontrado en graph.py"
        # Encontrar el cierre del paréntesis de la tupla de strings
        end = source.find("\n        )\n", start) + len("\n        )\n")
        block = source[start:end]
        local_ns: dict = {}
        exec(f"result = {block}", local_ns)  # noqa: S102
        return local_ns["result"]

    def test_uses_services_plural(self):
        content = self._get_s91a_content()
        assert "from src.contracts.services import" in content
        assert "from src.contracts.service import" not in content

    def test_no_try_except_importerror(self):
        content = self._get_s91a_content()
        assert "try:" not in content
        assert "except ImportError:" not in content

    def test_router_definition_present(self):
        content = self._get_s91a_content()
        assert "router = APIRouter(" in content

    def test_imports_are_top_level(self):
        content = self._get_s91a_content()
        import_lines = [l for l in content.splitlines() if "from src.contracts" in l]
        assert len(import_lines) >= 2
        for line in import_lines:
            assert not line.startswith("    from"), (
                f"Import indentado (bajo try:): {line!r}"
            )
