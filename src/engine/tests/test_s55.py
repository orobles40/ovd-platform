"""
OVD Platform — Tests S55

S55-A: _log_runner_response usa log.warning (no log.info) para diagnóstico visible
S55-B: _write_artifacts guard de no-sobreescritura en rondas de retry
S55-C: _build_single_task_sdd_content inyecta float hint en tarea de tests
S55-D: update_test_retry log.warning para archivos en disco (S54-D elevado)
"""

import os
import pathlib
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import logging
from unittest.mock import MagicMock, patch

import pytest

import graph

# ---------------------------------------------------------------------------
# S55-A: _log_runner_response emite WARNING no INFO
# ---------------------------------------------------------------------------


def test_log_runner_response_uses_warning_for_main_line(tmp_path, caplog):
    """S55-A: el log principal de done_reason/eval_count es WARNING."""
    response = MagicMock()
    response.response_metadata = {
        "done_reason": "stop",
        "eval_count": 100,
        "prompt_eval_count": 200,
    }
    response.content = "```python:src/imc/models.py\nclass X: pass\n```"

    with caplog.at_level(logging.WARNING, logger="ovd-graph"):
        graph._log_runner_response(response, "backend")

    warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any(
        "S54-A runner[backend]" in m and "done_reason=stop" in m for m in warning_msgs
    ), f"No se encontró WARNING con done_reason=stop. Mensajes: {warning_msgs}"


def test_log_runner_response_uses_warning_for_fence_found(tmp_path, caplog):
    """S55-A: el log de fence :path encontrado es WARNING."""
    response = MagicMock()
    response.response_metadata = {
        "done_reason": "stop",
        "eval_count": 50,
        "prompt_eval_count": 30,
    }
    response.content = "```python:src/imc/service.py\ndef calcular(): pass\n```"

    with caplog.at_level(logging.WARNING, logger="ovd-graph"):
        graph._log_runner_response(response, "backend")

    warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("fence :path encontrado" in m for m in warning_msgs), (
        f"No se encontró WARNING de fence. Mensajes: {warning_msgs}"
    )


# ---------------------------------------------------------------------------
# S55-B: _write_artifacts — guard de no-sobreescritura
# ---------------------------------------------------------------------------


def test_write_artifacts_preserves_existing_when_new_content_empty(tmp_path):
    """S55-B: si archivo existe con contenido y nuevo content=vacío, preserva el existente."""
    target = tmp_path / "src" / "imc" / "models.py"
    target.parent.mkdir(parents=True)
    original_content = "class ImcRequest:\n    pass\n"
    target.write_text(original_content)
    original_size = target.stat().st_size

    # Nuevo output sin content en el fence
    output = "```python:src/imc/models.py\n\n```"

    result = graph._write_artifacts(
        output, str(tmp_path), "backend", preserve_nonempty=True
    )

    # Archivo debe preservarse
    assert target.read_text() == original_content, (
        "El archivo existente fue sobreescrito con vacío"
    )
    # Debe retornar el archivo como "escrito" (con tamaño original)
    assert len(result) == 1
    assert result[0]["size"] == original_size


def test_write_artifacts_preserves_existing_when_new_content_truncated(tmp_path):
    """S131-A: nuevo contenido no vacío sobreescribe siempre (protección <50% eliminada).

    S55-B protegía con umbral <50%. S131-A lo eliminó porque bloqueaba fixes válidos
    en retries (root cause del QA 62/100). Solo se preserva si el nuevo contenido es
    vacío o solo whitespace.
    """
    target = tmp_path / "src" / "imc" / "service.py"
    target.parent.mkdir(parents=True)
    original_content = (
        "def calcular_imc(peso, altura):\n    imc = round(peso / altura**2, 2)\n    return imc\n"
        * 10
    )
    target.write_text(original_content)

    # Nuevo output con contenido pequeño pero válido — S131-A lo sobreescribe
    # Usa nombre en inglés para evitar renombrado por postprocessor S72-B
    small_content = "def calculate_bmi(weight, height):\n    return round(weight / height**2, 2)\n"
    output = f"```python:src/imc/service.py\n{small_content}\n```"

    result = graph._write_artifacts(
        output, str(tmp_path), "backend", preserve_nonempty=True
    )

    # S131-A: se sobreescribe (no se preserva el original aunque sea < 50%)
    written = target.read_text()
    assert "calculate_bmi" in written, (
        "S131-A: nuevo contenido no vacío debe sobreescribir incluso si es < 50% del original"
    )


def test_write_artifacts_overwrites_when_new_content_larger(tmp_path):
    """S55-B: si nuevo contenido es >= 50% del original, sobreescribe normalmente."""
    target = tmp_path / "src" / "imc" / "service.py"
    target.parent.mkdir(parents=True)
    original_content = "# viejo\n"
    target.write_text(original_content)

    new_content = "def calculate_bmi(peso, altura):\n    return round(peso / altura**2, 2), 'Normal'\n"
    output = f"```python:src/imc/service.py\n{new_content}\n```"

    result = graph._write_artifacts(
        output, str(tmp_path), "backend", preserve_nonempty=True
    )

    # Debe sobreescribir porque el nuevo es mayor
    written_text = target.read_text()
    assert "calculate_bmi" in written_text
    assert result[0]["size"] > len(original_content.encode())


def test_write_artifacts_without_flag_overwrites_always(tmp_path):
    """S55-B: sin preserve_nonempty, el comportamiento original sobreescribe siempre."""
    target = tmp_path / "src" / "imc" / "models.py"
    target.parent.mkdir(parents=True)
    target.write_text("class ImcRequest:\n    pass\n")

    output = "```python:src/imc/models.py\n\n```"
    graph._write_artifacts(output, str(tmp_path), "backend", preserve_nonempty=False)

    # Sin flag, sobreescribe con vacío/newline (no conserva el original)
    assert target.read_text().strip() == ""


def test_write_artifacts_preserve_logs_warning_on_skip(tmp_path, caplog):
    """S55-B: la preservación emite WARNING con información del archivo."""
    target = tmp_path / "src" / "imc" / "models.py"
    target.parent.mkdir(parents=True)
    target.write_text("class ImcRequest:\n    pass\n")

    output = "```python:src/imc/models.py\n\n```"

    with caplog.at_level(logging.WARNING, logger="ovd-graph"):
        graph._write_artifacts(output, str(tmp_path), "backend", preserve_nonempty=True)

    warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("S55-B" in m and "src/imc/models.py" in m for m in warning_msgs), (
        f"No se encontró WARNING de S55-B. Mensajes: {warning_msgs}"
    )


# ---------------------------------------------------------------------------
# S55-C: float hint en tarea de tests
# ---------------------------------------------------------------------------


def _make_sdd_with_task(task_desc: str, title: str = "Implementar módulo IMC") -> dict:
    return {
        "summary": "SDD IMC",
        "requirements": [
            {
                "id": "REQ-001",
                "description": "Calcular IMC",
                "priority": "must",
                "acceptance_criteria": [],
            }
        ],
        "design_overview": "Simple design",
        "design_diagrams": [],
        "constraints": [],
        "tasks": [
            {
                "id": "TASK-001",
                "agent": "backend",
                "title": title,
                "description": task_desc,
                "depends_on": [],
                "estimated_complexity": "low",
            }
        ],
    }


def test_float_hint_injected_for_test_task():
    """S55-C: tarea con keyword 'test' recibe hint S55-C con instrucción round()."""
    sdd = _make_sdd_with_task(
        "Crear `tests/test_imc.py` con pytest: casos happy path",
        title="Casos de prueba IMC",
    )
    task = sdd["tasks"][0]
    result = graph._build_single_task_sdd_content(sdd, "backend", task, 0, 1)

    assert "S55-C" in result, "Hint S55-C no encontrado en output"
    assert "round()" in result, "Instrucción round() no encontrada"
    assert "NUNCA escribas valores float de memoria" in result


def test_float_hint_injected_for_pytest_task():
    """S55-C: tarea con keyword 'pytest' recibe hint S55-C."""
    sdd = _make_sdd_with_task(
        "Crear `tests/test_imc.py` con pytest: happy path y casos edge",
        title="Casos de prueba IMC",
    )
    task = sdd["tasks"][0]
    result = graph._build_single_task_sdd_content(sdd, "backend", task, 0, 1)

    assert "S55-C" in result


def test_no_float_hint_for_non_test_task():
    """S55-C: tarea de producción sin keywords de test NO recibe hint S55-C."""
    sdd = _make_sdd_with_task(
        "Crear `src/imc/service.py` con función calcular_imc(peso, altura)"
    )
    task = sdd["tasks"][0]
    result = graph._build_single_task_sdd_content(sdd, "backend", task, 0, 1)

    assert "S55-C" not in result, (
        "Hint S55-C inyectado erróneamente en tarea de producción"
    )


# ---------------------------------------------------------------------------
# S55-D: update_test_retry log.warning para archivos en disco
# ---------------------------------------------------------------------------


def test_update_test_retry_logs_disk_files_as_warning(tmp_path, caplog):
    """S55-D: S54-D en update_test_retry usa WARNING (visible sin configuración adicional)."""
    # Crear archivos Python en el directorio de trabajo
    src_dir = tmp_path / "src" / "imc"
    src_dir.mkdir(parents=True)
    (src_dir / "models.py").write_text("class ImcRequest: pass\n")
    (src_dir / "service.py").write_text("def calcular_imc(): pass\n")

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_imc.py").write_text("def test_ok(): pass\n")

    state = {
        "test_results": {
            "passed": False,
            "output": "AssertionError: assert 22.35 == 22.86",
            "runner": "pytest",
        },
        "retry_feedback": "",
        "test_retry_count": 0,
        "directory": str(tmp_path),
        "selective_retry_agents": [],
        "agent_results": [],
    }

    with caplog.at_level(logging.WARNING, logger="ovd-graph"):
        graph.update_test_retry(state)

    warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any(
        "S54-D update_test_retry" in m and "archivo(s) Python" in m
        for m in warning_msgs
    ), f"No se encontró WARNING de S54-D. Mensajes: {warning_msgs}"
