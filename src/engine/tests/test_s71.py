"""
Tests S71
  S71-A: system_sdd.md contiene regla naming inglés + tabla canónica
         system_backend_python.md contiene tabla canónica + regla "no adaptar nombre"
  S71-D: system_backend_python.md contiene regla @field_validator + @model_validator
  S71-F: system_backend_python.md contiene regla SQLAlchemy + Oracle thick mode
"""
import pathlib
import pytest

_TEMPLATES_DIR = pathlib.Path(__file__).parent.parent / "templates"
_SDD_TEMPLATE = _TEMPLATES_DIR / "system_sdd.md"
_BACKEND_PY = _TEMPLATES_DIR / "system_backend_python.md"


# ---------------------------------------------------------------------------
# S71-A: system_sdd.md — naming en inglés
# ---------------------------------------------------------------------------

class TestS71A_SDD:
    def test_sdd_no_usa_calcular_imc_español(self):
        """S71-A: calcular_imc no debe aparecer como nombre recomendado (solo en lista PROHIBIDO)."""
        content = _SDD_TEMPLATE.read_text(encoding="utf-8")
        for line in content.split("\n"):
            if "calcular_imc" in line:
                assert "PROHIBIDO" in line or "❌" in line, \
                    f"calcular_imc aparece fuera del contexto PROHIBIDO: {line}"

    def test_sdd_usa_calculate_bmi_en_ejemplos(self):
        """S71-A: system_sdd.md usa nombre canónico en inglés 'calculate_bmi'."""
        content = _SDD_TEMPLATE.read_text(encoding="utf-8")
        assert "calculate_bmi" in content

    def test_sdd_contiene_regla_naming_s71a(self):
        """S71-A: system_sdd.md contiene sección de regla de naming S71-A."""
        content = _SDD_TEMPLATE.read_text(encoding="utf-8")
        assert "S71-A" in content
        assert "inglés" in content.lower() or "english" in content.lower()

    def test_sdd_tabla_nombres_canonicos(self):
        """S71-A: system_sdd.md tiene tabla con nombres canónicos en inglés."""
        content = _SDD_TEMPLATE.read_text(encoding="utf-8")
        assert "validate_rut" in content
        assert "is_prime" in content
        assert "calculate_bmi" in content

    def test_sdd_prohibe_nombres_español(self):
        """S71-A: system_sdd.md menciona explícitamente la prohibición de nombres en español."""
        content = _SDD_TEMPLATE.read_text(encoding="utf-8")
        assert "validar_rut" in content  # debe aparecer en la lista de prohibidos
        assert "PROHIBIDO" in content or "prohibido" in content.lower()


# ---------------------------------------------------------------------------
# S71-A: system_backend_python.md — tabla canónica + regla de nombre exacto
# ---------------------------------------------------------------------------

class TestS71A_Backend:
    def test_backend_tabla_canonica_validate_rut(self):
        """S71-A: system_backend_python.md tiene validate_rut en tabla canónica."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "validate_rut(rut: str) -> bool" in content

    def test_backend_tabla_canonica_is_prime(self):
        """S71-A: system_backend_python.md tiene is_prime en tabla canónica."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "is_prime(n: int) -> bool" in content

    def test_backend_regla_nombre_exacto(self):
        """S71-A: system_backend_python.md tiene regla de respetar nombre de task description."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "task description" in content.lower() or "task_description" in content.lower()
        assert "NO adaptes" in content or "no adaptes" in content.lower()

    def test_backend_rut_en_canonical_path(self):
        """S71-A: template usa ruta canónica src/utils/rut_validator.py."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "src/utils/rut_validator.py" in content

    def test_backend_no_usa_path_generico_paquete(self):
        """S71-A: template no usa path genérico src/<paquete>/utils/rut.py."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "src/<paquete>/utils/rut.py" not in content


# ---------------------------------------------------------------------------
# S71-D: Pydantic v2 — @field_validator genérico + @model_validator
# ---------------------------------------------------------------------------

class TestS71D:
    def test_template_field_validator_generico(self):
        """S71-D: system_backend_python.md muestra @field_validator para campo genérico (no solo RUT)."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        # Debe haber un ejemplo de @field_validator fuera de la sección de RUT
        idx_pydantic_v2 = content.find("Pydantic v2")
        assert idx_pydantic_v2 != -1, "Debe tener sección Pydantic v2"
        section = content[idx_pydantic_v2:idx_pydantic_v2 + 2000]
        assert "@field_validator" in section
        assert "@classmethod" in section

    def test_template_prohibe_validator_v1(self):
        """S71-D: template menciona que @validator está PROHIBIDO."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "NUNCA uses" in content or "PROHIBIDO" in content
        assert "@validator" in content  # debe aparecer como el ejemplo malo

    def test_template_model_validator(self):
        """S71-D: template incluye @model_validator(mode='after') para campos calculados."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "@model_validator" in content
        assert "mode='after'" in content

    def test_template_valor_total_ejemplo(self):
        """S71-D: template usa valor_total como ejemplo de campo calculado."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "valor_total" in content
        assert "model_validator" in content

    def test_template_tabla_equivalencias_v1_v2(self):
        """S71-D: template tiene tabla de equivalencias v1 → v2."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "orm_mode" in content  # aparece como ejemplo deprecado
        assert "from_attributes" in content  # reemplazo v2

    def test_template_classmethod_obligatorio(self):
        """S71-D: template menciona @classmethod como obligatorio en v2."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "@classmethod" in content
        assert "OBLIGATORIO" in content or "obligatorio" in content.lower()


# ---------------------------------------------------------------------------
# S71-F: SQLAlchemy ORM + Oracle thick mode
# ---------------------------------------------------------------------------

class TestS71F:
    def test_template_prohibe_oracledb_directo(self):
        """S71-F: template prohíbe oracledb.connect() directo en endpoints."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "PROHIBIDO" in content
        assert "oracledb.connect()" in content

    def test_template_sqlalchemy_get_session(self):
        """S71-F: template muestra patrón get_session() con yield."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "get_session" in content
        assert "yield session" in content

    def test_template_oracle_thick_mode(self):
        """S71-F: template especifica thick mode para Oracle 12c."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "thick_mode" in content or "init_oracle_client" in content

    def test_template_oracle_12c_menciona_version(self):
        """S71-F: template menciona que thin mode no soporta Oracle 12c."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "12c" in content

    def test_template_sqlalchemy_depends(self):
        """S71-F: template muestra Session = Depends(get_session) en endpoint."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        assert "Depends(get_session)" in content

    def test_template_modelos_orm_en_models_py(self):
        """S71-F: template indica que modelos ORM van en models.py, no service.py."""
        content = _BACKEND_PY.read_text(encoding="utf-8")
        # Ya existe en S70-D, verificamos que se mantiene
        assert "models.py" in content
        assert "service.py" in content
