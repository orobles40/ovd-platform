"""
Tests S108 — pytest PASS: fix S79-C falso positivo, Pydantic Date, service.py cleanup,
clasificación errores pytest.

P1 (S108-A): _verify_db_url_matches_fr usa oracle_involved del fr_analysis
P2 (S108-B): _fix_sqlalchemy_date_in_pydantic_schemas
P3 (S108-C): _remove_duplicate_service_files
P4 (S108-D): _classify_pytest_failures + _build_typed_retry_feedback
"""

from __future__ import annotations

import pathlib
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Imports de las funciones a testear
# ---------------------------------------------------------------------------
from code_postprocessor import (
    _fix_sqlalchemy_date_in_pydantic_schemas,
    _remove_duplicate_service_files,
)
from graph import (
    _build_typed_retry_feedback,
    _classify_pytest_failures,
    _verify_db_url_matches_fr,
)

# ---------------------------------------------------------------------------
# TestS79CFix — P1
# ---------------------------------------------------------------------------


class TestS79CFix:
    """S108-A: _verify_db_url_matches_fr usa oracle_involved del fr_analysis."""

    def _make_work_dir(self, db_content: str) -> str:
        tmp = tempfile.mkdtemp()
        src = pathlib.Path(tmp) / "src"
        src.mkdir()
        (src / "database.py").write_text(db_content, encoding="utf-8")
        return tmp

    _POSTGRES_DB = (
        "from sqlalchemy import create_engine\n"
        "DATABASE_URL = 'postgresql+psycopg://u:p@localhost/db'\n"
        "engine = create_engine(DATABASE_URL)\n"
    )
    _ORACLE_DB = (
        "import oracledb\n"
        "DATABASE_URL = 'oracle+oracledb://u:p@localhost:1521/?service_name=XEPDB1'\n"
        "engine = create_engine(DATABASE_URL)\n"
    )

    def test_oracle_involved_false_no_genera_warning_S79C(self):
        """FR dice 'NO Oracle', oracle_involved=False → sin warning S79-C."""
        work_dir = self._make_work_dir(self._POSTGRES_DB)
        fr_text = "Sistema con Docker y PostgreSQL (NO Oracle)"
        ok, feedback = _verify_db_url_matches_fr(
            work_dir, fr_text, oracle_involved=False
        )
        assert ok is True
        assert feedback == ""

    def test_oracle_involved_true_genera_warning_S79C(self):
        """FR real con Oracle, oracle_involved=True pero database.py usa PostgreSQL → warning."""
        work_dir = self._make_work_dir(self._POSTGRES_DB)
        fr_text = "Sistema con Oracle 19c y conexión JDBC"
        ok, feedback = _verify_db_url_matches_fr(
            work_dir, fr_text, oracle_involved=True
        )
        assert ok is False
        assert "S79-C" in feedback

    def test_negacion_en_fr_text_no_activa_oracle(self):
        """oracle_involved=False prevalece sobre cualquier keyword en el texto del FR."""
        work_dir = self._make_work_dir(self._POSTGRES_DB)
        fr_text = (
            "IMPORTANTE: usar PostgreSQL, NO usar Oracle, excluir Oracle de la stack"
        )
        ok, feedback = _verify_db_url_matches_fr(
            work_dir, fr_text, oracle_involved=False
        )
        assert ok is True, f"Esperaba ok=True pero got: {feedback}"

    def test_sin_oracle_involved_usa_keyword_fallback(self):
        """Sin oracle_involved → fallback a keyword matching (comportamiento original)."""
        work_dir = self._make_work_dir(self._POSTGRES_DB)
        # FR sin oracle_involved — debería hacer keyword matching
        fr_text = "Usar base de datos PostgreSQL"
        ok, feedback = _verify_db_url_matches_fr(
            work_dir, fr_text, oracle_involved=None
        )
        # FR solo menciona PostgreSQL, database.py tiene PostgreSQL → coherente
        assert ok is True


# ---------------------------------------------------------------------------
# TestPydanticDateFix — P2
# ---------------------------------------------------------------------------


class TestPydanticDateFix:
    """S108-B: _fix_sqlalchemy_date_in_pydantic_schemas."""

    def test_date_sqlalchemy_en_schema_reemplazado(self):
        """Date de SQLAlchemy en schema Pydantic puro → import datetime, Date removido del import SA."""
        # Archivo solo con BaseModel (sin Column(Date)) → aplica el fix
        content = (
            "from sqlalchemy import Integer, Date\n"
            "from pydantic import BaseModel\n"
            "\n"
            "class ContratoCreate(BaseModel):\n"
            "    fecha_inicio: Date\n"
            "    nombre: str\n"
        )
        result = _fix_sqlalchemy_date_in_pydantic_schemas(
            content, "src/contracts/schemas.py"
        )
        assert "from datetime import date" in result
        # Date debe haberse removido del import SQLAlchemy
        sa_import_line = [
            l for l in result.splitlines() if "from sqlalchemy import" in l
        ]
        assert not sa_import_line or "Date" not in sa_import_line[0]

    def test_archivo_mixto_orm_pydantic_no_tocado(self):
        """Archivo con ORM (Column(Date)) + BaseModel → no se toca (Date en Column sigue siendo válido)."""
        content = (
            "from sqlalchemy import Column, Integer, Date\n"
            "from pydantic import BaseModel\n"
            "\n"
            "class ContratoORM(Base):\n"
            "    fecha_inicio: date = Column(Date, nullable=False)\n"
            "\n"
            "class ContratoCreate(BaseModel):\n"
            "    fecha_inicio: date\n"
        )
        result = _fix_sqlalchemy_date_in_pydantic_schemas(
            content, "src/contracts/models.py"
        )
        # No debe modificar — Column(Date) protege el import
        assert result == content

    def test_orm_date_no_tocado(self):
        """Archivo ORM puro (sin BaseModel) → Date de SQLAlchemy intacto."""
        content = (
            "from sqlalchemy import Column, Integer, Date\n"
            "from sqlalchemy.orm import DeclarativeBase\n"
            "\n"
            "class Base(DeclarativeBase):\n"
            "    pass\n"
            "\n"
            "class ContratoORM(Base):\n"
            "    __tablename__ = 'contratos'\n"
            "    id = Column(Integer, primary_key=True)\n"
            "    fecha_inicio = Column(Date)\n"
        )
        result = _fix_sqlalchemy_date_in_pydantic_schemas(
            content, "src/contracts/models.py"
        )
        # Sin BaseModel → no debe tocarse
        assert result == content

    def test_import_datetime_no_duplicado(self):
        """Si from datetime import date ya existe, no duplicar el import."""
        content = (
            "from datetime import date\n"
            "from sqlalchemy import Column, Integer, Date\n"
            "from pydantic import BaseModel\n"
            "\n"
            "class Schema(BaseModel):\n"
            "    fecha: Date\n"
        )
        result = _fix_sqlalchemy_date_in_pydantic_schemas(content, "src/schemas.py")
        # No debe aparecer dos veces 'from datetime import date'
        assert result.count("from datetime import date") <= 1

    def test_sin_date_en_imports_no_modifica(self):
        """Schema Pydantic sin Date de SQLAlchemy → no se modifica."""
        content = (
            "from datetime import date\n"
            "from pydantic import BaseModel\n"
            "\n"
            "class Schema(BaseModel):\n"
            "    fecha: date\n"
            "    nombre: str\n"
        )
        result = _fix_sqlalchemy_date_in_pydantic_schemas(content, "src/schemas.py")
        assert result == content

    def test_template_contiene_seccion_separacion(self):
        """system_backend_python.md contiene la sección SEPARACIÓN CRÍTICA."""
        template_path = (
            pathlib.Path(__file__).parent.parent
            / "templates"
            / "system_backend_python.md"
        )
        assert template_path.exists(), "Template no encontrado"
        content = template_path.read_text(encoding="utf-8")
        assert "SEPARACIÓN CRÍTICA" in content, (
            "Sección S108-B no encontrada en template"
        )
        assert "BaseModel" in content
        assert "from datetime import date" in content


# ---------------------------------------------------------------------------
# TestServiceFileCleanup — P3
# ---------------------------------------------------------------------------


class TestServiceFileCleanup:
    """S108-C: _remove_duplicate_service_files."""

    def _setup_dir(self, files: dict[str, str]) -> str:
        tmp = tempfile.mkdtemp()
        base = pathlib.Path(tmp)
        for rel_path, content in files.items():
            full = base / rel_path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content, encoding="utf-8")
        return tmp

    def test_service_identico_eliminado(self):
        """service.py con contenido idéntico a services.py → se elimina."""
        content = "def create_contract(): pass\n"
        work_dir = self._setup_dir(
            {
                "src/contracts/services.py": content,
                "src/contracts/service.py": content,
            }
        )
        fixes = _remove_duplicate_service_files(work_dir)
        assert not (
            pathlib.Path(work_dir) / "src" / "contracts" / "service.py"
        ).exists()
        assert any("eliminado" in f for f in fixes)

    def test_service_stub_eliminado(self):
        """service.py con menos de 50 chars → stub vacío, se elimina."""
        work_dir = self._setup_dir(
            {
                "src/contracts/services.py": "def create_contract(): pass\n",
                "src/contracts/service.py": "pass\n",
            }
        )
        fixes = _remove_duplicate_service_files(work_dir)
        assert not (
            pathlib.Path(work_dir) / "src" / "contracts" / "service.py"
        ).exists()
        assert any("stub" in f for f in fixes)

    def test_services_preservado_siempre(self):
        """services.py nunca se elimina."""
        content = "def create_contract(): pass\n"
        work_dir = self._setup_dir(
            {
                "src/contracts/services.py": content,
                "src/contracts/service.py": content,
            }
        )
        _remove_duplicate_service_files(work_dir)
        assert (pathlib.Path(work_dir) / "src" / "contracts" / "services.py").exists()

    def test_sin_services_no_hace_nada(self):
        """Sin services.py presente → no elimina nada."""
        work_dir = self._setup_dir(
            {
                "src/contracts/service.py": "def create_contract(): pass\n",
            }
        )
        fixes = _remove_duplicate_service_files(work_dir)
        assert fixes == []
        assert (pathlib.Path(work_dir) / "src" / "contracts" / "service.py").exists()


# ---------------------------------------------------------------------------
# TestPytestFailureClassifier — P4
# ---------------------------------------------------------------------------


class TestPytestFailureClassifier:
    """S108-D: _classify_pytest_failures + _build_typed_retry_feedback."""

    def test_clasifica_type_errors(self):
        """TypeError en output → aparece en category type_errors."""
        output = "TypeError: unknown type 'Date' in ContratoCreate"
        classified = _classify_pytest_failures(output)
        assert len(classified["type_errors"]) > 0
        assert any("TypeError" in e for e in classified["type_errors"])

    def test_clasifica_import_errors(self):
        """ImportError en output → aparece en category import_errors."""
        output = "ModuleNotFoundError: No module named 'src.contracts.service'"
        classified = _classify_pytest_failures(output)
        assert len(classified["import_errors"]) > 0
        assert any("ModuleNotFoundError" in e for e in classified["import_errors"])

    def test_clasifica_name_errors(self):
        """AttributeError en output → aparece en category name_errors."""
        output = "AttributeError: module 'src.contracts.services' has no attribute 'delete_contract'"
        classified = _classify_pytest_failures(output)
        assert len(classified["name_errors"]) > 0

    def test_clasifica_assertion_errors(self):
        """AssertionError en output → aparece en category assertion_errors."""
        output = "AssertionError: assert 200 == 404"
        classified = _classify_pytest_failures(output)
        assert len(classified["assertion_errors"]) > 0

    def test_output_limpio_retorna_listas_vacias(self):
        """Output sin errores → todas las listas vacías."""
        output = "5 passed in 0.32s"
        classified = _classify_pytest_failures(output)
        assert all(len(v) == 0 for v in classified.values())

    def test_feedback_type_error_menciona_datetime(self):
        """Feedback para type_error incluye instrucción sobre from datetime import date."""
        classified = {
            "import_errors": [],
            "type_errors": ["TypeError: unknown type 'Date'"],
            "name_errors": [],
            "assertion_errors": [],
            "fixture_errors": [],
        }
        feedback = _build_typed_retry_feedback(classified)
        assert "datetime" in feedback
        assert "date" in feedback

    def test_feedback_import_error_menciona_naming(self):
        """Feedback para import_error menciona naming mismatch."""
        classified = {
            "import_errors": ["ModuleNotFoundError: No module named 'src.x'"],
            "type_errors": [],
            "name_errors": [],
            "assertion_errors": [],
            "fixture_errors": [],
        }
        feedback = _build_typed_retry_feedback(classified)
        assert "naming" in feedback.lower() or "services.py" in feedback

    def test_feedback_vacio_cuando_sin_errores(self):
        """Sin errores clasificados → feedback vacío."""
        classified = {
            "import_errors": [],
            "type_errors": [],
            "name_errors": [],
            "assertion_errors": [],
            "fixture_errors": [],
        }
        feedback = _build_typed_retry_feedback(classified)
        assert feedback == ""
