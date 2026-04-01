"""
OVD Platform Python SDK
Copyright 2026 Omar Robles

Cliente Python para la API OVD Platform.

Uso básico:
    from ovd_client import OvdClient

    client = OvdClient(base_url="https://api.ovd.omarrobles.devoud")
    client.auth.login(email="admin@example.com", password="secret")

    # Iniciar un ciclo OVD
    session = client.cycles.start(
        session_id="sess_001",
        project_id="proj_001",
        directory="/app",
        feature_request="Agregar autenticación OAuth2",
    )

    # Streaming de eventos SSE
    for event in client.cycles.stream_events(session["thread_id"]):
        print(event)
"""

from .client import OvdClient, OvdApiError

__all__ = ["OvdClient", "OvdApiError"]
__version__ = "0.1.0"
