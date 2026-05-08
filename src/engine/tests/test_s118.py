"""Tests S118 — Fix detección _is_structural para "no tests ran" (pytest --tb=short).

Causa raíz: pytest con --tb=short imprime "no tests ran" en lugar de "collected 0 items"
cuando hay ImportError durante la recolección. _is_structural requería "collected 0 items"
→ last_test_error = "" → retries corrían a ciegas sin feedback del error anterior.

S118-A: update_test_retry._is_structural acepta "no tests ran" e "ImportError while importing"
S118-B: run_tests S57-B._is_collection_error acepta los mismos patrones
S118-C: S65-E requirements.txt mínimo incluye pytest-asyncio y asyncpg
"""

import pathlib
import re

# ---------------------------------------------------------------------------
# Helpers de lectura de código fuente
# ---------------------------------------------------------------------------

_GRAPH_SRC = pathlib.Path("graph.py").read_text(encoding="utf-8")


def _get_function_body(src: str, func_name: str) -> str:
    """Extrae el cuerpo de una función hasta la siguiente def/async def al mismo nivel."""
    pattern = (
        rf"(?:async )?def {re.escape(func_name)}\b.*?(?=\n(?:async )?def [a-z_]|\Z)"
    )
    m = re.search(pattern, src, re.DOTALL)
    return m.group(0) if m else ""


# ---------------------------------------------------------------------------
# S118-A — _is_structural en update_test_retry
# ---------------------------------------------------------------------------


def test_is_structural_uses_no_tests_ran():
    """_is_structural debe aceptar 'no tests ran' (output real de pytest --tb=short)."""
    body = _get_function_body(_GRAPH_SRC, "update_test_retry")
    assert body, "update_test_retry no encontrada en graph.py"
    assert "no tests ran" in body, (
        "S118-A: _is_structural debe incluir 'no tests ran' como indicador de collection error"
    )


def test_is_structural_uses_importerror_while_importing():
    """_is_structural debe aceptar 'ImportError while importing' (frase estándar pytest)."""
    body = _get_function_body(_GRAPH_SRC, "update_test_retry")
    assert "ImportError while importing" in body, (
        "S118-A: _is_structural debe incluir 'ImportError while importing'"
    )


def test_is_structural_still_accepts_collected_0_items():
    """_is_structural conserva 'collected 0 items' como condición alternativa (backward compat)."""
    body = _get_function_body(_GRAPH_SRC, "update_test_retry")
    assert "collected 0 items" in body, (
        "S118-A: _is_structural no debe eliminar 'collected 0 items' — es una condición OR"
    )


def test_is_structural_requires_importerror_or_modulenotfound():
    """_is_structural sigue requiriendo ImportError/ModuleNotFoundError (evita false positives)."""
    body = _get_function_body(_GRAPH_SRC, "update_test_retry")
    # La lógica debe combinar el error de import con las frases de "no collection"
    has_import_check = "ModuleNotFoundError" in body and "ImportError" in body
    assert has_import_check, (
        "S118-A: _is_structural debe comprobar ModuleNotFoundError/ImportError además de las frases de collection"
    )


def test_is_structural_s118a_comment_present():
    """El comentario S118-A debe estar presente para trazabilidad."""
    body = _get_function_body(_GRAPH_SRC, "update_test_retry")
    assert "S118-A" in body, (
        "S118-A: falta comentario de trazabilidad en update_test_retry"
    )


# ---------------------------------------------------------------------------
# S118-B — _is_collection_error en run_tests (S57-B)
# ---------------------------------------------------------------------------


def _get_run_tests_body(src: str) -> str:
    return _get_function_body(src, "run_tests")


def test_s57b_uses_no_tests_ran():
    """S57-B en run_tests debe aceptar 'no tests ran' para enriquecer el output."""
    body = _get_run_tests_body(_GRAPH_SRC)
    assert body, "run_tests no encontrada en graph.py"
    assert "no tests ran" in body, (
        "S118-B: S57-B._is_collection_error debe incluir 'no tests ran'"
    )


def test_s57b_uses_importerror_while_importing():
    """S57-B en run_tests debe aceptar 'ImportError while importing'."""
    body = _get_run_tests_body(_GRAPH_SRC)
    assert "ImportError while importing" in body, (
        "S118-B: S57-B._is_collection_error debe incluir 'ImportError while importing'"
    )


def test_s57b_s118b_comment_present():
    """El comentario S118-B debe estar presente en run_tests."""
    body = _get_run_tests_body(_GRAPH_SRC)
    assert "S118-B" in body, "S118-B: falta comentario de trazabilidad en run_tests"


# ---------------------------------------------------------------------------
# S118-C — S65-E requirements.txt mínimo
# ---------------------------------------------------------------------------


def _get_ensure_infra_body(src: str) -> str:
    return _get_function_body(src, "_ensure_python_infrastructure")


def test_s65e_requirements_includes_pytest_asyncio():
    """S65-E debe incluir pytest-asyncio en el requirements.txt mínimo."""
    body = _get_ensure_infra_body(_GRAPH_SRC)
    assert body, "_ensure_python_infrastructure no encontrada en graph.py"
    assert "pytest-asyncio" in body, (
        "S118-C: el requirements.txt mínimo de S65-E debe incluir pytest-asyncio"
    )


def test_s65e_requirements_includes_asyncpg():
    """S65-E debe incluir asyncpg para tests con async SQLAlchemy."""
    body = _get_ensure_infra_body(_GRAPH_SRC)
    assert "asyncpg" in body, (
        "S118-C: el requirements.txt mínimo de S65-E debe incluir asyncpg"
    )


def test_s65e_requirements_still_includes_core_packages():
    """S65-E no debe eliminar los paquetes core existentes."""
    body = _get_ensure_infra_body(_GRAPH_SRC)
    for pkg in ("fastapi", "uvicorn", "sqlalchemy", "pydantic", "pytest", "httpx"):
        assert pkg in body, (
            f"S118-C: {pkg} no debe eliminarse del requirements.txt mínimo"
        )


def test_s65e_s118c_comment_present():
    """El comentario S118-C debe estar presente para trazabilidad."""
    body = _get_ensure_infra_body(_GRAPH_SRC)
    assert "S118-C" in body, (
        "S118-C: falta comentario de trazabilidad en _ensure_python_infrastructure"
    )
