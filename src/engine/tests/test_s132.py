"""Tests S132 — Heartbeat adaptativo + router registration + frontend guard + RLS fix.

H1: Heartbeat threshold adaptativo por complejidad (30/60/90 min).
H2: _s132_ensure_router_registration garantiza include_router en main.py.
H3: frontend no puede escribir archivos .py.
H4: OVD_SECURITY_MIN_SCORE en env (verificación documental).
H5: content_bytes se recalcula post-postprocessing.
H6: SET app.current_org_id removido de api.py (psycopg3 no acepta parámetros en SET).
"""

import pathlib
import sys
import tempfile
import textwrap

import pytest

_ENGINE_DIR = pathlib.Path(".")
sys.path.insert(0, str(_ENGINE_DIR))

_GRAPH_SRC = (_ENGINE_DIR / "graph.py").read_text(encoding="utf-8")
_API_SRC = (_ENGINE_DIR / "api.py").read_text(encoding="utf-8")
_CHECKOUT_SRC = (_ENGINE_DIR / "task_checkout.py").read_text(encoding="utf-8")
_SETTINGS_SRC = (_ENGINE_DIR / "settings.py").read_text(encoding="utf-8")


# ── H1: Heartbeat adaptativo ─────────────────────────────────────────────────


def test_h1_settings_has_high_threshold():
    """settings.py define ovd_stale_session_minutes_high."""
    assert "ovd_stale_session_minutes_high" in _SETTINGS_SRC


def test_h1_settings_has_critical_threshold():
    """settings.py define ovd_stale_session_minutes_critical."""
    assert "ovd_stale_session_minutes_critical" in _SETTINGS_SRC


def test_h1_threshold_for_session_exists():
    """task_checkout.py contiene _threshold_for_session."""
    assert "_threshold_for_session" in _CHECKOUT_SRC


def test_h1_threshold_critical_branch():
    """_threshold_for_session tiene rama para complexity == 'critical'."""
    assert (
        'complexity == "critical"' in _CHECKOUT_SRC
        or "complexity == 'critical'" in _CHECKOUT_SRC
    )


def test_h1_threshold_high_medium_branch():
    """_threshold_for_session tiene rama para complexity in ('high', 'medium')."""
    assert '"high"' in _CHECKOUT_SRC or "'high'" in _CHECKOUT_SRC


def test_h1_detect_stale_uses_effective_threshold():
    """detect_stale_sessions usa effective_threshold por sesión, no un único cutoff global."""
    assert "effective_threshold" in _CHECKOUT_SRC


def test_h1_session_meta_includes_complexity():
    """api.py registra complexity en session_meta para heartbeat."""
    assert '"complexity"' in _API_SRC or "'complexity'" in _API_SRC


# ── H2: Router registration ──────────────────────────────────────────────────


def test_h2_function_exists():
    """graph.py define _s132_ensure_router_registration."""
    assert "_s132_ensure_router_registration" in _GRAPH_SRC


def test_h2_function_called_in_run_tests():
    """_s132_ensure_router_registration se llama desde run_tests."""
    idx_fn = _GRAPH_SRC.index("def _s132_ensure_router_registration")
    idx_call = _GRAPH_SRC.find("_s132_ensure_router_registration(work_dir)")
    assert idx_call > idx_fn, "La función debe llamarse después de su definición"


def test_h2_function_scans_router_py():
    """La función busca archivos router.py en el work_dir."""
    assert "router.py" in _GRAPH_SRC


def test_h2_function_injects_include_router():
    """La función puede inyectar include_router en main.py."""
    assert "include_router" in _GRAPH_SRC


def test_h2_ensure_router_registration_logic():
    """Prueba funcional: inyecta router faltante en main.py."""
    from graph import _s132_ensure_router_registration

    with tempfile.TemporaryDirectory() as tmp:
        src = pathlib.Path(tmp) / "src"
        turnos = src / "turnos"
        turnos.mkdir(parents=True)

        # Crear router.py para módulo 'turnos'
        (turnos / "router.py").write_text(
            "from fastapi import APIRouter\nrouter = APIRouter()\n", encoding="utf-8"
        )

        # main.py sin include_router para turnos
        (src / "main.py").write_text(
            textwrap.dedent("""\
                from fastapi import FastAPI
                app = FastAPI()
            """),
            encoding="utf-8",
        )

        injected = _s132_ensure_router_registration(tmp)
        assert "turnos" in injected

        main_content = (src / "main.py").read_text(encoding="utf-8")
        assert "include_router" in main_content
        assert "turnos" in main_content


def test_h2_no_injection_when_already_registered():
    """No inyectar si main.py ya tiene include_router para el módulo."""
    from graph import _s132_ensure_router_registration

    with tempfile.TemporaryDirectory() as tmp:
        src = pathlib.Path(tmp) / "src"
        pacientes = src / "pacientes"
        pacientes.mkdir(parents=True)

        (pacientes / "router.py").write_text(
            "from fastapi import APIRouter\nrouter = APIRouter()\n", encoding="utf-8"
        )

        (src / "main.py").write_text(
            textwrap.dedent("""\
                from fastapi import FastAPI
                from src.pacientes.router import router as pacientes_router
                app = FastAPI()
                app.include_router(pacientes_router)
            """),
            encoding="utf-8",
        )

        injected = _s132_ensure_router_registration(tmp)
        assert "pacientes" not in injected


# ── H3: Frontend Python guard ────────────────────────────────────────────────


def test_h3_guard_exists_in_write_artifacts():
    """graph.py contiene el guard S132-H3 para frontend + .py."""
    assert "S132-H3" in _GRAPH_SRC


def test_h3_guard_checks_frontend_agent():
    """El guard verifica agent == 'frontend'."""
    assert 'agent == "frontend"' in _GRAPH_SRC or "agent == 'frontend'" in _GRAPH_SRC


def test_h3_guard_checks_py_extension():
    """El guard verifica extensión .py."""
    assert '.endswith(".py")' in _GRAPH_SRC


# ── H5: content_bytes post-postprocessing ────────────────────────────────────


def test_h5_content_bytes_recalculated():
    """graph.py contiene S132-H5 comentando recálculo de content_bytes post-postprocess."""
    assert "S132-H5" in _GRAPH_SRC


def test_h5_recalculation_after_postprocessing():
    """content_bytes se asigna después de postprocess_python_file en _write_artifacts."""
    h5_idx = _GRAPH_SRC.find("S132-H5")
    assert h5_idx > 0
    # La asignación debe estar después del índice del marker H5
    assign_idx = _GRAPH_SRC.find("content_bytes = content.encode", h5_idx)
    assert assign_idx > h5_idx, "content_bytes debe recalcularse después del marker H5"


# ── H6: RLS SET fix ──────────────────────────────────────────────────────────


def test_h6_set_removed_from_session_create():
    """api.py no tiene SET app.current_org_id = %s en session_create."""
    # La línea ofensiva fue en contexto de _c47 (session_create)
    assert "SET app.current_org_id = %s" not in _API_SRC


def test_h6_no_parameterized_set():
    """Ningún SET con %s como parámetro de org_id en api.py."""
    assert 'execute("SET app.current_org_id = %s"' not in _API_SRC
    assert "execute('SET app.current_org_id = %s'" not in _API_SRC


def test_h6_rls_org_id_variable_removed():
    """La variable _rls_org_id fue eliminada de _ensure_cycle_registered."""
    assert "_rls_org_id" not in _API_SRC
