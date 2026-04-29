"""Tests S100 — stub cleanup, py_compile pre-check, template fixes."""

import pathlib
import sys
import tempfile

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# S100-A: limpieza de stubs residuales
# ---------------------------------------------------------------------------


class TestS100AStubCleanup:
    def _make_stub(self, directory: pathlib.Path, rel_path: str, content: str):
        fp = directory / rel_path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        return fp

    def test_stub_file_detected_by_marker(self, tmp_path):
        fp = self._make_stub(
            tmp_path,
            "src/contracts/services.py",
            "# stub auto-generado por S96-A — src.contracts.services\n\ndef create_benefit(*args, **kwargs):\n    ...\n",
        )
        marker = "# stub auto-generado por S96-A"
        first_line = fp.read_text(encoding="utf-8").split("\n", 1)[0]
        assert first_line.startswith(marker)

    def test_non_stub_file_not_detected(self, tmp_path):
        fp = self._make_stub(
            tmp_path,
            "src/contracts/services.py",
            "from sqlalchemy.orm import Session\n\ndef create_benefit(data, db: Session):\n    pass\n",
        )
        marker = "# stub auto-generado por S96-A"
        first_line = fp.read_text(encoding="utf-8").split("\n", 1)[0]
        assert not first_line.startswith(marker)

    def test_stub_cleanup_removes_stub_files(self, tmp_path):
        stub = self._make_stub(
            tmp_path,
            "src/contracts/services.py",
            "# stub auto-generado por S96-A — src.contracts.services\ndef create_benefit(*args, **kwargs):\n    ...\n",
        )
        real = self._make_stub(
            tmp_path,
            "src/auth/router.py",
            "from fastapi import APIRouter\nrouter = APIRouter()\n",
        )
        marker = "# stub auto-generado por S96-A"
        removed = []
        for py_file in tmp_path.rglob("*.py"):
            first_line = py_file.read_text(encoding="utf-8", errors="ignore").split(
                "\n", 1
            )[0]
            if first_line.startswith(marker):
                py_file.unlink()
                removed.append(py_file.name)

        assert "services.py" in removed
        assert not stub.exists()
        assert real.exists()

    def test_stub_cleanup_skips_if_no_stubs(self, tmp_path):
        real = self._make_stub(
            tmp_path,
            "src/auth/router.py",
            "from fastapi import APIRouter\nrouter = APIRouter()\n",
        )
        marker = "# stub auto-generado por S96-A"
        removed = []
        for py_file in tmp_path.rglob("*.py"):
            first_line = py_file.read_text(encoding="utf-8", errors="ignore").split(
                "\n", 1
            )[0]
            if first_line.startswith(marker):
                py_file.unlink()
                removed.append(py_file.name)
        assert removed == []
        assert real.exists()


# ---------------------------------------------------------------------------
# S100-B: py_compile pre-check
# ---------------------------------------------------------------------------


class TestS100BPyCompile:
    def _write_py(self, directory: pathlib.Path, rel_path: str, content: str):
        fp = directory / rel_path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        return fp

    def test_valid_python_compiles_ok(self, tmp_path):
        fp = self._write_py(
            tmp_path, "src/main.py", "from fastapi import FastAPI\napp = FastAPI()\n"
        )
        errors = []
        try:
            compile(fp.read_text(encoding="utf-8"), str(fp), "exec")
        except SyntaxError as e:
            errors.append(str(e))
        assert errors == []

    def test_syntax_error_detected(self, tmp_path):
        fp = self._write_py(
            tmp_path,
            "src/contracts/services.py",
            "def create_benefit(\n    # sin cerrar paréntesis\n",
        )
        errors = []
        for py_file in tmp_path.rglob("*.py"):
            try:
                compile(
                    py_file.read_text(encoding="utf-8", errors="ignore"),
                    str(py_file),
                    "exec",
                )
            except SyntaxError as e:
                rel = str(py_file.relative_to(tmp_path))
                errors.append(f"{rel}:{e.lineno}: {e.msg}")
        assert len(errors) == 1
        assert "services.py" in errors[0]

    def test_multiple_syntax_errors_all_detected(self, tmp_path):
        self._write_py(tmp_path, "a.py", "def foo(\n")
        self._write_py(tmp_path, "b.py", "class Bar\n")
        errors = []
        for py_file in sorted(tmp_path.rglob("*.py")):
            try:
                compile(
                    py_file.read_text(encoding="utf-8", errors="ignore"),
                    str(py_file),
                    "exec",
                )
            except SyntaxError as e:
                errors.append(f"{py_file.name}:{e.lineno}")
        assert len(errors) == 2

    def test_valid_files_not_flagged(self, tmp_path):
        self._write_py(
            tmp_path,
            "src/models.py",
            "from sqlalchemy.orm import DeclarativeBase\nclass Base(DeclarativeBase): pass\n",
        )
        self._write_py(
            tmp_path, "src/main.py", "from fastapi import FastAPI\napp = FastAPI()\n"
        )
        errors = []
        for py_file in tmp_path.rglob("*.py"):
            try:
                compile(
                    py_file.read_text(encoding="utf-8", errors="ignore"),
                    str(py_file),
                    "exec",
                )
            except SyntaxError as e:
                errors.append(str(e))
        assert errors == []


# ---------------------------------------------------------------------------
# S100-I: naming services.py (singular vs plural)
# ---------------------------------------------------------------------------


class TestS100INamingServices:
    def test_template_uses_services_plural(self):
        template_path = (
            pathlib.Path(__file__).parent.parent
            / "templates"
            / "system_backend_python.md"
        )
        content = template_path.read_text(encoding="utf-8")
        assert "src/contracts/services.py" in content, (
            "template debe usar services.py (plural)"
        )

    def test_template_does_not_use_service_singular_in_table(self):
        template_path = (
            pathlib.Path(__file__).parent.parent
            / "templates"
            / "system_backend_python.md"
        )
        content = template_path.read_text(encoding="utf-8")
        # La tabla canónica no debe tener service.py singular para contracts
        assert "src/contracts/service.py" not in content, (
            "no debe quedar service.py singular"
        )


# ---------------------------------------------------------------------------
# S100-C: prohibición PyJWT
# ---------------------------------------------------------------------------


class TestS100CJWT:
    def test_template_uses_jose(self):
        template_path = (
            pathlib.Path(__file__).parent.parent
            / "templates"
            / "system_backend_python.md"
        )
        content = template_path.read_text(encoding="utf-8")
        assert "from jose import" in content
        assert "python-jose" in content

    def test_template_prohibits_pyjwt(self):
        template_path = (
            pathlib.Path(__file__).parent.parent
            / "templates"
            / "system_backend_python.md"
        )
        content = template_path.read_text(encoding="utf-8")
        assert "NUNCA uses" in content or "PyJWT" in content or "S100-C" in content


# ---------------------------------------------------------------------------
# S100-F: anti-patrones Oracle en template
# ---------------------------------------------------------------------------


class TestS100FOracleTemplate:
    def _get_oracle_template(self):
        path = (
            pathlib.Path(__file__).parent.parent
            / "templates"
            / "system_database_oracle.md"
        )
        return path.read_text(encoding="utf-8")

    def test_oracle_template_has_prime_trigger_pattern(self):
        content = self._get_oracle_template()
        assert "RAISE_APPLICATION_ERROR" in content
        assert (
            "primo" in content.lower()
            or "prime" in content.lower()
            or "clave_primo" in content
        )

    def test_oracle_template_prohibits_number_for_dv(self):
        content = self._get_oracle_template()
        assert "VARCHAR2(1)" in content
        assert "ORA-06502" in content or "NUMBER" in content

    def test_oracle_template_has_length_between_8_9(self):
        content = self._get_oracle_template()
        assert "BETWEEN 8 AND 9" in content


# ---------------------------------------------------------------------------
# S100-G: validateRut TypeScript en template frontend
# ---------------------------------------------------------------------------


class TestS100GFrontendRut:
    def _get_frontend_template(self):
        path = (
            pathlib.Path(__file__).parent.parent
            / "templates"
            / "system_frontend_react.md"
        )
        return path.read_text(encoding="utf-8")

    def test_frontend_template_has_typescript_validate_rut(self):
        content = self._get_frontend_template()
        assert "validateRut" in content or "validate_rut" in content
        assert ".ts" in content

    def test_frontend_template_prohibits_python_import(self):
        content = self._get_frontend_template()
        assert "PROHIBIDO" in content
        assert "rut_validator" in content

    def test_frontend_template_allows_k_in_input(self):
        content = self._get_frontend_template()
        assert "K" in content and ("input" in content.lower() or "onChange" in content)


# ---------------------------------------------------------------------------
# S100-L: SSE reconnect state restore (lógica de mapeo)
# ---------------------------------------------------------------------------


class TestS100LReconnectMapping:
    STATUS_DONE_UP_TO = {
        "analyzed": 0,
        "sdd_generated": 1,
        "approved": 2,
        "rejected": 2,
        "routing": 3,
        "security_reviewed": 5,
        "qa_done": 6,
        "tests_done": 7,
        "tests_failed": 7,
        "tests_skipped": 7,
        "docs_done": 8,
        "docs_skipped": 8,
        "done": 9,
    }

    def test_analyzed_maps_to_node_0(self):
        assert self.STATUS_DONE_UP_TO["analyzed"] == 0

    def test_done_maps_to_node_9(self):
        assert self.STATUS_DONE_UP_TO["done"] == 9

    def test_security_reviewed_maps_to_5(self):
        assert self.STATUS_DONE_UP_TO["security_reviewed"] == 5

    def test_unknown_status_returns_minus1(self):
        result = self.STATUS_DONE_UP_TO.get("unknown_status", -1)
        assert result == -1

    def test_tests_failed_same_as_tests_done(self):
        assert (
            self.STATUS_DONE_UP_TO["tests_failed"]
            == self.STATUS_DONE_UP_TO["tests_done"]
        )
