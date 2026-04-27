"""
Tests S66 — S66-A: corrección imports en feedback, S66-B: límite tareas/agente,
            S66-C: detección de import loop idéntico.
"""
import pathlib
import sys
import tempfile

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from graph import _validate_artifacts_imports


# ---------------------------------------------------------------------------
# S66-A: feedback incluye ruta correcta
# ---------------------------------------------------------------------------

def _make_artifact(path: str, content: str, tmpdir: pathlib.Path) -> dict:
    full = tmpdir / path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return {"path": path, "content": content}


def test_s66a_correction_suggests_parent_module():
    """S66-A: cuando src.auth.utils.rut no existe pero src.auth.utils sí,
    el feedback debe sugerir 'from src.auth.utils import ...'."""
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td)
        # Crear utils.py con validate_rut definido
        (p / "src" / "auth").mkdir(parents=True, exist_ok=True)
        (p / "src" / "auth" / "utils.py").write_text(
            "def validate_rut(rut): pass\ndef clean_rut(rut): pass\n",
            encoding="utf-8",
        )
        # Archivo con phantom import
        art = _make_artifact(
            "src/auth/models.py",
            "from src.auth.utils.rut import validate_rut, clean_rut\n",
            p,
        )
        ok, feedback = _validate_artifacts_imports(
            agent_results=[{"artifacts": [art]}],
            directory=td,
            written_files=["src/auth/utils.py", "src/auth/models.py"],
        )
    assert not ok
    assert "módulo no existe" in feedback
    assert "CORRECCIÓN" in feedback
    assert "src.auth.utils" in feedback


def test_s66a_correction_fallback_when_no_match():
    """S66-A: cuando ningún módulo define los nombres importados, trunca el path."""
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td)
        (p / "src").mkdir()
        (p / "src" / "utils.py").write_text("x = 1\n", encoding="utf-8")
        art = _make_artifact(
            "src/main.py",
            "from src.auth.utils.rut import clean_rut\n",
            p,
        )
        ok, feedback = _validate_artifacts_imports(
            agent_results=[{"artifacts": [art]}],
            directory=td,
            written_files=["src/utils.py", "src/main.py"],
        )
    assert not ok
    # Debe tener sección de módulos disponibles
    assert "MÓDULOS DISPONIBLES" in feedback


def test_s66a_available_modules_listed():
    """S66-A: el feedback lista módulos disponibles en disco."""
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td)
        (p / "src").mkdir()
        (p / "src" / "service.py").write_text("def do(): pass\n", encoding="utf-8")
        (p / "src" / "models.py").write_text("class Foo: pass\n", encoding="utf-8")
        art = _make_artifact(
            "src/main.py",
            "from src.phantom.module import Foo\n",
            p,
        )
        ok, feedback = _validate_artifacts_imports(
            agent_results=[{"artifacts": [art]}],
            directory=td,
            written_files=["src/service.py", "src/models.py", "src/main.py"],
        )
    assert not ok
    assert "MÓDULOS DISPONIBLES EN DISCO" in feedback
    # Al menos uno de los módulos reales debe aparecer
    assert "src.service" in feedback or "src.models" in feedback


def test_s66a_clean_imports_no_correction_block():
    """S66-A: cuando no hay imports rotos no hay sección de corrección."""
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td)
        art = _make_artifact("src/main.py", "from fastapi import FastAPI\n", p)
        ok, feedback = _validate_artifacts_imports(
            agent_results=[{"artifacts": [art]}],
            directory=td,
            written_files=["src/main.py"],
        )
    assert ok
    assert feedback == ""


# ---------------------------------------------------------------------------
# S66-B / S67-B: límite dinámico de tareas por agente según complejidad
# ---------------------------------------------------------------------------

def _make_sdd_tasks(agent: str, n: int) -> list[dict]:
    return [{"id": f"T{i}", "agent": agent, "title": f"Tarea {i}", "description": ""} for i in range(1, n + 1)]


def _apply_task_cap(tasks: list[dict], complexity: str) -> tuple[list[dict], list[str]]:
    """Replica la lógica S66-B/S67-B de graph.py::generate_sdd."""
    _TASK_CAPS = {"low": 5, "medium": 8, "high": 10, "critical": 12}
    _MAX = _TASK_CAPS.get(complexity, 8)
    by_agent: dict = {}
    for t in tasks:
        by_agent.setdefault(t["agent"], []).append(t)
    trimmed: list[dict] = []
    trimmed_agents: list[str] = []
    for agent, agent_tasks in by_agent.items():
        if len(agent_tasks) > _MAX:
            trimmed_agents.append(f"{agent}({len(agent_tasks)}→{_MAX})")
            trimmed.extend(agent_tasks[:_MAX])
        else:
            trimmed.extend(agent_tasks)
    return trimmed, trimmed_agents


def test_s66b_tasks_trimmed_low_complexity():
    """S67-B: FR low → cap 5 tareas/agente."""
    tasks = _make_sdd_tasks("backend", 11) + _make_sdd_tasks("devops", 2)
    result, trimmed = _apply_task_cap(tasks, "low")
    backend = [t for t in result if t["agent"] == "backend"]
    assert len(backend) == 5
    assert len(trimmed) == 1
    assert "backend(11→5)" in trimmed[0]


def test_s67b_tasks_trimmed_medium_complexity():
    """S67-B: FR medium → cap 8 tareas/agente."""
    tasks = _make_sdd_tasks("backend", 13) + _make_sdd_tasks("devops", 3)
    result, trimmed = _apply_task_cap(tasks, "medium")
    backend = [t for t in result if t["agent"] == "backend"]
    devops = [t for t in result if t["agent"] == "devops"]
    assert len(backend) == 8
    assert len(devops) == 3
    assert "backend(13→8)" in trimmed[0]


def test_s67b_tasks_trimmed_high_complexity():
    """S67-B: FR high → cap 10 tareas/agente."""
    tasks = _make_sdd_tasks("backend", 15)
    result, trimmed = _apply_task_cap(tasks, "high")
    backend = [t for t in result if t["agent"] == "backend"]
    assert len(backend) == 10
    assert "backend(15→10)" in trimmed[0]


def test_s66b_tasks_under_limit_unchanged():
    """S66-B: SDD con 3 tareas no debe modificarse (bajo cualquier cap)."""
    tasks = _make_sdd_tasks("backend", 3) + _make_sdd_tasks("devops", 2)
    result, trimmed = _apply_task_cap(tasks, "low")
    assert len(trimmed) == 0
    assert len(result) == 5


# ---------------------------------------------------------------------------
# S66-C: detección de import loop idéntico
# ---------------------------------------------------------------------------

def _s66c_is_same_import_loop(import_feedback: str, last_test_error: str, retry_round: int) -> bool:
    """Replica la condición S66-C de graph.py::run_tests."""
    return (
        retry_round >= 1
        and "[S65-A] IMPORTS ROTOS" in last_test_error
        and import_feedback.split("\n")[1:4] == last_test_error.split("\n")[1:4]
    )


def test_s66c_same_feedback_detected_as_loop():
    """S66-C: mismo feedback S65-A en rondas 0 y 1 → loop detectado."""
    feedback = (
        "[S65-A] IMPORTS ROTOS — detectados ANTES de pytest:\n"
        "  src/auth/models.py: from src.auth.utils.rut import validate_rut  ← módulo no existe\n"
        "  → CORRECCIÓN: usa `from src.auth.utils import validate_rut`\n"
    )
    assert _s66c_is_same_import_loop(feedback, feedback, retry_round=1)


def test_s66c_different_feedback_not_detected_as_loop():
    """S66-C: feedback diferente entre rondas → NO es loop."""
    feedback_r0 = (
        "[S65-A] IMPORTS ROTOS — detectados ANTES de pytest:\n"
        "  src/auth/models.py: from src.auth.utils.rut import validate_rut\n"
    )
    feedback_r1 = (
        "[S65-A] IMPORTS ROTOS — detectados ANTES de pytest:\n"
        "  src/contracts/models.py: from src.auth.utils.rut import require_valid_rut\n"
    )
    assert not _s66c_is_same_import_loop(feedback_r1, feedback_r0, retry_round=1)


def test_s66c_round_zero_not_detected():
    """S66-C: ronda 0 nunca es detectada como loop (es la primera vez)."""
    feedback = "[S65-A] IMPORTS ROTOS — detectados ANTES de pytest:\n  src/x.py: from phantom import y\n"
    assert not _s66c_is_same_import_loop(feedback, feedback, retry_round=0)


def test_s66c_non_s65a_error_not_detected():
    """S66-C: si el error anterior no era S65-A, no aplica el shortcut."""
    feedback = "[S65-A] IMPORTS ROTOS — detectados ANTES de pytest:\n  src/x.py: from phantom import y\n"
    prev_error = "ModuleNotFoundError: No module named 'src.auth'\ncollected 0 items\n"
    assert not _s66c_is_same_import_loop(feedback, prev_error, retry_round=1)
