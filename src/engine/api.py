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
import hmac
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sse_starlette.sse import EventSourceResponse

# Fase A — MCP Client Pool (context7 + futuros servidores)
import mcp_client
import nats_client

# S11.G — Nightly Web Researcher scheduler
import nightly_researcher
import pending_store
import rag_seed
import research
import telemetry  # Sprint 10 — GAP-A6
import web_researcher  # Sprint 11 — S11.B
from audit_logger import AuditLogger  # Sprint 10
from checkpointer import checkpointer_context
from context_resolver import ContextResolver  # Sprint 8 — GAP-A3
from graph import OVDState, build_graph

# LOW-03 — Rate limiting en endpoints de autenticación
from rate_limiter import limiter
from routers.api_v1 import router as api_v1_router

# S12 — API Web pública
from routers.auth_router import router as auth_router

# PP-03 + PP-02 + S20-GAP-R3 — Atomic Task Checkout + Heartbeat Watcher + Stale Cancel
from settings import get_settings
from startup_check import assert_env, check_ollama_model
from task_checkout import (
    AlreadyRunningError,
    SessionLock,
    cancel_stale_sessions,
    detect_stale_sessions,
    register_task,
)

# ---------------------------------------------------------------------------
# Estado global del engine
# ---------------------------------------------------------------------------

log = logging.getLogger("ovd.api")

_cfg = get_settings()

_graph = None
_checkpointer = None

# S20 — GAP-R1: timeout global del stream SSE. Si el grafo no termina en este tiempo,
# el stream se cierra con un evento de error. Configurable via OVD_SSE_STREAM_TIMEOUT_SECS.
_SSE_STREAM_TIMEOUT: float = _cfg.ovd_sse_stream_timeout_secs

# S47-A: Background graph execution — el grafo corre en tasks separadas del SSE
# Al desconectarse el cliente, la ejecución del grafo NO se cancela.
_graph_tasks: dict[str, asyncio.Task] = {}  # thread_id → background task del grafo
_event_queues: dict[str, asyncio.Queue] = {}  # thread_id → queue de eventos SSE
_stream_done: dict[str, asyncio.Event] = {}  # thread_id → señal de fin de stream

# v0.2: Replay buffer para reconexión SSE con Last-Event-ID
_event_replay: dict[
    str, list[dict]
] = {}  # thread_id → eventos ordenados con id asignado
_event_id_counters: dict[str, int] = {}  # thread_id → próximo id de evento
_REPLAY_BUFFER_MAX = 500  # máx eventos en memoria por thread


def _configure_app_loggers() -> None:
    """S59-A/A1: configura logging con dictConfig para garantizar handlers en todos los loggers de app."""
    import logging.config as _lc

    level_str = os.environ.get(
        "OVD_LOG_LEVEL", os.environ.get("LOG_LEVEL", "WARNING")
    ).upper()
    numeric = getattr(logging, level_str, logging.WARNING)
    _lc.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "ovd": {"format": "%(asctime)s [%(name)s] %(levelname)s %(message)s"},
            },
            "handlers": {
                "stderr": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stderr",
                    "formatter": "ovd",
                },
            },
            "root": {"level": numeric, "handlers": ["stderr"]},
            "loggers": {
                "uvicorn": {"level": numeric, "propagate": True},
                "uvicorn.error": {"level": numeric, "propagate": True},
                "ovd.api": {"level": numeric, "propagate": True},
                "ovd.graph": {"level": numeric, "propagate": True},
                "ovd-graph": {"level": numeric, "propagate": True},
                "ovd.startup": {"level": numeric, "propagate": True},
                "ovd.heartbeat": {"level": numeric, "propagate": True},
            },
        }
    )
    logging.getLogger("ovd.api").warning(
        "S59-A/A1: logging configurado via dictConfig — OVD_LOG_LEVEL=%s (numeric=%d)",
        level_str,
        numeric,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graph, _checkpointer
    _configure_app_loggers()  # S56-B: configurar antes de assert_env para capturar warnings
    assert_env()  # falla rapido si faltan variables criticas
    await (
        check_ollama_model()
    )  # P3.B: verifica modelo Ollama disponible (warning, no fatal)
    telemetry.setup_telemetry()  # Sprint 10: inicializa OTEL provider
    async with checkpointer_context() as cp:
        await cp.setup()
        _checkpointer = cp
        _graph = build_graph(_checkpointer)
        nightly_researcher.start_scheduler()  # S11.G: arranca job nightly en background
        # PP-02 — Heartbeat watcher: detecta sesiones colgadas cada 60s
        watcher_task = asyncio.create_task(_stale_session_watcher())
        # Fase A — iniciar MCP pool (context7); fallo es no-fatal
        await mcp_client.pool.start()
        yield
    # S11.G — detener scheduler antes de cerrar
    nightly_researcher.stop_scheduler()
    watcher_task.cancel()
    # Fase A — cerrar sesiones MCP
    await mcp_client.pool.stop()
    # N1.A — cerrar conexión NATS al apagar el engine
    await nats_client.close()


app = FastAPI(
    title="OVD Engine",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — orígenes permitidos configurables por variable de entorno.
# En dev: http://localhost:5173 (Vite). En prod: dominio del dashboard.
# OVD_CORS_ORIGINS puede ser una lista separada por comas.
_cors_raw = (
    _cfg.ovd_cors_origins
    or "http://localhost:5173,http://localhost:3000,http://localhost:80"
)
_cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-OVD-Secret"],
)

# LOW-03: registrar rate limiter y handler de límite excedido
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# S12 — routers de API pública
app.include_router(auth_router)
app.include_router(api_v1_router)

# ---------------------------------------------------------------------------
# Auth: verifica X-OVD-Secret en cada request
# ---------------------------------------------------------------------------

OVD_SECRET = _cfg.ovd_engine_secret


def verify_secret(
    x_ovd_secret: str | None = Header(default=None, alias="X-OVD-Secret"),
    authorization: str | None = Header(default=None),
    token: str | None = Query(
        default=None
    ),  # EventSource no soporta headers — usa ?token=
) -> None:
    """FastAPI Dependency: acepta JWT válido (dashboard) O X-OVD-Secret válido (TUI/CLI).

    Usar via Depends(verify_secret) en cada endpoint protegido.
    Si viene un JWT Bearer válido (header o query ?token=), se omite el check del secret.
    EventSource del browser no soporta headers — usa ?token=<jwt> para el stream SSE.
    Si no hay JWT, se exige X-OVD-Secret (autenticación TUI/CLI server-to-server).
    """
    # SEC MEDIUM-01: usar compare_digest para evitar timing attacks
    if not OVD_SECRET:
        return  # sin secret configurado, no hay restricción (dev/test)

    # Extraer JWT: desde Authorization: Bearer <token> O desde ?token=<jwt>
    jwt_token: str | None = None
    if authorization and authorization.startswith("Bearer "):
        jwt_token = authorization[7:]
    elif token:
        jwt_token = token

    if jwt_token:
        from auth import verify_access_token

        try:
            verify_access_token(jwt_token)
            return  # JWT válido → no se requiere X-OVD-Secret
        except Exception:
            pass  # JWT inválido/expirado → continúa a check de secret

    # Sin JWT válido → exigir X-OVD-Secret (TUI/CLI)
    if not hmac.compare_digest(x_ovd_secret or "", OVD_SECRET):
        raise HTTPException(status_code=401, detail="X-OVD-Secret invalido")


# ---------------------------------------------------------------------------
# Modelos de request/response
# ---------------------------------------------------------------------------


class StartSessionRequest(BaseModel):
    session_id: str = ""  # si no viene, el server usa thread_id
    org_id: str
    project_id: str = ""
    directory: str = ""  # opcional — dashboard no tiene ruta local
    feature_request: str = ""
    parent_thread_id: str | None = None
    # Sprint 8 — project_context acepta JSON estructurado del Stack Registry
    # (retrocompatible: si llega texto libre, ContextResolver lo envuelve como project_description)
    project_context: str = (
        ""  # perfil tecnologico — JSON del Stack Registry o texto libre
    )
    jwt_token: str = ""  # JWT del Bridge para consultar config de agentes (GAP-013a)
    rag_context: str = ""  # contexto RAG pre-recuperado por el Bridge (GAP-006)
    language: str = "es"  # Idioma de los prompts del sistema (FASE 5.C): es | en | pt
    auto_approve: bool = False  # P5.A: si True, salta el interrupt de aprobación humana
    # S6 — GitHub PAT (inyectado por Bridge desde Project Profile)
    github_token: str = ""  # PAT del proyecto
    github_repo: str = ""  # URL del repo, ej: https://github.com/org/repo
    github_branch: str = "main"  # branch base
    # S11 — Web Researcher: activación explícita (también se activa via [research] en el FR)
    research_enabled: bool = False
    # S21 — Visión: imagen adjunta al Feature Request (qwen2.5vl pre-procesador)
    image_base64: str = (
        ""  # imagen codificada en base64 (PNG/JPG/WEBP) — engine la procesa
    )
    image_description: str = (
        ""  # descripción ya procesada externamente — omite el nodo describe_image
    )


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
    # Sin "event:" field — todos los eventos disparan onmessage en el cliente.
    # El tipo se discrimina con el campo "type" dentro del JSON.
    return {"data": json.dumps({"type": event_type, "data": data})}


async def _stream_graph_events(thread_id: str, config: dict) -> AsyncIterator[dict]:
    """
    Ejecuta el grafo en modo streaming y emite eventos SSE.
    Mapea los eventos del grafo al contrato de eventos del bridge TypeScript.
    """
    graph = _graph
    if not graph:
        yield _make_sse_event(
            "error", {"message": "Engine no inicializado", "recoverable": False}
        )
        return

    try:
        last_done_event: dict | None = None
        last_message_content: str = ""

        async for mode, event in graph.astream(
            None, config, stream_mode=["values", "updates"]
        ):
            if mode == "updates":
                # Emitir node_end por cada nodo que acaba de completarse
                for node_name, node_output in event.items():
                    if node_name == "__interrupt__":
                        continue
                    yield _make_sse_event("node_end", {"node": node_name})
                    # S22: eventos custom para nodos de calidad y docs
                    if isinstance(node_output, dict):
                        if node_name == "run_tests" and node_output.get("test_results"):
                            yield _make_sse_event(
                                "test_results", node_output["test_results"]
                            )
                        elif (
                            node_name == "generate_docs"
                            and node_output.get("generated_docs") is not None
                        ):
                            yield _make_sse_event(
                                "generated_docs",
                                {
                                    "count": len(node_output.get("generated_docs", [])),
                                    "docs": [
                                        {"type": d.get("type"), "path": d.get("path")}
                                        for d in node_output.get("generated_docs", [])
                                    ],
                                },
                            )
                continue

            # mode == "values": estado completo tras cada nodo
            # Emitir mensajes nuevos del estado (solo si el contenido cambió)
            messages = event.get("messages", [])
            if messages:
                last = messages[-1]
                content = last.get("content", "")
                if content and content != last_message_content:
                    last_message_content = content
                    yield _make_sse_event(
                        "message",
                        {
                            "role": last.get("role", "agent"),
                            "content": content,
                        },
                    )

            # Acumular el estado "done" — no emitir todavía (create_pr corre después)
            if event.get("status", "") == "done":
                last_done_event = event

        # El grafo terminó — emitir evento done con estado final (incluye github_pr de create_pr)
        if last_done_event is not None:
            token_usage = last_done_event.get("token_usage", {})
            total_in = sum(
                v.get("input", 0) for v in token_usage.values() if isinstance(v, dict)
            )
            total_out = sum(
                v.get("output", 0) for v in token_usage.values() if isinstance(v, dict)
            )
            yield _make_sse_event(
                "done",
                {
                    "summary": f"Ciclo completado. {len(last_done_event.get('deliverables', []))} artefacto(s).",
                    "deliverables": last_done_event.get("deliverables", []),
                    # P4.C — security y QA para resumen en TUI
                    "security_result": last_done_event.get("security_result", {}),
                    "qa_result": last_done_event.get("qa_result", {}),
                    # S22 — calidad y docs
                    "test_results": last_done_event.get("test_results", {}),
                    "security_scan_results": last_done_event.get(
                        "security_scan_results", {}
                    ),
                    "generated_docs": last_done_event.get("generated_docs", []),
                    "token_summary": {
                        "total_input": total_in,
                        "total_output": total_out,
                    },
                    # S6 — URL del PR creado (vacío si sin GitHub config)
                    "github_pr": last_done_event.get("github_pr", {}),
                    # Incluir estado para cycle log y fine-tuning
                    "state": {
                        "feature_request": last_done_event.get("feature_request", ""),
                        "fr_analysis": last_done_event.get("fr_analysis", {}),
                        "sdd": last_done_event.get("sdd", {}),
                        "agent_results": last_done_event.get("agent_results", []),
                        "security_result": last_done_event.get("security_result", {}),
                        "qa_result": last_done_event.get("qa_result", {}),
                        "test_results": last_done_event.get("test_results", {}),
                        "security_scan_results": last_done_event.get(
                            "security_scan_results", {}
                        ),
                        "generated_docs": last_done_event.get("generated_docs", []),
                        "token_usage": token_usage,
                        "github_pr": last_done_event.get("github_pr", {}),
                    },
                },
            )

        # S29-A: INSERT a ovd_cycles movido al nodo deliver (graph.py)
        # para garantizar persistencia aunque el cliente SSE se desconecte.

        # Tras el stream: detectar interrupt de aprobación pendiente (request_approval)
        if graph and not last_done_event:
            try:
                snap = await graph.aget_state(config)
                if snap and snap.tasks:
                    for task in snap.tasks:
                        for interrupt in task.interrupts or []:
                            iv = (
                                interrupt.value
                                if hasattr(interrupt, "value")
                                else interrupt
                            )
                            if (
                                isinstance(iv, dict)
                                and iv.get("type") == "pending_approval"
                            ):
                                ctx = iv.get("context", {})
                                sv = snap.values or {}
                                pending_store.add(
                                    config["configurable"]["thread_id"],
                                    {
                                        "thread_id": config["configurable"][
                                            "thread_id"
                                        ],
                                        "session_id": sv.get("session_id", ""),
                                        "org_id": sv.get("org_id", ""),
                                        "project_id": sv.get("project_id", ""),
                                        "feature_request": sv.get(
                                            "feature_request", ""
                                        ),
                                        "sdd_summary": ctx.get("sdd_summary", ""),
                                        "sdd": {
                                            "summary": ctx.get("sdd_summary", ""),
                                            "requirements": ctx.get("requirements", []),
                                            "tasks": ctx.get("tasks", []),
                                            "constraints": ctx.get("constraints", []),
                                        },
                                        "revision_count": sv.get("revision_count", 0),
                                    },
                                )
                                yield _make_sse_event(
                                    "pending_approval",
                                    {
                                        "sdd_summary": ctx.get("sdd_summary", ""),
                                        "requirements": ctx.get("requirements", []),
                                        "tasks": ctx.get("tasks", []),
                                        "constraints": ctx.get("constraints", []),
                                        "fr_type": ctx.get("fr_type", ""),
                                        "complexity": ctx.get("complexity", ""),
                                        "revision_count": sv.get("revision_count", 0),
                                    },
                                )
            except Exception:
                pass  # no propagar errores de detección de interrupt

    except (
        BaseException
    ) as e:  # S46-A: captura CancelledError (BaseException) además de Exception
        error_msg = str(e) if str(e) else type(e).__name__
        log.error(
            "_stream_graph_events: excepción fatal — %s: %s",
            type(e).__name__,
            error_msg,
            exc_info=True,
        )
        yield _make_sse_event(
            "error",
            {
                "message": error_msg,
                "error_type": type(e).__name__,
                "recoverable": False,
            },
        )
        if isinstance(e, (KeyboardInterrupt, SystemExit)):
            raise  # no silenciar señales del sistema operativo


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
    _: None = Depends(verify_secret),
):
    thread_id = body.parent_thread_id or str(uuid.uuid4())
    session_id = body.session_id or thread_id  # dashboard no genera session_id propio

    config = {
        "configurable": {
            "thread_id": thread_id,
            "org_id": body.org_id,
            "project_id": body.project_id,
        }
    }

    # Verificar si el thread ya existe (resumir sesion)
    if _checkpointer:
        existing = await _checkpointer.aget(config)
        if existing:
            return JSONResponse(
                {
                    "thread_id": thread_id,
                    "session_id": session_id,
                    "status": "resumed",
                }
            )

    # Nueva sesion: recuperar contexto RAG si no viene pre-cargado (GAP-006)
    rag_ctx = body.rag_context
    if not rag_ctx and body.feature_request and body.jwt_token:
        rag_ctx = rag_seed.retrieve_context(
            body.feature_request, body.org_id, body.project_id, body.jwt_token
        )

    # S45-A: Si project_context no viene en el body (dashboard no lo envía),
    # cargarlo desde ovd_project_profiles para que constraints y stack lleguen a los agentes.
    effective_project_context = body.project_context
    if not effective_project_context and body.project_id:
        _db_url = os.environ.get("DATABASE_URL", "")
        if _db_url:
            try:
                async with await psycopg.AsyncConnection.connect(_db_url) as _conn:
                    _row = await _conn.execute(
                        """SELECT language, framework, db_engine, runtime, additional_stack,
                                  legacy_stack, constraints, code_style, project_description
                           FROM ovd_project_profiles
                           WHERE project_id = %s AND org_id = %s AND active = true
                           LIMIT 1""",
                        (body.project_id, body.org_id),
                    )
                    _r = await _row.fetchone()
                    if _r:
                        _profile = {
                            "language": _r[0] or "",
                            "framework": _r[1] or "",
                            "db_engine": _r[2] or "",
                            "runtime": _r[3] or "",
                            "additional_stack": _r[4] if _r[4] else [],
                            "legacy_stack": _r[5] or "",
                            "constraints": _r[6] or "",
                            "code_style": _r[7] or "",
                            "project_description": _r[8] or "",
                        }
                        effective_project_context = json.dumps(
                            _profile, ensure_ascii=False
                        )
                        logging.getLogger("ovd.api").info(
                            "session_create: S45-A perfil cargado desde ovd_project_profiles "
                            "— constraints=%d chars, framework=%s",
                            len(_r[6] or ""),
                            _r[1] or "—",
                        )
            except Exception as _e:
                logging.getLogger("ovd.api").warning(
                    "session_create: S45-A error al cargar ovd_project_profiles — %s",
                    _e,
                )

    # Sprint 8+9 — GAP-A3+GAP-A4: construir AgentContext tipado desde el profile
    # to_prompt_block() genera el markdown con restricciones del stack (S8)
    # resolve_async() recupera credenciales desde Infisical si hay secret_ref (S9)
    lang = body.language if body.language in ("es", "en", "pt") else "es"
    agent_ctx = await ContextResolver.resolve_async(
        org_id=body.org_id,
        project_id=body.project_id,
        project_context=effective_project_context,  # S45-A: usa perfil cargado desde BD si body vacío
        rag_context=rag_ctx,
        language=lang,
    )
    resolved_project_context = agent_ctx.to_prompt_block()

    # Resolver directorio del workspace: usar body.directory si viene explícito,
    # si no, hacer lookup en ovd_projects por project_id (dashboard no envía directory)
    resolved_directory = body.directory
    if not resolved_directory and body.project_id:
        _db_url = os.environ.get("DATABASE_URL", "")
        if _db_url:
            try:
                async with await psycopg.AsyncConnection.connect(_db_url) as _conn:
                    _row = await _conn.execute(
                        "SELECT directory FROM ovd_projects WHERE id = %s AND org_id = %s",
                        (body.project_id, body.org_id),
                    )
                    _r = await _row.fetchone()
                    if _r and _r[0]:
                        resolved_directory = _r[0]
                        logging.getLogger("ovd.api").info(
                            "session_create: directory resuelto desde proyecto — %s",
                            resolved_directory,
                        )
            except Exception as _e:
                logging.getLogger("ovd.api").warning(
                    "session_create: no se pudo resolver directory del proyecto — %s",
                    _e,
                )

    if not resolved_directory and body.project_id:
        # S120-A: directorio de fallback cuando el proyecto no tiene directory en BD.
        # Normalizar project_id a slug: PRJ_TURNOS_DEMO → prj-turnos-demo
        _slug = body.project_id.lower().replace("_", "-")
        resolved_directory = f"/srv/projects/{_slug}"
        logging.getLogger("ovd.api").warning(
            "session_create: S120-A directorio fallback — project_id=%s → %s",
            body.project_id,
            resolved_directory,
        )

    if not resolved_directory:
        import tempfile as _tempfile

        resolved_directory = _tempfile.mkdtemp(prefix=f"ovd_{session_id[:8]}_")
        logging.getLogger("ovd.api").info(
            "session_create: directory no provisto — tmpdir creado: %s",
            resolved_directory,
        )

    # S104-C + S105-P1: limpiar residuos de ciclos anteriores
    if resolved_directory:
        import shutil as _shutil_c
        from pathlib import Path as _Path_c

        _ws = _Path_c(resolved_directory)

        # S112-D: crear el directorio del proyecto si no existe (DO App Platform no lo pre-crea)
        _ws.mkdir(parents=True, exist_ok=True)

        # S104-C: eliminar __pycache__ para evitar bytecode residual
        for _cache_dir in _ws.rglob("__pycache__"):
            try:
                _shutil_c.rmtree(_cache_dir, ignore_errors=True)
            except Exception:
                pass
        logging.getLogger("ovd.api").info(
            "session_create: S104-C __pycache__ limpiado en %s", resolved_directory
        )

        # S105-P1: eliminar test_*.py generados por ciclos anteriores para evitar
        # naming_mismatch entre tests OLD (de un SDD anterior) y código NEW (del SDD actual).
        # Los tests del ciclo nuevo los regenera el agente backend — no los preservamos entre ciclos.
        _tests_dir = _ws / "tests"
        if _tests_dir.exists():
            _removed = []
            for _old_test in _tests_dir.glob("test_*.py"):
                try:
                    _old_test.unlink()
                    _removed.append(_old_test.name)
                except Exception:
                    pass
            if _removed:
                logging.getLogger("ovd.api").info(
                    "session_create: S105-P1 eliminados %d test(s) del ciclo anterior: %s",
                    len(_removed),
                    _removed,
                )

    # S42-E: Resolver stack_language desde ovd_stack_profiles por project_id
    resolved_stack_language = ""
    if body.project_id:
        _db_url = os.environ.get("DATABASE_URL", "")
        if _db_url:
            try:
                async with await psycopg.AsyncConnection.connect(_db_url) as _conn:
                    _row = await _conn.execute(
                        "SELECT language FROM ovd_stack_profiles WHERE project_id = %s AND active = true LIMIT 1",
                        (body.project_id,),
                    )
                    _r = await _row.fetchone()
                    if _r and _r[0]:
                        resolved_stack_language = _r[0].lower().strip()
                        logging.getLogger("ovd.api").info(
                            "session_create: S42-E stack_language='%s' para project_id=%s",
                            resolved_stack_language,
                            body.project_id,
                        )
            except Exception as _e:
                logging.getLogger("ovd.api").warning(
                    "session_create: S42-E no se pudo resolver stack_language — %s", _e
                )

    # Nueva sesion: inicializar el estado del grafo
    initial_state: OVDState = {
        "session_id": session_id,
        "org_id": body.org_id,
        "project_id": body.project_id,
        "directory": resolved_directory,
        "feature_request": body.feature_request,
        "project_context": resolved_project_context,  # S8: bloque tipado con restricciones incluidas
        "stack_routing": agent_ctx.model_routing,  # S8: routing efectivo para model_router
        "stack_language": resolved_stack_language,  # S42-E: lenguaje del stack ("python", "typescript", ...)
        "jwt_token": body.jwt_token,
        "rag_context": rag_ctx,
        "language": lang,
        "constraints_version": "",  # se calcula en analyze_fr
        "uncertainty_register": [],
        "fr_analysis": {},
        "sdd": {},
        "approval_decision": "",
        "approval_comment": "",
        "revision_count": 0,
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
        "github_token": body.github_token,
        "github_repo": body.github_repo,
        "github_branch": body.github_branch or "main",
        "github_pr": {},
        # S11 — Web Researcher
        "research_enabled": body.research_enabled,
        "web_research_results": [],
        # S21 — Visión
        "image_base64": body.image_base64,
        "image_description": body.image_description,
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
        session_id=session_id,
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

    # S47-B: registrar ciclo como 'started' al crear sesión — visible en telemetría
    # aunque el ciclo no llegue a deliver. ON CONFLICT DO NOTHING: si ya existe (reanudación), no pisar.
    try:
        _db_url_for_cycle = os.environ.get("DATABASE_URL", "")
        if _db_url_for_cycle:
            import psycopg as _psycopg47

            async with await _psycopg47.AsyncConnection.connect(
                _db_url_for_cycle
            ) as _c47:
                await _c47.execute("SET app.current_org_id = %s", (body.org_id,))
                await _c47.execute(
                    """INSERT INTO ovd_cycles
                         (id, org_id, project_id, session_id, thread_id,
                          fr_text, auto_approved, status)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,'started')
                       ON CONFLICT (thread_id) DO NOTHING""",
                    (
                        str(uuid.uuid4()),
                        body.org_id,
                        body.project_id or None,
                        session_id,
                        thread_id,
                        body.feature_request,
                        body.auto_approve,
                    ),
                )
                await _c47.commit()
    except Exception as _db47_err:
        log.warning("S47-B: error registrando ciclo 'started' — %s", _db47_err)

    # S70-A: disparar background task inmediatamente — no esperar SSE
    if thread_id not in _event_queues:
        _event_queues[thread_id] = asyncio.Queue(maxsize=2000)
        _stream_done[thread_id] = asyncio.Event()
    _s70_existing = _graph_tasks.get(thread_id)
    if _s70_existing is None or _s70_existing.done():
        _stream_done[thread_id].clear()
        _s70_task = asyncio.create_task(
            _run_graph_background(thread_id, config),
            name=f"ovd_graph_{thread_id[:8]}",
        )
        _graph_tasks[thread_id] = _s70_task
        log.info(
            "S70-A: background task lanzada para thread=%s sin esperar SSE",
            thread_id[:8],
        )

    return JSONResponse(
        {
            "thread_id": thread_id,
            "session_id": session_id,
            "status": "created",
        },
        status_code=201,
    )


async def _queue_put_with_replay(thread_id: str, event: dict) -> None:
    """v0.2: asigna id monotónico al evento, lo guarda en replay buffer y lo encola."""
    queue = _event_queues.get(thread_id)
    if queue is None:
        return
    n = _event_id_counters.get(thread_id, 0) + 1
    _event_id_counters[thread_id] = n
    event_with_id = {**event, "id": str(n)}
    buf = _event_replay.setdefault(thread_id, [])
    buf.append(event_with_id)
    if len(buf) > _REPLAY_BUFFER_MAX:
        buf.pop(0)
    await queue.put(event_with_id)


async def _run_graph_background(thread_id: str, config: dict) -> None:
    """
    S47-A: ejecuta el grafo LangGraph en una task asyncio separada del SSE.

    Ventaja clave: si el cliente SSE se desconecta, esta task NO se cancela.
    El grafo completa su ejecución y los eventos se acumulan en _event_queues[thread_id]
    para que el cliente pueda reconectar y recibir el estado actualizado.
    """
    queue = _event_queues[thread_id]
    done_ev = _stream_done[thread_id]
    try:
        async with SessionLock(thread_id):
            # PP-05 — registrar sesión activa para el Org Chart
            session_meta: dict = {
                "org_id": "",
                "project_id": "",
                "feature_request": "",
                "session_id": "",
            }
            if _graph:
                try:
                    snap = await _graph.aget_state(config)
                    if snap and snap.values:
                        v = snap.values
                        session_meta = {
                            "org_id": v.get("org_id", ""),
                            "project_id": v.get("project_id", ""),
                            "feature_request": v.get("feature_request", ""),
                            "session_id": v.get("session_id", ""),
                        }
                except Exception:
                    pass
            from task_checkout import register_session, unregister_session

            register_session(thread_id, session_meta)
            # S20-GAP-R3: registrar task para poder cancelarla si queda stale
            current_task = asyncio.current_task()
            if current_task is not None:
                register_task(thread_id, current_task)
            try:
                # S20-GAP-R1: timeout global — el grafo no puede correr eternamente
                async with asyncio.timeout(_SSE_STREAM_TIMEOUT):
                    async for event in _stream_graph_events(thread_id, config):
                        await _queue_put_with_replay(thread_id, event)
            except asyncio.TimeoutError:
                log.error(
                    "S47-A: timeout global para thread=%s tras %.0fs",
                    thread_id,
                    _SSE_STREAM_TIMEOUT,
                )
                await _queue_put_with_replay(
                    thread_id,
                    _make_sse_event(
                        "error",
                        {
                            "message": f"Timeout global del grafo ({_SSE_STREAM_TIMEOUT:.0f}s). Consulta /session/{thread_id}/state",
                            "recoverable": False,
                        },
                    ),
                )
            finally:
                unregister_session(thread_id)
    except AlreadyRunningError:
        await _queue_put_with_replay(
            thread_id,
            _make_sse_event(
                "error",
                {
                    "message": "Ciclo ya en ejecución — espera a que termine o usa /session/{thread_id}/state",
                    "recoverable": False,
                },
            ),
        )
    except Exception as exc:
        log.error(
            "S47-A: error fatal en background task thread=%s: %s",
            thread_id,
            exc,
            exc_info=True,
        )
        await _queue_put_with_replay(
            thread_id,
            _make_sse_event(
                "error",
                {
                    "message": str(exc) or type(exc).__name__,
                    "recoverable": False,
                },
            ),
        )
    finally:
        done_ev.set()
        _graph_tasks.pop(thread_id, None)
        # S48-D: loguear el nodo donde quedó el grafo (diagnóstico de fallos)
        if _graph:
            try:
                snap = await _graph.aget_state(config)
                if snap:
                    last_node = (
                        snap.metadata.get("source", "?") if snap.metadata else "?"
                    )
                    next_nodes = list(snap.next) if snap.next else []
                    log.info(
                        "S48-D: thread=%s terminó en source='%s', next=%s, values_keys=%s",
                        thread_id[:8],
                        last_node,
                        next_nodes,
                        list(snap.values.keys()) if snap.values else [],
                    )
            except Exception as _snap_err:
                log.debug("S48-D: no se pudo obtener snapshot — %s", _snap_err)
        # S47-B: garantizar registro en ovd_cycles aunque deliver no haya corrido
        await _ensure_cycle_registered(thread_id, config)
        # Limpiar queue y done_event después de 10 min (evitar memory leak)
        # S59-A/A3: add_done_callback para detectar errores en tarea fire-and-forget
        _cleanup_task = asyncio.create_task(_deferred_cleanup(thread_id, 600))

        def _on_cleanup_done(t: asyncio.Task) -> None:
            if not t.cancelled() and (exc := t.exception()):
                log.error(
                    "S59-A: _deferred_cleanup error para thread=%s: %s",
                    thread_id[:8],
                    exc,
                )

        _cleanup_task.add_done_callback(_on_cleanup_done)


async def _deferred_cleanup(thread_id: str, delay: float) -> None:
    """S47-A: limpia queue y done_event un tiempo después de que el grafo termine."""
    await asyncio.sleep(delay)
    _event_queues.pop(thread_id, None)
    _stream_done.pop(thread_id, None)
    _event_replay.pop(thread_id, None)
    _event_id_counters.pop(thread_id, None)


async def _ensure_cycle_registered(thread_id: str, config: dict) -> None:
    """
    S47-B: si deliver no escribió en ovd_cycles, marcar el ciclo como 'failed'
    con los datos parciales disponibles en el checkpoint LangGraph.
    """
    try:
        _db_url = os.environ.get("DATABASE_URL", "")
        if not _db_url:
            return
        import psycopg as _psycopg47b

        # Leer checkpoint antes de abrir conexión (org_id necesario para RLS SET)
        _snap_pre: object = None
        _rls_org_id = ""
        if _graph:
            try:
                _snap_pre = await _graph.aget_state(config)
                if _snap_pre and _snap_pre.values:  # type: ignore[union-attr]
                    _rls_org_id = _snap_pre.values.get("org_id", "")  # type: ignore[union-attr]
            except Exception:
                pass

        async with await _psycopg47b.AsyncConnection.connect(_db_url) as _conn:
            if _rls_org_id:
                await _conn.execute("SET app.current_org_id = %s", (_rls_org_id,))
            cur = await _conn.execute(
                "SELECT status FROM ovd_cycles WHERE thread_id = %s", (thread_id,)
            )
            row = await cur.fetchone()
            if not row:
                log.warning(
                    "S47-B: ciclo %s no registrado en BD (session_create falló?)",
                    thread_id[:8],
                )
                return
            if row[0] == "completed":
                return  # deliver ya lo actualizó correctamente
            # Ciclo terminó sin llegar a deliver — actualizar con datos del checkpoint
            snap = _snap_pre
            if not (snap and snap.values) and _graph:  # type: ignore[union-attr]
                try:
                    snap = await _graph.aget_state(config)
                except Exception:
                    pass
            if snap and snap.values:  # type: ignore[union-attr]
                try:
                    v = snap.values  # type: ignore[union-attr]
                    qa = v.get("qa_result", {})
                    fr_a = v.get("fr_analysis", {})
                    # S59-A/A5: capturar error_message y failed_at_node del checkpoint
                    last_error = v.get("_last_error", "")
                    failed_node = ""
                    if snap.metadata:
                        failed_node = snap.metadata.get("source", "")
                    await _conn.execute(
                        """UPDATE ovd_cycles SET
                            status         = 'failed',
                            fr_analysis    = %s,
                            sdd            = %s,
                            qa_score       = %s,
                            complexity     = %s,
                            fr_type        = %s,
                            error_message  = %s,
                            failed_at_node = %s
                        WHERE thread_id = %s AND status != 'completed'""",
                        (
                            json.dumps(fr_a),
                            json.dumps(v.get("sdd", {})),
                            qa.get("score", 0) if isinstance(qa, dict) else 0,
                            fr_a.get("complexity", ""),
                            fr_a.get("type", ""),
                            last_error or None,
                            failed_node or None,
                            thread_id,
                        ),
                    )
                    await _conn.commit()
                    log.info(
                        "S47-B: ciclo %s marcado 'failed' — nodo=%s error=%s",
                        thread_id[:8],
                        failed_node or "?",
                        (last_error or "")[:120],
                    )
                except Exception as _snap_err:
                    log.warning(
                        "S47-B: error leyendo checkpoint para %s — %s",
                        thread_id[:8],
                        _snap_err,
                    )
    except Exception as _e:
        log.warning("S47-B: _ensure_cycle_registered error — %s", _e)


@app.get("/session/{thread_id}/stream")
async def stream_session(
    thread_id: str,
    request: Request,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    _: None = Depends(verify_secret),
):
    """
    S47-A: SSE que lee de una queue. El grafo corre en background.
    v0.2: soporta Last-Event-ID para reconexión sin perder eventos.

    Si el cliente desconecta, el grafo CONTINÚA ejecutándose.
    Si el cliente reconecta con Last-Event-ID, se reproducen los eventos perdidos.
    """
    config = {"configurable": {"thread_id": thread_id}}

    # Inicializar queue y done_event para este thread si no existen
    if thread_id not in _event_queues:
        _event_queues[thread_id] = asyncio.Queue(maxsize=2000)
        _stream_done[thread_id] = asyncio.Event()
    queue = _event_queues[thread_id]
    done_ev = _stream_done[thread_id]

    # Lanzar background task si no está corriendo (o si el anterior ya terminó)
    existing = _graph_tasks.get(thread_id)
    if existing is None or existing.done():
        done_ev.clear()
        task = asyncio.create_task(
            _run_graph_background(thread_id, config),
            name=f"ovd_graph_{thread_id[:8]}",
        )
        _graph_tasks[thread_id] = task
        log.info("S47-A: background task lanzada para thread=%s", thread_id[:8])

    async def event_generator():
        """
        Lee eventos de la queue y los emite como SSE.
        v0.2: reproduce eventos perdidos si el cliente reconecta con Last-Event-ID.
        Si no hay eventos en 30s, emite heartbeat para mantener la conexión viva.
        """
        # v0.2: replay de eventos perdidos al reconectar
        if last_event_id is not None:
            try:
                last_id = int(last_event_id)
                missed = [
                    e
                    for e in _event_replay.get(thread_id, [])
                    if int(e.get("id", 0)) > last_id
                ]
                if missed:
                    log.info(
                        "v0.2: reconexión thread=%s — reproduciendo %d evento(s) desde id=%s",
                        thread_id[:8],
                        len(missed),
                        last_event_id,
                    )
                for e in missed:
                    yield e
            except (ValueError, TypeError):
                pass

        while not (done_ev.is_set() and queue.empty()):
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield event
            except asyncio.TimeoutError:
                if await request.is_disconnected():
                    log.info(
                        "S47-A: cliente SSE desconectado para %s — grafo continúa en background",
                        thread_id[:8],
                    )
                    break
                # Heartbeat — mantiene la conexión SSE viva durante ciclos largos
                yield _make_sse_event("heartbeat", {"ts": time.time()})
            except asyncio.CancelledError:
                log.info(
                    "S47-A: event_generator cancelado para %s — grafo continúa",
                    thread_id[:8],
                )
                break

    return EventSourceResponse(event_generator())


async def _stale_session_watcher():
    """
    PP-02 — Heartbeat watcher: detecta sesiones colgadas cada 60s.
    Corre como tarea background durante el lifespan del engine.
    """
    _WATCHER_INTERVAL = get_settings().ovd_watcher_interval_secs
    import logging

    log = logging.getLogger("ovd.heartbeat")
    log.info("heartbeat: watcher iniciado (intervalo=%ds)", _WATCHER_INTERVAL)
    while True:
        try:
            await asyncio.sleep(_WATCHER_INTERVAL)
            # S20 — GAP-R3: cancelar sesiones colgadas (no solo detectar)
            cancelled = await cancel_stale_sessions(nats_publish_fn=nats_client.publish)
            if cancelled:
                log.warning(
                    "heartbeat: %d sesión(es) colgada(s) cancelada(s): %s",
                    len(cancelled),
                    cancelled,
                )
        except asyncio.CancelledError:
            log.info("heartbeat: watcher detenido")
            break
        except Exception as e:
            log.error("heartbeat: error en watcher — %s", e)


async def _heartbeat(request: Request):
    """Emite heartbeats mientras la conexion este activa."""
    while True:
        await asyncio.sleep(15)
        if await request.is_disconnected():
            break


@app.get("/session/{thread_id}/state")
async def get_session_state(
    thread_id: str,
    _: None = Depends(verify_secret),
):
    """
    Devuelve el estado actual del ciclo incluyendo el SDD completo.
    Usado por el TUI para poblar la pantalla de revisión iterativa del SDD.
    """
    if not _graph:
        raise HTTPException(503, detail="Engine no inicializado")

    config = {"configurable": {"thread_id": thread_id}}
    state = await _graph.aget_state(config)
    if not state or not state.values:
        raise HTTPException(404, detail="Thread no encontrado")

    v = state.values
    return {
        "status": v.get("status", ""),
        "sdd": v.get("sdd", {}),
        "fr_analysis": v.get("fr_analysis", {}),
        "feature_request": v.get("feature_request", ""),
        "revision_count": v.get("revision_count", 0),
        "revision_history": v.get("revision_history", []),
    }


@app.get("/session/{thread_id}/delivery")
async def get_session_delivery(
    thread_id: str,
    org_id: str,
    _: None = Depends(verify_secret),
):
    """
    S16T.C — Devuelve los entregables completos del ciclo una vez finalizado.
    Incluye: artefactos por agente (con lista de archivos escritos), informe, scores.
    """
    if not _graph:
        raise HTTPException(503, detail="Engine no inicializado")

    config = {"configurable": {"thread_id": thread_id}}
    state = await _graph.aget_state(config)
    if not state or not state.values:
        raise HTTPException(404, detail="Thread no encontrado")

    v = state.values

    # SEC-01: ownership validation — denegar si thread sin org_id o si no coincide.
    # La condición original "if thread_org and ..." permitía acceso cuando el thread
    # no tenía org_id almacenado (brecha estructural).
    if not org_id:
        raise HTTPException(400, detail="org_id es obligatorio")
    thread_org = v.get("org_id", "")
    if not thread_org or thread_org != org_id:
        raise HTTPException(
            403, detail="No autorizado: thread pertenece a otra organización"
        )
    security = v.get("security_result", {})
    qa = v.get("qa_result", {})

    token_usage = v.get("token_usage", {})
    total_in = sum(
        u.get("input", 0) for u in token_usage.values() if isinstance(u, dict)
    )
    total_out = sum(
        u.get("output", 0) for u in token_usage.values() if isinstance(u, dict)
    )

    elapsed = 0.0
    if v.get("cycle_start_ts"):
        import time as _time

        elapsed = _time.time() - v["cycle_start_ts"]

    return {
        "status": v.get("status", ""),
        "directory": v.get("directory", ""),
        "deliverables": v.get("deliverables", []),
        "security": {
            "score": security.get("score"),
            "passed": security.get("passed"),
            "severity": security.get("severity"),
        },
        "qa": {
            "score": qa.get("score"),
            "passed": qa.get("passed"),
            "sdd_compliance": qa.get("sdd_compliance"),
            "issues": qa.get("issues", []),
        },
        "tokens_in": total_in,
        "tokens_out": total_out,
        "elapsed_secs": round(elapsed, 1),
    }


@app.get("/session/{thread_id}/artifacts/download")
async def download_session_artifacts(
    thread_id: str,
    _: None = Depends(verify_secret),
):
    """S112-E: descarga el código generado por el ciclo como ZIP."""
    import io
    import zipfile
    from pathlib import Path as _ArtPath

    if not _graph:
        raise HTTPException(503, detail="Engine no inicializado")

    config = {"configurable": {"thread_id": thread_id}}
    state = await _graph.aget_state(config)
    if not state or not state.values:
        raise HTTPException(404, detail="Thread no encontrado")

    v = state.values
    directory = v.get("directory", "")
    session_id = v.get("session_id", thread_id)

    if not directory:
        raise HTTPException(404, detail="Directorio de entregables no configurado")

    ws = _ArtPath(directory)
    if not ws.exists():
        raise HTTPException(404, detail=f"Directorio no encontrado: {directory}")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in ws.rglob("*"):
            if f.is_file() and "__pycache__" not in str(f) and ".git" not in str(f):
                zf.write(f, f.relative_to(ws))
    buf.seek(0)

    filename = f"ovd-{session_id[:8]}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.delete("/session/{thread_id}")
async def cleanup_session(
    thread_id: str,
    _: None = Depends(verify_secret),
):
    """S125: elimina el tmpdir del engine para este ciclo (llamado por el desktop tras extraer ZIP)."""
    if not _graph:
        raise HTTPException(503, detail="Engine no inicializado")

    config = {"configurable": {"thread_id": thread_id}}
    state = await _graph.aget_state(config)
    if not state or not state.values:
        return {"ok": True, "removed": False, "reason": "thread no encontrado"}

    directory = state.values.get("directory", "")
    if not directory:
        return {"ok": True, "removed": False, "reason": "sin directorio"}

    import tempfile as _tmpmod
    from pathlib import Path as _CleanPath

    # Solo eliminar si es un tmpdir creado por el engine (no el directorio de trabajo del proyecto)
    tmp_root = _tmpmod.gettempdir()
    p = _CleanPath(directory)
    if not str(p).startswith(tmp_root):
        return {"ok": True, "removed": False, "reason": "no es tmpdir — se preserva"}

    import shutil as _shutil_del

    try:
        _shutil_del.rmtree(directory, ignore_errors=True)
        logging.getLogger("ovd.api").info(
            "S125: tmpdir eliminado por desktop: %s", directory
        )
        return {"ok": True, "removed": True, "directory": directory}
    except Exception as e:
        return {"ok": False, "removed": False, "reason": str(e)}


@app.post("/session/{thread_id}/approve")
async def approve_session(
    thread_id: str,
    body: ApproveRequest,
    _: None = Depends(verify_secret),
):
    if not _graph:
        raise HTTPException(503, detail="Engine no inicializado")

    config = {"configurable": {"thread_id": thread_id}}

    # Mapear action al valor de approval_decision del grafo
    _action_map = {
        "approve": "approved",
        "reject": "rejected",
        "revise": "revision_requested",
    }
    # Compatibilidad: si no viene action, usar approved boolean
    if body.action not in _action_map:
        body.action = "approve" if body.approved else "reject"

    decision = _action_map[body.action]

    await _graph.aupdate_state(
        config,
        {
            "approval_decision": decision,
            "approval_comment": body.comment or "",
        },
        as_node="request_approval",
    )

    # Limpiar del almacén de aprobaciones pendientes (si venía del dashboard)
    pending_store.remove(thread_id)

    return {"ok": True, "status": decision, "thread_id": thread_id}


@app.post("/session/{thread_id}/escalate")
async def escalate_session(
    thread_id: str,
    body: EscalateRequest,
    _: None = Depends(verify_secret),
):
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
    jwt_token: str = ""  # JWT del Bridge para obtener el Project Profile
    project_context: str = ""  # alternativa: pasar el contexto directamente
    topic: str = ""  # tema especifico a investigar (opcional)
    bridge_url: str = ""  # URL del Bridge (default: variable de entorno)


class ClientEventPayload(BaseModel):
    thread_id: str
    event: str
    client: dict = {}


@app.post("/telemetry/client-event", status_code=204)
async def receive_client_event(
    body: ClientEventPayload,
    _: None = Depends(verify_secret),
):
    """T4 — Recibe eventos de telemetría desde el desktop (fire-and-forget)."""
    log.info(
        "S126-T4 client_event thread=%s event=%s client=%s",
        body.thread_id[:8],
        body.event,
        body.client,
    )


@app.post("/research/run")
async def run_research(
    body: ResearchRequest,
    _: None = Depends(verify_secret),
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

    bridge = body.bridge_url or os.environ.get(
        "OVD_BRIDGE_URL", "http://localhost:3000"
    )

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
    project_id: str | None = None  # None → indexar a nivel org
    jwt_token: str = ""
    queries: list[str]  # términos de búsqueda (máx. 4)
    context: str = ""  # contexto adicional para la síntesis
    bridge_url: str = ""


@app.post("/research/ask")
async def research_ask(
    body: WebResearchRequest,
    _: None = Depends(verify_secret),
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

    bridge = body.bridge_url or os.environ.get(
        "OVD_BRIDGE_URL", "http://localhost:3000"
    )

    findings = await web_researcher.run_web_research(
        queries=body.queries,
        org_id=body.org_id,
        project_id=body.project_id,
        jwt_token=body.jwt_token,
        bridge_url=bridge,
        context=body.context,
    )

    return JSONResponse(
        {
            "synthesis": findings.synthesis,
            "results_count": len(findings.results),
            "indexed": findings.indexed,
            "queries": findings.queries,
            "results": [
                {"title": r.title, "url": r.url, "snippet": r.snippet[:300]}
                for r in findings.results[:10]
            ],
        }
    )


# ---------------------------------------------------------------------------
# Admin — Nightly Researcher (S11.G)
# ---------------------------------------------------------------------------

from auth import verify_access_token  # noqa: E402


@app.post("/admin/nightly-research/run")
async def admin_nightly_run(
    request: Request,
    _: None = Depends(verify_secret),
):
    """
    Dispara el job de investigación nightly manualmente (S11.G).

    Requiere X-OVD-Secret válido o JWT admin. Si se incluye Authorization Bearer,
    verifica que el token tenga rol admin.
    Útil para pruebas y para forzar un ciclo de investigación fuera de hora.

    Response:
      - orgs_processed: número de orgs analizadas
      - total_indexed: documentos indexados en pgvector
      - alerts_sent: alertas CVE publicadas en NATS
      - errors: lista de errores no fatales
    """
    # Si viene JWT, verificar rol admin
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    if token:
        payload = verify_access_token(token)
        if payload.role != "admin":
            raise HTTPException(status_code=403, detail="Se requiere rol admin")

    summary = await nightly_researcher.run_nightly_research()
    return JSONResponse(summary)
