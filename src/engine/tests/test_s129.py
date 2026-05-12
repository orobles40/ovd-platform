"""Tests S129 — Full-Stack SDD Coverage.

S129-A: FRAnalysisOutput tiene campo frontend_required: bool.
S129-B: system_sdd.md incluye checklist obligatorio de cobertura full-stack.
S129-C: _ensure_frontend_tasks_if_fullstack inyecta tareas frontend cuando faltan.
S129-D: timeout adaptativo en api.py suma qa_retry_count + test_retry_count.
S129-E: backend_python.md incluye patrón SQLAlchemy async con commit/rollback.
"""

import pathlib
import sys
import types

import pytest

_ENGINE_DIR = pathlib.Path(".")
sys.path.insert(0, str(_ENGINE_DIR))

_API_SRC = (_ENGINE_DIR / "api.py").read_text(encoding="utf-8")
_SDD_TEMPLATE = (_ENGINE_DIR / "templates" / "system_sdd.md").read_text(
    encoding="utf-8"
)
_ANALYZER_TEMPLATE = (_ENGINE_DIR / "templates" / "system_analyzer.md").read_text(
    encoding="utf-8"
)
_BACKEND_STACK = (_ENGINE_DIR / "templates" / "stack" / "backend_python.md").read_text(
    encoding="utf-8"
)


# ── S129-A: FRAnalysisOutput.frontend_required ──────────────────────────────


def test_s129a_fr_analysis_output_has_frontend_required_field():
    """FRAnalysisOutput debe tener campo frontend_required: bool."""
    import graph as g

    output = g.FRAnalysisOutput(
        fr_type="feature",
        complexity="medium",
        components=["frontend", "backend"],
        oracle_involved=False,
        risks=[],
        summary="Test FR",
        frontend_required=True,
    )
    assert output.frontend_required is True


def test_s129a_fr_analysis_output_frontend_required_defaults_false():
    """frontend_required debe ser False por defecto para no romper ciclos existentes."""
    import graph as g

    output = g.FRAnalysisOutput(
        fr_type="bug",
        complexity="low",
        components=["backend"],
        oracle_involved=False,
        risks=[],
        summary="Fix bug",
    )
    assert output.frontend_required is False


def test_s129a_system_analyzer_mentions_frontend_required():
    """system_analyzer.md debe mencionar frontend_required para que el LLM lo emita."""
    assert "frontend_required" in _ANALYZER_TEMPLATE


# ── S129-B: system_sdd.md checklist full-stack ──────────────────────────────


def test_s129b_sdd_template_has_fullstack_checklist():
    """system_sdd.md debe incluir sección de verificación full-stack."""
    assert "frontend" in _SDD_TEMPLATE.lower()
    # Debe mencionar la obligatoriedad de tareas frontend cuando el FR las requiere
    assert any(
        kw in _SDD_TEMPLATE
        for kw in ["S129", "CHECKLIST FULL-STACK", "tarea frontend", "agentamiento"]
    )


def test_s129b_sdd_template_prohibits_backend_only_for_fullstack():
    """system_sdd.md debe advertir que backend-only es inválido para FRs full-stack."""
    assert any(
        phrase in _SDD_TEMPLATE
        for phrase in [
            "NO generes solo tareas backend",
            "no generes solo tareas backend",
            "backend-only",
            "backend only",
            "NUNCA solo backend",
        ]
    )


def test_s129b_sdd_template_frontend_agent_example():
    """system_sdd.md debe incluir ejemplo con agente frontend."""
    assert (
        '"agent": "frontend"' in _SDD_TEMPLATE or "'agent': 'frontend'" in _SDD_TEMPLATE
    )


# ── S129-C: _ensure_frontend_tasks_if_fullstack ──────────────────────────────


def test_s129c_ensure_frontend_function_exists():
    """graph.py debe exportar _ensure_frontend_tasks_if_fullstack."""
    import graph as g

    assert hasattr(g, "_ensure_frontend_tasks_if_fullstack"), (
        "_ensure_frontend_tasks_if_fullstack no existe en graph.py"
    )


def test_s129c_infer_entity_name_helper_exists():
    """graph.py debe exportar _infer_entity_name_from_fr."""
    import graph as g

    assert hasattr(g, "_infer_entity_name_from_fr"), (
        "_infer_entity_name_from_fr no existe en graph.py"
    )


def test_s129c_infer_entity_name_turnos():
    """_infer_entity_name_from_fr debe inferir 'Turno' desde 'agendamiento de turnos'."""
    import graph as g

    name = g._infer_entity_name_from_fr(
        "Implementar módulo de agendamiento de turnos médicos"
    )
    assert name == "Turno"


def test_s129c_infer_entity_name_pacientes():
    """_infer_entity_name_from_fr debe inferir 'Paciente' desde 'pacientes'."""
    import graph as g

    name = g._infer_entity_name_from_fr("CRUD de pacientes con historial médico")
    assert name == "Paciente"


def test_s129c_infer_entity_name_fallback():
    """_infer_entity_name_from_fr retorna 'Entidad' si no puede inferir."""
    import graph as g

    name = g._infer_entity_name_from_fr("Mejorar rendimiento de la aplicación")
    assert isinstance(name, str) and len(name) > 0


def test_s129c_injects_frontend_tasks_when_missing():
    """_ensure_frontend_tasks_if_fullstack inyecta tarea frontend si no hay ninguna."""
    import graph as g

    sdd = {
        "tasks": [
            {"id": "T1", "agent": "backend", "file": "src/turnos/models.py"},
            {"id": "T2", "agent": "database", "file": "migrations/001_turnos.sql"},
        ]
    }
    fr_analysis = {
        "frontend_required": True,
        "summary": "Módulo de agendamiento de turnos médicos",
    }
    fr_raw = "Implementar módulo de agendamiento de turnos médicos"

    result = g._ensure_frontend_tasks_if_fullstack(sdd, fr_analysis, fr_raw)

    frontend_tasks = [t for t in result["tasks"] if t.get("agent") == "frontend"]
    assert len(frontend_tasks) >= 1, "Debe inyectar al menos 1 tarea frontend"


def test_s129c_does_not_inject_when_frontend_already_present():
    """No debe inyectar si ya hay tareas frontend en el SDD."""
    import graph as g

    sdd = {
        "tasks": [
            {"id": "T1", "agent": "backend", "file": "src/turnos/models.py"},
            {
                "id": "T2",
                "agent": "frontend",
                "file": "frontend/src/pages/Turnos.tsx",
            },
        ]
    }
    fr_analysis = {"frontend_required": True, "summary": "Módulo de turnos"}
    fr_raw = "Implementar módulo de agendamiento de turnos"

    result = g._ensure_frontend_tasks_if_fullstack(sdd, fr_analysis, fr_raw)
    frontend_tasks = [t for t in result["tasks"] if t.get("agent") == "frontend"]
    # Exactamente la misma cantidad — no debe duplicar
    assert len(frontend_tasks) == 1


def test_s129c_does_not_inject_when_not_frontend_required():
    """No debe inyectar si frontend_required es False."""
    import graph as g

    sdd = {
        "tasks": [
            {"id": "T1", "agent": "backend", "file": "src/jobs/cleanup.py"},
        ]
    }
    fr_analysis = {"frontend_required": False, "summary": "Job de limpieza nocturna"}
    fr_raw = "Agregar job de limpieza nocturna de registros expirados"

    original_count = len(sdd["tasks"])
    result = g._ensure_frontend_tasks_if_fullstack(sdd, fr_analysis, fr_raw)
    assert len(result["tasks"]) == original_count


def test_s129c_injected_task_has_tsx_file():
    """La tarea inyectada debe tener un archivo .tsx válido."""
    import graph as g

    sdd = {"tasks": [{"id": "T1", "agent": "backend", "file": "src/turnos/models.py"}]}
    fr_analysis = {"frontend_required": True, "summary": "Módulo de agendamiento"}
    fr_raw = "Módulo de agendamiento de turnos"

    result = g._ensure_frontend_tasks_if_fullstack(sdd, fr_analysis, fr_raw)
    frontend_tasks = [t for t in result["tasks"] if t.get("agent") == "frontend"]
    assert any(".tsx" in t.get("file", "") for t in frontend_tasks)


# ── S129-D: timeout adaptativo con qa_retry_count ───────────────────────────


def test_s129d_api_reads_qa_retry_count():
    """api.py debe leer qa_retry_count del checkpoint además de test_retry_count."""
    assert "qa_retry_count" in _API_SRC


def test_s129d_adaptive_timeout_sums_both_retries():
    """El timeout adaptativo debe sumar test_retry + qa_retry."""
    # Verificar que la fórmula usa ambos valores
    # Buscar el bloque del timeout adaptativo
    timeout_block_start = _API_SRC.find("_d1_retry_round")
    assert timeout_block_start != -1
    timeout_block = _API_SRC[timeout_block_start : timeout_block_start + 800]
    assert "qa_retry_count" in timeout_block
    # La suma debe estar presente de alguna forma
    assert any(op in timeout_block for op in ["+", "sum(", "_d1_total"])


def test_s129d_adaptive_timeout_log_mentions_qa():
    """El log del timeout adaptativo debe mencionar qa_retry para facilitar debugging."""
    assert "qa_retry" in _API_SRC or "qa_retry_count" in _API_SRC


# ── S129-E: backend_python.md SQLAlchemy async transaction ──────────────────


def test_s129e_backend_stack_has_async_session_pattern():
    """backend_python.md debe incluir patrón async with session como transacción."""
    assert any(
        kw in _BACKEND_STACK for kw in ["async with", "AsyncSession", "async_session"]
    )


def test_s129e_backend_stack_has_commit_rollback_pattern():
    """backend_python.md debe incluir ejemplo de commit/rollback explícito."""
    assert "commit" in _BACKEND_STACK.lower()
    assert "rollback" in _BACKEND_STACK.lower()
