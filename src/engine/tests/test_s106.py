"""S106-P1..P6 — Tests para auto-generación schemas Pydantic, filtros RAG Oracle,
devops guard, penalidad naming mismatch y list functions en type contract."""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from graph import (
    _S106_P2_ALIASES,
    _build_type_contract,
    _calc_naming_mismatch_penalty,
    _check_undefined_import_names,
    _fix_sdd_agent_assignments,
    _strip_db_restrictions,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sdd(tasks: list[dict]) -> dict:
    return {"tasks": tasks, "summary": "", "requirements": [], "design": {}}


def _sdd_with_orm(orm_class: str, file: str = "src/contracts/models.py") -> dict:
    return _make_sdd(
        [
            {
                "id": "TASK-001",
                "agent": "backend",
                "output_file": file,
                "description": f"Crear {file} con {orm_class}",
                "title": f"class {orm_class}(Base): ...",
            }
        ]
    )


# ---------------------------------------------------------------------------
# S106-P1-A — Auto-generación de schemas Pydantic desde clase ORM
# ---------------------------------------------------------------------------


class TestS106P1Pydantic:
    def test_orm_class_genera_create_schema(self):
        sdd = _sdd_with_orm("ContratoORM")
        contract = _build_type_contract(sdd)
        assert "ContratoCreate" in contract

    def test_orm_class_genera_update_schema(self):
        sdd = _sdd_with_orm("ContratoORM")
        contract = _build_type_contract(sdd)
        assert "ContratoUpdate" in contract

    def test_orm_class_genera_response_schema(self):
        sdd = _sdd_with_orm("ContratoORM")
        contract = _build_type_contract(sdd)
        assert "ContratoResponse" in contract

    def test_orm_sin_suffix_genera_schemas(self):
        """class Contrato(Base) sin sufijo ORM también genera schemas."""
        sdd = _make_sdd(
            [
                {
                    "id": "TASK-001",
                    "agent": "backend",
                    "output_file": "src/contracts/models.py",
                    "description": "Crear models.py con class Contrato(Base)",
                    "title": "class Contrato(Base): ...",
                }
            ]
        )
        contract = _build_type_contract(sdd)
        assert "ContratoCreate" in contract

    def test_multiples_entidades_generan_schemas_propios(self):
        sdd = _make_sdd(
            [
                {
                    "id": "TASK-001",
                    "agent": "backend",
                    "output_file": "src/contracts/models.py",
                    "description": "class ContratoORM(Base) y class BeneficioORM(Base)",
                    "title": "class ContratoORM / class BeneficioORM",
                }
            ]
        )
        contract = _build_type_contract(sdd)
        assert "ContratoCreate" in contract
        assert "ContratoResponse" in contract
        assert "BeneficioCreate" in contract
        assert "BeneficioResponse" in contract

    def test_schemas_marcados_como_obligatorios(self):
        """Los schemas Pydantic auto-generados deben marcarse con S72-A (obligatorio)."""
        sdd = _sdd_with_orm("ContratoORM")
        contract = _build_type_contract(sdd)
        assert "OBLIGATORIO" in contract

    def test_schemas_solo_en_models_py(self):
        """La auto-generación solo aplica a archivos models.py, no a services.py."""
        sdd = _make_sdd(
            [
                {
                    "id": "TASK-001",
                    "agent": "backend",
                    "output_file": "src/contracts/services.py",
                    "description": "class ContratoService: ...",
                    "title": "ContratoService",
                }
            ]
        )
        contract = _build_type_contract(sdd)
        # services.py no debe generar schemas Pydantic automáticamente
        assert "ContratoCreate" not in contract

    def test_no_genera_schemas_para_clases_minusculas(self):
        """Nombres en minúscula no son clases de dominio — no genera schemas."""
        sdd = _make_sdd(
            [
                {
                    "id": "TASK-001",
                    "agent": "backend",
                    "output_file": "src/contracts/models.py",
                    "description": "helper function contrato_helper",
                    "title": "contrato_helper",
                }
            ]
        )
        contract = _build_type_contract(sdd)
        assert "contrato_helperCreate" not in contract

    def test_schemas_no_duplicados(self):
        """Si ContratoCreate ya existe en la task, no se duplica."""
        sdd = _make_sdd(
            [
                {
                    "id": "TASK-001",
                    "agent": "backend",
                    "output_file": "src/contracts/models.py",
                    "description": "class ContratoORM(Base) y class ContratoCreate(BaseModel)",
                    "title": "modelos ORM y Pydantic",
                }
            ]
        )
        contract = _build_type_contract(sdd)
        assert contract.count("ContratoCreate") == 1

    def test_base_model_en_contrato(self):
        """Los schemas auto-generados deben indicar BaseModel en la firma."""
        sdd = _sdd_with_orm("ContratoORM")
        contract = _build_type_contract(sdd)
        assert "BaseModel" in contract

    def test_sdd_sin_models_no_genera_schemas(self):
        """Si no hay tarea de models.py, no se generan schemas Pydantic."""
        sdd = _make_sdd(
            [
                {
                    "id": "TASK-001",
                    "agent": "backend",
                    "output_file": "src/main.py",
                    "description": "FastAPI app",
                    "title": "main.py",
                }
            ]
        )
        contract = _build_type_contract(sdd)
        # No hay clase ORM → no hay schemas Pydantic auto-generados
        assert "Create(BaseModel)" not in contract


# ---------------------------------------------------------------------------
# S106-P1-B — Template system_sdd.md contiene la regla
# ---------------------------------------------------------------------------


class TestS106P1Template:
    def _template(self) -> str:
        path = pathlib.Path(__file__).parent.parent / "templates" / "system_sdd.md"
        return path.read_text(encoding="utf-8")

    def test_template_contiene_s106p1(self):
        assert "S106-P1" in self._template()

    def test_template_menciona_schemas_pydantic(self):
        content = self._template()
        assert "Pydantic" in content or "BaseModel" in content

    def test_template_menciona_create_update_response(self):
        content = self._template()
        assert "Create" in content
        assert "Update" in content
        assert "Response" in content

    def test_template_explica_consecuencia_error(self):
        """El template debe advertir que la ausencia causa ImportError."""
        assert "ImportError" in self._template()


# ---------------------------------------------------------------------------
# S106-P2-A — Template prohíbe validate_rut_format
# ---------------------------------------------------------------------------


class TestS106P2Template:
    def _template(self) -> str:
        path = pathlib.Path(__file__).parent.parent / "templates" / "system_sdd.md"
        return path.read_text(encoding="utf-8")

    def test_template_contiene_s106p2(self):
        assert "S106-P2" in self._template()

    def test_template_prohibe_validate_rut_format(self):
        assert "validate_rut_format" in self._template()

    def test_template_menciona_nombre_canonico(self):
        assert "validate_rut" in self._template()

    def test_aliases_dict_contiene_validate_rut_format(self):
        assert "validate_rut_format" in _S106_P2_ALIASES

    def test_aliases_apuntan_a_validate_rut(self):
        assert _S106_P2_ALIASES["validate_rut_format"] == "validate_rut"
        assert _S106_P2_ALIASES["rut_is_valid"] == "validate_rut"


# ---------------------------------------------------------------------------
# S106-P2-B — Auto-corrección de aliases en _check_undefined_import_names
# ---------------------------------------------------------------------------


class TestS106P2AutoCorrect:
    def _make_module(self, tmp_path: pathlib.Path, name: str, content: str) -> None:
        parts = name.split(".")
        pkg = tmp_path
        for part in parts[:-1]:
            pkg = pkg / part
            pkg.mkdir(exist_ok=True)
            (pkg / "__init__.py").touch(exist_ok=True)
        (pkg / f"{parts[-1]}.py").write_text(content, encoding="utf-8")

    def test_alias_corregido_no_aparece_en_undefined(self, tmp_path):
        """validate_rut_format → validate_rut cuando validate_rut está definida."""
        self._make_module(
            tmp_path,
            "src.utils.rut_validator",
            "def validate_rut(rut: str) -> bool:\n    return True\n",
        )
        consumer = tmp_path / "src" / "contracts" / "services.py"
        consumer.parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "src" / "__init__.py").touch(exist_ok=True)
        consumer.write_text(
            "from src.utils.rut_validator import validate_rut_format\n"
            "def create_contract(): pass\n",
            encoding="utf-8",
        )
        ok, feedback = _check_undefined_import_names(
            [{"artifacts": [{"path": "src/contracts/services.py"}]}],
            str(tmp_path),
        )
        assert ok, feedback
        assert "validate_rut_format" not in feedback

    def test_alias_corregido_en_disco(self, tmp_path):
        """El archivo queda corregido en disco tras la auto-corrección."""
        self._make_module(
            tmp_path,
            "src.utils.rut_validator",
            "def validate_rut(rut: str) -> bool:\n    return True\n",
        )
        consumer = tmp_path / "src" / "contracts" / "services.py"
        consumer.parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "src" / "__init__.py").touch(exist_ok=True)
        consumer.write_text(
            "from src.utils.rut_validator import validate_rut_format\n",
            encoding="utf-8",
        )
        _check_undefined_import_names(
            [{"artifacts": [{"path": "src/contracts/services.py"}]}],
            str(tmp_path),
        )
        corrected = consumer.read_text(encoding="utf-8")
        assert "validate_rut_format" not in corrected
        assert "import validate_rut" in corrected

    def test_alias_desconocido_sigue_en_undefined(self, tmp_path):
        """Un alias no listado en _S106_P2_ALIASES sigue apareciendo como undefined."""
        self._make_module(
            tmp_path,
            "src.utils.rut_validator",
            "def validate_rut(rut: str) -> bool:\n    return True\n",
        )
        consumer = tmp_path / "src" / "contracts" / "services.py"
        consumer.parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "src" / "__init__.py").touch(exist_ok=True)
        consumer.write_text(
            "from src.utils.rut_validator import unknown_function_xyz\n",
            encoding="utf-8",
        )
        ok, feedback = _check_undefined_import_names(
            [{"artifacts": [{"path": "src/contracts/services.py"}]}],
            str(tmp_path),
        )
        assert not ok
        assert "unknown_function_xyz" in feedback


# ---------------------------------------------------------------------------
# S106-P3 — Filtro RAG Oracle: _ORACLE_INFRA_KEYWORDS
# ---------------------------------------------------------------------------


class TestS106P3OracleFilter:
    def test_xepdb1_filtrado_cuando_no_oracle(self):
        ctx = "DATABASE_URL=oracle+oracledb://user:pass@localhost:1521/XEPDB1\n"
        result = _strip_db_restrictions(ctx, oracle_involved=False)
        assert "XEPDB1" not in result.upper()

    def test_port_1521_filtrado_cuando_no_oracle(self):
        ctx = "  ports:\n    - '1521:1521'\n"
        result = _strip_db_restrictions(ctx, oracle_involved=False)
        assert ":1521" not in result

    def test_oracle_infra_preservada_cuando_oracle_involved(self):
        """Cuando oracle_involved=True, la infra Oracle NO se filtra."""
        ctx = "host.docker.internal:1521/XEPDB1\n"
        result = _strip_db_restrictions(ctx, oracle_involved=True)
        assert "XEPDB1" in result.upper()

    def test_postgresql_no_filtrado(self):
        ctx = "DATABASE_URL=postgresql://user:pass@localhost:5432/db\n"
        result = _strip_db_restrictions(ctx, oracle_involved=False)
        assert "postgresql" in result

    def test_oracle_keyword_filtrado(self):
        ctx = "# Oracle database configuration\nfetch_first 10 rows only\n"
        result = _strip_db_restrictions(ctx, oracle_involved=False)
        assert "Oracle" not in result
        assert "fetch_first" not in result


# ---------------------------------------------------------------------------
# S106-P4 — Devops guard en _fix_sdd_agent_assignments
# ---------------------------------------------------------------------------


class TestS106P4DevopsGuard:
    def test_devops_sin_output_file_no_reasignado(self):
        """Tarea devops sin output_file no debe reasignarse por keywords."""
        tasks = [
            {
                "id": "TASK-011",
                "agent": "devops",
                "output_file": "",
                "title": "Crear docker-compose con servicio frontend y backend",
                "description": "docker-compose con componentes frontend dashboard y backend API",
            }
        ]
        result = _fix_sdd_agent_assignments(tasks)
        assert result[0]["agent"] == "devops"

    def test_backend_sin_output_file_si_reasignado_a_frontend(self):
        """Tarea backend sin output_file con keywords frontend SÍ se reasigna."""
        tasks = [
            {
                "id": "TASK-002",
                "agent": "backend",
                "output_file": "",
                "title": "LoginForm component with React",
                "description": "component LoginForm tailwind",
            }
        ]
        result = _fix_sdd_agent_assignments(tasks)
        assert result[0]["agent"] == "frontend"

    def test_devops_con_output_file_aun_puede_corregirse(self):
        """Tarea devops con output_file incorrecto (ej: .tsx) sí se corrige vía S101-B."""
        tasks = [
            {
                "id": "TASK-003",
                "agent": "devops",
                "output_file": "src/components/Dashboard.tsx",
                "title": "Dashboard component",
                "description": "React component for dashboard",
            }
        ]
        result = _fix_sdd_agent_assignments(tasks)
        # output_file .tsx → frontend por extensión (S101-B)
        assert result[0]["agent"] == "frontend"


# ---------------------------------------------------------------------------
# S106-P5 — Penalidad QA por naming mismatches
# ---------------------------------------------------------------------------


class TestS106P5NamingPenalty:
    def _make_s103p2_error(self, count: int) -> str:
        lines = ["[S103-P2] NOMBRES NO DEFINIDOS EN MÓDULO:"]
        for i in range(count):
            lines.append(
                f"  src/contracts/services.py: from src.utils.rut_validator import func_{i}"
                f"  ← 'func_{i}' no definido en src.utils.rut_validator"
            )
        return "\n".join(lines)

    def test_sin_s103p2_penalty_es_cero(self):
        assert _calc_naming_mismatch_penalty("") == 0
        assert _calc_naming_mismatch_penalty("AssertionError: assert 1 == 2") == 0

    def test_un_mismatch_resta_2_pts(self):
        assert _calc_naming_mismatch_penalty(self._make_s103p2_error(1)) == 2

    def test_cinco_mismatches_restan_10_pts(self):
        assert _calc_naming_mismatch_penalty(self._make_s103p2_error(5)) == 10

    def test_penalty_maxima_30_pts(self):
        assert _calc_naming_mismatch_penalty(self._make_s103p2_error(20)) == 30

    def test_penalty_sin_marker_s103p2_es_cero(self):
        """Sin la etiqueta [S103-P2], no se penaliza aunque haya líneas similares."""
        fake = "  some_file.py: from mod import func  ← 'func' no definido en mod"
        assert _calc_naming_mismatch_penalty(fake) == 0

    def test_calc_naming_mismatch_penalty_es_callable(self):
        assert callable(_calc_naming_mismatch_penalty)


# ---------------------------------------------------------------------------
# S106-P6 — Type contract incluye list_{entity}s(db: Session)
# ---------------------------------------------------------------------------


class TestS106P6ListFunctions:
    def _make_sdd_service(
        self, entity: str, file: str = "src/contracts/service.py"
    ) -> dict:
        return {
            "tasks": [
                {
                    "id": "TASK-001",
                    "agent": "backend",
                    "output_file": file,
                    "description": f"Crear {file} con class {entity}ORM operations",
                    "title": f"class {entity}ORM service",
                }
            ],
            "summary": "",
            "requirements": [],
            "design": {},
        }

    def test_service_task_genera_list_function(self):
        sdd = self._make_sdd_service("Contrato")
        contract = _build_type_contract(sdd)
        assert "list_contratos" in contract

    def test_services_plural_file_genera_list_function(self):
        sdd = self._make_sdd_service("Beneficio", "src/beneficios/services.py")
        contract = _build_type_contract(sdd)
        assert "list_beneficios" in contract

    def test_list_function_incluye_db_session(self):
        sdd = self._make_sdd_service("Contrato")
        contract = _build_type_contract(sdd)
        assert "db: Session" in contract

    def test_list_function_orm_suffix_strippeado(self):
        """ContratoORM → list_contratos (no list_contratoorms)."""
        sdd = self._make_sdd_service("Contrato")
        contract = _build_type_contract(sdd)
        assert "list_contratoorms" not in contract.lower()
        assert "list_contratos" in contract

    def test_list_function_no_duplicada(self):
        """Si list_contratos ya está en el contrato por otra ruta, no se duplica."""
        sdd = {
            "tasks": [
                {
                    "id": "TASK-001",
                    "agent": "backend",
                    "output_file": "src/contracts/service.py",
                    "description": "`def list_contratos(db: Session)` y class ContratoORM ops",
                    "title": "service",
                }
            ],
            "summary": "",
            "requirements": [],
            "design": {},
        }
        contract = _build_type_contract(sdd)
        assert contract.count("list_contratos") == 1

    def test_non_service_file_no_genera_list(self):
        """main.py no genera list functions aunque mencione entidades."""
        sdd = {
            "tasks": [
                {
                    "id": "TASK-001",
                    "agent": "backend",
                    "output_file": "src/main.py",
                    "description": "FastAPI app with ContratoORM",
                    "title": "main",
                }
            ],
            "summary": "",
            "requirements": [],
            "design": {},
        }
        contract = _build_type_contract(sdd)
        # main.py no es service.py — no genera list functions
        assert "list_contratos" not in contract
