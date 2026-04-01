"""
OVD Platform — PostgreSQL Checkpointer para LangGraph
Copyright 2026 Omar Robles

Gestiona la persistencia del estado del grafo LangGraph en PostgreSQL.
Permite resumir sesiones interrumpidas (human_approval, escalacion, reinicio).

La tabla que usa LangGraph se llama 'checkpoints' — creada automaticamente
por langgraph-checkpoint-postgres al iniciar.
"""
from __future__ import annotations
import os
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise EnvironmentError("DATABASE_URL no configurada")
    return url


def checkpointer_context(url: str | None = None):
    """
    Retorna el context manager del checkpointer PostgreSQL asincronico.
    Usar con 'async with' en el lifespan de FastAPI:

        async with checkpointer_context() as cp:
            await cp.setup()
            graph = build_graph(cp)
            yield  # app corre aqui
    """
    return AsyncPostgresSaver.from_conn_string(url or get_database_url())
