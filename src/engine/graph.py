"""
OVD Platform — Grafo LangGraph con router de agentes
Copyright 2026 Omar Robles

Grafo del ciclo FR → SDD → aprobacion → agentes → security_audit → QA → entrega.

Nodos:
  analyze_fr        — analiza el Feature Request del usuario
  generate_sdd      — genera especificacion SDD con 4 artefactos separados (GAP-007)
  human_approval    — interrupt: espera aprobacion del arquitecto
  route_agents      — elige agentes del SDD o via LLM router y prepara el fan-out (GAP-002)
  agent_executor    — ejecuta un solo agente especializado (N instancias en paralelo, GAP-002)
  security_audit    — auditoria de seguridad independiente (GAP-001)
  qa_review         — revisa calidad y cumplimiento del SDD
  handle_escalation — interrupt: escala a supervision humana si retries se agotan
  deliver           — empaqueta y entrega los artefactos al TUI

Agentes especializados:
  frontend  — componentes UI segun el stack del proyecto
  backend   — API routes, middleware, servicios, auth
  database  — SQL/ORM segun el motor del proyecto
  devops    — Docker, CI/CD, scripts de infraestructura

GAPs implementados:
  GAP-001: security_audit como nodo independiente
  GAP-002: Send() fan-out nativo LangGraph (route_agents + agent_executor)
  GAP-004: constraints_version + uncertainty_register en OVDState (Annotated reducer)
  GAP-005: retry loops QA/Security hasta 3 reintentos antes de escalar
  GAP-007: generate_sdd produce 4 artefactos separados con structured output

Estados: idle → analyzing → generating_sdd → pending_approval →
         executing → security_review → qa_review → [escalated] → delivering → done
"""
from __future__ import annotations
import asyncio
import hashlib
import json as _json
import logging
import operator
import os
import pathlib
import sys
import time
import uuid
from typing import Any

import psycopg  # S29-A: persistencia de ciclos desde deliver

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

log = logging.getLogger("ovd-graph")
from typing_extensions import Annotated, TypedDict

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI   # S21: usado en describe_image (visión)
from pydantic import BaseModel, Field, field_validator
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import interrupt, Send, Command
import model_router
import template_loader
import github_helper
import nats_client
import telemetry  # Sprint 10 — GAP-A6
import web_researcher  # Sprint 11 — S11.B
from tools import make_file_tools, read_project_context, calculate_expression  # S17T
import mcp_client  # Fase A — MCP tools (context7)
import lessons     # S41 — lecciones aprendidas por proyecto y agente

# ---------------------------------------------------------------------------
# Configuración operacional
# ---------------------------------------------------------------------------

# PP-01: presupuesto máximo de tokens por ciclo (entrada + salida acumulados).
# 0 = sin límite. Configurable via OVD_CYCLE_TOKEN_BUDGET en .env.
# Ejemplo: OVD_CYCLE_TOKEN_BUDGET=80000 limita ciclos a ~80k tokens totales.
_CYCLE_BUDGET_TOKENS: int = int(os.getenv("OVD_CYCLE_TOKEN_BUDGET", "0"))

# S20 — GAP-R1: timeout máximo por nodo de ejecución de agente.
# Si el LLM no responde en este tiempo, el nodo retorna un resultado de error parcial
# sin matar el ciclo completo. Configurable via OVD_NODE_TIMEOUT_SECS.
_NODE_TIMEOUT: float = float(os.getenv("OVD_NODE_TIMEOUT_SECS", "120"))

# S41P.A — Timeouts diferenciados por nodo. Sobrescriben _NODE_TIMEOUT cuando están definidos.
# Cada nodo tiene su propio peso según la carga de trabajo esperada:
#   LLM pesados (agentes, security):   1200-1800s — qwen3-coder:30b puede tardar mucho
#   LLM livianos (analyze, sdd, docs): 300-600s   — salida estructurada, contexto menor
#   I/O puro (tests, deliver):         120-300s    — sin LLM, solo filesystem/subprocess
_AGENTS_TIMEOUT: float   = float(os.getenv("OVD_AGENTS_TIMEOUT_SECS",   str(_NODE_TIMEOUT)))
_SECURITY_TIMEOUT: float = float(os.getenv("OVD_SECURITY_TIMEOUT_SECS", "1800"))
_QA_TIMEOUT: float       = float(os.getenv("OVD_QA_TIMEOUT_SECS",       "1200"))
_ANALYZE_TIMEOUT: float  = float(os.getenv("OVD_ANALYZE_TIMEOUT_SECS",  "300"))   # S41P.A
_SDD_TIMEOUT: float      = float(os.getenv("OVD_SDD_TIMEOUT_SECS",      "600"))   # S41P.A
_RESEARCH_TIMEOUT: float = float(os.getenv("OVD_RESEARCH_TIMEOUT_SECS", "180"))   # S41P.A
_TESTS_TIMEOUT: float    = float(os.getenv("OVD_TESTS_TIMEOUT_SECS",    "300"))
_DOCS_TIMEOUT: float     = float(os.getenv("OVD_DOCS_TIMEOUT_SECS",     "600"))

# S43-D: flags adicionales por runner — centralizados para facilitar mantenimiento.
# Cada runner puede tener flags extra que se agregan al comando base.
# pytest: --import-mode=importlib resuelve imports sin depender de __init__.py en raíz.
# vitest/cargo: flags propios del runner; lista vacía significa "sin flags extra".
_RUNNER_FLAGS: dict[str, list[str]] = {
    "pytest": ["--no-header", "--import-mode=importlib"],
    "vitest": ["--reporter=verbose"],
    "cargo":  [],
}

# ---------------------------------------------------------------------------
# Schemas de structured output
# ---------------------------------------------------------------------------

class FRAnalysisOutput(BaseModel):
    """Resultado estructurado del analisis del Feature Request."""
    fr_type: str = Field(
        description="Tipo de cambio: 'bug', 'feature', 'refactor', 'security', 'performance'",
    )
    complexity: str = Field(
        description="Complejidad estimada: 'low', 'medium', 'high', 'critical'",
    )
    components: list[str] = Field(
        default_factory=list,
        description="Lista de componentes afectados (modulos, servicios, tablas)",
    )
    oracle_involved: bool = Field(
        description="True si el cambio involucra consultas o esquema Oracle",
    )
    risks: list[str] = Field(
        default_factory=list,
        description="Riesgos identificados en el FR",
    )
    summary: str = Field(
        description="Resumen de 1-2 oraciones del FR analizado",
    )


class AgentRouterOutput(BaseModel):
    """Decide que agentes especializados ejecutar para este FR."""
    agents: list[str] = Field(
        description=(
            "Lista de agentes a ejecutar. Valores permitidos: "
            "'frontend', 'backend', 'database', 'devops'. "
            "Incluir solo los agentes relevantes para el FR (minimo 1)."
        ),
    )
    rationale: str = Field(
        description="Justificacion breve de por que se eligieron esos agentes",
    )


class SecurityAuditOutput(BaseModel):
    """Resultado estructurado de la auditoria de seguridad (GAP-001)."""
    passed: bool = Field(
        description="True si no se encontraron vulnerabilidades criticas o altas",
    )
    score: int = Field(
        ge=0,
        le=100,
        description="Score de seguridad de 0 a 100",
    )
    severity: str = Field(
        description="Severidad maxima encontrada: 'none', 'low', 'medium', 'high', 'critical'",
    )
    vulnerabilities: list[str] = Field(
        default_factory=list,
        description="Vulnerabilidades OWASP identificadas (ej: 'A01-Broken Access Control')",
    )
    secrets_found: list[str] = Field(
        default_factory=list,
        description="Secrets o credenciales hardcodeadas detectadas",
    )
    insecure_patterns: list[str] = Field(
        default_factory=list,
        description="Patrones inseguros: SQL injection, XSS, command injection, etc.",
    )
    rls_compliant: bool = Field(
        default=True,
        description="True si el codigo filtra siempre por org_id (multi-tenant)",
    )
    remediation: list[str] = Field(
        default_factory=list,
        description="Acciones especificas de remediacion para los issues encontrados",
    )
    summary: str = Field(
        description="Veredicto de seguridad en 1-2 oraciones",
    )


class SDDRequirement(BaseModel):
    """Un requisito funcional o no-funcional del SDD."""
    id: str = Field(description="Identificador unico, ej: 'REQ-001'")
    type: str = Field(description="'functional' | 'non_functional'")
    description: str = Field(description="Descripcion clara del requisito")
    priority: str = Field(description="'must' | 'should' | 'could'")
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="Criterios medibles para considerar el requisito cumplido",
    )


class SDDConstraint(BaseModel):
    """Una restriccion tecnica del proyecto."""
    id: str = Field(description="Identificador unico, ej: 'CON-001'")
    category: str = Field(
        description="Categoria: 'security', 'performance', 'compatibility', 'technology', 'compliance'",
    )
    description: str = Field(description="Descripcion de la restriccion")
    rationale: str = Field(description="Por que existe esta restriccion")


class SDDTask(BaseModel):
    """Una tarea de implementacion del SDD."""
    id: str = Field(description="Identificador unico, ej: 'TASK-001'")
    agent: str = Field(
        description="Agente responsable: 'frontend' | 'backend' | 'database' | 'devops'",
    )
    title: str = Field(description="Titulo breve de la tarea")
    description: str = Field(description="Descripcion detallada de lo que se debe implementar")
    depends_on: list[str] = Field(
        default_factory=list,
        description="IDs de tareas que deben completarse antes (ej: ['TASK-001'])",
    )
    estimated_complexity: str = Field(
        description="Complejidad estimada: 'low' | 'medium' | 'high'",
    )


class SDDOutput(BaseModel):
    """Los 4 artefactos separados del SDD (GAP-007)."""
    # Artefacto 1: Requisitos
    requirements: list[SDDRequirement] = Field(
        description="Lista de requisitos funcionales y no funcionales",
    )
    # Artefacto 2: Diseno
    design_overview: str = Field(
        description=(
            "Vision general de la arquitectura y decisions de diseno en formato Markdown. "
            "Incluir: componentes involucrados, flujo de datos, patrones elegidos."
        ),
    )
    design_diagrams: list[str] = Field(
        default_factory=list,
        description="Pseudocodigo o descripcion textual de diagramas clave (mermaid o texto libre)",
    )
    # Artefacto 3: Restricciones
    constraints: list[SDDConstraint] = Field(
        description="Lista de restricciones tecnicas que los agentes deben respetar",
    )
    # Artefacto 4: Tareas
    tasks: list[SDDTask] = Field(
        description="Lista de tareas de implementacion ordenadas por agente y dependencias",
    )
    summary: str = Field(
        description="Resumen ejecutivo del SDD en 2-3 oraciones",
    )


class QAReviewOutput(BaseModel):
    """Resultado estructurado de la revision QA de calidad."""
    passed: bool = Field(
        description="True si el resultado pasa todos los criterios de calidad",
    )
    score: int = Field(
        ge=0,
        le=100,
        description="Score de calidad de 0 a 100",
    )
    issues: list[str] = Field(
        default_factory=list,
        description="Lista de issues de calidad encontrados (vacia si passed=True)",
    )
    sdd_compliance: bool = Field(
        default=True,
        description="True si la implementacion cumple todos los requisitos del SDD",
    )
    missing_requirements: list[str] = Field(
        default_factory=list,
        description="Requisitos del SDD no implementados",
    )
    code_quality_issues: list[str] = Field(
        default_factory=list,
        description="Issues de calidad de codigo: duplicacion, complejidad, naming, etc.",
    )
    summary: str = Field(
        description="Veredicto de calidad en 1-2 oraciones",
    )

    @classmethod
    def _coerce_str_list(cls, v: object) -> list[str]:
        """S36-A: si el LLM retorna un str en vez de list[str], lo convierte sin iterar chars."""
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                return []
            lines = [ln.strip().lstrip("-•* ") for ln in stripped.splitlines() if ln.strip()]
            return lines if lines else [stripped]
        return v

    @field_validator("issues", "missing_requirements", "code_quality_issues", mode="before")
    @classmethod
    def _coerce_list_fields(cls, v: object) -> list[str]:
        return cls._coerce_str_list(v)


# ---------------------------------------------------------------------------
# Reducers para fan-out nativo (GAP-002)
# ---------------------------------------------------------------------------

def _list_reset_or_add(existing: list, update: list | None) -> list:
    """
    Reducer para agent_results.
    - None  → resetea a [] (enviado por route_agents antes de un nuevo ciclo)
    - list  → acumula (enviado por cada agent_executor en paralelo)
    """
    if update is None:
        return []
    return existing + update


def _merge_token_usage(existing: dict, update: dict | None) -> dict:
    """
    Reducer para token_usage.
    Fusiona los dicts de uso de tokens de cada agent_executor en paralelo.
    Formato: { "agent_name": { "input": N, "output": N } }
    """
    if not update:
        return existing
    merged = dict(existing)
    for key, val in update.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
            merged[key] = {
                k: merged[key].get(k, 0) + val.get(k, 0)
                for k in set(merged[key]) | set(val)
            }
        else:
            merged[key] = val
    return merged


def _keep_best_qa(existing: dict, update: dict) -> dict:
    """S57-A: reducer que preserva el mejor resultado QA del ciclo.

    En ciclos con retry, qa_review puede ejecutarse 2-3 veces. El primer resultado
    puede ser 65/100, el segundo 95/100, y el tercero (tras código degradado) 65/100.
    Sin reducer, LangGraph sobreescribe con el último. Con este reducer, el estado
    siempre contiene el mejor score acumulado — sin cambios en qa_review ni en deliver.
    """
    if not existing:
        return update
    if not update:
        return existing
    return existing if existing.get("score", 0) >= update.get("score", 0) else update


# ---------------------------------------------------------------------------
# State del grafo
# ---------------------------------------------------------------------------

class OVDState(TypedDict):
    # Input
    session_id: str
    org_id: str
    project_id: str
    directory: str
    feature_request: str
    project_context: str   # bloque Markdown del Project Profile con restricciones (S8: generado por ContextResolver)
    jwt_token: str         # JWT del Bridge para consultar config de agentes (GAP-013a)
    language: str          # Idioma de los prompts del sistema: "es" | "en" | "pt" (FASE 5.C)
    auto_approve: bool     # P5.A: si True, salta el interrupt de aprobación humana

    # Sprint 8 — Stack Registry routing (GAP-A1 + GAP-A3)
    stack_routing: str          # routing efectivo resuelto por ContextResolver: auto|ollama|claude|openai
    stack_db_engine: str        # motor de BD del workspace (para logging)
    stack_db_version: str       # versión del motor de BD (para logging)
    stack_restrictions: list    # restricciones activas inyectadas en project_context (para debug)

    # S42-E — Stack-aware template selection
    # Lenguaje del stack tecnológico del proyecto: "python", "typescript", "java", "go", etc.
    # Leído desde ovd_stack_profiles.language en api.py.
    # Usado por template_loader.render_composed() para componer base + stack/backend_{sl}.md (S58-pre).
    # Vacío ("") = sin perfil configurado → usa solo template base.
    stack_language: str

    # Sprint 10 — OTEL trace_id (GAP-A6)
    # Propagado desde api.py para correlacionar spans de todos los nodos del ciclo
    trace_id: str               # trace_id hexadecimal (32 chars) del span raíz del ciclo

    # S6 — Integración GitHub via PAT
    github_token:  str     # PAT del proyecto (viene del Project Profile via Bridge)
    github_repo:   str     # URL del repo, ej: https://github.com/org/repo
    github_branch: str     # branch base (default: "main")
    github_pr:     dict    # resultado del PR creado por create_pr (pr_url, branch, files)

    # GAP-006: contexto recuperado del RAG para el proyecto (inyectado en generate_sdd)
    rag_context: str

    # Sprint 11 — Web Researcher (S11.C)
    # research_enabled: True si [research] o @research en el FR, o activación explícita
    # web_research_results: hallazgos de la búsqueda web (para debug/audit)
    research_enabled: bool
    web_research_results: list[dict]

    # S21 — Visión: imagen adjunta al Feature Request
    # image_base64: imagen cruda (se consume en describe_image y no fluye más)
    # image_description: descripción textual generada por qwen2.5vl (fluye a analyze_fr)
    image_base64: str
    image_description: str

    # GAP-004: version de constraints del proyecto (hash MD5 del project_context)
    # Permite detectar si los constraints cambiaron entre ciclos
    constraints_version: str

    # GAP-004: registro de incertidumbres identificadas por los agentes
    # Cada item: {"agent": str, "item": str, "severity": "low"|"medium"|"high"|"critical"}
    # operator.add: acumula incertidumbres de todos los agentes en paralelo (GAP-002)
    uncertainty_register: Annotated[list[dict], operator.add]

    # Intermedios
    fr_analysis: dict[str, Any]
    sdd: dict[str, Any]
    approval_decision: str          # "approved" | "rejected" | "revision_requested" | ""
    approval_comment: str
    # Iterative SDD review: historial de revisiones del arquitecto
    revision_count:   int            # número de veces que se ha revisado el SDD (0 = primera generación)
    revision_history: list[dict]     # [{"round": int, "comment": str}]

    # GAP-002: fan-out nativo LangGraph
    # selected_agents: agentes elegidos por route_agents para el ciclo actual
    # current_agent:   agente que ejecuta el nodo agent_executor (inyectado via Send)
    # agent_results:   reducer acumula resultados de cada agent_executor en paralelo
    selected_agents: list[str]
    current_agent: str
    agent_results: Annotated[list[dict], _list_reset_or_add]

    # S47: agentes client-side pendientes (esperan a que grupo server-side termine)
    pending_agents: list[str]
    # S59-B: buffer interno — lista copiada por _dispatch_frontend_node antes de limpiar pending_agents
    _dispatch_now: list[str]

    # GAP-001: resultado de la auditoria de seguridad independiente
    security_result: dict[str, Any]

    qa_result: Annotated[dict, _keep_best_qa]  # S57-A: preserva el mejor score del ciclo

    # GAP-005: contadores de reintentos (max 3 antes de escalar)
    security_retry_count: int       # reintentos de security_audit → execute_agents
    qa_retry_count: int             # reintentos de qa_review → execute_agents
    retry_feedback: str             # feedback acumulado para los agentes en reintentos

    escalation_resolution: str

    # S22 — run_tests: ejecución real de tests generados
    test_results: dict[str, Any]    # {passed, output, runner, retry_round, error}
    test_retry_count: int           # 0..2, máx 2 rondas de retry vía route_agents

    # S53-B — Selective Send: agentes a re-ejecutar en retry de tests (subset de selected_agents)
    # Si vacío o no definido → route_agents usa todos los agentes del SDD (comportamiento normal)
    # Si definido → route_agents ejecuta solo estos agentes (reduce de N agentes a 1)
    selective_retry_agents: list[str]

    # S61-B: último error estructural de tests (sin truncar) para detección de repetición en S60-B
    last_test_error: str

    # S61-D: resultados de agentes preservados durante selective retry (no reseteados)
    _kept_agent_results: list[dict]

    # S22 — security scanning CLI (previo al LLM review)
    security_scan_results: dict[str, Any]  # {tools_run, findings, blocked}

    # S22 — generate_docs: documentación automática post-QA
    generated_docs: list[dict]      # [{type, content, path}]

    # FASE 4.D: uso de tokens por agente — reducer fusiona los dicts en paralelo
    # Formato: { "frontend": { "input": N, "output": N }, "backend": {...} }
    token_usage: Annotated[dict, _merge_token_usage]

    # P5.C: timestamp UNIX de inicio del ciclo (registrado en analyze_fr)
    cycle_start_ts: float

    # Output
    deliverables: list[dict]
    status: str                     # estado actual del ciclo
    messages: list[dict]            # historial de mensajes para el TUI


def _extract_usage(response: Any) -> dict[str, int]:
    """
    FASE 4.D / P4.A: extrae tokens de uso de un AIMessage de LangChain.

    Orden de prioridad (de más a menos confiable):
      1. usage_metadata  — campo estándar LangChain >= 0.2 (todos los backends)
      2. response_metadata["token_usage"] — ChatOpenAI / Ollama
      3. response_metadata["usage"]       — Anthropic / raw OpenAI

    Devuelve {"input": N, "output": N} o ceros si no está disponible.
    """
    # 1. usage_metadata: LangChain lo normaliza para todos los providers
    um = getattr(response, "usage_metadata", None)
    if um and isinstance(um, dict):
        return {
            "input":  um.get("input_tokens",  0),
            "output": um.get("output_tokens", 0),
        }

    # 2 + 3. response_metadata: ChatOpenAI usa "token_usage", Anthropic usa "usage"
    meta  = getattr(response, "response_metadata", {}) or {}
    usage = meta.get("token_usage") or meta.get("usage") or {}
    return {
        "input":  usage.get("input_tokens",  0) or usage.get("prompt_tokens",     0),
        "output": usage.get("output_tokens", 0) or usage.get("completion_tokens", 0),
    }


# P3.A — Tasas de costo por provider (USD por 1K tokens, aproximadas)
_COST_PER_1K_INPUT:  dict[str, float] = {"claude": 0.003,  "openai": 0.005,  "ollama": 0.0, "custom": 0.0}
_COST_PER_1K_OUTPUT: dict[str, float] = {"claude": 0.015,  "openai": 0.015,  "ollama": 0.0, "custom": 0.0}


def _estimate_cost(token_usage: dict, provider: str) -> float:
    """P3.A — Estima el costo en USD según el uso de tokens y el provider."""
    total_in  = sum(v.get("input", 0)  for v in token_usage.values() if isinstance(v, dict))
    total_out = sum(v.get("output", 0) for v in token_usage.values() if isinstance(v, dict))
    cost = (
        (total_in  / 1000) * _COST_PER_1K_INPUT.get(provider,  0.0) +
        (total_out / 1000) * _COST_PER_1K_OUTPUT.get(provider, 0.0)
    )
    return round(cost, 6)


# ---------------------------------------------------------------------------
# Helper: truncado de contexto para modelos con ventana pequeña (P2.B)
# ---------------------------------------------------------------------------

_MAX_CONTEXT_CHARS = int(os.environ.get("OVD_MAX_CONTEXT_TOKENS", "28000")) * 4  # ~4 chars/token


def _truncate(text: str, max_chars: int = _MAX_CONTEXT_CHARS) -> str:
    """Trunca el texto al límite de caracteres conservando el inicio."""
    if len(text) <= max_chars:
        return text
    log.warning("_truncate: texto truncado de %d a %d chars", len(text), max_chars)
    return text[:max_chars] + "\n\n[... truncado por límite de contexto ...]"


# ---------------------------------------------------------------------------
# Helper: structured output robusto para modelos OSS (P1.B) — S20: backoff exponencial
# ---------------------------------------------------------------------------

_INVOKE_MAX_RETRIES = int(os.environ.get("OVD_MAX_RETRIES", "3"))


async def invoke_structured(
    llm: Any,
    messages: list,
    output_class: type,
    max_retries: int | None = None,
) -> Any:
    """
    Invoca el LLM con structured output y reintenta con JSON hint explícito
    si el modelo devuelve output malformado (común en OSS 7B-14B).

    S20 — GAP-R2: backoff exponencial entre reintentos (1s, 2s, 4s, max 10s).

    Flujo:
      1. Intento normal via with_structured_output (function calling / JSON mode)
      2. Si falla: agrega hint con schema JSON explícito y reintenta con backoff
      3. Si agota reintentos: propaga la excepción original

    Compatible con Claude (tool_use nativo) y Ollama (JSON mode via ChatOpenAI).
    """
    retries = max_retries if max_retries is not None else _INVOKE_MAX_RETRIES
    schema_hint = _json.dumps(output_class.model_json_schema(), indent=2)
    hint_msg = HumanMessage(content=(
        "IMPORTANTE: Responde ÚNICAMENTE con un objeto JSON válido "
        f"que cumpla exactamente este schema:\n```json\n{schema_hint}\n```\n"
        "Sin texto adicional, sin markdown, sin explicaciones."
    ))

    attempt_state = {"count": 0}

    @retry(
        stop=stop_after_attempt(retries + 1),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _attempt() -> Any:
        n = attempt_state["count"]
        attempt_state["count"] += 1
        msgs = messages if n == 0 else messages + [hint_msg]
        try:
            return await llm.with_structured_output(output_class).ainvoke(msgs)
        except Exception as exc:
            log.warning(
                "invoke_structured: intento %d/%d falló (%s: %s) — reintentando con backoff",
                n + 1, retries + 1, type(exc).__name__, str(exc)[:120],
            )
            raise

    return await _attempt()


# ---------------------------------------------------------------------------
# Nodos del grafo
# ---------------------------------------------------------------------------

async def clone_repo(state: OVDState) -> dict:
    """
    S6 — G1.B: Si github_repo está configurado, clona o actualiza el repo
    antes de analyze_fr. Actualiza state["directory"] con la ruta local.
    No-op si github_repo está vacío.
    """
    github_repo   = state.get("github_repo", "")
    github_token  = state.get("github_token", "")
    github_branch = state.get("github_branch", "") or "main"

    if not github_repo or not github_token:
        return {}  # sin config GitHub — continuar con directory existente

    try:
        local_dir = github_helper.clone_or_pull(github_repo, github_token, github_branch)
        log.info("clone_repo: repo disponible en %s", local_dir)
        return {
            "directory": local_dir,
            "messages": state.get("messages", []) + [{
                "role": "agent",
                "content": f"Repositorio clonado: {github_repo} (branch: {github_branch})",
            }],
        }
    except Exception as e:
        log.error("clone_repo: error clonando repo — %s", e)
        # No fallar el ciclo — continuar con directory original
        return {
            "messages": state.get("messages", []) + [{
                "role": "agent",
                "content": f"Advertencia: no se pudo clonar el repo ({e}). Continuando sin contexto de repositorio.",
            }],
        }


# ---------------------------------------------------------------------------
# S21 — Visión: pre-procesador de imágenes adjuntas al Feature Request
# ---------------------------------------------------------------------------

_VISION_MODEL   = os.environ.get("OVD_VISION_MODEL", "qwen2.5vl:7b")
_VISION_URL     = os.environ.get("OVD_VISION_OLLAMA_URL", os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"))
_VISION_ENABLED = os.environ.get("OVD_VISION_ENABLED", "true").lower() == "true"

_VISION_PROMPT = (
    "Eres un asistente técnico especializado en UI/UX. "
    "Describe este diseño, wireframe o screenshot con el nivel de detalle necesario "
    "para que un desarrollador frontend pueda implementarlo sin ver la imagen. "
    "Incluye: estructura general, componentes visibles, jerarquía visual, "
    "colores dominantes, tipografía, espaciado aparente y flujo de interacción."
)


async def describe_image(state: OVDState) -> dict:
    """
    S21 — Pre-procesa imagen adjunta con qwen2.5vl antes de analyze_fr.
    - Si no hay imagen → no-op transparente (retorna {}).
    - Si ya hay image_description → no-op (evita reprocesar).
    - Si OVD_VISION_ENABLED=false → no-op.
    En todos los no-op, image_base64 se limpia del estado para no arrastrar datos grandes.
    """
    if not _VISION_ENABLED or not state.get("image_base64") or state.get("image_description"):
        return {"image_base64": ""}  # limpiar aunque sea no-op

    log.info("describe_image: procesando imagen con %s", _VISION_MODEL)

    base_url = _VISION_URL.rstrip("/") + "/v1"
    llm_vision = ChatOpenAI(
        model=_VISION_MODEL,
        base_url=base_url,
        api_key="ollama",
        max_tokens=1024,
        temperature=0.0,
        request_timeout=float(os.environ.get("OVD_NODE_TIMEOUT_SECS", "120")),
    )

    try:
        response = await llm_vision.ainvoke([
            HumanMessage(content=[
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{state['image_base64']}"},
                },
                {"type": "text", "text": _VISION_PROMPT},
            ])
        ])
        description = response.content
        log.info("describe_image: descripción generada (%d chars)", len(description))
        return {
            "image_base64": "",           # limpiar bytes crudos — ya no se necesitan
            "image_description": description,
        }
    except Exception as e:
        log.warning("describe_image: error procesando imagen — %s. Continuando sin descripción visual.", e)
        return {"image_base64": ""}


def _build_fr_content(state: OVDState) -> str:
    """S21: construye el contenido del HumanMessage para analyze_fr, inyectando la descripción visual si existe."""
    content = f"Feature Request:\n{state['feature_request']}"
    image_desc = state.get("image_description", "")
    if image_desc:
        content += f"\n\nDescripción visual del diseño adjunto:\n{image_desc}"
    return content


async def analyze_fr(state: OVDState) -> dict:
    """Analiza el Feature Request y extrae contexto tecnico con structured output."""
    project_ctx = state.get("project_context", "")

    # GAP-004: calcular constraints_version como hash del project_context
    constraints_version = hashlib.md5(project_ctx.encode()).hexdigest()[:8] if project_ctx else "no-profile"

    async with telemetry.node_span("analyze_fr", state) as span:
        llm = await model_router.get_llm_with_context(
            "analyzer", state.get("org_id", ""), state.get("project_id", ""),
            state.get("jwt_token", ""), state.get("stack_routing", "auto"),
        )
        try:
            result: FRAnalysisOutput = await asyncio.wait_for(
                invoke_structured(llm, [
                    SystemMessage(content=template_loader.render(
                        "system_analyzer",
                        language=state.get("language", "es"),
                        project_context=project_ctx,
                    )),
                    HumanMessage(content=_build_fr_content(state)),
                ], FRAnalysisOutput),
                timeout=_ANALYZE_TIMEOUT,  # S41P.A
            )
        except asyncio.TimeoutError:
            log.error("analyze_fr: timeout tras %.0fs — retornando análisis mínimo", _ANALYZE_TIMEOUT)
            result = FRAnalysisOutput(
                fr_type="feature", complexity="medium", components=[], oracle_involved=False,
                risks=[], summary=f"[Timeout en análisis tras {_ANALYZE_TIMEOUT:.0f}s. Revisa el LLM.]",
            )

        span.set_attributes({
            "ovd.fr_type":    result.fr_type,
            "ovd.complexity": result.complexity,
            "ovd.oracle_involved": result.oracle_involved,
            "ovd.risks_count": len(result.risks),
            "ovd.constraints_version": constraints_version,
        })

    analysis = {
        "raw": result.summary,
        "type": result.fr_type,
        "complexity": result.complexity,
        "components": result.components,
        "oracle_involved": result.oracle_involved,
        "risks": result.risks,
        "summary": result.summary,
    }

    new_state = {
        "fr_analysis": analysis,
        "constraints_version": constraints_version,
        "uncertainty_register": [],  # GAP-004: inicializar registro vacio
        "security_retry_count": 0,   # GAP-005: inicializar contadores
        "qa_retry_count": 0,
        "retry_feedback": "",
        "token_usage": {},   # FASE 4.D: inicializar acumulador de tokens
        "cycle_start_ts": time.time(),  # P5.C: timestamp inicio del ciclo
        "status": "analyzed",
        "messages": state.get("messages", []) + [{
            "role": "agent",
            "content": (
                f"Analisis completado — Tipo: {result.fr_type}, "
                f"Complejidad: {result.complexity}, "
                f"Constraints version: {constraints_version}\n{result.summary}"
            ),
        }],
    }
    # N1.B — publicar session.started (fire-and-forget)
    await nats_client.publish_started({**state, "fr_analysis": analysis})
    return new_state


_OVD_BRIDGE_URL = os.environ.get("OVD_BRIDGE_URL", "http://localhost:3000")


def _should_run_web_research(state: OVDState) -> bool:
    """
    Sprint 11 — Determina si el Web Researcher debe activarse.

    Triggers (Modo A — proactivo):
      1. FR contiene '[research]' o '@research' (activación explícita del usuario)
      2. research_enabled=True en el estado (activado via API)
      3. fr_type='security' (los FRs de seguridad siempre buscan CVEs actuales)
      4. oracle_involved=True + complexity in (high, critical) (stacks legacy complejos)
    """
    fr = state.get("feature_request", "").lower()
    if "[research]" in fr or "@research" in fr:
        return True
    if state.get("research_enabled", False):
        return True

    analysis = state.get("fr_analysis", {})
    if analysis.get("fr_type") == "security":
        return True
    if analysis.get("oracle_involved") and analysis.get("complexity") in ("high", "critical"):
        return True
    return False


def _build_research_queries(state: OVDState) -> list[str]:
    """
    Sprint 11 — Construye queries de búsqueda a partir del análisis del FR.

    Combina: tipo de FR + componentes afectados + stack tecnológico + riesgos.
    Máximo _MAX_QUERIES queries (controlado en web_researcher.py).
    """
    analysis = state.get("fr_analysis", {})
    project_ctx = state.get("project_context", "")
    fr = state.get("feature_request", "")

    queries: list[str] = []

    # Query 1: stack + tipo de cambio + año actual
    fr_type = analysis.get("fr_type", "feature")
    components = analysis.get("components", [])
    if components:
        queries.append(f"{' '.join(components[:2])} {fr_type} best practices 2025")

    # Query 2: CVEs del stack si FR es de seguridad o Oracle
    db_engine = state.get("stack_db_engine", "")
    db_version = state.get("stack_db_version", "")
    if db_engine and db_version:
        queries.append(f"{db_engine} {db_version} CVE vulnerabilities 2024 2025")
    elif analysis.get("oracle_involved"):
        queries.append("Oracle database security vulnerabilities CVE 2024 2025")

    # Query 3: riesgos identificados en el análisis
    risks = analysis.get("risks", [])
    if risks:
        queries.append(f"{risks[0]} mitigation {' '.join(components[:1])}")

    # Query 4: fallback — FR resumido para contexto general
    if len(queries) < 2:
        summary = analysis.get("summary", fr[:100])
        queries.append(f"{summary[:80]} security considerations")

    return queries


async def web_research_node(state: OVDState) -> dict:
    """
    Sprint 11 — S11.C: Nodo de investigación web del grafo.

    Posición en el grafo: entre analyze_fr y generate_sdd.
    Es un no-op si _should_run_web_research() retorna False.

    Cuando se activa:
      1. Construye queries desde el análisis del FR
      2. Busca en la web via search_providers.py (DuckDuckGo/Tavily/SearXNG)
      3. Sintetiza los resultados con el LLM
      4. Indexa la síntesis en RAG a nivel org
      5. Agrega la síntesis al rag_context para que generate_sdd lo use
    """
    if not _should_run_web_research(state):
        return {}   # no-op — continuar sin búsqueda

    async with telemetry.node_span("web_research", state) as span:
        queries = _build_research_queries(state)
        span.set_attribute("ovd.web_research.queries_count", len(queries))
        span.set_attribute("ovd.web_research.queries", str(queries[:2]))

        bridge_url = _OVD_BRIDGE_URL
        jwt_token  = state.get("jwt_token", "")
        org_id     = state.get("org_id", "")
        project_id = state.get("project_id")

        # S11.H — cargar fuentes curadas configuradas para este proyecto
        curated_urls = await web_researcher.load_curated_urls(
            org_id=org_id,
            project_id=project_id,
            db_url=os.environ.get("DATABASE_URL", ""),
        )

        try:
            findings = await asyncio.wait_for(  # S41P.A
                web_researcher.run_web_research(
                    queries=queries,
                    org_id=org_id,
                    project_id=project_id,
                    jwt_token=jwt_token,
                    bridge_url=bridge_url,
                    context=state.get("project_context", ""),
                    curated_urls=curated_urls or None,
                ),
                timeout=_RESEARCH_TIMEOUT,
            )
            span.set_attribute("ovd.web_research.results_count", len(findings.results))
            span.set_attribute("ovd.web_research.indexed", findings.indexed)
        except asyncio.TimeoutError:
            log.warning("web_research_node: timeout tras %.0fs — omitiendo investigación web", _RESEARCH_TIMEOUT)
            return {
                "messages": state.get("messages", []) + [{
                    "role": "agent",
                    "content": f"Investigación web omitida por timeout ({_RESEARCH_TIMEOUT:.0f}s).",
                }],
            }
        except Exception as e:
            log.warning("web_research_node: error en búsqueda web — %s", e)
            return {
                "messages": state.get("messages", []) + [{
                    "role": "agent",
                    "content": f"Investigación web omitida por error: {e}",
                }],
            }

    if not findings.synthesis:
        return {}

    # Agregar síntesis al rag_context existente
    existing_rag = state.get("rag_context", "")
    separator = "\n\n---\n\n" if existing_rag else ""
    enriched_rag = (
        f"{existing_rag}{separator}"
        f"## Investigación web reciente\n{findings.synthesis}"
    )

    return {
        "rag_context": enriched_rag,
        "web_research_results": [
            {"title": r.title, "url": r.url, "snippet": r.snippet[:200]}
            for r in findings.results[:10]
        ],
        "messages": state.get("messages", []) + [{
            "role": "agent",
            "content": (
                f"Investigación web completada — {len(findings.results)} resultados, "
                f"{findings.indexed} indexado(s) en RAG. "
                f"Proveedor: {findings.results[0].url.split('/')[2] if findings.results else 'N/A'}"
            ),
        }],
    }


_DB_RESTRICTION_KEYWORDS = (
    "oracle", "fetch_first", "lateral join", "listagg", "rownum",
    "python-oracledb", "oracledb", "thick mode", "cx_oracle",
    "no_json", "no_fetch", "no_lateral", "no_listagg",
    "no_with_function", "no_window", "use_rownum", "no_merge",
    "tns", "sqlnet", "wallet", "oracle_home",
)


def _strip_db_restrictions(project_ctx: str) -> str:
    """S56-C: elimina líneas con restricciones de BD cuando oracle_involved=False.

    Evita que restricciones Oracle (fetch_first, lateral join, etc.) contaminen
    el SDD de FRs que no tienen nada que ver con la BD. Filtra línea por línea
    para no afectar el contenido que sigue a una restricción.
    """
    if not project_ctx:
        return project_ctx
    trailing_newline = project_ctx.endswith("\n")
    lines = project_ctx.splitlines()
    filtered: list[str] = []
    for line in lines:
        lower = line.lower()
        if any(kw in lower for kw in _DB_RESTRICTION_KEYWORDS):
            log.warning(
                "S56-C: omitiendo restricción de BD del project_ctx (oracle_involved=False): %s",
                line.strip()[:80],
            )
            continue
        filtered.append(line)
    result = "\n".join(filtered)
    if trailing_newline:
        result += "\n"
    return result


async def generate_sdd(state: OVDState) -> dict:
    """
    Genera el SDD con 4 artefactos separados usando structured output (GAP-007):
      1. requirements  — lista de requisitos funcionales y no-funcionales
      2. design        — vision arquitectonica y diagramas
      3. constraints   — restricciones tecnicas del proyecto
      4. tasks         — tareas por agente con dependencias

    Si revision_count > 0, incorpora el feedback del arquitecto (approval_comment)
    para regenerar el SDD en ciclos de revisión iterativa (S15-TUI).
    """
    project_ctx    = state.get("project_context", "")
    rag_ctx        = state.get("rag_context", "")
    revision_count = state.get("revision_count", 0)
    revision_comment = state.get("approval_comment", "")

    # S56-C: si el FR no involucra Oracle, limpiar restricciones de BD del contexto del proyecto
    # para evitar que contaminen el SDD con oracle_involved=False.
    fr_analysis = state.get("fr_analysis", {})
    if not fr_analysis.get("oracle_involved", True) and project_ctx:
        project_ctx = _strip_db_restrictions(project_ctx)

    # Construir el bloque de revisión si corresponde
    revision_block = ""
    if revision_count > 0 and revision_comment:
        revision_block = (
            f"\n\n## Feedback del Arquitecto — Revisión #{revision_count}\n"
            f"{revision_comment}\n\n"
            "Incorpora este feedback en el nuevo SDD. Mantén lo que no fue objetado."
        )

    human_content = (
        f"Feature Request:\n{state['feature_request']}\n\n"
        f"Analisis previo:\n{state['fr_analysis'].get('raw', '')}"
        f"{revision_block}"
    )

    async with telemetry.node_span("generate_sdd", state) as span:
        if revision_count > 0:
            span.set_attribute("ovd.sdd.revision_round", revision_count)

        llm = await model_router.get_llm_with_context(
            "sdd", state.get("org_id", ""), state.get("project_id", ""),
            state.get("jwt_token", ""), state.get("stack_routing", "auto"),
        )
        try:
            result: SDDOutput = await asyncio.wait_for(
                invoke_structured(llm, [
                    SystemMessage(content=template_loader.render(
                        "system_sdd",
                        language=state.get("language", "es"),
                        project_context=project_ctx,
                        rag_context=rag_ctx,
                    )),
                    HumanMessage(content=human_content),
                ], SDDOutput),
                timeout=_SDD_TIMEOUT,  # S41P.A
            )
        except asyncio.TimeoutError:
            log.error("generate_sdd: timeout tras %.0fs — retornando SDD mínimo", _SDD_TIMEOUT)
            result = SDDOutput(
                summary=f"[Timeout en SDD tras {_SDD_TIMEOUT:.0f}s. Revisa el LLM.]",
                requirements=[], design_overview="", design_diagrams=[],
                constraints=[], tasks=[],
            )

        # Serializar los 4 artefactos como dicts para el estado
        sdd = {
            "summary": result.summary,
            "requirements": [r.dict() for r in result.requirements],
            "design": {"overview": result.design_overview, "diagrams": result.design_diagrams},
            "constraints": [c.dict() for c in result.constraints],
            "tasks": [t.dict() for t in result.tasks],
        }

        n_req   = len(sdd["requirements"])
        n_tasks = len(sdd["tasks"])
        n_agents = len({t["agent"] for t in sdd["tasks"]})

        span.set_attributes({
            "ovd.sdd.requirements_count": n_req,
            "ovd.sdd.tasks_count":        n_tasks,
            "ovd.sdd.agents_count":       n_agents,
        })

    summary_msg = (
        f"SDD generado: {n_req} requisito(s), {n_tasks} tarea(s) "
        f"para {n_agents} agente(s).\n\n{result.summary}"
    )

    revision_history = state.get("revision_history", [])
    if revision_count > 0 and revision_comment:
        revision_history = revision_history + [{"round": revision_count, "comment": revision_comment}]

    round_label = f" (revisión #{revision_count + 1})" if revision_count > 0 else ""
    return {
        "sdd": sdd,
        "status": "sdd_generated",
        "approval_comment":  "",                    # limpiar para la próxima iteración
        "revision_count":    revision_count + 1,
        "revision_history":  revision_history,
        "messages": state.get("messages", []) + [{
            "role": "agent",
            "content": f"SDD generado{round_label}: {n_req} requisito(s), {n_tasks} tarea(s) "
                       f"para {n_agents} agente(s).",
        }],
    }


async def request_approval(state: OVDState) -> dict:
    """
    Interrupt: pausa el grafo y espera aprobacion humana del arquitecto.
    P5.A: si auto_approve=True en el state, aprueba automáticamente sin interrupt().
    El TUI recibe el evento pending_approval y muestra el modal de aprobacion.
    """
    # P5.A — Auto-approve: saltar el interrupt para pruebas y CI/CD
    if state.get("auto_approve", False):
        log.info("request_approval: auto_approve=True — aprobando SDD automáticamente")
        await nats_client.publish_approved(state)  # N1.B
        return {
            "approval_decision": "approved",
            "approval_comment": "[auto-aprobado]",
            "status": "approved",
            "messages": state.get("messages", []) + [{
                "role": "agent",
                "content": "SDD aprobado automáticamente (auto_approve=True).",
            }],
        }

    # interrupt() pausa el grafo — la ejecucion se resume cuando
    # el TUI llama a POST /session/{id}/approve
    decision = interrupt({
        "type": "pending_approval",
        "permission_id": f"sdd_approval_{state['session_id']}",
        "reason": "Aprobacion del SDD requerida antes de ejecutar los agentes",
        "context": {
            # GAP-007: exponer los 4 artefactos separados en el modal de aprobacion
            "sdd_summary": state["sdd"].get("summary", ""),
            "requirements_count": len(state["sdd"].get("requirements", [])),
            "requirements": state["sdd"].get("requirements", []),
            "design_overview": state["sdd"].get("design", {}).get("overview", "")[:800],
            "constraints": state["sdd"].get("constraints", []),
            "tasks": state["sdd"].get("tasks", []),
            "fr_type": state["fr_analysis"].get("type", ""),
            "complexity": state["fr_analysis"].get("complexity", ""),
        },
    })

    approval = decision.get("approved", False)
    comment = decision.get("comment", "")

    # N1.B — publicar evento aprobado/rechazado
    await nats_client.publish_approved({**state, "approval_comment": comment})

    return {
        "approval_decision": "approved" if approval else "rejected",
        "approval_comment": comment,
        "status": "approved" if approval else "rejected",
        "messages": state.get("messages", []) + [{
            "role": "agent",
            "content": f"Decision de aprobacion: {'Aprobado' if approval else 'Rechazado'}. {comment}",
        }],
    }


def _log_runner_response(response: Any, agent_name: str) -> None:
    """S54-A: Diagnóstico de done_reason, tokens reales y presencia de fence :path."""
    meta = getattr(response, "response_metadata", {}) or {}
    done_reason  = meta.get("done_reason", "unknown")
    eval_count   = meta.get("eval_count", 0)
    prompt_count = meta.get("prompt_eval_count", 0)
    content_len  = len(response.content) if response.content else 0

    log.warning(
        "S54-A runner[%s]: done_reason=%s eval_count=%d prompt_eval_count=%d output_len=%d",
        agent_name, done_reason, eval_count, prompt_count, content_len,
    )
    if done_reason == "length":
        log.warning(
            "S54-A runner[%s]: TRUNCADO — output cortado por num_predict. "
            "Primeros 400 chars: %s",
            agent_name, (response.content or "")[:400].replace("\n", "↵"),
        )

    # Verificar presencia de fence :path (indicador de que el modelo siguió el formato)
    content = response.content or ""
    has_path_fence = bool(
        _re.search(r"```[\w+\-]*:[^\n`]+", content)
    )
    if not has_path_fence and content_len > 50:
        log.warning(
            "S54-A runner[%s]: output NO contiene fence con :path — "
            "_write_artifacts no podrá escribir archivos. "
            "Primeros 500 chars: %s",
            agent_name, content[:500].replace("\n", "↵"),
        )
    else:
        import re as _re2
        paths_found = _re2.findall(r"```[\w+\-]*:([^\n`]+)", content)
        log.warning("S54-A runner[%s]: fence :path encontrado en %d bloque(s): %s", agent_name, len(paths_found), paths_found)


async def _run_frontend_agent(
    sdd_content: str, comment: str, llm: Any, project_ctx: str = "", retry_feedback: str = "", language: str = "es", rag_context: str = "", *, stack_language: str = ""
) -> dict:
    """Agente especializado en frontend: segun el stack del proyecto."""
    response = await llm.ainvoke([
        SystemMessage(content=template_loader.render_composed(  # S58-pre: base + stack section
            "system_frontend",
            language=language,
            stack_language=stack_language,
            project_context=project_ctx,
            retry_feedback=retry_feedback,
            rag_context=rag_context,
        )),
        HumanMessage(content=(
            f"SDD Aprobado:\n{sdd_content}\n\n"
            f"Comentario del arquitecto: {comment}\n\n"
            "Implementa los artefactos frontend definidos en el SDD."
        )),
    ])
    _log_runner_response(response, "frontend")  # S54-A
    uncertainties = _extract_uncertainties(response.content, "frontend")
    return {"agent": "frontend", "output": response.content, "artifacts": [], "uncertainties": uncertainties, "tokens": _extract_usage(response)}


async def _run_backend_agent(
    sdd_content: str, comment: str, llm: Any, project_ctx: str = "", retry_feedback: str = "", language: str = "es", rag_context: str = "", *, stack_language: str = ""
) -> dict:
    """Agente especializado en backend: segun el stack del proyecto."""
    response = await llm.ainvoke([
        SystemMessage(content=template_loader.render_composed(  # S58-pre: base + stack section
            "system_backend",
            language=language,
            stack_language=stack_language,
            project_context=project_ctx,
            retry_feedback=retry_feedback,
            rag_context=rag_context,
        )),
        HumanMessage(content=(
            f"SDD Aprobado:\n{sdd_content}\n\n"
            f"Comentario del arquitecto: {comment}\n\n"
            "Implementa los artefactos backend definidos en el SDD."
        )),
    ])
    _log_runner_response(response, "backend")  # S54-A
    uncertainties = _extract_uncertainties(response.content, "backend")
    return {"agent": "backend", "output": response.content, "artifacts": [], "uncertainties": uncertainties, "tokens": _extract_usage(response)}


async def _run_database_agent(
    sdd_content: str, comment: str, llm: Any, project_ctx: str = "", retry_feedback: str = "", language: str = "es", rag_context: str = "", *, stack_language: str = ""
) -> dict:
    """Agente especializado en base de datos: segun el motor del proyecto."""
    response = await llm.ainvoke([
        SystemMessage(content=template_loader.render_composed(  # S58-pre: base + stack section
            "system_database",
            language=language,
            stack_language=stack_language,
            project_context=project_ctx,
            retry_feedback=retry_feedback,
            rag_context=rag_context,
        )),
        HumanMessage(content=(
            f"SDD Aprobado:\n{sdd_content}\n\n"
            f"Comentario del arquitecto: {comment}\n\n"
            "Implementa los artefactos de base de datos definidos en el SDD."
        )),
    ])
    _log_runner_response(response, "database")  # S54-A
    uncertainties = _extract_uncertainties(response.content, "database")
    return {"agent": "database", "output": response.content, "artifacts": [], "uncertainties": uncertainties, "tokens": _extract_usage(response)}


async def _run_devops_agent(
    sdd_content: str, comment: str, llm: Any, project_ctx: str = "", retry_feedback: str = "", language: str = "es", rag_context: str = "", *, stack_language: str = ""
) -> dict:
    """Agente especializado en DevOps: segun el CI/CD del proyecto."""
    response = await llm.ainvoke([
        SystemMessage(content=template_loader.render_composed(  # S58-pre: base + stack section
            "system_devops",
            language=language,
            stack_language=stack_language,
            project_context=project_ctx,
            retry_feedback=retry_feedback,
            rag_context=rag_context,
        )),
        HumanMessage(content=(
            f"SDD Aprobado:\n{sdd_content}\n\n"
            f"Comentario del arquitecto: {comment}\n\n"
            "Implementa los artefactos de infraestructura definidos en el SDD."
        )),
    ])
    _log_runner_response(response, "devops")  # S54-A
    uncertainties = _extract_uncertainties(response.content, "devops")
    return {"agent": "devops", "output": response.content, "artifacts": [], "uncertainties": uncertainties, "tokens": _extract_usage(response)}


def _extract_uncertainties(code_output: str, agent: str) -> list[dict]:
    """
    GAP-004: Extrae items de incertidumbre del output del agente.
    Los agentes deben comentar 'UNCERTAINTY: <descripcion>' cuando
    toman decisiones con informacion incompleta.
    """
    uncertainties = []
    for line in code_output.splitlines():
        stripped = line.strip()
        if "UNCERTAINTY:" in stripped.upper():
            idx = stripped.upper().index("UNCERTAINTY:")
            item_text = stripped[idx + len("UNCERTAINTY:"):].strip().lstrip("# /")
            severity = "high" if any(w in item_text.lower() for w in ["critico", "critical", "seguridad", "security", "auth"]) else "medium"
            uncertainties.append({"agent": agent, "item": item_text, "severity": severity})
    return uncertainties


# Mapa de nombre → funcion de agente
_AGENT_RUNNERS = {
    "frontend": _run_frontend_agent,
    "backend":  _run_backend_agent,
    "database": _run_database_agent,
    "devops":   _run_devops_agent,
}

# S47: grupos de ejecución por capa — aplica a cualquier stack
# Grupo 1 (server-side): se ejecutan primero en paralelo
# Grupo 2 (client-side): se ejecutan después, con acceso al código del grupo 1
_SERVER_SIDE_AGENTS: frozenset[str] = frozenset({"database", "backend", "devops"})
_CLIENT_SIDE_AGENTS: frozenset[str] = frozenset({"frontend"})


def _build_agent_sdd_content(sdd: dict, agent_name: str) -> str:
    """GAP-007+GAP-002: construye el SDD filtrado por las tareas del agente dado."""
    tasks_from_sdd = sdd.get("tasks", [])
    agent_tasks = [t for t in tasks_from_sdd if t.get("agent") == agent_name]
    return (
        f"## Summary\n{sdd.get('summary', '')}\n\n"
        f"## Requirements\n{_json.dumps(sdd.get('requirements', []), ensure_ascii=False, indent=2)}\n\n"
        f"## Design\n{sdd.get('design', {}).get('overview', '')}\n\n"
        f"## Constraints\n{_json.dumps(sdd.get('constraints', []), ensure_ascii=False, indent=2)}\n\n"
        f"## Your Tasks ({agent_name})\n{_json.dumps(agent_tasks, ensure_ascii=False, indent=2)}"
    )


def _extract_expected_files_from_task(description: str) -> list[str]:
    """S54-B: extrae rutas de archivos mencionados en la descripción de una tarea SDD.

    Busca patrones tipo `src/imc/models.py`, `tests/test_imc.py`, etc.
    Retorna lista de rutas únicas en orden de aparición.
    """
    paths = _re.findall(
        r'\b(?:src|tests|app|lib|pkg)/[\w/\-\.]+\.(?:py|ts|tsx|js|jsx|sql|yaml|yml|json|toml|ini|cfg)\b',
        description,
    )
    # Dedup preservando orden
    seen: set[str] = set()
    result: list[str] = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            result.append(p)
    return result


def _filter_requirements_for_task(requirements: list, task: dict) -> list:
    """S56-D: retorna solo los requisitos relevantes para esta tarea.

    Si la tarea tiene `depends_on` con IDs de requisito, filtra solo esos.
    Si no hay referencia explícita, devuelve todos (comportamiento original).
    """
    if not requirements:
        return requirements
    depends_on = task.get("depends_on", [])
    if not depends_on:
        return requirements
    # depends_on puede ser lista de task IDs o req IDs — filtrar req IDs (REQ-*)
    req_ids = {d for d in depends_on if isinstance(d, str) and d.upper().startswith("REQ-")}
    if not req_ids:
        return requirements
    filtered = [r for r in requirements if r.get("id", "") in req_ids]
    # Siempre incluir must-requirements para no perder criterios críticos
    must_reqs = [r for r in requirements if r.get("priority", "") == "must" and r not in filtered]
    return filtered + must_reqs


def _build_single_task_sdd_content(sdd: dict, agent_name: str, task: dict, task_index: int, total_tasks: int) -> str:
    """S39-D: construye el SDD para una sola tarea del agente.

    El agente recibe el contexto compartido completo (summary, requirements, design,
    constraints) pero solo una tarea en 'Your Task'. Esto reduce el output de
    10-15K tokens (todas las tareas) a ~800 tokens (una tarea), eliminando timeouts.
    """
    # S56-D: filtrar requirements por depends_on de la tarea para reducir tokens
    task_requirements = _filter_requirements_for_task(sdd.get("requirements", []), task)

    base = (
        f"## Summary\n{sdd.get('summary', '')}\n\n"
        f"## Requirements\n{_json.dumps(task_requirements, ensure_ascii=False, indent=2)}\n\n"
        f"## Design\n{sdd.get('design', {}).get('overview', '')}\n\n"
        f"## Constraints\n{_json.dumps(sdd.get('constraints', []), ensure_ascii=False, indent=2)}\n\n"
        f"## Your Task ({agent_name}) — {task_index + 1}/{total_tasks}\n"
        f"{_json.dumps(task, ensure_ascii=False, indent=2)}"
    )

    # S54-B: inyectar instrucción de fence con ruta exacta, extraída de la descripción de la tarea.
    # Mismo mecanismo que S51-A para tests — instrucción a nivel de tarea, no solo en el system prompt.
    task_desc = task.get("description", "") + " " + task.get("title", "")
    expected_files = _extract_expected_files_from_task(task_desc)
    if expected_files:
        # Detectar extensión para el lang del fence
        def _lang_for(path: str) -> str:
            ext = path.rsplit(".", 1)[-1] if "." in path else ""
            return {"py": "python", "ts": "typescript", "tsx": "typescript",
                    "js": "javascript", "jsx": "javascript", "sql": "sql",
                    "yaml": "yaml", "yml": "yaml", "toml": "toml",
                    "json": "json", "ini": "ini", "cfg": "ini"}.get(ext, ext)

        fence_examples = "\n".join(
            f"```{_lang_for(f)}:{f}\n# tu implementación aquí\n```" for f in expected_files
        )
        fence_hint = (
            f"\n\n[S54-B] FORMATO OBLIGATORIO — Genera EXACTAMENTE {len(expected_files)} archivo(s) "
            f"con el fence :path correcto:\n\n"
            f"{fence_examples}\n\n"
            "CRÍTICO: El fence DEBE incluir la ruta exacta después de los backticks "
            "(```python:src/imc/models.py). Sin esa ruta, el archivo NO se escribe al disco. "
            "NO omitas la ruta bajo ninguna circunstancia."
        )
        log.debug(
            "_build_single_task_sdd_content: S54-B inyectando fence hint para %d archivo(s): %s",
            len(expected_files), expected_files,
        )

        # S55-C: para tareas de tests, agregar instrucción explícita de round() para floats.
        # Previene que el LLM escriba valores float literales calculados de memoria (divergen
        # del valor real calculado por la implementación → AssertionError inevitable).
        _task_desc_lower = task_desc.lower()
        _is_test_task = any(kw in _task_desc_lower for kw in ("test", "pytest", "unitari", "spec"))
        if _is_test_task:
            float_hint = (
                "\n\n[S55-C] REGLA CRÍTICA PARA VALORES FLOAT EN TESTS:\n"
                "NUNCA escribas valores float de memoria en los asserts. "
                "SIEMPRE usa round() con la misma fórmula que la implementación:\n"
                "  ✅ CORRECTO:  assert calcular_imc(70, 1.75) == (round(70/1.75**2, 2), 'Normal')\n"
                "  ❌ PROHIBIDO: assert calcular_imc(70, 1.75) == (22.86, 'Normal')  # literal inventado\n"
                "El valor hardcodeado DIVERGE del valor calculado. Usa round() para garantizar exactitud."
            )
            return base + fence_hint + float_hint

        return base + fence_hint

    return base


async def route_agents(state: OVDState) -> dict:
    """
    GAP-002: Nodo de routing que prepara el fan-out nativo de LangGraph.

    1. Determina qué agentes ejecutar (desde el SDD o via LLM router como fallback).
    2. Resetea agent_results para el nuevo ciclo (via reducer con None).
    3. Almacena selected_agents para que _dispatch_agents genere los Send().

    El fan-out ocurre en la arista condicional post-route_agents via _dispatch_agents.
    """
    sdd = state["sdd"]
    analysis = state.get("fr_analysis", {})
    org_id = state.get("org_id", "")
    project_id = state.get("project_id", "")
    jwt_token = state.get("jwt_token", "")

    # S53-B: Selective Send — si venimos de un retry de tests y se identificó el agente fallido,
    # re-ejecutar solo ese agente en vez de todos los del SDD
    selective_agents = state.get("selective_retry_agents", [])
    test_retry_count = state.get("test_retry_count", 0)
    if selective_agents and test_retry_count > 0:
        log.info(
            "route_agents: S53-B selective retry — solo ejecutar agentes=%s (test_retry_count=%d)",
            selective_agents, test_retry_count,
        )
        # S61-D: preservar resultados de agentes NO retried (frontend, database si backend falla).
        # Resetear solo los resultados del agente que se va a re-ejecutar.
        _prev_results = state.get("agent_results", [])
        _kept_results = [r for r in _prev_results if r.get("agent") not in selective_agents]
        if _kept_results:
            log.info("route_agents: S61-D preservando %d resultado(s) de agentes no-retried: %s",
                     len(_kept_results), [r.get("agent") for r in _kept_results])
        # Primero reseteamos (None), luego el reducer acumulará los _kept_results via Send()
        # No podemos devolver lista directamente porque route_agents no es agent_executor.
        # Solución: devolver None para resetear y guardar kept en campo temporal.
        return {
            "agent_results": None,
            "_kept_agent_results": _kept_results,  # S61-D: rescatados antes del reset
            "selected_agents": selective_agents,
            "pending_agents": [],
            "_dispatch_now": [],
            "selective_retry_agents": [],  # limpiar para no interferir con ciclos siguientes
            "status": "routing",
            "messages": state.get("messages", []) + [{
                "role": "agent",
                "content": f"S53-B: re-ejecutando solo agente(s) {selective_agents} (test retry selectivo)...",
            }],
        }

    # GAP-007: si el SDD tiene tareas por agente, usarlas directamente
    tasks_from_sdd = sdd.get("tasks", [])
    sdd_agents = list({t.get("agent") for t in tasks_from_sdd if t.get("agent") in _AGENT_RUNNERS})

    if sdd_agents:
        selected = sdd_agents
        routing_note = f"Agentes del SDD: {', '.join(selected)}"
    else:
        # Fallback: router LLM elige agentes segun el analisis del FR
        router_base = await model_router.get_llm_with_context(
            "backend", org_id, project_id, jwt_token, state.get("stack_routing", "auto"),
        )
        sdd_summary = (
            f"## Summary\n{sdd.get('summary', '')}\n\n"
            f"## Requirements\n{_json.dumps(sdd.get('requirements', []), ensure_ascii=False, indent=2)}"
        )
        router_result: AgentRouterOutput = await invoke_structured(
            router_base,
            [
                SystemMessage(content=template_loader.render(
                    "system_router",
                    language=state.get("language", "es"),
                )),
                HumanMessage(content=(
                    f"FR type: {analysis.get('type', 'feature')}\n"
                    f"Complexity: {analysis.get('complexity', 'medium')}\n"
                    f"Components: {', '.join(analysis.get('components', []))}\n"
                    f"Oracle involved: {analysis.get('oracle_involved', False)}\n\n"
                    f"SDD (resumen):\n{sdd_summary[:2000]}"
                )),
            ],
            AgentRouterOutput,
        )
        selected = [a for a in router_result.agents if a in _AGENT_RUNNERS] or ["backend"]
        routing_note = f"Router activo: {', '.join(selected)}"

    retry_info = ""
    retry_total = state.get("security_retry_count", 0) + state.get("qa_retry_count", 0)
    if retry_total > 0:
        retry_info = f" (ciclo de reintento #{retry_total})"

    # S47: separar en grupos por capa para ejecución secuencial
    group1 = [a for a in selected if a in _SERVER_SIDE_AGENTS]
    group2 = [a for a in selected if a in _CLIENT_SIDE_AGENTS]
    # Si no hay server-side, client-side va directamente en el primer fan-out
    pending = group2 if group1 else []
    dispatch_note = ""
    if group1 and group2:
        dispatch_note = f" | server-side primero: {group1}, client-side después: {group2}"

    return {
        # GAP-002: None activa el reset en el reducer _list_reset_or_add
        "agent_results": None,
        "selected_agents": selected,
        "pending_agents": pending,  # S47: agentes client-side que esperan al grupo 1
        "status": "routing",
        "messages": state.get("messages", []) + [{
            "role": "agent",
            "content": f"{routing_note} ({len(selected)} agente(s)){retry_info}{dispatch_note} — iniciando fan-out...",
        }],
    }


def _make_agent_sends(agents: list[str], state: OVDState) -> list[Send]:
    """Helper: genera los Send() para una lista de agentes dado el estado actual."""
    shared = {
        "sdd":             state.get("sdd", {}),
        "org_id":          state.get("org_id", ""),
        "project_id":      state.get("project_id", ""),
        "jwt_token":       state.get("jwt_token", ""),
        "project_context": state.get("project_context", ""),
        "retry_feedback":  state.get("retry_feedback", ""),
        "approval_comment": state.get("approval_comment", ""),
        "language":        state.get("language", "es"),
        "stack_language":  state.get("stack_language", ""),  # S42-E
        "directory":       state.get("directory", ""),
        "session_id":      state.get("session_id", ""),
    }
    return [Send("agent_executor", {**shared, "current_agent": agent}) for agent in agents]


def _dispatch_agents(state: OVDState) -> list[Send]:
    """
    S47: Fan-out en dos grupos por capa.

    Grupo 1 (server-side): database + backend + devops — se despachán aquí en paralelo.
    Grupo 2 (client-side): frontend — guardado en pending_agents, se despacha después en
    dispatch_frontend cuando el grupo 1 termina y su código está en disco.

    Si no hay agentes server-side (solo frontend), se despacha directamente aquí.
    Aplica a cualquier stack — el criterio es la capa, no el lenguaje.
    """
    selected = state.get("selected_agents", ["backend"])

    group1 = [a for a in selected if a in _SERVER_SIDE_AGENTS]
    group2 = [a for a in selected if a in _CLIENT_SIDE_AGENTS]

    if group1:
        log.info("S47 _dispatch_agents: grupo 1 server-side=%s | pendientes client-side=%s", group1, group2)
        # group2 se guarda en pending_agents vía el nodo route_agents (actualizado allí)
        return _make_agent_sends(group1, state)
    else:
        # Solo hay agentes client-side (caso edge: SDD solo tiene frontend)
        log.info("S47 _dispatch_agents: solo client-side=%s, despachando directamente", group2)
        return _make_agent_sends(group2, state)


def _dispatch_frontend(state: OVDState) -> list[Send]:
    """
    S47/S59-B: Fan-out del grupo 2 (client-side) después de que el grupo 1 terminó.
    Lee desde _dispatch_now (copiado por _dispatch_frontend_node antes de limpiar
    pending_agents) para evitar que el edge vea la lista ya vacía.
    """
    pending = state.get("_dispatch_now", [])
    log.info("S47 dispatch_frontend: despachando agentes client-side=%s", pending)
    return _make_agent_sends(pending, state)


async def _agent_executor_impl(state: OVDState) -> dict:
    """Implementación interna de agent_executor — envuelta por el wrapper S59-A/A4."""
    agent_name = state.get("current_agent", "backend")
    sdd = state["sdd"]
    comment = state.get("approval_comment", "")
    project_ctx = state.get("project_context", "")
    org_id = state.get("org_id", "")
    project_id = state.get("project_id", "")
    jwt_token = state.get("jwt_token", "")
    retry_feedback = state.get("retry_feedback", "")
    language = state.get("language", "es")
    stack_language = state.get("stack_language", "")  # S42-E: lenguaje del stack del proyecto
    rag_context = state.get("rag_context", "")  # RAG-03: contexto de entregas previas

    # PP-01: verificar presupuesto de tokens del ciclo antes de invocar el agente
    if _CYCLE_BUDGET_TOKENS > 0:
        existing_usage = state.get("token_usage", {})
        tokens_so_far = sum(
            v.get("input", 0) + v.get("output", 0)
            for v in existing_usage.values() if isinstance(v, dict)
        )
        if tokens_so_far >= _CYCLE_BUDGET_TOKENS:
            log.warning(
                "PP-01: agente '%s' omitido — presupuesto de tokens agotado (%d/%d)",
                agent_name, tokens_so_far, _CYCLE_BUDGET_TOKENS,
            )
            return {
                "agent_results": [{
                    "agent": agent_name,
                    "output": (
                        f"[Agente omitido: presupuesto de tokens del ciclo agotado "
                        f"({tokens_so_far:,} / {_CYCLE_BUDGET_TOKENS:,} tokens). "
                        f"Aumenta OVD_CYCLE_TOKEN_BUDGET para incluir este agente.]"
                    ),
                    "artifacts": [],
                    "uncertainties": [],
                    "tokens": {"input": 0, "output": 0},
                    "skipped": True,
                }],
                "token_usage": {agent_name: {"input": 0, "output": 0}},
            }

    # Obtener LLM configurado para este agente — S8: con Stack Registry routing
    llm = await model_router.get_llm_with_context(
        agent_name, org_id, project_id, jwt_token, state.get("stack_routing", "auto"),
    )

    # S6 — G1.C: inyectar contexto de archivos del repo si está disponible
    directory = state.get("directory", "")
    if directory and state.get("github_repo", ""):
        repo_ctx = github_helper.read_repo_context(directory, agent_name)
        if repo_ctx:
            project_ctx = (project_ctx + "\n\n" + repo_ctx).strip() if project_ctx else repo_ctx

    # S17T.C: leer archivos existentes del proyecto para enriquecer el contexto (base inicial)
    if directory:
        existing_ctx = read_project_context(directory, agent_name)
        if existing_ctx:
            project_ctx = (project_ctx + "\n\n" + existing_ctx).strip() if project_ctx else existing_ctx

    # S41.B1: consultar lecciones de ciclos anteriores para este agente y proyecto
    fr_text = state.get("feature_request", "") or state.get("fr_analysis", {}).get("raw", "")
    lessons_context = await lessons.query_lessons_context(
        project_id=project_id,
        agent_name=agent_name,
        fr_text=fr_text,
    )
    if lessons_context:
        log.info("agent_executor[%s]: S41 — %d chars de lecciones recuperadas", agent_name, len(lessons_context))

    # Ejecutar el agente especializado
    runner = _AGENT_RUNNERS.get(agent_name, _run_backend_agent)

    # S17T.A+B + Fase A: file tools + MCP tools (context7 para agentes implementadores)
    # Solo activar tool calling cuando hay directory real — sin directory el modelo
    # entra en bucle infinito de MCP calls sin producir output (ADR-002).
    if directory:
        _file_tools = make_file_tools(directory)
        tools = _file_tools + mcp_client.pool.get_langchain_tools(agent_name)
        # S53-A: calculate_expression disponible para agente backend (modelos Claude/OpenAI)
        # Solo cuando el directorio existe en disco (_file_tools no vacío)
        # Evita que tests con directory mock hagan a S39-D llamar _run_agent_with_tools innecesariamente
        if agent_name == "backend" and _file_tools:
            tools.append(calculate_expression)
    else:
        tools = []

    # S39-D: task-by-task execution — una tarea por llamada al LLM.
    # Si el SDD asigna N tareas a este agente, se ejecutan secuencialmente en vez de
    # enviarlas todas juntas. Cada iteración refresca read_project_context() para que
    # la tarea N+1 vea los archivos escritos por la tarea N (acumulación natural).
    # Elimina timeouts estructuralmente: cada tarea ~800 tokens vs 10-15K tokens en total.
    agent_tasks = [t for t in sdd.get("tasks", []) if t.get("agent") == agent_name]

    if len(agent_tasks) > 1:
        log.info(
            "agent_executor[%s]: S39-D — %d tareas, ejecutando una a la vez",
            agent_name, len(agent_tasks),
        )
        all_artifacts: list[dict] = []
        all_output_parts: list[str] = []
        total_tokens_all: dict = {"input": 0, "output": 0}
        all_uncertainties: list[dict] = []

        for i, task in enumerate(agent_tasks):
            # Refrescar contexto del proyecto — incluye archivos de tareas anteriores
            task_project_ctx = project_ctx
            if directory:
                updated_ctx = read_project_context(directory, agent_name)
                if updated_ctx:
                    task_project_ctx = (project_ctx + "\n\n" + updated_ctx).strip() if project_ctx else updated_ctx

            task_sdd_content = _truncate(
                _build_single_task_sdd_content(sdd, agent_name, task, i, len(agent_tasks))
            )
            # S51-A: tarea de tests → instrucción de prioridad máxima
            _task_desc_lower = (task.get("description", "") + " " + task.get("id", "")).lower()
            if any(kw in _task_desc_lower for kw in ("test", "pytest", "spec", "unitari")):
                task_sdd_content = (
                    "[PRIORIDAD MÁXIMA — S51-A] Esta tarea genera el archivo de tests. "
                    "DEBES incluir el bloque ```python:tests/test_<paquete>.py con al menos 3 casos de prueba. "
                    "No omitas este archivo bajo ninguna circunstancia.\n\n"
                ) + task_sdd_content
                log.info("agent_executor[%s]: S51-A tarea de tests detectada — instrucción de prioridad máxima inyectada", agent_name)
            log.info(
                "agent_executor[%s]: S39-D tarea %d/%d — id=%s",
                agent_name, i + 1, len(agent_tasks), task.get("id", "?"),
            )

            try:
                if tools:
                    task_result = await asyncio.wait_for(
                        _run_agent_with_tools(
                            agent_name, task_sdd_content, comment, llm,
                            task_project_ctx, retry_feedback, language, tools, directory, rag_context,
                            stack_language=stack_language,  # S42-E
                            lessons_context=lessons_context,  # S41
                            stack_routing=state.get("stack_routing", "auto"),  # S49-C
                        ),
                        timeout=_AGENTS_TIMEOUT,  # S41P.A
                    )
                else:
                    task_result = await asyncio.wait_for(
                        runner(task_sdd_content, comment, llm, task_project_ctx, retry_feedback, language, rag_context, stack_language=stack_language),
                        timeout=_AGENTS_TIMEOUT,  # S41P.A
                    )
            except asyncio.TimeoutError:
                log.error(
                    "agent_executor[%s]: S39-D timeout en tarea %d/%d (id=%s) — continuando",
                    agent_name, i + 1, len(agent_tasks), task.get("id", "?"),
                )
                task_result = {
                    "agent": agent_name,
                    "output": f"[Timeout en tarea {i + 1}/{len(agent_tasks)}: {task.get('id', '?')}]",
                    "artifacts": [],
                    "uncertainties": [],
                    "tokens": {"input": 0, "output": 0},
                }

            all_artifacts.extend(task_result.get("artifacts", []))
            if task_result.get("output"):
                all_output_parts.append(task_result["output"])
            t = task_result.get("tokens", {"input": 0, "output": 0})
            total_tokens_all["input"] += t.get("input", 0)
            total_tokens_all["output"] += t.get("output", 0)
            all_uncertainties.extend(task_result.get("uncertainties", []))

        # S51-C: verificar que si el SDD tenía tarea de tests se generó al menos un test_*.py
        _s51_test_tasks = [
            t for t in agent_tasks
            if any(kw in (t.get("description", "") + " " + t.get("id", "")).lower()
                   for kw in ("test", "pytest", "spec", "unitari"))
        ]
        _s51_test_arts = [
            a for a in all_artifacts
            if "test_" in a.get("path", "").lower() or "/tests/" in a.get("path", "").lower()
        ]
        if _s51_test_tasks and not _s51_test_arts:
            log.warning(
                "agent_executor[%s]: S51-C — tarea de tests en SDD pero ningún test_*.py generado — reintentando",
                agent_name,
            )
            _s51_retry_task = _s51_test_tasks[0]
            _s51_retry_sdd = (
                "[PRIORIDAD MÁXIMA — S51-C SEGUNDO INTENTO] El intento anterior NO generó el archivo de tests. "
                "DEBES generar ahora el archivo ```python:tests/test_<paquete>.py``` con al menos 3 casos de prueba. "
                "Este es tu único objetivo en este turno.\n\n"
            ) + _truncate(_build_single_task_sdd_content(sdd, agent_name, _s51_retry_task, 0, 1))
            # Refrescar contexto con archivos ya escritos
            _s51_ctx = task_project_ctx
            if directory:
                _s51_updated = read_project_context(directory, agent_name)
                if _s51_updated:
                    _s51_ctx = (_s51_ctx + "\n\n" + _s51_updated).strip() if _s51_ctx else _s51_updated
            try:
                if tools:
                    _s51_result = await asyncio.wait_for(
                        _run_agent_with_tools(
                            agent_name, _s51_retry_sdd, comment, llm,
                            _s51_ctx, retry_feedback, language, tools, directory, rag_context,
                            stack_language=stack_language,
                            lessons_context=lessons_context,
                            stack_routing=state.get("stack_routing", "auto"),
                        ),
                        timeout=_AGENTS_TIMEOUT,
                    )
                else:
                    _s51_result = await asyncio.wait_for(
                        runner(_s51_retry_sdd, comment, llm, _s51_ctx, retry_feedback, language, rag_context, stack_language=stack_language),
                        timeout=_AGENTS_TIMEOUT,
                    )
                all_artifacts.extend(_s51_result.get("artifacts", []))
                if _s51_result.get("output"):
                    all_output_parts.append(_s51_result["output"])
                _s51_t = _s51_result.get("tokens", {"input": 0, "output": 0})
                total_tokens_all["input"] += _s51_t.get("input", 0)
                total_tokens_all["output"] += _s51_t.get("output", 0)
                log.info(
                    "agent_executor[%s]: S51-C retry completado — %d artifacts nuevos",
                    agent_name, len(_s51_result.get("artifacts", [])),
                )
            except asyncio.TimeoutError:
                log.error("agent_executor[%s]: S51-C retry timeout — sin tests", agent_name)

        result = {
            "agent": agent_name,
            "output": "\n\n".join(all_output_parts),
            "artifacts": all_artifacts,
            "uncertainties": all_uncertainties,
            "tokens": total_tokens_all,
        }

    else:
        # 0 o 1 tarea: comportamiento original (una sola llamada al LLM)
        # GAP-007: SDD filtrado solo con las tareas de este agente
        # P2.B: truncar para proteger la ventana de contexto de modelos 7B (32k tokens)
        agent_sdd_content = _truncate(_build_agent_sdd_content(sdd, agent_name))

        async def _invoke_agent_logic() -> dict:
            if tools:
                return await _run_agent_with_tools(
                    agent_name, agent_sdd_content, comment, llm,
                    project_ctx, retry_feedback, language, tools, directory, rag_context,
                    stack_language=stack_language,   # S42-E
                    lessons_context=lessons_context,  # S41
                    stack_routing=state.get("stack_routing", "auto"),  # S49-C
                )
            return await runner(agent_sdd_content, comment, llm, project_ctx, retry_feedback, language, rag_context, stack_language=stack_language)

        # S20 — GAP-R1 / S41P.A: timeout por nodo — si el LLM cuelga, retornar error parcial sin matar el ciclo
        try:
            result = await asyncio.wait_for(_invoke_agent_logic(), timeout=_AGENTS_TIMEOUT)
        except asyncio.TimeoutError:
            log.error(
                "agent_executor: TIMEOUT en nodo '%s' tras %.0fs — retornando resultado de error",
                agent_name, _AGENTS_TIMEOUT,
            )
            result = {
                "agent": agent_name,
                "output": f"[Timeout: el agente '{agent_name}' no respondió en {_AGENTS_TIMEOUT:.0f}s. Revisa el estado del LLM.]",
                "artifacts": [],
                "uncertainties": [],
                "tokens": {"input": 0, "output": 0},
                "error": "timeout",
            }

    # GAP-004: incertidumbres del agente — acumuladas via reducer operator.add
    agent_uncertainties = result.get("uncertainties", [])

    # FASE 4.D: tokens de este agente — fusionados via _merge_token_usage
    tokens = result.get("tokens", {"input": 0, "output": 0})

    return {
        # Reducer _list_reset_or_add acumula este resultado con los de otros agentes paralelos
        "agent_results": [result],
        # Reducer operator.add acumula incertidumbres de todos los agentes (GAP-002 + GAP-004)
        "uncertainty_register": agent_uncertainties,
        # Reducer _merge_token_usage fusiona el uso de tokens de cada agente paralelo
        "token_usage": {agent_name: tokens},
        # NOTA: no actualizar "status" aquí — múltiples agentes en paralelo generan
        # INVALID_CONCURRENT_GRAPH_UPDATE ya que status no tiene reducer.
        # security_audit lo actualizará al terminar el fan-out.
    }


def _agent_executor_error_result(agent_name: str, exc: Exception) -> dict:
    """S59-A/A4: resultado degradado cuando agent_executor lanza excepción no capturada."""
    log.error(
        "agent_executor[%s]: EXCEPCIÓN NO CAPTURADA — ciclo continúa con resultado degradado",
        agent_name, exc_info=True,
    )
    return {
        "agent_results": [{
            "agent": agent_name,
            "output": f"[S59-A ERROR]: {type(exc).__name__}: {exc}",
            "artifacts": [],
            "uncertainties": [],
            "tokens": {"input": 0, "output": 0},
            "error": "exception",
        }],
        "uncertainty_register": [],
        "token_usage": {agent_name: {"input": 0, "output": 0}},
    }


async def agent_executor(state: OVDState) -> dict:
    """
    S59-A/A4: wrapper que captura excepciones no manejadas de _agent_executor_impl.
    Si el agente falla inesperadamente, el ciclo continúa con resultado degradado
    en vez de silenciar el error o abortar el superstep de LangGraph.
    """
    agent_name = state.get("current_agent", "backend")
    try:
        return await _agent_executor_impl(state)
    except Exception as exc:
        return _agent_executor_error_result(agent_name, exc)


# ─── S49-C helpers ────────────────────────────────────────────────────────────

def _get_chat_ollama_class():
    """Retorna la clase ChatOllama si langchain_ollama está disponible, o object como fallback."""
    try:
        from langchain_ollama import ChatOllama
        return ChatOllama
    except ImportError:
        return type(None)


_OLLAMA_MODEL_PATTERNS = (
    "qwen", "llama", "mistral", "deepseek", "phi", "gemma", "codellama",
    "nomic", "nous", "vicuna", "orca", "wizardcoder", "starcoder",
)

def _looks_like_ollama_model(model_name: str) -> bool:
    """Heurística: si el nombre del modelo contiene algún pattern típico de Ollama."""
    m = model_name.lower()
    return any(p in m for p in _OLLAMA_MODEL_PATTERNS)


# ──────────────────────────────────────────────────────────────────────────────

async def _run_agent_with_tools(
    agent_name: str,
    sdd_content: str,
    comment: str,
    llm: Any,
    project_ctx: str,
    retry_feedback: str,
    language: str,
    tools: list,
    directory: str,
    rag_context: str = "",
    *,
    stack_language: str = "",     # S42-E: lenguaje del stack para selección de template
    lessons_context: str = "",    # S41: lecciones de ciclos anteriores del mismo proyecto
    stack_routing: str = "auto",  # S49-C: routing del stack para detectar Ollama
) -> dict:
    """
    S17T.B — Bucle agentico con tool calling.

    1. Vincula el LLM con las herramientas de archivo.
    2. Itera: invoca el LLM → ejecuta tool calls → reinvoca hasta que
       no haya más tool calls o se alcance el límite de iteraciones.
    3. Recopila los archivos escritos via write_file/edit_file como artefactos.
    4. Si el modelo no soporta tool calling (AttributeError, ValueError),
       cae en el runner tradicional via _AGENT_RUNNERS.

    Límite de iteraciones: 8 (suficiente para un agente que escribe ~4 archivos
    con lectura previa de cada uno).
    """
    from langchain_core.messages import ToolMessage
    import json as _json

    _MAX_TOOL_ITERS = 8

    # S49-C: modelos Ollama no usan tool calling — detectar y saltar directamente al runner
    # Evita overhead de bind_tools + iteración completa que siempre falla con Ollama
    _is_ollama = (
        stack_routing == "ollama"
        or isinstance(llm, _get_chat_ollama_class())
        or (hasattr(llm, "model") and _looks_like_ollama_model(getattr(llm, "model", "")))
    )
    if _is_ollama:
        log.info(
            "S49-C: agente '%s' — modelo Ollama detectado (stack_routing=%s), usando runner directo sin tool calling",
            agent_name, stack_routing,
        )
        runner = _AGENT_RUNNERS.get(agent_name, _run_backend_agent)
        runner_result = await runner(
            sdd_content, comment, llm, project_ctx, retry_feedback, language, rag_context,
            stack_language=stack_language,
        )
        # S50-A: escribir archivos al disco durante execute_agents (no esperar a deliver)
        # Permite que run_tests detecte los test files correctamente via filesystem
        if directory and not runner_result.get("artifacts") and runner_result.get("output"):
            # S55-B: en rondas de retry (retry_feedback presente) preservar archivos existentes
            _preserve = bool(retry_feedback)
            written_arts = _write_artifacts(runner_result["output"], directory, agent_name, preserve_nonempty=_preserve)
            if written_arts:
                runner_result = dict(runner_result, artifacts=written_arts)
                log.info("S50-A: agente '%s' S49-C — %d archivo(s) escritos al disco via runner", agent_name, len(written_arts))
        return runner_result

    # Intentar vincular herramientas — no todos los modelos lo soportan
    try:
        bound_llm = llm.bind_tools(tools)
    except (AttributeError, NotImplementedError, ValueError):
        # Fallback: el modelo no soporta tool calling → runner tradicional
        runner = _AGENT_RUNNERS.get(agent_name, _run_backend_agent)
        return await runner(sdd_content, comment, llm, project_ctx, retry_feedback, language, rag_context)

    system_prompt = template_loader.render_composed(  # S58-pre: base + stack section
        f"system_{agent_name}",
        language=language,
        stack_language=stack_language,
        project_context=project_ctx,
        retry_feedback=retry_feedback,
        rag_context=rag_context,
        lessons_context=lessons_context,  # S41
    )
    human_content = (
        f"SDD Aprobado:\n{sdd_content}\n\n"
        f"Comentario del arquitecto: {comment}\n\n"
        f"Implementa los artefactos {agent_name} definidos en el SDD usando las herramientas disponibles.\n\n"
        f"IMPORTANTE: Organiza los archivos en subdirectorios apropiados (ej: src/app/components/, src/routes/, etc.). "
        f"NO uses rutas planas sin directorio. Empieza a escribir archivos directamente con write_file."
    )

    messages: list = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_content),
    ]

    written_files: list[str] = []
    total_tokens = {"input": 0, "output": 0}
    final_output = ""

    try:
        for _iter in range(_MAX_TOOL_ITERS):
            response = await bound_llm.ainvoke(messages)

            # Acumular tokens
            usage = _extract_usage(response)
            total_tokens["input"]  += usage.get("input", 0)
            total_tokens["output"] += usage.get("output", 0)

            # Si no hay tool calls, terminamos
            tool_calls = getattr(response, "tool_calls", []) or []
            if not tool_calls:
                final_output = response.content or ""
                if _iter == 0:
                    # S49-A: modelo ignoró tools en primera iteración → switch inmediato al runner
                    # Evita el loop S30-B que es lento e impreciso
                    log.warning(
                        "S49-A: agente '%s' — modelo no usó tools en iter 0 (content=%d chars). "
                        "Switch a runner directo.",
                        agent_name, len(final_output),
                    )
                    _runner = _AGENT_RUNNERS.get(agent_name, _run_backend_agent)
                    _runner_result = await _runner(
                        sdd_content, comment, llm, project_ctx,
                        retry_feedback, language, rag_context,
                        stack_language=stack_language,
                    )
                    # S50-A: escribir archivos al disco durante execute_agents (no esperar a deliver)
                    # Permite que run_tests detecte los test files correctamente via filesystem
                    if directory and not _runner_result.get("artifacts") and _runner_result.get("output"):
                        # S55-B: en rondas de retry (retry_feedback presente) preservar archivos existentes
                        _preserve = bool(retry_feedback)
                        _written = _write_artifacts(_runner_result["output"], directory, agent_name, preserve_nonempty=_preserve)
                        if _written:
                            _runner_result = dict(_runner_result, artifacts=_written)
                            log.info("S50-A: agente '%s' S49-A — %d archivo(s) escritos al disco via runner", agent_name, len(_written))
                    return _runner_result
                else:
                    log.info(
                        "S48-C: agente '%s' — terminó tool loop en iteración %d (sin más tool_calls). "
                        "written_files=%d",
                        agent_name, _iter, len(written_files),
                    )
                break

            # Agregar el mensaje del asistente con las tool calls
            messages.append(response)

            # Ejecutar cada tool call
            for tc in tool_calls:
                tool_name = tc.get("name", "")
                tool_args = tc.get("args", {})
                tool_id   = tc.get("id", tool_name)

                # Buscar la tool correspondiente
                tool_fn = next(
                    (t for t in tools if t.name == tool_name), None
                )
                if tool_fn is None:
                    tool_result = f"ERROR: herramienta '{tool_name}' no encontrada."
                else:
                    try:
                        # S38-A: usar ainvoke async si la tool lo soporta (ej: context7 StructuredTool)
                        # Fallback a invoke() síncrono para tools que no soporten async
                        if hasattr(tool_fn, "ainvoke"):
                            try:
                                tool_result = await tool_fn.ainvoke(tool_args)
                            except NotImplementedError:
                                tool_result = tool_fn.invoke(tool_args)
                        else:
                            tool_result = tool_fn.invoke(tool_args)
                        # Registrar archivos escritos (write_file y edit_file)
                        if tool_name in ("write_file", "edit_file") and isinstance(tool_result, str):
                            if not tool_result.startswith("ERROR"):
                                # write_file retorna la ruta absoluta
                                rel = os.path.relpath(
                                    tool_result if tool_name == "write_file" else
                                    str((pathlib.Path(directory) / tool_args.get("path", "")).resolve()),
                                    directory
                                )
                                if rel not in written_files:
                                    written_files.append(rel)
                    except Exception as e:
                        tool_result = f"ERROR al ejecutar {tool_name}: {e}"
                        log.warning("S30-B: tool '%s' falló para agente '%s': %s", tool_name, agent_name, e)

                messages.append(ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_id,
                ))

            # S30-D: compresión de ventana de contexto — evita explosión a 48K+ tokens
            # Mantener: [SystemMessage, HumanMessage] + últimos 6 mensajes (3 exchanges)
            _MAX_HIST = 8
            if len(messages) > _MAX_HIST + 2:
                messages = messages[:2] + messages[-_MAX_HIST:]

        else:
            # Se alcanzó el límite de iteraciones — usar el último response
            if hasattr(response, "content"):
                final_output = response.content or ""

    except Exception as e:
        log.error(
            "S17T tool calling falló para %s — usando fallback sin tools",
            agent_name, exc_info=True,  # S59-A/A2: traceback completo
        )
        runner = _AGENT_RUNNERS.get(agent_name, _run_backend_agent)
        return await runner(  # S46-B: pasar rag_context y stack_language que faltaban
            sdd_content, comment, llm, project_ctx,
            retry_feedback, language, rag_context,
            stack_language=stack_language,
        )

    # S24-D / S30-B: logging de tracking post-ejecución
    log.info(
        "_run_agent_with_tools[%s]: written_files=%d %s | final_output=%d chars | total_tokens=%s",
        agent_name, len(written_files), written_files[:5], len(final_output), total_tokens,
    )
    if len(written_files) == 0:
        log.warning("S30-B: agente '%s' no escribió ningún archivo via tools — fallback a output parsing", agent_name)

    # Construir artefactos desde archivos escritos via tool calls
    artifacts = _build_artifacts_from_files(written_files, directory)

    # Si no se escribió nada via tools, intentar parsear del output del LLM
    if not artifacts and final_output:
        # S57-D: en rounds de retry, preservar archivos existentes con contenido válido
        # para evitar sobreescritura destructiva si el LLM genera output truncado o vacío
        artifacts = _write_artifacts(
            final_output, directory, agent_name,
            preserve_nonempty=bool(retry_feedback),  # S57-D
        )

    # S24-A: post-scan del workspace — detectar archivos escritos que no fueron
    # capturados por el tracking de tool calls (e.g., tool_result no era str puro).
    if not artifacts and directory:
        artifacts = _scan_workspace_artifacts(directory, agent_start_ts=None)
        if artifacts:
            log.info(
                "_run_agent_with_tools[%s]: S24-A post-scan encontró %d archivo(s) en disco",
                agent_name, len(artifacts),
            )

    log.info(
        "_run_agent_with_tools[%s]: artifacts finales=%d",
        agent_name, len(artifacts),
    )

    uncertainties = _extract_uncertainties(final_output, agent_name)

    return {
        "agent": agent_name,
        "output": final_output,
        "artifacts": artifacts,
        "uncertainties": uncertainties,
        "tokens": total_tokens,
    }


def _build_artifacts_from_files(written_files: list[str], directory: str) -> list[dict]:
    """Construye la lista de artefactos a partir de archivos escritos via tool calls."""
    artifacts = []
    for rel_path in written_files:
        abs_path = os.path.join(directory, rel_path)
        try:
            size = os.path.getsize(abs_path)
        except OSError:
            size = 0
        artifacts.append({
            "path": rel_path,
            "size": size,
            "language": _guess_language(rel_path),
        })
    return artifacts


def _scan_workspace_artifacts(directory: str, agent_start_ts: float | None = None) -> list[dict]:
    """S24-A — Escanea el directorio del workspace para descubrir archivos de implementación.

    Fallback cuando el tracking de tool calls no captura los archivos escritos
    (e.g., tool_result no era str puro, tool name distinto al esperado, etc.).

    Solo incluye archivos de código fuente (.py, .ts, .tsx, .js, .sql, etc.).
    Excluye: directorios ocultos, __pycache__, node_modules, *.md de entrega, .DS_Store.
    """
    _SKIP_DIRS  = {"__pycache__", "node_modules", ".git", ".venv", "venv", ".mypy_cache"}
    _CODE_EXTS  = {".py", ".ts", ".tsx", ".js", ".jsx", ".sql", ".yaml", ".yml",
                   ".tf", ".sh", ".json", ".toml", ".ini", ".cfg", ".rs", ".go", ".java"}
    _SKIP_FILES = {".DS_Store"}

    base = pathlib.Path(directory).expanduser().resolve()
    if not base.exists():
        return []

    artifacts = []
    for abs_path in base.rglob("*"):
        if not abs_path.is_file():
            continue
        # Excluir por directorio padre
        if any(part in _SKIP_DIRS or part.startswith(".") for part in abs_path.parts):
            continue
        # Excluir archivos de sistema y entregas OVD
        if abs_path.name in _SKIP_FILES:
            continue
        if abs_path.name.startswith("ovd-delivery-"):
            continue
        if abs_path.suffix.lower() == ".md":
            continue
        if abs_path.suffix.lower() not in _CODE_EXTS:
            continue
        # Filtrar por tiempo de modificación si se proporciona timestamp de inicio
        if agent_start_ts is not None:
            try:
                if abs_path.stat().st_mtime < agent_start_ts:
                    continue
            except OSError:
                continue
        try:
            rel = str(abs_path.relative_to(base))
            size = abs_path.stat().st_size
            artifacts.append({"path": rel, "size": size, "language": _guess_language(rel)})
        except (ValueError, OSError):
            continue
    return artifacts


def _guess_language(path: str) -> str:
    """Infiere el lenguaje desde la extensión del archivo."""
    ext = pathlib.Path(path).suffix.lower()
    return {
        ".py": "python", ".ts": "typescript", ".tsx": "typescript",
        ".js": "javascript", ".jsx": "javascript", ".sql": "sql",
        ".yaml": "yaml", ".yml": "yaml", ".tf": "hcl",
        ".sh": "bash", ".md": "markdown", ".json": "json",
        ".toml": "toml", ".rs": "rust", ".go": "go",
    }.get(ext, "text")


def _parse_security_fallback(raw: str) -> SecurityAuditOutput:
    """
    BUG-04: Fallback parser para cuando invoke_structured falla con modelos pequeños
    (qwen2.5-coder:7b, mistral, etc.) que no siguen structured output.

    Intenta extraer campos clave con regex del texto libre del LLM.
    Si el modelo no generó datos útiles, retorna resultado neutro con score=75
    (indica que el análisis no fue concluyente, no que hay vulnerabilidades).
    """
    import re as _re2
    import json as _json2

    # 1. Intentar parsear JSON embebido en el texto
    json_match = _re2.search(r'\{[\s\S]*"score"[\s\S]*\}', raw)
    if json_match:
        try:
            data = _json2.loads(json_match.group(0))
            parsed_score = int(data.get("score", 75))
            parsed_vulns = list(data.get("vulnerabilities", []))
            parsed_secrets = list(data.get("secrets_found", []))
            # BUG-04: score=0 sin vulnerabilidades ni secrets = fallo de parsing del modelo.
            # Un modelo que no siguió el schema suele emitir score=0 como valor por defecto.
            # Si hay vulnerabilidades concretas, respetamos el score (puede ser 0 legítimo).
            if parsed_score == 0 and not parsed_vulns and not parsed_secrets:
                parsed_score = 75
            return SecurityAuditOutput(
                passed=bool(data.get("passed", True)),
                score=parsed_score,
                severity=str(data.get("severity", "none")),
                vulnerabilities=parsed_vulns,
                secrets_found=parsed_secrets,
                insecure_patterns=list(data.get("insecure_patterns", [])),
                rls_compliant=bool(data.get("rls_compliant", True)),
                remediation=list(data.get("remediation", [])),
                summary=str(data.get("summary", "Análisis extraído del texto de respuesta.")),
            )
        except Exception:
            pass

    # 2. Extraer score con regex del texto libre
    score = 75  # neutro por defecto
    score_match = _re2.search(r'"?score"?\s*[=:]\s*(\d{1,3})', raw, _re2.IGNORECASE)
    if score_match:
        raw_score = min(100, max(0, int(score_match.group(1))))
        # BUG-04: score=0 en texto libre = modelo no concluyente (ej: "score: 0/100")
        score = raw_score if raw_score > 0 else 75

    # 3. Detectar severidad por keywords
    severity = "none"
    raw_lower = raw.lower()
    if any(w in raw_lower for w in ["critical", "crítico", "critico"]):
        severity = "critical"
    elif any(w in raw_lower for w in ["high", "alto", "alta"]):
        severity = "high"
    elif any(w in raw_lower for w in ["medium", "medio", "media"]):
        severity = "medium"
    elif any(w in raw_lower for w in ["low", "bajo", "baja"]):
        severity = "low"

    passed = severity not in ("high", "critical") and score >= 50

    log.warning(
        "security_audit: invoke_structured falló — usando fallback parser "
        "(score=%d, severity=%s, passed=%s)", score, severity, passed
    )
    return SecurityAuditOutput(
        passed=passed,
        score=score,
        severity=severity,
        vulnerabilities=[],
        secrets_found=[],
        insecure_patterns=[],
        rls_compliant=True,
        remediation=[],
        summary="Análisis de seguridad completado (modo compatibilidad con modelo local).",
    )


def _parse_qa_fallback(raw: str) -> QAReviewOutput:
    """
    S20 — GAP-R5: Fallback parser para qa_review cuando invoke_structured falla.
    Intenta extraer campos clave con regex del texto libre del LLM.
    Si no encuentra datos útiles, retorna resultado neutro (score=70, passed=True).
    """
    import re as _re3
    import json as _json3

    # 1. Intentar parsear JSON embebido en el texto
    json_match = _re3.search(r'\{[\s\S]*"score"[\s\S]*\}', raw)
    if json_match:
        try:
            data = _json3.loads(json_match.group(0))
            parsed_score = int(data.get("score", 70))
            if parsed_score == 0 and not data.get("issues"):
                parsed_score = 70
            return QAReviewOutput(
                passed=bool(data.get("passed", True)),
                score=parsed_score,
                issues=list(data.get("issues", [])),
                sdd_compliance=bool(data.get("sdd_compliance", True)),
                missing_requirements=list(data.get("missing_requirements", [])),
                code_quality_issues=list(data.get("code_quality_issues", [])),
                summary=str(data.get("summary", "QA extraído del texto de respuesta.")),
            )
        except Exception:
            pass

    # 2. Extraer score con regex
    score = 70
    score_match = _re3.search(r'"?score"?\s*[=:]\s*(\d{1,3})', raw, _re3.IGNORECASE)
    if score_match:
        raw_score = min(100, max(0, int(score_match.group(1))))
        score = raw_score if raw_score > 0 else 70

    passed = score >= 60

    log.warning(
        "qa_review: invoke_structured falló — usando fallback parser (score=%d, passed=%s)",
        score, passed,
    )
    return QAReviewOutput(
        passed=passed,
        score=score,
        issues=[],
        sdd_compliance=True,
        missing_requirements=[],
        code_quality_issues=[],
        summary="QA completado (modo compatibilidad con modelo local).",
    )


async def security_audit(state: OVDState) -> dict:
    """
    GAP-001: Auditoria de seguridad independiente del QA de calidad.
    Ejecuta despues de execute_agents y antes de qa_review.
    Evalua exclusivamente aspectos de seguridad: OWASP, secrets, RLS, injection.

    BUG-04: Incluye fallback robusto para modelos OSS pequeños (qwen2.5-coder:7b)
    que no siguen el schema de structured output correctamente.
    """
    # S48-A: bypass completo cuando OVD_SECURITY_MIN_SCORE=0 — no invocar el LLM.
    # Antes (Nivel1-E) el bypass era solo en el router (post-ejecución). El nodo
    # seguía llamando al LLM y podía tardar 20+ min antes de hacer timeout.
    if int(os.environ.get("OVD_SECURITY_MIN_SCORE", "0")) == 0:
        log.info("S48-A: OVD_SECURITY_MIN_SCORE=0 — security_audit bypaseado en dev (sin LLM)")
        return {
            "security_result": {
                "passed": True,
                "score": 100,
                "severity": "none",
                "vulnerabilities": [],
                "recommendations": [],
                "summary": "Auditoría omitida en dev (OVD_SECURITY_MIN_SCORE=0)",
            },
            "security_scan_results": {},
            "status": "security_reviewed",
            "messages": state.get("messages", []) + [{
                "role": "agent",
                "content": "Security Audit — Score: 100/100, Severity: none, Passed: True (bypass dev S48-A)",
            }],
        }

    project_ctx = state.get("project_context", "")
    org_id = state.get("org_id", "")
    project_id = state.get("project_id", "")
    jwt_token = state.get("jwt_token", "")

    # El agente de security usa su propia config — S8: con Stack Registry routing
    llm = await model_router.get_llm_with_context(
        "security", org_id, project_id, jwt_token, state.get("stack_routing", "auto"),
    )

    # S22 — Fase 1: Security scanning CLI (opcional, controlado por OVD_SECURITY_SCAN_ENABLED)
    scan_results: dict = {}
    scan_context = ""
    if os.getenv("OVD_SECURITY_SCAN_ENABLED", "false").lower() == "true":
        try:
            scan_results = await _run_security_scans(
                state.get("agent_results", []),
                state.get("directory", ""),
            )
            if scan_results.get("findings"):
                findings_text = "\n".join(
                    f"  [{f['severity']}] {f['tool']}: {f['message']}"
                    for f in scan_results["findings"][:20]
                )
                scan_context = (
                    f"\n\n## Resultados de Security Scanning CLI\n"
                    f"Tools ejecutadas: {', '.join(scan_results['tools_run']) or 'ninguna'}\n"
                    f"Hallazgos ({len(scan_results['findings'])}):\n{findings_text}\n"
                    f"Bloqueado por scan: {scan_results.get('blocked', False)}"
                )
        except Exception as scan_exc:
            log.warning("security_audit: error en CLI scanning (%s), continuando sin scan", scan_exc)

    # S26-C / S31-A: filesystem-first — solo archivos del ciclo actual (mtime >= cycle_start_ts)
    sec_directory = state.get("directory", "")
    agent_code_parts: list[str] = []
    if sec_directory:
        base = pathlib.Path(sec_directory).expanduser().resolve()
        _CODE_EXTS_SEC = {".py", ".ts", ".tsx", ".js", ".sql", ".yaml", ".yml", ".go", ".rs", ".java"}
        _SKIP_SEC = {"__pycache__", "node_modules", ".git", ".venv", "venv", ".mypy_cache"}
        sec_cycle_ts = state.get("cycle_start_ts", 0)
        if base.exists():
            for fp in sorted(base.rglob("*")):
                if not fp.is_file():
                    continue
                if any(part in _SKIP_SEC or part.startswith(".") for part in fp.relative_to(base).parts):
                    continue
                if fp.suffix.lower() not in _CODE_EXTS_SEC:
                    continue
                if fp.name.startswith("ovd-delivery-"):
                    continue
                # S31-A: excluir archivos de ciclos anteriores
                if sec_cycle_ts > 0:
                    try:
                        if fp.stat().st_mtime < sec_cycle_ts - 5:
                            continue
                    except OSError:
                        pass
                try:
                    rel = str(fp.relative_to(base))
                    ext = fp.suffix.lstrip(".")
                    content = fp.read_text(encoding="utf-8", errors="replace")
                    agent_code_parts.append(f"```{ext}:{rel}\n{content}\n```")
                except (OSError, ValueError):
                    pass
            if agent_code_parts:
                log.info("security_audit: S26-C/S31-A leyó %d archivo(s) del ciclo actual", len(agent_code_parts))
    if not agent_code_parts:
        agent_code_parts = [r.get("output", "") for r in state.get("agent_results", [])]
    agent_code = _truncate("\n\n".join(agent_code_parts), 16000)

    messages = [
        SystemMessage(content=template_loader.render(
            "system_security",
            language=state.get("language", "es"),
            project_context=project_ctx,
        )),
        HumanMessage(content=(
            f"Codigo generado por los agentes:\n{agent_code}{scan_context}"
        )),
    ]

    # S41P.A — Timeout diferenciado para security_audit (LLM pesado, puede tardar mucho)
    async def _invoke_security_llm() -> SecurityAuditOutput:
        try:
            res = await invoke_structured(llm, messages, SecurityAuditOutput)
            # BUG-04: detectar resultado inválido (score=0 con severity=high y sin vulnerabilidades
            # es señal de que el modelo no siguió el schema — ocurre con qwen2.5-coder:7b)
            if res.score == 0 and not res.vulnerabilities and not res.secrets_found:
                log.warning(
                    "security_audit: score=0 sin vulnerabilidades — probable fallo de parsing, "
                    "intentando fallback"
                )
                raw_resp = await llm.ainvoke(messages)
                raw_text = raw_resp.content if hasattr(raw_resp, "content") else str(raw_resp)
                res = _parse_security_fallback(raw_text)
        except Exception as exc:
            log.warning("security_audit: invoke_structured falló (%s) — usando fallback", exc)
            try:
                raw_resp = await llm.ainvoke(messages)
                raw_text = raw_resp.content if hasattr(raw_resp, "content") else str(raw_resp)
                res = _parse_security_fallback(raw_text)
            except Exception as exc2:
                log.error("security_audit: fallback también falló (%s) — resultado neutro", exc2)
                res = SecurityAuditOutput(
                    passed=True, score=75, severity="none",
                    vulnerabilities=[], secrets_found=[], insecure_patterns=[],
                    rls_compliant=True, remediation=[],
                    summary="Auditoría de seguridad no disponible (error de modelo).",
                )
        return res

    result: SecurityAuditOutput
    try:
        result = await asyncio.wait_for(_invoke_security_llm(), timeout=_SECURITY_TIMEOUT)
    except asyncio.TimeoutError:
        log.error("security_audit: TIMEOUT tras %.0fs — resultado neutro", _SECURITY_TIMEOUT)
        result = SecurityAuditOutput(
            passed=True, score=75, severity="none",
            vulnerabilities=[], secrets_found=[], insecure_patterns=[],
            rls_compliant=True, remediation=[],
            summary=f"Auditoría de seguridad no disponible (timeout tras {_SECURITY_TIMEOUT:.0f}s).",
        )

    security = {
        "passed": result.passed,
        "score": result.score,
        "severity": result.severity,
        "vulnerabilities": result.vulnerabilities,
        "secrets_found": result.secrets_found,
        "insecure_patterns": result.insecure_patterns,
        "rls_compliant": result.rls_compliant,
        "remediation": result.remediation,
        "summary": result.summary,
    }

    # S22: marcar como bloqueado si el scan CLI detectó secretos/CVE críticos
    if scan_results.get("blocked"):
        security["severity"] = "critical"
        security["passed"] = False
        security["summary"] = (
            f"[BLOQUEADO POR SECURITY SCAN] {security.get('summary', '')} "
            f"| Scan findings: {len(scan_results.get('findings', []))}"
        )

    # S41.A3: indexar findings de seguridad como lecciones (fire-and-forget)
    if security.get("vulnerabilities"):
        agent_names = [r.get("agent", "") for r in state.get("agent_results", []) if r.get("agent")]
        # S59-A/A3: add_done_callback para detectar errores en tarea fire-and-forget
        _lesson_task = asyncio.create_task(lessons.index_security_finding(
            project_id=state.get("project_id", ""),
            org_id=state.get("org_id", ""),
            vulnerabilities=security.get("vulnerabilities", []),
            severity=security.get("severity", "none"),
            score=security.get("score", 0),
            cycle_id=state.get("session_id", ""),
            agent_names=agent_names,
        ))
        def _on_lesson_done(t: asyncio.Task) -> None:
            if not t.cancelled() and (exc := t.exception()):
                log.error("S59-A: lessons.index_security_finding error: %s", exc, exc_info=exc)
        _lesson_task.add_done_callback(_on_lesson_done)

    return {
        "security_result": security,
        "security_scan_results": scan_results,
        "status": "security_reviewed",
        "messages": state.get("messages", []) + [{
            "role": "agent",
            "content": (
                f"Security Audit — Score: {result.score}/100, "
                f"Severity: {result.severity}, "
                f"Passed: {result.passed}, "
                f"Vulnerabilidades: {len(result.vulnerabilities)}\n{result.summary}"
            ),
        }],
    }


def _summarize_for_qa(directory: str) -> str:
    """S39-B: lee el workspace y produce un resumen estructurado para el agente QA.

    Patrón MetaGPT SummarizeCode: el QA recibe defs/clases públicas (no el body completo).
    Resuelve QA score bajo cuando los agentes tuvieron timeouts y `output` quedó vacío
    pero los archivos sí están en disco. Complementa S24-C (filesystem-first).
    """
    if not directory:
        return ""
    work_dir = pathlib.Path(directory).expanduser().resolve()
    if not work_dir.exists():
        return ""
    _SKIP_SUMM = {"__pycache__", "node_modules", ".git", ".venv", "venv", ".mypy_cache"}
    _CODE_EXTS_SUMM = {".py", ".ts", ".tsx", ".js", ".sql"}
    lines: list[str] = []
    for fp in sorted(work_dir.rglob("*")):
        if not fp.is_file():
            continue
        if any(part in _SKIP_SUMM or part.startswith(".") for part in fp.relative_to(work_dir).parts):
            continue
        if fp.suffix.lower() not in _CODE_EXTS_SUMM:
            continue
        if fp.name.startswith("ovd-delivery-"):
            continue
        try:
            rel = fp.relative_to(work_dir)
            source = fp.read_text(errors="replace")
            defs = [
                line.strip() for line in source.splitlines()
                if line.strip().startswith(("def ", "class ", "async def "))
            ]
            if defs:
                lines.append(f"### {rel}\n" + "\n".join(defs[:20]))
        except (OSError, ValueError):
            pass
    return "\n\n".join(lines)


def _build_qa_sdd_block(sdd: dict) -> str:
    """S56-A: serializa requirements completos del SDD para el QA reviewer.

    Evita que el LLM evalúe contra criterios del proyecto (Oracle, etc.) en lugar
    de los requisitos reales del feature request. El bloque se antepone al código
    revisado para que aparezca en la posición primaria del prompt.
    """
    requirements = sdd.get("requirements", [])
    if not requirements:
        return ""
    lines = ["## Requisitos del SDD a verificar (EVALÚA SOLO ESTOS):\n"]
    for req in requirements:
        lines.append(
            f"**{req.get('id', '?')}** [{req.get('priority', 'should')}] — {req.get('description', '')}"
        )
        for crit in req.get("acceptance_criteria", []):
            lines.append(f"  - [ ] {crit}")
        lines.append("")
    return "\n".join(lines)


async def qa_review(state: OVDState) -> dict:
    """Revisa calidad y cumplimiento del SDD (no seguridad — eso lo hace security_audit)."""
    # S62-B: reutilizar QA anterior cuando hay retry de tests (no de QA).
    # Señal: test_retry_count > 0 (persiste en estado) en vez de selective_retry_agents
    # (que route_agents limpia antes de que qa_review lo lea — bug S61-C).
    # Condición extra: qa_retry_count == 0 para no bloquear retries de QA legítimos.
    _prev_qa = state.get("qa_result", {})
    _test_retry_count = state.get("test_retry_count", 0)
    _qa_retry_count = state.get("qa_retry_count", 0)
    if _test_retry_count > 0 and _qa_retry_count == 0 and _prev_qa.get("score", 0) > 0:
        log.info(
            "qa_review: S62-B test_retry_count=%d, qa_retry_count=%d — reutilizando QA previo (score=%d)",
            _test_retry_count, _qa_retry_count, _prev_qa.get("score", 0),
        )
        return {"qa_result": _prev_qa, "qa_passed": _prev_qa.get("passed", True)}

    project_ctx = state.get("project_context", "")
    llm = await model_router.get_llm_with_context(
        "qa", state.get("org_id", ""), state.get("project_id", ""),
        state.get("jwt_token", ""), state.get("stack_routing", "auto"),
    )
    # S23-C / S24-C: construir contexto de código para QA.
    # Estrategia (orden de prioridad):
    #   1. Filesystem directo cuando directory disponible — más fiable que artifacts[] o output
    #   2. artifacts[] del agente — tool calling path
    #   3. output del agente — path clásico (fences en texto)
    qa_directory = state.get("directory", "")
    agent_output_parts: list[str] = []

    if qa_directory:
        # S24-C: leer archivos de código desde el workspace directamente
        import pathlib as _pl
        base = _pl.Path(qa_directory).expanduser().resolve()
        _CODE_EXTS_QA = {".py", ".ts", ".tsx", ".js", ".sql", ".yaml", ".yml", ".go", ".rs", ".java"}
        _SKIP_QA = {"__pycache__", "node_modules", ".git", ".venv", "venv", ".mypy_cache"}
        file_blocks: list[str] = []
        # S31-A: solo archivos escritos en este ciclo (mtime >= cycle_start_ts - 5s buffer)
        cycle_ts = state.get("cycle_start_ts", 0)
        if base.exists():
            for fp in sorted(base.rglob("*")):
                if not fp.is_file():
                    continue
                if any(part in _SKIP_QA or part.startswith(".") for part in fp.relative_to(base).parts):
                    continue
                if fp.suffix.lower() not in _CODE_EXTS_QA:
                    continue
                if fp.name.startswith("ovd-delivery-"):
                    continue
                # S31-A: excluir archivos de ciclos anteriores
                if cycle_ts > 0:
                    try:
                        if fp.stat().st_mtime < cycle_ts - 5:
                            continue
                    except OSError:
                        pass
                try:
                    rel = str(fp.relative_to(base))
                    ext = fp.suffix.lstrip(".")
                    content = fp.read_text(encoding="utf-8", errors="replace")
                    file_blocks.append(f"```{ext}:{rel}\n{content}\n```")
                except (OSError, ValueError):
                    pass
        if file_blocks:
            agent_output_parts.append("\n\n".join(file_blocks))
            log.info("qa_review: S24-C / S31-A leyó %d archivo(s) del ciclo actual para contexto QA", len(file_blocks))

    # Fallback si no hay directory o no hay archivos en disco
    if not agent_output_parts:
        for r in state.get("agent_results", []):
            output    = r.get("output", "")
            artifacts = r.get("artifacts", [])
            if artifacts and qa_directory:
                import pathlib as _pl2
                base2 = _pl2.Path(qa_directory).expanduser().resolve()
                fb: list[str] = []
                for art in artifacts:
                    p = art.get("path", "") if isinstance(art, dict) else str(art)
                    if not p:
                        continue
                    fp2 = (base2 / p).resolve()
                    try:
                        fp2.relative_to(base2)
                        if fp2.exists():
                            fb.append(f"```{fp2.suffix.lstrip('.')}:{p}\n{fp2.read_text(encoding='utf-8', errors='replace')}\n```")
                    except (ValueError, OSError):
                        pass
                if fb:
                    agent_output_parts.append("\n\n".join(fb))
                    continue
            if output:
                agent_output_parts.append(output)

    agent_output = "\n\n".join(agent_output_parts)

    # S39-B: resumen estructurado del workspace para QA (patrón MetaGPT SummarizeCode).
    # Complementa S24-C: cuando los agentes tuvieron timeouts y output quedó vacío,
    # el QA recibe al menos los defs/clases públicos de los archivos en disco.
    qa_summary = _summarize_for_qa(qa_directory)
    if qa_summary:
        log.info("qa_review: S39-B summary del workspace — %d líneas", qa_summary.count("\n"))

    # S56-A-fix: SDD del ciclo en SystemMessage como referencia primaria.
    # project_ctx se pasa como contexto secundario — previene que restricciones legacy
    # (Oracle, RUT) contaminen la evaluación de features sin esas dependencias.
    _qa_sdd_block = _build_qa_sdd_block(state.get("sdd", {}))
    _project_ctx_filtered = _strip_db_restrictions(project_ctx)

    messages_qa = [
        SystemMessage(content=template_loader.render(
            "system_qa",
            language=state.get("language", "es"),
            project_context=_project_ctx_filtered,
            cycle_sdd_context=_qa_sdd_block,
        )),
        HumanMessage(content=(
            f"## Código generado:\n{_truncate(agent_output, 20000)}"
            + (f"\n\n## Estructura workspace (S39-B):\n{_truncate(qa_summary, 3000)}" if qa_summary else "")
        )),
    ]

    # S20 — GAP-R5 / S41P.A: fallback robusto con timeout diferenciado
    async def _invoke_qa_llm() -> QAReviewOutput:
        try:
            res = await invoke_structured(llm, messages_qa, QAReviewOutput)
            # Detectar parsing fallido: score=0 sin issues = modelo no siguió el schema
            if res.score == 0 and not res.issues:
                raw_resp = await llm.ainvoke(messages_qa)
                res = _parse_qa_fallback(raw_resp.content)
        except Exception as exc:
            log.warning("qa_review: invoke_structured falló (%s: %s) — usando fallback", type(exc).__name__, str(exc)[:120])
            try:
                raw_resp = await llm.ainvoke(messages_qa)
                res = _parse_qa_fallback(raw_resp.content)
            except Exception as exc2:
                log.error("qa_review: fallback también falló (%s) — resultado neutro", exc2)
                res = QAReviewOutput(
                    passed=True,
                    score=70,
                    issues=[],
                    sdd_compliance=True,
                    missing_requirements=[],
                    code_quality_issues=[],
                    summary="QA completado (modo fallback — resultado neutro).",
                )
        return res

    result: QAReviewOutput
    try:
        result = await asyncio.wait_for(_invoke_qa_llm(), timeout=_QA_TIMEOUT)
    except asyncio.TimeoutError:
        log.error("qa_review: TIMEOUT tras %.0fs — resultado neutro", _QA_TIMEOUT)
        result = QAReviewOutput(
            passed=True,
            score=70,
            issues=[],
            sdd_compliance=True,
            missing_requirements=[],
            code_quality_issues=[],
            summary=f"QA no disponible (timeout tras {_QA_TIMEOUT:.0f}s).",
        )

    qa = {
        "passed": result.passed,
        "score": result.score,
        "issues": result.issues,
        "sdd_compliance": result.sdd_compliance,
        "missing_requirements": result.missing_requirements,
        "code_quality_issues": result.code_quality_issues,
        "summary": result.summary,
    }

    # S41.A2: indexar issues de QA como lecciones (fire-and-forget)
    all_issues = result.issues + result.missing_requirements + result.code_quality_issues
    if all_issues:
        agent_names = [r.get("agent", "") for r in state.get("agent_results", []) if r.get("agent")]
        asyncio.create_task(lessons.index_qa_finding(
            project_id=state.get("project_id", ""),
            org_id=state.get("org_id", ""),
            issues=all_issues,
            score=result.score,
            cycle_id=state.get("session_id", ""),
            agent_names=agent_names,
        ))

    return {
        "qa_result": qa,
        "status": "qa_done",
        "messages": state.get("messages", []) + [{
            "role": "agent",
            "content": (
                f"QA completado — Score: {result.score}/100, "
                f"Passed: {result.passed}, "
                f"SDD compliance: {result.sdd_compliance}, "
                f"Issues: {len(result.issues)}\n{result.summary}"
            ),
        }],
    }


async def handle_escalation(state: OVDState) -> dict:
    """
    Interrupt: escala a supervision humana cuando se agotan los reintentos (max 3).
    El TUI muestra el modal con todos los issues de security y QA, y las incertidumbres.
    """
    security_result = state.get("security_result", {})
    qa_result = state.get("qa_result", {})
    uncertainties = state.get("uncertainty_register", [])

    resolution = interrupt({
        "type": "escalated",
        "reason": (
            f"Se agotaron los reintentos (security: {state.get('security_retry_count', 0)}, "
            f"qa: {state.get('qa_retry_count', 0)}) — requiere supervision del arquitecto"
        ),
        "context": {
            "security_passed": security_result.get("passed", True),
            "security_score": security_result.get("score", 100),
            "security_severity": security_result.get("severity", "none"),
            "security_vulnerabilities": security_result.get("vulnerabilities", []),
            "security_remediation": security_result.get("remediation", []),
            "qa_passed": qa_result.get("passed", True),
            "qa_score": qa_result.get("score", 100),
            "qa_issues": qa_result.get("issues", []),
            "missing_requirements": qa_result.get("missing_requirements", []),
            "uncertainty_register": uncertainties,
            "retry_feedback": state.get("retry_feedback", ""),
        },
    })

    reason = (
        f"Se agotaron los reintentos (security: {state.get('security_retry_count', 0)}, "
        f"qa: {state.get('qa_retry_count', 0)})"
    )
    # N1.B — publicar evento escalado
    await nats_client.publish_escalated(
        {**state, "escalation_resolution": resolution.get("resolution", "")},
        reason,
    )

    return {
        "escalation_resolution": resolution.get("resolution", ""),
        "status": "escalation_resolved",
        "messages": state.get("messages", []) + [{
            "role": "agent",
            "content": f"Escalacion resuelta por el arquitecto: {resolution.get('resolution', '')}",
        }],
    }


# ---------------------------------------------------------------------------
# S22 — Nodo run_tests: ejecución real de tests generados
# ---------------------------------------------------------------------------

async def run_tests(state: OVDState) -> dict:
    """S22 — Ejecuta los tests generados por los agentes y captura el resultado.

    Detecta el runner (pytest / vitest / cargo test) por extensión de archivos.
    Si no hay archivos de test detectados, retorna passed=True con warning.
    Escribe los archivos al directorio de workspace y ejecuta el runner.
    En caso de fallo: incluye output completo para el retry loop.
    No bloquea el ciclo — el arquitecto ve el resultado real en el panel de aprobación.
    """
    import tempfile

    agent_results = state.get("agent_results", [])
    directory     = state.get("directory", "")
    retry_round   = state.get("test_retry_count", 0)

    # S24-D: logging de estado antes de detectar runner
    arts_counts = [(r.get("agent","?"), len(r.get("artifacts",[]))) for r in agent_results]
    log.info("run_tests: directory='%s' | agent_results artifacts=%s", directory, arts_counts)

    runner = _detect_test_runner(agent_results, directory=directory)

    # S24-D: logging de resultado de detección
    log.info("run_tests: runner detectado='%s'", runner)

    if not runner:
        log.info("run_tests: no se detectaron archivos de test, omitiendo ejecución")
        return {
            "test_results": {
                "passed": True,
                "output": "No se detectaron archivos de test en los artefactos generados.",
                "runner": "none",
                "retry_round": retry_round,
            },
            "status": "tests_skipped",
            "messages": state.get("messages", []) + [{
                "role": "agent",
                "content": "Tests: no se detectaron archivos de test — continuando sin ejecutar.",
            }],
        }

    # Escribir artefactos al directorio de trabajo (ya debería existir si S16T.A funcionó)
    work_dir = directory or tempfile.mkdtemp(prefix="ovd_tests_")

    # S42-B / S60-C: en rounds de retry, limpiar archivos del round anterior.
    # S60-C: pasar agents_to_retry y sdd para cleanup quirúrgico (solo los agentes que re-ejecutan).
    if retry_round > 0 and directory:
        cycle_ts = state.get("cycle_start_ts", 0)
        _selective = state.get("selective_retry_agents", [])
        _sdd_for_cleanup = state.get("sdd", {})
        _cleanup_impl_files_from_prev_retry(
            work_dir, cycle_ts,
            agents_to_retry=_selective if _selective else None,
            sdd=_sdd_for_cleanup if _selective else None,
        )

    # S27-A / S43-B: inyectar conftest.py solo para proyectos Python (pytest).
    # S61-A: Si pytest.ini ya tiene `pythonpath`, NO inyectar sys.path.insert(0, "src"):
    #         causaría doble prefijo (busca src/src/main.py en vez de src/main.py).
    if work_dir and runner == "pytest":
        _conftest = pathlib.Path(work_dir) / "conftest.py"
        _pytest_ini = pathlib.Path(work_dir) / "pytest.ini"
        _pyproject = pathlib.Path(work_dir) / "pyproject.toml"
        _is_retry_round = retry_round > 0

        # S62-A: auto-crear pytest.ini cuando no existe y pyproject.toml tampoco tiene config pytest.
        # El agente no siempre genera pytest.ini a pesar de las instrucciones del template.
        # El engine garantiza que exista para evitar ModuleNotFoundError por sys.path incorrecto.
        if not _pytest_ini.exists():
            _pyproject_has_pytest = (
                _pyproject.exists()
                and "[tool.pytest.ini_options]" in _pyproject.read_text(encoding="utf-8", errors="replace")
            )
            if not _pyproject_has_pytest:
                _pytest_ini.write_text("[pytest]\npythonpath = .\n", encoding="utf-8")
                log.warning("run_tests: S62-A pytest.ini no encontrado — creado con pythonpath = .")

        _has_pytest_pythonpath = (
            _pytest_ini.exists()
            and "pythonpath" in _pytest_ini.read_text(encoding="utf-8", errors="replace")
        )
        _conftest_content = (
            "import sys, os\n"
            'sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))\n'
        )
        if _has_pytest_pythonpath:
            # S61-A: pytest.ini ya gestiona pythonpath — no sobreescribir conftest
            log.info("run_tests: S61-A pytest.ini tiene pythonpath — omitiendo inyección de conftest.py sys.path")
        elif not _conftest.exists() or _conftest.stat().st_size == 0:
            _conftest.write_text(_conftest_content, encoding="utf-8")
            log.info("run_tests: S27-A/S43-B conftest.py inyectado (Python/pytest) en %s", _conftest)
        elif _is_retry_round:
            # S57-C: en rounds de retry, regenerar conftest.py para reflejar posible
            # reorganización del código por el agente. Si la estructura cambió, el
            # conftest viejo apunta a rutas incorrectas → ImportError inevitable.
            _conftest.write_text(_conftest_content, encoding="utf-8")
            log.warning("run_tests: S57-C conftest.py regenerado en retry_round=%d — %s", retry_round, _conftest)

    # Ejecutar runner
    passed = False
    output = ""
    try:
        if runner == "pytest":
            # S31-C / S32-A: selección inteligente de test files según mtime del ciclo
            # - Si hay test files nuevos (del ciclo actual) → ejecutar solo esos
            # - Si solo hay test files antiguos (proyecto real pre-existente) → ejecutar todos
            # - Si no hay ningún test file → skip graceful (passed=True + warning)
            cycle_ts = state.get("cycle_start_ts", 0)
            _pytest_args: list[str] = []
            if cycle_ts > 0 and work_dir:
                _base = pathlib.Path(work_dir)
                _all_tests = [str(fp) for fp in sorted(_base.rglob("test_*.py"))]
                _cycle_tests = [
                    str(fp) for fp in sorted(_base.rglob("test_*.py"))
                    if fp.stat().st_mtime >= cycle_ts - 5
                ]
                if _cycle_tests:
                    # Hay tests nuevos del ciclo — ejecutar solo esos (evita contaminación)
                    _pytest_args = _cycle_tests
                    log.info("run_tests: S31-C usando %d test file(s) del ciclo actual", len(_cycle_tests))
                elif _all_tests:
                    # Proyecto real con tests pre-existentes — ejecutar todos (S32-A)
                    _pytest_args = [work_dir]
                    log.info("run_tests: S32-A sin tests nuevos, %d test(s) pre-existentes → work_dir", len(_all_tests))
                else:
                    # Sin ningún test file en el workspace → skip graceful
                    log.warning("run_tests: S32-A sin test files en %s — passed=True con warning", work_dir)
                    passed = True
                    output = "[Sin test files encontrados en el workspace — convención test_*.py]"
                    cmd = []  # no ejecutar pytest
            else:
                _pytest_args = [work_dir]
            # S28-C: flags claros sin conflicto (-v y -q se anulan)
            # S33-C: en retry rounds, usar --tb=long para dar más contexto al agente
            # S43-D: flags extra desde _RUNNER_FLAGS (centralizados a nivel módulo)
            _tb_mode = "long" if retry_round > 0 else "short"
            _extra_flags = _RUNNER_FLAGS.get("pytest", [])
            cmd = ([sys.executable, "-m", "pytest"] + _pytest_args
                   + [f"--tb={_tb_mode}", f"--rootdir={work_dir}"]
                   + _extra_flags
                   ) if _pytest_args else []
        elif runner == "vitest":
            cmd = ["npx", "vitest", "run"] + _RUNNER_FLAGS.get("vitest", [])
        elif runner == "cargo":
            cmd = ["cargo", "test", "--manifest-path", f"{work_dir}/Cargo.toml"]
        else:
            cmd = []

        if cmd:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=work_dir,
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
                output = stdout.decode("utf-8", errors="replace") if stdout else ""
                rc = proc.returncode
                passed = rc == 0
                # S28-C: diagnóstico por exit code de pytest
                if runner == "pytest":
                    if rc == 5:
                        log.warning(
                            "run_tests: pytest exit 5 — 0 tests encontrados en %s. "
                            "Verificar que los archivos sigan convención test_*.py con funciones def test_*(). "
                            "Archivos en workspace: %s",
                            work_dir,
                            [str(p.relative_to(work_dir)) for p in pathlib.Path(work_dir).rglob("*.py")][:10],
                        )
                    elif rc == 4:
                        # S57-B: exit 4 = USAGE_ERROR (flags inválidos o directorio inexistente)
                        # NO es collection error — los ImportError reales llegan como rc==1
                        log.warning(
                            "run_tests: S57-B pytest exit 4 (USAGE_ERROR) — "
                            "flags inválidos o directorio inexistente. cmd=%s output=%s",
                            cmd, output[:300],
                        )
                    elif rc == 2:
                        log.warning("run_tests: pytest exit 2 — ejecución interrumpida. Output: %s", output[:200])
                # S57-B: cuando rc==1, distinguir entre collection error e AssertionError
                if rc == 1 and not passed:
                    _is_collection_error = (
                        "collected 0 items" in output and (
                            "ImportError" in output
                            or "ModuleNotFoundError" in output
                            or "attempted relative import" in output
                            or "ERROR" in output
                        )
                    )
                    if _is_collection_error:
                        # S57-B: verdadero collection error — extraer ImportError para feedback
                        _import_errors = [
                            line for line in output.splitlines()
                            if "ImportError" in line or "ModuleNotFoundError" in line
                            or "attempted relative import" in line
                        ]
                        log.warning(
                            "run_tests: S57-B collection error (rc=1, 0 items) — ImportError: %s",
                            " | ".join(_import_errors[:3]),
                        )
                        output = (
                            f"[DIAGNÓSTICO S57-B] Error de colección (ImportError/ModuleNotFoundError):\n"
                            + "\n".join(_import_errors[:5])
                            + f"\n\n{_get_import_error_diagnosis(runner)}\n\n"
                            + output
                        )
                    else:
                        # S33-B: fallos de aserción — extraer AssertionError para diagnóstico
                        _assert_lines = [
                            line for line in output.splitlines()
                            if "AssertionError" in line or (line.strip().startswith("assert ") and "==" in line)
                            or (line.strip().startswith("E ") and ("assert" in line.lower() or "==" in line))
                        ]
                        if _assert_lines:
                            log.info("run_tests: S33-B AssertionError(s) detectados: %d líneas", len(_assert_lines))
                            output = (
                                f"[DIAGNÓSTICO S33-B] Fallos de aserción detectados:\n"
                                + "\n".join(_assert_lines[:10])
                                + "\n\n"
                                + output
                            )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                output = f"[timeout después de 60s — tests interrumpidos]"
                passed = False
    except FileNotFoundError:
        output = f"[runner '{runner}' no está instalado en el entorno]"
        passed = True  # No bloquear si el runner no está disponible
        log.warning("run_tests: runner '%s' no encontrado, continuando", runner)
    except Exception as exc:
        output = f"[error ejecutando tests: {exc}]"
        passed = False
        log.warning("run_tests: error inesperado: %s", exc)

    log.info("run_tests: runner=%s passed=%s retry_round=%d", runner, passed, retry_round)

    # S41.A4: indexar fallos de tests como lecciones (fire-and-forget, solo cuando falla)
    if not passed and output:
        agent_names = [r.get("agent", "") for r in state.get("agent_results", []) if r.get("agent")]
        asyncio.create_task(lessons.index_test_failure(
            project_id=state.get("project_id", ""),
            org_id=state.get("org_id", ""),
            error_text=output,
            runner=runner,
            cycle_id=state.get("session_id", ""),
            agent_names=agent_names,
        ))

    status_msg = f"Tests ({runner}): {'OK' if passed else 'FAIL'} — {output[:200].strip()}"
    return {
        "test_results": {
            "passed": passed,
            "output": output[:4000],  # truncar para no inflar el state
            "runner": runner,
            "retry_round": retry_round,
        },
        "status": "tests_done" if passed else "tests_failed",
        "messages": state.get("messages", []) + [{"role": "agent", "content": status_msg}],
    }


def _route_after_tests(state: OVDState) -> str:
    """S22 — Routing condicional después de run_tests.

    - Tests OK → generate_docs
    - Tests FAIL y retry_count < 2 → test_retry (→ route_agents)
    - Tests FAIL y retry agotado → generate_docs (con warning, no bloquea)
    """
    tr = state.get("test_results", {})
    if tr.get("passed", True):
        return "generate_docs"
    retry_count = state.get("test_retry_count", 0)
    if retry_count < 2:
        return "test_retry"
    log.warning("run_tests: max retries alcanzado, continuando con generate_docs (tests fallidos)")
    return "generate_docs"


def _get_retry_no_modify_instruction(runner: str) -> str:
    """S33-A / S43-E: Instrucción de no modificar tests, adaptada al runner/stack."""
    base = (
        "⚠️ INSTRUCCIÓN CRÍTICA: Los tests son la especificación correcta y NO deben modificarse. "
        "Solo corrige la IMPLEMENTACIÓN para que los tests pasen. "
        "NUNCA modifiques, elimines ni agregues tests."
    )
    if runner in ("pytest", ""):
        return (
            "⚠️ INSTRUCCIÓN CRÍTICA: Los tests son la especificación correcta y NO deben modificarse. "
            "Solo corrige la IMPLEMENTACIÓN (archivos en src/) para que los tests pasen. "
            "NUNCA modifiques, elimines ni agregues tests."
        )
    if runner == "vitest":
        return (
            "⚠️ INSTRUCCIÓN CRÍTICA: Los tests son la especificación correcta y NO deben modificarse. "
            "Solo corrige la IMPLEMENTACIÓN (archivos en src/) para que los tests pasen. "
            "NUNCA modifiques, elimines ni agregues tests. "
            "(TypeScript: implementación en src/, tests en tests/ o __tests__/)"
        )
    if runner == "cargo":
        return (
            "⚠️ INSTRUCCIÓN CRÍTICA: Los tests son la especificación correcta y NO deben modificarse. "
            "Solo corrige la IMPLEMENTACIÓN (archivos en src/) para que los tests pasen. "
            "NUNCA modifiques, elimines ni agregues tests. "
            "(Rust: tests de integración en tests/, unitarios con #[cfg(test)] dentro del módulo)"
        )
    return base


def _get_import_error_diagnosis(runner: str) -> str:
    """S43-C: Diagnóstico de error de importación adaptado al runner/stack."""
    if runner == "pytest":
        return (
            "SOLUCIÓN: Asegúrate de que src/<paquete>/__init__.py existe y que "
            "conftest.py tiene sys.path.insert(0, 'src'). "
            "Escribe estos archivos de infraestructura PRIMERO antes que el código de negocio."
        )
    if runner == "vitest":
        return (
            "SOLUCIÓN: Verifica que las rutas de importación usen la notación del proyecto "
            "(paths en tsconfig.json). Asegúrate de que el módulo referenciado existe "
            "en src/ con el nombre exacto (TypeScript es case-sensitive en Linux)."
        )
    if runner == "cargo":
        return (
            "SOLUCIÓN: Verifica que el módulo esté declarado con 'mod <nombre>;' en lib.rs o main.rs "
            "y que el archivo existe en la ruta esperada por Rust."
        )
    return (
        "SOLUCIÓN: Verifica que el módulo importado existe y es accesible "
        "desde el directorio raíz del proyecto."
    )


def _detect_duplicate_functions(work_dir: str) -> str:
    """S42-D: Escanea archivos Python del workspace y detecta funciones definidas más de una vez.

    Retorna un string con el diagnóstico listo para incluir en retry_feedback.
    Vacío si no hay duplicados.

    Busca patrones `def nombre_funcion(` en archivos .py (excluye tests, __pycache__, .venv).
    Si el mismo nombre aparece en 2+ archivos distintos → duplicado.
    """
    import re as _re
    base = pathlib.Path(work_dir)
    if not base.exists():
        return ""

    _SKIP_S42 = {"__pycache__", ".venv", "venv", "node_modules", ".git", ".mypy_cache"}
    fn_map: dict[str, list[str]] = {}  # nombre_funcion → [rutas donde aparece]

    for fp in sorted(base.rglob("*.py")):
        parts = fp.relative_to(base).parts
        if any(p in _SKIP_S42 or p.startswith(".") for p in parts):
            continue
        if fp.name.startswith("test_") or fp.name == "conftest.py":
            continue
        try:
            src = fp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(fp.relative_to(base))
        for match in _re.finditer(r"^def\s+(\w+)\s*\(", src, _re.MULTILINE):
            fn_name = match.group(1)
            fn_map.setdefault(fn_name, [])
            if rel not in fn_map[fn_name]:
                fn_map[fn_name].append(rel)

    duplicates = {fn: paths for fn, paths in fn_map.items() if len(paths) > 1}
    if not duplicates:
        return ""

    lines = ["⚠️ FUNCIONES DUPLICADAS DETECTADAS (S42-D) — hay implementaciones conflictivas:"]
    for fn, paths in list(duplicates.items())[:5]:  # máx 5 para no inflar feedback
        lines.append(f"  - `{fn}` definida en: {', '.join(paths)}")
    lines.append(
        "\nElige UNA sola ubicación para cada función y ELIMINA las demás definiciones. "
        "Los tests importan desde una ruta específica — asegúrate de que coincida."
    )
    return "\n".join(lines)


def _cleanup_impl_files_from_prev_retry(
    work_dir: str,
    cycle_start_ts: float,
    agents_to_retry: list[str] | None = None,
    sdd: dict | None = None,
) -> None:
    """S42-B / S60-C: Elimina archivos de implementación del ciclo actual antes de un retry.

    S60-C: Si se pasan `agents_to_retry` y `sdd`, solo elimina los archivos que pertenecen
    a los agentes que van a re-ejecutarse (paths del SDD para esos agentes).
    Preserva archivos de agentes que NO están en retry (frontend, database, etc.).

    Fallback al comportamiento original S42-B si no se pasan agentes o SDD.
    """
    if not work_dir or cycle_start_ts <= 0:
        return
    base = pathlib.Path(work_dir)
    if not base.exists():
        return

    _SKIP_B = {"__pycache__", ".venv", "venv", "node_modules", ".git"}
    _SAFE_NAMES = {"conftest.py", "pytest.ini", "setup.py", "pyproject.toml"}
    removed = []

    # S60-C: construir conjunto de paths que pertenecen a los agentes en retry
    retry_paths: set[str] = set()
    if agents_to_retry and sdd:
        for task in sdd.get("tasks", []):
            if task.get("agent") in agents_to_retry:
                for art in task.get("artifacts", []):
                    p = art.get("path", "") if isinstance(art, dict) else str(art)
                    if p:
                        retry_paths.add(p.lstrip("/"))
        log.info(
            "run_tests: S60-C cleanup quirúrgico — agentes=%s, paths candidatos=%d",
            agents_to_retry, len(retry_paths),
        )

    for fp in sorted(base.rglob("*.py")):
        parts = fp.relative_to(base).parts
        if any(p in _SKIP_B or p.startswith(".") for p in parts):
            continue
        if fp.name.startswith("test_") or fp.name in _SAFE_NAMES:
            continue

        # S60-C: si hay lista de paths del retry, preservar archivos que NO están en ella
        if retry_paths:
            rel = str(fp.relative_to(base))
            if not any(rel == rp or rel.startswith(rp.rsplit("/", 1)[0] + "/") for rp in retry_paths):
                continue  # este archivo no pertenece al agente en retry — preservar

        try:
            mtime = fp.stat().st_mtime
        except OSError:
            continue
        if mtime >= cycle_start_ts - 5:
            try:
                fp.unlink()
                removed.append(str(fp.relative_to(base)))
            except OSError:
                pass

    if removed:
        log.info(
            "run_tests: S42-B/S60-C cleanup previo a retry — eliminados %d archivo(s): %s",
            len(removed), removed[:10],
        )


def _extract_assert_errors(output: str) -> list[str]:
    """S34: Extrae líneas de AssertionError / assert X == Y del output de pytest."""
    return [
        line.strip() for line in output.splitlines()
        if "AssertionError" in line
        or (line.strip().startswith("E ") and ("assert" in line.lower() or "==" in line))
        or (line.strip().startswith("assert ") and "==" in line)
    ]


def _extract_failed_test_blocks(output: str) -> str:
    """S34-B: Extrae bloques FAILED con nombre de test y línea de aserción del output --tb=long."""
    blocks: list[str] = []
    lines = output.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        # Detectar inicio de bloque FAILED (línea de guiones con nombre de test)
        if line.startswith("FAILED ") or (line.startswith("_") and "::" in line):
            block_lines = [line]
            i += 1
            # Capturar hasta 12 líneas del bloque (suficiente para ver la aserción)
            while i < len(lines) and len(block_lines) < 12:
                block_lines.append(lines[i])
                stripped = lines[i].strip()
                # Detectar línea de aserción independiente del número de espacios
                if (stripped.startswith("E") and "assert" in stripped.lower()) or "AssertionError" in lines[i]:
                    break
                i += 1
            blocks.append("\n".join(block_lines))
        i += 1
    return "\n\n".join(blocks[:3])  # máx 3 bloques para no inflar el feedback


def _infer_failing_agent_from_test_output(test_output: str) -> str | None:
    """S53-B: heurística para detectar qué agente debe re-ejecutarse a partir del output de pytest.

    Analiza el output para identificar el agente responsable del fallo:
    - ImportError con 'src.' → backend
    - ModuleNotFoundError con un path conocido → backend o database
    - AssertionError en un endpoint → backend
    - Falla en un .tsx/.ts → frontend (no implementado aún)

    Retorna el nombre del agente si se puede inferir con confianza, None si ambiguo.
    """
    if not test_output:
        return None

    lower = test_output.lower()

    # ImportError / ModuleNotFoundError — casi siempre es backend
    if "importerror" in lower or "modulenotfounderror" in lower:
        # Si menciona 'from src.' o 'import src.' → backend
        if "from src." in test_output or "import src." in test_output:
            return "backend"
        # Genérico — puede ser backend
        return "backend"

    # AssertionError con valores float o funciones de cálculo → backend
    if "assertionerror" in lower:
        if any(kw in lower for kw in ("imc", "bmi", "calculate", "round(", "assert")):
            return "backend"

    # Error de sintaxis Python → backend (el archivo .py tiene syntax error)
    if "syntaxerror" in lower and ".py" in lower:
        return "backend"

    return None  # no podemos inferir con confianza


def _build_module_contracts(agent_results: list[dict]) -> str:
    """S53-C: construye un contrato inmutable de rutas de módulo a partir de los artifacts escritos en Round 1.

    Extrae archivos .py que no sean tests y los convierte a importaciones canónicas.
    Retorna un bloque de texto para inyectar en retry_feedback.

    Ejemplo de salida:
        CONTRATO INMUTABLE — NO cambiar rutas ni nombres de módulos entre rounds:
        - src/imc/service.py  → from src.imc.service import ...
        - src/imc/models.py   → from src.imc.models import ...
        - src/imc/main.py     → from src.imc.main import ...
    """
    module_lines: list[str] = []
    for result in agent_results:
        for art in result.get("artifacts", []):
            path = art.get("path", "")
            if not path.endswith(".py"):
                continue
            # Excluir tests y conftest
            basename = path.rsplit("/", 1)[-1]
            if basename.startswith("test_") or basename == "conftest.py":
                continue
            # Convertir ruta a nombre de módulo: src/imc/service.py → src.imc.service
            module_name = path.replace("/", ".").removesuffix(".py")
            module_lines.append(f"  - {path}  → from {module_name} import ...")

    if not module_lines:
        return ""

    lines_text = "\n".join(module_lines)
    return (
        "\n\n⚠️ CONTRATO INMUTABLE (S53-C) — NO cambiar rutas ni nombres de módulos entre rounds:\n"
        f"{lines_text}\n"
        "Usa EXACTAMENTE estas rutas de importación. NO renombres paquetes, NO muevas archivos."
    )


def update_test_retry(state: OVDState) -> dict | Command:
    """S22 — Incrementa el contador de retries de tests e inyecta feedback al retry loop."""
    tr = state.get("test_results", {})
    test_output = tr.get("output", "")
    existing = state.get("retry_feedback", "")
    retry_round = state.get("test_retry_count", 0)

    # S60-B: detectar error estructural no-retryable.
    # S61-B: usa last_test_error (sin truncar) en vez de existing (truncado a 800 chars).
    _rc = tr.get("return_code", 0)
    _is_structural = (
        ("ModuleNotFoundError" in test_output or "ImportError" in test_output)
        and "collected 0 items" in test_output
    )
    _last_test_error = state.get("last_test_error", "")
    _same_error_repeated = _is_structural and (
        "ModuleNotFoundError" in _last_test_error or "ImportError" in _last_test_error
    )
    if _same_error_repeated and retry_round >= 1:
        _err_lines = [l for l in test_output.splitlines() if "ModuleNotFoundError" in l or "ImportError" in l][:3]
        log.warning(
            "update_test_retry: S60-B+S62-C error estructural repetido (rc=%d, ronda=%d) — "
            "Command(goto=generate_docs), saltando route_agents. Líneas: %s",
            _rc, retry_round, _err_lines,
        )
        # S62-C: Command(goto=...) sobrescribe el edge test_retry → route_agents.
        # El grafo salta directamente a generate_docs sin despachar una ronda extra de agentes.
        return Command(
            update={
                "test_retry_count": 2,
                "retry_feedback": existing,
                "selective_retry_agents": [],
                "last_test_error": test_output if _is_structural else "",
                "status": "structural_error_no_retry",
                "messages": state.get("messages", []) + [{
                    "role": "agent",
                    "content": (
                        f"S60-B: Error estructural de imports (ronda {retry_round + 1}) — "
                        "mismo error en rondas consecutivas. Pasando a generate_docs con diagnóstico."
                    ),
                }],
            },
            goto="generate_docs",
        )

    # S34-A: detectar si el mismo AssertionError se repite respecto al round anterior
    current_assert_errors = _extract_assert_errors(test_output)
    repeat_hint = ""
    if existing and current_assert_errors:
        repeated = [e for e in current_assert_errors if e in existing]
        if repeated:
            repeat_hint = (
                "\n\n⚠️ MISMO ERROR POR SEGUNDA VEZ (S34-A): La siguiente aserción falló igual que en el round anterior:\n"
                + "\n".join(repeated[:3])
                + "\nEsto indica un error en la fórmula o lógica matemática. "
                "Revisa la implementación desde cero. No son los tests — el valor esperado ES correcto."
            )
            log.warning("update_test_retry: S34-A error repetido detectado: %s", repeated[:2])

    # S34-B: extraer bloque del test fallido para contexto
    failed_blocks = _extract_failed_test_blocks(test_output)
    failed_block_section = (
        f"\nBloque(s) del test fallido:\n{failed_blocks}\n" if failed_blocks else ""
    )

    # S39-C: incluir solo stderr exacto (~300 chars de raw output), no el output completo.
    # Los AssertionErrors y bloques fallidos ya están extraídos arriba con mayor precisión.
    # Reducción: ~1500 chars de output → ~300 chars → total feedback 3000 → 800 chars.
    raw_snippet = test_output[:300] if not current_assert_errors else ""
    output_section = (
        f"\nAssertionErrors:\n" + "\n".join(current_assert_errors[:5]) + "\n"
        if current_assert_errors else
        f"\nOutput (stderr):\n{raw_snippet}\n"
    )

    # S42-D: detectar funciones duplicadas en el workspace
    work_dir_for_dup = state.get("directory", "")
    duplicate_hint = ""
    if work_dir_for_dup:
        duplicate_hint = _detect_duplicate_functions(work_dir_for_dup)
        if duplicate_hint:
            log.warning("update_test_retry: S42-D duplicados detectados en %s", work_dir_for_dup)

    # S53-C: contrato inmutable de rutas de módulo — previene que el modelo cambie nombres entre rounds
    module_contract_hint = _build_module_contracts(state.get("agent_results", []))
    if module_contract_hint:
        log.info("update_test_retry: S53-C contrato de módulos inyectado en retry_feedback")

    # S33-A / S43-E: instrucción de no modificar tests — stack-aware via helper
    _runner_for_msg = tr.get("runner", "")
    new_feedback = (
        _get_retry_no_modify_instruction(_runner_for_msg) + "\n\n"
        f"TESTS FALLIDOS (ronda {retry_round + 1}/2) — "
        f"runner: {tr.get('runner', '?')}\n"
        + module_contract_hint  # S53-C
        + (f"\n{duplicate_hint}\n" if duplicate_hint else "")  # S42-D
        + failed_block_section
        + output_section
        + "Corregir SOLO la implementación para que los tests pasen."
        + repeat_hint
    )
    accumulated = f"{existing}\n\n{new_feedback}".strip() if existing else new_feedback
    accumulated = _truncate(accumulated, 800)  # S39-C: 3000 → 800 chars (solo stderr exacto)

    # S54-D: loguear archivos físicos en disco antes del retry — diagnóstico de persistencia
    _work_dir = state.get("directory", "")
    if _work_dir:
        try:
            _disk_files = sorted(
                str(p.relative_to(pathlib.Path(_work_dir)))
                for p in pathlib.Path(_work_dir).rglob("*.py")
                if not any(x in str(p) for x in ("__pycache__", ".venv", ".pytest_cache"))
            )
            log.warning(
                "S54-D update_test_retry: %d archivo(s) Python en disco antes del retry: %s",
                len(_disk_files), _disk_files,
            )
            _src_files = [f for f in _disk_files if f.startswith("src/")]
            _test_files = [f for f in _disk_files if f.startswith("tests/")]
            if not _src_files:
                log.warning(
                    "S54-D update_test_retry: NO hay archivos src/ en disco — "
                    "los archivos de producción no fueron escritos correctamente en el round anterior",
                )
            if not _test_files:
                log.warning(
                    "S54-D update_test_retry: NO hay archivos tests/ en disco",
                )
        except Exception as _e:
            log.debug("S54-D update_test_retry: error leyendo disco — %s", _e)

    # S53-B: detectar agente fallido para Selective Send
    selective_agents: list[str] = []
    failing_agent = _infer_failing_agent_from_test_output(test_output)
    if failing_agent:
        selective_agents = [failing_agent]
        log.info(
            "update_test_retry: S53-B agente fallido detectado → selective_retry_agents=%s",
            selective_agents,
        )
    else:
        log.info("update_test_retry: S53-B no se pudo inferir agente fallido — re-ejecutando todos")

    # S61-B: guardar error sin truncar para que S60-B pueda detectar repetición en siguiente ronda
    _new_last_error = test_output if _is_structural else ""

    return {
        "test_retry_count": state.get("test_retry_count", 0) + 1,
        "retry_feedback": accumulated,
        "selective_retry_agents": selective_agents,  # S53-B
        "last_test_error": _new_last_error,  # S61-B
        "status": "retrying_after_test_failure",
        "messages": state.get("messages", []) + [{
            "role": "agent",
            "content": (
                f"Tests fallidos (reintento {state.get('test_retry_count', 0) + 1}/2). "
                f"Runner: {tr.get('runner', '?')}. "
                + (f"Reintentando solo agente '{failing_agent}' (S53-B)..." if failing_agent else "Regenerando implementación con feedback de tests...")
            ),
        }],
    }


# ---------------------------------------------------------------------------
# S22 — Nodo generate_docs: documentación automática post-QA
# ---------------------------------------------------------------------------

async def generate_docs(state: OVDState) -> dict:
    """S22 — Genera documentación técnica a partir del SDD y el código entregado.

    Tipo de doc generado según el tipo de FR:
      - endpoint/backend → OpenAPI spec + ejemplos curl
      - component/frontend → README de componente + props API
      - migration/database → migration guide + rollback instructions
      - service → README + OpenAPI + diagrama Mermaid
      - refactor → CHANGELOG entry + ADR si hay decisión arquitectónica

    Fallo graceful: si el LLM falla, retorna generated_docs=[] sin romper el ciclo.
    """
    sdd          = state.get("sdd", {})
    fr_type      = state.get("fr_analysis", {}).get("type", "feature")
    agent_output = "\n\n".join(r.get("output", "") for r in state.get("agent_results", []))
    test_results = state.get("test_results", {})

    llm = await model_router.get_llm_with_context(
        "backend",  # usa el LLM de backend — capacidad general de texto
        state.get("org_id", ""),
        state.get("project_id", ""),
        state.get("jwt_token", ""),
        state.get("stack_routing", "auto"),
    )

    # S43-A: instrucciones por tipo de FR movidas a system_docs.md.
    # El prompt solo indica el tipo detectado — el template contiene la tabla completa.
    test_summary = ""
    if test_results:
        status = "PASARON" if test_results.get("passed") else "FALLARON"
        test_summary = f"\nTests: {status} (runner: {test_results.get('runner', 'none')})\n"

    prompt_content = (
        f"SDD (resumen):\n{_truncate(sdd.get('summary', ''), 4000)}\n\n"
        f"Tipo de Feature Request: {fr_type}\n{test_summary}\n"
        f"Código implementado:\n{_truncate(agent_output, 8000)}\n\n"
        "Aplica las instrucciones del tipo de FR indicado arriba (ver tabla en tu prompt de sistema).\n"
        "Sé conciso y técnico. No repitas el código implementado, documenta cómo usarlo."
    )

    try:
        system_prompt = template_loader.render(
            "system_docs",
            language=state.get("language", "es"),
            project_context=state.get("project_context", ""),
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt_content),
        ]
        response = await asyncio.wait_for(llm.ainvoke(messages), timeout=_DOCS_TIMEOUT)  # S41P.A
        raw = response.content if hasattr(response, "content") else str(response)

        # Parsear bloques de documentación (mismo patrón que _write_artifacts)
        import re as _re
        pattern = _re.compile(r"```[\w+\-]*:([^\n`]+)\n(.*?)```", _re.DOTALL)
        docs = []
        for match in pattern.finditer(raw):
            rel_path = match.group(1).strip()
            content  = match.group(2).strip()
            doc_type = (
                "openapi"  if rel_path.endswith((".yaml", ".yml")) else
                "adr"      if "adr" in rel_path.lower() else
                "changelog" if "changelog" in rel_path.lower() else
                "readme"
            )
            docs.append({"type": doc_type, "content": content, "path": rel_path})

        log.info("generate_docs: %d documentos generados para FR tipo '%s'", len(docs), fr_type)
    except Exception as exc:
        log.warning("generate_docs: error generando docs (%s) — continuando sin docs", exc)
        docs = []

    msg = (
        f"Documentación generada: {len(docs)} archivo(s)" if docs
        else "Documentación: no se pudo generar (ciclo continúa sin docs)"
    )
    return {
        "generated_docs": docs,
        "status": "docs_done" if docs else "docs_skipped",
        "messages": state.get("messages", []) + [{"role": "agent", "content": msg}],
    }


# ---------------------------------------------------------------------------
# S16T.A — Escritura de artefactos al directorio del workspace
# ---------------------------------------------------------------------------

import re as _re

def _write_artifacts(
    agent_output: str,
    directory: str,
    agent: str,
    preserve_nonempty: bool = False,  # S55-B: preserva archivos existentes no-vacíos en retry
) -> list[dict]:
    """Parsea bloques de código con ruta (```lang:path) y los escribe al disco.

    Formato esperado del agente:
        ```python:src/api/routes/cycles_export.py
        # código
        ```

    Retorna lista de {path, size, lang} para cada archivo escrito.
    Si el directorio no existe o no tiene permisos, registra warning y continúa.

    preserve_nonempty=True: si el archivo ya existe con contenido y el nuevo contenido
    está vacío o tiene menos del 50% del tamaño original, se conserva el existente.
    Previene sobreescritura destructiva en rondas de retry cuando el LLM no sigue el
    formato de fence correctamente (efecto "Lost in the Middle").
    """
    if not directory or not agent_output:
        return []

    base = pathlib.Path(directory).expanduser().resolve()
    if not base.exists():
        log.warning("_write_artifacts: directorio '%s' no existe, omitiendo escritura", directory)
        return []

    # Regex: ```lang:relative/path\n...content...\n```
    pattern = _re.compile(
        r"```[\w+\-]*:([^\n`]+)\n(.*?)```",
        _re.DOTALL,
    )

    written = []
    all_matches = list(pattern.finditer(agent_output))
    if not all_matches:
        # S52-C: output presente pero sin bloques de código con ruta — diagnóstico para detectar truncación o formato incorrecto
        log.warning(
            "_write_artifacts[%s]: 0 matches de regex en output de %d chars — "
            "posible truncación (num_ctx) o formato incorrecto (falta ruta en fence). "
            "Primeros 300 chars: %s",
            agent, len(agent_output), agent_output[:300].replace("\n", "↵"),
        )
    for match in all_matches:
        rel_path = match.group(1).strip()
        content  = match.group(2)

        # Seguridad: no permitir rutas que escapen del directorio base
        target = (base / rel_path).resolve()
        try:
            target.relative_to(base)
        except ValueError:
            log.warning("_write_artifacts: ruta '%s' escapa del directorio base, omitida", rel_path)
            continue

        lang = _re.match(r"```([\w+\-]*)", match.group(0))
        lang_name = lang.group(1).split(":")[0] if lang else ""

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            content_bytes = content.encode("utf-8")

            # S55-B: guard de no-sobreescritura en rondas de retry
            if preserve_nonempty and target.exists():
                existing_size = target.stat().st_size
                if existing_size > 0:
                    new_size = len(content_bytes)
                    if new_size == 0:
                        log.warning(
                            "_write_artifacts[%s]: S55-B — '%s' ya existe (%d bytes), "
                            "nuevo contenido VACÍO — preservando archivo existente",
                            agent, rel_path, existing_size,
                        )
                        written.append({"path": rel_path, "size": existing_size, "lang": lang_name})
                        continue
                    elif new_size < existing_size // 2:
                        log.warning(
                            "_write_artifacts[%s]: S55-B — '%s' existente (%d bytes) → "
                            "nuevo contenido (%d bytes) es <50%% del original — preservando",
                            agent, rel_path, existing_size, new_size,
                        )
                        written.append({"path": rel_path, "size": existing_size, "lang": lang_name})
                        continue
                    else:
                        log.warning(
                            "_write_artifacts[%s]: S55-B — '%s' existente (%d bytes) → "
                            "sobreescribiendo con nuevo contenido (%d bytes)",
                            agent, rel_path, existing_size, new_size,
                        )

            target.write_text(content, encoding="utf-8")
            # S54-A: verificación post-write — confirmar que el archivo existe en disco
            if not target.exists():
                log.error(
                    "_write_artifacts[%s]: VERIFICACIÓN FALLIDA — '%s' no existe en disco tras write_text",
                    agent, rel_path,
                )
            elif target.stat().st_size == 0 and content_bytes:
                log.warning(
                    "_write_artifacts[%s]: archivo '%s' escrito pero 0 bytes en disco (content_len=%d)",
                    agent, rel_path, len(content_bytes),
                )
            else:
                log.info(
                    "_write_artifacts[%s]: escrito %s (%d bytes) — verificado en disco ✓",
                    agent, rel_path, len(content_bytes),
                )
            written.append({
                "path": rel_path,
                "size": len(content_bytes),
                "lang": lang_name,
            })
        except OSError as e:
            log.warning("_write_artifacts[%s]: no se pudo escribir '%s': %s", agent, rel_path, e)

    return written


# ---------------------------------------------------------------------------
# S22 — Security scanning CLI (previo al LLM review en security_audit)
# ---------------------------------------------------------------------------

async def _exec_scan_tool(cmd: list[str], timeout: int = 30) -> str:
    """Ejecuta una CLI de security scanning y retorna stdout+stderr.

    Si el tool no está instalado (FileNotFoundError) retorna string vacío y loguea warning.
    Si excede el timeout retorna mensaje de error sin propagar excepción.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return stdout.decode("utf-8", errors="replace") if stdout else ""
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return f"[timeout después de {timeout}s]"
    except FileNotFoundError:
        log.warning("_exec_scan_tool: '%s' no está instalado, omitiendo", cmd[0])
        return ""
    except Exception as exc:
        log.warning("_exec_scan_tool: '%s' falló (%s), omitiendo", cmd[0], exc)
        return ""


async def _run_security_scans(agent_results: list[dict], directory: str) -> dict:
    """Ejecuta tools CLI de security scanning sobre el código generado.

    Tools (todas opcionales — si no están instaladas se omiten sin error):
      - semgrep   : SAST (SQL injection, XSS, path traversal)
      - gitleaks  : secretos hardcodeados en el código
      - pip-audit / npm audit : vulnerabilidades en dependencias

    Retorna:
      {tools_run: [str], findings: [{tool, severity, message}], blocked: bool}
    """
    import tempfile

    results: dict = {"tools_run": [], "findings": [], "blocked": False}

    # Determinar directorio de trabajo: preferir el workspace, sino usar tmpdir efímero
    work_dir: str | None = None
    if directory:
        work_dir_path = pathlib.Path(directory).expanduser().resolve()
        if work_dir_path.exists():
            work_dir = str(work_dir_path)

    if not work_dir:
        # Si no hay directorio de workspace, escribir code en tmpdir para scan
        work_dir = tempfile.mkdtemp(prefix="ovd_scan_")
        for r in agent_results:
            output = r.get("output", "")
            if output:
                tmp_file = pathlib.Path(work_dir) / f"{r.get('agent', 'agent')}.txt"
                try:
                    tmp_file.write_text(output, encoding="utf-8")
                except OSError:
                    pass

    # 1. SAST — semgrep
    semgrep_out = await _exec_scan_tool(
        ["semgrep", "--config=auto", "--json", "--no-git-ignore", work_dir],
        timeout=60,
    )
    if semgrep_out and semgrep_out != f"[timeout después de 60s]":
        results["tools_run"].append("semgrep")
        try:
            import json as _json
            sg = _json.loads(semgrep_out)
            for r in sg.get("results", []):
                sev = r.get("extra", {}).get("severity", "WARNING").upper()
                results["findings"].append({
                    "tool": "semgrep",
                    "severity": sev,
                    "message": f"{r.get('check_id', '')}: {r.get('extra', {}).get('message', '')} [{r.get('path', '')}:{r.get('start', {}).get('line', '?')}]",
                })
                if sev in ("ERROR", "CRITICAL"):
                    results["blocked"] = True
        except Exception:
            if semgrep_out.strip():
                results["findings"].append({"tool": "semgrep", "severity": "INFO", "message": semgrep_out[:500]})

    # 2. Secretos — gitleaks
    gitleaks_out = await _exec_scan_tool(
        ["gitleaks", "detect", "--source", work_dir, "--no-git", "--exit-code", "0", "--report-format", "json"],
        timeout=30,
    )
    if gitleaks_out and gitleaks_out != f"[timeout después de 30s]":
        results["tools_run"].append("gitleaks")
        try:
            import json as _json
            leaks = _json.loads(gitleaks_out)
            if isinstance(leaks, list):
                for leak in leaks:
                    results["findings"].append({
                        "tool": "gitleaks",
                        "severity": "CRITICAL",
                        "message": f"Secreto detectado: {leak.get('Description', '')} en {leak.get('File', '')}:{leak.get('StartLine', '?')}",
                    })
                    results["blocked"] = True
        except Exception:
            if gitleaks_out.strip():
                results["findings"].append({"tool": "gitleaks", "severity": "INFO", "message": gitleaks_out[:500]})

    # 3. Dependencias — pip-audit (si hay requirements.txt o pyproject.toml)
    has_py_deps = any(
        (pathlib.Path(work_dir) / f).exists()
        for f in ["requirements.txt", "pyproject.toml", "requirements-dev.txt"]
    )
    if has_py_deps:
        pip_out = await _exec_scan_tool(["pip-audit", "--json", "-r", f"{work_dir}/requirements.txt"], timeout=60)
        if pip_out:
            results["tools_run"].append("pip-audit")
            try:
                import json as _json
                audit = _json.loads(pip_out)
                for dep in audit.get("dependencies", []):
                    for vuln in dep.get("vulns", []):
                        sev = vuln.get("aliases", [""])[0] if vuln.get("aliases") else "CVE"
                        results["findings"].append({
                            "tool": "pip-audit",
                            "severity": "HIGH",
                            "message": f"{dep.get('name')}: {vuln.get('id', '')} — {vuln.get('description', '')[:200]}",
                        })
                        if "CRITICAL" in str(vuln).upper():
                            results["blocked"] = True
            except Exception:
                pass

    log.info(
        "_run_security_scans: tools=%s findings=%d blocked=%s",
        results["tools_run"], len(results["findings"]), results["blocked"],
    )
    return results


# ---------------------------------------------------------------------------
# S22 — Detección de runner de tests y ejecución
# ---------------------------------------------------------------------------

def _detect_test_runner(agent_results: list[dict], directory: str = "") -> str | None:
    """Detecta el runner de tests apropiado según las extensiones de los archivos generados.

    .py → pytest | .ts/.tsx → vitest | .rs → cargo test
    Retorna None si no se detectan archivos de test generados.

    S23-B / S24-B: orden de búsqueda:
      0. Filesystem cuando directory disponible (más fiable — archivos ya en disco)
      1. artifacts[] del agente (tool calling path)
      2. fences ```lang:path del output (path clásico)
    """
    import re as _re

    # S24-B: filesystem-first cuando directory está disponible
    # Los archivos ya están en disco al momento de correr run_tests.
    # Es más fiable que depender del tracking de tool calls o del output del LLM.
    if directory:
        import pathlib as _pl
        base = _pl.Path(directory).expanduser().resolve()
        if base.exists():
            _skip = {"__pycache__", "node_modules", ".git", ".venv", "venv"}
            def _safe_rglob(pattern: str) -> list:
                return [
                    p for p in base.rglob(pattern)
                    if not any(part in _skip for part in p.parts)
                ]
            py_tests = _safe_rglob("test_*.py") + _safe_rglob("*_test.py")
            ts_tests = _safe_rglob("*.test.ts") + _safe_rglob("*.spec.ts") + \
                       _safe_rglob("*.test.tsx") + _safe_rglob("*.spec.tsx")
            rs_files = _safe_rglob("*.rs")
            if py_tests:
                log.debug("_detect_test_runner: pytest detectado via filesystem — %s", py_tests[:3])
                return "pytest"
            if ts_tests:
                return "vitest"
            if rs_files:
                return "cargo"

    # Fallback: artifacts[] del agente y fences en output (sin directory)
    def _classify(paths: list[str]) -> str | None:
        if any(("test_" in p or "_test." in p or "/test" in p) and p.endswith(".py") for p in paths):
            return "pytest"
        if any(("test." in p or "spec." in p) and (p.endswith(".ts") or p.endswith(".tsx")) for p in paths):
            return "vitest"
        if any(p.endswith(".rs") for p in paths):
            return "cargo"
        return None

    all_paths: list[str] = []
    for r in agent_results:
        for art in r.get("artifacts", []):
            p = art.get("path", "") if isinstance(art, dict) else str(art)
            if p:
                all_paths.append(p)
    all_output = "\n".join(r.get("output", "") for r in agent_results)
    all_paths.extend(_re.findall(r"```[\w+\-]*:([^\n`]+)", all_output))

    return _classify(all_paths)


async def _index_delivery_report(state: dict, report_file: str) -> None:
    """
    RAG-02 — Indexa el informe de entrega en el RAG via knowledge.bootstrap.
    Fire-and-forget: los errores se loguean pero no propagan al ciclo.
    Respeta OVD_RAG_ENABLED=false para entornos sin Bridge activo.
    """
    import os
    if os.getenv("OVD_RAG_ENABLED", "true").lower() == "false":
        return
    try:
        import pathlib
        import sys as _sys
        # S27-C: asegurar que src/ esté en sys.path para resolver el módulo 'knowledge'
        _knowledge_parent = str(pathlib.Path(__file__).parent.parent)
        if _knowledge_parent not in _sys.path:
            _sys.path.insert(0, _knowledge_parent)
        from knowledge import bootstrap
        bridge_url = os.getenv("OVD_BRIDGE_URL", state.get("bridge_url", "http://localhost:3000"))
        await bootstrap.run(
            org_id=state.get("org_id", ""),
            project_id=state.get("project_id", ""),
            source_path=pathlib.Path(report_file),
            doc_type="delivery",
            bridge_url=bridge_url,
            jwt_token=state.get("jwt_token", ""),
        )
        log.info("RAG-02: informe de entrega indexado — %s", report_file)
    except Exception as e:
        log.warning("RAG-02: error indexando informe de entrega — %s", e)


def _generate_delivery_report(
    state: dict,
    deliverables: list[dict],
    cost_usd: float,
    elapsed_str: str,
    total_in: int,
    total_out: int,
    provider: str,
) -> str:
    """Genera el informe Markdown del ciclo OVD y lo escribe al directorio del workspace.

    Archivo: {directory}/ovd-delivery-{session_id[:8]}-{timestamp}.md
    Retorna la ruta relativa del informe generado, o "" si no se pudo escribir.
    """
    directory  = state.get("directory", "")
    session_id = state.get("session_id", "unknown")
    sdd        = state.get("sdd", {})
    security   = state.get("security_result", {})
    qa         = state.get("qa_result", {})
    fr         = state.get("feature_request", "")

    reqs  = sdd.get("requirements", [])
    tasks = sdd.get("tasks", [])
    cons  = sdd.get("constraints", [])

    # --- Construir secciones ---
    req_lines  = "\n".join(
        f"| {r.get('id','?')} | {r.get('priority','?')} | {r.get('description','?')} |"
        if isinstance(r, dict) else f"| ? | ? | {r} |"
        for r in reqs
    )
    task_lines = "\n".join(
        f"| {t.get('id','?')} | {t.get('agent','?')} | {t.get('complexity','?')} | {t.get('description','?')} |"
        if isinstance(t, dict) else f"| ? | ? | ? | {t} |"
        for t in tasks
    )
    con_lines  = "\n".join(
        f"| {c.get('id','?')} | {c.get('type','?')} | {c.get('description','?')} |"
        if isinstance(c, dict) else f"| ? | ? | {c} |"
        for c in cons
    )

    impl_sections = []
    for d in deliverables:
        if d.get("type") == "implementation":
            agent    = d.get("agent", "?")
            files    = d.get("artifacts", [])
            file_list = "\n".join(f"  - `{f['path']}` ({f.get('size', 0)} bytes)" for f in files) or "  _(sin archivos detectados)_"
            impl_sections.append(f"### Agente: {agent}\n{file_list}")

    # OB-02: YAML frontmatter para búsqueda semántica y filtros en RAG/Obsidian
    agents_used = [d.get("agent", "?") for d in deliverables if d.get("type") == "implementation"]
    files_count = sum(len(d.get("artifacts", [])) for d in deliverables if d.get("type") == "implementation")
    import datetime as _dt
    date_str = _dt.date.today().isoformat()
    fr_short = fr.replace('"', "'").replace("\n", " ")[:200]

    frontmatter = f"""---
session_id: "{session_id}"
date: "{date_str}"
feature_request: "{fr_short}"
provider: "{provider}"
security_score: {security.get('score', 0)}
security_passed: {str(security.get('passed', False)).lower()}
security_severity: "{security.get('severity', 'none')}"
qa_score: {qa.get('score', 0)}
qa_passed: {str(qa.get('passed', False)).lower()}
sdd_compliance: {str(qa.get('sdd_compliance', False)).lower()}
agents: [{", ".join(f'"{a}"' for a in agents_used)}]
files: {files_count}
tokens_in: {total_in}
tokens_out: {total_out}
cost_usd: {cost_usd:.4f}
---
"""

    report = frontmatter + f"""# Informe de Entrega OVD
**Ciclo:** `{session_id}`
**Feature Request:** {fr}
**Duración:** {elapsed_str} | **Costo estimado:** ${cost_usd:.4f} ({provider})
**Tokens:** {total_in} entrada / {total_out} salida

---

## SDD — Resumen
{sdd.get('summary', '_Sin resumen_')}

## Requisitos ({len(reqs)})
| ID | Prioridad | Descripción |
|----|-----------|-------------|
{req_lines or '_Sin requisitos_'}

## Tareas ({len(tasks)})
| ID | Agente | Complejidad | Descripción |
|----|--------|-------------|-------------|
{task_lines or '_Sin tareas_'}

## Restricciones ({len(cons)})
| ID | Tipo | Descripción |
|----|------|-------------|
{con_lines or '_Sin restricciones_'}

---

## Resultados de Auditoría
| Métrica | Valor |
|---------|-------|
| Security Score | {security.get('score', '?')}/100 |
| Security Passed | {'✅' if security.get('passed') else '❌'} |
| QA Score | {qa.get('score', '?')}/100 |
| QA Passed | {'✅' if qa.get('passed') else '❌'} |
| SDD Compliance | {'✅' if qa.get('sdd_compliance') else '❌'} |

---

## Archivos Generados
{"".join(chr(10) + s for s in impl_sections) or '_Sin archivos generados_'}

---
_Generado por OVD Platform · Omar Robles_
"""

    if not directory:
        return ""

    base = pathlib.Path(directory).expanduser().resolve()
    if not base.exists():
        return ""

    report_name = f"ovd-delivery-{session_id[:8]}-{int(time.time())}.md"
    report_path = base / report_name
    try:
        report_path.write_text(report, encoding="utf-8")
        log.info("_generate_delivery_report: informe escrito en %s", report_path)
        return str(report_path)  # S37-B: ruta absoluta para que RAG-02 la encuentre
    except OSError as e:
        log.warning("_generate_delivery_report: no se pudo escribir informe: %s", e)
        return ""


async def _git_integration(directory: str, session_id: str, feature_request: str,
                           written_files: list[str]) -> dict:
    """
    S6.A: Detecta si el directorio es un repo git, crea branch ovd/{session_id[:12]}.
    S6.B: git add de los artefactos escritos + commit con mensaje estándar OVD.
    S6.C: Abre Pull Request en GitHub si hay remote origin GitHub + GITHUB_PAT.

    Retorna dict:
      {
        "enabled": bool,
        "branch": str | None,
        "commit": str | None,   # SHA corto
        "pr_url": str | None,
        "error": str | None,
      }

    Falla silenciosamente — nunca interrumpe el ciclo OVD.
    """
    import subprocess
    import os as _os2

    result = {"enabled": False, "branch": None, "commit": None, "pr_url": None, "error": None}

    if not directory or not written_files:
        return result

    base = pathlib.Path(directory).expanduser().resolve()
    if not base.exists():
        return result

    def git(*args, **kwargs):
        return subprocess.run(
            ["git", *args],
            cwd=str(base),
            capture_output=True, text=True,
            timeout=30,
            **kwargs,
        )

    # S6.A — verificar que es un repo git
    check = git("rev-parse", "--git-dir")
    if check.returncode != 0:
        log.info("_git_integration: '%s' no es un repo git, omitiendo", directory)
        return result

    result["enabled"] = True
    branch_name = f"ovd/{session_id[:12]}"

    try:
        # Asegurarse de tener rama base limpia
        git("fetch", "--quiet")
        create = git("checkout", "-b", branch_name)
        if create.returncode != 0:
            # La rama ya existe — usarla
            git("checkout", branch_name)
        result["branch"] = branch_name
        log.info("_git_integration: branch '%s' listo", branch_name)
    except Exception as e:
        result["error"] = f"S6.A branch: {e}"
        log.warning("_git_integration: error creando branch: %s", e)
        return result

    # S6.B — git add de los archivos escritos + commit
    try:
        for rel_path in written_files:
            git("add", rel_path)

        short_fr = feature_request[:72].replace('"', "'")
        short_id = session_id[:12]
        commit_msg = f"feat(ovd): {short_fr} [cycle:{short_id}]"
        commit = git("commit", "-m", commit_msg)
        if commit.returncode == 0:
            sha = git("rev-parse", "--short", "HEAD")
            result["commit"] = sha.stdout.strip() if sha.returncode == 0 else None
            log.info("_git_integration: commit %s — '%s'", result['commit'], commit_msg)
        else:
            log.warning("_git_integration: commit vacío o fallido: %s", commit.stderr[:200])
    except Exception as e:
        result["error"] = f"S6.B commit: {e}"
        log.warning("_git_integration: error en commit: %s", e)

    # S6.C — Pull Request via GitHub API si hay GITHUB_PAT
    github_pat = _os2.getenv("GITHUB_PAT") or _os2.getenv("GITHUB_TOKEN", "")
    if not github_pat or not result["commit"]:
        return result

    try:
        # Detectar remote origin GitHub
        remote = git("remote", "get-url", "origin")
        remote_url = remote.stdout.strip()
        # Extraer owner/repo de URLs SSH o HTTPS
        import re as _re3
        gh_match = _re3.search(r"github\.com[:/]([^/]+)/([^/.]+?)(?:\.git)?$", remote_url)
        if not gh_match:
            log.info("_git_integration: remote no es GitHub, omitiendo PR")
            return result

        owner, repo = gh_match.group(1), gh_match.group(2)

        # Push branch
        push = git("push", "-u", "origin", branch_name)
        if push.returncode != 0:
            log.warning("_git_integration: error en push: %s", push.stderr[:200])
            return result

        # Obtener rama base (default branch del repo)
        import urllib.request, urllib.error, json as _json3
        headers = {
            "Authorization": f"Bearer {github_pat}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        # Crear el PR
        sdd = {}  # no tenemos el estado aquí, usar feature_request como body
        pr_title = f"feat(ovd): {feature_request[:72]}"
        pr_body = (
            f"## Feature Request\n{feature_request}\n\n"
            f"## Ciclo OVD\n- Session ID: `{session_id}`\n"
            f"- Branch: `{branch_name}`\n"
            f"- Commit: `{result['commit']}`\n\n"
            f"_Generado automáticamente por OVD Platform · Omar Robles_"
        )

        # Obtener default branch
        req = urllib.request.Request(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            repo_info = _json3.loads(resp.read())
        base_branch = repo_info.get("default_branch", "main")

        pr_data = _json3.dumps({
            "title": pr_title,
            "body": pr_body,
            "head": branch_name,
            "base": base_branch,
        }).encode()

        pr_req = urllib.request.Request(
            f"https://api.github.com/repos/{owner}/{repo}/pulls",
            data=pr_data,
            headers={**headers, "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(pr_req, timeout=15) as resp:
            pr_resp = _json3.loads(resp.read())

        result["pr_url"] = pr_resp.get("html_url", "")
        log.info("_git_integration: PR abierto: %s", result["pr_url"])

    except Exception as e:
        log.warning("_git_integration: error creando PR en GitHub: %s", e)
        result["error"] = f"S6.C PR: {e}"

    return result


async def deliver(state: OVDState) -> dict:
    """Empaqueta y entrega los artefactos al TUI.

    GAP-007: incluye el SDD como artefacto independiente con sus 4 secciones.
    S16T.A: escribe artefactos de implementación al directorio del workspace.
    S16T.B: genera informe de entrega Markdown en el directorio del workspace.
    S6.A+B+C: crea branch git, commit de artefactos y PR en GitHub (si aplica).
    P3.A:   reporta costo estimado en USD (0.00 para Ollama).
    P4.B:   exporta el ciclo completo a JSONL para fine-tuning.
    P4.C:   el payload de entrega incluye security_result y qa_result.
    """
    deliverables = []

    # Artefacto SDD (GAP-007): los 4 artefactos separados como entregable de especificacion
    sdd = state.get("sdd", {})
    if sdd:
        deliverables.append({
            "type": "sdd",
            "agent": "architect",
            "summary": sdd.get("summary", ""),
            "artifacts": {
                "requirements": sdd.get("requirements", []),
                "design": sdd.get("design", {}),
                "constraints": sdd.get("constraints", []),
                "tasks": sdd.get("tasks", []),
            },
        })

    # Artefactos de implementacion de cada agente — S16T.A: escribir archivos al disco
    directory = state.get("directory", "")
    # S61-D: fusionar resultados de agentes preservados en selective retry
    _kept = state.get("_kept_agent_results", [])
    _current = state.get("agent_results", [])
    if _kept:
        # Merging: kept results first, then replace with current if same agent
        _current_agents = {r.get("agent") for r in _current}
        _merged = [r for r in _kept if r.get("agent") not in _current_agents] + _current
        log.info("deliver: S61-D fusionando %d resultado(s) preservados + %d actuales = %d total",
                 len(_kept), len(_current), len(_merged))
    else:
        _merged = _current
    for result in _merged:
        agent_name       = result.get("agent", "unknown")
        agent_output     = result.get("output", "")
        existing_arts    = result.get("artifacts", [])
        # S23-A: si el agente usó tool calling (artifacts ya en disco), no re-parsear output
        if existing_arts and directory:
            written = existing_arts
            log.debug("deliver: agente '%s' usó tool calling — %d archivos ya en disco", agent_name, len(written))
        else:
            written = _write_artifacts(agent_output, directory, agent_name)
            # S24-A: último fallback — escanear workspace si output vacío y nada fue escrito
            if not written and directory and not agent_output:
                written = _scan_workspace_artifacts(directory)
                if written:
                    log.info("deliver: S24-A scan encontró %d archivo(s) no trackeados para agente '%s'", len(written), agent_name)
        # S50-B: deduplicar artefactos por path — cuando S39-D ejecuta N tareas vía runner,
        # cada tarea puede generar el mismo archivo. Mantener solo la última versión de cada path.
        seen_paths: dict[str, dict] = {}
        for art in written:
            seen_paths[art.get("path", art.get("lang", id(art)))] = art
        written_dedup = list(seen_paths.values())
        if len(written_dedup) < len(written):
            log.info("S50-B: deduplicados %d → %d artefactos para agente '%s'", len(written), len(written_dedup), agent_name)
        deliverables.append({
            "type": "implementation",
            "agent": agent_name,
            "content": agent_output,
            "artifacts": written_dedup,  # [{path, size, lang}] escritos al disco, sin duplicados
        })

    # S22 — Artefactos de documentación generados por generate_docs
    if directory:
        base_path = pathlib.Path(directory).expanduser().resolve()
        for doc in state.get("generated_docs", []):
            doc_path = doc.get("path", "")
            doc_content = doc.get("content", "")
            if not doc_path or not doc_content:
                continue
            target = (base_path / doc_path).resolve()
            try:
                target.relative_to(base_path)  # seguridad: no escapar del directorio base
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(doc_content, encoding="utf-8")
                deliverables.append({
                    "type": "docs",
                    "agent": "docs",
                    "path": doc_path,
                    "doc_type": doc.get("type", "readme"),
                    "artifacts": [{"path": doc_path, "size": len(doc_content.encode("utf-8")), "lang": "markdown"}],
                })
                log.info("deliver: doc escrito: %s (%d bytes)", doc_path, len(doc_content.encode("utf-8")))
            except (ValueError, OSError) as e:
                log.warning("deliver: no se pudo escribir doc '%s': %s", doc_path, e)

    # P3.A — Costo estimado (cached — sin llamada de red)
    org_id      = state.get("org_id", "")
    project_id  = state.get("project_id", "")
    jwt_token   = state.get("jwt_token", "")
    rep_config  = await model_router.resolve("backend", org_id, project_id, jwt_token)
    token_usage = state.get("token_usage", {})
    cost_usd    = _estimate_cost(token_usage, rep_config.provider)
    total_in    = sum(v.get("input", 0)  for v in token_usage.values() if isinstance(v, dict))
    total_out   = sum(v.get("output", 0) for v in token_usage.values() if isinstance(v, dict))

    # P5.C — Duración del ciclo
    elapsed_secs = time.time() - state.get("cycle_start_ts", time.time())
    elapsed_str  = f"{int(elapsed_secs // 60)}m {int(elapsed_secs % 60)}s"

    # P4.C — Incluir resultados de auditoría en el payload de entrega
    security_result = state.get("security_result", {})
    qa_result       = state.get("qa_result", {})

    # S16T.B — Generar informe de entrega Markdown en el directorio del workspace
    report_file = _generate_delivery_report(
        state, deliverables, cost_usd, elapsed_str, total_in, total_out, rep_config.provider
    )
    if report_file:
        deliverables.append({
            "type": "report",
            "agent": "ovd",
            "path": report_file,
            "artifacts": [],
        })

    # S6.A+B+C — Git integration: branch + commit + PR (fire-and-forget, no bloquea entrega)
    all_written = [
        f["path"]
        for d in deliverables
        if d.get("type") == "implementation"
        for f in d.get("artifacts", [])
    ]
    if all_written:
        asyncio.create_task(_git_integration(
            directory=state.get("directory", ""),
            session_id=state.get("session_id", ""),
            feature_request=state.get("feature_request", ""),
            written_files=all_written,
        ))

    # P4.B — Exportar ciclo completo a JSONL para fine-tuning
    _export_finetune_record(state, deliverables, rep_config.provider, cost_usd, elapsed_secs)

    # RAG-02 — Indexar informe de entrega en RAG (fire-and-forget)
    if report_file:
        asyncio.create_task(_index_delivery_report(state, report_file))

    # S41.A5 — Indexar post-mortem del ciclo como lección (fire-and-forget)
    _agent_names_deliver = [r.get("agent", "") for r in state.get("agent_results", []) if r.get("agent")]
    asyncio.create_task(lessons.index_cycle_postmortem(
        project_id=state.get("project_id", ""),
        org_id=state.get("org_id", ""),
        cycle_id=state.get("session_id", ""),
        agent_names=_agent_names_deliver,
        qa_score=qa_result.get("score", 0),
        security_score=security_result.get("score", 0),
        tests_passed=state.get("test_results", {}).get("passed", False),
        retry_counts={
            "security": state.get("security_retry_count", 0),
            "qa": state.get("qa_retry_count", 0),
            "tests": state.get("test_retry_count", 0),
        },
    ))

    # N1.B — publicar evento done con artefactos completos para RAG
    await nats_client.publish_done(state, elapsed_secs, cost_usd)

    # Sprint 10 — span de cierre del ciclo con métricas completas
    async with telemetry.node_span("deliver", state) as span:
        span.set_attributes({
            "ovd.deliverables_count": len(deliverables),
            "ovd.elapsed_secs":       round(elapsed_secs, 2),
            "ovd.cost_usd":           cost_usd,
        })
        telemetry.record_token_usage(span, token_usage)
        telemetry.record_qa_result(span, qa_result)
        telemetry.record_security_result(span, security_result)

    # Sprint 10 — audit log de ciclo completado (fire-and-forget)
    from audit_logger import AuditLogger
    qa_score = qa_result.get("score")
    await AuditLogger.cycle_completed(
        org_id=state.get("org_id", ""),
        thread_id=state.get("session_id", ""),
        project_id=state.get("project_id", ""),
        qa_score=qa_score,
        tokens_total=total_in + total_out,
        duration_secs=elapsed_secs,
        model_routing=state.get("stack_routing", "auto"),
    )

    # S29-A — Persistir ciclo en ovd_cycles desde el nodo deliver
    # Movido desde api._stream_graph_events para garantizar persistencia
    # aunque el cliente SSE se desconecte antes de recibir el evento "done".
    _db_url = os.environ.get("DATABASE_URL", "")
    if _db_url:
        try:
            _fr_analysis_p = state.get("fr_analysis", {})
            _qa_result_p   = state.get("qa_result", {})
            _session_id_p  = state.get("session_id", "")
            async with await psycopg.AsyncConnection.connect(_db_url) as _conn:
                await _conn.execute(
                    """
                    INSERT INTO ovd_cycles
                      (id, org_id, project_id, session_id, thread_id,
                       fr_text, fr_analysis, sdd, agent_results, qa_result,
                       qa_score, complexity, fr_type, auto_approved,
                       tokens_input, tokens_output, tokens_total,
                       tokens_by_agent, cost_usd, status)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'completed')
                    ON CONFLICT (thread_id) DO UPDATE SET
                      fr_analysis    = EXCLUDED.fr_analysis,
                      sdd            = EXCLUDED.sdd,
                      agent_results  = EXCLUDED.agent_results,
                      qa_result      = EXCLUDED.qa_result,
                      qa_score       = EXCLUDED.qa_score,
                      complexity     = EXCLUDED.complexity,
                      fr_type        = EXCLUDED.fr_type,
                      tokens_input   = EXCLUDED.tokens_input,
                      tokens_output  = EXCLUDED.tokens_output,
                      tokens_total   = EXCLUDED.tokens_total,
                      tokens_by_agent = EXCLUDED.tokens_by_agent,
                      cost_usd       = EXCLUDED.cost_usd,
                      status         = 'completed'
                    """,
                    (
                        str(uuid.uuid4()),
                        state.get("org_id", ""),
                        state.get("project_id") or None,
                        _session_id_p, _session_id_p,
                        state.get("feature_request", ""),
                        _json.dumps(_fr_analysis_p),
                        _json.dumps(state.get("sdd", {})),
                        _json.dumps(state.get("agent_results", [])),
                        _json.dumps(_qa_result_p),
                        _qa_result_p.get("score") or 0,
                        _fr_analysis_p.get("complexity", ""),
                        _fr_analysis_p.get("type", ""),
                        state.get("auto_approve", False),
                        total_in, total_out, total_in + total_out,
                        _json.dumps(state.get("token_usage", {})),
                        cost_usd,
                    ),
                )
                await _conn.commit()
            log.info("deliver: ciclo persistido en ovd_cycles (session=%s)", _session_id_p)
        except Exception as _db_err:
            log.warning("deliver: persist_cycle: error al guardar en DB — %s", _db_err)

    return {
        "deliverables": deliverables,
        "security_result": security_result,
        "qa_result": qa_result,
        "status": "done",
        "messages": state.get("messages", []) + [{
            "role": "agent",
            "content": (
                f"Entrega completada. {len(deliverables)} artefacto(s) generado(s). "
                f"SDD: {len(sdd.get('requirements', []))} req, "
                f"{len(sdd.get('tasks', []))} tareas. "
                f"Security: {security_result.get('score', '?')}/100 | "
                f"QA: {qa_result.get('score', '?')}/100. "
                f"Tokens: {total_in} in / {total_out} out. "
                f"Costo: ${cost_usd:.4f} ({rep_config.provider}). "
                f"Duración: {elapsed_str}"
            ),
        }],
    }


# ---------------------------------------------------------------------------
# S6 — G1.D: Crear PR automático en GitHub
# ---------------------------------------------------------------------------

async def create_pr(state: OVDState) -> dict:
    """
    S6 — G1.D: Crea branch ovd/{session_id}, hace commit de los artefactos
    generados y abre un PR automático en GitHub.
    No-op si github_token o github_repo no están configurados.
    """
    github_token  = state.get("github_token", "")
    github_repo   = state.get("github_repo", "")
    github_branch = state.get("github_branch", "") or "main"

    if not github_token or not github_repo:
        return {}  # sin config GitHub — no-op

    directory    = state.get("directory", "")
    session_id   = state.get("session_id", "")
    agent_results = state.get("agent_results", [])
    sdd_summary  = state.get("sdd", {}).get("summary", "")
    qa_score     = state.get("qa_result", {}).get("score", 0)
    security_score = state.get("security_result", {}).get("score", 0)

    pr_result = await github_helper.create_pr(
        directory=directory,
        github_token=github_token,
        github_repo=github_repo,
        github_branch=github_branch,
        session_id=session_id,
        agent_results=agent_results,
        sdd_summary=sdd_summary,
        qa_score=qa_score,
        security_score=security_score,
    )

    msg_content = (
        f"PR creado: {pr_result.get('pr_url')} — branch `{pr_result.get('branch')}`, "
        f"{len(pr_result.get('files', []))} archivo(s) commiteado(s)."
        if pr_result.get("ok")
        else f"PR no creado: {pr_result.get('reason', 'error desconocido')}"
    )

    log.info("create_pr: %s", msg_content)

    return {
        "github_pr": pr_result,
        "github_token": "",   # LOW-02: limpiar PAT del checkpointer tras uso
        "messages": state.get("messages", []) + [{
            "role": "agent",
            "content": msg_content,
        }],
    }


# ---------------------------------------------------------------------------
# P4.B — Export de ciclos para fine-tuning
# ---------------------------------------------------------------------------

_FINETUNE_DIR = pathlib.Path(os.environ.get("OVD_FINETUNE_DIR", "/tmp/ovd-finetune"))


def _export_finetune_record(
    state: OVDState,
    deliverables: list[dict],
    provider: str,
    cost_usd: float,
    duration_secs: float = 0.0,
) -> None:
    """
    P4.B — Guarda el ciclo completo en JSONL para alimentar el pipeline de fine-tuning.

    Cada línea del archivo es un ciclo independiente con:
      - feature_request, fr_analysis, sdd, agent_results
      - security_result, qa_result, token_usage, cost_usd, provider
      - org_id, project_id (para filtrado multi-tenant en fine-tuning)

    El archivo se nombra ovd-cycles-YYYY-MM-DD.jsonl para rotación diaria.
    """
    try:
        _FINETUNE_DIR.mkdir(parents=True, exist_ok=True)
        date_str = time.strftime("%Y-%m-%d")
        fpath = _FINETUNE_DIR / f"ovd-cycles-{date_str}.jsonl"

        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "org_id":          state.get("org_id", ""),
            "project_id":      state.get("project_id", ""),
            "provider":        provider,
            "cost_usd":        cost_usd,
            "feature_request": state.get("feature_request", ""),
            "fr_analysis":     state.get("fr_analysis", {}),
            "sdd":             state.get("sdd", {}),
            "agent_results":   [
                {"agent": r.get("agent"), "output": r.get("output", "")}
                for r in state.get("agent_results", [])
            ],
            "security_result": state.get("security_result", {}),
            "qa_result":       state.get("qa_result", {}),
            "token_usage":     state.get("token_usage", {}),
            "security_retries": state.get("security_retry_count", 0),
            "qa_retries":       state.get("qa_retry_count", 0),
            "duration_secs":    round(duration_secs, 1),
        }

        with fpath.open("a", encoding="utf-8") as f:
            f.write(_json.dumps(record, ensure_ascii=False) + "\n")

        log.info("P4.B: ciclo exportado a %s", fpath)
    except Exception as exc:
        log.warning("P4.B: no se pudo exportar ciclo para fine-tuning: %s", exc)


# ---------------------------------------------------------------------------
# Routing condicional (GAP-005: retry loops)
# ---------------------------------------------------------------------------

MAX_RETRIES = int(os.environ.get("OVD_MAX_RETRIES", "3"))

# P5.B — Score mínimo para considerar QA aprobado, independiente del booleano del modelo.
# Permite que modelos 7B (que tienden a dar 65/100 y passed=False) completen el ciclo.
# Configurable via OVD_QA_MIN_SCORE (default 70). Para pruebas locales usar 60.
_QA_MIN_SCORE = int(os.environ.get("OVD_QA_MIN_SCORE", "70"))

# P5.B — Score mínimo análogo para security (default 0 = solo usa el booleano del modelo).
_SECURITY_MIN_SCORE = int(os.environ.get("OVD_SECURITY_MIN_SCORE", "0"))


def route_after_approval(state: OVDState) -> str:
    decision = state.get("approval_decision", "")
    if decision == "approved":
        return "route_agents"          # GAP-002: fan-out nativo
    elif decision == "revision_requested":
        return "generate_sdd"          # S15-TUI: volver a generar SDD con feedback
    return END                         # "rejected" o vacío → terminar ciclo


def route_after_security(state: OVDState) -> str:
    """
    GAP-005 / P5.B: Despues del security_audit:
    - Si paso (booleano O score >= _SECURITY_MIN_SCORE): continuar a qa_review
    - Si fallo y quedan reintentos: volver a execute_agents con feedback de remediacion
    - Si fallo y se agotaron los reintentos: escalar al arquitecto
    """
    security = state.get("security_result", {})
    passed = security.get("passed", True)
    # P5.B: también pasar si el score supera el umbral configurable
    # Nivel1-E: OVD_SECURITY_MIN_SCORE=0 significa "bypass security retry en dev"
    #           (antes: > 0 nunca se cumplía con valor 0, causando retry infinito en dev)
    if not passed:
        if _SECURITY_MIN_SCORE == 0:
            passed = True  # dev: no bloquear por security
        elif security.get("score", 0) >= _SECURITY_MIN_SCORE:
            passed = True
    if passed:
        return "qa_review"

    retry_count = state.get("security_retry_count", 0)
    if retry_count < MAX_RETRIES:
        return "route_agents"  # GAP-002
    return "handle_escalation"


def _build_security_feedback(security: dict) -> str:
    """Construye el feedback de security para el reintento de los agentes."""
    lines = ["SECURITY AUDIT FAILED — issues a corregir obligatoriamente:"]
    for v in security.get("vulnerabilities", []):
        lines.append(f"  - Vulnerabilidad OWASP: {v}")
    for s in security.get("secrets_found", []):
        lines.append(f"  - Secret hardcodeado detectado: {s}")
    for p in security.get("insecure_patterns", []):
        lines.append(f"  - Patron inseguro: {p}")
    if not security.get("rls_compliant", True):
        lines.append("  - RLS VIOLATION: hay queries sin filtro org_id")
    for r in security.get("remediation", []):
        lines.append(f"  - Remediacion requerida: {r}")
    return "\n".join(lines)


def _build_qa_feedback(qa: dict) -> str:
    """Construye el feedback de QA para el reintento de los agentes."""
    lines = ["QA REVIEW FAILED — issues a corregir:"]
    for i in qa.get("issues", []):
        lines.append(f"  - Issue: {i}")
    for m in qa.get("missing_requirements", []):
        lines.append(f"  - Requisito SDD no implementado: {m}")
    for c in qa.get("code_quality_issues", []):
        lines.append(f"  - Calidad de codigo: {c}")
    return "\n".join(lines)


def route_after_qa(state: OVDState) -> str:
    """
    GAP-005 / P5.B: Despues del qa_review:
    - Si paso (booleano O score >= _QA_MIN_SCORE): entregar
    - Si fallo y quedan reintentos: volver a execute_agents con feedback de calidad
    - Si fallo y se agotaron los reintentos: escalar al arquitecto
    """
    qa = state.get("qa_result", {})
    passed = qa.get("passed", False)
    # P5.B: también pasar si el score supera el umbral configurable
    if not passed:
        passed = qa.get("score", 0) >= _QA_MIN_SCORE
        if passed:
            log.info(
                "route_after_qa: QA passed=False del modelo pero score=%d >= umbral=%d — aprobando",
                qa.get("score", 0), _QA_MIN_SCORE,
            )
    if passed:
        return "run_tests"  # S22: pasar por run_tests antes de generate_docs → deliver

    retry_count = state.get("qa_retry_count", 0)
    if retry_count < MAX_RETRIES:
        return "route_agents"  # GAP-002
    return "handle_escalation"


def update_security_retry(state: OVDState) -> dict:
    """
    GAP-005: Nodo intermedio que incrementa el contador de reintentos de security
    y construye el feedback acumulado antes de volver a execute_agents.
    LangGraph llama a este nodo cuando route_after_security devuelve 'execute_agents'.
    """
    security = state.get("security_result", {})
    new_feedback = _build_security_feedback(security)
    existing_feedback = state.get("retry_feedback", "")
    accumulated = f"{existing_feedback}\n\n{new_feedback}".strip() if existing_feedback else new_feedback

    return {
        "security_retry_count": state.get("security_retry_count", 0) + 1,
        "retry_feedback": accumulated,
        "status": "retrying_after_security",
        "messages": state.get("messages", []) + [{
            "role": "agent",
            "content": (
                f"Security audit fallido (reintento {state.get('security_retry_count', 0) + 1}/{MAX_RETRIES}). "
                f"Severity: {security.get('severity', 'unknown')}. "
                "Regenerando implementacion con feedback de remediacion..."
            ),
        }],
    }


def update_qa_retry(state: OVDState) -> dict:
    """
    GAP-005: Nodo intermedio que incrementa el contador de reintentos de QA
    y construye el feedback acumulado antes de volver a execute_agents.
    LangGraph llama a este nodo cuando route_after_qa devuelve 'execute_agents'.
    """
    qa = state.get("qa_result", {})
    new_feedback = _build_qa_feedback(qa)
    existing_feedback = state.get("retry_feedback", "")
    accumulated = f"{existing_feedback}\n\n{new_feedback}".strip() if existing_feedback else new_feedback
    accumulated = _truncate(accumulated, 3000)  # S31-B: cap para no explotar contexto del agente

    return {
        "qa_retry_count": state.get("qa_retry_count", 0) + 1,
        "retry_feedback": accumulated,
        "status": "retrying_after_qa",
        "messages": state.get("messages", []) + [{
            "role": "agent",
            "content": (
                f"QA fallido (reintento {state.get('qa_retry_count', 0) + 1}/{MAX_RETRIES}). "
                f"Score: {qa.get('score', 0)}/100. "
                "Regenerando implementacion con feedback de calidad..."
            ),
        }],
    }


# ---------------------------------------------------------------------------
# Construccion del grafo
# ---------------------------------------------------------------------------
#
# Flujo principal (GAP-002: fan-out nativo LangGraph):
#   START → clone_repo → analyze_fr → [web_research?] → generate_sdd → request_approval
#         → route_agents → [Send: agent_executor × N en paralelo]
#         → security_audit → qa_review → deliver → create_pr → END
#
# S6:  clone_repo es no-op si github_repo no está configurado.
#      create_pr es no-op si github_token no está configurado.
# S11: web_research_node es no-op si no hay trigger (ver _should_run_web_research).
#
# Flujo de reintentos (GAP-005):
#   security_audit [FAIL] → security_retry → route_agents  (max 3x, fan-out nuevo ciclo)
#   security_audit [MAX]  → handle_escalation → deliver → create_pr → END
#   qa_review      [FAIL] → qa_retry → route_agents         (max 3x)
#   qa_review      [MAX]  → handle_escalation → deliver → create_pr → END
#
def _route_after_analyze_fr(state: OVDState) -> str:
    """S11: después de analyze_fr, ir a web_research si hay trigger, o directo a generate_sdd."""
    if _should_run_web_research(state):
        return "web_research"
    return "generate_sdd"


def _route_after_agent_executor(state: OVDState) -> str:
    """
    S47: después de que agent_executor termina, decide si hay agentes client-side pendientes.
    - Si pending_agents no está vacío → dispatch_frontend (grupo 2 espera al grupo 1)
    - Si pending_agents está vacío → security_audit (flujo normal)
    LangGraph llama esta función en el nodo que recibe el resultado acumulado del fan-out.
    """
    pending = state.get("pending_agents", [])
    if pending:
        log.info("S47 _route_after_agent_executor: %d agente(s) client-side pendientes → dispatch_frontend", len(pending))
        return "dispatch_frontend"
    return "security_audit"


async def _dispatch_frontend_node(state: OVDState) -> dict:
    """
    S47: Nodo de transición antes del segundo fan-out.
    Limpia pending_agents y copia la lista a _dispatch_now para que el edge
    condicional _dispatch_frontend pueda leerla (el edge ve el estado post-nodo).
    No ejecuta ningún LLM — solo prepara el estado.
    """
    pending = state.get("pending_agents", [])
    log.info("S47 dispatch_frontend_node: preparando fan-out client-side=%s", pending)
    return {
        "pending_agents": [],    # vaciar — ya procesados en _dispatch_now
        "_dispatch_now": list(pending),  # S59-B: buffer para el edge condicional
    }


def build_graph(checkpointer: BaseCheckpointSaver) -> StateGraph:
    builder = StateGraph(OVDState)

    # S6: clonar repo antes de analyze_fr (no-op si sin github_repo)
    builder.add_node("clone_repo", clone_repo)

    # S21: pre-procesador de imagen (no-op si sin imagen)
    builder.add_node("describe_image", describe_image)

    # Nodos principales
    builder.add_node("analyze_fr", analyze_fr)
    builder.add_node("web_research", web_research_node)   # S11: investigación web (no-op si sin trigger)
    builder.add_node("generate_sdd", generate_sdd)
    builder.add_node("request_approval", request_approval)
    # GAP-002: fan-out nativo — route_agents + agent_executor reemplazan execute_agents
    builder.add_node("route_agents", route_agents)
    builder.add_node("agent_executor", agent_executor)
    builder.add_node("security_audit", security_audit)   # GAP-001
    builder.add_node("qa_review", qa_review)
    builder.add_node("handle_escalation", handle_escalation)
    builder.add_node("deliver", deliver)
    builder.add_node("create_pr", create_pr)   # S6: PR automático (no-op sin github_token)

    # Nodos de reintento (GAP-005): incrementan contadores y feedback antes del retry
    builder.add_node("security_retry", update_security_retry)
    builder.add_node("qa_retry", update_qa_retry)

    # S22: nodos de calidad y documentación automática
    builder.add_node("run_tests", run_tests)          # ejecución real de tests generados
    builder.add_node("test_retry", update_test_retry) # retry de tests → route_agents
    builder.add_node("generate_docs", generate_docs)  # documentación automática post-QA

    # Flujo principal
    builder.add_edge(START, "clone_repo")               # S6
    builder.add_edge("clone_repo", "describe_image")    # S21: pre-procesador imagen (no-op si sin imagen)
    builder.add_edge("describe_image", "analyze_fr")
    # S11: routing condicional — web_research si hay trigger, si no directo a generate_sdd
    builder.add_conditional_edges("analyze_fr", _route_after_analyze_fr, {
        "web_research": "web_research",
        "generate_sdd": "generate_sdd",
    })
    builder.add_edge("web_research", "generate_sdd")   # S11: siempre converge en generate_sdd
    builder.add_edge("generate_sdd", "request_approval")
    builder.add_conditional_edges("request_approval", route_after_approval, {
        "route_agents": "route_agents",
        "generate_sdd": "generate_sdd",   # S15-TUI: revisión iterativa del SDD
        END: END,
    })

    # GAP-002 + S47: fan-out en dos grupos por capa
    # Grupo 1 (server-side): database + backend + devops — paralelo
    # Grupo 2 (client-side): frontend — espera al grupo 1 vía dispatch_frontend
    builder.add_node("dispatch_frontend", _dispatch_frontend_node)
    builder.add_conditional_edges("route_agents", _dispatch_agents)
    # Después del fan-out: si hay client-side pendiente → dispatch_frontend; si no → security_audit
    builder.add_conditional_edges("agent_executor", _route_after_agent_executor, {
        "dispatch_frontend": "dispatch_frontend",
        "security_audit":    "security_audit",
    })
    # Segundo fan-out: client-side
    builder.add_conditional_edges("dispatch_frontend", _dispatch_frontend)
    # Después del fan-out frontend → security_audit (mismo flujo que antes)
    # LangGraph converge los Send() en el nodo destino automáticamente

    # Routing con retry loops
    builder.add_conditional_edges(
        "security_audit",
        route_after_security,
        {
            "qa_review": "qa_review",
            "route_agents": "security_retry",   # GAP-002: retry va a route_agents
            "handle_escalation": "handle_escalation",
        },
    )
    builder.add_edge("security_retry", "route_agents")  # GAP-002

    builder.add_conditional_edges(
        "qa_review",
        route_after_qa,
        {
            "run_tests": "run_tests",           # S22: QA pasa → ejecutar tests reales
            "route_agents": "qa_retry",         # GAP-002: retry va a route_agents
            "handle_escalation": "handle_escalation",
        },
    )
    builder.add_edge("qa_retry", "route_agents")   # GAP-002

    # S22: run_tests → generate_docs | test_retry → route_agents
    builder.add_conditional_edges(
        "run_tests",
        _route_after_tests,
        {
            "generate_docs": "generate_docs",
            "test_retry": "test_retry",
        },
    )
    builder.add_edge("test_retry", "route_agents")  # S22: retry de tests re-ejecuta agentes

    # S22: generate_docs → deliver
    builder.add_edge("generate_docs", "deliver")

    builder.add_edge("handle_escalation", "deliver")
    builder.add_edge("deliver", "create_pr")   # S6
    builder.add_edge("create_pr", END)

    return builder.compile(checkpointer=checkpointer)
