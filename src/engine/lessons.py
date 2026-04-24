"""
OVD Platform — S41: Módulo de lecciones aprendidas por proyecto y agente.

Indexa errores de ciclos anteriores (QA findings, security findings, test failures,
post-mortems) en pgvector. En el siguiente ciclo del mismo proyecto, cada agente
consulta solo sus propias lecciones antes de escribir código.

doc_type por agente: lesson_backend, lesson_frontend, lesson_database, lesson_devops, lesson_general
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

log = logging.getLogger("ovd-lessons")

# Agentes implementadores conocidos → tienen doc_type propio
_KNOWN_AGENTS = frozenset({"backend", "frontend", "database", "devops"})


def _lesson_doc_type(agent_name: str) -> str:
    """Retorna el doc_type de lección para un agente."""
    if agent_name in _KNOWN_AGENTS:
        return f"lesson_{agent_name}"
    return "lesson_general"


def _is_rag_enabled() -> bool:
    return os.getenv("OVD_RAG_ENABLED", "true").lower() == "true"


def _date_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


async def _index(chunks: list[dict], project_id: str, org_id: str, label: str) -> None:
    """Helper: indexa chunks en pgvector; fire-and-forget — no propaga errores."""
    try:
        import rag
        await rag.index_chunks_async(chunks, project_id=project_id, org_id=org_id)
        log.info("S41: %s — %d chunk(s) indexados en proyecto '%s'", label, len(chunks), project_id)
    except Exception as exc:
        log.warning("S41: error indexando %s en proyecto '%s': %s", label, project_id, exc)


# ---------------------------------------------------------------------------
# S41.A2 — Indexar QA findings
# ---------------------------------------------------------------------------

async def index_qa_finding(
    *,
    project_id: str,
    org_id: str,
    issues: list[str],
    score: int,
    cycle_id: str,
    agent_names: list[str],
) -> None:
    """
    Indexa issues de QA como lecciones para cada agente que participó en el ciclo.
    Solo se indexa si hay issues reales (no cuando QA pasa sin problemas).
    """
    if not _is_rag_enabled() or not issues or not project_id:
        return

    issues_text = "\n".join(f"- {i}" for i in issues[:10])
    agents = [a for a in agent_names if a in _KNOWN_AGENTS] or ["general"]
    date = _date_str()
    short_id = cycle_id[:8] if cycle_id else "?"

    chunks = []
    for agent_name in agents:
        content = (
            f"[QA finding — ciclo {short_id}] score={score}/100\n"
            f"Issues detectados en la implementación:\n{issues_text}\n"
            f"Asegúrate de resolver estos issues antes de finalizar tu implementación."
        )
        chunks.append({
            "content": content,
            "doc_type": _lesson_doc_type(agent_name),
            "source_file": f"qa_finding/{short_id}",
            "metadata": {
                "lesson_type": "qa",
                "agent_name": agent_name,
                "cycle_id": cycle_id,
                "qa_score": score,
                "created_at": date,
            },
        })

    await _index(chunks, project_id, org_id, f"QA finding (score={score})")


# ---------------------------------------------------------------------------
# S41.A3 — Indexar Security findings
# ---------------------------------------------------------------------------

async def index_security_finding(
    *,
    project_id: str,
    org_id: str,
    vulnerabilities: list[str],
    severity: str,
    score: int,
    cycle_id: str,
    agent_names: list[str],
) -> None:
    """
    Indexa vulnerabilidades de seguridad como lecciones.
    Solo se indexa si la severidad es medium o mayor.
    """
    if not _is_rag_enabled() or not project_id:
        return
    if severity in ("none", "low") or not vulnerabilities:
        return

    vulns_text = "\n".join(f"- {v}" for v in vulnerabilities[:10])
    agents = [a for a in agent_names if a in _KNOWN_AGENTS] or ["general"]
    date = _date_str()
    short_id = cycle_id[:8] if cycle_id else "?"

    chunks = []
    for agent_name in agents:
        content = (
            f"[Security finding — ciclo {short_id}] severity={severity}, score={score}/100\n"
            f"Vulnerabilidades encontradas:\n{vulns_text}\n"
            f"Evita estos patrones de seguridad en tu implementación."
        )
        chunks.append({
            "content": content,
            "doc_type": _lesson_doc_type(agent_name),
            "source_file": f"security_finding/{short_id}",
            "metadata": {
                "lesson_type": "security",
                "agent_name": agent_name,
                "severity": severity,
                "cycle_id": cycle_id,
                "qa_score": score,
                "created_at": date,
            },
        })

    await _index(chunks, project_id, org_id, f"Security finding (severity={severity})")


# ---------------------------------------------------------------------------
# S41.A4 — Indexar Test failures
# ---------------------------------------------------------------------------

async def index_test_failure(
    *,
    project_id: str,
    org_id: str,
    error_text: str,
    runner: str,
    cycle_id: str,
    agent_names: list[str],
) -> None:
    """
    Indexa fallos de tests como lecciones.
    Trunca el output del runner para no inflar el índice.
    """
    if not _is_rag_enabled() or not error_text or not project_id:
        return

    # Truncar output a lo relevante (primeras 1500 chars)
    error_truncated = error_text[:1500]
    agents = [a for a in agent_names if a in _KNOWN_AGENTS] or ["general"]
    date = _date_str()
    short_id = cycle_id[:8] if cycle_id else "?"

    chunks = []
    for agent_name in agents:
        content = (
            f"[Test failure — ciclo {short_id}] runner={runner}\n"
            f"Errores detectados:\n{error_truncated}\n"
            f"Corrige estos errores en la implementación para que los tests pasen."
        )
        chunks.append({
            "content": content,
            "doc_type": _lesson_doc_type(agent_name),
            "source_file": f"test_failure/{short_id}",
            "metadata": {
                "lesson_type": "test",
                "agent_name": agent_name,
                "runner": runner,
                "cycle_id": cycle_id,
                "created_at": date,
            },
        })

    await _index(chunks, project_id, org_id, f"Test failure (runner={runner})")


# ---------------------------------------------------------------------------
# S41.A5 — Post-mortem del ciclo completo
# ---------------------------------------------------------------------------

async def index_cycle_postmortem(
    *,
    project_id: str,
    org_id: str,
    cycle_id: str,
    agent_names: list[str],
    qa_score: int,
    security_score: int,
    tests_passed: bool,
    retry_counts: dict[str, int],
) -> None:
    """
    Indexa un resumen del ciclo completo.
    Se indexa siempre al finalizar deliver, independientemente del resultado.
    """
    if not _is_rag_enabled() or not project_id:
        return

    short_id = cycle_id[:8] if cycle_id else "?"
    date = _date_str()
    retries_text = ", ".join(f"{k}={v}" for k, v in retry_counts.items() if v > 0) or "ninguno"
    agents_text = ", ".join(agent_names) if agent_names else "ninguno"

    content = (
        f"[Postmortem — ciclo {short_id}]\n"
        f"Agentes: {agents_text}\n"
        f"QA: {qa_score}/100 | Security: {security_score}/100 | Tests: {'PASSED' if tests_passed else 'FAILED'}\n"
        f"Reintentos: {retries_text}"
    )

    agents_to_index = [a for a in agent_names if a in _KNOWN_AGENTS] or ["general"]

    chunks = []
    for agent_name in agents_to_index:
        chunks.append({
            "content": content,
            "doc_type": _lesson_doc_type(agent_name),
            "source_file": f"postmortem/{short_id}",
            "metadata": {
                "lesson_type": "postmortem",
                "agent_name": agent_name,
                "cycle_id": cycle_id,
                "qa_score": qa_score,
                "created_at": date,
            },
        })

    await _index(chunks, project_id, org_id, "Postmortem")


# ---------------------------------------------------------------------------
# S41.B1 — Consultar lecciones para un agente
# ---------------------------------------------------------------------------

async def query_lessons_context(
    *,
    project_id: str,
    agent_name: str,
    fr_text: str,
    top_k: int = 5,
) -> str:
    """
    S41.B1: Consulta lecciones relevantes para un agente y proyecto específico.

    Busca en:
      - lesson_{agent_name}  — lecciones específicas del agente
      - lesson_general       — lecciones cross-agent (postmortems, test failures)

    Retorna string formateado listo para inyectar en el prompt del agente.
    Retorna "" si no hay lecciones, RAG no está disponible, o falla silenciosamente.
    """
    if not _is_rag_enabled() or not project_id or not fr_text:
        return ""

    try:
        import rag

        agent_doc_type = _lesson_doc_type(agent_name)
        doc_types = [agent_doc_type]
        if agent_doc_type != "lesson_general":
            doc_types.append("lesson_general")

        context = await rag.search_async(
            query=fr_text,
            project_id=project_id,
            top_k=top_k,
            rag_filters=rag.RagFilters(doc_types=doc_types),
        )
        return context
    except Exception as exc:
        log.warning("S41.B1: error consultando lecciones para agente '%s': %s", agent_name, exc)
        return ""
