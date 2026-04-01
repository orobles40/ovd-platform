"""
OVD Platform — OVD Engine API
Copyright 2026 Omar Robles

FastAPI app que expone el grafo LangGraph al bridge TypeScript.

Endpoints internos (engine):
  GET  /health                          — estado del engine
  POST /session                         — crear o resumir sesion
  GET  /session/{thread_id}/stream      — SSE stream de eventos del grafo
  POST /session/{thread_id}/approve     — aprobar/rechazar human_approval
  POST /session/{thread_id}/escalate    — escalar a supervision humana

Endpoints públicos (S12 — API Web):
  POST /auth/login                      — autenticación JWT
  POST /auth/refresh                    — rotar refresh token
  POST /auth/logout                     — revocar refresh token
  GET  /auth/me                         — datos del usuario actual
  GET  /api/v1/orgs/{id}/projects       — listado de proyectos
  GET  /api/v1/orgs/{id}/cycles         — historial de ciclos
  GET  /api/v1/orgs/{id}/stats          — métricas agregadas
"""
from __future__ import annotations
import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

import hmac
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from checkpointer import checkpointer_context
from context_resolver import ContextResolver  # Sprint 8 — GAP-A3
from graph import build_graph, OVDState
import nats_client
import rag_seed
import research
import web_researcher  # Sprint 11 — S11.B
from startup_check import assert_env, check_ollama_model
import telemetry          # Sprint 10 — GAP-A6
from audit_logger import AuditLogger  # Sprint 10
# S12 — API Web pública
from routers.auth_router import router as auth_router
from routers.api_v1 import router as api_v1_router
# S11.G — Nightly Web Researcher scheduler
import nightly_researcher

# ---------------------------------------------------------------------------
# Estado global del engine
# ---------------------------------------------------------------------------

_graph = None
_checkpointer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graph, _checkpointer
    assert_env()                 # falla rapido si faltan variables criticas
    await check_ollama_model()   # P3.B: verifica modelo Ollama disponible (warning, no fatal)
    telemetry.setup_telemetry()  # Sprint 10: inicializa OTEL provider
    async with checkpointer_context() as cp:
        await cp.setup()
        _checkpointer = cp
        _graph = build_graph(_checkpointer)
        nightly_researcher.start_scheduler()   # S11.G: arranca job nightly en background
        yield
    # S11.G — detener scheduler antes de cerrar
    nightly_researcher.stop_scheduler()
    # N1.A — cerrar conexión NATS al apagar el engine
    await nats_client.close()


app = FastAPI(
    title="OVD Engine",
    version="0.1.0",
    lifespan=lifespan,
)

# S12 — routers de API pública
app.include_router(auth_router)
app.include_router(api_v1_router)

# ---------------------------------------------------------------------------
# Auth: verifica X-OVD-Secret en cada request
# ---------------------------------------------------------------------------

OVD_SECRET = os.environ.get("OVD_ENGINE_SECRET", "")


def verify_secret(x_ovd_secret: str | None = Header(default=None)) -> None:
    # SEC MEDIUM-01: usar compare_digest para evitar timing attacks
    if OVD_SECRET and not hmac.compare_digest(x_ovd_secret or "", OVD_SECRET):
        raise HTTPException(status_code=401, detail="X-OVD-Secret invalido")


# ---------------------------------------------------------------------------
# Modelos de request/response
# ---------------------------------------------------------------------------

class StartSessionRequest(BaseModel):
    session_id: str
    org_id: str
    project_id: str
    directory: str
    feature_request: str = ""
    parent_thread_id: str | None = None
    # Sprint 8 — project_context acepta JSON estructurado del Stack Registry
    # (retrocompatible: si llega texto libre, ContextResolver lo envuelve como project_description)
    project_context: str = ""   # perfil tecnologico — JSON del Stack Registry o texto libre
    jwt_token: str = ""         # JWT del Bridge para consultar config de agentes (GAP-013a)
    rag_context: str = ""       # contexto RAG pre-recuperado por el Bridge (GAP-006)
    language: str = "es"        # Idioma de los prompts del sistema (FASE 5.C): es | en | pt
    auto_approve: bool = False  # P5.A: si True, salta el interrupt de aprobación humana
    # S6 — GitHub PAT (inyectado por Bridge desde Project Profile)
    github_token:  str = ""    # PAT del proyecto
    github_repo:   str = ""    # URL del repo, ej: https://github.com/org/repo
    github_branch: str = "main"  # branch base
    # S11 — Web Researcher: activación explícita (también se activa via [research] en el FR)
    research_enabled: bool = False


class ApproveRequest(BaseModel):
    approved: bool
    permission_id: str | None = None
    comment: str | None = None
    # Iterative SDD review (S15-TUI):
    #   "approve"  → aprueba el SDD y ejecuta agentes
    #   "reject"   → rechaza definitivamente el ciclo
    #   "revise"   → solicita revisión: vuelve a generate_sdd con el comment como feedback
    action: str = "approve"


class EscalateRequest(BaseModel):
    reason: str
    escalated_to: str | None = None
    resolution: str | None = None


# ---------------------------------------------------------------------------
# Helpers SSE
# ---------------------------------------------------------------------------

def _make_sse_event(event_type: str, data: dict) -> dict:
    return {"event": event_type, "data": json.dumps({"type": event_type, "data": data})}


async def _stream_graph_events(thread_id: str, config: dict) -> AsyncIterator[dict]:
    """
    Ejecuta el grafo en modo streaming y emite eventos SSE.
    Mapea los eventos del grafo al contrato de eventos del bridge TypeScript.
    """
    graph = _graph
    if not graph:
        yield _make_sse_event("error", {"message": "Engine no inicializado", "recoverable": False})
        return

    try:
        last_done_event: dict | None = None
        last_message_content: str = ""

        async for event in graph.astream(None, config, stream_mode="values"):
            # Emitir mensajes nuevos del estado (solo si el contenido cambió)
            messages = event.get("messages", [])
            if messages:
                last = messages[-1]
                content = last.get("content", "")
                if content and content != last_message_content:
                    last_message_content = content
                    yield _make_sse_event("message", {
                        "role": last.get("role", "agent"),
                        "content": content,
                    })

            # Acumular el estado "done" — no emitir todavía (create_pr corre después)
            if event.get("status", "") == "done":
                last_done_event = event

        # El grafo terminó — emitir evento done con estado final (incluye github_pr de create_pr)
        if last_done_event is not None:
            token_usage = last_done_event.get("token_usage", {})
            total_in  = sum(v.get("input", 0)  for v in token_usage.values() if isinstance(v, dict))
            total_out = sum(v.get("output", 0) for v in token_usage.values() if isinstance(v, dict))
            yield _make_sse_event("done", {
                "summary": f"Ciclo completado. {len(last_done_event.get('deliverables', []))} artefacto(s).",
                "deliverables": last_done_event.get("deliverables", []),
                # P4.C — security y QA para resumen en TUI
                "security_result": last_done_event.get("security_result", {}),
                "qa_result":       last_done_event.get("qa_result", {}),
                "token_summary": {
                    "total_input":  total_in,
                    "total_output": total_out,
                },
                # S6 — URL del PR creado (vacío si sin GitHub config)
                "github_pr": last_done_event.get("github_pr", {}),
                # Incluir estado para cycle log y fine-tuning
                "state": {
                    "feature_request": last_done_event.get("feature_request", ""),
                    "fr_analysis":     last_done_event.get("fr_analysis", {}),
                    "sdd":             last_done_event.get("sdd", {}),
                    "agent_results":   last_done_event.get("agent_results", []),
                    "security_result": last_done_event.get("security_result", {}),
                    "qa_result":       last_done_event.get("qa_result", {}),
                    "token_usage":     token_usage,
                    "github_pr":       last_done_event.get("github_pr", {}),
                },
            })

    except Exception as e:
        yield _make_sse_event("error", {"message": str(e), "recoverable": False})


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "engine": "ovd-engine", "version": "0.1.0"}


@app.post("/session")
async def start_session(
    body: StartSessionRequest,
    request: Request,
    x_ovd_secret: str | None = Header(default=None),
):
    verify_secret(x_ovd_secret)
    thread_id = body.parent_thread_id or str(uuid.uuid4())

    config = {"configurable": {"thread_id": thread_id}}

    # Verificar si el thread ya existe (resumir sesion)
    if _checkpointer:
        existing = await _checkpointer.aget(config)
        if existing:
            return JSONResponse({
                "thread_id": thread_id,
                "session_id": body.session_id,
                "status": "resumed",
            })

    # Nueva sesion: recuperar contexto RAG si no viene pre-cargado (GAP-006)
    rag_ctx = body.rag_context
    if not rag_ctx and body.feature_request and body.jwt_token:
        rag_ctx = rag_seed.retrieve_context(
            body.feature_request, body.org_id, body.project_id, body.jwt_token
        )

    # Sprint 8+9 — GAP-A3+GAP-A4: construir AgentContext tipado desde el profile
    # to_prompt_block() genera el markdown con restricciones del stack (S8)
    # resolve_async() recupera credenciales desde Infisical si hay secret_ref (S9)
    lang = body.language if body.language in ("es", "en", "pt") else "es"
    agent_ctx = await ContextResolver.resolve_async(
        org_id=body.org_id,
        project_id=body.project_id,
        project_context=body.project_context,
        rag_context=rag_ctx,
        language=lang,
    )
    resolved_project_context = agent_ctx.to_prompt_block()

    # Nueva sesion: inicializar el estado del grafo
    initial_state: OVDState = {
        "session_id": body.session_id,
        "org_id": body.org_id,
        "project_id": body.project_id,
        "directory": body.directory,
        "feature_request": body.feature_request,
        "project_context": resolved_project_context,  # S8: bloque tipado con restricciones incluidas
        "stack_routing": agent_ctx.model_routing,      # S8: routing efectivo para model_router
        "jwt_token": body.jwt_token,
        "rag_context": rag_ctx,
        "language": lang,
        "constraints_version": "",  # se calcula en analyze_fr
        "uncertainty_register": [],
        "fr_analysis": {},
        "sdd": {},
        "approval_decision": "",
        "approval_comment": "",
        "revision_count":   0,
        "revision_history": [],
        # GAP-002: fan-out nativo
        "selected_agents": [],
        "current_agent": "",
        "agent_results": [],
        # FASE 4.D: acumulador de tokens por agente
        "token_usage": {},
        "security_result": {},
        "qa_result": {},
        "security_retry_count": 0,
        "qa_retry_count": 0,
        "retry_feedback": "",
        "escalation_resolution": "",
        "deliverables": [],
        "status": "idle",
        "messages": [],
        # P5.A — auto-approve sin interrupt
        "auto_approve": body.auto_approve,
        # P5.C — timestamp inicio (sobreescrito en analyze_fr con time.time())
        "cycle_start_ts": 0.0,
        # S8 — datos adicionales del AgentContext (para logging y debug)
        "stack_db_engine": agent_ctx.stack.db_engine,
        "stack_db_version": agent_ctx.stack.db_version,
        "stack_restrictions": agent_ctx.restrictions,
        # S10 — OTEL trace_id para correlacionar spans de todos los nodos
        "trace_id": "",  # se rellena abajo con el span raíz del ciclo
        # S6 — GitHub PAT (inyectado por Bridge desde Project Profile)
        "github_token":  body.github_token,
        "github_repo":   body.github_repo,
        "github_branch": body.github_branch or "main",
        "github_pr":     {},
        # S11 — Web Researcher
        "research_enabled":    body.research_enabled,
        "web_research_results": [],
    }

    # Sprint 10: span raíz del ciclo — el trace_id se inyecta en el estado
    # para que cada nodo del grafo pueda crear spans hijos correlacionados
    with telemetry.cycle_span(
        thread_id=thread_id,
        org_id=body.org_id,
        project_id=body.project_id,
        feature_request=body.feature_request,
        stack_routing=agent_ctx.model_routing,
    ) as cycle_sp:
        initial_state["trace_id"] = telemetry.get_trace_id(cycle_sp)

    # Guardar estado inicial en checkpointer (no ejecutar aun)
    if _graph:
        await _graph.aupdate_state(config, initial_state)

    # Sprint 10: audit log de sesión creada (fire-and-forget)
    await AuditLogger.session_created(
        org_id=body.org_id,
        project_id=body.project_id,
        session_id=body.session_id,
        thread_id=thread_id,
        feature_request=body.feature_request,
    )

    # Sprint 9: si hay secrets, registrar acceso en audit (sin valores)
    if agent_ctx.workspace_credentials:
        await AuditLogger.secret_accessed(
            org_id=body.org_id,
            project_id=body.project_id,
            secret_ref=agent_ctx.secret_ref,
            keys_count=len(agent_ctx.workspace_credentials),
        )

    return JSONResponse({
        "thread_id": thread_id,
        "session_id": body.session_id,
        "status": "created",
    }, status_code=201)


@app.get("/session/{thread_id}/stream")
async def stream_session(
    thread_id: str,
    request: Request,
    x_ovd_secret: str | None = Header(default=None),
):
    verify_secret(x_ovd_secret)
    config = {"configurable": {"thread_id": thread_id}}

    async def event_generator():
        # Heartbeat cada 15s para mantener conexion
        heartbeat_task = asyncio.create_task(_heartbeat(request))
        try:
            async for event in _stream_graph_events(thread_id, config):
                if await request.is_disconnected():
                    break
                yield event
                await asyncio.sleep(0)
        finally:
            heartbeat_task.cancel()

    return EventSourceResponse(event_generator())


async def _heartbeat(request: Request):
    """Emite heartbeats mientras la conexion este activa."""
    while True:
        await asyncio.sleep(15)
        if await request.is_disconnected():
            break


@app.get("/session/{thread_id}/state")
async def get_session_state(
    thread_id: str,
    x_ovd_secret: str | None = Header(default=None),
):
    """
    Devuelve el estado actual del ciclo incluyendo el SDD completo.
    Usado por el TUI para poblar la pantalla de revisión iterativa del SDD.
    """
    verify_secret(x_ovd_secret)
    if not _graph:
        raise HTTPException(503, detail="Engine no inicializado")

    config = {"configurable": {"thread_id": thread_id}}
    state = await _graph.aget_state(config)
    if not state or not state.values:
        raise HTTPException(404, detail="Thread no encontrado")

    v = state.values
    return {
        "status":           v.get("status", ""),
        "sdd":              v.get("sdd", {}),
        "fr_analysis":      v.get("fr_analysis", {}),
        "feature_request":  v.get("feature_request", ""),
        "revision_count":   v.get("revision_count", 0),
        "revision_history": v.get("revision_history", []),
    }


@app.get("/session/{thread_id}/delivery")
async def get_session_delivery(
    thread_id: str,
    org_id: str,
    x_ovd_secret: str | None = Header(default=None),
):
    """
    S16T.C — Devuelve los entregables completos del ciclo una vez finalizado.
    Incluye: artefactos por agente (con lista de archivos escritos), informe, scores.
    """
    verify_secret(x_ovd_secret)
    if not _graph:
        raise HTTPException(503, detail="Engine no inicializado")

    config = {"configurable": {"thread_id": thread_id}}
    state = await _graph.aget_state(config)
    if not state or not state.values:
        raise HTTPException(404, detail="Thread no encontrado")

    v = state.values

    # SEC-01: verificar que el thread pertenece al org_id del caller
    thread_org = v.get("org_id", "")
    if thread_org and thread_org != org_id:
        raise HTTPException(403, detail="No autorizado: thread pertenece a otra organización")
    security = v.get("security_result", {})
    qa       = v.get("qa_result", {})

    token_usage = v.get("token_usage", {})
    total_in  = sum(u.get("input",  0) for u in token_usage.values() if isinstance(u, dict))
    total_out = sum(u.get("output", 0) for u in token_usage.values() if isinstance(u, dict))

    elapsed = 0.0
    if v.get("cycle_start_ts"):
        import time as _time
        elapsed = _time.time() - v["cycle_start_ts"]

    return {
        "status":       v.get("status", ""),
        "directory":    v.get("directory", ""),
        "deliverables": v.get("deliverables", []),
        "security": {
            "score":   security.get("score"),
            "passed":  security.get("passed"),
            "severity": security.get("severity"),
        },
        "qa": {
            "score":          qa.get("score"),
            "passed":         qa.get("passed"),
            "sdd_compliance": qa.get("sdd_compliance"),
            "issues":         qa.get("issues", []),
        },
        "tokens_in":    total_in,
        "tokens_out":   total_out,
        "elapsed_secs": round(elapsed, 1),
    }


@app.post("/session/{thread_id}/approve")
async def approve_session(
    thread_id: str,
    body: ApproveRequest,
    x_ovd_secret: str | None = Header(default=None),
):
    verify_secret(x_ovd_secret)
    if not _graph:
        raise HTTPException(503, detail="Engine no inicializado")

    config = {"configurable": {"thread_id": thread_id}}

    # Mapear action al valor de approval_decision del grafo
    _action_map = {
        "approve": "approved",
        "reject":  "rejected",
        "revise":  "revision_requested",
    }
    # Compatibilidad: si no viene action, usar approved boolean
    if body.action not in _action_map:
        body.action = "approve" if body.approved else "reject"

    decision = _action_map[body.action]

    await _graph.aupdate_state(
        config,
        {
            "approval_decision": decision,
            "approval_comment":  body.comment or "",
        },
        as_node="request_approval",
    )

    return {"ok": True, "status": decision, "thread_id": thread_id}


@app.post("/session/{thread_id}/escalate")
async def escalate_session(
    thread_id: str,
    body: EscalateRequest,
    x_ovd_secret: str | None = Header(default=None),
):
    verify_secret(x_ovd_secret)
    if not _graph:
        raise HTTPException(503, detail="Engine no inicializado")

    config = {"configurable": {"thread_id": thread_id}}

    await _graph.aupdate_state(
        config,
        {"escalation_resolution": body.resolution or "", "status": "escalated"},
        as_node="handle_escalation",
    )

    return {"ok": True, "status": "escalated", "thread_id": thread_id}


# ---------------------------------------------------------------------------
# Research Agent (GAP-009)
# ---------------------------------------------------------------------------

class ResearchRequest(BaseModel):
    org_id: str
    project_id: str
    jwt_token: str = ""            # JWT del Bridge para obtener el Project Profile
    project_context: str = ""     # alternativa: pasar el contexto directamente
    topic: str = ""               # tema especifico a investigar (opcional)
    bridge_url: str = ""          # URL del Bridge (default: variable de entorno)


@app.post("/research/run")
async def run_research(
    body: ResearchRequest,
    x_ovd_secret: str | None = Header(default=None),
):
    """
    Ejecuta el Research Agent para un proyecto (GAP-009).

    Identifica CVEs, deprecaciones y riesgos de seguridad del stack del proyecto
    y los indexa en el RAG via el Bridge para que los agentes puedan consultarlos
    en ciclos futuros.

    Response:
      - indexed: numero de documentos indexados en el RAG
      - risk_level: nivel de riesgo general del stack
      - summary: resumen ejecutivo
      - cve_count / deprecation_count: contadores por tipo
    """
    verify_secret(x_ovd_secret)

    bridge = body.bridge_url or os.environ.get("OVD_BRIDGE_URL", "http://localhost:3000")

    result = await research.run_research(
        org_id=body.org_id,
        project_id=body.project_id,
        jwt_token=body.jwt_token,
        bridge_url=bridge,
        project_context=body.project_context,
        topic=body.topic,
    )

    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Web Researcher — consultas ad-hoc (Sprint 11 — S11.D)
# ---------------------------------------------------------------------------

class WebResearchRequest(BaseModel):
    org_id: str
    project_id: str | None = None   # None → indexar a nivel org
    jwt_token: str = ""
    queries: list[str]              # términos de búsqueda (máx. 4)
    context: str = ""               # contexto adicional para la síntesis
    bridge_url: str = ""


@app.post("/research/ask")
async def research_ask(
    body: WebResearchRequest,
    x_ovd_secret: str | None = Header(default=None),
):
    """
    Ejecuta el Web Researcher para consultas ad-hoc (Sprint 11 — S11.D).

    A diferencia de /research/run (GAP-009, LLM knowledge-based), este endpoint
    realiza búsquedas web reales en tiempo real.

    Response:
      - synthesis: síntesis LLM de los hallazgos
      - results_count: número de resultados encontrados
      - indexed: documentos indexados en RAG org-level
      - queries: queries ejecutadas (puede diferir del input por límite máximo)
    """
    verify_secret(x_ovd_secret)

    bridge = body.bridge_url or os.environ.get("OVD_BRIDGE_URL", "http://localhost:3000")

    findings = await web_researcher.run_web_research(
        queries=body.queries,
        org_id=body.org_id,
        project_id=body.project_id,
        jwt_token=body.jwt_token,
        bridge_url=bridge,
        context=body.context,
    )

    return JSONResponse({
        "synthesis":     findings.synthesis,
        "results_count": len(findings.results),
        "indexed":       findings.indexed,
        "queries":       findings.queries,
        "results": [
            {"title": r.title, "url": r.url, "snippet": r.snippet[:300]}
            for r in findings.results[:10]
        ],
    })


# ---------------------------------------------------------------------------
# Admin — Nightly Researcher (S11.G)
# ---------------------------------------------------------------------------

from auth import verify_access_token  # noqa: E402


@app.post("/admin/nightly-research/run")
async def admin_nightly_run(
    request: Request,
    x_ovd_secret: str | None = Header(default=None),
):
    """
    Dispara el job de investigación nightly manualmente (S11.G).

    Requiere X-OVD-Secret válido. Si se incluye Authorization Bearer, verifica
    que el token tenga rol admin.
    Útil para pruebas y para forzar un ciclo de investigación fuera de hora.

    Response:
      - orgs_processed: número de orgs analizadas
      - total_indexed: documentos indexados en pgvector
      - alerts_sent: alertas CVE publicadas en NATS
      - errors: lista de errores no fatales
    """
    verify_secret(x_ovd_secret)

    # Si viene JWT, verificar rol admin
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    if token:
        payload = verify_access_token(token)
        if payload.role != "admin":
            raise HTTPException(status_code=403, detail="Se requiere rol admin")

    summary = await nightly_researcher.run_nightly_research()
    return JSONResponse(summary)
