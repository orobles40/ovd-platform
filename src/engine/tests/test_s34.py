"""
OVD Platform — Tests S34: detección de error repetido + extracción de bloque de test fallido
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import inspect

import pytest
from factories import make_state

# ---------------------------------------------------------------------------
# Helpers bajo test
# ---------------------------------------------------------------------------


def _get_graph():
    import graph as _graph

    return _graph


# ---------------------------------------------------------------------------
# S34-A — Detección de error repetido
# ---------------------------------------------------------------------------


class TestS34ARepeatDetection:
    """S34-A: update_test_retry detecta cuando el mismo AssertionError se repite."""

    def test_extract_assert_errors_existe(self):
        """_extract_assert_errors es una función accesible en graph."""
        g = _get_graph()
        assert hasattr(g, "_extract_assert_errors"), (
            "_extract_assert_errors no encontrada en graph"
        )

    def test_extract_assert_errors_detecta_linea_E(self):
        """Detecta líneas que empiezan con 'E ' y contienen assert o ==."""
        g = _get_graph()
        output = "E   assert 951.34 == 32.0\nE   AssertionError\nsome other line"
        result = g._extract_assert_errors(output)
        assert len(result) >= 2
        assert any("951.34" in e for e in result)

    def test_extract_assert_errors_detecta_assertion_error(self):
        """Detecta líneas con 'AssertionError'."""
        g = _get_graph()
        output = "AssertionError: assert 1 != 2\nnormal line\nE   assert x == y"
        result = g._extract_assert_errors(output)
        assert any("AssertionError" in e for e in result)

    def test_extract_assert_errors_ignora_lineas_normales(self):
        """No incluye líneas sin AssertionError ni assert."""
        g = _get_graph()
        output = "PASSED test_foo\ncollected 5 items\n1 passed in 0.1s"
        result = g._extract_assert_errors(output)
        assert len(result) == 0

    def test_update_test_retry_detecta_error_repetido(self):
        """Cuando el mismo error aparece en existing y en test_output, agrega hint S34-A."""
        g = _get_graph()
        assert_line = "E   assert 951.34 == 32.0"
        state = make_state(
            test_results={
                "passed": False,
                "output": f"FAILED\n{assert_line}\n1 failed",
                "runner": "pytest",
            },
            test_retry_count=1,
            # existing ya contiene el mismo error del round anterior
            retry_feedback=f"TESTS FALLIDOS (ronda 1/2)\n{assert_line}\nOutput anterior",
        )
        result = g.update_test_retry(state)
        feedback = result["retry_feedback"]
        assert "S34-A" in feedback or "MISMO ERROR" in feedback, (
            "S34-A no detectó el error repetido"
        )
        assert "951.34" in feedback

    def test_update_test_retry_no_falso_positivo_sin_repeticion(self):
        """No agrega hint S34-A cuando el error NO se repite."""
        g = _get_graph()
        state = make_state(
            test_results={
                "passed": False,
                "output": "E   assert 5 == 10\n1 failed",
                "runner": "pytest",
            },
            test_retry_count=1,
            retry_feedback="TESTS FALLIDOS (ronda 1/2)\nE   assert 100 == 200\noutput anterior",
        )
        result = g.update_test_retry(state)
        feedback = result["retry_feedback"]
        # Si los errores son distintos (5==10 vs 100==200), no debe haber hint de repetición
        assert "MISMO ERROR POR SEGUNDA VEZ" not in feedback

    def test_update_test_retry_sin_existing_no_hint_repeticion(self):
        """En el primer retry (sin existing), nunca hay hint de repetición."""
        g = _get_graph()
        state = make_state(
            test_results={
                "passed": False,
                "output": "E   assert 1 == 2\n1 failed",
                "runner": "pytest",
            },
            test_retry_count=0,
            retry_feedback="",
        )
        result = g.update_test_retry(state)
        feedback = result["retry_feedback"]
        assert "MISMO ERROR POR SEGUNDA VEZ" not in feedback

    def test_hint_repeticion_incluye_solucion(self):
        """El hint de S34-A incluye instrucción de revisar fórmula."""
        g = _get_graph()
        assert_line = "E   assert 951.34 == 32.0"
        state = make_state(
            test_results={
                "passed": False,
                "output": f"FAILED\n{assert_line}",
                "runner": "pytest",
            },
            test_retry_count=1,
            retry_feedback=f"Round 1\n{assert_line}",
        )
        result = g.update_test_retry(state)
        feedback = result["retry_feedback"]
        if "MISMO ERROR" in feedback:
            assert (
                "fórmula" in feedback.lower()
                or "lógica" in feedback.lower()
                or "implementación" in feedback.lower()
            )


# ---------------------------------------------------------------------------
# S34-B — Extracción de bloque de test fallido
# ---------------------------------------------------------------------------


class TestS34BFailedTestBlock:
    """S34-B: extrae el bloque FAILED con nombre de test y línea de aserción."""

    def test_extract_failed_test_blocks_existe(self):
        """_extract_failed_test_blocks es accesible en graph."""
        g = _get_graph()
        assert hasattr(g, "_extract_failed_test_blocks")

    def test_extrae_bloque_failed(self):
        """Extrae el bloque que empieza con FAILED."""
        g = _get_graph()
        output = """
FAILED tests/test_temp.py::test_celsius_to_fahrenheit
    def test_celsius_to_fahrenheit():
        result = convertir_temperatura(0, 'C', 'F')
E       assert 951.34 == 32.0
PASSED tests/test_temp.py::test_kelvin_valid
"""
        result = g._extract_failed_test_blocks(output)
        assert "test_celsius_to_fahrenheit" in result
        assert "951.34" in result

    def test_extrae_maximo_3_bloques(self):
        """No extrae más de 3 bloques aunque haya más fallos."""
        g = _get_graph()
        # Generar 5 bloques FAILED
        blocks = "\n".join(
            [
                f"FAILED tests/test_foo.py::test_{i}\n    def test_{i}():\nE       assert {i} == 0"
                for i in range(5)
            ]
        )
        result = g._extract_failed_test_blocks(blocks)
        # Máximo 3 bloques
        count = result.count("FAILED")
        assert count <= 3

    def test_retorna_vacio_si_no_hay_bloques(self):
        """Retorna string vacío si no hay bloques FAILED."""
        g = _get_graph()
        output = "1 passed in 0.1s\nall good"
        result = g._extract_failed_test_blocks(output)
        assert result == ""

    def test_bloque_aparece_en_feedback(self):
        """El bloque del test fallido aparece en el feedback de update_test_retry."""
        g = _get_graph()
        output = (
            "FAILED tests/test_temp.py::test_c_to_f\n"
            "    def test_c_to_f():\n"
            "        result = convertir(0, 'C', 'F')\n"
            "E       assert 951.34 == 32.0\n"
            "1 failed in 0.1s"
        )
        state = make_state(
            test_results={"passed": False, "output": output, "runner": "pytest"},
            test_retry_count=0,
            retry_feedback="",
        )
        result = g.update_test_retry(state)
        feedback = result["retry_feedback"]
        # El bloque del test fallido o su información debe estar en el feedback
        assert "test_c_to_f" in feedback or "951.34" in feedback or "Bloque" in feedback

    def test_feedback_tiene_seccion_bloque(self):
        """El feedback incluye sección 'Bloque(s) del test fallido' cuando hay bloques."""
        g = _get_graph()
        output = "FAILED tests/test_x.py::test_suma\n    def test_suma():\nE       assert 10 == 5\n1 failed"
        state = make_state(
            test_results={"passed": False, "output": output, "runner": "pytest"},
            test_retry_count=0,
            retry_feedback="",
        )
        result = g.update_test_retry(state)
        feedback = result["retry_feedback"]
        assert "Bloque" in feedback or "test_suma" in feedback
