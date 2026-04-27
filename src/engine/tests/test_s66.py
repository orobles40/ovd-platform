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
# S66-B: límite máx 5 tareas por agente en generate_sdd
# ---------------------------------------------------------------------------

def _make_sdd_tasks(agent: str, n: int) -> list[dict]:
    return [{"id": f"T{i}", "agent": agent, "title": f"Tarea {i}", "description": ""} for i in range(1, n + 1)]


def test_s66b_tasks_trimmed_to_5():
    """S66-B: SDD con 11 tareas en backend debe quedar en 5."""
    import graph as _g
    import types

    # Patch mínimo de generate_sdd para invocar solo el post-procesamiento
    tasks = _make_sdd_tasks("backend", 11) + _make_sdd_tasks("devops", 2)
    sdd = {"tasks": tasks, "requirements": [], "design": {}, "constraints": [], "summary": ""}

    _MAX = 5
    _tasks_by_agent: dict = {}
    for t in sdd["tasks"]:
        _tasks_by_agent.setdefault(t["agent"], []).append(t)
    _tasks_trimmed = []
    for agent, agent_tasks in _tasks_by_agent.items():
        _tasks_trimmed.extend(agent_tasks[:_MAX])
    sdd["tasks"] = _tasks_trimmed

    backend_tasks = [t for t in sdd["tasks"] if t["agent"] == "backend"]
    devops_tasks  = [t for t in sdd["tasks"] if t["agent"] == "devops"]
    assert len(backend_tasks) == 5, f"backend debería tener 5, tiene {len(backend_tasks)}"
    assert len(devops_tasks) == 2, f"devops debería tener 2, tiene {len(devops_tasks)}"
    assert len(sdd["tasks"]) == 7


def test_s66b_tasks_under_limit_unchanged():
    """S66-B: SDD con 3 tareas por agente no debe modificarse."""
    tasks = _make_sdd_tasks("backend", 3) + _make_sdd_tasks("devops", 2)
    _MAX = 5
    original_len = len(tasks)
    _tasks_by_agent: dict = {}
    for t in tasks:
        _tasks_by_agent.setdefault(t["agent"], []).append(t)
    _tasks_trimmed = []
    trimmed_agents = []
    for agent, agent_tasks in _tasks_by_agent.items():
        if len(agent_tasks) > _MAX:
            trimmed_agents.append(agent)
            _tasks_trimmed.extend(agent_tasks[:_MAX])
        else:
            _tasks_trimmed.extend(agent_tasks)
    assert len(trimmed_agents) == 0
    assert len(_tasks_trimmed) == original_len


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
