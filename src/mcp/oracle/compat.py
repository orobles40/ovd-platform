"""
OVD Platform — Oracle SQL compatibility validator
Copyright 2026 Omar Robles

Valida si una query SQL es compatible con la version Oracle de cada sede.
CAS = Oracle 12c (no soporta features 19c)
CAT, CAV = Oracle 19c (compatibilidad completa)
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Features de Oracle 19c NO disponibles en 12c
# ---------------------------------------------------------------------------

ORACLE_19C_ONLY: list[tuple[str, str]] = [
    # (patron regex, descripcion)
    (r"\bJSON_OBJECT\s*\(", "JSON_OBJECT() — Oracle 19c only"),
    (r"\bJSON_ARRAY\s*\(", "JSON_ARRAY() — Oracle 19c only"),
    (r"\bJSON_ARRAYAGG\s*\(", "JSON_ARRAYAGG() — Oracle 19c only"),
    (r"\bJSON_OBJECTAGG\s*\(", "JSON_OBJECTAGG() — Oracle 19c only"),
    (r"\bAPPROXIMATE\b", "APPROXIMATE COUNT — Oracle 19c only"),
    (r"\bMATCH_RECOGNIZE\b", "MATCH_RECOGNIZE — Oracle 19c only"),
    (r"\bLISTAGG\s*\(.*\)\s*WITHIN\s+GROUP\s*\(.*\)\s*OVER\b", "LISTAGG with OVER — Oracle 19c only"),
    (r"\bGROUP\s+BY\s+\(\s*\)", "GROUP BY () — Oracle 19c only"),
    (r"\bFETCH\s+FIRST\b.*\bROWS\s+ONLY\b.*\bWITH\s+TIES\b", "FETCH WITH TIES — Oracle 19c only"),
    (r"\bVECTOR\b", "VECTOR type — Oracle 23ai only"),
]

# Patrones que son advertencias (funciona pero comportamiento puede diferir)
ORACLE_19C_WARNINGS: list[tuple[str, str]] = [
    (r"\bJSON_VALUE\s*\(", "JSON_VALUE existe en 12c pero con sintaxis limitada"),
    (r"\bJSON_TABLE\s*\(", "JSON_TABLE existe en 12c pero con menos opciones"),
    (r"\bLISTAGG\s*\(.*OVERFLOW", "LISTAGG OVERFLOW clause — Oracle 19c feature"),
]


@dataclass
class CompatResult:
    valid: bool
    issues: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    target_version: str = ""


def validate(sql: str, target_sede: str) -> CompatResult:
    """
    Valida compatibilidad de una query SQL con la sede objetivo.

    CAS → Oracle 12c (mas restrictivo)
    CAT, CAV → Oracle 19c (permisivo)
    """
    sede = target_sede.upper()
    if sede not in ("CAS", "CAT", "CAV"):
        return CompatResult(valid=False, issues=[{"message": f"Sede invalida: {target_sede}. Usar CAS, CAT o CAV"}])

    # Oracle 19c acepta todo lo que Oracle 12c acepta y mas
    if sede in ("CAT", "CAV"):
        return CompatResult(valid=True, target_version="Oracle 19c")

    # Validar para Oracle 12c (CAS)
    issues = []
    warnings = []
    sql_upper = sql.upper()

    for pattern, description in ORACLE_19C_ONLY:
        if re.search(pattern, sql_upper, re.IGNORECASE | re.DOTALL):
            issues.append({
                "severity": "error",
                "message": description,
                "suggestion": "Reescribir usando sintaxis Oracle 12c compatible",
            })

    for pattern, description in ORACLE_19C_WARNINGS:
        if re.search(pattern, sql_upper, re.IGNORECASE | re.DOTALL):
            warnings.append({
                "severity": "warning",
                "message": description,
            })

    return CompatResult(
        valid=len(issues) == 0,
        issues=issues,
        warnings=warnings,
        target_version="Oracle 12c",
    )
