"""Tests S121 — Fix ImportError en conftest.py por engine module-level + lazy init rule.

S121-A: backend_python.md prohíbe create_async_engine() a nivel de módulo en src/database.py.
S121-B: backend_python.md prohíbe 'from src.database import ...' en tests/conftest.py.
S121-C: update_test_retry inyecta hint de lazy init cuando conftest.py tiene ImportError de database.
"""

import pathlib
import re

_ENGINE_ROOT = pathlib.Path(".")
_GRAPH_SRC = (_ENGINE_ROOT / "graph.py").read_text(encoding="utf-8")
_BACKEND_PY_MD = (_ENGINE_ROOT / "templates" / "stack" / "backend_python.md").read_text(
    encoding="utf-8"
)


def _get_function_body(src: str, func_name: str) -> str:
    pattern = rf"(?:async )?def {re.escape(func_name)}\b.*?(?=\n(?:async )?def [a-z_]|\Z)"
    m = re.search(pattern, src, re.DOTALL)
    return m.group(0) if m else ""


# ---------------------------------------------------------------------------
# S121-A — PROHIBIDO engine module-level en src/database.py
# ---------------------------------------------------------------------------


def test_s121a_rule_present_in_backend_python_md():
    """backend_python.md debe tener sección S121-A sobre lazy engine init."""
    assert "S121-A" in _BACKEND_PY_MD, (
        "S121-A: falta referencia S121-A en backend_python.md"
    )


def test_s121a_prohibits_module_level_engine():
    """backend_python.md debe prohibir create_async_engine a nivel de módulo."""
    assert "PROHIBIDO" in _BACKEND_PY_MD or "NUNCA" in _BACKEND_PY_MD
    # La sección S121-A debe usar "module-level" o "nivel de módulo"
    assert "nivel de módulo" in _BACKEND_PY_MD or "module-level" in _BACKEND_PY_MD, (
        "S121-A: debe mencionar el riesgo de engine a nivel de módulo"
    )


def test_s121a_shows_lazy_factory_pattern():
    """backend_python.md debe mostrar el patrón factory con _engine=None."""
    assert "_engine = None" in _BACKEND_PY_MD or "_engine=None" in _BACKEND_PY_MD, (
        "S121-A: debe mostrar el patrón _engine=None como estado lazy"
    )
    assert "get_engine" in _BACKEND_PY_MD, (
        "S121-A: debe mostrar la función get_engine() como factory"
    )


def test_s121a_explains_importerror_cause():
    """backend_python.md debe explicar que el error ocurre en colección de pytest."""
    assert "ImportError" in _BACKEND_PY_MD, (
        "S121-A: debe mencionar ImportError como consecuencia"
    )


# ---------------------------------------------------------------------------
# S121-B — PROHIBIDO from src.database import ... en conftest.py
# ---------------------------------------------------------------------------


def test_s121b_rule_present_in_backend_python_md():
    """backend_python.md debe tener sección S121-B sobre conftest.py."""
    assert "S121-B" in _BACKEND_PY_MD, (
        "S121-B: falta referencia S121-B en backend_python.md"
    )


def test_s121b_prohibits_database_import_in_conftest():
    """backend_python.md debe prohibir 'from src.database import' en conftest.py."""
    assert "from src.database import" in _BACKEND_PY_MD, (
        "S121-B: debe mostrar el patrón prohibido 'from src.database import ...'"
    )


def test_s121b_shows_httpx_minimal_conftest():
    """backend_python.md debe mostrar el conftest mínimo con httpx.AsyncClient."""
    assert "ASGITransport" in _BACKEND_PY_MD, (
        "S121-B: debe mostrar ASGITransport como patrón correcto de conftest"
    )
    assert "AsyncClient" in _BACKEND_PY_MD, (
        "S121-B: debe mostrar httpx.AsyncClient en el conftest correcto"
    )


# ---------------------------------------------------------------------------
# S121-C — update_test_retry inyecta hint cuando conftest.py tiene ImportError
# ---------------------------------------------------------------------------


def test_s121c_detection_present_in_update_test_retry():
    """update_test_retry debe tener detección de conftest ImportError."""
    body = _get_function_body(_GRAPH_SRC, "update_test_retry")
    assert body, "update_test_retry no encontrada en graph.py"
    assert "_is_conftest_importerror" in body, (
        "S121-C: falta _is_conftest_importerror en update_test_retry"
    )


def test_s121c_checks_conftest_and_database_in_output():
    """La detección S121-C verifica 'conftest.py' y 'database' en test_output."""
    body = _get_function_body(_GRAPH_SRC, "update_test_retry")
    assert "conftest.py" in body, (
        "S121-C: debe verificar 'conftest.py' en test_output"
    )
    assert '"database"' in body or "'database'" in body, (
        "S121-C: debe verificar 'database' en test_output para limitar falsos positivos"
    )


def test_s121c_hint_describes_lazy_init():
    """El hint S121-C debe describir la solución de lazy init."""
    body = _get_function_body(_GRAPH_SRC, "update_test_retry")
    assert "_conftest_import_hint" in body, (
        "S121-C: falta _conftest_import_hint en update_test_retry"
    )
    assert "S121-C" in body, (
        "S121-C: falta comentario de trazabilidad S121-C en update_test_retry"
    )


def test_s121c_hint_injected_in_new_feedback():
    """_conftest_import_hint debe estar incluido en new_feedback."""
    body = _get_function_body(_GRAPH_SRC, "update_test_retry")
    # Buscar el bloque donde se construye new_feedback
    idx_nf = body.find("new_feedback")
    assert idx_nf != -1, "new_feedback no encontrado en update_test_retry"
    # Desde new_feedback, buscar que _conftest_import_hint aparezca en las próximas líneas
    block = body[idx_nf : idx_nf + 1200]
    assert "_conftest_import_hint" in block, (
        "S121-C: _conftest_import_hint debe estar referenciado en new_feedback"
    )


def test_s121c_lazy_init_mentioned_in_hint():
    """El cuerpo de _conftest_import_hint debe mencionar la solución de lazy init."""
    body = _get_function_body(_GRAPH_SRC, "update_test_retry")
    # Buscar la cadena del hint
    idx = body.find("_conftest_import_hint =")
    assert idx != -1, "S121-C: no se encontró asignación de _conftest_import_hint"
    hint_block = body[idx : idx + 1400]
    assert "factory" in hint_block or "get_engine" in hint_block, (
        "S121-C: el hint debe mencionar la solución factory/get_engine"
    )
    assert "ASGITransport" in hint_block or "httpx" in hint_block or "src.main" in hint_block, (
        "S121-C: el hint debe mencionar el conftest correcto con src.main"
    )
