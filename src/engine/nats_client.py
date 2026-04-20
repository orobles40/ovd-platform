"""
OVD Platform — NATS Client (Sprint 7)
Copyright 2026 Omar Robles

Cliente NATS para publicar eventos del ciclo OVD en JetStream.
Fire-and-forget: si NATS_URL no está configurada o la publicación falla,
el ciclo continúa sin interrupciones.

Subjects publicados:
  ovd.{org_id}.session.started    — ciclo iniciado (analyze_fr)
  ovd.{org_id}.session.approved   — SDD aprobado (request_approval)
  ovd.{org_id}.session.done       — ciclo completado con artefactos (deliver)
  ovd.{org_id}.session.escalated  — ciclo escalado (handle_escalation)
  ovd.{org_id}.session.error      — error no recuperable

El payload de ovd.*.session.done incluye todos los artefactos del ciclo
para que el Bridge los indexe en el RAG del proyecto.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from tenacity import retry, stop_after_attempt, wait_fixed

log = logging.getLogger("ovd-nats")

NATS_URL   = os.environ.get("NATS_URL", "")
NATS_CREDS = os.environ.get("NATS_CREDS_FILE", "")

# Conexión lazy — se crea al primer publish
_nc: Any = None
_lock = asyncio.Lock()


def _is_enabled() -> bool:
    return bool(NATS_URL)


async def _get_connection() -> Any:
    """Obtiene (o crea) la conexión NATS. Retorna None si no está configurada."""
    global _nc
    if not _is_enabled():
        return None

    async with _lock:
        if _nc and _nc.is_connected:
            return _nc
        try:
            import nats as nats_lib
            kwargs: dict = {"servers": [NATS_URL]}
            if NATS_CREDS:
                kwargs["credentials"] = NATS_CREDS
            _nc = await nats_lib.connect(**kwargs)
            log.info("nats_client: conectado a %s", NATS_URL)
            return _nc
        except Exception as e:
            log.warning("nats_client: no se pudo conectar a NATS — %s", e)
            return None


_NATS_MAX_RETRIES = 2
_NATS_BACKOFF_SECS = 1.0
_DATABASE_URL = os.environ.get("DATABASE_URL", "")


@retry(stop=stop_after_attempt(_NATS_MAX_RETRIES + 1), wait=wait_fixed(_NATS_BACKOFF_SECS), reraise=True)
async def _publish_with_retry(nc: Any, subject: str, data: bytes) -> None:
    """Publica en NATS con reintentos. Levanta excepción si agota intentos."""
    await nc.publish(subject, data)


async def _send_to_dlq(subject: str, payload: dict[str, Any], error: str) -> None:
    """
    S20 — GAP-R7: Persiste mensaje fallido en tabla ovd_nats_dlq (dead letter queue).
    Fire-and-forget: si el INSERT falla, solo loguea — nunca bloquea el ciclo.
    """
    if not _DATABASE_URL:
        log.warning("nats_client: DLQ omitida — DATABASE_URL no configurada")
        return
    try:
        import psycopg
        async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
            await conn.execute(
                "INSERT INTO ovd_nats_dlq (subject, payload, error) VALUES (%s, %s, %s)",
                (subject, json.dumps(payload, default=str), error),
            )
            log.info("nats_client: mensaje encolado en DLQ — subject=%s", subject)
    except Exception as dlq_exc:
        log.error("nats_client: DLQ insert falló — %s", dlq_exc)


async def publish(subject: str, payload: dict[str, Any]) -> None:
    """
    Publica un mensaje en NATS. Fire-and-forget: los errores se loggean
    pero no propagan — el ciclo continúa sin interrupciones.

    S20 — GAP-R7: reintenta hasta _NATS_MAX_RETRIES veces con backoff de 1s.
    Si agota todos los reintentos, persiste el mensaje en ovd_nats_dlq.
    """
    if not _is_enabled():
        return

    try:
        nc = await _get_connection()
        if nc is None:
            return
        data = json.dumps(payload, default=str).encode()
        await _publish_with_retry(nc, subject, data)
        log.debug("nats_client: publicado en %s (%d bytes)", subject, len(data))
    except Exception as e:
        log.warning(
            "nats_client: error publicando en %s tras %d intentos — enviando a DLQ — %s",
            subject, _NATS_MAX_RETRIES + 1, e,
        )
        try:
            await _send_to_dlq(subject, payload, str(e))
        except Exception as dlq_exc:
            log.error("nats_client: DLQ también falló para %s — %s", subject, dlq_exc)


async def close() -> None:
    """Cierra la conexión NATS al apagar el engine."""
    global _nc
    if _nc:
        try:
            await _nc.close()
            log.info("nats_client: conexión cerrada")
        except Exception:
            pass
        _nc = None


# ---------------------------------------------------------------------------
# Helpers por tipo de evento — construyen el payload estándar
# ---------------------------------------------------------------------------

def _base_payload(state: dict) -> dict:
    """Campos comunes a todos los eventos."""
    return {
        "session_id":  state.get("session_id", ""),
        "org_id":      state.get("org_id", ""),
        "project_id":  state.get("project_id", ""),
        "feature_request": state.get("feature_request", ""),
    }


async def publish_started(state: dict) -> None:
    org_id = state.get("org_id", "unknown")
    payload = {
        **_base_payload(state),
        "fr_analysis": state.get("fr_analysis", {}),
    }
    await publish(f"ovd.{org_id}.session.started", payload)


async def publish_approved(state: dict) -> None:
    org_id = state.get("org_id", "unknown")
    payload = {
        **_base_payload(state),
        "sdd_summary":        state.get("sdd", {}).get("summary", ""),
        "requirements_count": len(state.get("sdd", {}).get("requirements", [])),
        "tasks_count":        len(state.get("sdd", {}).get("tasks", [])),
        "approval_comment":   state.get("approval_comment", ""),
    }
    await publish(f"ovd.{org_id}.session.approved", payload)


async def publish_done(state: dict, duration_secs: float, cost_usd: float) -> None:
    """
    Payload completo para retroalimentar el RAG en el Bridge.
    Incluye SDD + artefactos de agentes + resultados de calidad.
    Los artefactos de código se truncan a 8KB para no saturar el bus.
    """
    org_id = state.get("org_id", "unknown")
    token_usage = state.get("token_usage", {})
    total_in  = sum(v.get("input", 0)  for v in token_usage.values() if isinstance(v, dict))
    total_out = sum(v.get("output", 0) for v in token_usage.values() if isinstance(v, dict))

    # Truncar código de agentes para no saturar NATS (límite recomendado: 1MB por mensaje)
    agent_results_trimmed = []
    for r in state.get("agent_results", []):
        output = r.get("output", "")
        agent_results_trimmed.append({
            "agent":  r.get("agent", ""),
            "output": output[:8192] + ("\n... [truncado]" if len(output) > 8192 else ""),
            "tokens": r.get("tokens", {}),
        })

    payload = {
        **_base_payload(state),
        # SDD completo para indexar en RAG
        "sdd": state.get("sdd", {}),
        # Artefactos de implementación (truncados)
        "agent_results": agent_results_trimmed,
        # Resultados de calidad
        "security_result": state.get("security_result", {}),
        "qa_result":       state.get("qa_result", {}),
        # Métricas del ciclo
        "token_usage":    {"total_input": total_in, "total_output": total_out},
        "duration_secs":  round(duration_secs, 1),
        "cost_usd":       cost_usd,
        # GitHub PR si fue creado
        "github_pr":      state.get("github_pr", {}),
    }
    await publish(f"ovd.{org_id}.session.done", payload)


async def publish_escalated(state: dict, reason: str) -> None:
    org_id = state.get("org_id", "unknown")
    payload = {
        **_base_payload(state),
        "reason":               reason,
        "security_retry_count": state.get("security_retry_count", 0),
        "qa_retry_count":       state.get("qa_retry_count", 0),
        "escalation_resolution": state.get("escalation_resolution", ""),
    }
    await publish(f"ovd.{org_id}.session.escalated", payload)
