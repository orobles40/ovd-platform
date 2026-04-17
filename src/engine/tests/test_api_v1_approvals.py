"""
OVD Platform — Tests: endpoint de aprobaciones pendientes (Bloque A)
GET /api/v1/orgs/{org_id}/approvals/pending

Estrategia: pending_store mockeado en memoria, BD mockeada con AsyncMock.
No requiere infraestructura.
"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

_TEST_SECRET  = "a" * 64
_ORG_ID       = "ORG_APPROVAL_TEST"
_OTHER_ORG_ID = "ORG_OTHER"
_USER_ID      = "USR_APPROVAL_01"
_PROJECT_ID   = "PROJ_001"


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


@pytest.fixture(autouse=True)
def clear_store():
    import pending_store
    pending_store._store.clear()
    yield
    pending_store._store.clear()


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


def _approval_item(thread_id: str, org_id: str = _ORG_ID, project_id: str = "") -> dict:
    return {
        "thread_id":      thread_id,
        "session_id":     f"sess-{thread_id}",
        "org_id":         org_id,
        "project_id":     project_id,
        "feature_request": f"Feature para {thread_id}",
        "sdd_summary":    "Resumen del SDD generado",
        "sdd": {
            "summary":      "Módulo de autenticación",
            "requirements": [{"id": "R1", "description": "JWT válido"}],
            "tasks":        [{"agent": "backend", "title": "Implementar JWT handler"}],
            "constraints":  [],
        },
        "revision_count": 0,
    }


def _conn_with_project(project_name: str = "OVD Platform"):
    """Mock de conexión que retorna un proyecto para el enriquecimiento."""
    cursor = MagicMock()
    cursor.fetchall = AsyncMock(return_value=[(_PROJECT_ID, project_name)])
    cursor.fetchone = AsyncMock(return_value=None)
    conn = AsyncMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__  = AsyncMock(return_value=False)
    conn.execute    = AsyncMock(return_value=cursor)
    return conn


# ---------------------------------------------------------------------------
# TestListPendingApprovals — sin items
# ---------------------------------------------------------------------------

class TestListPendingApprovalsVacio:
    @pytest.mark.asyncio
    async def test_retorna_lista_vacia_si_no_hay_pendientes(self, app, auth_headers):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(
                f"/api/v1/orgs/{_ORG_ID}/approvals/pending",
                headers=auth_headers,
            )
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_sin_token_retorna_401(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(f"/api/v1/orgs/{_ORG_ID}/approvals/pending")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_otro_org_retorna_403(self, app):
        import auth
        token = auth.create_access_token(_USER_ID, _OTHER_ORG_ID, "developer")
        headers = {"Authorization": f"Bearer {token}"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(
                f"/api/v1/orgs/{_ORG_ID}/approvals/pending",
                headers=headers,
            )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# TestListPendingApprovals — con items
# ---------------------------------------------------------------------------

class TestListPendingApprovalsConItems:
    @pytest.mark.asyncio
    async def test_retorna_items_del_org(self, app, auth_headers):
        import pending_store
        pending_store.add("TH1", _approval_item("TH1"))
        pending_store.add("TH2", _approval_item("TH2"))

        with patch("psycopg.AsyncConnection.connect", return_value=_conn_with_project()):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    f"/api/v1/orgs/{_ORG_ID}/approvals/pending",
                    headers=auth_headers,
                )

        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2
        thread_ids = {item["thread_id"] for item in data}
        assert thread_ids == {"TH1", "TH2"}

    @pytest.mark.asyncio
    async def test_item_tiene_campos_requeridos(self, app, auth_headers):
        import pending_store
        pending_store.add("TH1", _approval_item("TH1"))

        with patch("psycopg.AsyncConnection.connect", return_value=_conn_with_project()):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    f"/api/v1/orgs/{_ORG_ID}/approvals/pending",
                    headers=auth_headers,
                )

        item = r.json()[0]
        for campo in ["thread_id", "session_id", "feature_request",
                      "sdd_summary", "sdd", "created_at", "revision_count"]:
            assert campo in item, f"Campo '{campo}' ausente en la respuesta"

    @pytest.mark.asyncio
    async def test_created_at_es_iso8601(self, app, auth_headers):
        import pending_store
        from datetime import datetime
        pending_store.add("TH1", _approval_item("TH1"))

        with patch("psycopg.AsyncConnection.connect", return_value=_conn_with_project()):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    f"/api/v1/orgs/{_ORG_ID}/approvals/pending",
                    headers=auth_headers,
                )

        created_at = r.json()[0]["created_at"]
        # Debe parsear sin lanzar excepción
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        assert dt is not None

    @pytest.mark.asyncio
    async def test_sdd_contiene_requirements_y_tasks(self, app, auth_headers):
        import pending_store
        pending_store.add("TH1", _approval_item("TH1"))

        with patch("psycopg.AsyncConnection.connect", return_value=_conn_with_project()):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    f"/api/v1/orgs/{_ORG_ID}/approvals/pending",
                    headers=auth_headers,
                )

        sdd = r.json()[0]["sdd"]
        assert "requirements" in sdd
        assert "tasks" in sdd
        assert len(sdd["requirements"]) == 1
        assert sdd["requirements"][0]["id"] == "R1"


# ---------------------------------------------------------------------------
# TestAislamientoMultiOrg — regresión SEC-01
# ---------------------------------------------------------------------------

class TestAislamientoApprovals:
    @pytest.mark.asyncio
    async def test_org_a_no_ve_pendientes_de_org_b(self, app, auth_headers):
        import pending_store
        # ORG_ID tiene 2 pendientes, ORG_OTHER tiene 1
        pending_store.add("TH_A1", _approval_item("TH_A1", _ORG_ID))
        pending_store.add("TH_A2", _approval_item("TH_A2", _ORG_ID))
        pending_store.add("TH_B1", _approval_item("TH_B1", _OTHER_ORG_ID))

        conn = MagicMock()
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__  = AsyncMock(return_value=False)
        cursor = MagicMock()
        cursor.fetchall = AsyncMock(return_value=[])
        conn.execute = AsyncMock(return_value=cursor)

        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    f"/api/v1/orgs/{_ORG_ID}/approvals/pending",
                    headers=auth_headers,
                )

        data = r.json()
        assert len(data) == 2
        for item in data:
            assert item["thread_id"] != "TH_B1"

    @pytest.mark.asyncio
    async def test_revision_count_preservado(self, app, auth_headers):
        import pending_store
        item = _approval_item("TH1")
        item["revision_count"] = 2
        pending_store.add("TH1", item)

        with patch("psycopg.AsyncConnection.connect", return_value=_conn_with_project()):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    f"/api/v1/orgs/{_ORG_ID}/approvals/pending",
                    headers=auth_headers,
                )

        assert r.json()[0]["revision_count"] == 2
