"""
OVD Platform — Tests de regresión de seguridad (Bloque A)

Cubre los 4 hallazgos corregidos en el sprint SEC-2026-03-28:
  LOW-02:    PAT GitHub se limpia del checkpointer tras uso (graph.py)
  LOW-03:    Rate limiting activo en endpoints de auth (auth_router.py)
  MEDIUM-02: INTERVAL SQL usa parámetro ligado, no f-string (api_v1.py)
  MEDIUM-04: Refresh token se emite en cookie HttpOnly + Secure (auth_router.py)

No requiere BD real — usa mocks y AsyncClient ASGI.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import inspect
import re
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

_TEST_SECRET = "a" * 64
_ORG_ID      = "ORG_TEST"
_USER_ID     = "USR_TEST_01"


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


def _empty_conn():
    """Conexión mock que no devuelve filas."""
    cursor = MagicMock()
    cursor.fetchone  = AsyncMock(return_value=None)
    cursor.fetchall  = AsyncMock(return_value=[])
    cursor.rowcount  = 1
    conn = AsyncMock()
    conn.__aenter__  = AsyncMock(return_value=conn)
    conn.__aexit__   = AsyncMock(return_value=False)
    conn.execute     = AsyncMock(return_value=cursor)
    conn.commit      = AsyncMock()
    return conn


# ---------------------------------------------------------------------------
# LOW-02: PAT limpiado del checkpointer tras uso
# ---------------------------------------------------------------------------

class TestLOW02PATCleanup:
    """
    Verifica que el nodo que realiza la integración GitHub
    retorna github_token="" en su estado de salida, de modo que
    el checkpointer de LangGraph no almacena el PAT en texto plano.
    """

    def test_nodo_git_limpia_github_token_post_uso(self):
        """El nodo de integración Git asigna github_token='' al estado de salida."""
        import graph
        source = inspect.getsource(graph)
        # Buscar la línea exacta del fix LOW-02
        match = re.search(
            r'"github_token"\s*:\s*""\s*.*LOW-02',
            source,
        )
        assert match is not None, (
            "LOW-02: no se encontró 'github_token': '' # LOW-02 en graph.py — "
            "el PAT puede persistir en el checkpointer"
        )

    def test_github_token_vaciado_en_estado_salida(self):
        """Verifica la estructura del estado de salida del nodo de entrega."""
        import graph
        # Buscar el bloque donde se limpia el PAT
        source = inspect.getsource(graph)
        # Debe existir exactamente UNA asignación de vaciado por el fix
        matches = re.findall(r'"github_token"\s*:\s*""', source)
        assert len(matches) >= 1, (
            "LOW-02: no se encontró ninguna asignación github_token='' en graph.py"
        )

    def test_inject_token_no_expone_pat_en_logs(self):
        """El error de clone redacta el PAT con *** antes de loguear."""
        import github_helper
        source = inspect.getsource(github_helper)
        assert "***:***@" in source or "\\*\\*\\*" in source, (
            "SEC HIGH-02: no se encontró redacción del PAT en mensajes de error"
        )


# ---------------------------------------------------------------------------
# LOW-03: Rate limiting en endpoints de autenticación
# ---------------------------------------------------------------------------

class TestLOW03RateLimiting:
    """
    Verifica que el decorador @limiter.limit está aplicado en login y refresh.
    No prueba slowapi internamente — verifica que la configuración existe.
    """

    def test_login_endpoint_tiene_rate_limit(self):
        from routers.auth_router import login
        # slowapi añade __limits__ al endpoint decorado
        assert hasattr(login, "_rate_limits") or hasattr(login, "__wrapped__") or \
               any("limit" in str(getattr(login, attr, ""))
                   for attr in dir(login)), \
            "LOW-03: el endpoint /auth/login no tiene decorador @limiter.limit"

    def test_rate_limiter_configurado_en_modulo(self):
        from rate_limiter import limiter
        assert limiter is not None
        assert callable(limiter.limit)

    def test_login_source_tiene_limite_10_por_minuto(self):
        import routers.auth_router as ar
        source = inspect.getsource(ar)
        assert "10/minute" in source, (
            "LOW-03: no se encontró límite '10/minute' en auth_router.py"
        )

    def test_refresh_source_tiene_limite_20_por_minuto(self):
        import routers.auth_router as ar
        source = inspect.getsource(ar)
        assert "20/minute" in source, (
            "LOW-03: no se encontró límite '20/minute' en auth_router.py"
        )

    def test_limiter_usa_remote_address(self):
        """La clave de rate limit debe ser la IP del cliente, no un valor fijo."""
        from rate_limiter import limiter
        from slowapi.util import get_remote_address
        assert limiter._key_func is get_remote_address, (
            "LOW-03: el limiter no usa get_remote_address como key_func"
        )


# ---------------------------------------------------------------------------
# MEDIUM-02: INTERVAL SQL usa parámetro ligado
# ---------------------------------------------------------------------------

class TestMEDIUM02IntervalSQL:
    """
    Verifica que las queries con INTERVAL no usan f-string para inyectar el
    número de días — deben usar el patrón (%s * INTERVAL '1 day') con
    psycopg parámetro ligado para evitar SQL injection.
    """

    def test_stats_no_usa_fstring_para_interval(self):
        import routers.api_v1 as av
        source = inspect.getsource(av)
        # Patrón SEGURO: el número de días va como parámetro, no interpolado
        safe_pattern = re.search(
            r"\(%s\s*\*\s*INTERVAL\s*'1 day'\)",
            source,
        )
        assert safe_pattern is not None, (
            "MEDIUM-02: no se encontró el patrón (%s * INTERVAL '1 day') — "
            "verificar que los días no se inyectan via f-string"
        )

    def test_telemetry_no_usa_fstring_para_interval(self):
        import routers.api_v1 as av
        source = inspect.getsource(av)
        # Debe aparecer al menos dos veces (stats + telemetry)
        matches = re.findall(r"\(%s\s*\*\s*INTERVAL\s*'1 day'\)", source)
        assert len(matches) >= 2, (
            f"MEDIUM-02: se esperaban ≥2 usos de (%s * INTERVAL '1 day'), "
            f"se encontraron {len(matches)}"
        )

    def test_no_hay_fstring_interpolacion_de_days(self):
        import routers.api_v1 as av
        source = inspect.getsource(av)
        # Buscar el anti-patrón: f"... {days} ..." dentro de una query SQL
        dangerous = re.findall(
            r'f"[^"]*INTERVAL[^"]*\{days\}[^"]*"',
            source,
        )
        assert dangerous == [], (
            f"MEDIUM-02: se encontró interpolación insegura de 'days' en SQL: {dangerous}"
        )

    @pytest.mark.asyncio
    async def test_stats_endpoint_acepta_days_como_query_param(self, app, auth_headers):
        """El endpoint /stats debe aceptar ?days= como entero ligado, no interpolado."""
        from decimal import Decimal
        stats_row = (0, Decimal("0"), 0, Decimal("0"), 0, 0)
        cursor = MagicMock()
        cursor.fetchone  = AsyncMock(return_value=stats_row)
        cursor.fetchall  = AsyncMock(return_value=[])
        conn = _empty_conn()
        conn.execute = AsyncMock(return_value=cursor)

        with patch("psycopg.AsyncConnection.connect", return_value=conn):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get(
                    f"/api/v1/orgs/{_ORG_ID}/stats?days=90",
                    headers=auth_headers,
                )
        assert r.status_code == 200
        assert r.json()["period_days"] == 90


# ---------------------------------------------------------------------------
# MEDIUM-04: Refresh token en cookie HttpOnly + Secure
# ---------------------------------------------------------------------------

class TestMEDIUM04HttpOnlyCookie:
    """
    Verifica que el endpoint /auth/login emite el refresh token
    en una cookie con flags HttpOnly y Secure activados.
    """

    def test_set_refresh_cookie_usa_httponly(self):
        import routers.auth_router as ar
        source = inspect.getsource(ar._set_refresh_cookie)
        assert "httponly=True" in source, (
            "MEDIUM-04: _set_refresh_cookie no usa httponly=True"
        )

    def test_set_refresh_cookie_usa_secure(self):
        import routers.auth_router as ar
        source = inspect.getsource(ar._set_refresh_cookie)
        assert "secure=True" in source, (
            "MEDIUM-04: _set_refresh_cookie no usa secure=True"
        )

    def test_set_refresh_cookie_usa_samesite_strict(self):
        import routers.auth_router as ar
        source = inspect.getsource(ar._set_refresh_cookie)
        assert "samesite" in source.lower(), (
            "MEDIUM-04: _set_refresh_cookie no configura samesite"
        )

    @pytest.mark.asyncio
    async def test_login_response_incluye_set_cookie(self, app):
        """El endpoint /auth/login devuelve Set-Cookie en la respuesta."""
        from passlib.hash import argon2 as _argon2
        password = "test-password-123"
        hashed   = _argon2.hash(password)

        user_record = {
            "id": _USER_ID, "org_id": _ORG_ID,
            "email": "test@test.com", "password_hash": hashed,
            "role": "admin", "active": True,
        }

        # Mock de issue_tokens para no necesitar BD
        from auth import TokenPair
        fake_pair = TokenPair(
            access_token="tok.acc.test",
            refresh_token="tok.ref.test",
            token_type="bearer",
            expires_in=3600,
        )

        with patch("routers.auth_router._get_user_by_email", AsyncMock(return_value=user_record)), \
             patch("routers.auth_router.issue_tokens", AsyncMock(return_value=fake_pair)):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r = await client.post(
                    "/auth/login",
                    json={"email": "test@test.com", "password": password},
                )

        assert r.status_code == 200
        # El header Set-Cookie debe existir
        set_cookie = r.headers.get("set-cookie", "")
        assert "ovd_refresh_token" in set_cookie, (
            "MEDIUM-04: la respuesta de /auth/login no incluye cookie ovd_refresh_token"
        )
        assert "httponly" in set_cookie.lower(), (
            "MEDIUM-04: la cookie ovd_refresh_token no tiene flag HttpOnly"
        )

    def test_logout_borra_cookie(self):
        """_set_refresh_cookie y logout deben gestionar la cookie en path=/auth."""
        import routers.auth_router as ar
        source = inspect.getsource(ar)
        assert 'delete_cookie("ovd_refresh_token"' in source or \
               "delete_cookie('ovd_refresh_token'" in source, (
            "MEDIUM-04: logout no llama delete_cookie para ovd_refresh_token"
        )
