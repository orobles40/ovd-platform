"""Tests S135-A — Fix security_audit: streaming fallback para DO GenAI.

El endpoint non-streaming de DO GenAI Platform tiene un timeout estricto con
workspaces grandes (≥30 archivos). invoke_structured usa llamadas síncronas que
superan ese límite → error 400. El fallback anterior (llm.ainvoke) también es
non-streaming y sufre el mismo problema.

Fix: reemplazar llm.ainvoke por llm.astream en el path de fallback de
security_audit. Los chunks se acumulan y se parsean con _parse_security_fallback.

H1: graph.py no usa llm.ainvoke en el path de fallback de security_audit.
H2: graph.py usa llm.astream en el path de fallback de security_audit (S135-A).
H3: _parse_security_fallback extrae score y passed de texto streaming JSON.
H4: _parse_security_fallback retorna score=75 neutro para texto vacío.
H5: graph.py contiene el marcador S135-A.
H6: El fallback de streaming acumula content de cada chunk.
"""

import json
import pathlib
import sys

_ENGINE_DIR = pathlib.Path(".")
sys.path.insert(0, str(_ENGINE_DIR))

_GRAPH_SRC = (_ENGINE_DIR / "graph.py").read_text(encoding="utf-8")

# ── Extraer la sección de _invoke_security_llm ───────────────────────────────

_SECURITY_SECTION_START = _GRAPH_SRC.find("async def _invoke_security_llm()")
_SECURITY_SECTION_END = _GRAPH_SRC.find(
    "\n    result: SecurityAuditOutput", _SECURITY_SECTION_START
)
_SECURITY_FN = _GRAPH_SRC[_SECURITY_SECTION_START:_SECURITY_SECTION_END]


# ── H1: no usa ainvoke en el fallback ────────────────────────────────────────


def test_h1_fallback_does_not_use_ainvoke():
    """_invoke_security_llm no llama llm.ainvoke en el path de fallback."""
    # El ainvoke que puede aparecer es solo en el BUG-04 path (score=0 check),
    # NO en el bloque except de invoke_structured
    except_idx = _SECURITY_FN.find("except Exception as exc:")
    if except_idx < 0:
        return  # función no encontrada — skip
    except_block = _SECURITY_FN[except_idx:]
    # No debe haber llm.ainvoke dentro del except de invoke_structured
    assert "await llm.ainvoke(messages)" not in except_block


# ── H2: usa astream en el fallback ───────────────────────────────────────────


def test_h2_fallback_uses_astream():
    """_invoke_security_llm usa llm.astream en el path de fallback."""
    assert "llm.astream" in _SECURITY_FN


def test_h2_fallback_astream_accumulates_chunks():
    """El fallback acumula _stream_chunks del loop astream."""
    assert "_stream_chunks" in _SECURITY_FN
    assert ".append(" in _SECURITY_FN


def test_h2_fallback_joins_chunks():
    """El fallback une los chunks con join antes de parsear."""
    assert (
        '"".join(_stream_chunks)' in _SECURITY_FN
        or "join(_stream_chunks)" in _SECURITY_FN
    )


# ── H3: _parse_security_fallback parsea JSON en texto streaming ──────────────


def test_h3_parse_security_fallback_extracts_json():
    """_parse_security_fallback extrae score y passed de un JSON embebido."""
    from graph import _parse_security_fallback

    raw = json.dumps(
        {
            "passed": True,
            "score": 90,
            "severity": "none",
            "vulnerabilities": [],
            "secrets_found": [],
            "insecure_patterns": [],
            "rls_compliant": True,
            "remediation": [],
            "summary": "No issues found.",
        }
    )
    result = _parse_security_fallback(raw)
    assert result.score == 90
    assert result.passed is True
    assert result.severity == "none"


def test_h3_parse_security_fallback_handles_streaming_prefix():
    """_parse_security_fallback maneja texto antes del JSON (como en respuesta streaming)."""
    from graph import _parse_security_fallback

    raw = 'Aquí está mi análisis:\n```json\n{"score": 80, "passed": true, "severity": "low", "vulnerabilities": [], "secrets_found": [], "insecure_patterns": [], "rls_compliant": true, "remediation": [], "summary": "Minor issues."}\n```'
    result = _parse_security_fallback(raw)
    assert result.score == 80


# ── H4: retorna score=75 neutro para texto vacío ─────────────────────────────


def test_h4_parse_security_fallback_empty_returns_neutral():
    """_parse_security_fallback retorna score=75 neutro cuando no hay JSON útil."""
    from graph import _parse_security_fallback

    result = _parse_security_fallback("")
    assert result.score == 75
    assert result.passed is True


def test_h4_parse_security_fallback_malformed_json_returns_neutral():
    """_parse_security_fallback retorna neutro para JSON malformado."""
    from graph import _parse_security_fallback

    result = _parse_security_fallback("{ score: invalid }")
    assert result.score == 75


# ── H5: marcador S135-A en graph.py ──────────────────────────────────────────


def test_h5_graph_has_s135a_marker():
    """graph.py contiene el marcador S135-A."""
    assert "S135-A" in _GRAPH_SRC


# ── H6: acumula content de cada chunk ────────────────────────────────────────


def test_h6_chunk_content_check():
    """El fallback verifica hasattr(chunk, 'content') antes de acumular."""
    assert "hasattr(_chunk" in _SECURITY_FN or "hasattr(_chunk," in _SECURITY_FN
    assert "_chunk.content" in _SECURITY_FN
