"""
OVD Platform — Secrets Adapter (Sprint 9 — GAP-A4)
Copyright 2026 Omar Robles

Abstracción para recuperar credenciales de workspaces desde un secrets manager.

Problema que resuelve:
    Las credenciales de Oracle del cliente (ORACLE_HOST, ORACLE_USER, ORACLE_PASS)
    estaban en .env.local. Con este módulo, se recuperan en runtime desde Infisical
    y nunca se persisten en la DB de OVD ni en archivos de configuración del servidor.

Arquitectura:
    - SecretsAdapter: interfaz abstracta (ABC)
    - InfisicalAdapter: implementación para Infisical auto-hosteado
    - EnvAdapter: fallback para desarrollo local (lee desde variables de entorno)
    - get_adapter(): factory que selecciona la implementación según la configuración

Diseño para migración futura:
    Cuando se defina el cloud proveedor, solo hay que implementar un nuevo adaptador:
        class AWSSecretsAdapter(SecretsAdapter): ...
        class GCPSecretManagerAdapter(SecretsAdapter): ...
    El resto del sistema (Context Resolver, graph.py) no cambia nada.

Uso desde context_resolver.py:
    adapter = get_adapter()
    secrets = await adapter.get_secrets("alemana-cas")
    # secrets = {"ORACLE_HOST": "...", "ORACLE_USER": "...", "ORACLE_PASS": "..."}
"""
from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod

import httpx

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Interfaz abstracta
# ---------------------------------------------------------------------------

class SecretsAdapter(ABC):
    """
    Interfaz abstracta para recuperar secrets de un workspace.

    Contrato:
        - get_secrets(secret_ref) devuelve un dict con los secrets del workspace
        - Las keys son los nombres de los secrets tal como están en el manager
        - Los valores son siempre strings
        - Si secret_ref no existe → devuelve {} (no lanza excepción)
    """

    @abstractmethod
    async def get_secrets(self, secret_ref: str) -> dict[str, str]:
        """
        Recupera todos los secrets asociados al secret_ref.

        Args:
            secret_ref: identificador del environment/path en el secrets manager
                        (e.g. "alemana-cas", "prod/oracle/cas")

        Returns:
            Dict con los secrets: {"ORACLE_HOST": "...", "ORACLE_USER": "...", ...}
            Dict vacío si secret_ref no existe o no hay credenciales.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """True si el adaptador está configurado y disponible."""


# ---------------------------------------------------------------------------
# Implementación Infisical
# ---------------------------------------------------------------------------

# Infisical API v3 endpoints
_INFISICAL_SECRETS_ENDPOINT = "/api/v3/secrets/raw"
_INFISICAL_AUTH_ENDPOINT    = "/api/v1/auth/universal-auth/login"

# Cache de tokens de acceso por instancia (evita re-autenticar en cada request)
_INFISICAL_ACCESS_TOKEN_CACHE: dict[str, str] = {}


class InfisicalAdapter(SecretsAdapter):
    """
    Adaptador para Infisical auto-hosteado.

    Configuración via variables de entorno:
        INFISICAL_URL          — URL base del Infisical (default: http://localhost:8080)
        INFISICAL_TOKEN        — Machine Identity Token (o Service Token legacy)
        INFISICAL_PROJECT_ID   — ID del proyecto "ovd-platform" en Infisical

    Modelo de datos en Infisical:
        Proyecto "ovd-platform"
        ├── Environment "alemana-cas"  → secrets del workspace CAS
        ├── Environment "alemana-cat"  → secrets del workspace CAT
        └── Environment "alemana-cav"  → secrets del workspace CAV

    El secret_ref en OVD corresponde al nombre del environment en Infisical.
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        project_id: str | None = None,
    ):
        self._base_url   = (base_url   or os.environ.get("INFISICAL_URL",       "http://localhost:8080")).rstrip("/")
        self._token      = token      or os.environ.get("INFISICAL_TOKEN",      "")
        self._project_id = project_id or os.environ.get("INFISICAL_PROJECT_ID", "")
        self._timeout    = float(os.environ.get("INFISICAL_TIMEOUT_SECS", "5"))

    def is_available(self) -> bool:
        return bool(self._token and self._project_id)

    async def get_secrets(self, secret_ref: str) -> dict[str, str]:
        """
        Recupera todos los secrets del environment `secret_ref` en Infisical.

        El secret_ref es el nombre del environment (e.g. "alemana-cas").
        Devuelve {} si el environment no existe o hay un error de conectividad.
        """
        if not self.is_available():
            log.warning(
                "secrets_adapter.InfisicalAdapter: no configurado "
                "(INFISICAL_TOKEN o INFISICAL_PROJECT_ID faltante) — devolviendo {}"
            )
            return {}

        try:
            return await self._fetch_secrets(secret_ref)
        except httpx.ConnectError:
            log.error(
                "secrets_adapter: no se puede conectar a Infisical en %s — "
                "verificar que el servicio esté levantado (docker compose --profile infisical up -d)",
                self._base_url,
            )
            return {}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                log.warning(
                    "secrets_adapter: environment '%s' no encontrado en Infisical — "
                    "crear el environment en http://localhost:8080",
                    secret_ref,
                )
            else:
                log.error(
                    "secrets_adapter: error HTTP %d al recuperar secrets de '%s'",
                    e.response.status_code, secret_ref,
                )
            return {}
        except Exception as e:
            log.error("secrets_adapter: error inesperado recuperando '%s' — %s", secret_ref, e)
            return {}

    async def _fetch_secrets(self, environment: str) -> dict[str, str]:
        """Llama a la API de Infisical y retorna el dict de secrets."""
        url = f"{self._base_url}{_INFISICAL_SECRETS_ENDPOINT}"
        params = {
            "workspaceId": self._project_id,
            "environment": environment,
            "secretPath": "/",        # raíz del environment
            "expandSecretReferences": "true",
        }
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

        secrets: dict[str, str] = {}
        for item in data.get("secrets", []):
            key   = item.get("secretKey", "")
            value = item.get("secretValue", "")
            if key:
                secrets[key] = value

        log.info(
            "secrets_adapter.InfisicalAdapter: %d secrets recuperados para environment '%s'",
            len(secrets), environment,
        )
        return secrets


# ---------------------------------------------------------------------------
# Implementación Env (fallback desarrollo local)
# ---------------------------------------------------------------------------

class EnvAdapter(SecretsAdapter):
    """
    Adaptador de fallback que lee secrets desde variables de entorno del proceso.

    Convención de naming:
        secret_ref = "alemana-cas"
        → busca variables con prefijo OVD_SECRET_ALEMANA_CAS_*
        → ej: OVD_SECRET_ALEMANA_CAS_ORACLE_HOST

    Útil para desarrollo local sin Infisical levantado.
    Las variables se configuran en .env.local del engine.

    IMPORTANTE: Este adaptador NO es adecuado para producción con clientes reales.
    Las credenciales del cliente nunca deben estar en el .env del servidor OVD.
    """

    def is_available(self) -> bool:
        return True  # siempre disponible como fallback

    async def get_secrets(self, secret_ref: str) -> dict[str, str]:
        prefix = f"OVD_SECRET_{secret_ref.upper().replace('-', '_')}_"
        secrets: dict[str, str] = {}
        for key, value in os.environ.items():
            if key.startswith(prefix):
                secret_name = key[len(prefix):]
                secrets[secret_name] = value

        if secrets:
            log.info(
                "secrets_adapter.EnvAdapter: %d secrets desde env para '%s' (solo para desarrollo)",
                len(secrets), secret_ref,
            )
        else:
            log.debug(
                "secrets_adapter.EnvAdapter: no se encontraron variables con prefijo %s*",
                prefix,
            )
        return secrets


# ---------------------------------------------------------------------------
# Factory: selecciona el adaptador según la configuración
# ---------------------------------------------------------------------------

_adapter_instance: SecretsAdapter | None = None


def get_adapter() -> SecretsAdapter:
    """
    Factory singleton. Devuelve el adaptador configurado.

    Prioridad:
    1. InfisicalAdapter si INFISICAL_TOKEN y INFISICAL_PROJECT_ID están configurados
    2. EnvAdapter como fallback (desarrollo local)

    La instancia se crea una sola vez — es thread-safe para uso async.
    """
    global _adapter_instance
    if _adapter_instance is not None:
        return _adapter_instance

    infisical = InfisicalAdapter()
    if infisical.is_available():
        log.info(
            "secrets_adapter: usando InfisicalAdapter → %s (proyecto: %s)",
            infisical._base_url, infisical._project_id,
        )
        _adapter_instance = infisical
    else:
        log.warning(
            "secrets_adapter: INFISICAL_TOKEN o INFISICAL_PROJECT_ID no configurados — "
            "usando EnvAdapter (solo para desarrollo). "
            "Para producción: configurar Infisical con 'docker compose --profile infisical up -d'"
        )
        _adapter_instance = EnvAdapter()

    return _adapter_instance


def reset_adapter() -> None:
    """Fuerza reinicialización del factory. Útil en tests."""
    global _adapter_instance
    _adapter_instance = None
