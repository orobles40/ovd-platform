"""
OVD Platform — Tests: API REST v1 (S12.B)
Cubre: /api/v1/orgs/{id}/projects, /cycles, /stats

Estrategia: token JWT real (con _TEST_SECRET), BD mockeada con AsyncMock.
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

_TEST_SECRET = "a" * 64
_ORG_ID      = "01KMK160F1TJ807Z0BDSJD504D"
_USER_ID     = "01KMK160F1XCGGT5K2Q1QWQHGZ"
_PROJECT_ID  = "01KMK17YZ5BKEMVAS4XZSTG9AW"
_CYCLE_ID    = "CYCLE001"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_secrets(monkeypatch):
    import auth
    monkeypatch.setattr(auth, "_JWT_SECRET", _TEST_SECRET)
    import routers.auth_router as ar
    monkeypatch.setattr(ar, "_DATABASE_URL", "postgresql://mock")
    import routers.api_v1 as av
    monkeypatch.setattr(av, "_DATABASE_URL", "postgresql://mock")


@pytest.fixture
def app():
    from routers.auth_router import router as auth_router
    from routers.api_v1 import router as api_v1_router
    a = FastAPI()
    a.include_router(auth_router)
    a.include_router(api_v1_router)
    return a


@pytest.fixture
def auth_headers(monkeypatch):
    import auth
    monkeypatch.setattr(auth, "_JWT_SECRET", _TEST_SECRET)
    token = auth.create_access_token(_USER_ID, _ORG_ID, "admin")
    return {"Authorization": f"Bearer {token}"}


def _conn_mock(*fetchone_results, rowcount=1):
    """Crea un mock de conexión psycopg con fetchone devolviendo los valores dados en secuencia."""
    cursor = MagicMock()
    cursor.fetchone  = AsyncMock(side_effect=list(fetchone_results))
    cursor.fetchall  = AsyncMock(return_value=[])
    cursor.rowcount  = rowcount
    conn = AsyncMock()
    conn.__aenter__  = AsyncMock(return_value=conn)
    conn.__aexit__   = AsyncMock(return_value=False)
    conn.execute     = AsyncMock(return_value=cursor)
    conn.commit      = AsyncMock()
    return conn


# ---------------------------------------------------------------------------
# Tests: Proyectos — GET /api/v1/orgs/{org_id}/projects
# ---------------------------------------------------------------------------

class TestListProjects:
    @pytest.mark.asyncio
    async def test_lista_proyectos_vacia(self, app, auth_headers):
        cursor = MagicMock()
        cursor.fetchall = AsyncMock(return_value=[])
        conn = AsyncMock()
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__  = AsyncMock(return_value=False)
        conn.execute    = AsyncMock(return_value=cursor)

        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(f"/api/v1/orgs/{_ORG_ID}/projects", headers=auth_headers)

        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_lista_proyectos_con_datos(self, app, auth_headers):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        rows = [
            (_PROJECT_ID, "OVD Platform", "Desc", "/path", True, now, "Java", "Struts", "Oracle"),
        ]
        cursor = MagicMock()
        cursor.fetchall = AsyncMock(return_value=rows)
        conn = AsyncMock()
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__  = AsyncMock(return_value=False)
        conn.execute    = AsyncMock(return_value=cursor)

        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(f"/api/v1/orgs/{_ORG_ID}/projects", headers=auth_headers)

        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["id"] == _PROJECT_ID
        assert data[0]["stack"]["language"] == "Java"

    @pytest.mark.asyncio
    async def test_sin_token_retorna_401(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(f"/api/v1/orgs/{_ORG_ID}/projects")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_otro_org_retorna_403(self, app, monkeypatch):
        import auth
        monkeypatch.setattr(auth, "_JWT_SECRET", _TEST_SECRET)
        # Token de otro org
        token = auth.create_access_token(_USER_ID, "otro-org-id", "developer")
        headers = {"Authorization": f"Bearer {token}"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(f"/api/v1/orgs/{_ORG_ID}/projects", headers=headers)
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Tests: Proyectos — POST /api/v1/orgs/{org_id}/projects
# ---------------------------------------------------------------------------

class TestCreateProject:
    @pytest.mark.asyncio
    async def test_crear_proyecto(self, app, auth_headers):
        cursor = MagicMock()
        cursor.fetchone = AsyncMock(return_value=None)
        conn = AsyncMock()
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__  = AsyncMock(return_value=False)
        conn.execute    = AsyncMock(return_value=cursor)
        conn.commit     = AsyncMock()

        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.post(
                    f"/api/v1/orgs/{_ORG_ID}/projects",
                    json={"name": "Nuevo Proyecto", "directory": "/srv/app"},
                    headers=auth_headers,
                )

        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Nuevo Proyecto"
        assert "id" in data


# ---------------------------------------------------------------------------
# Tests: Ciclos — GET /api/v1/orgs/{org_id}/cycles
# ---------------------------------------------------------------------------

class TestListCycles:
    @pytest.mark.asyncio
    async def test_lista_ciclos_vacia(self, app, auth_headers):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        cursor = MagicMock()
        cursor.fetchall  = AsyncMock(return_value=[])
        cursor.fetchone  = AsyncMock(return_value=(0,))
        conn = AsyncMock()
        conn.__aenter__  = AsyncMock(return_value=conn)
        conn.__aexit__   = AsyncMock(return_value=False)
        conn.execute     = AsyncMock(return_value=cursor)

        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(f"/api/v1/orgs/{_ORG_ID}/cycles", headers=auth_headers)

        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_lista_ciclos_con_datos(self, app, auth_headers):
        from datetime import datetime, timezone
        from decimal import Decimal
        now = datetime.now(timezone.utc)
        row = (_CYCLE_ID, _PROJECT_ID, "OVD Platform", "sess1",
               "Implementar autenticación JWT", 85, "medium", "feature",
               1500, Decimal("0.000320"), now)
        cursor = MagicMock()
        cursor.fetchall  = AsyncMock(return_value=[row])
        cursor.fetchone  = AsyncMock(return_value=(1,))
        conn = AsyncMock()
        conn.__aenter__  = AsyncMock(return_value=conn)
        conn.__aexit__   = AsyncMock(return_value=False)
        conn.execute     = AsyncMock(return_value=cursor)

        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(f"/api/v1/orgs/{_ORG_ID}/cycles", headers=auth_headers)

        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == _CYCLE_ID
        assert data["items"][0]["qa_score"] == 85

    @pytest.mark.asyncio
    async def test_paginacion_params(self, app, auth_headers):
        cursor = MagicMock()
        cursor.fetchall = AsyncMock(return_value=[])
        cursor.fetchone = AsyncMock(return_value=(0,))
        conn = AsyncMock()
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__  = AsyncMock(return_value=False)
        conn.execute    = AsyncMock(return_value=cursor)

        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    f"/api/v1/orgs/{_ORG_ID}/cycles?limit=10&offset=20",
                    headers=auth_headers,
                )

        assert r.status_code == 200
        data = r.json()
        assert data["limit"] == 10
        assert data["offset"] == 20


# ---------------------------------------------------------------------------
# Tests: Ciclos — GET /api/v1/orgs/{org_id}/cycles/{cycle_id}
# ---------------------------------------------------------------------------

class TestGetCycle:
    @pytest.mark.asyncio
    async def test_ciclo_no_encontrado_retorna_404(self, app, auth_headers):
        cursor = MagicMock()
        cursor.fetchone = AsyncMock(return_value=None)
        conn = AsyncMock()
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__  = AsyncMock(return_value=False)
        conn.execute    = AsyncMock(return_value=cursor)

        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    f"/api/v1/orgs/{_ORG_ID}/cycles/NOEXISTE",
                    headers=auth_headers,
                )

        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_ciclo_detalle_completo(self, app, auth_headers):
        from datetime import datetime, timezone
        from decimal import Decimal
        now = datetime.now(timezone.utc)
        fr_analysis = json.dumps({"complexity": "medium", "fr_type": "feature"})
        sdd         = json.dumps({"sections": []})
        agent_res   = json.dumps([{"agent": "backend", "status": "ok"}])
        qa_result   = json.dumps({"score": 85, "issues": []})
        by_agent    = json.dumps({"analyzer": {"input": 300, "output": 150}})

        row = (
            _CYCLE_ID, _PROJECT_ID, "OVD Platform",
            "sess1", "thread1", "Implementar JWT",
            fr_analysis, sdd, agent_res, qa_result,
            85, "medium", "feature", False,
            500, 300, 800,
            by_agent, Decimal("0.000250"), now,
        )
        cursor = MagicMock()
        cursor.fetchone = AsyncMock(return_value=row)
        conn = AsyncMock()
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__  = AsyncMock(return_value=False)
        conn.execute    = AsyncMock(return_value=cursor)

        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    f"/api/v1/orgs/{_ORG_ID}/cycles/{_CYCLE_ID}",
                    headers=auth_headers,
                )

        assert r.status_code == 200
        data = r.json()
        assert data["id"] == _CYCLE_ID
        assert data["qa_score"] == 85
        assert data["tokens"]["total"] == 800
        assert data["fr_analysis"]["complexity"] == "medium"
        assert data["tokens"]["by_agent"]["analyzer"]["input"] == 300


# ---------------------------------------------------------------------------
# Tests: Stats — GET /api/v1/orgs/{org_id}/stats
# ---------------------------------------------------------------------------

class TestGetStats:
    @pytest.mark.asyncio
    async def test_stats_sin_ciclos(self, app, auth_headers):
        from decimal import Decimal
        stats_row = (0, Decimal("0"), 0, Decimal("0"), 0, 0)
        cursor = MagicMock()
        cursor.fetchone  = AsyncMock(return_value=stats_row)
        cursor.fetchall  = AsyncMock(return_value=[])
        conn = AsyncMock()
        conn.__aenter__  = AsyncMock(return_value=conn)
        conn.__aexit__   = AsyncMock(return_value=False)
        conn.execute     = AsyncMock(return_value=cursor)

        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(f"/api/v1/orgs/{_ORG_ID}/stats", headers=auth_headers)

        assert r.status_code == 200
        data = r.json()
        assert data["total_cycles"] == 0
        assert data["avg_qa_score"] == 0.0
        assert data["fr_type_distribution"] == {}

    @pytest.mark.asyncio
    async def test_stats_con_datos(self, app, auth_headers):
        from decimal import Decimal
        stats_row = (42, Decimal("83.5"), 95000, Decimal("0.028"), 38, 3)
        fr_rows   = [("feature", 25), ("bugfix", 12), ("refactor", 5)]
        daily_rows = []

        call_count = 0
        cursors = []
        for row, all_rows in [
            (stats_row, None),
            (None, fr_rows),
            (None, daily_rows),
        ]:
            c = MagicMock()
            c.fetchone  = AsyncMock(return_value=row)
            c.fetchall  = AsyncMock(return_value=all_rows or [])
            cursors.append(c)

        cursor_iter = iter(cursors)
        conn = AsyncMock()
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__  = AsyncMock(return_value=False)
        conn.execute    = AsyncMock(side_effect=lambda *a, **kw: next(cursor_iter))
        conn.commit     = AsyncMock()

        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(f"/api/v1/orgs/{_ORG_ID}/stats?days=30", headers=auth_headers)

        assert r.status_code == 200
        data = r.json()
        assert data["total_cycles"] == 42
        assert data["avg_qa_score"] == 83.5
        assert data["fr_type_distribution"]["feature"] == 25
