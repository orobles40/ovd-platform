"""
OVD Platform — Audit Logger (Sprint 10 — GAP-A6 / Tabla 0006)
Copyright 2026 Omar Robles

Escribe eventos de auditoría en ovd_audit_logs.
Durante S7 la tabla existía pero estaba vacía — este módulo la activa.

Eventos registrados:
  session_created       — nueva sesión OVD iniciada
  cycle_completed       — ciclo terminado (con qa_score, tokens, duración)
  cycle_approved        — ciclo aprobado por el arquitecto
  cycle_rejected        — ciclo rechazado por el arquitecto
  cycle_escalated       — ciclo escalado a supervisión humana
  secret_accessed       — credenciales recuperadas desde Infisical (sin valores)
  config_changed        — cambio en agent_config o project_profile
  rls_violation_attempt — intento de acceso cross-tenant detectado (seguridad)

Uso:
  from audit_logger import AuditLogger
  await AuditLogger.log(
      event="cycle_completed",
      org_id="org_123",
      resource_type="cycle",
      resource_id=thread_id,
      summary="Ciclo completado — qa_score: 92, tokens: 4821",
  )
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg

log = logging.getLogger(__name__)

_DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Eventos válidos — tipados para evitar typos en los call sites
AUDIT_EVENTS = {
    "session_created",
    "cycle_completed",
    "cycle_approved",
    "cycle_rejected",
    "cycle_escalated",
    "secret_accessed",
    "config_changed",
    "rls_violation_attempt",
    "login",
    "logout",
    "token_refreshed",
    "token_revoked",
}


class AuditLogger:
    """
    Escribe eventos de auditoría en ovd_audit_logs de forma no-bloqueante.

    Diseño:
    - Fire-and-forget: los errores de escritura se loguean pero no propagan
      (una falla de audit log no debe interrumpir un ciclo OVD)
    - Cada evento tiene un ID único y timestamp UTC
    - old_value / new_value: serialización JSON de estados antes/después
    """

    @staticmethod
    async def log(
        event: str,
        org_id: str,
        resource_type: str,
        summary: str,
        resource_id: str | None = None,
        user_id: str | None = None,
        old_value: Any = None,
        new_value: Any = None,
    ) -> None:
        """
        Registra un evento de auditoría.

        Args:
            event:         tipo de evento (ver AUDIT_EVENTS)
            org_id:        organización que realiza la acción
            resource_type: tipo de recurso afectado (cycle, config, session, auth, secret)
            summary:       descripción legible del evento (aparece en UI de auditoría)
            resource_id:   ID del recurso afectado (thread_id, config_id, etc.)
            user_id:       usuario que realizó la acción (None si es acción del sistema)
            old_value:     estado anterior (serializable a JSON)
            new_value:     estado nuevo (serializable a JSON)
        """
        if not _DATABASE_URL:
            log.debug("audit_logger: DATABASE_URL no configurado — evento '%s' no registrado", event)
            return

        if event not in AUDIT_EVENTS:
            log.warning("audit_logger: evento desconocido '%s' — registrando de todas formas", event)

        try:
            await _write_audit_log(
                event=event,
                org_id=org_id,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                summary=summary,
                old_value=json.dumps(old_value, default=str) if old_value is not None else None,
                new_value=json.dumps(new_value, default=str) if new_value is not None else None,
            )
        except Exception as e:
            # Fire-and-forget: log el error pero no interrumpir el flujo
            log.error("audit_logger: error escribiendo evento '%s' — %s", event, e)

    # ── Helpers para eventos específicos ────────────────────────────────────

    @staticmethod
    async def session_created(
        org_id: str, project_id: str, session_id: str, thread_id: str,
        feature_request: str, user_id: str | None = None,
    ) -> None:
        await AuditLogger.log(
            event="session_created",
            org_id=org_id,
            resource_type="session",
            resource_id=thread_id,
            summary=f"Sesión iniciada — project: {project_id} | FR: {feature_request[:80]}",
            user_id=user_id,
            new_value={"session_id": session_id, "thread_id": thread_id, "project_id": project_id},
        )

    @staticmethod
    async def cycle_completed(
        org_id: str, thread_id: str, project_id: str,
        qa_score: int | None, tokens_total: int, duration_secs: float,
        model_routing: str = "auto",
    ) -> None:
        await AuditLogger.log(
            event="cycle_completed",
            org_id=org_id,
            resource_type="cycle",
            resource_id=thread_id,
            summary=(
                f"Ciclo completado — qa_score: {qa_score} | "
                f"tokens: {tokens_total} | duración: {duration_secs:.1f}s | "
                f"modelo: {model_routing}"
            ),
            new_value={
                "thread_id": thread_id,
                "project_id": project_id,
                "qa_score": qa_score,
                "tokens_total": tokens_total,
                "duration_secs": round(duration_secs, 2),
                "model_routing": model_routing,
            },
        )

    @staticmethod
    async def cycle_approved(
        org_id: str, thread_id: str, comment: str | None, user_id: str | None = None,
    ) -> None:
        await AuditLogger.log(
            event="cycle_approved",
            org_id=org_id,
            resource_type="cycle",
            resource_id=thread_id,
            summary=f"Ciclo aprobado{f' — {comment}' if comment else ''}",
            user_id=user_id,
        )

    @staticmethod
    async def cycle_rejected(
        org_id: str, thread_id: str, comment: str | None, user_id: str | None = None,
    ) -> None:
        await AuditLogger.log(
            event="cycle_rejected",
            org_id=org_id,
            resource_type="cycle",
            resource_id=thread_id,
            summary=f"Ciclo rechazado{f' — {comment}' if comment else ''}",
            user_id=user_id,
        )

    @staticmethod
    async def cycle_escalated(
        org_id: str, thread_id: str, reason: str,
    ) -> None:
        await AuditLogger.log(
            event="cycle_escalated",
            org_id=org_id,
            resource_type="cycle",
            resource_id=thread_id,
            summary=f"Ciclo escalado — {reason[:120]}",
        )

    @staticmethod
    async def secret_accessed(
        org_id: str, project_id: str, secret_ref: str, keys_count: int,
    ) -> None:
        """
        Registra acceso a secrets. NUNCA incluir los valores en el log.
        Solo se registra: qué workspace accedió y cuántas claves se recuperaron.
        """
        await AuditLogger.log(
            event="secret_accessed",
            org_id=org_id,
            resource_type="secret",
            resource_id=secret_ref,
            summary=f"Secrets accedidos — project: {project_id} | ref: {secret_ref} | claves: {keys_count}",
            new_value={"project_id": project_id, "secret_ref": secret_ref, "keys_count": keys_count},
        )


# ---------------------------------------------------------------------------
# Escritura a BD (async, no-bloqueante)
# ---------------------------------------------------------------------------

async def _write_audit_log(
    event: str,
    org_id: str,
    user_id: str | None,
    resource_type: str,
    resource_id: str | None,
    summary: str,
    old_value: str | None,
    new_value: str | None,
) -> None:
    """Inserta un registro en ovd_audit_logs."""
    log_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
        await conn.execute(
            """
            INSERT INTO ovd_audit_logs
              (id, org_id, user_id, action, resource_type, resource_id, summary, old_value, new_value, time_created)
            VALUES
              (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (log_id, org_id, user_id, event, resource_type, resource_id, summary, old_value, new_value, now),
        )
        await conn.commit()
