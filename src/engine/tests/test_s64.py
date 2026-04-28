"""
Tests S64 — manifest de módulos, infraestructura HTTP, tabla RUTs verificada, reglas templates.
"""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from graph import _build_sdd_module_manifest, _build_single_task_sdd_content

# ---------------------------------------------------------------------------
# S64-B: _build_sdd_module_manifest
# ---------------------------------------------------------------------------

_SDD_WITH_TASKS = {
    "summary": "API contratos",
    "tasks": [
        {"agent": "backend", "file": "src/database.py", "description": "get_db"},
        {
            "agent": "backend",
            "file": "src/contracts/service.py",
            "description": "service",
        },
        {"agent": "backend", "file": "src/main.py", "description": "entry point"},
        {
            "agent": "backend",
            "file": "tests/test_contracts.py",
            "description": "tests",
        },  # excluir
    ],
    "requirements": [],
    "constraints": [],
    "design": {},
}


def test_s64b_manifest_includes_sdd_tasks():
    """El manifest incluye los módulos .py de las tareas del SDD (excluyendo tests/)."""
    result = _build_sdd_module_manifest(_SDD_WITH_TASKS, written_files=None)
    assert "src/database.py" in result
    assert "src/contracts/service.py" in result
    assert "src/main.py" in result


def test_s64b_manifest_excludes_test_files():
    """El manifest NO incluye archivos de tests/ — no son importables como módulos."""
    result = _build_sdd_module_manifest(_SDD_WITH_TASKS, written_files=None)
    assert "tests/test_contracts.py" not in result


def test_s64b_manifest_includes_written_files():
    """El manifest incluye archivos ya escritos en disco (tareas anteriores del ciclo)."""
    written = ["src/rut/validator.py", "src/benefits/prime_validator.py"]
    result = _build_sdd_module_manifest(_SDD_WITH_TASKS, written_files=written)
    assert "src/rut/validator.py" in result
    assert "src/benefits/prime_validator.py" in result


def test_s64b_manifest_empty_without_tasks():
    """Sin tareas .py en el SDD y sin written_files, el manifest retorna cadena vacía."""
    sdd_empty = {
        "summary": "test",
        "tasks": [],
        "requirements": [],
        "constraints": [],
        "design": {},
    }
    result = _build_sdd_module_manifest(sdd_empty, written_files=None)
    assert result == ""


def test_s64b_manifest_empty_without_py_tasks():
    """SDD con solo tareas SQL/YAML no genera manifest — sin módulos Python."""
    sdd_sql = {
        "summary": "migrations",
        "tasks": [
            {
                "agent": "database",
                "file": "migrations/001_up.sql",
                "description": "tabla",
            },
        ],
        "requirements": [],
        "constraints": [],
        "design": {},
    }
    result = _build_sdd_module_manifest(sdd_sql, written_files=None)
    assert result == ""


def test_s64b_manifest_contains_prohibition():
    """El manifest contiene instrucción explícita de PROHIBIDO para módulos no listados."""
    result = _build_sdd_module_manifest(_SDD_WITH_TASKS, written_files=None)
    assert "PROHIBIDO" in result
    assert "src.database" in result  # ejemplo específico en la prohibición


def test_s64b_manifest_deduplicates_tasks_and_written():
    """Si un archivo aparece en SDD y en written_files, solo aparece una vez."""
    written = ["src/database.py"]  # también está en SDD
    result = _build_sdd_module_manifest(_SDD_WITH_TASKS, written_files=written)
    assert result.count("src/database.py") == 1


def test_s64b_manifest_injected_at_start_of_task_content():
    """El manifest aparece al INICIO del contenido de la tarea (máxima atención del LLM)."""
    task = {
        "agent": "backend",
        "file": "src/main.py",
        "description": "entry point",
        "id": "TASK-003",
    }
    content = _build_single_task_sdd_content(
        _SDD_WITH_TASKS, "backend", task, 0, 1, written_files=["src/database.py"]
    )
    # El manifest debe estar antes que el Summary
    manifest_pos = content.find("[S64-B")
    summary_pos = content.find("## Summary")
    assert manifest_pos != -1, "El manifest S64-B debe estar presente"
    assert manifest_pos < summary_pos, "El manifest debe aparecer ANTES del Summary"


def test_s64b_no_manifest_when_no_py_tasks():
    """_build_single_task_sdd_content sin módulos Python no agrega ruido innecesario."""
    sdd_no_py = {
        "summary": "migrations only",
        "tasks": [
            {"agent": "database", "file": "migrations/up.sql", "description": "x"}
        ],
        "requirements": [],
        "constraints": [],
        "design": {},
    }
    task = {
        "agent": "database",
        "file": "migrations/up.sql",
        "description": "x",
        "id": "T-1",
    }
    content = _build_single_task_sdd_content(
        sdd_no_py, "database", task, 0, 1, written_files=None
    )
    assert "[S64-B" not in content


# ---------------------------------------------------------------------------
# S64-A: tabla RUTs verificados en template backend_python.md
# ---------------------------------------------------------------------------

_TEMPLATE_PATH = (
    pathlib.Path(__file__).parent.parent / "templates" / "stack" / "backend_python.md"
)


def test_s64a_template_has_rut_table():
    """backend_python.md contiene la tabla de RUTs con al menos 7 entradas verificadas."""
    content = _TEMPLATE_PATH.read_text(encoding="utf-8")
    # Verificar que los RUTs matemáticamente correctos están presentes
    assert "12.345.678-5" in content
    assert "1.000.005-K" in content
    assert "9.999.999-3" in content
    assert "11.111.111-1" in content
    assert "5.678.901-4" in content


def test_s64a_template_rut_invalid_cases():
    """backend_python.md marca como inválidos los RUTs con DV incorrecto."""
    content = _TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "12.345.678-9" in content  # inválido en la tabla
    assert "9.999.999-K" in content  # inválido (DV real=3)
    assert "1.234.567-0" in content  # inválido (DV real=4)


def test_s64a_template_1234567_4_is_valid():
    """1.234.567-4 debe estar marcado como VÁLIDO (DV=4 es correcto para ese cuerpo)."""
    content = _TEMPLATE_PATH.read_text(encoding="utf-8")
    # Debe existir como válido, con nota explícita
    assert "1.234.567-4" in content
    # No debe estar en la sección de inválidos con texto que lo marque como tal
    lines_with_rut = [l for l in content.splitlines() if "1.234.567-4" in l]
    # Al menos una línea debe indicar que es válido
    valid_lines = [
        l
        for l in lines_with_rut
        if "válido" in l.lower() or "True" in l or "== True" in l
    ]
    assert valid_lines, (
        f"1.234.567-4 no está marcado como válido. Líneas: {lines_with_rut}"
    )


def test_s64a_template_has_prohibition():
    """backend_python.md contiene instrucción PROHIBIDO para inventar RUTs."""
    content = _TEMPLATE_PATH.read_text(encoding="utf-8")
    assert (
        "PROHIBIDO" in content
        or "NUNCA inventes" in content
        or "NUNCA inventar" in content
    )


# ---------------------------------------------------------------------------
# S64-C: system_sdd.md regla infraestructura HTTP
# ---------------------------------------------------------------------------

_SDD_TEMPLATE_PATH = (
    pathlib.Path(__file__).parent.parent / "templates" / "system_sdd.md"
)


def test_s64c_sdd_template_has_infrastructure_rule():
    """system_sdd.md contiene la regla S64-C sobre infraestructura HTTP."""
    content = _SDD_TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "S64-C" in content


def test_s64c_sdd_template_mentions_database_py():
    """system_sdd.md menciona src/database.py como tarea explícita obligatoria."""
    content = _SDD_TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "src/database.py" in content


def test_s64c_sdd_template_mentions_auth_dependencies():
    """system_sdd.md menciona src/auth/dependencies.py como tarea de infraestructura."""
    content = _SDD_TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "src/auth/dependencies.py" in content


def test_s64c_sdd_template_has_order_constraint():
    """system_sdd.md indica que infraestructura va ANTES que service y main."""
    content = _SDD_TEMPLATE_PATH.read_text(encoding="utf-8")
    # La regla debe mencionar orden explícito
    assert (
        "PRIMERO" in content
        or "antes" in content.lower()
        or "infraestructura" in content.lower()
    )


# ---------------------------------------------------------------------------
# S64-D: system_backend.md reglas routing/ORM/datetime
# ---------------------------------------------------------------------------

_BACKEND_TEMPLATE_PATH = (
    pathlib.Path(__file__).parent.parent / "templates" / "system_backend.md"
)


def test_s64d1_routing_rule_present():
    """system_backend.md contiene regla de orden de rutas FastAPI (estáticas antes paramétricas)."""
    content = _BACKEND_TEMPLATE_PATH.read_text(encoding="utf-8")
    assert (
        "S64-D" in content
        or "estática" in content.lower()
        or "estáticas" in content.lower()
    )
    assert "paramétrica" in content.lower() or "paramétric" in content.lower()


def test_s64d1_routing_shows_example():
    """system_backend.md incluye ejemplo ❌/✅ del orden de rutas."""
    content = _BACKEND_TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "/contratos/vencimientos" in content or "/contratos/{" in content


def test_s64d2_orm_pydantic_prohibition():
    """backend_python.md prohíbe session.add() con modelos Pydantic (D2 es Python-specific)."""
    content = _TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "db.add" in content.lower() or "session.add" in content.lower()
    assert "PROHIBIDO" in content


def test_s64d2_3layer_pattern_present():
    """backend_python.md describe el patrón de 3 capas ORM/Pydantic."""
    content = _TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "DeclarativeBase" in content or "from_attributes" in content


def test_s64d3_sysdate_prohibition():
    """backend_python.md prohíbe func.sysdate() y propone alternativa agnóstica (D3 Python-specific)."""
    content = _TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "sysdate" in content
    assert "datetime.now" in content or "current_timestamp" in content
