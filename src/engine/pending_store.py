"""
OVD Platform — Almacén en memoria de sesiones con aprobación pendiente.

Singleton de módulo — compartido entre api.py y api_v1.py sin imports circulares.
Se limpia en memory ante restart del engine; los threads siguen en el checkpointer.
"""
from __future__ import annotations

import time
from typing import Any

# Clave: thread_id   Valor: dict con todos los datos de la aprobación pendiente
_store: dict[str, dict[str, Any]] = {}


def add(thread_id: str, data: dict[str, Any]) -> None:
    """Registra un thread como pendiente de aprobación."""
    _store[thread_id] = {**data, "stored_at": time.time()}


def remove(thread_id: str) -> None:
    """Elimina el thread del almacén (tras aprobar/rechazar)."""
    _store.pop(thread_id, None)


def list_by_org(org_id: str) -> list[dict[str, Any]]:
    """Retorna todas las aprobaciones pendientes de un org."""
    return [v for v in _store.values() if v.get("org_id") == org_id]


def get(thread_id: str) -> dict[str, Any] | None:
    return _store.get(thread_id)
