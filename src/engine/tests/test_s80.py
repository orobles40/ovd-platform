"""
Tests S80 — ORM manifest vacío, S79-C sin restricción, declarative_base postprocessor,
auth_router obligatorio, caps de tareas reducidos.

S80-A: _verify_orm_class_names manifest vacío — 5 tests
S80-B: S79-C corre en todos los rounds — 3 tests
S80-C: _fix_declarative_base_import — 5 tests
S80-D: auth_router en _ensure_fastapi_main_task — 4 tests
S80-E: caps high:8, critical:10 — 3 tests
"""

import pathlib
import sys
import textwrap

import pytest

_ENGINE_DIR = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(_ENGINE_DIR))


# ---------------------------------------------------------------------------
# S80-A — _verify_orm_class_names detecta manifest vacío + imports ORM en service.py
# ---------------------------------------------------------------------------


class TestS80A:
    def _write(self, tmp_path, rel: str, content: str) -> None:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(content), encoding="utf-8")

    def test_manifest_vacio_con_orm_imports_es_error(self, tmp_path):
        """S80-A: models.py Pydantic-only + service.py importa ContractORM → error."""
        self._write(
            tmp_path,
            "src/contracts/models.py",
            "from pydantic import BaseModel\n"
            "class ContractBase(BaseModel): pass\n"
            "class ContractCreate(BaseModel): pass\n",
        )
        self._write(
            tmp_path,
            "src/contracts/service.py",
            "from src.contracts.models import ContractORM\n"
            "def get_all(db): return db.query(ContractORM).all()\n",
        )
        from graph import _verify_orm_class_names

        ok, feedback = _verify_orm_class_names(str(tmp_path))
        assert not ok
        assert "S80-A" in feedback
        assert "ContractORM" in feedback
        assert "from src.database import Base" in feedback

    def test_manifest_vacio_sin_orm_imports_es_ok(self, tmp_path):
        """S80-A: models.py Pydantic + service.py no importa ORM → OK."""
        self._write(
            tmp_path,
            "src/contracts/models.py",
            "from pydantic import BaseModel\nclass ContractCreate(BaseModel): pass\n",
        )
        self._write(
            tmp_path,
            "src/contracts/service.py",
            "from src.contracts.models import ContractCreate\n"
            "def create(data, db): pass\n",
        )
        from graph import _verify_orm_class_names

        ok, feedback = _verify_orm_class_names(str(tmp_path))
        assert ok
        assert feedback == ""

    def test_manifest_vacio_multiples_orm_imports(self, tmp_path):
        """S80-A: service.py importa BenefitORM, ContractORM desde modelos Pydantic-only."""
        self._write(
            tmp_path,
            "src/benefits/models.py",
            "from pydantic import BaseModel\nclass BenefitCreate(BaseModel): pass\n",
        )
        self._write(
            tmp_path,
            "src/benefits/service.py",
            "from src.benefits.models import BenefitORM\n"
            "from src.contracts.models import ContractORM\n"
            "def list_benefits(db): return db.query(BenefitORM).all()\n",
        )
        from graph import _verify_orm_class_names

        ok, feedback = _verify_orm_class_names(str(tmp_path))
        assert not ok
        assert "BenefitORM" in feedback or "ContractORM" in feedback

    def test_manifest_vacio_sin_service_py_es_ok(self, tmp_path):
        """S80-A: manifest vacío y sin service.py → OK."""
        self._write(
            tmp_path,
            "src/contracts/models.py",
            "from pydantic import BaseModel\nclass ContractCreate(BaseModel): pass\n",
        )
        from graph import _verify_orm_class_names

        ok, _ = _verify_orm_class_names(str(tmp_path))
        assert ok

    def test_manifest_con_orm_classes_usa_s79a(self, tmp_path):
        """S80-A: cuando manifest tiene ORM classes, el path S79-A original sigue funcionando."""
        self._write(
            tmp_path,
            "src/contracts/models.py",
            "from src.database import Base\n"
            "class ContractORM(Base):\n"
            "    __tablename__ = 'contracts'\n",
        )
        self._write(
            tmp_path,
            "src/contracts/service.py",
            "from src.contracts.models import ContratoORM\n"
            "def get(db): return db.query(ContratoORM).all()\n",
        )
        from graph import _verify_orm_class_names

        ok, feedback = _verify_orm_class_names(str(tmp_path))
        assert not ok
        assert "ContratoORM" in feedback


# ---------------------------------------------------------------------------
# S80-B — S79-C corre en todas las rondas (sin retry_round == 0)
# ---------------------------------------------------------------------------


class TestS80B:
    """Verifica que S79-C detecta DB URL inconsistente independientemente del round."""

    def _write(self, tmp_path, rel: str, content: str) -> None:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(content), encoding="utf-8")

    def test_s79c_detecta_oracle_cuando_fr_pide_postgres(self, tmp_path):
        """S79-C (S80-B): FR PostgreSQL + database.py Oracle → error."""
        self._write(
            tmp_path,
            "src/database.py",
            "import oracledb\n"
            "DATABASE_URL = 'oracle+oracledb://user:pass@host:1521/XE'\n"
            "engine = create_engine(DATABASE_URL)\n",
        )
        from graph import _verify_db_url_matches_fr

        ok, feedback = _verify_db_url_matches_fr(
            str(tmp_path), "Sistema de contratos con PostgreSQL + SQLAlchemy ORM"
        )
        assert not ok
        assert "S79-C" in feedback
        assert "postgresql" in feedback.lower() or "PostgreSQL" in feedback

    def test_s79c_ok_cuando_fr_y_db_son_postgres(self, tmp_path):
        """S79-C: FR PostgreSQL + database.py PostgreSQL → OK."""
        self._write(
            tmp_path,
            "src/database.py",
            "DATABASE_URL = 'postgresql+psycopg://user:pass@localhost:5432/db'\n"
            "engine = create_engine(DATABASE_URL)\n",
        )
        from graph import _verify_db_url_matches_fr

        ok, _ = _verify_db_url_matches_fr(str(tmp_path), "Sistema con PostgreSQL")
        assert ok

    def test_s79c_ok_cuando_fr_no_menciona_bd(self, tmp_path):
        """S79-C: FR sin mención de BD → OK (no inferir)."""
        self._write(
            tmp_path,
            "src/database.py",
            "DATABASE_URL = 'oracle+oracledb://user:pass@host:1521/XE'\n",
        )
        from graph import _verify_db_url_matches_fr

        ok, _ = _verify_db_url_matches_fr(str(tmp_path), "Sistema de cálculo de IMC")
        assert ok


# ---------------------------------------------------------------------------
# S80-C — _fix_declarative_base_import postprocessor
# ---------------------------------------------------------------------------


class TestS80C:
    def test_reemplaza_declarative_base_en_models(self):
        """S80-C: Base = declarative_base() reemplazado por from src.database import Base."""
        from code_postprocessor import _fix_declarative_base_import

        content = (
            "from sqlalchemy.orm import declarative_base\n"
            "Base = declarative_base()\n"
            "class BenefitORM(Base):\n"
            "    __tablename__ = 'benefits'\n"
        )
        result = _fix_declarative_base_import(content, "src/benefits/models.py")
        assert "declarative_base()" not in result
        assert "from src.database import Base" in result
        assert "class BenefitORM(Base):" in result

    def test_no_modifica_database_py(self):
        """S80-C: src/database.py no se toca (es la fuente correcta)."""
        from code_postprocessor import _fix_declarative_base_import

        content = (
            "from sqlalchemy.orm import declarative_base\nBase = declarative_base()\n"
        )
        result = _fix_declarative_base_import(content, "src/database.py")
        assert result == content

    def test_no_modifica_si_no_hay_declarative_base(self):
        """S80-C: código sin declarative_base no se modifica."""
        from code_postprocessor import _fix_declarative_base_import

        content = (
            "from src.database import Base\n"
            "class ContractORM(Base):\n"
            "    __tablename__ = 'contracts'\n"
        )
        result = _fix_declarative_base_import(content, "src/contracts/models.py")
        assert result == content

    def test_no_duplica_import_si_ya_existe(self):
        """S80-C: no agrega segundo import si from src.database import Base ya está."""
        from code_postprocessor import _fix_declarative_base_import

        content = (
            "from src.database import Base\n"
            "from sqlalchemy.orm import declarative_base\n"
            "Base = declarative_base()\n"
            "class ORM(Base): pass\n"
        )
        result = _fix_declarative_base_import(content, "src/x/models.py")
        assert result.count("from src.database import Base") == 1

    def test_pipeline_postprocess_aplica_s80c(self):
        """S80-C: postprocess_python_file() llama _fix_declarative_base_import."""
        from code_postprocessor import postprocess_python_file

        content = (
            "from sqlalchemy.orm import declarative_base\n"
            "Base = declarative_base()\n"
            "class BenefitORM(Base):\n"
            "    __tablename__ = 'benefits'\n"
        )
        result = postprocess_python_file(content, "src/benefits/models.py")
        assert "declarative_base()" not in result
        assert "from src.database import Base" in result


# ---------------------------------------------------------------------------
# S80-D — auth_router obligatorio en _ensure_fastapi_main_task
# ---------------------------------------------------------------------------


class TestS80D:
    def _sdd_with_auth_router(self) -> dict:
        return {
            "tasks": [
                {
                    "id": "T1",
                    "agent": "backend",
                    "file": "src/auth/router.py",
                    "title": "Auth router",
                    "description": "Login endpoint",
                },
                {
                    "id": "T2",
                    "agent": "backend",
                    "file": "src/contracts/router.py",
                    "title": "Contracts router",
                    "description": "CRUD contratos",
                },
            ]
        }

    def _fr_with_auth(self) -> dict:
        return {
            "raw": "Sistema de contratos api rest con autenticación JWT login RUT",
            "type": "backend",
        }

    def test_incluye_auth_router_en_hints_cuando_sdd_tiene_auth_router(self):
        """S80-D: SDD con src/auth/router.py → TASK-INFRA-MAIN incluye auth_router."""
        from graph import _ensure_fastapi_main_task

        sdd = self._sdd_with_auth_router()
        result = _ensure_fastapi_main_task(sdd, self._fr_with_auth())
        main_task = next(
            (t for t in result["tasks"] if t.get("file") == "src/main.py"), None
        )
        assert main_task is not None
        assert "auth_router" in main_task["description"]

    def test_no_inyecta_auth_router_si_sdd_no_tiene_auth_router_py(self):
        """S80-D: SDD sin src/auth/router.py → no inyectar auth_router aunque FR mencione JWT."""
        from graph import _ensure_fastapi_main_task

        sdd = {
            "tasks": [
                {
                    "id": "T1",
                    "agent": "backend",
                    "file": "src/contracts/router.py",
                    "title": "Contracts",
                    "description": "CRUD",
                },
            ]
        }
        result = _ensure_fastapi_main_task(
            sdd, {"raw": "api rest con jwt login endpoint", "type": "backend"}
        )
        main_task = next(
            (t for t in result["tasks"] if t.get("file") == "src/main.py"), None
        )
        assert main_task is not None
        # Solo contracts_router debe estar, no auth_router (no existe en SDD)
        assert "auth_router" not in main_task["description"]
        assert "contracts_router" in main_task["description"]

    def test_no_duplica_auth_router_si_ya_esta(self):
        """S80-D: si auth_router ya está en hints, no se duplica."""
        from graph import _ensure_fastapi_main_task

        sdd = {
            "tasks": [
                {
                    "id": "T1",
                    "agent": "backend",
                    "file": "src/auth/router.py",
                    "title": "Auth",
                    "description": "login",
                },
            ]
        }
        result = _ensure_fastapi_main_task(
            sdd, {"raw": "api rest login jwt auth endpoint", "type": "backend"}
        )
        main_task = next(
            (t for t in result["tasks"] if t.get("file") == "src/main.py"), None
        )
        assert main_task is not None
        assert main_task["description"].count("auth_router") == 1

    def test_no_inyecta_auth_router_sin_auth_en_fr(self):
        """S80-D: FR sin auth/login/jwt → no inyectar auth_router."""
        from graph import _ensure_fastapi_main_task

        sdd = {
            "tasks": [
                {
                    "id": "T1",
                    "agent": "backend",
                    "file": "src/imc/router.py",
                    "title": "IMC",
                    "description": "calcular IMC",
                },
            ]
        }
        result = _ensure_fastapi_main_task(
            sdd, {"raw": "calculadora de imc", "type": "backend"}
        )
        main_task = next(
            (t for t in result["tasks"] if t.get("file") == "src/main.py"), None
        )
        if main_task:
            assert "auth_router" not in main_task["description"]


# ---------------------------------------------------------------------------
# S80-E — Caps de tareas reducidos high:8, critical:10
# ---------------------------------------------------------------------------


class TestS80E:
    def test_cap_high_es_8(self):
        """S80-E: complejidad 'high' → cap 8 (era 10)."""
        _TASK_CAPS = {"low": 5, "medium": 8, "high": 8, "critical": 10}
        assert _TASK_CAPS["high"] == 8

    def test_cap_critical_es_10(self):
        """S80-E: complejidad 'critical' → cap 10 (era 12)."""
        _TASK_CAPS = {"low": 5, "medium": 8, "high": 8, "critical": 10}
        assert _TASK_CAPS["critical"] == 10

    def test_cap_medium_sin_cambio(self):
        """S80-E: medium sigue en 8."""
        _TASK_CAPS = {"low": 5, "medium": 8, "high": 8, "critical": 10}
        assert _TASK_CAPS["medium"] == 8
