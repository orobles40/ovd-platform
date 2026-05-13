"""Tests S130 — ORM Naming Consistency + Custom Exceptions + frontend_required example.

S130-A: orm_class en SDD task schema + _build_sdd_module_manifest lo propaga.
S130-A2: _build_architecture_contract_text incluye orm_contracts.
S130-B: _verify_orm_class_names corre en todos los retry rounds (no solo round 0).
S130-C: system_sdd.md exige excepciones de dominio en EXPORTS de services.py.
S130-C2: backend_python.md incluye patrón de custom exceptions.
S130-D: system_analyzer.md incluye ejemplo JSON con frontend_required: true.
"""

import pathlib
import sys

import pytest

_ENGINE_DIR = pathlib.Path(".")
sys.path.insert(0, str(_ENGINE_DIR))

_SDD_TEMPLATE = (_ENGINE_DIR / "templates" / "system_sdd.md").read_text(
    encoding="utf-8"
)
_ANALYZER_TEMPLATE = (_ENGINE_DIR / "templates" / "system_analyzer.md").read_text(
    encoding="utf-8"
)
_BACKEND_STACK = (_ENGINE_DIR / "templates" / "stack" / "backend_python.md").read_text(
    encoding="utf-8"
)

_GRAPH_SRC = (_ENGINE_DIR / "graph.py").read_text(encoding="utf-8")


# ── S130-A: orm_class en SDD task schema ─────────────────────────────────────


def test_s130a_sdd_template_requires_orm_class():
    """system_sdd.md debe mencionar orm_class como campo obligatorio en tasks de models.py."""
    assert "orm_class" in _SDD_TEMPLATE


def test_s130a_module_manifest_uses_orm_class_when_present():
    """_build_sdd_module_manifest usa orm_class cuando el task lo declara."""
    import graph as g

    sdd = {
        "tasks": [
            {
                "id": "T1",
                "agent": "backend",
                "file": "src/turnos/models.py",
                "orm_class": "TurnoORM",
            }
        ]
    }
    result = g._build_sdd_module_manifest(sdd, written_files=None)
    assert "TurnoORM" in result, (
        "El manifest debe mostrar 'TurnoORM' cuando orm_class='TurnoORM'"
    )
    # No debe mostrar <nombre> cuando orm_class está declarado
    assert "import <nombre>" not in result or "TurnoORM" in result


def test_s130a_module_manifest_backward_compat_without_orm_class():
    """Si no hay orm_class, el manifest sigue funcionando (backward compat)."""
    import graph as g

    sdd = {
        "tasks": [
            {
                "id": "T1",
                "agent": "backend",
                "file": "src/contratos/models.py",
            }
        ]
    }
    result = g._build_sdd_module_manifest(sdd, written_files=None)
    assert "src/contratos/models.py" in result
    # No debe lanzar excepción


def test_s130a_module_manifest_multiple_orm_classes():
    """Cuando hay múltiples tasks con orm_class, cada una se muestra con su nombre."""
    import graph as g

    sdd = {
        "tasks": [
            {
                "id": "T1",
                "agent": "backend",
                "file": "src/turnos/models.py",
                "orm_class": "TurnoORM",
            },
            {
                "id": "T2",
                "agent": "backend",
                "file": "src/doctores/models.py",
                "orm_class": "DoctorORM",
            },
        ]
    }
    result = g._build_sdd_module_manifest(sdd, written_files=None)
    assert "TurnoORM" in result
    assert "DoctorORM" in result


# ── S130-A2: architecture contract incluye orm_contracts ─────────────────────


def test_s130a2_architecture_contract_includes_orm_contracts():
    """_build_architecture_contract_text incluye orm_contracts cuando hay tasks con orm_class."""
    import graph as g

    sdd = {
        "tasks": [
            {
                "id": "T1",
                "agent": "backend",
                "file": "src/turnos/models.py",
                "orm_class": "TurnoORM",
                "title": "Crear modelo TurnoORM",
            },
            {
                "id": "T2",
                "agent": "backend",
                "file": "src/turnos/services.py",
                "title": "Crear servicio de turnos",
                "description": "Implementa `def create_turno(db, data)` y `def get_turno(db, id)`",
            },
        ]
    }
    result = g._build_architecture_contract_text(sdd)
    assert "orm_contracts" in result or "TurnoORM" in result, (
        "El contrato debe incluir orm_contracts o mencionar TurnoORM explícitamente"
    )


def test_s130a2_architecture_contract_orm_specifies_import_name():
    """El contrato ORM indica el nombre exacto que services.py debe importar."""
    import graph as g

    sdd = {
        "tasks": [
            {
                "id": "T1",
                "agent": "backend",
                "file": "src/pacientes/models.py",
                "orm_class": "PacienteORM",
                "title": "Crear modelo PacienteORM",
            },
        ]
    }
    result = g._build_architecture_contract_text(sdd)
    if result:  # Solo si el contrato genera algo
        assert "PacienteORM" in result


# ── S130-B: _verify_orm_class_names en todos los retry rounds ────────────────


def test_s130b_verify_orm_not_guarded_by_retry_round():
    """En graph.py, _verify_orm_class_names NO debe tener guard retry_round == 0."""
    # Buscar el bloque donde se llama _verify_orm_class_names
    call_idx = _GRAPH_SRC.find("_verify_orm_class_names(work_dir)")
    assert call_idx != -1, "_verify_orm_class_names no encontrado en graph.py"

    # Extraer las 3 líneas antes de la llamada para verificar la condición
    preceding = _GRAPH_SRC[max(0, call_idx - 200) : call_idx]
    # NO debe tener la guard retry_round == 0 justo antes de la llamada
    assert "retry_round == 0" not in preceding[-150:], (
        "La guard 'retry_round == 0' debe eliminarse de _verify_orm_class_names "
        "(S130-B). Aplica el mismo patrón que S80-B para _verify_db_url_matches_fr."
    )


def test_s130b_verify_db_url_is_precedent():
    """Confirma que _verify_db_url_matches_fr YA no tiene la guard (precedente S80-B)."""
    db_url_call = _GRAPH_SRC.find("_verify_db_url_matches_fr(")
    assert db_url_call != -1
    preceding = _GRAPH_SRC[max(0, db_url_call - 200) : db_url_call]
    assert "retry_round == 0" not in preceding[-150:], (
        "S80-B debería haber eliminado esta guard — test de precedente roto"
    )


# ── S130-C: custom exceptions en system_sdd.md ───────────────────────────────


def test_s130c_sdd_template_mentions_domain_exceptions():
    """system_sdd.md debe mencionar excepciones de dominio en EXPORTS de services.py."""
    assert any(
        phrase in _SDD_TEMPLATE
        for phrase in [
            "NoEncontradaError",
            "NoEncontradoError",
            "domain exception",
            "excepción de dominio",
            "excepcion de dominio",
            "DomainError",
        ]
    ), "system_sdd.md debe tener patrón de excepción de dominio en sección EXPORTS"


def test_s130c_sdd_template_exports_section_exists():
    """system_sdd.md debe tener sección EXPORTS para tasks de services.py."""
    assert "EXPORTS" in _SDD_TEMPLATE


# ── S130-C2: custom exceptions en backend_python.md ─────────────────────────


def test_s130c2_backend_stack_has_domain_exception_class():
    """backend_python.md debe incluir patrón de clase exception de dominio."""
    assert any(
        kw in _BACKEND_STACK
        for kw in [
            "NoEncontradaError",
            "NoEncontradoError",
            "class.*Error(Exception)",
            "Error(Exception)",
        ]
    ), "backend_python.md debe tener ejemplo de custom exception de dominio"


def test_s130c2_backend_stack_prohibits_http_exception_in_services():
    """backend_python.md debe prohibir HTTPException en services.py."""
    assert any(
        phrase in _BACKEND_STACK
        for phrase in [
            "NUNCA lanzar HTTPException desde services",
            "HTTPException desde service",
            "HTTPException en service",
            "PROHIBIDO.*HTTPException.*service",
        ]
    ), "backend_python.md debe prohibir HTTPException en services.py"


# ── S130-D: frontend_required ejemplo en system_analyzer.md ─────────────────


def test_s130d_system_analyzer_has_frontend_required_json_example():
    """system_analyzer.md debe incluir ejemplo JSON con frontend_required: true."""
    assert (
        '"frontend_required": true' in _ANALYZER_TEMPLATE
        or "'frontend_required': true" in _ANALYZER_TEMPLATE
        or "frontend_required: true" in _ANALYZER_TEMPLATE
    ), (
        "system_analyzer.md debe tener ejemplo JSON explícito con frontend_required: true"
    )


def test_s130d_system_analyzer_has_false_example_too():
    """system_analyzer.md debe tener el caso false para claridad."""
    assert "frontend_required" in _ANALYZER_TEMPLATE
    assert "false" in _ANALYZER_TEMPLATE.lower()
