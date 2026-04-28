"""
OVD Platform — Tests S37: audit_logger bigint + RAG-02 ruta absoluta
S37-A: audit_logger INSERT no pasa id (bigint con sequence)
S37-B: _generate_delivery_report retorna ruta absoluta para RAG-02
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import inspect
import pathlib

import pytest

# ---------------------------------------------------------------------------
# S37-A — audit_logger INSERT omite columna id (bigint con sequence)
# ---------------------------------------------------------------------------


class TestS37AAuditLoggerBigint:
    """S37-A: el INSERT de audit_logger no incluye 'id' — lo genera la BD con nextval."""

    def _get_write_source(self) -> str:
        import audit_logger

        return inspect.getsource(audit_logger._write_audit_log)

    def test_insert_no_incluye_columna_id(self):
        """El INSERT no debe listar 'id' como columna explícita."""
        src = self._get_write_source()
        # La forma incorrecta sería: INSERT INTO ovd_audit_log (id, org_id, ...)
        assert "id, org_id" not in src, (
            "S37-A: INSERT incluye 'id' como columna — rompe el bigint sequence"
        )

    def test_insert_empieza_con_org_id(self):
        """El INSERT debe comenzar con org_id (primera columna sin id)."""
        src = self._get_write_source()
        assert "(org_id, user_id" in src, (
            "S37-A: INSERT no empieza con org_id — revisar columnas"
        )

    def test_no_genera_uuid_para_id(self):
        """No debe generarse un UUID para la columna id (era la causa del error bigint)."""
        src = self._get_write_source()
        # El UUID ahora no se usa para el INSERT
        # La función puede importar uuid para otros fines, pero no debe asignarlo al INSERT
        lines = [l.strip() for l in src.splitlines()]
        insert_section = False
        for line in lines:
            if "INSERT INTO" in line:
                insert_section = True
            if insert_section and "log_id" in line and "VALUES" in line:
                pytest.fail("S37-A: log_id (UUID) sigue siendo pasado en el INSERT")
            if insert_section and "await conn.commit()" in line:
                break

    def test_parametros_values_son_7(self):
        """El INSERT tiene 7 columnas y 7 valores (%s) sin id."""
        src = self._get_write_source()
        # Contar %s en la query — deben ser 7 (sin id)
        import re

        match = re.search(r"VALUES\s*\(([^)]+)\)", src)
        if match:
            placeholders = match.group(1).count("%s")
            assert placeholders == 7, (
                f"S37-A: INSERT tiene {placeholders} placeholders, esperados 7 (sin id)"
            )


# ---------------------------------------------------------------------------
# S37-B — _generate_delivery_report retorna ruta absoluta
# ---------------------------------------------------------------------------


class TestS37BDeliveryReportPath:
    """S37-B: _generate_delivery_report retorna ruta absoluta para que RAG-02 funcione."""

    def _get_func_source(self) -> str:
        import graph as g

        return inspect.getsource(g._generate_delivery_report)

    def test_retorna_str_report_path(self):
        """La función retorna str(report_path) no report_name."""
        src = self._get_func_source()
        assert "return str(report_path)" in src, (
            "S37-B: _generate_delivery_report no retorna str(report_path) — RAG-02 no encontrará el archivo"
        )

    def test_no_retorna_solo_report_name(self):
        """No debe retornar solo report_name (sería ruta relativa sin directorio)."""
        src = self._get_func_source()
        # Asegurar que "return report_name" no está (salvo en el except)
        lines = src.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == "return report_name":
                pytest.fail(
                    f"S37-B: línea {i + 1} retorna 'report_name' (relativo) — "
                    "debe ser 'return str(report_path)'"
                )

    def test_ruta_absoluta_en_tmpdir(self, tmp_path):
        """Verificación funcional: la ruta retornada existe como archivo absoluto."""
        import asyncio

        import graph as g

        # Simular un state mínimo
        state = {
            "session_id": "test-s37-session",
            "directory": str(tmp_path),
            "sdd": {"requirements": [], "tasks": []},
            "agent_results": [],
            "security_result": {
                "score": 100,
                "passed": True,
                "severity": "none",
                "vulnerabilities": [],
                "secrets_found": [],
                "insecure_patterns": [],
                "rls_compliant": True,
                "remediation": [],
                "summary": "ok",
            },
            "qa_result": {
                "score": 90,
                "passed": True,
                "issues": [],
                "sdd_compliance": True,
                "missing_requirements": [],
                "code_quality_issues": [],
                "summary": "ok",
            },
            "test_results": {"passed": True, "output": "1 passed", "runner": "pytest"},
            "generated_docs": [],
            "token_usage": {},
            "cycle_start_ts": 0.0,
        }

        result_path = g._generate_delivery_report(
            state, [], 0.0, "1m 0s", 0, 0, "ollama"
        )
        if result_path:
            p = pathlib.Path(result_path)
            assert p.is_absolute(), (
                f"S37-B: ruta retornada '{result_path}' no es absoluta"
            )
            assert p.exists(), f"S37-B: archivo '{result_path}' no existe en disco"
