"""
Tests S79 — ORM naming verifier + CRUD template + DB URL verifier + login BD note.

S79-A: _verify_orm_class_names — detecta mismatch entre models.py y service.py — 7 tests
S79-B: template CRUD completo + tabla nombres ORM — 4 tests
S79-C: _verify_db_url_matches_fr — detecta Oracle URL cuando FR pide PostgreSQL — 5 tests
S79-D: template nota login consulta BD — 3 tests
"""

import pathlib

import pytest

_ENGINE_DIR = pathlib.Path(__file__).parent.parent
_TEMPLATES_DIR = _ENGINE_DIR / "templates"
_BACKEND_PY = _TEMPLATES_DIR / "system_backend_python.md"


# ---------------------------------------------------------------------------
# S79-A — _verify_orm_class_names
# ---------------------------------------------------------------------------


class TestS79A:
    def _make_models(self, tmp_path, content: str) -> None:
        (tmp_path / "src" / "contracts").mkdir(parents=True)
        (tmp_path / "src" / "contracts" / "models.py").write_text(
            content, encoding="utf-8"
        )

    def _make_service(self, tmp_path, content: str) -> None:
        (tmp_path / "src" / "contracts" / "service.py").write_text(
            content, encoding="utf-8"
        )

    def test_detecta_contrato_vs_contract(self, tmp_path):
        """S79-A: models.py define ContractORM, service.py importa ContratoORM → error."""
        self._make_models(
            tmp_path,
            (
                "from src.database import Base\n"
                "from sqlalchemy.orm import Mapped, mapped_column\n"
                "class ContractORM(Base):\n"
                "    __tablename__ = 'contracts'\n"
                "    id: Mapped[int] = mapped_column(primary_key=True)\n"
            ),
        )
        self._make_service(
            tmp_path,
            (
                "from src.contracts.models import ContratoORM\n"
                "def get_all(db): return db.query(ContratoORM).all()\n"
            ),
        )
        from graph import _verify_orm_class_names

        ok, feedback = _verify_orm_class_names(str(tmp_path))
        assert not ok
        assert "S79-A" in feedback
        assert "ContratoORM" in feedback
        assert "ContractORM" in feedback

    def test_no_op_con_nombres_consistentes(self, tmp_path):
        """S79-A: models.py y service.py usan ContractORM → ok=True."""
        self._make_models(
            tmp_path,
            (
                "from src.database import Base\n"
                "from sqlalchemy.orm import Mapped, mapped_column\n"
                "class ContractORM(Base):\n"
                "    __tablename__ = 'contracts'\n"
                "    id: Mapped[int] = mapped_column(primary_key=True)\n"
            ),
        )
        self._make_service(
            tmp_path,
            (
                "from src.contracts.models import ContractORM\n"
                "def get_all(db): return db.query(ContractORM).all()\n"
            ),
        )
        from graph import _verify_orm_class_names

        ok, feedback = _verify_orm_class_names(str(tmp_path))
        assert ok
        assert feedback == ""

    def test_no_op_sin_models_py(self, tmp_path):
        """S79-A: sin models.py → ok=True (no hay ORM manifest que verificar)."""
        (tmp_path / "src").mkdir()
        from graph import _verify_orm_class_names

        ok, feedback = _verify_orm_class_names(str(tmp_path))
        assert ok

    def test_hint_candidato_cuando_hay_coincidencia_aproximada(self, tmp_path):
        """S79-A: si hay candidato similar, el feedback incluye '¿quisiste decir:'."""
        self._make_models(
            tmp_path,
            (
                "from src.database import Base\n"
                "from sqlalchemy.orm import Mapped, mapped_column\n"
                "class BenefitORM(Base):\n"
                "    __tablename__ = 'benefits'\n"
                "    id: Mapped[int] = mapped_column(primary_key=True)\n"
            ),
        )
        self._make_service(
            tmp_path,
            (
                "from src.contracts.models import BeneficioORM\n"
                "def get_all(db): return db.query(BeneficioORM).all()\n"
            ),
        )
        from graph import _verify_orm_class_names

        ok, feedback = _verify_orm_class_names(str(tmp_path))
        assert not ok
        assert "quisiste decir" in feedback

    def test_ignora_imports_pydantic_schema(self, tmp_path):
        """S79-A: imports que terminan en Request/Response/Schema no son ORM → se ignoran."""
        self._make_models(
            tmp_path,
            (
                "from src.database import Base\n"
                "from sqlalchemy.orm import Mapped, mapped_column\n"
                "class ContractORM(Base):\n"
                "    __tablename__ = 'contracts'\n"
                "    id: Mapped[int] = mapped_column(primary_key=True)\n"
            ),
        )
        self._make_service(
            tmp_path,
            (
                "from src.contracts.models import ContractORM, ContractCreate, ContractResponse\n"
                "def create(data: ContractCreate, db): pass\n"
            ),
        )
        from graph import _verify_orm_class_names

        ok, feedback = _verify_orm_class_names(str(tmp_path))
        assert ok, f"No debería reportar error para schemas Pydantic: {feedback}"

    def test_detecta_multiples_inconsistencias(self, tmp_path):
        """S79-A: múltiples imports incorrectos → todos aparecen en el feedback."""
        self._make_models(
            tmp_path,
            (
                "from src.database import Base\n"
                "from sqlalchemy.orm import Mapped, mapped_column\n"
                "class ContractORM(Base):\n"
                "    __tablename__ = 'contracts'\n"
                "    id: Mapped[int] = mapped_column(primary_key=True)\n"
                "class BenefitORM(Base):\n"
                "    __tablename__ = 'benefits'\n"
                "    id: Mapped[int] = mapped_column(primary_key=True)\n"
            ),
        )
        self._make_service(
            tmp_path,
            (
                "from src.contracts.models import ContratoORM, BeneficioORM\n"
                "def get(db): return db.query(ContratoORM).all()\n"
            ),
        )
        from graph import _verify_orm_class_names

        ok, feedback = _verify_orm_class_names(str(tmp_path))
        assert not ok
        assert "ContratoORM" in feedback
        assert "BeneficioORM" in feedback

    def test_no_op_con_work_dir_vacio(self):
        """S79-A: work_dir vacío o None → ok=True sin error."""
        from graph import _verify_orm_class_names

        ok, feedback = _verify_orm_class_names("")
        assert ok
        ok2, _ = _verify_orm_class_names("/ruta/que/no/existe/xyz123")
        assert ok2


# ---------------------------------------------------------------------------
# S79-B — Template CRUD completo + tabla de nombres ORM
# ---------------------------------------------------------------------------


class TestS79B:
    def test_template_contiene_create_benefit_implementacion(self):
        """S79-B: template debe incluir implementación completa de create_benefit."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "def create_benefit(" in content
        assert "db.add(" in content
        assert "db.commit()" in content

    def test_template_contiene_list_benefits(self):
        """S79-B: template debe incluir list_benefits completo."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "def list_benefits(" in content
        assert "db.query(" in content

    def test_template_contiene_tabla_nombres_orm(self):
        """S79-B: template debe incluir tabla con ContractORM/BenefitORM/UserORM correctos."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "ContractORM" in content
        assert "BenefitORM" in content
        assert "UserORM" in content

    def test_template_prohibe_nombres_espanol_en_tabla(self):
        """S79-B: la tabla de nombres prohibidos debe incluir ContratoORM y BeneficioORM."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "ContratoORM" in content  # aparece como nombre PROHIBIDO
        assert "BeneficioORM" in content  # aparece como nombre PROHIBIDO


# ---------------------------------------------------------------------------
# S79-C — _verify_db_url_matches_fr
# ---------------------------------------------------------------------------


class TestS79C:
    def _make_database(self, tmp_path, db_url_line: str) -> None:
        (tmp_path / "src").mkdir(exist_ok=True)
        (tmp_path / "src" / "database.py").write_text(
            f"from sqlalchemy import create_engine\n"
            f"DATABASE_URL = '{db_url_line}'\n"
            f"engine = create_engine(DATABASE_URL)\n",
            encoding="utf-8",
        )

    def test_detecta_oracle_cuando_fr_pide_postgres(self, tmp_path):
        """S79-C: FR menciona PostgreSQL pero database.py tiene oracle URL → error."""
        self._make_database(tmp_path, "oracle+oracledb://user:pass@host:1521/XEPDB1")
        from graph import _verify_db_url_matches_fr

        ok, feedback = _verify_db_url_matches_fr(
            str(tmp_path),
            "Sistema de contratos con PostgreSQL + SQLAlchemy ORM",
        )
        assert not ok
        assert "S79-C" in feedback
        assert "Oracle" in feedback or "oracle" in feedback

    def test_no_op_con_postgres_y_fr_postgres(self, tmp_path):
        """S79-C: FR pide PostgreSQL y database.py tiene URL PostgreSQL → ok=True."""
        self._make_database(
            tmp_path, "postgresql+psycopg://user:pass@localhost:5432/db"
        )
        from graph import _verify_db_url_matches_fr

        ok, feedback = _verify_db_url_matches_fr(
            str(tmp_path),
            "Sistema de contratos con PostgreSQL + SQLAlchemy ORM",
        )
        assert ok

    def test_no_op_sin_database_py(self, tmp_path):
        """S79-C: si database.py no existe → ok=True."""
        from graph import _verify_db_url_matches_fr

        ok, _ = _verify_db_url_matches_fr(str(tmp_path), "PostgreSQL ORM")
        assert ok

    def test_no_op_con_fr_sin_bd_explicita(self, tmp_path):
        """S79-C: FR sin mención de BD → no verifica URL → ok=True."""
        self._make_database(tmp_path, "oracle+oracledb://user:pass@host:1521/XEPDB1")
        from graph import _verify_db_url_matches_fr

        ok, _ = _verify_db_url_matches_fr(
            str(tmp_path), "Sistema de gestión de empleados"
        )
        assert ok

    def test_feedback_incluye_hint_postgresql(self, tmp_path):
        """S79-C: cuando FR pide PostgreSQL, el feedback sugiere URL postgresql+psycopg."""
        self._make_database(tmp_path, "oracle+oracledb://user:pass@host:1521/XEPDB1")
        from graph import _verify_db_url_matches_fr

        ok, feedback = _verify_db_url_matches_fr(
            str(tmp_path),
            "Sistema con autenticación JWT usando PostgreSQL + SQLAlchemy",
        )
        assert not ok
        assert "postgresql" in feedback.lower()


# ---------------------------------------------------------------------------
# S79-D — Template nota login BD check
# ---------------------------------------------------------------------------


class TestS79D:
    def test_template_contiene_nota_s79d(self):
        """S79-D: template debe incluir nota S79-D sobre consultar UserORM en BD."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "S79-D" in content

    def test_template_nota_menciona_obligatorio(self):
        """S79-D: la nota debe usar la palabra OBLIGATORIO."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        idx_s79d = content.find("S79-D")
        assert idx_s79d != -1
        nearby = content[idx_s79d : idx_s79d + 300]
        assert "OBLIGATORIO" in nearby

    def test_template_nota_menciona_userorm_o_consulta(self):
        """S79-D: la nota debe mencionar consultar UserORM o db.query."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "UserORM" in content
        # La sección de login debe incluir db.query(UserORM) como ejemplo
        login_section = content[
            content.find("async def login") : content.find("async def login") + 800
        ]
        assert "UserORM" in login_section or "db.query" in login_section
