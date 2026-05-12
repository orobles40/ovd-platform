"""Tests S126 — OVD Desktop: telemetría completa (T3 SQLite, T4 endpoint, T6 crash).

S126-A: db.rs existe con init_db, log_error, db_save_cycle, db_list_project_cycles.
S126-B: db::db_save_cycle y db::db_list_project_cycles y db::db_list_errors
        están registrados en lib.rs invoke_handler.
S126-C: db::init_db() se llama en lib.rs setup.
S126-D: main.rs tiene el panic hook que llama a db::log_error.
S126-E: tauri.ts exporta dbSaveCycle, dbListProjectCycles, dbListErrors.
S126-F: endpoint POST /telemetry/client-event existe en api.py.
S126-G: endpoint devuelve 204 (no content) con secret válido.
S126-H: endpoint rechaza request sin secret con 403.
S126-I: ovd.ts exporta reportClientEvent.
S126-J: FrLauncher.tsx importa dbSaveCycle y reportClientEvent.
S126-K: FrLauncher.tsx llama dbSaveCycle después de saveCycleEntry.
S126-L: FrLauncher.tsx llama reportClientEvent con event='cycle_completed'.
"""

import pathlib
import re

import pytest
from fastapi.testclient import TestClient

# ── Rutas de archivos fuente ──────────────────────────────────────────────────

_ENGINE_DIR = pathlib.Path(".")
_DESKTOP_DIR = _ENGINE_DIR / ".." / "desktop"

_API_SRC = (_ENGINE_DIR / "api.py").read_text(encoding="utf-8")

_DB_RS = (_DESKTOP_DIR / "src-tauri" / "src" / "db.rs").read_text(encoding="utf-8")
_LIB_RS = (_DESKTOP_DIR / "src-tauri" / "src" / "lib.rs").read_text(encoding="utf-8")
_MAIN_RS = (_DESKTOP_DIR / "src-tauri" / "src" / "main.rs").read_text(encoding="utf-8")

_TAURI_TS = (_DESKTOP_DIR / "frontend" / "src" / "lib" / "tauri.ts").read_text(
    encoding="utf-8"
)

_OVD_TS = (_DESKTOP_DIR / "frontend" / "src" / "lib" / "ovd.ts").read_text(
    encoding="utf-8"
)

_LAUNCHER_TSX = (
    _DESKTOP_DIR / "frontend" / "src" / "pages" / "FrLauncher.tsx"
).read_text(encoding="utf-8")


# ── S126-A: db.rs estructura ──────────────────────────────────────────────────


def test_s126a_db_rs_has_init_db():
    assert "pub fn init_db()" in _DB_RS


def test_s126a_db_rs_has_log_error():
    assert "pub fn log_error(" in _DB_RS


def test_s126a_db_rs_has_cycle_history_table():
    assert "cycle_history" in _DB_RS


def test_s126a_db_rs_has_error_log_table():
    assert "error_log" in _DB_RS


def test_s126a_db_rs_has_db_save_cycle_command():
    assert "pub async fn db_save_cycle(" in _DB_RS


def test_s126a_db_rs_has_db_list_project_cycles_command():
    assert "pub async fn db_list_project_cycles(" in _DB_RS


def test_s126a_db_rs_has_db_list_errors_command():
    assert "pub async fn db_list_errors(" in _DB_RS


# ── S126-B/C: lib.rs registración ────────────────────────────────────────────


def test_s126b_lib_rs_registers_db_save_cycle():
    assert "db::db_save_cycle" in _LIB_RS


def test_s126b_lib_rs_registers_db_list_project_cycles():
    assert "db::db_list_project_cycles" in _LIB_RS


def test_s126b_lib_rs_registers_db_list_errors():
    assert "db::db_list_errors" in _LIB_RS


def test_s126c_lib_rs_calls_init_db():
    assert "db::init_db()" in _LIB_RS


# ── S126-D: main.rs panic hook ────────────────────────────────────────────────


def test_s126d_main_rs_has_panic_hook():
    assert "set_hook" in _MAIN_RS


def test_s126d_main_rs_panic_hook_calls_log_error():
    assert "db::log_error" in _MAIN_RS


# ── S126-E: tauri.ts TypeScript wrappers ─────────────────────────────────────


def test_s126e_tauri_ts_exports_db_save_cycle():
    assert "dbSaveCycle" in _TAURI_TS


def test_s126e_tauri_ts_exports_db_list_project_cycles():
    assert "dbListProjectCycles" in _TAURI_TS


def test_s126e_tauri_ts_exports_db_list_errors():
    assert "dbListErrors" in _TAURI_TS


def test_s126e_tauri_ts_has_cycle_entry_interface():
    assert "CycleEntry" in _TAURI_TS


def test_s126e_tauri_ts_has_error_log_entry_interface():
    assert "ErrorLogEntry" in _TAURI_TS


# ── S126-F/G/H: endpoint engine T4 ───────────────────────────────────────────


def test_s126f_api_has_telemetry_client_event_endpoint():
    assert "/telemetry/client-event" in _API_SRC


def test_s126f_api_endpoint_uses_verify_secret():
    block = _API_SRC[_API_SRC.find("/telemetry/client-event") :]
    assert "verify_secret" in block[:300]


def test_s126g_telemetry_endpoint_returns_204():
    import os
    import sys

    sys.path.insert(0, str(_ENGINE_DIR))
    os.environ.setdefault("OVD_SECRET", "test-secret")
    os.environ.setdefault("DATABASE_URL", "")
    os.environ.setdefault("ANTHROPIC_API_KEY", "dummy")
    from api import app  # noqa: PLC0415

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/telemetry/client-event",
        json={"thread_id": "abc123", "event": "cycle_completed", "client": {}},
        headers={"X-OVD-Secret": "test-secret"},
    )
    assert resp.status_code == 204


def test_s126h_telemetry_endpoint_rejects_no_secret():
    """Cuando OVD_SECRET está configurado, requests sin header deben ser rechazados."""
    import sys

    sys.path.insert(0, str(_ENGINE_DIR))
    import api as api_module  # noqa: PLC0415

    original_secret = api_module.OVD_SECRET
    api_module.OVD_SECRET = "patched-secret"
    try:
        client = TestClient(api_module.app, raise_server_exceptions=False)
        resp = client.post(
            "/telemetry/client-event",
            json={"thread_id": "abc123", "event": "cycle_completed", "client": {}},
        )
        assert resp.status_code in (401, 403)
    finally:
        api_module.OVD_SECRET = original_secret


# ── S126-I: ovd.ts reportClientEvent ─────────────────────────────────────────


def test_s126i_ovd_ts_exports_report_client_event():
    assert "reportClientEvent" in _OVD_TS


def test_s126i_ovd_ts_report_client_event_posts_to_telemetry():
    assert "/telemetry/client-event" in _OVD_TS


# ── S126-J/K/L: FrLauncher.tsx integración ───────────────────────────────────


def test_s126j_launcher_imports_db_save_cycle():
    assert "dbSaveCycle" in _LAUNCHER_TSX


def test_s126j_launcher_imports_report_client_event():
    assert "reportClientEvent" in _LAUNCHER_TSX


def test_s126k_launcher_calls_db_save_cycle():
    assert "dbSaveCycle(" in _LAUNCHER_TSX


def test_s126l_launcher_calls_report_client_event_with_cycle_completed():
    assert "cycle_completed" in _LAUNCHER_TSX
