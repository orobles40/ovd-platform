"""
OVD Platform — Tests S36: QA issues parsing + floating point instructions
S36-A: QAReviewOutput._coerce_list_fields — evita Issues: 1548 por str→chars
S36-B: system_backend.md — instrucción de verificar valores numéricos en tests
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ---------------------------------------------------------------------------
# S36-A — QAReviewOutput coerce str→list sin partir en caracteres
# ---------------------------------------------------------------------------

class TestS36AQAIssuesParsing:
    """S36-A: QAReviewOutput._coerce_list_fields convierte str a list correctamente."""

    def _get_qa_output_class(self):
        import graph as g
        return g.QAReviewOutput

    def test_issues_str_no_se_parte_en_chars(self):
        """Un str pasado a issues NO genera lista de caracteres (bug original: Issues: 1548)."""
        QAReviewOutput = self._get_qa_output_class()
        # Simular lo que ocurre cuando el LLM retorna issues como string
        issue_text = "El código no tiene manejo de errores adecuado"
        obj = QAReviewOutput(
            passed=False,
            score=65,
            issues=issue_text,
            sdd_compliance=True,
            missing_requirements=[],
            code_quality_issues=[],
            summary="Calidad baja",
        )
        # NO debe tener len == len(issue_text)
        assert len(obj.issues) != len(issue_text), \
            f"issues se partió en {len(obj.issues)} caracteres en vez de items"
        # Debe tener ≤ número de líneas del texto
        assert len(obj.issues) <= issue_text.count("\n") + 1

    def test_issues_str_multilinea_se_convierte_en_lista(self):
        """Un str multilinea se convierte en lista de items por línea."""
        QAReviewOutput = self._get_qa_output_class()
        issues_text = "- Falta manejo de errores\n- No hay tests\n- Falta documentación"
        obj = QAReviewOutput(
            passed=False,
            score=50,
            issues=issues_text,
            sdd_compliance=False,
            missing_requirements=[],
            code_quality_issues=[],
            summary="Calidad insuficiente",
        )
        assert len(obj.issues) == 3
        assert any("manejo de errores" in i for i in obj.issues)
        assert any("tests" in i for i in obj.issues)

    def test_issues_str_vacio_retorna_lista_vacia(self):
        """Un str vacío retorna [] sin lanzar error."""
        QAReviewOutput = self._get_qa_output_class()
        obj = QAReviewOutput(
            passed=True,
            score=90,
            issues="",
            sdd_compliance=True,
            missing_requirements="",
            code_quality_issues="",
            summary="Calidad aceptable",
        )
        assert obj.issues == []
        assert obj.missing_requirements == []
        assert obj.code_quality_issues == []

    def test_issues_lista_normal_no_se_altera(self):
        """Una list[str] válida pasa sin modificaciones."""
        QAReviewOutput = self._get_qa_output_class()
        issues_list = ["Issue A", "Issue B", "Issue C"]
        obj = QAReviewOutput(
            passed=False,
            score=70,
            issues=issues_list,
            sdd_compliance=True,
            missing_requirements=[],
            code_quality_issues=[],
            summary="Issues menores",
        )
        assert obj.issues == issues_list

    def test_issues_string_largo_no_da_miles_de_items(self):
        """Un string de 1548 chars NO produce 1548 items (regression del bug original)."""
        QAReviewOutput = self._get_qa_output_class()
        # Simular respuesta larga del LLM como string
        long_str = "x" * 1548
        obj = QAReviewOutput(
            passed=False,
            score=30,
            issues=long_str,
            sdd_compliance=False,
            missing_requirements=[],
            code_quality_issues=[],
            summary="Muchos issues",
        )
        assert len(obj.issues) < 100, \
            f"Bug S36-A: issues tiene {len(obj.issues)} items para un string de 1548 chars"

    def test_len_issues_log_correcto(self):
        """len(result.issues) en el log refleja número de issues reales, no chars."""
        QAReviewOutput = self._get_qa_output_class()
        # 3 issues en un string con bullets
        issues_text = "- Falta auth\n- SQL injection\n- Sin logging"
        obj = QAReviewOutput(
            passed=False,
            score=40,
            issues=issues_text,
            sdd_compliance=False,
            missing_requirements=[],
            code_quality_issues=[],
            summary="Crítico",
        )
        # El log haría f"Issues: {len(result.issues)}" → debe ser ≤ 10, no 100+
        assert len(obj.issues) <= 10, \
            f"Log mostraría 'Issues: {len(obj.issues)}' — debería ser ≤ 10"

    def test_missing_requirements_str_funciona(self):
        """missing_requirements también acepta str y lo convierte a list."""
        QAReviewOutput = self._get_qa_output_class()
        obj = QAReviewOutput(
            passed=False,
            score=60,
            issues=[],
            sdd_compliance=False,
            missing_requirements="- R1: Autenticación\n- R2: Rate limiting",
            code_quality_issues=[],
            summary="Faltan requisitos",
        )
        assert len(obj.missing_requirements) == 2
        assert any("R1" in r for r in obj.missing_requirements)


# ---------------------------------------------------------------------------
# S36-B — system_backend.md instrucción de valores numéricos en tests
# ---------------------------------------------------------------------------

class TestS36BFloatInstructions:
    """S36-B: system_backend.md incluye instrucción sobre valores float en tests."""

    def _get_template_content(self) -> str:
        import pathlib
        tmpl = pathlib.Path(__file__).parent.parent / "templates" / "system_backend.md"
        return tmpl.read_text(encoding="utf-8")

    def test_template_menciona_punto_flotante(self):
        """El template menciona el problema de punto flotante en tests."""
        content = self._get_template_content()
        assert "punto flotante" in content.lower() or "float" in content.lower(), \
            "system_backend.md no menciona el problema de valores float en tests"

    def test_template_menciona_round(self):
        """El template muestra el uso de round() para verificar valores."""
        content = self._get_template_content()
        assert "round(" in content, \
            "system_backend.md no muestra ejemplo con round()"

    def test_template_prohibe_valores_de_memoria(self):
        """El template prohíbe escribir valores numéricos de memoria."""
        content = self._get_template_content()
        assert "memoria" in content.lower() or "NUNCA" in content, \
            "system_backend.md no prohíbe valores numéricos de memoria"

    def test_template_incluye_ejemplo_verificacion(self):
        """El template incluye un ejemplo verificable de cálculo antes de escribir el test."""
        content = self._get_template_content()
        # Debe haber un bloque de código con Python de verificación
        assert "```python" in content or "```" in content, \
            "system_backend.md no incluye ejemplo de código para verificar valores"

    def test_float_verification_math(self):
        """El valor correcto de round(53.4 / 1.70**2, 2) es 18.48, no 18.49."""
        result = round(53.4 / 1.70**2, 2)
        assert result == 18.48, \
            f"El valor correcto es 18.48 pero obtenemos {result}"

    def test_float_rounding_precision(self):
        """Documenta que round() con distintos decimales da resultados distintos."""
        # El agente debe verificar con el mismo round() que usa su implementación
        raw = 53.4 / 1.70**2
        assert round(raw, 2) == 18.48
        assert round(raw, 1) == 18.5
        assert round(raw, 0) == 18.0
