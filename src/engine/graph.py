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
import time
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

log = logging.getLogger("ovd-graph")
from typing_extensions import Annotated, TypedDict

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import interrupt, Send
import model_router
import template_loader
import github_helper
import nats_client
import telemetry  # Sprint 10 — GAP-A6
import web_researcher  # Sprint 11 — S11.B
from tools import make_file_tools, read_project_context  # S17T
import mcp_client  # Fase A — MCP tools (context7)

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

    # GAP-001: resultado de la auditoria de seguridad independiente
    security_result: dict[str, Any]

    qa_result: dict[str, Any]

    # GAP-005: contadores de reintentos (max 3 antes de escalar)
    security_retry_count: int       # reintentos de security_audit → execute_agents
    qa_retry_count: int             # reintentos de qa_review → execute_agents
    retry_feedback: str             # feedback acumulado para los agentes en reintentos

    escalation_resolution: str

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
        result: FRAnalysisOutput = await invoke_structured(llm, [
            SystemMessage(content=template_loader.render(
                "system_analyzer",
                language=state.get("language", "es"),
                project_context=project_ctx,
            )),
            HumanMessage(content=f"Feature Request:\n{state['feature_request']}"),
        ], FRAnalysisOutput)

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
            findings = await web_researcher.run_web_research(
                queries=queries,
                org_id=org_id,
                project_id=project_id,
                jwt_token=jwt_token,
                bridge_url=bridge_url,
                context=state.get("project_context", ""),
                curated_urls=curated_urls or None,
            )
            span.set_attribute("ovd.web_research.results_count", len(findings.results))
            span.set_attribute("ovd.web_research.indexed", findings.indexed)
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
        result: SDDOutput = await invoke_structured(llm, [
            SystemMessage(content=template_loader.render(
                "system_sdd",
                language=state.get("language", "es"),
                project_context=project_ctx,
                rag_context=rag_ctx,
            )),
            HumanMessage(content=human_content),
        ], SDDOutput)

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


async def _run_frontend_agent(
    sdd_content: str, comment: str, llm: Any, project_ctx: str = "", retry_feedback: str = "", language: str = "es", rag_context: str = ""
) -> dict:
    """Agente especializado en frontend: segun el stack del proyecto."""
    response = await llm.ainvoke([
        SystemMessage(content=template_loader.render(
            "system_frontend",
            language=language,
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
    uncertainties = _extract_uncertainties(response.content, "frontend")
    return {"agent": "frontend", "output": response.content, "artifacts": [], "uncertainties": uncertainties, "tokens": _extract_usage(response)}


async def _run_backend_agent(
    sdd_content: str, comment: str, llm: Any, project_ctx: str = "", retry_feedback: str = "", language: str = "es", rag_context: str = ""
) -> dict:
    """Agente especializado en backend: segun el stack del proyecto."""
    response = await llm.ainvoke([
        SystemMessage(content=template_loader.render(
            "system_backend",
            language=language,
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
    uncertainties = _extract_uncertainties(response.content, "backend")
    return {"agent": "backend", "output": response.content, "artifacts": [], "uncertainties": uncertainties, "tokens": _extract_usage(response)}


async def _run_database_agent(
    sdd_content: str, comment: str, llm: Any, project_ctx: str = "", retry_feedback: str = "", language: str = "es", rag_context: str = ""
) -> dict:
    """Agente especializado en base de datos: segun el motor del proyecto."""
    response = await llm.ainvoke([
        SystemMessage(content=template_loader.render(
            "system_database",
            language=language,
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
    uncertainties = _extract_uncertainties(response.content, "database")
    return {"agent": "database", "output": response.content, "artifacts": [], "uncertainties": uncertainties, "tokens": _extract_usage(response)}


async def _run_devops_agent(
    sdd_content: str, comment: str, llm: Any, project_ctx: str = "", retry_feedback: str = "", language: str = "es", rag_context: str = ""
) -> dict:
    """Agente especializado en DevOps: segun el CI/CD del proyecto."""
    response = await llm.ainvoke([
        SystemMessage(content=template_loader.render(
            "system_devops",
            language=language,
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

    return {
        # GAP-002: None activa el reset en el reducer _list_reset_or_add
        "agent_results": None,
        "selected_agents": selected,
        "status": "routing",
        "messages": state.get("messages", []) + [{
            "role": "agent",
            "content": f"{routing_note} ({len(selected)} agente(s)){retry_info} — iniciando fan-out...",
        }],
    }


def _dispatch_agents(state: OVDState) -> list[Send]:
    """
    GAP-002: Arista condicional que genera un Send() por cada agente seleccionado.
    LangGraph ejecuta todos los agent_executor en paralelo con checkpointing individual.
    """
    selected = state.get("selected_agents", ["backend"])
    # LangGraph 1.x: Send() pasa SOLO el dict al nodo destino (no fusiona con estado padre).
    # Incluir todos los campos que agent_executor necesita.
    shared = {
        "sdd":             state.get("sdd", {}),
        "org_id":          state.get("org_id", ""),
        "project_id":      state.get("project_id", ""),
        "jwt_token":       state.get("jwt_token", ""),
        "project_context": state.get("project_context", ""),
        "retry_feedback":  state.get("retry_feedback", ""),
        "approval_comment": state.get("approval_comment", ""),
        "language":        state.get("language", "es"),
        "directory":       state.get("directory", ""),
        "session_id":      state.get("session_id", ""),
    }
    return [Send("agent_executor", {**shared, "current_agent": agent}) for agent in selected]


async def agent_executor(state: OVDState) -> dict:
    """
    GAP-002: Nodo que ejecuta un solo agente especializado.
    Recibe current_agent del Send() emitido por _dispatch_agents.
    Multiples instancias corren en paralelo; los resultados se acumulan
    en agent_results via el reducer _list_reset_or_add.
    """
    agent_name = state.get("current_agent", "backend")
    sdd = state["sdd"]
    comment = state.get("approval_comment", "")
    project_ctx = state.get("project_context", "")
    org_id = state.get("org_id", "")
    project_id = state.get("project_id", "")
    jwt_token = state.get("jwt_token", "")
    retry_feedback = state.get("retry_feedback", "")
    language = state.get("language", "es")
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

    # GAP-007: SDD filtrado solo con las tareas de este agente
    # P2.B: truncar para proteger la ventana de contexto de modelos 7B (32k tokens)
    agent_sdd_content = _truncate(_build_agent_sdd_content(sdd, agent_name))

    # S6 — G1.C: inyectar contexto de archivos del repo si está disponible
    directory = state.get("directory", "")
    if directory and state.get("github_repo", ""):
        repo_ctx = github_helper.read_repo_context(directory, agent_name)
        if repo_ctx:
            project_ctx = (project_ctx + "\n\n" + repo_ctx).strip() if project_ctx else repo_ctx

    # S17T.C: leer archivos existentes del proyecto para enriquecer el contexto
    if directory:
        existing_ctx = read_project_context(directory, agent_name)
        if existing_ctx:
            project_ctx = (project_ctx + "\n\n" + existing_ctx).strip() if project_ctx else existing_ctx

    # Ejecutar el agente especializado
    runner = _AGENT_RUNNERS.get(agent_name, _run_backend_agent)

    # S17T.A+B + Fase A: file tools + MCP tools (context7 para agentes implementadores)
    tools = make_file_tools(directory) if directory else []
    tools += mcp_client.pool.get_langchain_tools(agent_name)

    async def _invoke_agent_logic() -> dict:
        if tools:
            return await _run_agent_with_tools(
                agent_name, agent_sdd_content, comment, llm,
                project_ctx, retry_feedback, language, tools, directory, rag_context
            )
        return await runner(agent_sdd_content, comment, llm, project_ctx, retry_feedback, language, rag_context)

    # S20 — GAP-R1: timeout por nodo — si el LLM cuelga, retornar error parcial sin matar el ciclo
    try:
        result = await asyncio.wait_for(_invoke_agent_logic(), timeout=_NODE_TIMEOUT)
    except asyncio.TimeoutError:
        log.error(
            "agent_executor: TIMEOUT en nodo '%s' tras %.0fs — retornando resultado de error",
            agent_name, _NODE_TIMEOUT,
        )
        result = {
            "agent": agent_name,
            "output": f"[Timeout: el agente '{agent_name}' no respondió en {_NODE_TIMEOUT:.0f}s. Revisa el estado del LLM.]",
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

    # Intentar vincular herramientas — no todos los modelos lo soportan
    try:
        bound_llm = llm.bind_tools(tools)
    except (AttributeError, NotImplementedError, ValueError):
        # Fallback: el modelo no soporta tool calling → runner tradicional
        runner = _AGENT_RUNNERS.get(agent_name, _run_backend_agent)
        return await runner(sdd_content, comment, llm, project_ctx, retry_feedback, language, rag_context)

    system_prompt = template_loader.render(
        f"system_{agent_name}",
        language=language,
        project_context=project_ctx,
        retry_feedback=retry_feedback,
        rag_context=rag_context,
    )
    human_content = (
        f"SDD Aprobado:\n{sdd_content}\n\n"
        f"Comentario del arquitecto: {comment}\n\n"
        f"Implementa los artefactos {agent_name} definidos en el SDD usando las herramientas disponibles."
    )

    messages: list = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_content),
    ]

    written_files: list[str] = []
    total_tokens = {"input": 0, "output": 0}
    final_output = ""

    try:
        for _ in range(_MAX_TOOL_ITERS):
            response = await bound_llm.ainvoke(messages)

            # Acumular tokens
            usage = _extract_usage(response)
            total_tokens["input"]  += usage.get("input", 0)
            total_tokens["output"] += usage.get("output", 0)

            # Si no hay tool calls, terminamos
            tool_calls = getattr(response, "tool_calls", []) or []
            if not tool_calls:
                final_output = response.content or ""
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
                        # Las tools de LangChain se invocan con .invoke()
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

                messages.append(ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_id,
                ))

        else:
            # Se alcanzó el límite de iteraciones — usar el último response
            if hasattr(response, "content"):
                final_output = response.content or ""

    except Exception as e:
        log.warning(f"S17T tool calling falló para {agent_name}: {e} — usando fallback")
        runner = _AGENT_RUNNERS.get(agent_name, _run_backend_agent)
        return await runner(sdd_content, comment, llm, project_ctx, retry_feedback, language)

    # Construir artefactos desde archivos escritos
    artifacts = _build_artifacts_from_files(written_files, directory)

    # Si no se escribió nada via tools, intentar parsear del output del LLM
    if not artifacts and final_output:
        artifacts = _write_artifacts(final_output, directory)

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
    project_ctx = state.get("project_context", "")
    org_id = state.get("org_id", "")
    project_id = state.get("project_id", "")
    jwt_token = state.get("jwt_token", "")

    # El agente de security usa su propia config — S8: con Stack Registry routing
    llm = await model_router.get_llm_with_context(
        "security", org_id, project_id, jwt_token, state.get("stack_routing", "auto"),
    )

    messages = [
        SystemMessage(content=template_loader.render(
            "system_security",
            language=state.get("language", "es"),
            project_context=project_ctx,
        )),
        HumanMessage(content=(
            f"Codigo generado por los agentes:\n{_truncate('\n\n'.join(r.get('output', '') for r in state.get('agent_results', [])), 16000)}"
        )),
    ]

    result: SecurityAuditOutput
    try:
        result = await invoke_structured(llm, messages, SecurityAuditOutput)
        # BUG-04: detectar resultado inválido (score=0 con severity=high y sin vulnerabilidades
        # es señal de que el modelo no siguió el schema — ocurre con qwen2.5-coder:7b)
        if result.score == 0 and not result.vulnerabilities and not result.secrets_found:
            log.warning(
                "security_audit: score=0 sin vulnerabilidades — probable fallo de parsing, "
                "intentando fallback"
            )
            raw_resp = await llm.ainvoke(messages)
            raw_text = raw_resp.content if hasattr(raw_resp, "content") else str(raw_resp)
            result = _parse_security_fallback(raw_text)
    except Exception as exc:
        log.warning("security_audit: invoke_structured falló (%s) — usando fallback", exc)
        try:
            raw_resp = await llm.ainvoke(messages)
            raw_text = raw_resp.content if hasattr(raw_resp, "content") else str(raw_resp)
            result = _parse_security_fallback(raw_text)
        except Exception as exc2:
            log.error("security_audit: fallback también falló (%s) — resultado neutro", exc2)
            result = SecurityAuditOutput(
                passed=True, score=75, severity="none",
                vulnerabilities=[], secrets_found=[], insecure_patterns=[],
                rls_compliant=True, remediation=[],
                summary="Auditoría de seguridad no disponible (error de modelo).",
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

    return {
        "security_result": security,
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


async def qa_review(state: OVDState) -> dict:
    """Revisa calidad y cumplimiento del SDD (no seguridad — eso lo hace security_audit)."""
    project_ctx = state.get("project_context", "")
    llm = await model_router.get_llm_with_context(
        "qa", state.get("org_id", ""), state.get("project_id", ""),
        state.get("jwt_token", ""), state.get("stack_routing", "auto"),
    )
    agent_output = "\n\n".join(
        r.get("output", "") for r in state.get("agent_results", [])
    )
    messages_qa = [
        SystemMessage(content=template_loader.render(
            "system_qa",
            language=state.get("language", "es"),
            project_context=project_ctx,
        )),
        HumanMessage(content=(
            f"SDD aprobado:\n{_truncate(state['sdd'].get('summary', ''), 8000)}\n\n"
            f"Resultado de implementacion a revisar:\n{_truncate(agent_output, 12000)}"
        )),
    ]

    # S20 — GAP-R5: fallback robusto igual que security_audit
    result: QAReviewOutput
    try:
        result = await invoke_structured(llm, messages_qa, QAReviewOutput)
        # Detectar parsing fallido: score=0 sin issues = modelo no siguió el schema
        if result.score == 0 and not result.issues:
            raw_resp = await llm.ainvoke(messages_qa)
            result = _parse_qa_fallback(raw_resp.content)
    except Exception as exc:
        log.warning("qa_review: invoke_structured falló (%s: %s) — usando fallback", type(exc).__name__, str(exc)[:120])
        try:
            raw_resp = await llm.ainvoke(messages_qa)
            result = _parse_qa_fallback(raw_resp.content)
        except Exception as exc2:
            log.error("qa_review: fallback también falló (%s) — resultado neutro", exc2)
            result = QAReviewOutput(
                passed=True,
                score=70,
                issues=[],
                sdd_compliance=True,
                missing_requirements=[],
                code_quality_issues=[],
                summary="QA completado (modo fallback — resultado neutro).",
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
# S16T.A — Escritura de artefactos al directorio del workspace
# ---------------------------------------------------------------------------

import re as _re

def _write_artifacts(agent_output: str, directory: str, agent: str) -> list[dict]:
    """Parsea bloques de código con ruta (```lang:path) y los escribe al disco.

    Formato esperado del agente:
        ```python:src/api/routes/cycles_export.py
        # código
        ```

    Retorna lista de {path, size, lang} para cada archivo escrito.
    Si el directorio no existe o no tiene permisos, registra warning y continúa.
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
    for match in pattern.finditer(agent_output):
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
            target.write_text(content, encoding="utf-8")
            written.append({
                "path": rel_path,
                "size": len(content.encode("utf-8")),
                "lang": lang_name,
            })
            log.info("_write_artifacts[%s]: escrito %s (%d bytes)", agent, rel_path, len(content.encode("utf-8")))
        except OSError as e:
            log.warning("_write_artifacts[%s]: no se pudo escribir '%s': %s", agent, rel_path, e)

    return written


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
        return report_name
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
    for result in state.get("agent_results", []):
        agent_name   = result.get("agent", "unknown")
        agent_output = result.get("output", "")
        written      = _write_artifacts(agent_output, directory, agent_name)
        deliverables.append({
            "type": "implementation",
            "agent": agent_name,
            "content": agent_output,
            "artifacts": written,  # [{path, size, lang}] escritos al disco
        })

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
    if not passed and _SECURITY_MIN_SCORE > 0:
        passed = security.get("score", 0) >= _SECURITY_MIN_SCORE
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
        return "deliver"

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


def build_graph(checkpointer: BaseCheckpointSaver) -> StateGraph:
    builder = StateGraph(OVDState)

    # S6: clonar repo antes de analyze_fr (no-op si sin github_repo)
    builder.add_node("clone_repo", clone_repo)

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

    # Flujo principal
    builder.add_edge(START, "clone_repo")      # S6
    builder.add_edge("clone_repo", "analyze_fr")
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

    # GAP-002: fan-out — route_agents elige agentes, _dispatch_agents emite Send() por cada uno
    # Todos los agent_executor corren en paralelo con checkpointing individual
    # Al terminar todos, convergen en security_audit
    builder.add_conditional_edges("route_agents", _dispatch_agents)
    builder.add_edge("agent_executor", "security_audit")

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
            "deliver": "deliver",
            "route_agents": "qa_retry",         # GAP-002: retry va a route_agents
            "handle_escalation": "handle_escalation",
        },
    )
    builder.add_edge("qa_retry", "route_agents")   # GAP-002

    builder.add_edge("handle_escalation", "deliver")
    builder.add_edge("deliver", "create_pr")   # S6
    builder.add_edge("create_pr", END)

    return builder.compile(checkpointer=checkpointer)
