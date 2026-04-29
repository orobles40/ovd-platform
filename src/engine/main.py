"""
OVD Platform — OVD Engine entrypoint
Copyright 2026 Omar Robles
"""

from dotenv import load_dotenv

load_dotenv(".env.local", override=False)

import uvicorn

from api import app  # noqa: F401 — importar para registrar rutas
from settings import get_settings

if __name__ == "__main__":
    _s = get_settings()

    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=_s.port,
        log_level=_s.log_level.lower(),
        reload=_s.node_env == "development",
        # workers=1 es intencional: _graph_tasks, _event_queues y _stream_done
        # son dicts en memoria. Multi-process (Gunicorn) rompería el SSE porque
        # cada proceso tiene su propia copia. Migrar a Redis/NATS primero.
        # Ver docs/PLAN_MANTENIBILIDAD.md — Decisiones arquitectónicas.
        workers=1,
    )
