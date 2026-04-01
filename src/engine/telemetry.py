"""
OVD Platform — Telemetría OTEL (Sprint 10 — GAP-A6)
Copyright 2026 Omar Robles

Instrumentación OpenTelemetry para el OVD Engine.

Qué conecta:
  - Un span raíz por ciclo con trace_id compartido
  - Spans hijos por cada nodo LangGraph (analyze_fr, generate_sdd, agent_executor, etc.)
  - Atributos clave: org_id, project_id, agent_role, model_routing, qa_score, tokens
  - Propagación de trace_id desde api.py → todos los nodos del grafo

Qué ya existía (no parte de cero):
  - OTEL Collector en docker-compose.yml (Sprint 3)
  - LangSmith tracing con LANGCHAIN_TRACING_V2 (Sprint 3)
  - estimated_cost_usd y tokens_total en ovd_cycle_logs (Sprint 4)
  Este sprint conecta esos puntos.

Dashboard esperado (Jaeger / Grafana):
  - Latencia por nodo (p50/p95)
  - Tasa de aprobación por org/proyecto
  - QA score promedio por modelo
  - Tokens por agente
  - Alertas: ciclo sin avanzar > N minutos

Uso en graph.py:
  from telemetry import cycle_span, node_span, get_tracer

  # En api.py — crear span raíz al iniciar sesión:
  with cycle_span(thread_id, org_id, project_id, feature_request) as span:
      trace_id = get_trace_id(span)  # propagar al estado del grafo

  # En cada nodo — span hijo automático:
  async with node_span("analyze_fr", state) as span:
      span.set_attribute("complexity", result.complexity)
      ...
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncIterator, Iterator

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import NonRecordingSpan, StatusCode

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Inicialización del provider (singleton)
# ---------------------------------------------------------------------------

_tracer: trace.Tracer | None = None
_initialized = False


def setup_telemetry(service_name: str = "ovd-engine") -> None:
    """
    Inicializa el TracerProvider con exportación al OTEL Collector.
    Llamar una vez en el lifespan de FastAPI.

    Si OTEL_EXPORTER_OTLP_ENDPOINT no está configurado, usa ConsoleExporter
    (logs de trazas en stdout — útil para desarrollo local).
    """
    global _tracer, _initialized
    if _initialized:
        return

    resource = Resource.create({
        "service.name":    service_name,
        "service.version": "0.1.0",
        "deployment.environment": os.environ.get("NODE_ENV", "development"),
    })

    provider = TracerProvider(resource=resource)

    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if otlp_endpoint:
        exporter = OTLPSpanExporter(
            endpoint=f"{otlp_endpoint.rstrip('/')}/v1/traces",
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        log.info("telemetry: OTLP exporter → %s", otlp_endpoint)
    else:
        # Desarrollo: imprimir spans en consola solo si DEBUG
        if os.environ.get("LOG_LEVEL", "info").lower() == "debug":
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        log.info("telemetry: OTEL_EXPORTER_OTLP_ENDPOINT no configurado — spans locales únicamente")

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer("ovd.engine")
    _initialized = True


def get_tracer() -> trace.Tracer:
    """Devuelve el tracer. Inicializa con ConsoleExporter si setup_telemetry() no fue llamado."""
    global _tracer
    if _tracer is None:
        setup_telemetry()
    return _tracer


def get_trace_id(span: trace.Span) -> str:
    """Devuelve el trace_id como string hexadecimal de 32 chars. "" si es NonRecordingSpan."""
    ctx = span.get_span_context()
    if ctx and ctx.is_valid:
        return format(ctx.trace_id, "032x")
    return ""


# ---------------------------------------------------------------------------
# Span de ciclo (raíz)
# ---------------------------------------------------------------------------

@contextmanager
def cycle_span(
    thread_id: str,
    org_id: str,
    project_id: str,
    feature_request: str,
    stack_routing: str = "auto",
) -> Iterator[trace.Span]:
    """
    Context manager que crea el span raíz de un ciclo OVD.
    El trace_id de este span se propaga a todos los nodos del grafo.

    Uso en api.py (POST /session):
        with telemetry.cycle_span(thread_id, org_id, project_id, fr) as span:
            trace_id = telemetry.get_trace_id(span)
            initial_state["trace_id"] = trace_id
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(
        name="ovd.cycle",
        kind=trace.SpanKind.SERVER,
    ) as span:
        span.set_attributes({
            "ovd.thread_id":      thread_id,
            "ovd.org_id":         org_id,
            "ovd.project_id":     project_id,
            "ovd.fr_preview":     feature_request[:120],
            "ovd.stack_routing":  stack_routing,
        })
        try:
            yield span
        except Exception as e:
            span.set_status(StatusCode.ERROR, str(e))
            raise


# ---------------------------------------------------------------------------
# Span de nodo (hijo del ciclo)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def node_span(
    node_name: str,
    state: dict[str, Any],
) -> AsyncIterator[trace.Span]:
    """
    Context manager async que crea un span hijo para un nodo del grafo.
    Extrae org_id, project_id y trace_id del estado del grafo.

    Uso en cada nodo de graph.py:
        async with telemetry.node_span("analyze_fr", state) as span:
            result = await invoke_structured(...)
            span.set_attribute("ovd.fr_type", result.fr_type)
            span.set_attribute("ovd.complexity", result.complexity)
    """
    tracer = get_tracer()

    # Recuperar contexto del ciclo padre si hay trace_id en el estado
    parent_context = _get_parent_context(state.get("trace_id", ""))

    with tracer.start_as_current_span(
        name=f"ovd.node.{node_name}",
        context=parent_context,
        kind=trace.SpanKind.INTERNAL,
    ) as span:
        span.set_attributes({
            "ovd.node":       node_name,
            "ovd.org_id":     state.get("org_id", ""),
            "ovd.project_id": state.get("project_id", ""),
            "ovd.thread_id":  state.get("session_id", ""),
            "ovd.stack_routing": state.get("stack_routing", "auto"),
        })
        try:
            yield span
        except Exception as e:
            span.set_status(StatusCode.ERROR, str(e))
            raise
        else:
            span.set_status(StatusCode.OK)


def _get_parent_context(trace_id_hex: str) -> Any:
    """
    Reconstruye el contexto OTEL a partir del trace_id hexadecimal.
    Permite que los spans de nodo sean hijos del span raíz del ciclo
    aunque se creen en contextos async separados.
    """
    if not trace_id_hex or len(trace_id_hex) != 32:
        return None
    try:
        from opentelemetry.trace import TraceFlags
        from opentelemetry.trace.span import SpanContext
        ctx = SpanContext(
            trace_id=int(trace_id_hex, 16),
            span_id=trace.INVALID_SPAN_ID,
            is_remote=True,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )
        return trace.set_span_in_context(NonRecordingSpan(ctx))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Helpers para atributos comunes
# ---------------------------------------------------------------------------

def record_token_usage(span: trace.Span, token_usage: dict[str, dict]) -> None:
    """
    Registra el uso de tokens por agente como atributos del span.
    Formato entrada: {"backend": {"input": 1200, "output": 800}, ...}
    """
    total_input  = sum(v.get("input", 0)  for v in token_usage.values() if isinstance(v, dict))
    total_output = sum(v.get("output", 0) for v in token_usage.values() if isinstance(v, dict))
    span.set_attributes({
        "ovd.tokens.total_input":  total_input,
        "ovd.tokens.total_output": total_output,
        "ovd.tokens.total":        total_input + total_output,
    })
    for agent, usage in token_usage.items():
        if isinstance(usage, dict):
            span.set_attribute(f"ovd.tokens.{agent}.input",  usage.get("input",  0))
            span.set_attribute(f"ovd.tokens.{agent}.output", usage.get("output", 0))


def record_qa_result(span: trace.Span, qa_result: dict) -> None:
    """Registra el resultado QA como atributos del span."""
    span.set_attributes({
        "ovd.qa.passed": qa_result.get("passed", False),
        "ovd.qa.score":  qa_result.get("score", 0),
        "ovd.qa.issues": len(qa_result.get("issues", [])),
    })


def record_security_result(span: trace.Span, security_result: dict) -> None:
    """Registra el resultado de security audit como atributos del span."""
    span.set_attributes({
        "ovd.security.passed":   security_result.get("passed", False),
        "ovd.security.score":    security_result.get("score", 0),
        "ovd.security.severity": security_result.get("severity", "none"),
        "ovd.security.vulns":    len(security_result.get("vulnerabilities", [])),
    })
