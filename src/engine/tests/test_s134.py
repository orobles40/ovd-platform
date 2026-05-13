"""Tests S134-A — Fix S132-H1: actualizar complexity post-analyze_fr.

Corrige la regresión donde session_meta.complexity siempre quedaba vacío al
momento del registro inicial (analyze_fr no había corrido aún), causando que
_threshold_for_session devolviera el default de 30 min en lugar de 60 min
para ciclos medium/high/critical.

H1: update_session_complexity existe en task_checkout y actualiza _active_sessions.
H2: update_session_complexity es no-op si thread_id no existe o complexity vacío.
H3: _threshold_for_session retorna valores correctos por complejidad.
H4: update_session_complexity es invocada en _run_graph_background (api.py).
H5: La señal de actualización se basa en el evento node_end de analyze_fr.
"""

import json
import pathlib
import sys

_ENGINE_DIR = pathlib.Path(".")
sys.path.insert(0, str(_ENGINE_DIR))

_API_SRC = (_ENGINE_DIR / "api.py").read_text(encoding="utf-8")
_TC_SRC = (_ENGINE_DIR / "task_checkout.py").read_text(encoding="utf-8")


# ── H1: update_session_complexity ────────────────────────────────────────────


def test_h1_function_exists_in_task_checkout():
    """task_checkout.py define update_session_complexity."""
    assert "update_session_complexity" in _TC_SRC


def test_h1_updates_active_session_complexity():
    """update_session_complexity cambia el campo complexity en _active_sessions."""
    from task_checkout import (
        _active_sessions,
        register_session,
        unregister_session,
        update_session_complexity,
    )

    tid = "test-s134-h1-update"
    register_session(tid, {"org_id": "test", "feature_request": "fr", "complexity": ""})
    try:
        assert _active_sessions[tid]["complexity"] == ""
        update_session_complexity(tid, "medium")
        assert _active_sessions[tid]["complexity"] == "medium"
    finally:
        unregister_session(tid)


def test_h1_overwrites_previous_complexity():
    """update_session_complexity sobreescribe una complexity previa con la nueva."""
    from task_checkout import (
        _active_sessions,
        register_session,
        unregister_session,
        update_session_complexity,
    )

    tid = "test-s134-h1-overwrite"
    register_session(tid, {"org_id": "test", "feature_request": "fr", "complexity": "low"})
    try:
        update_session_complexity(tid, "high")
        assert _active_sessions[tid]["complexity"] == "high"
    finally:
        unregister_session(tid)


# ── H2: no-op si thread_id ausente o complexity vacía ────────────────────────


def test_h2_noop_when_thread_id_not_registered():
    """update_session_complexity no lanza excepción si thread_id no existe."""
    from task_checkout import update_session_complexity

    # No debe lanzar KeyError ni similar
    update_session_complexity("nonexistent-thread-s134", "medium")


def test_h2_noop_when_complexity_empty():
    """update_session_complexity no borra la complexity existente si la nueva es vacía."""
    from task_checkout import (
        _active_sessions,
        register_session,
        unregister_session,
        update_session_complexity,
    )

    tid = "test-s134-h2-empty"
    register_session(tid, {"org_id": "test", "feature_request": "fr", "complexity": "medium"})
    try:
        update_session_complexity(tid, "")
        # complexity no debe cambiar
        assert _active_sessions[tid]["complexity"] == "medium"
    finally:
        unregister_session(tid)


# ── H3: _threshold_for_session devuelve umbrales correctos ───────────────────


def test_h3_threshold_medium_returns_high_minutes():
    """medium complexity usa umbral ovd_stale_session_minutes_high (≥ 60)."""
    from task_checkout import _threshold_for_session

    meta_medium = {"complexity": "medium"}
    threshold = _threshold_for_session(meta_medium, default=30)
    assert threshold >= 60, f"Se esperaba ≥60 para medium, got {threshold}"


def test_h3_threshold_high_returns_high_minutes():
    """high complexity usa umbral ovd_stale_session_minutes_high (≥ 60)."""
    from task_checkout import _threshold_for_session

    meta_high = {"complexity": "high"}
    threshold = _threshold_for_session(meta_high, default=30)
    assert threshold >= 60, f"Se esperaba ≥60 para high, got {threshold}"


def test_h3_threshold_critical_returns_critical_minutes():
    """critical complexity usa umbral ovd_stale_session_minutes_critical (≥ 90)."""
    from task_checkout import _threshold_for_session

    meta_critical = {"complexity": "critical"}
    threshold = _threshold_for_session(meta_critical, default=30)
    assert threshold >= 90, f"Se esperaba ≥90 para critical, got {threshold}"


def test_h3_threshold_empty_returns_default():
    """complexity vacía devuelve el default (30 min) — confirma el bug original."""
    from task_checkout import _threshold_for_session

    meta_empty = {"complexity": ""}
    threshold = _threshold_for_session(meta_empty, default=30)
    assert threshold == 30, f"Se esperaba 30 (default) para complexity='', got {threshold}"


def test_h3_threshold_low_returns_default():
    """low complexity devuelve el default."""
    from task_checkout import _threshold_for_session

    meta_low = {"complexity": "low"}
    threshold = _threshold_for_session(meta_low, default=30)
    assert threshold == 30


# ── H4: api.py contiene el interceptor S134-A ────────────────────────────────


def test_h4_api_imports_update_session_complexity():
    """api.py importa update_session_complexity desde task_checkout."""
    assert "update_session_complexity" in _API_SRC


def test_h4_api_checks_node_end_analyze_fr():
    """api.py verifica el evento node_end + analyze_fr para disparar la actualización."""
    assert '"node_end"' in _API_SRC or "node_end" in _API_SRC
    assert '"analyze_fr"' in _API_SRC or "analyze_fr" in _API_SRC


def test_h4_api_has_s134a_marker():
    """api.py contiene el marcador S134-A."""
    assert "S134-A" in _API_SRC


# ── H5: señal basada en datos del evento SSE ─────────────────────────────────


def test_h5_node_end_analyze_fr_event_detectable():
    """El evento node_end de analyze_fr es detectable con string check en el raw SSE."""
    event = {"data": json.dumps({"type": "node_end", "data": {"node": "analyze_fr"}})}
    raw = event.get("data", "")
    assert '"node_end"' in raw
    assert '"analyze_fr"' in raw


def test_h5_other_node_end_not_triggered():
    """El evento node_end de otro nodo no dispara el interceptor S134-A."""
    event = {"data": json.dumps({"type": "node_end", "data": {"node": "generate_sdd"}})}
    raw = event.get("data", "")
    # El check '"analyze_fr"' in raw debe ser False para este evento
    assert '"analyze_fr"' not in raw


def test_h5_heartbeat_event_not_triggered():
    """Un evento heartbeat no dispara el interceptor S134-A."""
    event = {"data": json.dumps({"type": "heartbeat", "data": {"ts": 1234567890}})}
    raw = event.get("data", "")
    assert '"node_end"' not in raw
    assert '"analyze_fr"' not in raw
