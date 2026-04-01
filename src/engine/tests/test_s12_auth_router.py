"""
OVD Platform — Tests: Auth Router endpoints (S12.A)
Cubre: POST /auth/login, /auth/refresh, /auth/logout, GET /auth/me

Estrategia: AsyncMock sobre psycopg para evitar dependencia de BD real.
El JWT se genera con el mismo _TEST_SECRET que los tests de S10.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

# ---------------------------------------------------------------------------
# Constantes de test
# ---------------------------------------------------------------------------

_TEST_SECRET = "a" * 64
_ORG_ID  = "01KMK160F1TJ807Z0BDSJD504D"
_USER_ID = "01KMK160F1XCGGT5K2Q1QWQHGZ"
_EMAIL   = "omar@omarrobles.dev"

# Hash argon2id de "test-password-123"
# Generado con: passlib.hash.argon2.hash("test-password-123")
_PWD_PLAIN = "test-password-123"
from passlib.hash import argon2 as _argon2
_PWD_HASH = _argon2.hash(_PWD_PLAIN)

_USER_ROW = {
    "id":            _USER_ID,
    "org_id":        _ORG_ID,
    "email":         _EMAIL,
    "password_hash": _PWD_HASH,
    "role":          "admin",
    "active":        True,
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_jwt_secret(monkeypatch):
    import auth
    monkeypatch.setattr(auth, "_JWT_SECRET", _TEST_SECRET)
    import routers.auth_router as ar
    monkeypatch.setattr(ar, "_DATABASE_URL", "postgresql://mock")


def _make_conn_mock(user_row: dict | None = _USER_ROW, role: str = "admin", email: str = _EMAIL):
    """Devuelve un mock de psycopg.AsyncConnection con fetchone configurado."""
    fetch_user   = AsyncMock(return_value=tuple(user_row.values()) if user_row else None)
    fetch_role   = AsyncMock(return_value=(role,))
    fetch_email  = AsyncMock(return_value=(email,))
    fetch_insert = AsyncMock(return_value=None)

    cursor_mock = MagicMock()
    # Secuencia de fetchone: primero login (user), luego inserta refresh token, luego /me (email)
    cursor_mock.fetchone = AsyncMock(side_effect=[
        tuple(user_row.values()) if user_row else None,  # _get_user_by_email en login
        None,                                             # INSERT refresh token (execute, no fetchone)
        (email,),                                         # /me → email lookup
    ])

    execute_mock = AsyncMock(return_value=cursor_mock)
    conn_mock = AsyncMock()
    conn_mock.__aenter__ = AsyncMock(return_value=conn_mock)
    conn_mock.__aexit__  = AsyncMock(return_value=False)
    conn_mock.execute    = execute_mock
    conn_mock.commit     = AsyncMock()
    return conn_mock


@pytest.fixture
def app_with_mocks(monkeypatch):
    """FastAPI app mínima con solo los routers S12 (sin lifespan del engine completo)."""
    from fastapi import FastAPI
    from routers.auth_router import router as auth_router

    app = FastAPI()
    app.include_router(auth_router)
    return app


# ---------------------------------------------------------------------------
# Tests: POST /auth/login
# ---------------------------------------------------------------------------

class TestLogin:
    @pytest.mark.asyncio
    async def test_login_exitoso(self, app_with_mocks):
        conn = _make_conn_mock()
        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
                r = await client.post("/auth/login", json={"email": _EMAIL, "password": _PWD_PLAIN})

        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 3600

    @pytest.mark.asyncio
    async def test_login_password_incorrecta(self, app_with_mocks):
        conn = _make_conn_mock()
        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
                r = await client.post("/auth/login", json={"email": _EMAIL, "password": "wrong-password"})

        assert r.status_code == 401
        assert "inválidas" in r.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_usuario_no_existe(self, app_with_mocks):
        conn = _make_conn_mock(user_row=None)
        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
                r = await client.post("/auth/login", json={"email": "noexiste@test.com", "password": "x"})

        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_login_usuario_inactivo(self, app_with_mocks):
        inactive = {**_USER_ROW, "active": False}
        conn = _make_conn_mock(user_row=inactive)
        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
                r = await client.post("/auth/login", json={"email": _EMAIL, "password": _PWD_PLAIN})

        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_login_genera_jwt_valido(self, app_with_mocks):
        conn = _make_conn_mock()
        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
                r = await client.post("/auth/login", json={"email": _EMAIL, "password": _PWD_PLAIN})

        from auth import verify_access_token
        token = r.json()["access_token"]
        payload = verify_access_token(token)
        assert payload.sub == _USER_ID
        assert payload.org_id == _ORG_ID
        assert payload.role == "admin"


# ---------------------------------------------------------------------------
# Tests: GET /auth/me
# ---------------------------------------------------------------------------

class TestMe:
    def _valid_token(self):
        import auth as _auth
        import routers.auth_router as ar
        old = _auth._JWT_SECRET
        _auth._JWT_SECRET = _TEST_SECRET
        token = _auth.create_access_token(_USER_ID, _ORG_ID, "admin")
        _auth._JWT_SECRET = old
        return token

    @pytest.mark.asyncio
    async def test_me_con_token_valido(self, app_with_mocks, monkeypatch):
        import auth
        monkeypatch.setattr(auth, "_JWT_SECRET", _TEST_SECRET)
        token = auth.create_access_token(_USER_ID, _ORG_ID, "admin")

        cursor = MagicMock()
        cursor.fetchone = AsyncMock(return_value=(_EMAIL,))
        conn = AsyncMock()
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__  = AsyncMock(return_value=False)
        conn.execute    = AsyncMock(return_value=cursor)

        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
                r = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

        assert r.status_code == 200
        data = r.json()
        assert data["user_id"] == _USER_ID
        assert data["org_id"] == _ORG_ID
        assert data["role"] == "admin"
        assert data["email"] == _EMAIL

    @pytest.mark.asyncio
    async def test_me_sin_token_retorna_401(self, app_with_mocks):
        async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
            r = await client.get("/auth/me")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_me_token_invalido_retorna_401(self, app_with_mocks):
        async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
            r = await client.get("/auth/me", headers={"Authorization": "Bearer token.invalido.xxx"})
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Tests: POST /auth/logout
# ---------------------------------------------------------------------------

class TestLogout:
    @pytest.mark.asyncio
    async def test_logout_retorna_204(self, app_with_mocks):
        cursor = MagicMock()
        cursor.rowcount = 1
        conn = AsyncMock()
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__  = AsyncMock(return_value=False)
        conn.execute    = AsyncMock(return_value=cursor)
        conn.commit     = AsyncMock()

        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
                r = await client.post("/auth/logout", json={"refresh_token": "any-token-value"})

        assert r.status_code == 204


# ---------------------------------------------------------------------------
# Tests: inject_current_user (dependencia reutilizable)
# ---------------------------------------------------------------------------

class TestInjectCurrentUser:
    @pytest.mark.asyncio
    async def test_token_expirado_retorna_401(self, app_with_mocks, monkeypatch):
        """Un JWT firmado con otro secret debe fallar."""
        import auth
        monkeypatch.setattr(auth, "_JWT_SECRET", "b" * 64)
        token_otro_secret = auth.create_access_token(_USER_ID, _ORG_ID, "dev")

        monkeypatch.setattr(auth, "_JWT_SECRET", _TEST_SECRET)
        async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
            r = await client.get("/auth/me", headers={"Authorization": f"Bearer {token_otro_secret}"})
        assert r.status_code == 401
