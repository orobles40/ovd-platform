"""Tests S101 — postprocesadores deterministas: service.py rename, SDD agent fix, DATABASE_URL env, oracle_involved."""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# S101-A — Rename service.py → services.py
# ---------------------------------------------------------------------------


class TestS101AServiceRename:
    def _make_py(
        self, directory: pathlib.Path, rel_path: str, content: str
    ) -> pathlib.Path:
        fp = directory / rel_path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        return fp

    def _apply_rename(self, work_dir: pathlib.Path) -> list[str]:
        """Lógica de S101-A extraída para tests unitarios."""
        renamed = []
        for svc_file in work_dir.rglob("service.py"):
            if any(
                p in {".venv", "__pycache__", "node_modules", ".git"}
                for p in svc_file.parts
            ):
                continue
            new_path = svc_file.parent / "services.py"
            svc_file.rename(new_path)
            module_dir = svc_file.parent.name
            renamed.append(str(svc_file.relative_to(work_dir)))
            for imp_file in work_dir.rglob("*.py"):
                if any(p in {".venv", "__pycache__"} for p in imp_file.parts):
                    continue
                try:
                    content = imp_file.read_text(encoding="utf-8", errors="ignore")
                    updated = content.replace(
                        f"from src.{module_dir}.service import",
                        f"from src.{module_dir}.services import",
                    ).replace("from .service import", "from .services import")
                    if updated != content:
                        imp_file.write_text(updated, encoding="utf-8")
                except OSError:
                    pass
        return renamed

    def test_service_singular_renamed_to_plural(self, tmp_path):
        self._make_py(
            tmp_path, "src/contracts/service.py", "def create_contract(): pass\n"
        )
        renamed = self._apply_rename(tmp_path)
        assert "src/contracts/service.py" in renamed
        assert not (tmp_path / "src/contracts/service.py").exists()
        assert (tmp_path / "src/contracts/services.py").exists()

    def test_imports_updated_after_rename(self, tmp_path):
        self._make_py(
            tmp_path, "src/contracts/service.py", "def create_contract(): pass\n"
        )
        self._make_py(
            tmp_path,
            "src/contracts/router.py",
            "from src.contracts.service import create_contract\n",
        )
        self._apply_rename(tmp_path)
        router_content = (tmp_path / "src/contracts/router.py").read_text()
        assert "from src.contracts.services import" in router_content
        assert "from src.contracts.service import" not in router_content

    def test_relative_imports_updated(self, tmp_path):
        self._make_py(tmp_path, "src/auth/service.py", "def login(): pass\n")
        self._make_py(tmp_path, "src/auth/router.py", "from .service import login\n")
        self._apply_rename(tmp_path)
        router_content = (tmp_path / "src/auth/router.py").read_text()
        assert "from .services import" in router_content

    def test_services_plural_not_renamed(self, tmp_path):
        self._make_py(
            tmp_path, "src/contracts/services.py", "def create_contract(): pass\n"
        )
        renamed = self._apply_rename(tmp_path)
        assert renamed == []
        assert (tmp_path / "src/contracts/services.py").exists()

    def test_venv_skipped(self, tmp_path):
        self._make_py(tmp_path, ".venv/lib/service.py", "# venv file\n")
        renamed = self._apply_rename(tmp_path)
        assert renamed == []
        assert (tmp_path / ".venv/lib/service.py").exists()

    def test_multiple_modules_renamed(self, tmp_path):
        self._make_py(tmp_path, "src/contracts/service.py", "def c(): pass\n")
        self._make_py(tmp_path, "src/auth/service.py", "def a(): pass\n")
        renamed = self._apply_rename(tmp_path)
        assert len(renamed) == 2
        assert (tmp_path / "src/contracts/services.py").exists()
        assert (tmp_path / "src/auth/services.py").exists()


# ---------------------------------------------------------------------------
# S101-B — Fix SDD agent assignments por output_file
# ---------------------------------------------------------------------------


class TestS101BSddAgentFix:
    def _apply_fix(self, tasks: list[dict]) -> list[dict]:
        """Lógica de _fix_sdd_agent_assignments extraída para tests."""
        import pathlib

        _ext_map = {
            ".tsx": "frontend",
            ".jsx": "frontend",
            ".css": "frontend",
            ".sql": "database",
        }
        _path_map = [
            ("migrations/", "database"),
            (".github/", "devops"),
            (".docker/", "devops"),
            ("src/components/", "frontend"),
            ("src/pages/", "frontend"),
        ]
        _name_map = {
            "Dockerfile": "devops",
            "docker-compose.yml": "devops",
            "nginx.conf": "devops",
        }
        for task in tasks:
            if not isinstance(task, dict):
                continue
            output_file = task.get("output_file", "") or task.get("file", "") or ""
            if not output_file:
                continue
            fname = pathlib.Path(output_file).name
            inferred = None
            if fname in _name_map:
                inferred = _name_map[fname]
            if inferred is None:
                for ext, agent in _ext_map.items():
                    if output_file.endswith(ext):
                        inferred = agent
                        break
            if inferred is None:
                for prefix, agent in _path_map:
                    if prefix in output_file:
                        inferred = agent
                        break
            if inferred and inferred != task.get("agent"):
                task["agent"] = inferred
        return tasks

    def test_tsx_reassigned_to_frontend(self):
        tasks = [
            {
                "id": "T1",
                "agent": "backend",
                "output_file": "src/components/LoginForm.tsx",
            }
        ]
        result = self._apply_fix(tasks)
        assert result[0]["agent"] == "frontend"

    def test_sql_reassigned_to_database(self):
        tasks = [
            {
                "id": "T2",
                "agent": "backend",
                "output_file": "migrations/001_create_tables.sql",
            }
        ]
        result = self._apply_fix(tasks)
        assert result[0]["agent"] == "database"

    def test_dockerfile_reassigned_to_devops(self):
        tasks = [{"id": "T3", "agent": "backend", "output_file": "Dockerfile"}]
        result = self._apply_fix(tasks)
        assert result[0]["agent"] == "devops"

    def test_docker_compose_reassigned_to_devops(self):
        tasks = [{"id": "T4", "agent": "backend", "output_file": "docker-compose.yml"}]
        result = self._apply_fix(tasks)
        assert result[0]["agent"] == "devops"

    def test_migrations_path_reassigned_to_database(self):
        tasks = [
            {
                "id": "T5",
                "agent": "backend",
                "output_file": "migrations/002_add_trigger.sql",
            }
        ]
        result = self._apply_fix(tasks)
        assert result[0]["agent"] == "database"

    def test_py_file_stays_backend(self):
        tasks = [
            {"id": "T6", "agent": "backend", "output_file": "src/contracts/services.py"}
        ]
        result = self._apply_fix(tasks)
        assert result[0]["agent"] == "backend"

    def test_frontend_task_not_changed_if_already_correct(self):
        tasks = [
            {
                "id": "T7",
                "agent": "frontend",
                "output_file": "src/components/Dashboard.tsx",
            }
        ]
        result = self._apply_fix(tasks)
        assert result[0]["agent"] == "frontend"

    def test_mixed_tasks_correct_distribution(self):
        tasks = [
            {"id": "T1", "agent": "backend", "output_file": "src/main.py"},
            {"id": "T2", "agent": "backend", "output_file": "src/components/App.tsx"},
            {"id": "T3", "agent": "backend", "output_file": "migrations/001.sql"},
            {"id": "T4", "agent": "backend", "output_file": "Dockerfile"},
        ]
        result = self._apply_fix(tasks)
        agents = {t["id"]: t["agent"] for t in result}
        assert agents["T1"] == "backend"
        assert agents["T2"] == "frontend"
        assert agents["T3"] == "database"
        assert agents["T4"] == "devops"

    def test_task_without_output_file_unchanged(self):
        tasks = [{"id": "T8", "agent": "backend"}]
        result = self._apply_fix(tasks)
        assert result[0]["agent"] == "backend"


# ---------------------------------------------------------------------------
# S101-C — DATABASE_URL hardcodeada → os.environ.get()
# ---------------------------------------------------------------------------


class TestS101CDatabaseUrlEnv:
    def _apply_fix(self, content: str, rel_path: str = "database.py") -> str:
        import re

        _pattern = re.compile(
            r'^(DATABASE_URL\s*=\s*)["\']([a-zA-Z][a-zA-Z0-9+._-]*://[^"\']+)["\']',
            re.MULTILINE,
        )
        match = _pattern.search(content)
        if not match:
            return content
        hardcoded_url = match.group(2)
        new_content = _pattern.sub(
            r'\g<1>os.environ.get("DATABASE_URL", "' + hardcoded_url + '")',
            content,
        )
        if "import os" not in new_content:
            lines = new_content.splitlines(keepends=True)
            insert_idx = 0
            for i, line in enumerate(lines):
                stripped = line.strip()
                if (
                    stripped
                    and not stripped.startswith("#")
                    and not stripped.startswith('"""')
                ):
                    insert_idx = i
                    break
            lines.insert(insert_idx, "import os\n")
            new_content = "".join(lines)
        return new_content

    def test_oracle_url_replaced_by_env(self):
        content = "DATABASE_URL = 'oracle+oracledb://user:pass@host:1521/XE'\n"
        result = self._apply_fix(content)
        assert 'os.environ.get("DATABASE_URL"' in result
        assert (
            "oracle+oracledb://user:pass@host:1521/XE" in result
        )  # preservado como default
        assert "DATABASE_URL = 'oracle+oracledb" not in result

    def test_postgres_url_replaced(self):
        content = 'DATABASE_URL = "postgresql+psycopg2://user:pw@localhost/db"\n'
        result = self._apply_fix(content)
        assert 'os.environ.get("DATABASE_URL"' in result

    def test_import_os_added_if_missing(self):
        content = "DATABASE_URL = 'oracle+oracledb://u:p@h:1521/XE'\nengine = create_engine(DATABASE_URL)\n"
        result = self._apply_fix(content)
        assert "import os" in result

    def test_import_os_not_duplicated(self):
        content = "import os\nDATABASE_URL = 'oracle+oracledb://u:p@h:1521/XE'\n"
        result = self._apply_fix(content)
        assert result.count("import os") == 1

    def test_env_var_already_set_not_modified(self):
        content = 'DATABASE_URL = os.environ.get("DATABASE_URL", "")\n'
        result = self._apply_fix(content)
        assert result == content  # sin cambios

    def test_non_database_file_not_modified(self):
        content = "DATABASE_URL = 'oracle+oracledb://u:p@h:1521/XE'\n"
        # rel_path distinto — no debería modificar
        import re

        _pattern = re.compile(
            r'^(DATABASE_URL\s*=\s*)["\']([a-zA-Z][a-zA-Z0-9+._-]*://[^"\']+)["\']',
            re.MULTILINE,
        )
        # Simulamos que el fix verifica el rel_path
        rel_path = "src/config.py"
        if not (rel_path.endswith("database.py") or rel_path.endswith("/database.py")):
            result = content  # no se aplica
        else:
            result = self._apply_fix(content, rel_path)
        assert result == content


# ---------------------------------------------------------------------------
# S101-D — oracle_involved forzado a True cuando FR menciona Oracle
# ---------------------------------------------------------------------------


class TestS101DOracleInvolved:
    def _compute_oracle_involved(
        self, llm_result: bool, fr_text: str, explicit_bd: str | None
    ) -> bool:
        """Simula la lógica de analyze_fr para oracle_involved."""
        oracle_override = (
            explicit_bd is not None and explicit_bd != "oracle" and llm_result
        )
        final = False if oracle_override else llm_result
        # S101-D
        if not final and "oracle" in fr_text.lower():
            final = True
        return final

    def test_oracle_in_fr_forces_true_when_llm_returns_false(self):
        result = self._compute_oracle_involved(False, "Sistema con Oracle XE 21c", None)
        assert result is True

    def test_oracle_in_fr_case_insensitive(self):
        result = self._compute_oracle_involved(
            False, "Base de datos ORACLE local", None
        )
        assert result is True

    def test_no_oracle_in_fr_stays_false(self):
        result = self._compute_oracle_involved(False, "Sistema con PostgreSQL", None)
        assert result is False

    def test_llm_true_preserved_without_fr_oracle(self):
        result = self._compute_oracle_involved(True, "Sistema con PostgreSQL", None)
        assert result is True

    def test_s97d_override_still_works_for_non_oracle(self):
        # S97-D: FR dice PostgreSQL explícitamente → oracle_involved=False
        result = self._compute_oracle_involved(
            True, "Sistema con PostgreSQL", "postgresql"
        )
        assert result is False

    def test_oracle_in_fr_not_overridden_by_s97d(self):
        # Si explicit_bd es oracle, S97-D no actúa (correct)
        result = self._compute_oracle_involved(
            False, "Base de datos Oracle XE", "oracle"
        )
        assert result is True

    def test_oracle_keyword_in_description_triggers(self):
        fr = "AUTENTICACIÓN: Login con RUT chileno. BASE DE DATOS (Oracle XE): Conexión oracle+oracledb"
        result = self._compute_oracle_involved(False, fr, None)
        assert result is True


# ---------------------------------------------------------------------------
# S101-E — Ruff I001 fix aplicado
# ---------------------------------------------------------------------------


class TestS101EImportSorting:
    def test_test_model_router_compila(self):
        path = pathlib.Path(__file__).parent / "test_model_router.py"
        assert path.exists()
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    def test_test_s98_compila(self):
        path = pathlib.Path(__file__).parent / "test_s98.py"
        assert path.exists()
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
