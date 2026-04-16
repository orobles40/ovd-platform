"""
OVD Platform — Tests para BUG-04: security_audit fallback parser
Copyright 2026 Omar Robles

Verifica que _parse_security_fallback extrae correctamente los datos
del texto libre cuando invoke_structured falla con modelos pequeños.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import pytest

# Importar el fallback directamente del módulo
from graph import _parse_security_fallback, SecurityAuditOutput


class TestParseFallbackJSON:
    """El fallback encuentra y parsea JSON embebido en el texto del LLM."""

    def test_json_completo_embebido(self):
        raw = '''
        Aquí está mi análisis de seguridad:
        {"passed": true, "score": 85, "severity": "none",
         "vulnerabilities": [], "secrets_found": [], "insecure_patterns": [],
         "rls_compliant": true, "remediation": [],
         "summary": "Código seguro sin vulnerabilidades detectadas."}
        '''
        result = _parse_security_fallback(raw)
        assert result.score == 85
        assert result.passed is True
        assert result.severity == "none"

    def test_json_con_vulnerabilidades(self):
        raw = json.dumps({
            "passed": False, "score": 30, "severity": "high",
            "vulnerabilities": ["A03-Injection"],
            "secrets_found": ["API_KEY hardcoded"],
            "insecure_patterns": ["SQL concatenation"],
            "rls_compliant": False,
            "remediation": ["Use parameterized queries"],
            "summary": "SQL injection detectado.",
        })
        result = _parse_security_fallback(raw)
        assert result.score == 30
        assert result.passed is False
        assert result.severity == "high"
        assert len(result.vulnerabilities) == 1
        assert len(result.secrets_found) == 1

    def test_json_score_fuera_de_rango_clamp(self):
        """Scores > 100 se deben clampear a 100."""
        raw = '{"score": 150, "passed": true, "severity": "none", "summary": "ok"}'
        result = _parse_security_fallback(raw)
        assert result.score == 100

    def test_json_score_negativo(self):
        """Scores negativos no son capturados por el regex (no hay signo) →
        el fallback usa el neutro 75. La severidad 'critical' sí se detecta por keyword."""
        raw = '{"score": -10, "passed": false, "severity": "critical", "summary": "bad"}'
        result = _parse_security_fallback(raw)
        # El regex r'"?score"?\s*[=:]\s*(\d{1,3})' no captura negativos →
        # score queda en 75 (neutro), pero severity se detecta por keyword
        assert result.score == 75
        assert result.severity == "critical"
        assert result.passed is False


class TestParseFallbackRegex:
    """Cuando no hay JSON válido, el fallback extrae datos con regex."""

    def test_score_con_regex(self):
        raw = 'El análisis indica score: 78 de vulnerabilidades encontradas.'
        result = _parse_security_fallback(raw)
        assert result.score == 78

    def test_severity_high_desde_keyword(self):
        raw = 'Encontré una vulnerabilidad HIGH en el código de autenticación.'
        result = _parse_security_fallback(raw)
        assert result.severity == "high"
        assert result.passed is False

    def test_severity_critical_desde_keyword(self):
        raw = 'Error CRITICAL: inyección SQL detectada en todos los endpoints.'
        result = _parse_security_fallback(raw)
        assert result.severity == "critical"
        assert result.passed is False

    def test_severity_low_passed_true(self):
        raw = 'Solo encontré un issue LOW de logging incompleto. score: 90'
        result = _parse_security_fallback(raw)
        assert result.severity == "low"
        assert result.passed is True
        assert result.score == 90

    def test_sin_datos_retorna_neutro(self):
        """Sin datos útiles, retorna score neutro 75 (no 0)."""
        raw = 'No entendí la pregunta.'
        result = _parse_security_fallback(raw)
        assert result.score == 75
        assert result.passed is True
        assert result.severity == "none"

    def test_texto_vacio_retorna_neutro(self):
        result = _parse_security_fallback("")
        assert result.score == 75
        assert result.passed is True


class TestParseFallbackTipos:
    """Verifica que el resultado siempre sea SecurityAuditOutput válido."""

    def test_retorna_instancia_correcta(self):
        result = _parse_security_fallback("score: 60")
        assert isinstance(result, SecurityAuditOutput)

    def test_listas_siempre_son_listas(self):
        result = _parse_security_fallback("texto sin JSON")
        assert isinstance(result.vulnerabilities, list)
        assert isinstance(result.secrets_found, list)
        assert isinstance(result.insecure_patterns, list)
        assert isinstance(result.remediation, list)

    def test_summary_siempre_es_string(self):
        result = _parse_security_fallback("score: 80")
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    def test_score_0_sin_vulns_se_corrige_a_neutro(self):
        """
        BUG-04: score=0 + sin vulnerabilidades ni secrets = fallo de parsing del modelo.
        _parse_security_fallback corrige el score a 75 (neutro) en lugar de propagar 0.
        """
        raw = '{"score": 0, "passed": false, "severity": "high", "vulnerabilities": [], "summary": "?"}'
        result = _parse_security_fallback(raw)
        assert isinstance(result, SecurityAuditOutput)
        # score=0 sin vulns ni secrets → corregido a 75 (fallo de parsing del modelo)
        assert result.score == 75

    def test_score_0_con_vulns_se_respeta(self):
        """
        BUG-04: score=0 CON vulnerabilidades específicas = resultado legítimo (código crítico).
        El fallback NO debe sobreescribir el score en este caso.
        """
        raw = json.dumps({
            "passed": False, "score": 0, "severity": "critical",
            "vulnerabilities": ["A03-Injection", "A01-Broken Access Control"],
            "secrets_found": [], "insecure_patterns": ["SQL concatenation sin parametrizar"],
            "rls_compliant": False, "remediation": ["Usar queries parametrizadas"],
            "summary": "Código con vulnerabilidades críticas múltiples.",
        })
        result = _parse_security_fallback(raw)
        # Con vulnerabilidades específicas, score=0 es legítimo
        assert result.score == 0
        assert result.passed is False
        assert len(result.vulnerabilities) == 2

    def test_score_0_con_secrets_se_respeta(self):
        """score=0 con secrets_found también se respeta (es un hallazgo real)."""
        raw = json.dumps({
            "passed": False, "score": 0, "severity": "critical",
            "vulnerabilities": [], "secrets_found": ["AWS_SECRET_KEY hardcoded"],
            "insecure_patterns": [], "rls_compliant": True, "remediation": [],
            "summary": "Secret hardcodeado detectado.",
        })
        result = _parse_security_fallback(raw)
        assert result.score == 0
        assert result.secrets_found == ["AWS_SECRET_KEY hardcoded"]

    def test_regex_score_cero_se_corrige_a_neutro(self):
        """
        BUG-04: cuando el modelo escribe 'score: 0' en texto libre,
        el regex capturaba 0, ahora se corrige a 75.
        """
        raw = 'El código tiene un score: 0/100 de seguridad.'
        result = _parse_security_fallback(raw)
        # score=0 en texto libre = modelo no concluyente → corregido a 75
        assert result.score == 75


class TestRegressionBUG04:
    """Tests de regresión para el fix de BUG-04."""

    def test_fallback_no_bloquea_ciclo(self):
        """El fallback nunca lanza excepciones."""
        textos_problematicos = [
            "",
            "null",
            "undefined",
            "{malformed json",
            "score: abc",
            "100" * 1000,  # texto muy largo
        ]
        for texto in textos_problematicos:
            result = _parse_security_fallback(texto)
            assert isinstance(result, SecurityAuditOutput), f"Falló con: {texto[:50]}"

    def test_severidades_validas(self):
        """severity siempre debe ser uno de los valores válidos."""
        valid = {"none", "low", "medium", "high", "critical"}
        for texto in ["", "alto riesgo", "crítico", "low severity", "MEDIUM issue"]:
            result = _parse_security_fallback(texto)
            assert result.severity in valid, f"severity inválido '{result.severity}' para: {texto}"
