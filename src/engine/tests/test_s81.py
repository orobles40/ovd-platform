"""
Tests S81 — ORM en service.py, DB URL independiente del runner, tests protegidos del cap, auth_router exacto.

S81-A: _fix_orm_in_service postprocessor — 5 tests
S81-B: _verify_db_url_matches_fr independiente del runner — 3 tests
S81-C: _is_test_task_sdd + tareas de tests protegidas del cap — 4 tests
S81-D: _ensure_fastapi_main_task usa path exacto src/auth/router.py — 3 tests
"""

import pathlib
import sys
import textwrap

import pytest

_ENGINE_DIR = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(_ENGINE_DIR))


# ---------------------------------------------------------------------------
# S81-A — _fix_orm_in_service elimina clases ORM duplicadas en service.py
# ---------------------------------------------------------------------------


class TestS81A:
    def test_elimina_orm_class_en_service(self):
        """S81-A: ContractORM(Base) en service.py debe eliminarse."""
        from code_postprocessor import _fix_orm_in_service

        content = textwrap.dedent("""\
            from src.database import Base
            from sqlalchemy import Column, Integer, String

            class ContractORM(Base):
                __tablename__ = 'contracts'
                id = Column(Integer, primary_key=True)

            def create_contract(data, db):
                obj = ContractORM(**data)
                db.add(obj)
                return obj
        """)
        result = _fix_orm_in_service(content, "src/contracts/service.py")
        assert "class ContractORM(Base)" not in result
        assert "from src.contracts.models import ContractORM" in result

    def test_no_modifica_models_py(self):
        """S81-A: models.py no se toca — los ORM son correctos allí."""
        from code_postprocessor import _fix_orm_in_service

        content = textwrap.dedent("""\
            from src.database import Base
            class ContractORM(Base):
                __tablename__ = 'contracts'
        """)
        result = _fix_orm_in_service(content, "src/contracts/models.py")
        assert result == content

    def test_no_modifica_service_sin_orm(self):
        """S81-A: service.py sin ORM no se toca."""
        from code_postprocessor import _fix_orm_in_service

        content = textwrap.dedent("""\
            from src.contracts.models import ContractORM
            def list_contracts(db): return db.query(ContractORM).all()
        """)
        result = _fix_orm_in_service(content, "src/contracts/service.py")
        assert result == content

    def test_elimina_multiple_orm_en_service(self):
        """S81-A: múltiples ORM en service.py — todas eliminadas."""
        from code_postprocessor import _fix_orm_in_service

        content = textwrap.dedent("""\
            from src.database import Base
            class ContractORM(Base):
                __tablename__ = 'contracts'
            class BenefitORM(Base):
                __tablename__ = 'benefits'
            def create_contract(data, db): pass
        """)
        result = _fix_orm_in_service(content, "src/contracts/service.py")
        assert "class ContractORM(Base)" not in result
        assert "class BenefitORM(Base)" not in result
        assert "BenefitORM" in result or "ContractORM" in result  # import agregado

    def test_pipeline_aplica_s81a(self):
        """S81-A: postprocess_python_file() llama _fix_orm_in_service."""
        from code_postprocessor import postprocess_python_file

        content = textwrap.dedent("""\
            from src.database import Base
            class ContractORM(Base):
                __tablename__ = 'contracts'
            def get_all(db): return db.query(ContractORM).all()
        """)
        result = postprocess_python_file(content, "src/contracts/service.py")
        assert "class ContractORM(Base)" not in result


# ---------------------------------------------------------------------------
# S81-B — _verify_db_url_matches_fr independiente del runner
# ---------------------------------------------------------------------------


class TestS81B:
    def _write(self, tmp_path, rel: str, content: str) -> None:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(content), encoding="utf-8")

    def test_s79c_actua_cuando_runner_es_none(self, tmp_path):
        """S81-B: sin test files (runner=None), S79-C debe igualmente detectar Oracle con FR PostgreSQL."""
        self._write(
            tmp_path,
            "src/database.py",
            "DATABASE_URL = 'oracle+oracledb://user:pass@host:1521/XE'\n"
            "engine = create_engine(DATABASE_URL)\n",
        )
        from graph import _verify_db_url_matches_fr

        ok, feedback = _verify_db_url_matches_fr(
            str(tmp_path), "Sistema de contratos con PostgreSQL + SQLAlchemy ORM"
        )
        assert not ok
        assert "S79-C" in feedback

    def test_s79c_ok_con_postgres_y_fr_postgres(self, tmp_path):
        """S81-B: FR PostgreSQL + database.py PostgreSQL → OK."""
        self._write(
            tmp_path,
            "src/database.py",
            "DATABASE_URL = 'postgresql+psycopg://user:pass@localhost:5432/db'\n",
        )
        from graph import _verify_db_url_matches_fr

        ok, _ = _verify_db_url_matches_fr(str(tmp_path), "Sistema con PostgreSQL")
        assert ok

    def test_s79c_ok_sin_database_py(self, tmp_path):
        """S81-B: sin database.py, no hay error falso positivo."""
        from graph import _verify_db_url_matches_fr

        ok, _ = _verify_db_url_matches_fr(str(tmp_path), "Sistema con PostgreSQL")
        assert ok


# ---------------------------------------------------------------------------
# S81-C — _is_test_task_sdd + protección del cap
# ---------------------------------------------------------------------------


class TestS81C:
    def test_identifica_tarea_de_tests_por_file(self):
        """S81-C: tarea con file tests/test_contracts.py → es test task."""
        from graph import _is_test_task_sdd

        task = {
            "file": "tests/test_contracts.py",
            "title": "Tests",
            "description": "pytest",
        }
        assert _is_test_task_sdd(task) is True

    def test_identifica_tarea_de_tests_por_titulo(self):
        """S81-C: tarea con title que contiene 'pytest' → es test task."""
        from graph import _is_test_task_sdd

        task = {
            "file": "src/contracts/service.py",
            "title": "Escribir pytest para contratos",
            "description": "",
        }
        assert _is_test_task_sdd(task) is True

    def test_no_identifica_tarea_business_como_test(self):
        """S81-C: tarea business normal no es test task."""
        from graph import _is_test_task_sdd

        task = {
            "file": "src/contracts/service.py",
            "title": "Crear contrato",
            "description": "CRUD",
        }
        assert _is_test_task_sdd(task) is False

    def test_tarea_test_no_eliminada_del_sdd(self):
        """S81-C: con cap=2 y 3 tareas business + 1 test, la tarea test sobrevive."""
        from graph import _is_infra_task, _is_test_task_sdd

        tasks = [
            {
                "file": "src/contracts/service.py",
                "title": "CRUD contratos",
                "description": "",
            },
            {
                "file": "src/contracts/router.py",
                "title": "Router contratos",
                "description": "",
            },
            {
                "file": "src/benefits/service.py",
                "title": "CRUD beneficios",
                "description": "",
            },
            {
                "file": "tests/test_contracts.py",
                "title": "Tests contratos",
                "description": "pytest",
            },
        ]
        cap = 2
        infra = [t for t in tasks if _is_infra_task(t)]
        tests = [t for t in tasks if _is_test_task_sdd(t) and not _is_infra_task(t)]
        biz = [t for t in tasks if not _is_infra_task(t) and not _is_test_task_sdd(t)]
        filtered = infra + tests + biz[:cap]
        assert any("test_contracts" in t.get("file", "") for t in filtered)
        assert (
            len(
                [
                    t
                    for t in filtered
                    if not _is_infra_task(t) and not _is_test_task_sdd(t)
                ]
            )
            == cap
        )


# ---------------------------------------------------------------------------
# S81-D — _ensure_fastapi_main_task usa path exacto src/auth/router.py
# ---------------------------------------------------------------------------


class TestS81D:
    def _fr(self) -> dict:
        return {
            "raw": "Sistema de contratos api rest con autenticación JWT login RUT",
            "type": "backend",
        }

    def test_inyecta_auth_router_con_path_exacto(self):
        """S81-D: SDD con task file = 'src/auth/router.py' → inyecta auth_router."""
        from graph import _ensure_fastapi_main_task

        sdd = {
            "tasks": [
                {
                    "id": "T1",
                    "agent": "backend",
                    "file": "src/auth/router.py",
                    "title": "Auth router",
                    "description": "login",
                },
            ]
        }
        result = _ensure_fastapi_main_task(sdd, self._fr())
        main_task = next(
            (t for t in result["tasks"] if t.get("file") == "src/main.py"), None
        )
        assert main_task is not None
        assert "auth_router" in main_task["description"]

    def test_no_inyecta_auth_router_con_auth_service_py(self):
        """S81-D: SDD con src/auth/service.py pero sin src/auth/router.py → NO inyectar auth_router."""
        from graph import _ensure_fastapi_main_task

        sdd = {
            "tasks": [
                {
                    "id": "T1",
                    "agent": "backend",
                    "file": "src/auth/service.py",
                    "title": "Auth service",
                    "description": "lógica auth",
                },
            ]
        }
        result = _ensure_fastapi_main_task(sdd, self._fr())
        main_task = next(
            (t for t in result["tasks"] if t.get("file") == "src/main.py"), None
        )
        if main_task:
            assert "auth_router" not in main_task["description"]

    def test_no_inyecta_auth_router_con_contracts_auth_router(self):
        """S81-D: src/contracts/auth_router.py no activa la inyección (no es src/auth/router.py)."""
        from graph import _ensure_fastapi_main_task

        sdd = {
            "tasks": [
                {
                    "id": "T1",
                    "agent": "backend",
                    "file": "src/contracts/auth_router.py",
                    "title": "Contracts auth router",
                    "description": "",
                },
            ]
        }
        result = _ensure_fastapi_main_task(sdd, self._fr())
        main_task = next(
            (t for t in result["tasks"] if t.get("file") == "src/main.py"), None
        )
        if main_task:
            # No debe inyectar el alias 'as auth_router' — solo contracts_router es válido
            assert "as auth_router" not in main_task["description"]
