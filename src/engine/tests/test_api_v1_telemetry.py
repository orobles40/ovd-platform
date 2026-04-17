"""
OVD Platform — Tests: endpoint de telemetría (Bloque A)
GET /api/v1/orgs/{org_id}/telemetry

Estrategia: BD mockeada con AsyncMock, token JWT real con _TEST_SECRET.
No requiere infraestructura.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date, timezone
from decimal import Decimal
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

_TEST_SECRET  = "a" * 64
_ORG_ID       = "ORG_TELEM_TEST"
_OTHER_ORG_ID = "ORG_OTHER"
_USER_ID      = "USR_TELEM_01"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_secrets(monkeypatch):
    import auth
    monkeypatch.setattr(auth, "_JWT_SECRET", _TEST_SECRET)
    import routers.api_v1 as av
    monkeypatch.setattr(av, "_DATABASE_URL", "postgresql://mock")
    import routers.auth_router as ar
    monkeypatch.setattr(ar, "_DATABASE_URL", "postgresql://mock")


@pytest.fixture
def app():
    from routers.auth_router import router as auth_router
    from routers.api_v1 import router as api_router
    a = FastAPI()
    a.include_router(auth_router)
    a.include_router(api_router)
    return a


@pytest.fixture
def auth_headers():
    import auth
    token = auth.create_access_token(_USER_ID, _ORG_ID, "admin")
    return {"Authorization": f"Bearer {token}"}


def _make_conn(daily_rows=None, agent_rows=None, complexity_rows=None, delta_row=None):
    """
    Crea una conexión mock que retorna los resultados en el orden en que
    el endpoint ejecuta las queries: daily → agents → complexity → delta.
    """
    daily_rows      = daily_rows      or []
    agent_rows      = agent_rows      or []
    complexity_rows = complexity_rows or []
    delta_row       = delta_row       or (Decimal("0"), Decimal("0"))

    cursors = []
    for rows, one in [
        (daily_rows,      None),
        (agent_rows,      None),
        (complexity_rows, None),
        (None,            delta_row),
    ]:
        c = MagicMock()
        c.fetchall  = AsyncMock(return_value=rows or [])
        c.fetchone  = AsyncMock(return_value=one)
        cursors.append(c)

    it = iter(cursors)
    conn = AsyncMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__  = AsyncMock(return_value=False)
    conn.execute    = AsyncMock(side_effect=lambda *a, **kw: next(it))
    return conn


# ---------------------------------------------------------------------------
# TestTelemetryAuth
# ---------------------------------------------------------------------------

class TestTelemetryAuth:
    @pytest.mark.asyncio
    async def test_sin_token_retorna_401(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(f"/api/v1/orgs/{_ORG_ID}/telemetry")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_otro_org_retorna_403(self, app):
        import auth
        token = auth.create_access_token(_USER_ID, _OTHER_ORG_ID, "developer")
        headers = {"Authorization": f"Bearer {token}"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(
                f"/api/v1/orgs/{_ORG_ID}/telemetry",
                headers=headers,
            )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# TestTelemetryEstructura
# ---------------------------------------------------------------------------

class TestTelemetryEstructura:
    @pytest.mark.asyncio
    async def test_respuesta_sin_datos_tiene_estructura_correcta(self, app, auth_headers):
        conn = _make_conn()
        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    f"/api/v1/orgs/{_ORG_ID}/telemetry",
                    headers=auth_headers,
                )

        assert r.status_code == 200
        data = r.json()
        for campo in ["period_days", "daily", "agent_tokens", "complexity_dist", "qa_delta"]:
            assert campo in data, f"Campo '{campo}' ausente en la respuesta"

    @pytest.mark.asyncio
    async def test_qa_delta_tiene_current_previous_diff(self, app, auth_headers):
        conn = _make_conn(delta_row=(Decimal("85.0"), Decimal("78.0")))
        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    f"/api/v1/orgs/{_ORG_ID}/telemetry",
                    headers=auth_headers,
                )

        qa = r.json()["qa_delta"]
        assert "current"  in qa
        assert "previous" in qa
        assert "diff"     in qa
        assert qa["current"]  == 85.0
        assert qa["previous"] == 78.0
        assert qa["diff"]     == 7.0

    @pytest.mark.asyncio
    async def test_period_days_default_es_30(self, app, auth_headers):
        conn = _make_conn()
        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    f"/api/v1/orgs/{_ORG_ID}/telemetry",
                    headers=auth_headers,
                )
        assert r.json()["period_days"] == 30

    @pytest.mark.asyncio
    async def test_period_days_personalizado(self, app, auth_headers):
        conn = _make_conn()
        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    f"/api/v1/orgs/{_ORG_ID}/telemetry?days=7",
                    headers=auth_headers,
                )
        assert r.json()["period_days"] == 7

    @pytest.mark.asyncio
    async def test_days_mayor_a_90_es_rechazado(self, app, auth_headers):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(
                f"/api/v1/orgs/{_ORG_ID}/telemetry?days=200",
                headers=auth_headers,
            )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# TestTelemetryConDatos
# ---------------------------------------------------------------------------

class TestTelemetryConDatos:
    @pytest.mark.asyncio
    async def test_daily_tiene_campos_requeridos(self, app, auth_headers):
        today = date.today()
        daily = [(today, 5, Decimal("82.0"), Decimal("0.0012"), 3000, 1500)]
        conn = _make_conn(daily_rows=daily)

        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    f"/api/v1/orgs/{_ORG_ID}/telemetry",
                    headers=auth_headers,
                )

        data = r.json()
        assert len(data["daily"]) == 1
        day = data["daily"][0]
        for campo in ["date", "cycle_count", "avg_qa", "cost_usd", "tokens_in", "tokens_out"]:
            assert campo in day, f"Campo '{campo}' ausente en daily"
        assert day["cycle_count"] == 5
        assert day["avg_qa"] == 82.0
        assert day["tokens_in"] == 3000

    @pytest.mark.asyncio
    async def test_agent_tokens_tiene_campos_requeridos(self, app, auth_headers):
        agents = [("backend", 10000, 5000, 8), ("frontend", 6000, 3000, 5)]
        conn = _make_conn(agent_rows=agents)

        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    f"/api/v1/orgs/{_ORG_ID}/telemetry",
                    headers=auth_headers,
                )

        data = r.json()
        assert len(data["agent_tokens"]) == 2
        agent = data["agent_tokens"][0]
        for campo in ["agent", "tokens_in", "tokens_out", "cycle_count"]:
            assert campo in agent
        assert agent["agent"] == "backend"
        assert agent["tokens_in"] == 10000

    @pytest.mark.asyncio
    async def test_complexity_dist_es_dict(self, app, auth_headers):
        complexity = [("high", 3), ("medium", 10), ("low", 7)]
        conn = _make_conn(complexity_rows=complexity)

        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    f"/api/v1/orgs/{_ORG_ID}/telemetry",
                    headers=auth_headers,
                )

        dist = r.json()["complexity_dist"]
        assert isinstance(dist, dict)
        assert dist["high"] == 3
        assert dist["medium"] == 10
        assert dist["low"] == 7

    @pytest.mark.asyncio
    async def test_qa_delta_diff_calculado_correctamente(self, app, auth_headers):
        conn = _make_conn(delta_row=(Decimal("90.0"), Decimal("80.0")))

        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    f"/api/v1/orgs/{_ORG_ID}/telemetry",
                    headers=auth_headers,
                )

        qa = r.json()["qa_delta"]
        assert qa["diff"] == pytest.approx(10.0, abs=0.1)

    @pytest.mark.asyncio
    async def test_qa_delta_negativo_cuando_calidad_baja(self, app, auth_headers):
        conn = _make_conn(delta_row=(Decimal("70.0"), Decimal("85.0")))

        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    f"/api/v1/orgs/{_ORG_ID}/telemetry",
                    headers=auth_headers,
                )

        qa = r.json()["qa_delta"]
        assert qa["diff"] < 0


# ---------------------------------------------------------------------------
# TestTelemetryAislamientoOrg
# ---------------------------------------------------------------------------

class TestTelemetryAislamientoOrg:
    @pytest.mark.asyncio
    async def test_admin_puede_acceder_a_su_propio_org(self, app, auth_headers):
        conn = _make_conn()
        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    f"/api/v1/orgs/{_ORG_ID}/telemetry",
                    headers=auth_headers,
                )
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_developer_puede_acceder_a_su_propio_org(self, app):
        import auth
        token = auth.create_access_token(_USER_ID, _ORG_ID, "developer")
        headers = {"Authorization": f"Bearer {token}"}
        conn = _make_conn()
        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    f"/api/v1/orgs/{_ORG_ID}/telemetry",
                    headers=headers,
                )
        assert r.status_code == 200
