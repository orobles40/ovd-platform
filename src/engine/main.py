"""
OVD Platform — OVD Engine entrypoint
Copyright 2026 Omar Robles
"""
import os
from dotenv import load_dotenv

load_dotenv(".env.local", override=False)

import uvicorn
from api import app  # noqa: F401 — importar para registrar rutas

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8001"))
    log_level = os.environ.get("LOG_LEVEL", "info").lower()

    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=port,
        log_level=log_level,
        reload=os.environ.get("NODE_ENV") == "development",
        # workers=1 es intencional: _graph_tasks, _event_queues y _stream_done
        # son dicts en memoria. Multi-process (Gunicorn) rompería el SSE porque
        # cada proceso tiene su propia copia. Migrar a Redis/NATS primero.
        # Ver docs/PLAN_MANTENIBILIDAD.md — Decisiones arquitectónicas.
        workers=1,
    )
