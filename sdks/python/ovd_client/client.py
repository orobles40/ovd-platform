"""
OVD Platform Python SDK — Cliente principal
Copyright 2026 Omar Robles

Cliente HTTP tipado para la API OVD Platform (/v1/).
Espeja la estructura del SDK TypeScript (packages/sdk/js/src/ovd/client.ts).

Dependencias:
    pip install httpx sseclient-py

Todos los métodos que retornan datos JSON devuelven dict[str, Any].
Los métodos de streaming devuelven iteradores de dict.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Generator, Iterator, Optional

try:
    import httpx
except ImportError:
    raise ImportError("Instalar dependencia: pip install httpx")


# ---------------------------------------------------------------------------
# Tipos y errores
# ---------------------------------------------------------------------------

class OvdApiError(Exception):
    """Error de la API OVD con código HTTP y path."""

    def __init__(self, message: str, status: int, path: str = ""):
        super().__init__(message)
        self.status = status
        self.path = path

    def __repr__(self) -> str:
        return f"OvdApiError(status={self.status}, path={self.path!r}, message={str(self)!r})"


# ---------------------------------------------------------------------------
# HTTP client interno
# ---------------------------------------------------------------------------

class _OvdHttpClient:
    """Cliente HTTP base con autenticación Bearer."""

    def __init__(self, base_url: str, timeout: float = 30.0, api_version: str = "v1"):
        self._base = base_url.rstrip("/")
        self._prefix = f"/{api_version}"
        self._token: Optional[str] = None
        self._http = httpx.Client(timeout=timeout)

    def set_token(self, token: str) -> None:
        self._token = token

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {"Content-Type": "application/json"}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self._base}{self._prefix}{path}"
        resp = self._http.request(method, url, headers=self._headers(), **kwargs)
        if not resp.is_success:
            try:
                detail = resp.json().get("message", resp.text)
            except Exception:
                detail = resp.text
            raise OvdApiError(detail, resp.status_code, path)
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    def stream(self, path: str) -> Iterator[dict[str, Any]]:
        """Iterador de eventos SSE desde el endpoint de streaming."""
        url = f"{self._base}{self._prefix}{path}"
        with self._http.stream("GET", url, headers=self._headers()) as resp:
            if not resp.is_success:
                raise OvdApiError(f"SSE stream error {resp.status_code}", resp.status_code, path)
            for line in resp.iter_lines():
                line = line.strip()
                if line.startswith("data:"):
                    raw = line[5:].strip()
                    if raw and raw != "[DONE]":
                        try:
                            yield json.loads(raw)
                        except json.JSONDecodeError:
                            pass

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "_OvdHttpClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Recursos
# ---------------------------------------------------------------------------

class AuthResource:
    """Autenticación — login y bootstrap de org."""

    def __init__(self, http: _OvdHttpClient):
        self._http = http

    def login(self, email: str, password: str) -> dict[str, Any]:
        """
        Inicia sesión y almacena el token JWT para las siguientes llamadas.
        Retorna: { token, user: { id, org_id, role } }
        """
        data = self._http.request("POST", "/auth/login", json={"email": email, "password": password})
        if token := data.get("token"):
            self._http.set_token(token)
        return data

    def create_org(self, org_name: str, org_slug: str, admin_email: str, admin_password: str) -> dict[str, Any]:
        """
        Crea una organización nueva con su primer usuario admin.
        Retorna: { token, org: { id, slug }, user: { id } }
        """
        data = self._http.request("POST", "/tenant/org", json={
            "org_name": org_name,
            "org_slug": org_slug,
            "admin_email": admin_email,
            "admin_password": admin_password,
        })
        if token := data.get("token"):
            self._http.set_token(token)
        return data


class UsersResource:
    """Gestión de usuarios de la org."""

    def __init__(self, http: _OvdHttpClient):
        self._http = http

    def list(self) -> list[dict[str, Any]]:
        return self._http.request("GET", "/tenant/users").get("users", [])

    def invite(self, email: str, role: str = "developer") -> dict[str, Any]:
        return self._http.request("POST", "/tenant/users", json={"email": email, "role": role})

    def update_role(self, user_id: str, role: str) -> dict[str, Any]:
        return self._http.request("PATCH", f"/tenant/users/{user_id}/role", json={"role": role})

    def deactivate(self, user_id: str) -> dict[str, Any]:
        return self._http.request("DELETE", f"/tenant/users/{user_id}")


class ProjectsResource:
    """Gestión de proyectos de la org."""

    def __init__(self, http: _OvdHttpClient):
        self._http = http

    def list(self) -> list[dict[str, Any]]:
        return self._http.request("GET", "/tenant/project").get("projects", [])

    def create(self, name: str, directory: str, description: str = "") -> dict[str, Any]:
        return self._http.request("POST", "/tenant/project", json={
            "name": name, "directory": directory, "description": description,
        })

    def delete(self, project_id: str) -> dict[str, Any]:
        return self._http.request("DELETE", f"/tenant/project/{project_id}")


class WebhooksResource:
    """Gestión de webhooks y verificación de firmas HMAC-SHA256."""

    def __init__(self, http: _OvdHttpClient):
        self._http = http

    def list(self) -> list[dict[str, Any]]:
        return self._http.request("GET", "/tenant/webhooks").get("webhooks", [])

    def create(self, url: str, secret: str, events: list[str]) -> dict[str, Any]:
        return self._http.request("POST", "/tenant/webhooks", json={
            "url": url, "secret": secret, "events": events,
        })

    def update(self, webhook_id: str, **fields: Any) -> dict[str, Any]:
        return self._http.request("PATCH", f"/tenant/webhooks/{webhook_id}", json=fields)

    def delete(self, webhook_id: str) -> dict[str, Any]:
        return self._http.request("DELETE", f"/tenant/webhooks/{webhook_id}")

    @staticmethod
    def verify_signature(payload: str, secret: str, signature: str) -> bool:
        """
        Verifica la firma HMAC-SHA256 de un webhook entrante.

        Args:
            payload:   Cuerpo del request como string.
            secret:    Secret configurado al crear el webhook.
            signature: Valor del header X-OVD-Signature (formato: sha256=<hex>).

        Returns:
            True si la firma es válida.

        Ejemplo:
            from flask import request
            if not WebhooksResource.verify_signature(
                request.get_data(as_text=True),
                "my-secret",
                request.headers["X-OVD-Signature"],
            ):
                abort(403)
        """
        if not signature or not signature.startswith("sha256="):
            return False
        expected = "sha256=" + hmac.new(
            secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)


class CyclesResource:
    """Ciclos OVD — iniciar sesiones y consumir eventos SSE."""

    def __init__(self, http: _OvdHttpClient):
        self._http = http

    def start(
        self,
        session_id: str,
        project_id: str,
        directory: str,
        feature_request: str,
        parent_thread_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Inicia una sesión OVD en el Engine.
        Retorna: { thread_id, session_id, status }
        """
        body: dict[str, Any] = {
            "sessionId": session_id,
            "projectId": project_id,
            "directory": directory,
            "featureRequest": feature_request,
        }
        if parent_thread_id:
            body["parentThreadId"] = parent_thread_id
        return self._http.request("POST", "/ovd/session", json=body)

    def get(self, session_id: str) -> dict[str, Any]:
        """Estado de la sesión OVD."""
        return self._http.request("GET", f"/ovd/session/{session_id}")

    def stream_events(self, session_id: str) -> Iterator[dict[str, Any]]:
        """
        Stream SSE de eventos del ciclo OVD.
        Itera sobre: message, pending_approval, done, error.

        Ejemplo:
            for event in client.cycles.stream_events("sess_001"):
                if event["type"] == "done":
                    print("Ciclo completado:", event["data"]["summary"])
                elif event["type"] == "message":
                    print("Agente:", event["data"]["content"])
        """
        return self._http.stream(f"/ovd/sessions/{session_id}/events")

    def approve(self, session_id: str, approved: bool, comment: str = "") -> dict[str, Any]:
        """Aprueba o rechaza una acción pendiente de human_approval."""
        return self._http.request("POST", f"/ovd/session/{session_id}/approve", json={
            "approved": approved,
            "comment": comment,
        })

    def escalate(self, session_id: str, reason: str) -> dict[str, Any]:
        """Escala el ciclo a supervisión humana."""
        return self._http.request("POST", f"/ovd/session/{session_id}/escalate", json={"reason": reason})


class MetricsResource:
    """Métricas de uso y billing."""

    def __init__(self, http: _OvdHttpClient):
        self._http = http

    def costs(self, days: int = 30) -> dict[str, Any]:
        """Costo estimado y tokens del período indicado."""
        return self._http.request("GET", f"/dashboard/api/costs?days={days}")

    def billing(self) -> dict[str, Any]:
        """Cuota mensual vs uso del mes en curso con % consumido."""
        return self._http.request("GET", "/dashboard/api/billing")

    def stats(self) -> dict[str, Any]:
        """Estadísticas generales del dashboard (ciclos, sesiones, QA scores)."""
        return self._http.request("GET", "/dashboard/api/stats")


class AuditResource:
    """Logs de auditoría."""

    def __init__(self, http: _OvdHttpClient):
        self._http = http

    def list(self, resource_type: Optional[str] = None) -> list[dict[str, Any]]:
        """Lista entradas de auditoría. Solo admin."""
        path = "/tenant/audit-logs"
        if resource_type:
            path += f"?resource_type={resource_type}"
        return self._http.request("GET", path).get("logs", [])


# ---------------------------------------------------------------------------
# Cliente principal
# ---------------------------------------------------------------------------

class OvdClient:
    """
    Cliente principal de la OVD Platform API.

    Ejemplo completo:
        client = OvdClient("https://api.ovd.omarrobles.devoud")
        client.auth.login("admin@org.com", "password")

        # Iniciar ciclo
        session = client.cycles.start(
            session_id="sess_abc",
            project_id="proj_001",
            directory="/app",
            feature_request="Agregar endpoint POST /items con validación Zod",
        )

        # Consumir eventos
        for ev in client.cycles.stream_events(session["session_id"]):
            if ev.get("type") == "done":
                print("Completado:", ev["data"]["summary"])
                break

        # Ver billing
        print(client.metrics.billing())
    """

    def __init__(
        self,
        base_url: str,
        token: Optional[str] = None,
        timeout: float = 30.0,
        api_version: str = "v1",
    ):
        self._http = _OvdHttpClient(base_url, timeout=timeout, api_version=api_version)
        if token:
            self._http.set_token(token)

        self.auth = AuthResource(self._http)
        self.users = UsersResource(self._http)
        self.projects = ProjectsResource(self._http)
        self.webhooks = WebhooksResource(self._http)
        self.cycles = CyclesResource(self._http)
        self.metrics = MetricsResource(self._http)
        self.audit = AuditResource(self._http)

    def set_token(self, token: str) -> None:
        """Inyecta un token JWT directamente (útil para flujos no-interactivos)."""
        self._http.set_token(token)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "OvdClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
