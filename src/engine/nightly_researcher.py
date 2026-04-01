"""
OVD Platform — Nightly Web Researcher Job (S11.G)
Copyright 2026 Omar Robles

Job proactivo que se ejecuta automáticamente cada noche para cada org activa:
  1. Lee los stack profiles de sus proyectos activos en la BD
  2. Genera queries de búsqueda específicas para el stack (CVEs, deprecaciones)
  3. Busca en web, sintetiza con LLM
  4. Indexa hallazgos directamente en pgvector (sin pasar por el Bridge)
  5. Si detecta CVE → publica alerta en NATS ovd.{org_id}.alerts.security

Scheduler:
  Se registra en el lifespan de FastAPI. Corre a las OVD_NIGHTLY_HOUR UTC (default 2am).
  También se puede disparar manualmente desde POST /admin/nightly-research/run.

Variables de entorno:
  OVD_NIGHTLY_HOUR=2         — hora UTC de ejecución (0-23, default: 2)
  OVD_NIGHTLY_ENABLED=true   — activar/desactivar scheduler (default: true)
  OVD_NIGHTLY_MAX_ORGS=10    — máx orgs procesadas por ejecución (default: 10)
  OVD_NIGHTLY_MAX_QUERIES=3  — máx queries por stack (default: 3)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx
import psycopg
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from search_providers import get_provider, SearchResult

log = logging.getLogger("ovd.nightly_researcher")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_DATABASE_URL    = os.environ.get("DATABASE_URL", "")
_OLLAMA_URL      = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
_EMBED_MODEL     = os.environ.get("OVD_EMBED_MODEL", "nomic-embed-text")
_LLM_MODEL       = os.environ.get("OVD_MODEL", "claude-sonnet-4-6")
_NATS_URL        = os.environ.get("NATS_URL", "nats://localhost:4222")
_NIGHTLY_HOUR    = int(os.environ.get("OVD_NIGHTLY_HOUR", "2"))
_NIGHTLY_ENABLED = os.environ.get("OVD_NIGHTLY_ENABLED", "true").lower() == "true"
_MAX_ORGS        = int(os.environ.get("OVD_NIGHTLY_MAX_ORGS", "10"))
_MAX_QUERIES     = int(os.environ.get("OVD_NIGHTLY_MAX_QUERIES", "3"))

# Palabras clave que indican CVE/vulnerabilidad en la síntesis
_CVE_KEYWORDS = [
    "cve-", "vulnerabilidad", "vulnerability", "exploit", "rce ",
    "remote code execution", "sql injection", "xss", "crítico", "critical",
    "patch urgente", "security advisory", "0-day", "zero-day",
]

_SYNTHESIS_SYSTEM = """Eres un investigador de seguridad y tecnología senior en Omar Robles.

Analiza los resultados de búsqueda web y sintetiza la información técnicamente relevante
para el stack indicado. Enfócate en:
1. CVEs activos o recientes (incluye número CVE si existe)
2. Deprecaciones y breaking changes en versiones actuales
3. Vulnerabilidades conocidas en el stack
4. Actualizaciones de seguridad pendientes

Sé conciso. Si detectas CVEs activos, menciónalos explícitamente con su número.
Si los resultados no son relevantes, indícalo en una línea."""


# ---------------------------------------------------------------------------
# Generación de queries por stack
# ---------------------------------------------------------------------------

def build_stack_queries(stack: dict[str, Any]) -> list[str]:
    """
    Genera queries de búsqueda proactiva basadas en el stack del proyecto.

    Args:
        stack: dict con keys opcionales: language, framework, database,
               db_version, db_restrictions

    Returns:
        Lista de queries priorizadas (CVEs primero, luego deprecaciones)
    """
    queries: list[str] = []
    year = datetime.now(timezone.utc).year

    db      = (stack.get("database") or "").strip()
    db_ver  = (stack.get("db_version") or "").strip()
    lang    = (stack.get("language") or "").strip()
    fw      = (stack.get("framework") or "").strip()

    # Queries de base de datos
    if db:
        db_full = f"{db} {db_ver}".strip()
        queries.append(f"{db_full} CVE {year} security vulnerability")
        queries.append(f"{db_full} deprecation breaking changes {year}")

    # Queries de lenguaje/framework
    if lang:
        queries.append(f"{lang} security advisory {year}")
    if fw:
        queries.append(f"{fw} CVE vulnerability {year}")

    # Fallback genérico si no hay stack definido
    if not queries:
        queries.append(f"software security advisories {year}")

    return queries[:_MAX_QUERIES]


# ---------------------------------------------------------------------------
# Embeddings via Ollama
# ---------------------------------------------------------------------------

async def get_embedding(text: str) -> list[float] | None:
    """
    Genera embedding usando Ollama. Retorna None si Ollama no está disponible.
    El campo embedding en pgvector acepta NULL — el documento se almacena
    pero no participa en búsqueda semántica hasta que se regenere el embedding.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{_OLLAMA_URL}/api/embeddings",
                json={"model": _EMBED_MODEL, "prompt": text[:2000]},
            )
            if resp.status_code == 200:
                return resp.json().get("embedding")
    except Exception as e:
        log.debug("Ollama embedding no disponible: %s", e)
    return None


# ---------------------------------------------------------------------------
# Síntesis LLM
# ---------------------------------------------------------------------------

async def synthesize(queries: list[str], results: list[SearchResult], stack_desc: str) -> str:
    """Sintetiza resultados de búsqueda con el LLM."""
    if not results:
        return "Sin resultados de búsqueda para este stack."

    results_text = "\n\n".join(
        f"[{i+1}] {r.title}\nURL: {r.url}\n{r.snippet[:350]}"
        for i, r in enumerate(results[:12])
    )
    try:
        llm = ChatAnthropic(
            model=_LLM_MODEL,
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            max_tokens=800,
        )
        response = await llm.ainvoke([
            SystemMessage(content=_SYNTHESIS_SYSTEM),
            HumanMessage(content=(
                f"Stack: {stack_desc}\n"
                f"Queries: {', '.join(queries)}\n\n"
                f"Resultados:\n{results_text}\n\n"
                "Sintetiza los hallazgos de seguridad y deprecaciones relevantes."
            )),
        ])
        return response.content
    except Exception as e:
        log.warning("Error en síntesis LLM: %s", e)
        return "\n".join(f"• {r.title}: {r.snippet[:150]}" for r in results[:5])


# ---------------------------------------------------------------------------
# Detección de CVE en síntesis
# ---------------------------------------------------------------------------

def has_cve(text: str) -> bool:
    """True si la síntesis menciona CVEs o vulnerabilidades críticas."""
    lower = text.lower()
    return any(kw in lower for kw in _CVE_KEYWORDS)


def extract_cve_ids(text: str) -> list[str]:
    """Extrae IDs CVE del texto (ej: CVE-2024-12345)."""
    import re
    return re.findall(r"CVE-\d{4}-\d{4,7}", text, re.IGNORECASE)


# ---------------------------------------------------------------------------
# Publicar alerta NATS
# ---------------------------------------------------------------------------

async def publish_cve_alert(org_id: str, project_name: str, synthesis: str, cve_ids: list[str]) -> None:
    """Publica alerta de seguridad en NATS si se detectan CVEs."""
    try:
        import nats
        nc = await nats.connect(_NATS_URL)
        subject = f"ovd.{org_id}.alerts.security"
        payload = json.dumps({
            "type":         "cve_detected",
            "org_id":       org_id,
            "project":      project_name,
            "cve_ids":      cve_ids,
            "summary":      synthesis[:500],
            "detected_at":  datetime.now(timezone.utc).isoformat(),
        }).encode()
        await nc.publish(subject, payload)
        await nc.drain()
        log.info("Alerta CVE publicada en NATS: %s → %s", subject, cve_ids)
    except Exception as e:
        log.warning("No se pudo publicar alerta NATS: %s", e)


# ---------------------------------------------------------------------------
# Indexar en RAG directo (pgvector)
# ---------------------------------------------------------------------------

async def index_to_rag(
    org_id: str,
    project_id: str | None,
    title: str,
    content: str,
    metadata: dict,
) -> bool:
    """
    Inserta el documento directamente en ovd_rag_embeddings (sin Bridge).
    Genera embedding via Ollama; si no está disponible, guarda sin vector.
    """
    embedding = await get_embedding(content)

    try:
        async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
            if embedding:
                await conn.execute(
                    """
                    INSERT INTO ovd_rag_embeddings
                        (org_id, cycle_id, content, embedding, metadata, created_at)
                    VALUES (%s, NULL, %s, %s::vector, %s, %s)
                    """,
                    (
                        org_id,
                        f"[{title}]\n\n{content}",
                        json.dumps(embedding),
                        json.dumps(metadata),
                        datetime.now(timezone.utc),
                    ),
                )
            else:
                # Sin embedding — contenido almacenado, sin búsqueda semántica
                await conn.execute(
                    """
                    INSERT INTO ovd_rag_embeddings
                        (org_id, cycle_id, content, embedding, metadata, created_at)
                    VALUES (%s, NULL, %s, NULL, %s, %s)
                    """,
                    (
                        org_id,
                        f"[{title}]\n\n{content}",
                        json.dumps(metadata),
                        datetime.now(timezone.utc),
                    ),
                )
            await conn.commit()
        return True
    except Exception as e:
        log.error("Error indexando en RAG: %s", e)
        return False


# ---------------------------------------------------------------------------
# Obtener orgs y stacks activos
# ---------------------------------------------------------------------------

async def get_active_orgs_with_stacks() -> list[dict]:
    """
    Retorna lista de orgs activas con sus proyectos y stack profiles.
    Formato: [{"org_id": str, "projects": [{"id", "name", "stack": dict}]}]
    """
    orgs: list[dict] = []
    try:
        async with await psycopg.AsyncConnection.connect(_DATABASE_URL) as conn:
            # Orgs activas (limitado a _MAX_ORGS)
            cur = await conn.execute(
                "SELECT id, name FROM ovd_orgs WHERE active = TRUE LIMIT %s",
                (_MAX_ORGS,),
            )
            rows = await cur.fetchall()

            for org_id, org_name in rows:
                # Proyectos activos con su stack profile más reciente
                cur2 = await conn.execute(
                    """
                    SELECT p.id, p.name,
                           sp.language, sp.framework, sp.database
                    FROM   ovd_projects p
                    LEFT JOIN ovd_stack_profiles sp
                           ON sp.project_id = p.id AND sp.active = TRUE
                    WHERE  p.org_id = %s AND p.active = TRUE
                    LIMIT  20
                    """,
                    (org_id,),
                )
                projects = []
                for pid, pname, lang, fw, db in await cur2.fetchall():
                    projects.append({
                        "id":   pid,
                        "name": pname,
                        "stack": {
                            "language":  lang or "",
                            "framework": fw or "",
                            "database":  db or "",
                        },
                    })
                if projects:
                    orgs.append({
                        "org_id":   org_id,
                        "org_name": org_name,
                        "projects": projects,
                    })
    except Exception as e:
        log.error("Error leyendo orgs de la BD: %s", e)
    return orgs


# ---------------------------------------------------------------------------
# Job principal
# ---------------------------------------------------------------------------

async def run_nightly_research() -> dict:
    """
    Ejecuta el job completo. Retorna resumen de ejecución.
    Es idempotente: si se ejecuta varias veces el mismo día, indexa duplicados
    marcados con la fecha — el RAG deduplicará por similitud en la búsqueda.
    """
    started_at = datetime.now(timezone.utc)
    log.info("nightly_researcher: iniciando job — %s UTC", started_at.strftime("%Y-%m-%d %H:%M"))

    provider  = get_provider()
    orgs      = await get_active_orgs_with_stacks()
    total_docs = 0
    total_cves = 0
    orgs_processed = 0

    for org in orgs:
        org_id    = org["org_id"]
        org_name  = org["org_name"]
        projects  = org["projects"]

        # Deduplicar stacks dentro del org (evitar buscar el mismo stack N veces)
        seen_stacks: set[str] = set()

        for project in projects:
            stack     = project["stack"]
            stack_key = f"{stack.get('language','')}-{stack.get('framework','')}-{stack.get('database','')}".lower()

            if stack_key in seen_stacks or stack_key == "--":
                continue
            seen_stacks.add(stack_key)

            queries = build_stack_queries(stack)
            if not queries:
                continue

            # Búsqueda web
            all_results: list[SearchResult] = []
            for q in queries:
                results = await provider.search(q, max_results=4)
                all_results.extend(results)

            stack_desc = f"{stack.get('language','')} {stack.get('framework','')} {stack.get('database','')}".strip()
            synthesis  = await synthesize(queries, all_results, stack_desc)

            # Indexar en RAG
            title    = f"Nightly research — {stack_desc} — {started_at.strftime('%Y-%m-%d')}"
            metadata = {
                "type":       "nightly_research",
                "stack":      stack_desc,
                "queries":    queries,
                "sources":    [r.url for r in all_results[:5]],
                "org_id":     org_id,
                "project_id": project["id"],
                "run_date":   started_at.isoformat(),
            }
            indexed = await index_to_rag(
                org_id=org_id,
                project_id=None,    # org-level: visible para todos los proyectos del org
                title=title,
                content=synthesis,
                metadata=metadata,
            )
            if indexed:
                total_docs += 1

            # Detección CVE → alerta NATS
            if has_cve(synthesis):
                cve_ids = extract_cve_ids(synthesis)
                total_cves += 1
                log.warning(
                    "CVE detectado en org=%s stack=%s cves=%s",
                    org_name, stack_desc, cve_ids or ["(sin ID explícito)"]
                )
                await publish_cve_alert(org_id, project["name"], synthesis, cve_ids)

        orgs_processed += 1

    elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
    summary = {
        "started_at":     started_at.isoformat(),
        "elapsed_secs":   round(elapsed, 1),
        "orgs_processed": orgs_processed,
        "docs_indexed":   total_docs,
        "cves_detected":  total_cves,
    }
    log.info("nightly_researcher: completado — %s", summary)
    return summary


# ---------------------------------------------------------------------------
# Scheduler asyncio (registrar en lifespan de FastAPI)
# ---------------------------------------------------------------------------

_scheduler_task: asyncio.Task | None = None


async def _scheduler_loop() -> None:
    """Loop que espera hasta la hora configurada y ejecuta el job."""
    log.info("nightly_researcher: scheduler activo (hora: %02d:00 UTC)", _NIGHTLY_HOUR)
    while True:
        now  = datetime.now(timezone.utc)
        # Calcular segundos hasta la próxima ejecución
        next_run = now.replace(hour=_NIGHTLY_HOUR, minute=0, second=0, microsecond=0)
        if next_run <= now:
            # Ya pasó la hora hoy — programar para mañana
            from datetime import timedelta
            next_run = next_run + timedelta(days=1)

        wait_secs = (next_run - now).total_seconds()
        log.info(
            "nightly_researcher: próxima ejecución en %.0f min (%s UTC)",
            wait_secs / 60,
            next_run.strftime("%Y-%m-%d %H:%M"),
        )
        await asyncio.sleep(wait_secs)

        try:
            await run_nightly_research()
        except Exception as e:
            log.error("nightly_researcher: error en job: %s", e)

        # Esperar 1 hora para evitar doble ejecución si el reloj tiene drift
        await asyncio.sleep(3600)


def start_scheduler() -> None:
    """
    Inicia el scheduler en background. Llamar desde el lifespan de FastAPI.
    No hace nada si OVD_NIGHTLY_ENABLED=false.
    """
    global _scheduler_task
    if not _NIGHTLY_ENABLED:
        log.info("nightly_researcher: scheduler desactivado (OVD_NIGHTLY_ENABLED=false)")
        return
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_scheduler_loop())
        log.info("nightly_researcher: scheduler iniciado")


def stop_scheduler() -> None:
    """Cancela el scheduler. Llamar desde el shutdown del lifespan."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        log.info("nightly_researcher: scheduler detenido")
