"""
OVD Platform — Auth Router (S12.A)
Copyright 2026 Omar Robles

Endpoints públicos de autenticación:
  POST /auth/login    — email + password → access_token + refresh_token
  POST /auth/refresh  — rota el refresh token
  POST /auth/logout   — revoca el refresh token
  GET  /auth/me       — retorna el payload del access token

Dependencia JWT: inject_current_user() → usa para rutas protegidas de API.
"""
from __future__ import annotations

import logging
import os

import psycopg
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.hash import argon2 as _argon2_hash
from pydantic import BaseModel

from auth import (
    AccessTokenPayload,
    TokenPair,
    issue_tokens,
    refresh_access_token,
    revoke_refresh_token,
    verify_access_token,
)

log = logging.getLogger(__name__)

_DATABASE_URL = os.environ.get("DATABASE_URL", "")

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Modelos de request/response
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class MeResponse(BaseModel):
    user_id: str
    org_id: str
    role: str
    email: str


# ---------------------------------------------------------------------------
# Helper: lookup usuario en BD
# ---------------------------------------------------------------------------

async def _get_user_by_email(email: str, org_id: str | None = None) -> dict | None:
    """Retorna la fila de ovd_users o None si no existe."""
    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        if org_id:
            row = await conn.execute(
                "SELECT id, org_id, email, password_hash, role, active "
                "FROM ovd_users WHERE email = %s AND org_id = %s",
                (email, org_id),
            )
        else:
            row = await conn.execute(
                "SELECT id, org_id, email, password_hash, role, active "
                "FROM ovd_users WHERE email = %s LIMIT 1",
                (email,),
            )
        record = await row.fetchone()

    if not record:
        return None

    return {
        "id":            record[0],
        "org_id":        record[1],
        "email":         record[2],
        "password_hash": record[3],
        "role":          record[4],
        "active":        record[5],
    }


# ---------------------------------------------------------------------------
# Dependencia reutilizable: usuario autenticado
# ---------------------------------------------------------------------------

async def inject_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AccessTokenPayload:
    """
    Dependencia FastAPI: extrae y valida el Bearer token.
    Inyectar en rutas protegidas con: Depends(inject_current_user)
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acceso requerido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return verify_access_token(credentials.credentials)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

_COOKIE_MAX_AGE = 7 * 24 * 3600  # 7 días en segundos


def _set_refresh_cookie(response: Response, token: str) -> None:
    """Establece el refresh token como cookie HttpOnly."""
    response.set_cookie(
        key="ovd_refresh_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=_COOKIE_MAX_AGE,
        path="/auth",
    )


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, response: Response):
    """
    Autentica al usuario con email + contraseña.
    Retorna access_token (JWT, 1h). El refresh_token se emite en cookie
    HttpOnly (MEDIUM-04) y también en el body para compatibilidad con el TUI.
    """
    user = await _get_user_by_email(body.email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    if not user["active"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario inactivo")

    # Verificar contraseña (argon2id o bcrypt según hash almacenado)
    try:
        pwd_ok = _argon2_hash.verify(body.password, user["password_hash"])
    except Exception:
        # Fallback: bcrypt si el hash no es argon2
        try:
            from passlib.hash import bcrypt as _bcrypt
            pwd_ok = _bcrypt.verify(body.password, user["password_hash"])
        except Exception:
            pwd_ok = False

    if not pwd_ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    user_agent = request.headers.get("User-Agent", "")
    ip = request.client.host if request.client else ""

    pair: TokenPair = await issue_tokens(
        user_id=user["id"],
        org_id=user["org_id"],
        role=user["role"],
        user_agent=user_agent,
        ip_address=ip,
    )

    log.info("auth: login exitoso — email=%s org=%s", body.email, user["org_id"])

    _set_refresh_cookie(response, pair.refresh_token)
    return LoginResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        token_type=pair.token_type,
        expires_in=pair.expires_in,
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh(
    request: Request,
    response: Response,
    body: RefreshRequest | None = None,
    ovd_refresh_token: str | None = Cookie(default=None),
):
    """Rota el refresh token y emite un nuevo par de tokens.
    Acepta el token desde cookie HttpOnly (web) o body (TUI).
    """
    raw_token = (body.refresh_token if body else None) or ovd_refresh_token
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token requerido")
    try:
        from auth import verify_refresh_token
        record = await verify_refresh_token(raw_token)

        async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
            row = await conn.execute(
                "SELECT role FROM ovd_users WHERE id = %s", (record["user_id"],)
            )
            r = await row.fetchone()
        role = r[0] if r else "developer"

        pair = await refresh_access_token(
            raw_refresh_token=raw_token,
            role=role,
            user_agent=request.headers.get("User-Agent", ""),
            ip_address=request.client.host if request.client else "",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    _set_refresh_cookie(response, pair.refresh_token)
    return LoginResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        token_type=pair.token_type,
        expires_in=pair.expires_in,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    body: RefreshRequest | None = None,
    ovd_refresh_token: str | None = Cookie(default=None),
):
    """Revoca el refresh token (logout).
    Acepta el token desde cookie HttpOnly (web) o body (TUI).
    """
    raw_token = (body.refresh_token if body else None) or ovd_refresh_token
    if raw_token:
        await revoke_refresh_token(raw_token, reason="logout")
    response.delete_cookie("ovd_refresh_token", path="/auth")


@router.get("/me", response_model=MeResponse)
async def me(current_user: AccessTokenPayload = Depends(inject_current_user)):
    """Retorna los datos del usuario autenticado (decodificados del JWT)."""
    # Buscar email en BD para completar la respuesta
    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        row = await conn.execute(
            "SELECT email FROM ovd_users WHERE id = %s AND org_id = %s",
            (current_user.sub, current_user.org_id),
        )
        r = await row.fetchone()

    return MeResponse(
        user_id=current_user.sub,
        org_id=current_user.org_id,
        role=current_user.role,
        email=r[0] if r else "",
    )
