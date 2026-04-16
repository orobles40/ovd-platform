"""
OVD Platform — PP-03 + PP-02: Atomic Task Checkout + Heartbeat / Stale Detection
Copyright 2026 Omar Robles

Coordina el acceso exclusivo a sesiones activas usando pg_advisory_lock.
Previene que dos instancias del engine procesen el mismo thread_id en paralelo.

PostgreSQL advisory locks (session-level):
  - pg_try_advisory_lock(key)  — intenta adquirir; retorna False si ya está tomado
  - pg_advisory_unlock(key)    — libera explícitamente

El lock se mantiene activo durante todo el streaming SSE (la conexión psycopg
se mantiene abierta). Se libera al salir del context manager, ya sea por
completar el ciclo, por error o por desconexión del cliente.

Uso:
    from task_checkout import SessionLock, AlreadyRunningError

    try:
        async with SessionLock(thread_id):
            # ejecutar el grafo
    except AlreadyRunningError:
        # responder 409 al cliente
"""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone

import psycopg

log = logging.getLogger("ovd.checkout")

_DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Umbral de sesión colgada (minutos). Configurable via env var.
_STALE_THRESHOLD_MINUTES = int(os.environ.get("OVD_STALE_SESSION_MINUTES", "30"))

# ---------------------------------------------------------------------------
# PP-05 — Registro en memoria de sesiones activas
# PP-02 — Detección de sesiones colgadas (stale)
# ---------------------------------------------------------------------------

_active_sessions: dict[str, dict] = {}
_stale_sessions:  dict[str, dict] = {}   # thread_id → metadata + detected_at


def register_session(thread_id: str, metadata: dict) -> None:
    """Registra una sesión como activa. Llamar al inicio del stream."""
    _active_sessions[thread_id] = {
        **metadata,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    # Si estaba en stale por un restart, limpiar
    _stale_sessions.pop(thread_id, None)


def unregister_session(thread_id: str) -> None:
    """Elimina una sesión del registro activo y stale. Llamar al finalizar el stream."""
    _active_sessions.pop(thread_id, None)
    _stale_sessions.pop(thread_id, None)


def list_active_sessions(org_id: str | None = None) -> list[dict]:
    """Retorna las sesiones activas, opcionalmente filtradas por org_id."""
    sessions = [{"thread_id": tid, **meta} for tid, meta in _active_sessions.items()]
    if org_id:
        sessions = [s for s in sessions if s.get("org_id") == org_id]
    return sessions


# ---------------------------------------------------------------------------
# PP-02 — Detección de stale sessions
# ---------------------------------------------------------------------------

def detect_stale_sessions(threshold_minutes: int = _STALE_THRESHOLD_MINUTES) -> list[dict]:
    """
    Revisa _active_sessions y marca como stale las que superan el umbral.
    Retorna la lista de sesiones colgadas detectadas en esta pasada.
    Llamar periódicamente desde el watcher de background.
    """
    now      = datetime.now(timezone.utc)
    cutoff   = now - timedelta(minutes=threshold_minutes)
    detected = []

    for tid, meta in list(_active_sessions.items()):
        started_str = meta.get("started_at", "")
        try:
            started = datetime.fromisoformat(started_str)
        except (ValueError, TypeError):
            continue

        if started < cutoff and tid not in _stale_sessions:
            stale_entry = {
                **meta,
                "detected_at":         now.isoformat(),
                "elapsed_minutes":     int((now - started).total_seconds() / 60),
                "threshold_minutes":   threshold_minutes,
            }
            _stale_sessions[tid] = stale_entry
            log.warning(
                "heartbeat: sesión colgada detectada — thread=%s elapsed=%dmin org=%s fr=%r",
                tid,
                stale_entry["elapsed_minutes"],
                meta.get("org_id", ""),
                (meta.get("feature_request") or "")[:60],
            )
            detected.append({"thread_id": tid, **stale_entry})

    return detected


def list_stale_sessions(org_id: str | None = None) -> list[dict]:
    """Retorna sesiones marcadas como colgadas, opcionalmente filtradas por org_id."""
    sessions = [{"thread_id": tid, **meta} for tid, meta in _stale_sessions.items()]
    if org_id:
        sessions = [s for s in sessions if s.get("org_id") == org_id]
    return sessions


def _lock_key(thread_id: str) -> int:
    """
    Convierte thread_id (UUID string) a un bigint de 63 bits para pg_advisory_lock.
    Usa los primeros 8 bytes del SHA-256 y lo fuerza a positivo (signed 64-bit).
    """
    digest = hashlib.sha256(thread_id.encode()).digest()
    raw = int.from_bytes(digest[:8], "big")
    return raw % (2**63)  # PostgreSQL bigint es signed; mantenemos positivo


class AlreadyRunningError(Exception):
    """El thread_id ya está siendo procesado por otra instancia del engine."""


class SessionLock:
    """
    Async context manager que adquiere un pg_advisory_lock al entrar
    y lo libera al salir (incluso ante excepciones o cancelación).

    Si el lock no está disponible, levanta AlreadyRunningError inmediatamente
    (no bloquea — usa pg_try_advisory_lock, no pg_advisory_lock).
    """

    def __init__(self, thread_id: str):
        self._thread_id = thread_id
        self._key       = _lock_key(thread_id)
        self._conn: psycopg.AsyncConnection | None = None

    async def __aenter__(self) -> "SessionLock":
        if not _DATABASE_URL:
            # Sin DB configurada: modo sin lock (dev local sin postgres)
            log.debug("checkout: DATABASE_URL no definida — lock omitido para %s", self._thread_id)
            return self

        conn = await psycopg.AsyncConnection.connect(_DATABASE_URL)
        try:
            row = await conn.execute("SELECT pg_try_advisory_lock(%s)", (self._key,))
            result = await row.fetchone()
            acquired = bool(result[0]) if result else False
        except Exception:
            await conn.close()
            raise

        if not acquired:
            await conn.close()
            log.warning("checkout: thread %s ya está activo (key=%d)", self._thread_id, self._key)
            raise AlreadyRunningError(
                f"El ciclo {self._thread_id!r} ya está siendo procesado por otra instancia."
            )

        self._conn = conn
        log.debug("checkout: lock adquirido para %s (key=%d)", self._thread_id, self._key)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._conn is not None:
            try:
                await self._conn.execute("SELECT pg_advisory_unlock(%s)", (self._key,))
                await self._conn.commit()
                log.debug("checkout: lock liberado para %s", self._thread_id)
            except Exception as e:
                log.warning("checkout: error al liberar lock para %s — %s", self._thread_id, e)
            finally:
                await self._conn.close()
                self._conn = None
        return False  # no suprimir excepciones
