"""
OVD Platform — Test de integración A: NATS real (Sprint 7)
Copyright 2026 Omar Robles

Requiere un servidor NATS corriendo en localhost:4222 (nats-py >= 2.6.0).
Levantarlo con: docker compose up -d nats

Verifica que nats_client publica mensajes reales y que un subscriber
los recibe correctamente en los subjects esperados.

  IA7.1 — publish_started llega al subscriber con el payload correcto
  IA7.2 — publish_approved llega con sdd_summary y counts correctos
  IA7.3 — publish_done llega con artefactos truncados y métricas
  IA7.4 — publish_escalated llega con reason y retry counts
  IA7.5 — fire-and-forget: el ciclo no se interrumpe si NATS cae tras la conexión
  IA7.6 — close() termina la conexión limpiamente y permite reconexión
"""
import sys
import os
import asyncio
import json

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

NATS_URL = "nats://localhost:4222"

# ---------------------------------------------------------------------------
# Fixture: activa NATS_URL real y resetea la conexión entre tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def use_real_nats(monkeypatch):
    import nats_client as nc
    monkeypatch.setattr(nc, "NATS_URL", NATS_URL)
    yield
    # Cerrar conexión lazy después de cada test para evitar leaks
    asyncio.run(nc.close())
    nc._nc = None


# ---------------------------------------------------------------------------
# Estado de prueba base
# ---------------------------------------------------------------------------

def _make_state(**overrides) -> dict:
    base = {
        "session_id":       "integ-sess-001",
        "org_id":           "org-integ",
        "project_id":       "proj-integ",
        "feature_request":  "Prueba de integración NATS",
        "fr_analysis":      {"type": "test", "complexity": "low"},
        "sdd": {
            "summary":      "SDD de prueba de integración",
            "requirements": ["r1", "r2"],
            "tasks":        ["t1"],
        },
        "approval_comment": "auto-aprobado",
        "agent_results": [
            {"agent": "backend", "output": "print('hello')", "tokens": {"input": 10, "output": 5}},
        ],
        "security_result":       {"passed": True, "score": 95},
        "qa_result":             {"passed": True, "score": 90},
        "token_usage": {
            "backend": {"input": 10, "output": 5},
        },
        "github_pr":             {},
        "security_retry_count":  0,
        "qa_retry_count":        0,
        "escalation_resolution": "sin escalación",
    }
    base.update(overrides)
    return base


async def _subscribe_one(subject: str, timeout: float = 3.0) -> dict | None:
    """
    Suscribe a un subject NATS, espera un mensaje y lo retorna parseado.
    Usa una conexión independiente del cliente bajo prueba.
    """
    import nats as nats_lib
    nc = await nats_lib.connect(NATS_URL)
    received = []

    async def handler(msg):
        received.append(json.loads(msg.data.decode()))

    sub = await nc.subscribe(subject, cb=handler)
    yield sub, received
    await sub.unsubscribe()
    await nc.close()


# ---------------------------------------------------------------------------
# Helper: subscriber con coroutine (nats-py requiere async callback)
# ---------------------------------------------------------------------------

async def _collect(nats_lib, subject: str, publish_coro, wait: float = 0.4) -> list:
    """Suscribe a subject, ejecuta publish_coro y retorna mensajes recibidos."""
    received = []

    async def handler(msg):
        received.append(json.loads(msg.data.decode()))

    sub_nc = await nats_lib.connect(NATS_URL)
    sub = await sub_nc.subscribe(subject, cb=handler)
    await asyncio.sleep(0.1)   # sub se registra en el servidor

    await publish_coro
    await asyncio.sleep(wait)  # esperar entrega

    await sub.unsubscribe()
    await sub_nc.close()
    return received


# ---------------------------------------------------------------------------
# IA7.1 — publish_started llega al subscriber
# ---------------------------------------------------------------------------

def test_publish_started_llega_a_nats():
    import nats as nats_lib
    import nats_client as nc

    state = _make_state()
    received = asyncio.run(_collect(
        nats_lib,
        "ovd.org-integ.session.started",
        nc.publish_started(state),
    ))

    assert len(received) == 1
    p = received[0]
    assert p["session_id"]  == "integ-sess-001"
    assert p["org_id"]      == "org-integ"
    assert p["fr_analysis"] == {"type": "test", "complexity": "low"}


# ---------------------------------------------------------------------------
# IA7.2 — publish_approved llega con sdd_summary y counts
# ---------------------------------------------------------------------------

def test_publish_approved_llega_a_nats():
    import nats as nats_lib
    import nats_client as nc

    received = asyncio.run(_collect(
        nats_lib,
        "ovd.org-integ.session.approved",
        nc.publish_approved(_make_state()),
    ))

    assert len(received) == 1
    p = received[0]
    assert p["sdd_summary"]        == "SDD de prueba de integración"
    assert p["requirements_count"] == 2
    assert p["tasks_count"]        == 1
    assert p["approval_comment"]   == "auto-aprobado"


# ---------------------------------------------------------------------------
# IA7.3 — publish_done llega con métricas y artefactos
# ---------------------------------------------------------------------------

def test_publish_done_llega_a_nats():
    import nats as nats_lib
    import nats_client as nc

    received = asyncio.run(_collect(
        nats_lib,
        "ovd.org-integ.session.done",
        nc.publish_done(_make_state(), duration_secs=180.0, cost_usd=0.012),
    ))

    assert len(received) == 1
    p = received[0]
    assert p["sdd"]["summary"]             == "SDD de prueba de integración"
    assert p["duration_secs"]              == 180.0
    assert p["cost_usd"]                   == 0.012
    assert p["token_usage"]["total_input"] == 10
    assert p["agent_results"][0]["agent"]  == "backend"
    assert p["security_result"]["score"]   == 95
    assert p["qa_result"]["score"]         == 90


# ---------------------------------------------------------------------------
# IA7.4 — publish_escalated llega con reason y retry counts
# ---------------------------------------------------------------------------

def test_publish_escalated_llega_a_nats():
    import nats as nats_lib
    import nats_client as nc

    state = _make_state(security_retry_count=2, qa_retry_count=3)
    received = asyncio.run(_collect(
        nats_lib,
        "ovd.org-integ.session.escalated",
        nc.publish_escalated(state, "Límite de reintentos alcanzado"),
    ))

    assert len(received) == 1
    p = received[0]
    assert p["reason"]               == "Límite de reintentos alcanzado"
    assert p["security_retry_count"] == 2
    assert p["qa_retry_count"]       == 3


# ---------------------------------------------------------------------------
# IA7.5 — fire-and-forget: error en nc.publish no interrumpe el caller
# ---------------------------------------------------------------------------

def test_fire_and_forget_no_interrumpe_al_llamador():
    """
    Simula que NATS desconecta durante publish. El caller no debe recibir excepción.
    """
    from unittest.mock import AsyncMock, patch
    import nats_client as nc

    async def _run():
        # Crear conexión real, luego reemplazar nc.publish por uno que falla
        mock_nc = AsyncMock()
        mock_nc.is_connected = True
        mock_nc.publish = AsyncMock(side_effect=ConnectionError("NATS desconectado"))

        nc._nc = mock_nc
        # No debe lanzar
        await nc.publish("ovd.org-integ.session.started", {"test": True})

    asyncio.run(_run())
    # Si llega aquí sin excepción, el test pasa


# ---------------------------------------------------------------------------
# IA7.6 — close() termina limpiamente y permite reconexión
# ---------------------------------------------------------------------------

def test_close_permite_reconexion():
    async def _run():
        import nats_client as nc

        # Primera conexión — forzar conexión lazy
        await nc._get_connection()
        assert nc._nc is not None
        assert nc._nc.is_connected

        # Cerrar
        await nc.close()
        assert nc._nc is None

        # Segunda conexión — debe reconectar sin error
        conn2 = await nc._get_connection()
        assert conn2 is not None
        assert conn2.is_connected

    asyncio.run(_run())
