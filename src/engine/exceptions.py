"""
OVD Platform — Jerarquía de excepciones de dominio
Copyright 2026 Omar Robles

Todas las excepciones propias del engine heredan de OVDError.
Esto permite catch genérico (OVDError) o específico por capa.

Jerarquía:
    OVDError
    ├── OVDConfigError        — configuración faltante o inválida al arrancar
    ├── OVDCycleError         — error durante ejecución de un ciclo completo
    │   └── OVDAgentError     — error en la ejecución de un agente específico
    ├── OVDValidationError    — artefacto generado no pasa validación
    ├── OVDTokenError         — JWT inválido, expirado o revocado
    ├── OVDNotFoundError      — recurso interno no encontrado
    └── OVDCircuitOpenError   — circuit breaker abierto en model_router
"""


class OVDError(Exception):
    """Base para todas las excepciones de dominio de OVD Platform."""


class OVDConfigError(OVDError):
    """Configuración faltante o inválida.

    Se lanza al arrancar el engine si faltan variables de entorno requeridas
    o si la configuración tiene valores incoherentes.

    Ejemplo: DATABASE_URL vacío, JWT_SECRET demasiado corto.
    """


class OVDCycleError(OVDError):
    """Error durante la ejecución de un ciclo completo.

    Indica que el ciclo no pudo completarse. Puede contener datos
    parciales de ejecución (fr_analysis, sdd parcial, etc.).
    """


class OVDAgentError(OVDCycleError):
    """Error en la ejecución de un agente específico dentro del ciclo.

    Args:
        agent_name: nombre del nodo/agente que falló (ej. "generate_sdd").
        message: descripción del error.
    """

    def __init__(self, agent_name: str, message: str) -> None:
        self.agent_name = agent_name
        super().__init__(f"[{agent_name}] {message}")


class OVDValidationError(OVDError):
    """Artefacto generado no pasa validación de calidad o seguridad.

    Ejemplo: QA score < umbral, imports inválidos en código generado.
    """


class OVDTokenError(OVDError):
    """JWT o refresh token inválido, expirado o revocado.

    Reemplaza ValueError genérico en auth.py para hacer el error
    identificable en logs y manejable en capas superiores.
    """


class OVDNotFoundError(OVDError):
    """Recurso interno no encontrado.

    Distinto de HTTPException 404 — este se usa en capa de dominio
    (ej. org no existe en BD) antes de convertirlo a HTTP response.
    """


class OVDCircuitOpenError(OVDError):
    """Circuit breaker abierto en model_router.

    Indica que el proveedor LLM está temporalmente deshabilitado
    por haber superado el umbral de fallos consecutivos.
    """
