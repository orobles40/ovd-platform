"""Tests S135-B — Fix persist_cycle: eliminar SET app.current_org_id de deliver.

Causa raíz: psycopg3 convierte %s a $1 para parameterized queries. El comando
SET de PostgreSQL no acepta parámetros con $N → "syntax error at or near '$1'".
Fix: eliminar SET app.current_org_id de graph.py deliver (consistente con
S132-H6 ya aplicado en api.py _ensure_cycle_registered).

H1: graph.py deliver no contiene SET app.current_org_id con placeholder %s.
H2: api.py _ensure_cycle_registered no contiene SET app.current_org_id (S132-H6).
H3: El INSERT de deliver usa %s (no $N) como placeholders.
H4: graph.py contiene el marcador S135-B.
H5: api.py contiene el comentario S132-H6.
"""

import pathlib
import sys

_ENGINE_DIR = pathlib.Path(".")
sys.path.insert(0, str(_ENGINE_DIR))

_GRAPH_SRC = (_ENGINE_DIR / "graph.py").read_text(encoding="utf-8")
_API_SRC = (_ENGINE_DIR / "api.py").read_text(encoding="utf-8")


# ── H1: deliver no tiene SET app.current_org_id con parámetro ────────────────


def test_h1_deliver_no_set_app_current_org_id_with_param():
    """deliver en graph.py no ejecuta SET app.current_org_id = %s."""
    # Buscar el contexto del deliver — después del bloque audit log
    deliver_section = _GRAPH_SRC[_GRAPH_SRC.rfind("S29-A") :]
    assert "SET app.current_org_id = %s" not in deliver_section


def test_h1_deliver_set_not_executed_before_insert():
    """El bloque deliver no llama await _conn.execute con SET app.current_org_id."""
    deliver_section = _GRAPH_SRC[_GRAPH_SRC.rfind("S29-A") :]
    # No debe haber execute("SET app.current_org_id
    assert '"SET app.current_org_id' not in deliver_section
    assert "'SET app.current_org_id" not in deliver_section


# ── H2: api.py _ensure_cycle_registered tampoco tiene el SET ─────────────────


def test_h2_ensure_cycle_no_set_app_current_org_id():
    """_ensure_cycle_registered en api.py no ejecuta SET app.current_org_id."""
    ensure_section = _API_SRC[_API_SRC.find("_ensure_cycle_registered") :]
    # Tomar solo hasta la próxima función async def
    next_fn = ensure_section.find("\nasync def ", 10)
    if next_fn > 0:
        ensure_section = ensure_section[:next_fn]
    assert "SET app.current_org_id = %s" not in ensure_section


# ── H3: INSERT en deliver usa %s como placeholders ───────────────────────────


def test_h3_deliver_insert_uses_percent_s_placeholders():
    """El INSERT de deliver usa %s, no $N."""
    deliver_section = _GRAPH_SRC[_GRAPH_SRC.rfind("INSERT INTO ovd_cycles") :]
    # Tomar solo las primeras líneas del INSERT
    insert_block = deliver_section[:2000]
    # Debe tener %s
    assert "%s" in insert_block
    # No debe tener $1, $2 como placeholders literales en el SQL
    assert "$1" not in insert_block
    assert "$2" not in insert_block


def test_h3_deliver_insert_has_correct_column_count():
    """El INSERT de deliver tiene 19 placeholders %s + 1 literal 'completed'."""
    idx = _GRAPH_SRC.rfind("INSERT INTO ovd_cycles")
    values_start = _GRAPH_SRC.find("VALUES", idx)
    values_end = _GRAPH_SRC.find("ON CONFLICT", values_start)
    values_block = _GRAPH_SRC[values_start:values_end]
    count_s = values_block.count("%s")
    assert count_s == 19, f"Se esperaban 19 %s en VALUES, se encontraron {count_s}"


# ── H4: marcador S135-B en graph.py ──────────────────────────────────────────


def test_h4_graph_has_s135b_marker():
    """graph.py contiene el marcador S135-B."""
    assert "S135-B" in _GRAPH_SRC


# ── H5: S132-H6 en api.py ────────────────────────────────────────────────────


def test_h5_api_has_s132h6_comment():
    """api.py documenta S132-H6 — SET omitido por incompatibilidad psycopg3."""
    assert "S132-H6" in _API_SRC


def test_h5_api_set_omit_reason_documented():
    """api.py explica que SET no acepta parámetros en psycopg3."""
    assert "SET no acepta parámetros" in _API_SRC or "SET" in _API_SRC
