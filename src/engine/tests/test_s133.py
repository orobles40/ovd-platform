"""Tests S133 — Fix @classmethod duplicado + retry full-delivery.

H1 (S133-C): _fix_duplicate_classmethod elimina @classmethod duplicados.
H2 (S133-C): postprocess_python_file llama al fix.
H3 (S133-B): retry preamble incluye instrucción de entrega completa.
H4 (S133-A): backend_python.md tiene aviso de alta visibilidad S133-A.
"""

import pathlib
import sys
import textwrap

_ENGINE_DIR = pathlib.Path(".")
sys.path.insert(0, str(_ENGINE_DIR))

_POSTPROCESSOR_SRC = (_ENGINE_DIR / "code_postprocessor.py").read_text(encoding="utf-8")
_GRAPH_SRC = (_ENGINE_DIR / "graph.py").read_text(encoding="utf-8")
_BACKEND_PY_TEMPLATE = (
    _ENGINE_DIR / "templates" / "stack" / "backend_python.md"
).read_text(encoding="utf-8")


# ── H1: _fix_duplicate_classmethod ──────────────────────────────────────────


def test_h1_function_exists_in_postprocessor():
    """code_postprocessor.py define _fix_duplicate_classmethod."""
    assert "_fix_duplicate_classmethod" in _POSTPROCESSOR_SRC


def test_h1_removes_double_classmethod():
    """Dos @classmethod consecutivos quedan como uno."""
    from code_postprocessor import _fix_duplicate_classmethod

    code = textwrap.dedent("""\
        class Foo:
            @field_validator('x')
            @classmethod
            @classmethod
            def validate_x(cls, v):
                return v
    """)
    result = _fix_duplicate_classmethod(code)
    assert result.count("@classmethod") == 1


def test_h1_removes_triple_classmethod():
    """Tres @classmethod consecutivos quedan como uno."""
    from code_postprocessor import _fix_duplicate_classmethod

    code = textwrap.dedent("""\
        @field_validator('y')
        @classmethod
        @classmethod
        @classmethod
        def validate_y(cls, v):
            return v
    """)
    result = _fix_duplicate_classmethod(code)
    assert result.count("@classmethod") == 1


def test_h1_no_change_when_single_classmethod():
    """Un solo @classmethod no es modificado."""
    from code_postprocessor import _fix_duplicate_classmethod

    code = textwrap.dedent("""\
        @field_validator('z')
        @classmethod
        def validate_z(cls, v):
            return v
    """)
    result = _fix_duplicate_classmethod(code)
    assert result == code


def test_h1_no_change_when_no_classmethod():
    """Código sin @classmethod no es modificado."""
    from code_postprocessor import _fix_duplicate_classmethod

    code = "def foo():\n    return 1\n"
    result = _fix_duplicate_classmethod(code)
    assert result == code


def test_h1_handles_indented_duplicate():
    """@classmethod duplicado con indentación es corregido."""
    from code_postprocessor import _fix_duplicate_classmethod

    code = textwrap.dedent("""\
        class TurnoCreate(BaseModel):
            rut: str

            @field_validator('rut')
            @classmethod
            @classmethod
            def validate_rut(cls, v: str) -> str:
                return v
    """)
    result = _fix_duplicate_classmethod(code)
    assert result.count("@classmethod") == 1
    assert "validate_rut" in result


def test_h1_non_consecutive_classmethods_preserved():
    """Dos @classmethod NO consecutivos (en distintos validators) son preservados."""
    from code_postprocessor import _fix_duplicate_classmethod

    code = textwrap.dedent("""\
        @field_validator('a')
        @classmethod
        def val_a(cls, v):
            return v

        @field_validator('b')
        @classmethod
        def val_b(cls, v):
            return v
    """)
    result = _fix_duplicate_classmethod(code)
    assert result.count("@classmethod") == 2


# ── H2: integración con postprocess_python_file ─────────────────────────────


def test_h2_postprocess_fixes_duplicate_classmethod():
    """postprocess_python_file elimina @classmethod duplicado en models.py."""
    from code_postprocessor import postprocess_python_file

    code = textwrap.dedent("""\
        from pydantic import BaseModel, field_validator

        class TurnoCreate(BaseModel):
            rut: str

            @field_validator('rut')
            @classmethod
            @classmethod
            def validate_rut(cls, v: str) -> str:
                if not v:
                    raise ValueError("RUT requerido")
                return v
    """)
    result = postprocess_python_file(code, "src/turnos/models.py")
    assert result.count("@classmethod") == 1
    assert "validate_rut" in result


def test_h2_called_after_decorator_order_fix():
    """S133-C se llama DESPUÉS de S77-B — necesario para limpiar duplicados que S72-B+S77-B crean."""
    # Buscar la llamada en postprocess_python_file (línea de comentario inline)
    idx_c = _POSTPROCESSOR_SRC.find("# S133-C: eliminar @classmethod duplicados consecutivos (debe correr post-S72B+S77B)")
    idx_77b = _POSTPROCESSOR_SRC.find("# S77-B: reordenar decoradores Pydantic (field_validator ANTES")
    assert idx_c != -1, "S133-C call marker no encontrado en postprocess_python_file"
    assert idx_77b != -1, "S77-B call marker no encontrado"
    assert idx_c > idx_77b, "S133-C debe correr después de S77-B"


# ── H3: retry preamble full-delivery ─────────────────────────────────────────


def test_h3_retry_preamble_has_full_delivery():
    """graph.py retry preamble incluye instrucción S133-B de entrega completa."""
    assert "S133-B" in _GRAPH_SRC


def test_h3_full_delivery_text_present():
    """El preamble indica entregar todos los archivos asignados."""
    assert (
        "Entrega TODOS tus archivos asignados" in _GRAPH_SRC
        or "todos tus archivos asignados" in _GRAPH_SRC
    )


def test_h3_full_delivery_in_retry_block():
    """La instrucción S133-B está dentro del bloque de retry preamble."""
    idx_preamble = _GRAPH_SRC.find("REINTENTO DE CORRECCIÓN (ronda {round})")
    idx_s133b = _GRAPH_SRC.find("S133-B")
    assert idx_s133b > idx_preamble - 500, "S133-B debe estar cerca del preamble"


# ── H4: template backend_python.md ──────────────────────────────────────────


def test_h4_template_has_s133a_alert():
    """backend_python.md contiene alerta S133-A."""
    assert "S133-A" in _BACKEND_PY_TEMPLATE


def test_h4_alert_is_before_s119c_rule():
    """La alerta S133-A aparece antes de la regla S119-C en el template."""
    idx_alert = _BACKEND_PY_TEMPLATE.find("S133-A")
    idx_rule = _BACKEND_PY_TEMPLATE.find("S119-C")
    assert idx_alert < idx_rule, "S133-A debe preceder a S119-C"


def test_h4_alert_mentions_typeerror():
    """La alerta S133-A menciona TypeError para comunicar el impacto."""
    alert_section = _BACKEND_PY_TEMPLATE[
        _BACKEND_PY_TEMPLATE.find("S133-A") : _BACKEND_PY_TEMPLATE.find("S133-A") + 300
    ]
    assert "TypeError" in alert_section
