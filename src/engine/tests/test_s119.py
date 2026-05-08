"""Tests S119 — Fix pytest en producción + propagación last_test_error + regla Pydantic v2.

S119-A: pytest y pytest-asyncio movidos a [project]dependencies — disponibles con uv sync --no-dev.
S119-B: _new_last_error en update_test_retry propaga [S103-P2] y "No module named" outputs.
S119-C: backend_python.md prohíbe @classmethod duplicado en Pydantic v2 field_validator.
"""

import pathlib
import re
import tomllib

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ENGINE_ROOT = pathlib.Path(".")
_GRAPH_SRC = (_ENGINE_ROOT / "graph.py").read_text(encoding="utf-8")
_PYPROJECT = tomllib.loads(
    (_ENGINE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
)
_BACKEND_PY_MD = (_ENGINE_ROOT / "templates" / "stack" / "backend_python.md").read_text(
    encoding="utf-8"
)


def _get_function_body(src: str, func_name: str) -> str:
    pattern = (
        rf"(?:async )?def {re.escape(func_name)}\b.*?(?=\n(?:async )?def [a-z_]|\Z)"
    )
    m = re.search(pattern, src, re.DOTALL)
    return m.group(0) if m else ""


# ---------------------------------------------------------------------------
# S119-A — pytest como dependencia principal (no dev)
# ---------------------------------------------------------------------------


def test_s119a_pytest_in_main_dependencies():
    """pytest debe estar en [project]dependencies, no solo en [dependency-groups]dev."""
    main_deps: list[str] = _PYPROJECT["project"]["dependencies"]
    has_pytest = any(
        "pytest>=" in d and "pytest-asyncio" not in d and "pytest-cov" not in d
        for d in main_deps
    )
    assert has_pytest, (
        "S119-A: pytest debe estar en [project]dependencies para que 'uv sync --no-dev' lo incluya en Docker prod"
    )


def test_s119a_pytest_asyncio_in_main_dependencies():
    """pytest-asyncio debe estar en [project]dependencies."""
    main_deps: list[str] = _PYPROJECT["project"]["dependencies"]
    has_asyncio = any("pytest-asyncio>=" in d for d in main_deps)
    assert has_asyncio, (
        "S119-A: pytest-asyncio debe estar en [project]dependencies para tests async en prod"
    )


def test_s119a_pytest_cov_still_in_dev():
    """pytest-cov permanece en [dependency-groups]dev — no es necesario en prod."""
    dev_deps: list[str] = _PYPROJECT.get("dependency-groups", {}).get("dev", [])
    has_cov = any("pytest-cov" in d for d in dev_deps)
    assert has_cov, "S119-A: pytest-cov debe permanecer en dev (no mover a main)"


def test_s119a_comment_present_in_pyproject():
    """El comentario S119-A debe estar en pyproject.toml para trazabilidad."""
    content = (_ENGINE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "S119-A" in content, (
        "S119-A: falta comentario de trazabilidad en pyproject.toml"
    )


# ---------------------------------------------------------------------------
# S119-B — _new_last_error propaga [S103-P2] y "No module named"
# ---------------------------------------------------------------------------


def test_s119b_new_last_error_includes_s103_output():
    """_new_last_error debe incluir test_output cuando contiene '[S103-P2]'."""
    body = _get_function_body(_GRAPH_SRC, "update_test_retry")
    assert body, "update_test_retry no encontrada en graph.py"
    assert "_is_s103_output" in body, (
        "S119-B: falta _is_s103_output en update_test_retry"
    )
    assert "[S103-P2]" in body, (
        "S119-B: la detección de [S103-P2] debe estar en update_test_retry"
    )


def test_s119b_new_last_error_includes_no_module():
    """_new_last_error debe incluir test_output cuando contiene 'No module named'."""
    body = _get_function_body(_GRAPH_SRC, "update_test_retry")
    assert "_is_no_module" in body, "S119-B: falta _is_no_module en update_test_retry"
    assert "No module named" in body, (
        "S119-B: 'No module named' debe estar en la detección de update_test_retry"
    )


def test_s119b_new_last_error_uses_or_chain():
    """_new_last_error usa OR chain: _is_structural OR _is_s65a OR _is_s103 OR _is_no_module."""
    body = _get_function_body(_GRAPH_SRC, "update_test_retry")
    # Verificar que la asignación de _new_last_error incluye todos los flags
    new_error_line = [
        l for l in body.splitlines() if "_new_last_error" in l and "test_output if" in l
    ]
    assert new_error_line, (
        "S119-B: no se encontró la asignación de _new_last_error con condición compuesta"
    )
    line = new_error_line[0]
    assert "_is_s103_output" in line, (
        "S119-B: _is_s103_output no está en la condición de _new_last_error"
    )
    assert "_is_no_module" in line, (
        "S119-B: _is_no_module no está en la condición de _new_last_error"
    )
    assert "_is_s65a_output" in line, (
        "S119-B: _is_s65a_output no debe eliminarse de la condición"
    )
    assert "_is_structural" in line, (
        "S119-B: _is_structural no debe eliminarse de la condición"
    )


def test_s119b_comment_present():
    """El comentario S119-B debe estar presente en update_test_retry."""
    body = _get_function_body(_GRAPH_SRC, "update_test_retry")
    assert "S119-B" in body, (
        "S119-B: falta comentario de trazabilidad en update_test_retry"
    )


# ---------------------------------------------------------------------------
# S119-C — Regla @classmethod duplicado en backend_python.md
# ---------------------------------------------------------------------------


def test_s119c_duplicate_classmethod_rule_present():
    """backend_python.md debe tener sección explícita sobre @classmethod duplicado."""
    assert "S119-C" in _BACKEND_PY_MD, (
        "S119-C: falta referencia S119-C en backend_python.md"
    )


def test_s119c_prohibits_classmethod_before_field_validator():
    """backend_python.md debe prohibir @classmethod antes de @field_validator."""
    assert "@classmethod" in _BACKEND_PY_MD and "@field_validator" in _BACKEND_PY_MD
    # La regla de prohibición debe existir
    assert "PROHIBIDO" in _BACKEND_PY_MD or "NUNCA" in _BACKEND_PY_MD, (
        "S119-C: debe haber una restricción PROHIBIDO/NUNCA sobre el patrón incorrecto"
    )


def test_s119c_shows_correct_decorator_order():
    """backend_python.md muestra el orden correcto: @field_validator primero, @classmethod debajo."""
    # El orden correcto en el ejemplo existente: @field_validator → @classmethod → def
    idx_fv = _BACKEND_PY_MD.find("@field_validator")
    idx_cm = _BACKEND_PY_MD.find("@classmethod", idx_fv)
    assert idx_fv != -1 and idx_cm != -1 and idx_cm > idx_fv, (
        "S119-C: el ejemplo correcto debe mostrar @field_validator antes de @classmethod"
    )


def test_s119c_prohibits_standalone_classmethod():
    """backend_python.md debe mostrar como incorrecto el @classmethod standalone en BaseModel."""
    assert (
        "standalone" in _BACKEND_PY_MD.lower()
        or "# ← no es un validator" in _BACKEND_PY_MD
    ), "S119-C: falta ejemplo de @classmethod standalone incorrecto en BaseModel"
