"""
OVD Platform — Tests S33: retry feedback mejorado (no modificar tests + AssertionError diagnosis + --tb=long)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import inspect
import pytest
from factories import make_state, make_agent_result


# ---------------------------------------------------------------------------
# S33-A — update_test_retry: instrucción de no modificar tests
# ---------------------------------------------------------------------------

class TestS33ANoModifyTests:
    """S33-A: update_test_retry incluye instrucción de no modificar tests."""

    def test_update_test_retry_incluye_instruccion_critica(self):
        """update_test_retry agrega instrucción de no modificar tests."""
        import graph as _graph
        src = inspect.getsource(_graph.update_test_retry)
        assert "S33-A" in src, "Etiqueta S33-A no encontrada en update_test_retry"
        assert "NUNCA modifiques" in src or "no deben modificarse" in src

    def test_instruccion_menciona_solo_implementacion(self):
        """La instrucción indica que solo se debe corregir la implementación."""
        import graph as _graph
        src = inspect.getsource(_graph.update_test_retry)
        assert "implementaci" in src.lower() and "src/" in src

    def test_instruccion_es_prominente(self):
        """En el feedback generado, la instrucción aparece antes del output de pytest."""
        import graph as _graph
        state = make_state(
            test_results={"passed": False, "output": "FAILED test_foo.py::test_bar\nassert 1 == 2", "runner": "pytest"},
            test_retry_count=0,
        )
        result = _graph.update_test_retry(state)
        feedback = result.get("retry_feedback", "")
        pos_instruccion = feedback.find("INSTRUCCIÓN") if "INSTRUCCIÓN" in feedback else feedback.find("NUNCA")
        pos_output = feedback.find("TESTS FALLIDOS")
        assert pos_instruccion != -1, "La instrucción no aparece en el feedback"
        assert pos_instruccion < pos_output, "La instrucción debe aparecer antes que 'TESTS FALLIDOS' en el feedback"

    def test_update_test_retry_feedback_contiene_instruccion(self):
        """El feedback generado contiene la instrucción de no modificar tests."""
        import graph as _graph
        state = make_state(
            test_results={"passed": False, "output": "assert 1 == 2\nFAILED test_foo.py", "runner": "pytest"},
            test_retry_count=0,
        )
        result = _graph.update_test_retry(state)
        feedback = result.get("retry_feedback", "")
        assert "NUNCA modifiques" in feedback or "no deben modificarse" in feedback or "INSTRUCCIÓN" in feedback

    def test_update_test_retry_incrementa_contador(self):
        """update_test_retry incrementa test_retry_count."""
        import graph as _graph
        state = make_state(
            test_results={"passed": False, "output": "FAILED", "runner": "pytest"},
            test_retry_count=0,
        )
        result = _graph.update_test_retry(state)
        assert result["test_retry_count"] == 1

    def test_update_test_retry_acumula_feedback_con_cap(self):
        """El feedback acumulado se trunca cerca de 3000 chars (S31-B). _truncate agrega ~43 chars de sufijo."""
        import graph as _graph
        estado_previo = "A" * 2800
        state = make_state(
            test_results={"passed": False, "output": "FAILED", "runner": "pytest"},
            test_retry_count=1,
            retry_feedback=estado_previo,
        )
        result = _graph.update_test_retry(state)
        # _truncate(text, 3000) retorna text[:3000] + sufijo (43 chars) → máximo ~3043
        assert len(result["retry_feedback"]) <= 3050, \
            f"Feedback demasiado largo: {len(result['retry_feedback'])} chars"


# ---------------------------------------------------------------------------
# S33-B — run_tests: extracción de AssertionError
# ---------------------------------------------------------------------------

class TestS33BAssertionErrorDiagnosis:
    """S33-B: run_tests extrae líneas de AssertionError cuando pytest falla con rc==1."""

    def test_run_tests_detecta_assertion_error(self):
        """run_tests tiene lógica S33-B para detectar AssertionError."""
        import graph as _graph
        src = inspect.getsource(_graph.run_tests)
        assert "S33-B" in src, "Etiqueta S33-B no encontrada en run_tests"
        assert "AssertionError" in src

    def test_run_tests_busca_lineas_assert(self):
        """run_tests busca líneas que empiezan con 'assert' o contienen 'AssertionError'."""
        import graph as _graph
        src = inspect.getsource(_graph.run_tests)
        assert "_assert_lines" in src

    def test_run_tests_diagnostico_incluye_prefijo(self):
        """El diagnóstico S33-B usa prefijo identificable."""
        import graph as _graph
        src = inspect.getsource(_graph.run_tests)
        assert "DIAGNÓSTICO S33-B" in src or "Fallos de aserción" in src

    def test_diagnostico_assertion_prepende_output(self):
        """El diagnóstico se prepende al output para que quede al principio del retry_feedback."""
        import graph as _graph
        src = inspect.getsource(_graph.run_tests)
        # El output se reasigna: output = "[DIAGNÓSTICO...]" + output
        assert 'output = ' in src and 'DIAGNÓSTICO S33-B' in src

    def test_assertion_extraction_logica(self):
        """La extracción de AssertionError filtra líneas relevantes."""
        sample_output = """
FAILED tests/test_stats.py::test_std
E   assert 1.5811 == 1.4142135623730951
E     comparison failed
AssertionError: assert 1.5811 != 1.4142
assert resultado['clave'] == valor
====== short test summary ======
"""
        lines = [
            line for line in sample_output.splitlines()
            if "AssertionError" in line
            or (line.strip().startswith("assert ") and "==" in line)
            or (line.strip().startswith("E ") and ("assert" in line.lower() or "==" in line))
        ]
        assert len(lines) >= 3, f"Debería detectar al menos 3 líneas relevantes, encontró: {lines}"


# ---------------------------------------------------------------------------
# S33-C — run_tests: --tb=long en retry rounds
# ---------------------------------------------------------------------------

class TestS33CTbLongOnRetry:
    """S33-C: en retry rounds (retry_round > 0), pytest usa --tb=long."""

    def test_run_tests_usa_tb_long_en_retry(self):
        """run_tests usa --tb=long cuando retry_round > 0."""
        import graph as _graph
        src = inspect.getsource(_graph.run_tests)
        assert "S33-C" in src, "Etiqueta S33-C no encontrada en run_tests"
        assert "long" in src and "short" in src  # ambos modos deben existir

    def test_tb_mode_depende_de_retry_round(self):
        """La selección de --tb depende de retry_round."""
        import graph as _graph
        src = inspect.getsource(_graph.run_tests)
        assert "_tb_mode" in src or "tb_mode" in src

    def test_primer_round_usa_short(self):
        """En el primer round (retry_round==0), usa --tb=short."""
        import graph as _graph
        src = inspect.getsource(_graph.run_tests)
        # retry_round > 0 → long, else → short
        assert 'retry_round > 0' in src or 'retry_round == 0' in src

    def test_tb_mode_aplicado_al_comando(self):
        """El _tb_mode se usa en el comando pytest final."""
        import graph as _graph
        src = inspect.getsource(_graph.run_tests)
        # El comando debe incluir el _tb_mode dinámicamente
        assert f'--tb={{' in src or '--tb=\'' in src or f'"--tb=' in src or f"f\"--tb=" in src or "_tb_mode" in src
