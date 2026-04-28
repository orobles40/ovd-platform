"""
Tests S77 — Postprocessors Oracle params + Pydantic decorator order +
             verify main.py routers + retry file extraction.

S77-A: _fix_sqlalchemy_oracle_params — 7 tests
S77-B: _fix_pydantic_decorator_order — 6 tests
S77-C: _verify_main_includes_routers — 3 tests
S77-D: _extract_failing_files (helper) — 4 tests
S77-F: auth _get_user_by_email BD errors — 2 tests
"""
import pathlib
import re
import textwrap

import pytest

from code_postprocessor import (
    _fix_sqlalchemy_oracle_params,
    _fix_pydantic_decorator_order,
    postprocess_python_file,
)


# ---------------------------------------------------------------------------
# S77-A — _fix_sqlalchemy_oracle_params
# ---------------------------------------------------------------------------

class TestS77A:
    def test_removes_thick_true(self):
        code = "engine = create_engine(DATABASE_URL, thick=True, echo=True)"
        result = _fix_sqlalchemy_oracle_params(code)
        assert "thick=True" not in result
        assert "echo=True" in result

    def test_removes_thick_false(self):
        code = "engine = create_engine(DATABASE_URL, thick=False)"
        result = _fix_sqlalchemy_oracle_params(code)
        assert "thick=False" not in result
        assert "create_engine" in result

    def test_removes_mode_thick_string(self):
        code = 'engine = create_engine(DATABASE_URL, mode="thick", echo=False)'
        result = _fix_sqlalchemy_oracle_params(code)
        assert 'mode="thick"' not in result
        assert "echo=False" in result

    def test_fixes_thick_mode_string_to_bool(self):
        code = "engine = create_engine(DATABASE_URL, thick_mode='True')"
        result = _fix_sqlalchemy_oracle_params(code)
        assert "thick_mode='True'" not in result
        assert "thick_mode=True" in result

    def test_preserves_thick_mode_true_valid(self):
        code = "engine = create_engine(DATABASE_URL, thick_mode=True)"
        result = _fix_sqlalchemy_oracle_params(code)
        assert "thick_mode=True" in result
        assert result == code  # no debería cambiar nada

    def test_no_op_outside_create_engine(self):
        code = "# thick=True es un comentario\nengine = create_engine(DATABASE_URL)"
        result = _fix_sqlalchemy_oracle_params(code)
        assert result == code  # thick= en comentario no afecta nada útil, create_engine sin params ok

    def test_no_op_when_no_create_engine(self):
        code = "x = thick=True  # código random"
        result = _fix_sqlalchemy_oracle_params(code)
        assert result == code  # fast path: no create_engine en el código


# ---------------------------------------------------------------------------
# S77-B — _fix_pydantic_decorator_order
# ---------------------------------------------------------------------------

class TestS77B:
    def test_reorders_classmethod_field_validator(self):
        code = textwrap.dedent("""\
            from pydantic import BaseModel, field_validator

            class Contract(BaseModel):
                rut: str

                @classmethod
                @field_validator('rut')
                def validate_rut(cls, v):
                    return v
        """)
        result = _fix_pydantic_decorator_order(code)
        # @field_validator debe aparecer ANTES de @classmethod en la línea
        fv_pos = result.find("@field_validator")
        cm_pos = result.find("@classmethod")
        assert fv_pos < cm_pos, "field_validator debe preceder a classmethod"

    def test_reorders_model_validator(self):
        code = textwrap.dedent("""\
            from pydantic import BaseModel, model_validator

            class MyModel(BaseModel):
                value: int

                @classmethod
                @model_validator(mode='before')
                def check_value(cls, v):
                    return v
        """)
        result = _fix_pydantic_decorator_order(code)
        mv_pos = result.find("@model_validator")
        cm_pos = result.find("@classmethod")
        assert mv_pos < cm_pos, "model_validator debe preceder a classmethod"

    def test_preserves_correct_order(self):
        code = textwrap.dedent("""\
            from pydantic import BaseModel, field_validator

            class Good(BaseModel):
                name: str

                @field_validator('name')
                @classmethod
                def validate_name(cls, v):
                    return v
        """)
        result = _fix_pydantic_decorator_order(code)
        # Orden ya correcto — no debe cambiar nada estructuralmente
        fv_pos = result.find("@field_validator")
        cm_pos = result.find("@classmethod")
        assert fv_pos < cm_pos

    def test_multiple_validators(self):
        code = textwrap.dedent("""\
            from pydantic import BaseModel, field_validator

            class Multi(BaseModel):
                a: str
                b: str

                @classmethod
                @field_validator('a')
                def val_a(cls, v):
                    return v

                @classmethod
                @field_validator('b')
                def val_b(cls, v):
                    return v
        """)
        result = _fix_pydantic_decorator_order(code)
        # Ambos deben estar reordenados
        assert result.count("@field_validator") == 2
        # field_validator debe aparecer antes que classmethod en ambas ocurrencias
        parts = result.split("@classmethod")
        assert all("@field_validator" in p for p in parts[:-1])

    def test_no_pydantic_validator_no_change(self):
        code = textwrap.dedent("""\
            class Simple:
                @classmethod
                def method(cls):
                    pass
        """)
        result = _fix_pydantic_decorator_order(code)
        assert result == code  # fast path: sin field_validator/model_validator

    def test_no_classmethod_no_change(self):
        code = textwrap.dedent("""\
            from pydantic import BaseModel, field_validator

            class Solo(BaseModel):
                x: str

                @field_validator('x')
                def check_x(cls, v):
                    return v
        """)
        result = _fix_pydantic_decorator_order(code)
        # Sin @classmethod no hay nada que reordenar
        assert "@field_validator" in result


# ---------------------------------------------------------------------------
# S77-C — _verify_main_includes_routers
# ---------------------------------------------------------------------------

class TestS77C:
    def test_detects_missing_auth_router(self, tmp_path):
        # Crear estructura: src/auth/router.py + src/main.py sin auth
        (tmp_path / "src" / "auth").mkdir(parents=True)
        (tmp_path / "src" / "auth" / "router.py").write_text("router = None", encoding="utf-8")
        (tmp_path / "src" / "main.py").write_text(
            "from fastapi import FastAPI\napp = FastAPI()\n",
            encoding="utf-8",
        )
        from graph import _verify_main_includes_routers
        missing, _ = _verify_main_includes_routers(str(tmp_path))
        assert "auth" in missing

    def test_no_op_when_all_routers_included(self, tmp_path):
        (tmp_path / "src" / "contracts").mkdir(parents=True)
        (tmp_path / "src" / "contracts" / "router.py").write_text("router = None", encoding="utf-8")
        (tmp_path / "src" / "main.py").write_text(
            "from src.contracts.router import router as contracts_router\n"
            "app.include_router(contracts_router, prefix='/contracts')\n",
            encoding="utf-8",
        )
        from graph import _verify_main_includes_routers
        missing, fix = _verify_main_includes_routers(str(tmp_path))
        assert missing == []
        assert fix is None

    def test_no_op_when_no_router_files(self, tmp_path):
        (tmp_path / "src").mkdir(parents=True)
        (tmp_path / "src" / "main.py").write_text(
            "from fastapi import FastAPI\napp = FastAPI()\n",
            encoding="utf-8",
        )
        from graph import _verify_main_includes_routers
        missing, fix = _verify_main_includes_routers(str(tmp_path))
        assert missing == []
        assert fix is None


# ---------------------------------------------------------------------------
# S77-D — helper extracción de archivos fallidos de pytest output
# ---------------------------------------------------------------------------

def _extract_failing_files_from_pytest(test_output: str) -> list[str]:
    """S77-D helper — mismo pattern que usará update_test_retry."""
    pattern = re.compile(r'(?:src|tests)/[\w/]+\.py(?=:|\s|$)')
    return list(set(pattern.findall(test_output)))


class TestS77D:
    def test_extracts_files_from_pytest_assert_error(self):
        output = "src/auth/router.py:23: AssertionError"
        files = _extract_failing_files_from_pytest(output)
        assert "src/auth/router.py" in files

    def test_extracts_files_from_failed_test(self):
        output = "FAILED tests/test_auth.py::test_login - AssertionError"
        files = _extract_failing_files_from_pytest(output)
        assert "tests/test_auth.py" in files

    def test_extracts_multiple_files(self):
        output = (
            "src/contracts/service.py:45: ImportError\n"
            "FAILED tests/test_contracts.py::test_create - AssertionError\n"
        )
        files = _extract_failing_files_from_pytest(output)
        assert "src/contracts/service.py" in files
        assert "tests/test_contracts.py" in files

    def test_no_op_when_no_files_in_output(self):
        output = "E   AssertionError: assert 1 == 2\nSome other line"
        files = _extract_failing_files_from_pytest(output)
        assert files == []


# ---------------------------------------------------------------------------
# S77-F — auth_router._get_user_by_email BD errors
# ---------------------------------------------------------------------------

class TestS77F:
    @pytest.mark.asyncio
    async def test_login_503_when_db_down(self, monkeypatch):
        """psycopg.OperationalError → HTTPException 503, no 500."""
        import psycopg
        from fastapi import HTTPException

        async def _mock_connect(*a, **kw):
            raise psycopg.OperationalError("Connection refused")

        monkeypatch.setattr(psycopg, "AsyncConnection", type("_M", (), {"connect": staticmethod(_mock_connect)}))

        import importlib, sys
        # Re-importar para que monkeypatch tome efecto
        if "routers.auth_router" in sys.modules:
            del sys.modules["routers.auth_router"]

        try:
            from routers.auth_router import _get_user_by_email
            await _get_user_by_email("test@example.com")
            pytest.fail("Debería haber lanzado HTTPException")
        except HTTPException as exc:
            assert exc.status_code == 503

    @pytest.mark.asyncio
    async def test_login_logs_undefined_column(self, monkeypatch, caplog):
        """psycopg UndefinedColumn → HTTPException 500 con mensaje de config."""
        import psycopg
        from fastapi import HTTPException
        import logging

        class _MockConn:
            async def __aenter__(self): return self
            async def __aexit__(self, *a): pass
            async def execute(self, *a, **kw):
                raise psycopg.errors.UndefinedColumn("column active does not exist")

        async def _mock_connect(*a, **kw):
            return _MockConn()

        monkeypatch.setattr(psycopg, "AsyncConnection", type("_M", (), {"connect": staticmethod(_mock_connect)}))

        import sys
        if "routers.auth_router" in sys.modules:
            del sys.modules["routers.auth_router"]

        with caplog.at_level(logging.ERROR):
            try:
                from routers.auth_router import _get_user_by_email
                await _get_user_by_email("test@example.com")
                pytest.fail("Debería lanzar HTTPException")
            except HTTPException as exc:
                assert exc.status_code == 500
                assert "configuración" in exc.detail.lower() or "config" in exc.detail.lower()
