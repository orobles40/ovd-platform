"""
OVD Platform — Model Router (GAP-013a, Sprint 8 — GAP-A1)
Copyright 2026 Omar Robles

Resuelve el LLM correcto para un agente en runtime consultando la
Configuration Layer via la API del Bridge.

El router aplica la herencia org → proyecto → agente y devuelve
el ChatModel de LangChain correspondiente al provider configurado:
  - ollama  → ChatOllama (local)
  - claude  → ChatAnthropic
  - openai  → ChatOpenAI (compatible)
  - custom  → ChatOpenAI con base_url custom (Kimi, Moonshot, Groq, etc.)

Si la API no responde, cae a SYSTEM_DEFAULT (Ollama qwen2.5-coder:7b).

Sprint 8 — Stack Registry routing:
  resolve_with_context() acepta un AgentContext y aplica el model_routing
  del Stack Registry como override sobre la config del Bridge.
  Regla: legacy_stack/restricciones → claude | stack moderno → ollama
  El operador puede sobreescribir con model_routing explícito en el profile.
"""
from __future__ import annotations
import os
import re
import logging
import time
from typing import Any
from dataclasses import dataclass

import httpx
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger("ovd-model-router")

# ---------------------------------------------------------------------------
# Config del Bridge (donde esta la API con la config de agentes)
# ---------------------------------------------------------------------------

_BRIDGE_URL = os.environ.get("OVD_BRIDGE_URL", "http://localhost:3000")
_BRIDGE_SECRET = os.environ.get("OVD_ENGINE_SECRET", "")

# Defaults del sistema si la API no responde o no hay config
_DEFAULT_PROVIDER = "ollama"
_DEFAULT_MODEL    = os.environ.get("OVD_MODEL", "qwen2.5-coder:7b")
_DEFAULT_OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

# P2.A — Timeout configurable para evitar que Ollama bloquee el ciclo indefinidamente
_LLM_TIMEOUT = float(os.environ.get("OVD_LLM_TIMEOUT_SECS", "300"))

# Modelos por defecto para roles de análisis (requieren structured output robusto).
# Se puede sobreescribir via API de agent-config igual que los roles de agente.
# Para uso con OSS se recomienda 14b+ en analyzer/sdd; 7b suficiente para qa.
_ANALYSIS_ROLE_DEFAULTS: dict[str, str] = {
    "analyzer": os.environ.get("OVD_MODEL_ANALYZER", _DEFAULT_MODEL),
    "sdd":      os.environ.get("OVD_MODEL_SDD",      _DEFAULT_MODEL),
    "qa":       os.environ.get("OVD_MODEL_QA",        _DEFAULT_MODEL),
}

# P2.C — Roles que usan structured output — requieren temperature baja para estabilidad
_STRUCTURED_ROLES = {"analyzer", "sdd", "qa", "security", "router"}

# ---------------------------------------------------------------------------
# S20 — GAP-R4: Circuit breaker por provider (lightweight, en memoria)
# ---------------------------------------------------------------------------

_CB_FAIL_THRESHOLD = int(os.environ.get("OVD_CB_FAIL_THRESHOLD", "5"))
_CB_RECOVERY_SECS  = float(os.environ.get("OVD_CB_RECOVERY_SECS", "30"))


class CircuitOpenError(Exception):
    """Lanzada cuando el circuit breaker está abierto para un provider."""


class _CircuitBreaker:
    """
    Circuit breaker simple en memoria por provider.
    Estados: closed → open → half-open → closed/open

    closed:    permite llamadas normales
    open:      rechaza inmediatamente tras N fallos consecutivos
    half-open: permite una llamada de prueba tras recovery_secs
    """

    def __init__(self, threshold: int, recovery_secs: float) -> None:
        self._threshold = threshold
        self._recovery  = recovery_secs
        self._failures:   dict[str, int]   = {}
        self._open_since: dict[str, float] = {}

    def is_open(self, provider: str) -> bool:
        if provider not in self._open_since:
            return False
        elapsed = time.monotonic() - self._open_since[provider]
        if elapsed >= self._recovery:
            # half-open: dejar pasar una prueba (el caller decide si registrar éxito/fallo)
            return False
        return True

    def record_failure(self, provider: str) -> None:
        count = self._failures.get(provider, 0) + 1
        self._failures[provider] = count
        if count >= self._threshold:
            if provider not in self._open_since:
                log.warning(
                    "circuit_breaker: circuito ABIERTO para provider='%s' tras %d fallos",
                    provider, count,
                )
            self._open_since[provider] = time.monotonic()

    def record_success(self, provider: str) -> None:
        if provider in self._open_since:
            log.info("circuit_breaker: circuito CERRADO para provider='%s'", provider)
        self._failures.pop(provider, None)
        self._open_since.pop(provider, None)

    def reset(self, provider: str | None = None) -> None:
        """Usado en tests para limpiar estado."""
        if provider:
            self._failures.pop(provider, None)
            self._open_since.pop(provider, None)
        else:
            self._failures.clear()
            self._open_since.clear()


# Singleton global
_cb = _CircuitBreaker(_CB_FAIL_THRESHOLD, _CB_RECOVERY_SECS)

# P3.C — Patrón para detectar modelos con menos de 7B parámetros
_SMALL_MODEL_RE = re.compile(r"\b([1-6])b\b|tiny|mini|phi[0-9]?[-:]mini", re.IGNORECASE)


def _warn_if_small_model(model: str, role: str) -> None:
    """P3.C — Emite warning si el modelo tiene indicios de ser < 7B parámetros."""
    if _SMALL_MODEL_RE.search(model):
        log.warning(
            "model_router: modelo '%s' (role=%s) parece tener menos de 7B parámetros — "
            "el structured output puede ser inestable; se recomienda 7b+ para roles analíticos",
            model, role,
        )


# P2.C — Temperature por uso y provider
# Structured: Claude=0.2, Ollama=0.0 | Generación: Claude=0.5, Ollama=0.3
def _resolve_temperature(role: str, provider: str) -> float:
    is_structured = role in _STRUCTURED_ROLES
    if provider == "claude":
        return 0.2 if is_structured else 0.5
    # ollama / openai / custom
    return 0.0 if is_structured else 0.3


# ---------------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------------

@dataclass
class ResolvedConfig:
    provider: str
    model: str
    base_url: str | None
    api_key_env: str | None
    extra_instructions: str | None
    constraints: str | None
    code_style: str | None
    resolved_from: str   # default | org | project | agent
    temperature: float = 0.0  # P2.C — calculado por _resolve_temperature


# ---------------------------------------------------------------------------
# Cache en memoria (TTL simple — se invalida al reiniciar el Engine)
# ---------------------------------------------------------------------------

_cache: dict[str, ResolvedConfig] = {}


def _cache_key(org_id: str, project_id: str, agent_role: str) -> str:
    return f"{org_id}:{project_id}:{agent_role}"


def invalidate_cache(org_id: str | None = None) -> None:
    """Invalida el cache de config. Sin org_id limpia todo."""
    if org_id is None:
        _cache.clear()
    else:
        keys = [k for k in _cache if k.startswith(f"{org_id}:")]
        for k in keys:
            del _cache[k]


# ---------------------------------------------------------------------------
# Resolucion de config via API del Bridge
# ---------------------------------------------------------------------------

async def _fetch_resolved(
    org_id: str,
    project_id: str,
    agent_role: str,
    jwt_token: str,
) -> ResolvedConfig | None:
    """
    Llama a GET /ovd/config/project/:projectId/resolved en el Bridge
    y extrae la config del agente solicitado.

    S20 — GAP-R8: reintenta hasta 3 veces con backoff (0.5s-2s) antes de caer a defaults.
    """
    url = f"{_BRIDGE_URL}/ovd/config/project/{project_id}/resolved"
    headers = {"Authorization": f"Bearer {jwt_token}"}
    if _BRIDGE_SECRET:
        headers["X-OVD-Secret"] = _BRIDGE_SECRET

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        reraise=True,
    )
    async def _do_fetch() -> ResolvedConfig | None:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(url, headers=headers)
            if not res.is_success:
                log.warning("model_router: bridge returned %s for config", res.status_code)
                return None

            data = res.json()
            resolved_all: dict[str, Any] = data.get("resolved", {})
            agent_cfg: dict[str, Any] = resolved_all.get(agent_role, {})

            if not agent_cfg:
                return None

            return ResolvedConfig(
                provider=agent_cfg.get("provider", _DEFAULT_PROVIDER),
                model=agent_cfg.get("model", _DEFAULT_MODEL),
                base_url=agent_cfg.get("baseUrl"),
                api_key_env=agent_cfg.get("apiKeyEnv"),
                extra_instructions=agent_cfg.get("extraInstructions"),
                constraints=agent_cfg.get("constraints"),
                code_style=agent_cfg.get("codeStyle"),
                resolved_from=agent_cfg.get("resolvedFrom", "default"),
            )

    try:
        return await _do_fetch()
    except Exception as exc:
        log.warning("model_router: failed to fetch config from bridge tras reintentos: %s", exc)
        return None


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------

async def resolve(
    agent_role: str,
    org_id: str,
    project_id: str,
    jwt_token: str = "",
) -> ResolvedConfig:
    """
    Devuelve la ResolvedConfig efectiva para un agente.
    Usa cache en memoria. Si la API no responde, retorna defaults del sistema.
    """
    key = _cache_key(org_id, project_id, agent_role)
    if key in _cache:
        return _cache[key]

    config = None
    if jwt_token:
        config = await _fetch_resolved(org_id, project_id, agent_role, jwt_token)

    if config is None:
        # Para roles de análisis usar el modelo específico configurado (puede diferir del default)
        model = _ANALYSIS_ROLE_DEFAULTS.get(agent_role, _DEFAULT_MODEL)
        config = ResolvedConfig(
            provider=_DEFAULT_PROVIDER,
            model=model,
            base_url=_DEFAULT_OLLAMA_URL,
            api_key_env=None,
            extra_instructions=None,
            constraints=None,
            code_style=None,
            resolved_from="default",
            temperature=_resolve_temperature(agent_role, _DEFAULT_PROVIDER),
        )
    else:
        # Config desde Bridge — calcular temperature si no viene explícita
        if config.temperature == 0.0:
            config.temperature = _resolve_temperature(agent_role, config.provider)

    _cache[key] = config
    log.info(
        "model_router resolved: role=%s provider=%s model=%s from=%s",
        agent_role, config.provider, config.model, config.resolved_from,
    )
    # P3.C — advertir si el modelo es probablemente < 7B (structured output inestable)
    _warn_if_small_model(config.model, agent_role)
    return config


def build_llm(config: ResolvedConfig) -> Any:
    """
    Construye el ChatModel de LangChain segun el provider resuelto.

    S20 — GAP-R4: lanza CircuitOpenError si el circuit breaker está abierto para el provider.
    El caller debe capturar esta excepción y usar un fallback inmediato.

    Providers:
      ollama  → ChatOllama via ChatOpenAI compatible (base_url local)
      claude  → ChatAnthropic
      openai  → ChatOpenAI (GPT-4o, o1, etc.)
      custom  → ChatOpenAI con base_url custom (Kimi, Moonshot, Groq, Together, etc.)
    """
    # S20 — GAP-R4: verificar circuit breaker antes de intentar la llamada
    if _cb.is_open(config.provider):
        raise CircuitOpenError(
            f"Circuit breaker ABIERTO para provider='{config.provider}' — "
            f"esperando {_CB_RECOVERY_SECS:.0f}s de recovery. Usa un provider alternativo."
        )
    # Resolver API key si se especifica una variable de entorno
    api_key: str | None = None
    if config.api_key_env:
        api_key = os.environ.get(config.api_key_env)

    if config.provider == "claude":
        return ChatAnthropic(
            model=config.model,
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY", ""),
            max_tokens=8192,
            temperature=config.temperature,
            timeout=_LLM_TIMEOUT,
        )

    if config.provider == "openai":
        return ChatOpenAI(
            model=config.model,
            api_key=api_key or os.environ.get("OPENAI_API_KEY", ""),
            max_tokens=8192,
            temperature=config.temperature,
            request_timeout=_LLM_TIMEOUT,
        )

    if config.provider in ("ollama", "custom"):
        # Ollama expone una API compatible con OpenAI en /v1
        base_url = config.base_url or _DEFAULT_OLLAMA_URL
        if config.provider == "ollama" and not base_url.endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"

        return ChatOpenAI(
            model=config.model,
            base_url=base_url,
            api_key=api_key or "ollama",   # Ollama acepta cualquier valor
            max_tokens=8192,
            temperature=config.temperature,
            request_timeout=_LLM_TIMEOUT,
        )

    # Fallback: Ollama con modelo por defecto
    log.warning("model_router: provider desconocido '%s', usando Ollama default", config.provider)
    return ChatOpenAI(
        model=_DEFAULT_MODEL,
        base_url=f"{_DEFAULT_OLLAMA_URL}/v1",
        api_key="ollama",
        max_tokens=8192,
        temperature=0.0,
        request_timeout=_LLM_TIMEOUT,
    )


async def get_llm(
    agent_role: str,
    org_id: str,
    project_id: str,
    jwt_token: str = "",
) -> Any:
    """
    Atajo: resuelve config y construye el LLM en un solo paso.
    Uso en graph.py: llm = await model_router.get_llm("backend", org_id, project_id, jwt)
    """
    config = await resolve(agent_role, org_id, project_id, jwt_token)
    return build_llm(config)


# ---------------------------------------------------------------------------
# Sprint 8 — Stack Registry routing override
# ---------------------------------------------------------------------------

# Modelos por defecto para cada provider cuando el routing viene del Stack Registry
_STACK_ROUTING_DEFAULTS: dict[str, tuple[str, str | None]] = {
    # (provider, model)  — None = usar _DEFAULT_MODEL / variable de entorno
    "claude": ("claude", os.environ.get("OVD_MODEL_CLAUDE", "claude-sonnet-4-6")),
    "ollama": ("ollama", os.environ.get("OVD_MODEL", _DEFAULT_MODEL)),
    "openai": ("openai", os.environ.get("OVD_MODEL_OPENAI", "gpt-4o-mini")),
}


def _apply_stack_routing(config: ResolvedConfig, stack_routing: str) -> ResolvedConfig:
    """
    Aplica el model_routing del Stack Registry como override sobre la
    config resuelta del Bridge.

    El Stack Registry tiene precedencia sobre la config del Bridge para
    garantizar que el agente correcto se use según la complejidad del stack
    (e.g. Oracle 12c siempre → Claude, sin importar la config del Bridge).

    Excepciones:
    - "auto": no hace nada (el Bridge / defaults del sistema deciden)
    - Si la config ya tiene un provider que coincide: no-op para evitar
      sobrescribir la config detallada del Bridge (model, base_url, etc.)
    """
    if stack_routing == "auto" or stack_routing not in _STACK_ROUTING_DEFAULTS:
        return config

    target_provider, target_model = _STACK_ROUTING_DEFAULTS[stack_routing]

    # Si el Bridge ya configuró el mismo provider, respetar su config (model, base_url, etc.)
    if config.provider == target_provider and config.resolved_from != "default":
        return config

    # Override: usar el provider del Stack Registry con el modelo por defecto
    return ResolvedConfig(
        provider=target_provider,
        model=target_model or config.model,
        base_url=config.base_url if target_provider == "ollama" else None,
        api_key_env=config.api_key_env,
        extra_instructions=config.extra_instructions,
        constraints=config.constraints,
        code_style=config.code_style,
        resolved_from=f"stack_registry:{stack_routing}",
        temperature=_resolve_temperature(config.resolved_from, target_provider),
    )


async def resolve_with_context(
    agent_role: str,
    org_id: str,
    project_id: str,
    jwt_token: str = "",
    stack_routing: str = "auto",
) -> ResolvedConfig:
    """
    Versión Sprint 8: resuelve config del Bridge y aplica el override
    del Stack Registry encima.

    Uso en graph.py (S8.C):
        from context_resolver import AgentContext
        config = await model_router.resolve_with_context(
            agent_role="backend",
            org_id=ctx.org_id,
            project_id=ctx.project_id,
            jwt_token=jwt_token,
            stack_routing=ctx.model_routing,
        )
        llm = build_llm(config)
    """
    config = await resolve(agent_role, org_id, project_id, jwt_token)
    config = _apply_stack_routing(config, stack_routing)
    log.info(
        "model_router stack_routing: role=%s stack_routing=%s → provider=%s model=%s from=%s",
        agent_role, stack_routing, config.provider, config.model, config.resolved_from,
    )
    return config


async def get_llm_with_context(
    agent_role: str,
    org_id: str,
    project_id: str,
    jwt_token: str = "",
    stack_routing: str = "auto",
) -> Any:
    """
    Atajo Sprint 8: resuelve config con Stack Registry routing y construye el LLM.
    Reemplaza get_llm() en los nodos del grafo que ya reciben AgentContext.
    """
    config = await resolve_with_context(
        agent_role, org_id, project_id, jwt_token, stack_routing
    )
    return build_llm(config)
