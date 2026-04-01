"""
OVD Platform — Startup Environment Validator (Engine Python)
Copyright 2026 Omar Robles

Valida que las variables de entorno criticas esten presentes al arrancar el Engine.
Se ejecuta en el lifespan de FastAPI antes de inicializar LangGraph.
Falla rapido con un mensaje claro en lugar de errores cripticos en runtime.
"""
from __future__ import annotations
import os
import sys
import logging
from dataclasses import dataclass, field

import httpx

log = logging.getLogger("ovd.startup")


@dataclass
class EnvVar:
    name: str
    required: bool
    description: str
    validate: callable = None   # (value: str) -> str | None


# Variables de entorno del OVD Engine
_ENGINE_ENV_VARS: list[EnvVar] = [
    # --- CRITICAS ---
    EnvVar(
        name="ANTHROPIC_API_KEY",
        required=False,   # Opcional cuando se usa Ollama como provider
        description="API key de Anthropic para los agentes LLM (no requerida con Ollama)",
        validate=lambda v: None if v.startswith("sk-ant-") else "debe empezar con sk-ant-",
    ),
    EnvVar(
        name="DATABASE_URL",
        required=True,
        description="URL de conexion PostgreSQL para el checkpointer LangGraph",
        validate=lambda v: None if v.startswith(("postgresql://", "postgres://")) else "debe empezar con postgresql://",
    ),
    EnvVar(
        name="NATS_URL",
        required=False,   # Opcional — solo requerida para eventos asincrónicos
        description="URL de NATS JetStream para mensajeria asincronica",
        validate=lambda v: None if v.startswith("nats://") else "debe empezar con nats://",
    ),

    # --- IMPORTANTES ---
    EnvVar(
        name="OVD_MODEL",
        required=False,
        description="Modelo Claude base (default: claude-sonnet-4-6)",
    ),
    EnvVar(
        name="OVD_ENGINE_SECRET",
        required=False,
        description="Secret compartido con el Bridge — dejar vacio solo en desarrollo",
    ),
    EnvVar(
        name="OVD_BRIDGE_URL",
        required=False,
        description="URL del Bridge para RAG callbacks y Research Agent",
    ),

    # --- TELEMETRIA ---
    EnvVar(
        name="OTEL_EXPORTER_OTLP_ENDPOINT",
        required=False,
        description="Endpoint OpenTelemetry Collector",
    ),
]


@dataclass
class CheckResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


def check_env() -> CheckResult:
    """Valida las variables de entorno del Engine."""
    result = CheckResult()

    for var in _ENGINE_ENV_VARS:
        value = os.environ.get(var.name)

        if not value:
            if var.required:
                result.errors.append(f"[REQUIRED] {var.name} — {var.description}")
            else:
                result.warnings.append(f"[OPTIONAL] {var.name} no definida — {var.description}")
            continue

        if var.validate:
            err = var.validate(value)
            if err:
                (result.errors if var.required else result.warnings).append(
                    f"[INVALID] {var.name} — {err}"
                )

    # Validacion especial: al menos un provider LLM debe estar configurado
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY", "").startswith("sk-ant-"))
    has_ollama    = bool(os.environ.get("OLLAMA_BASE_URL"))
    has_openai    = bool(os.environ.get("OPENAI_API_KEY"))
    if not (has_anthropic or has_ollama or has_openai):
        result.errors.append(
            "[REQUIRED] Sin provider LLM — define ANTHROPIC_API_KEY, OLLAMA_BASE_URL u OPENAI_API_KEY"
        )

    # Validacion especial: LangSmith tracing sin API key
    if os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true":
        if not os.environ.get("LANGCHAIN_API_KEY"):
            result.warnings.append(
                "[WARN] LANGCHAIN_TRACING_V2=true pero LANGCHAIN_API_KEY no definida — el tracing fallara"
            )

    # Validacion especial: Ollama embedding sin base URL
    if (
        os.environ.get("OVD_RAG_ENABLED", "true").lower() != "false"
        and os.environ.get("OVD_EMBEDDING_PROVIDER", "") == "ollama"
        and not os.environ.get("OLLAMA_BASE_URL")
    ):
        result.errors.append(
            "[REQUIRED] OLLAMA_BASE_URL — requerida cuando OVD_EMBEDDING_PROVIDER=ollama"
        )

    return result


def assert_env() -> None:
    """
    Ejecuta la validacion y termina el proceso si hay errores criticos.
    Llamar una vez en el lifespan de FastAPI antes de inicializar LangGraph.
    """
    result = check_env()

    for w in result.warnings:
        log.warning(w)

    if not result.ok:
        log.error("startup config errors — el engine no puede arrancar (%d error(es)):", len(result.errors))
        for e in result.errors:
            log.error("  %s", e)
        log.error("copia .env.example a .env y completa las variables marcadas con [REQUIRED]")
        sys.exit(1)

    log.info("startup config ok (warnings: %d)", len(result.warnings))


async def check_ollama_model() -> None:
    """
    P3.B — Verifica en runtime que el modelo Ollama configurado está disponible.

    Llama a GET {OLLAMA_BASE_URL}/api/tags y comprueba que OVD_MODEL aparece en
    la lista de modelos descargados. Emite warning (no fatal) si Ollama no responde
    o el modelo no está disponible — el engine arranca igual pero los nodos fallarán
    en runtime si el modelo no existe.
    """
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "")
    if not ollama_url:
        return  # Ollama no es el provider configurado

    model = os.environ.get("OVD_MODEL", "qwen2.5-coder:7b")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(f"{ollama_url}/api/tags")
            if not res.is_success:
                log.warning(
                    "startup: Ollama respondió %s al listar modelos — verifica que el servicio esté activo",
                    res.status_code,
                )
                return

            data = res.json()
            available = [m.get("name", "") for m in data.get("models", [])]

            # Normalizar: "qwen2.5-coder:7b" y "qwen2.5-coder:latest" → match parcial por nombre base
            model_base = model.split(":")[0]
            matched = any(m.split(":")[0] == model_base for m in available)

            if matched:
                log.info("startup: modelo Ollama '%s' disponible ✓", model)
            else:
                log.warning(
                    "startup: modelo Ollama '%s' NO encontrado en la lista local. "
                    "Modelos disponibles: %s. "
                    "Ejecuta: ollama pull %s",
                    model, available or ["(ninguno)"], model,
                )

    except Exception as exc:
        log.warning(
            "startup: no se pudo conectar a Ollama en %s (%s) — "
            "verifica que el servicio esté corriendo",
            ollama_url, exc,
        )
