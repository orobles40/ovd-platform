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
    )
