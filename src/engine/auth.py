"""
OVD Platform — Auth Module (Sprint 10 — GAP-A5)
Copyright 2026 Omar Robles

Gestión de access tokens (JWT) y refresh tokens para el sistema OVD.
Base para el reemplazo del Bridge TypeScript en Fase B.

Modelo:
  Access token:  JWT HS256, TTL 1 hora, stateless (no se almacena en BD)
  Refresh token: UUID opaco (v4), TTL 7 días, almacenado con hash en ovd_refresh_tokens

Flujo:
  1. POST /auth/login → issue_tokens() → {access_token, refresh_token, expires_in}
  2. POST /auth/refresh → refresh_access_token() → {access_token, refresh_token (rotado)}
  3. POST /auth/logout → revoke_refresh_token() → invalida el refresh token

Seguridad:
  - El refresh token nunca se almacena en texto plano (SHA-256 en BD)
  - Rotación: cada /auth/refresh emite un token nuevo y revoca el anterior
  - Expiración: los tokens vencidos son rechazados independientemente del hash
  - JWT_SECRET: mínimo 32 caracteres, configurado en variable de entorno

Endpoints (a implementar en api.py Fase B):
  POST /auth/login
  POST /auth/refresh
  POST /auth/logout
  POST /auth/me  ← verifica access token y devuelve payload
"""
from __future__ import annotations

import hashlib
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import psycopg
from jose import JWTError, jwt
from pydantic import BaseModel

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

_JWT_SECRET    = os.environ.get("JWT_SECRET", "")
_JWT_ALGORITHM = "HS256"
_ACCESS_TOKEN_TTL_HOURS   = int(os.environ.get("OVD_ACCESS_TOKEN_TTL_HOURS",  "1"))
_REFRESH_TOKEN_TTL_DAYS   = int(os.environ.get("OVD_REFRESH_TOKEN_TTL_DAYS",  "7"))
_DATABASE_URL             = os.environ.get("DATABASE_URL", "")


def _require_jwt_secret() -> str:
    if not _JWT_SECRET or len(_JWT_SECRET) < 32:
        raise RuntimeError(
            "JWT_SECRET no configurado o demasiado corto (mínimo 32 caracteres). "
            "Generar con: openssl rand -hex 32"
        )
    return _JWT_SECRET


# ---------------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------------

@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = _ACCESS_TOKEN_TTL_HOURS * 3600  # segundos


class AccessTokenPayload(BaseModel):
    sub: str          # user_id
    org_id: str
    role: str         # admin | developer | viewer
    exp: int          # Unix timestamp de expiración
    iat: int          # Unix timestamp de emisión


# ---------------------------------------------------------------------------
# Access Token (JWT)
# ---------------------------------------------------------------------------

def create_access_token(user_id: str, org_id: str, role: str) -> str:
    """
    Emite un JWT de acceso con TTL de 1 hora.
    Stateless: no se almacena en BD.
    """
    secret = _require_jwt_secret()
    now = datetime.now(timezone.utc)
    payload = {
        "sub":    user_id,
        "org_id": org_id,
        "role":   role,
        "iat":    int(now.timestamp()),
        "exp":    int((now + timedelta(hours=_ACCESS_TOKEN_TTL_HOURS)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=_JWT_ALGORITHM)


def verify_access_token(token: str) -> AccessTokenPayload:
    """
    Verifica y decodifica un access token JWT.
    Lanza JWTError si el token es inválido o expirado.
    """
    secret = _require_jwt_secret()
    try:
        payload = jwt.decode(token, secret, algorithms=[_JWT_ALGORITHM])
        return AccessTokenPayload(**payload)
    except JWTError as e:
        raise ValueError(f"Token inválido o expirado: {e}") from e


# ---------------------------------------------------------------------------
# Refresh Token
# ---------------------------------------------------------------------------

def _hash_token(raw_token: str) -> str:
    """SHA-256 del token crudo. Solo el hash se almacena en BD."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


async def create_refresh_token(
    user_id: str,
    org_id: str,
    user_agent: str = "",
    ip_address: str = "",
) -> str:
    """
    Genera y persiste un nuevo refresh token.
    Devuelve el token crudo (enviarlo al cliente, nunca almacenarlo localmente).
    """
    raw_token  = str(uuid.uuid4())
    token_hash = _hash_token(raw_token)
    token_id   = str(uuid.uuid4())
    now        = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=_REFRESH_TOKEN_TTL_DAYS)

    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        await conn.execute(
            """
            INSERT INTO ovd_refresh_tokens
              (id, org_id, user_id, token_hash, user_agent, ip_address, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (token_id, org_id, user_id, token_hash, user_agent or None, ip_address or None, expires_at),
        )
        await conn.commit()

    log.info("auth: refresh token creado para user=%s org=%s expires=%s", user_id, org_id, expires_at.date())
    return raw_token


async def verify_refresh_token(raw_token: str) -> dict:
    """
    Verifica que el refresh token existe, no está revocado y no ha expirado.
    Devuelve la fila de ovd_refresh_tokens como dict.
    Lanza ValueError si el token no es válido.
    """
    token_hash = _hash_token(raw_token)
    now = datetime.now(timezone.utc)

    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        row = await conn.execute(
            """
            SELECT id, org_id, user_id, expires_at, revoked, revoked_reason
            FROM ovd_refresh_tokens
            WHERE token_hash = %s
            """,
            (token_hash,),
        )
        record = await row.fetchone()

    if not record:
        raise ValueError("Refresh token no encontrado")

    token_id, org_id, user_id, expires_at, revoked, revoked_reason = record

    if revoked:
        log.warning("auth: intento de uso de refresh token revocado — user=%s reason=%s", user_id, revoked_reason)
        raise ValueError(f"Refresh token revocado: {revoked_reason}")

    if expires_at < now:
        raise ValueError("Refresh token expirado")

    return {
        "id":         token_id,
        "org_id":     org_id,
        "user_id":    user_id,
        "expires_at": expires_at,
    }


async def revoke_refresh_token(raw_token: str, reason: str = "logout") -> None:
    """
    Revoca un refresh token (logout o rotación).
    No-op si el token no existe.
    """
    token_hash = _hash_token(raw_token)
    now = datetime.now(timezone.utc)

    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        result = await conn.execute(
            """
            UPDATE ovd_refresh_tokens
            SET revoked = true, revoked_at = %s, revoked_reason = %s
            WHERE token_hash = %s AND revoked = false
            """,
            (now, reason, token_hash),
        )
        await conn.commit()
        rows_updated = result.rowcount

    if rows_updated > 0:
        log.info("auth: refresh token revocado — reason=%s", reason)


async def revoke_all_user_tokens(user_id: str, org_id: str, reason: str = "admin") -> int:
    """
    Revoca todos los refresh tokens activos de un usuario.
    Útil en cambio de contraseña o revocación de emergencia.
    Devuelve el número de tokens revocados.
    """
    now = datetime.now(timezone.utc)

    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        result = await conn.execute(
            """
            UPDATE ovd_refresh_tokens
            SET revoked = true, revoked_at = %s, revoked_reason = %s
            WHERE user_id = %s AND org_id = %s AND revoked = false
            """,
            (now, reason, user_id, org_id),
        )
        await conn.commit()
        count = result.rowcount

    log.info("auth: %d tokens revocados para user=%s reason=%s", count, user_id, reason)
    return count


# ---------------------------------------------------------------------------
# Flujo completo: issue + refresh
# ---------------------------------------------------------------------------

async def issue_tokens(
    user_id: str,
    org_id: str,
    role: str,
    user_agent: str = "",
    ip_address: str = "",
) -> TokenPair:
    """
    Emite un par completo (access + refresh) para un login exitoso.
    Llamar desde el endpoint POST /auth/login tras verificar credenciales.
    """
    access  = create_access_token(user_id, org_id, role)
    refresh = await create_refresh_token(user_id, org_id, user_agent, ip_address)
    return TokenPair(access_token=access, refresh_token=refresh)


async def refresh_access_token(
    raw_refresh_token: str,
    role: str,
    user_agent: str = "",
    ip_address: str = "",
) -> TokenPair:
    """
    Rota el refresh token y emite nuevos tokens.
    El token anterior queda revocado con reason='rotation'.

    Flujo seguro:
      1. Verificar token actual
      2. Emitir nuevo par
      3. Revocar token anterior
    El orden garantiza que si el paso 2 falla, el token anterior sigue válido.
    """
    # 1. Verificar token actual
    record = await verify_refresh_token(raw_refresh_token)

    # 2. Emitir nuevo par
    new_pair = await issue_tokens(
        user_id=record["user_id"],
        org_id=record["org_id"],
        role=role,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    # 3. Revocar token anterior (rotación)
    await revoke_refresh_token(raw_refresh_token, reason="rotation")

    log.info("auth: tokens rotados para user=%s", record["user_id"])
    return new_pair


async def cleanup_expired_tokens() -> int:
    """
    Elimina tokens expirados de la BD (job periódico sugerido: 1x/día).
    Devuelve el número de tokens eliminados.
    """
    now = datetime.now(timezone.utc)
    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        result = await conn.execute(
            "DELETE FROM ovd_refresh_tokens WHERE expires_at < %s",
            (now,),
        )
        await conn.commit()
        count = result.rowcount

    if count > 0:
        log.info("auth: %d refresh tokens expirados eliminados", count)
    return count
