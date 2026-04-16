"""
PP-02 — Tests para heartbeat / stale session detection en task_checkout.py
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import task_checkout
from task_checkout import (
    register_session,
    unregister_session,
    detect_stale_sessions,
    list_stale_sessions,
    list_active_sessions,
)


def _clean():
    """Limpia el estado global entre tests."""
    task_checkout._active_sessions.clear()
    task_checkout._stale_sessions.clear()


# ---------------------------------------------------------------------------
# detect_stale_sessions — sesión reciente no es stale
# ---------------------------------------------------------------------------

def test_recent_session_not_stale():
    _clean()
    register_session("t-recent", {"org_id": "org1", "feature_request": "nueva feature"})
    stale = detect_stale_sessions(threshold_minutes=30)
    assert stale == []
    _clean()


# ---------------------------------------------------------------------------
# detect_stale_sessions — sesión antigua sí es stale
# ---------------------------------------------------------------------------

def test_old_session_detected_as_stale():
    _clean()
    old_time = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
    task_checkout._active_sessions["t-old"] = {
        "org_id": "org1",
        "feature_request": "feature vieja",
        "started_at": old_time,
    }
    stale = detect_stale_sessions(threshold_minutes=30)
    assert len(stale) == 1
    assert stale[0]["thread_id"] == "t-old"
    assert stale[0]["elapsed_minutes"] >= 44
    _clean()


# ---------------------------------------------------------------------------
# detect_stale_sessions — no duplica en detecciones repetidas
# ---------------------------------------------------------------------------

def test_stale_not_duplicated_on_repeat_calls():
    _clean()
    old_time = (datetime.now(timezone.utc) - timedelta(minutes=60)).isoformat()
    task_checkout._active_sessions["t-dup"] = {
        "org_id": "org1",
        "feature_request": "feat",
        "started_at": old_time,
    }
    first  = detect_stale_sessions(threshold_minutes=30)
    second = detect_stale_sessions(threshold_minutes=30)
    assert len(first)  == 1
    assert len(second) == 0   # ya estaba en _stale_sessions, no se re-detecta
    _clean()


# ---------------------------------------------------------------------------
# list_stale_sessions — filtra por org_id
# ---------------------------------------------------------------------------

def test_list_stale_filters_by_org():
    _clean()
    old_time = (datetime.now(timezone.utc) - timedelta(minutes=40)).isoformat()
    for tid, org in [("t-a", "orgA"), ("t-b", "orgB")]:
        task_checkout._active_sessions[tid] = {
            "org_id": org, "feature_request": "x", "started_at": old_time,
        }
    detect_stale_sessions(threshold_minutes=30)
    assert len(list_stale_sessions("orgA")) == 1
    assert list_stale_sessions("orgA")[0]["thread_id"] == "t-a"
    assert len(list_stale_sessions("orgB")) == 1
    assert len(list_stale_sessions()) == 2
    _clean()


# ---------------------------------------------------------------------------
# unregister_session — limpia tanto activas como stale
# ---------------------------------------------------------------------------

def test_unregister_clears_stale():
    _clean()
    old_time = (datetime.now(timezone.utc) - timedelta(minutes=50)).isoformat()
    task_checkout._active_sessions["t-fin"] = {
        "org_id": "org1", "feature_request": "x", "started_at": old_time,
    }
    detect_stale_sessions(threshold_minutes=30)
    assert len(list_stale_sessions()) == 1

    unregister_session("t-fin")
    assert len(list_active_sessions()) == 0
    assert len(list_stale_sessions())  == 0
    _clean()


# ---------------------------------------------------------------------------
# register_session — limpiar stale si la sesión se re-registra
# ---------------------------------------------------------------------------

def test_register_clears_stale_entry():
    _clean()
    old_time = (datetime.now(timezone.utc) - timedelta(minutes=50)).isoformat()
    task_checkout._active_sessions["t-restart"] = {
        "org_id": "org1", "feature_request": "x", "started_at": old_time,
    }
    detect_stale_sessions(threshold_minutes=30)
    assert "t-restart" in task_checkout._stale_sessions

    # Re-registrar (como si el ciclo se reiniciara)
    register_session("t-restart", {"org_id": "org1", "feature_request": "reiniciado"})
    assert "t-restart" not in task_checkout._stale_sessions
    _clean()


# ---------------------------------------------------------------------------
# detect_stale_sessions — sesión con started_at inválido no falla
# ---------------------------------------------------------------------------

def test_invalid_started_at_does_not_crash():
    _clean()
    task_checkout._active_sessions["t-bad"] = {
        "org_id": "org1", "feature_request": "x", "started_at": "not-a-date",
    }
    stale = detect_stale_sessions(threshold_minutes=1)
    assert stale == []  # ignorada silenciosamente
    _clean()
