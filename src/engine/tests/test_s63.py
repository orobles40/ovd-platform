"""
OVD Platform — Tests S63

S63-A: status Annotated con last-write-wins
S63-B: cleanup en update_test_retry (no en run_tests)
S63-C: rag_context filtrado cuando oracle_involved=False
S63-D: test cases RUT correctos en template
"""

import os
import pathlib
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import graph

# ---------------------------------------------------------------------------
# S63-D: template RUT tiene casos correctos
# ---------------------------------------------------------------------------


def test_s63d_template_rut_9999999_dv_is_3():
    """S63-D: template backend_python.md indica que 9.999.999-K es INVÁLIDO."""
    tpl = (
        pathlib.Path(__file__).parent.parent
        / "templates"
        / "stack"
        / "backend_python.md"
    )
    content = tpl.read_text(encoding="utf-8")
    # El template NO debe afirmar que 9.999.999-K es válido
    assert '9.999.999-K") == True' not in content, (
        "template afirma que 9.999.999-K es válido — DV real es 3, no K"
    )
    # El template DEBE incluir el caso correcto
    assert "9.999.999-3" in content, "template no documenta que DV de 9.999.999 es 3"


def test_s63d_template_rut_invalid_case_documented():
    """S63-D: template documenta explícitamente que 9.999.999-K es INVÁLIDO."""
    tpl = (
        pathlib.Path(__file__).parent.parent
        / "templates"
        / "stack"
        / "backend_python.md"
    )
    content = tpl.read_text(encoding="utf-8")
    # Debe documentar que K es DV incorrecto para ese cuerpo
    assert "9.999.999-K" in content, (
        "template debería mencionar 9.999.999-K como caso inválido"
    )
    # Verifica que la mención sea como caso inválido (aparece en tabla con ❌ o comentario == False)
    _invalid_markers = ["== False", "❌ RUT inválido", "DV real de 9.999.999 es 3"]
    assert any(m in content for m in _invalid_markers), (
        "template debería marcar 9.999.999-K como inválido (con == False, ❌, o explicación)"
    )


def test_s63d_validate_rut_reference_implementation():
    """S63-D: verificar que el algoritmo módulo 11 sea correcto para casos conocidos."""

    # Implementación de referencia verificada
    def validate_rut(rut: str) -> bool:
        import re

        rut = rut.replace(".", "").replace("-", "").upper()
        if not re.match(r"^\d{7,8}[0-9K]$", rut):
            return False
        body, dv = rut[:-1], rut[-1]
        total, factor = 0, 2
        for digit in reversed(body):
            total += int(digit) * factor
            factor = 2 if factor == 7 else factor + 1
        remainder = 11 - (total % 11)
        expected = {10: "K", 11: "0"}.get(remainder, str(remainder))
        return dv == expected

    # Casos verificados computacionalmente
    assert validate_rut("1.000.005-K") is True, "1.000.005-K debe ser válido"
    assert validate_rut("12.345.678-5") is True, "12.345.678-5 debe ser válido"
    assert validate_rut("9.999.999-3") is True, "9.999.999-3 debe ser válido (DV=3)"
    assert validate_rut("9.999.999-K") is False, (
        "9.999.999-K debe ser INVÁLIDO (DV real=3)"
    )


# ---------------------------------------------------------------------------
# S63-A: status Annotated
# ---------------------------------------------------------------------------


def test_s63a_status_field_has_reducer():
    """S63-A: OVDState.status tiene reducer Annotated last-write-wins."""
    import typing

    import typing_extensions

    hints = typing.get_type_hints(graph.OVDState, include_extras=True)
    status_hint = hints.get("status")
    assert status_hint is not None
    # Si tiene Annotated, get_args retorna (tipo, *metadatos)
    args = typing_extensions.get_args(status_hint)
    assert len(args) >= 2, "status debe ser Annotated[str, reducer]"
    assert args[0] is str, "status debe ser str"


def test_s63a_status_reducer_is_callable():
    """S63-A: el reducer de status es callable (last-write-wins)."""
    import typing

    import typing_extensions

    hints = typing.get_type_hints(graph.OVDState, include_extras=True)
    status_hint = hints.get("status")
    args = typing_extensions.get_args(status_hint)
    assert len(args) >= 2, "status debe ser Annotated[str, reducer]"
    reducer = args[1]
    assert callable(reducer), "el segundo argumento de Annotated debe ser callable"
    # Verificar comportamiento last-write-wins: el reducer retorna el segundo valor
    result = reducer("old_value", "new_value")
    assert result == "new_value", (
        "el reducer debe retornar el segundo valor (last-write-wins)"
    )


# ---------------------------------------------------------------------------
# S63-B: cleanup en update_test_retry, NO en run_tests
# ---------------------------------------------------------------------------


def test_s63b_cleanup_uses_agent_results_not_rglob(tmp_path):
    """S63-B: cleanup S63-B borra solo archivos listados en agent_results del agente en retry."""
    # Simular archivos del retry anterior
    src = tmp_path / "src" / "contracts"
    src.mkdir(parents=True)
    (src / "service.py").write_text("# versión anterior")
    (src / "models.py").write_text("# versión anterior")

    # Simular un archivo que NO debe ser borrado (no está en agent_results)
    (tmp_path / "pytest.ini").write_text("[pytest]\npythonpath = .\n")

    state = {
        "test_results": {
            "passed": False,
            "output": "AssertionError: assert False == True\n",
            "return_code": 1,
        },
        "retry_feedback": "",
        "last_test_error": "",
        "test_retry_count": 1,
        "directory": str(tmp_path),
        "sdd": {"tasks": []},
        "agent_results": [
            {
                "agent": "backend",
                "artifacts": [
                    {"path": "src/contracts/service.py"},
                    {"path": "src/contracts/models.py"},
                ],
                "output": "",
            }
        ],
        "selective_retry_agents": ["backend"],
        "messages": [],
        "status": "",
    }

    result = graph.update_test_retry(state)

    # pytest.ini NO debe ser borrado
    assert (tmp_path / "pytest.ini").exists(), (
        "pytest.ini NO debe ser borrado por S63-B"
    )

    # Los archivos de agent_results DEBEN ser borrados (son del round anterior)
    assert not (src / "service.py").exists(), "service.py debe ser borrado por S63-B"
    assert not (src / "models.py").exists(), "models.py debe ser borrado por S63-B"


def test_s63b_cleanup_in_retry_round_zero(tmp_path):
    """S63-B: cleanup ocurre en retry_round==0 también — borra artefactos del round 0
    antes de despachar retry ronda 1, evitando mezcla de archivos parciales con nuevos."""
    src = tmp_path / "src"
    src.mkdir()
    service = src / "main.py"
    service.write_text("# primera ronda — debe ser borrado antes del retry")

    state = {
        "test_results": {
            "passed": False,
            "output": "AssertionError\n",
            "return_code": 1,
        },
        "retry_feedback": "",
        "last_test_error": "",
        "test_retry_count": 0,  # ronda 0 — S63-B DEBE limpiar igual
        "directory": str(tmp_path),
        "sdd": {"tasks": []},
        "agent_results": [
            {"agent": "backend", "artifacts": [{"path": "src/main.py"}], "output": ""}
        ],
        "selective_retry_agents": ["backend"],
        "messages": [],
        "status": "",
    }

    graph.update_test_retry(state)

    # S63-B debe borrar el archivo del round 0 antes del retry ronda 1
    assert not service.exists(), (
        "S63-B: debe borrar artefactos del round 0 antes de retry ronda 1"
    )


def test_s63b_cleanup_not_in_run_tests(tmp_path):
    """S63-B: run_tests ya NO hace cleanup de archivos (fue movido a update_test_retry)."""
    # Crear archivos que simularían haber sido escritos por el retry actual
    src = tmp_path / "src"
    src.mkdir()
    service = src / "main.py"
    service.write_text("from fastapi import FastAPI\napp = FastAPI()\n")

    test_file = tmp_path / "tests" / "test_app.py"
    test_file.parent.mkdir()
    test_file.write_text("def test_ok(): assert True\n")

    (tmp_path / "pytest.ini").write_text("[pytest]\npythonpath = .\n")

    state = {
        "test_results": {},
        "agent_results": [
            {"agent": "backend", "artifacts": [{"path": "src/main.py"}], "output": ""}
        ],
        "directory": str(tmp_path),
        "retry_feedback": "retry previo",
        "test_retry_count": 1,
        "cycle_start_ts": 0,
        "selective_retry_agents": [],
        "language": "es",
        "stack_language": "python",
        "org_id": "",
        "project_id": "",
        "jwt_token": "",
        "stack_routing": "auto",
    }

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"1 passed", None))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        import asyncio

        asyncio.run(graph.run_tests(state))

    # El archivo escrito por el retry actual NO debe ser borrado por run_tests
    assert service.exists(), (
        "S63-B: run_tests NO debe borrar src/main.py (es del retry actual)"
    )


# ---------------------------------------------------------------------------
# S63-C: rag_context filtrado
# ---------------------------------------------------------------------------


def test_s63c_strip_db_restrictions_filters_oracle_lines():
    """S63-C: _strip_db_restrictions elimina líneas con keywords Oracle."""
    context = """Framework: FastAPI
Python: 3.12
Oracle: python-oracledb thick mode requerido
thick mode: usar oracledb.init_oracle_client()
DATABASE_URL: oracle+oracledb://user:pass@host.docker.internal:1522
Validación: Pydantic v2
"""
    result = graph._strip_db_restrictions(context, oracle_involved=False)
    # Verificar que líneas Python puro NO fueron eliminadas
    assert "FastAPI" in result
    assert "Pydantic" in result
    # Verificar que se eliminaron líneas con Oracle
    assert "oracle+oracledb" not in result.lower()
    assert "oracledb.init_oracle_client" not in result


def test_s63c_strip_db_restrictions_preserves_non_oracle():
    """S63-C: _strip_db_restrictions no elimina líneas sin keywords Oracle."""
    context = """Framework: FastAPI
Python: 3.12
Validación: Pydantic v2
Tests: pytest
"""
    result = graph._strip_db_restrictions(context, oracle_involved=False)
    assert result.strip() == context.strip()


def test_s63c_accepts_oracle_involved_param():
    """S63-C: _strip_db_restrictions acepta parámetro oracle_involved."""
    import inspect

    sig = inspect.signature(graph._strip_db_restrictions)
    assert "oracle_involved" in sig.parameters, (
        "_strip_db_restrictions debe aceptar parámetro oracle_involved (S63-C)"
    )


def test_s63c_strip_empty_context():
    """S63-C: _strip_db_restrictions maneja contexto vacío."""
    assert graph._strip_db_restrictions("", oracle_involved=False) == ""
    assert graph._strip_db_restrictions(None, oracle_involved=False) is None
