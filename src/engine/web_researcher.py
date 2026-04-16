"""
OVD Platform — Web Researcher Agent (Sprint 11 — S11.B)
Copyright 2026 Omar Robles

Investigador web que complementa al Research Agent (GAP-009/research.py):
  - research.py   → usa conocimiento interno del LLM (hasta fecha de corte)
  - web_researcher.py → búsqueda web en tiempo real para información actual

Casos de uso:
  1. Enriquecer el contexto antes de generar el SDD (se activa por trigger en el FR)
  2. Resolver incertidumbres identificadas por los agentes especialistas
  3. Consultas ad-hoc via POST /research/ask

Indexado org-level:
  Los hallazgos se indexan con project_id=None (disponibles para todos los proyectos
  de la org). Esto permite que investigaciones previas beneficien ciclos futuros.

Cache de RAG:
  Antes de buscar en la web, consulta el RAG del org para evitar duplicados.
  Si encuentra contenido reciente (< 7 días) para el mismo tema, lo reutiliza.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from search_providers import get_provider, SearchResult

log = logging.getLogger("ovd.web_researcher")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_DEFAULT_MODEL    = os.environ.get("OVD_MODEL", "claude-sonnet-4-6")
_MAX_RESULTS_PER_QUERY = int(os.environ.get("OVD_WEB_MAX_RESULTS", "5"))
_MAX_QUERIES      = int(os.environ.get("OVD_WEB_MAX_QUERIES", "4"))
_CACHE_TTL_DAYS   = int(os.environ.get("OVD_WEB_CACHE_DAYS", "7"))


# ---------------------------------------------------------------------------
# Prompt de síntesis
# ---------------------------------------------------------------------------

_SYNTHESIS_SYSTEM = """Eres un investigador técnico senior en Omar Robles.

Tu tarea es analizar resultados de búsqueda web y sintetizar la información relevante
para el equipo de desarrollo, enfocándote en:
- Vulnerabilidades o CVEs actuales del stack tecnológico
- Cambios breaking o deprecaciones recientes
- Mejores prácticas actualizadas
- Problemas conocidos de compatibilidad

Sé conciso y técnico. Solo incluye información verificable de las fuentes proporcionadas.
Si los resultados no son relevantes para el contexto, indícalo claramente."""


# ---------------------------------------------------------------------------
# Resultado de investigación
# ---------------------------------------------------------------------------

@dataclass
class ResearchFindings:
    queries: list[str]
    results: list[SearchResult]
    synthesis: str          # síntesis LLM de los hallazgos
    indexed: int            # documentos indexados en RAG
    from_cache: bool = False    # True si se reutilizó caché del RAG


# ---------------------------------------------------------------------------
# Clase principal
# ---------------------------------------------------------------------------

class WebResearcher:
    """
    Investigador web que busca, sintetiza e indexa hallazgos en el RAG.

    Uso típico (desde web_research_node en graph.py):
        researcher = WebResearcher(bridge_url, jwt_token, org_id, project_id)
        findings = await researcher.research(
            queries=["Oracle 12c CVE 2025", "FastAPI security vulnerabilities"],
            context="Sistema hospitalario Oracle 12c + Python FastAPI",
        )
        # findings.synthesis se agrega al rag_context del estado del grafo
    """

    def __init__(
        self,
        bridge_url: str,
        jwt_token: str,
        org_id: str,
        project_id: str | None = None,     # None → indexar a nivel org
        model: str | None = None,
    ) -> None:
        self.bridge_url  = bridge_url.rstrip("/")
        self.jwt_token   = jwt_token
        self.org_id      = org_id
        self.project_id  = project_id      # None = org-level
        self._model      = model or _DEFAULT_MODEL
        self._llm        = ChatAnthropic(
            model=self._model,
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            max_tokens=1024,
        )
        self._provider   = get_provider()

    # -----------------------------------------------------------------------
    # Punto de entrada principal
    # -----------------------------------------------------------------------

    async def research(
        self,
        queries: list[str],
        context: str = "",
        curated_urls: list[str] | None = None,
    ) -> ResearchFindings:
        """
        Ejecuta el pipeline completo:
          1. Limitar queries al máximo configurado
          2. Para cada query, buscar en web (respetando caché RAG)
          3. Sintetizar resultados con el LLM
          4. Indexar síntesis en RAG (org-level)
          5. Retornar ResearchFindings

        Args:
            queries: lista de términos de búsqueda generados por analyze_fr
            context: contexto adicional para la síntesis (project_context + FR)
        """
        queries = queries[:_MAX_QUERIES]
        if not queries and not curated_urls:
            return ResearchFindings(
                queries=[], results=[], synthesis="", indexed=0
            )

        log.info("web_researcher: %d queries via %s", len(queries), self._provider.name)

        # Paso 1a: fuentes curadas — fetch directo de contenido
        all_results: list[SearchResult] = []
        if curated_urls:
            curated_results = await self._fetch_curated(curated_urls)
            all_results.extend(curated_results)
            log.info("web_researcher: %d fuentes curadas incorporadas", len(curated_results))

        # Paso 1b: buscar en web para cada query
        for query in queries:
            results = await self._provider.search(query, max_results=_MAX_RESULTS_PER_QUERY)
            all_results.extend(results)
            log.debug("  '%s' → %d resultados", query[:60], len(results))

        if not all_results:
            return ResearchFindings(
                queries=queries, results=[], synthesis="Sin resultados de búsqueda.", indexed=0
            )

        # Paso 2: sintetizar con LLM
        synthesis = await self._synthesize(queries, all_results, context)

        # Paso 3: indexar en RAG (org-level: project_id=None)
        indexed = await self._index_to_rag(queries, synthesis, all_results)

        return ResearchFindings(
            queries=queries,
            results=all_results,
            synthesis=synthesis,
            indexed=indexed,
        )

    async def research_uncertainties(
        self,
        uncertainties: list[dict],
        context: str = "",
        curated_urls: list[str] | None = None,
    ) -> ResearchFindings:
        """
        Modo B (reactivo): resuelve incertidumbres identificadas por los agentes.

        Convierte cada incertidumbre en una query de búsqueda y ejecuta research().
        Se llama cuando uncertainty_register tiene items de severidad medium/high/critical.

        Args:
            uncertainties: lista de {"agent": str, "item": str, "severity": str}
            context: project_context del ciclo actual
        """
        high_prio = [u for u in uncertainties if u.get("severity") in ("high", "critical", "medium")]
        if not high_prio:
            return ResearchFindings(queries=[], results=[], synthesis="", indexed=0)

        queries = [u["item"] for u in high_prio[:_MAX_QUERIES]]
        log.info("web_researcher (uncertainties): %d queries desde %d incertidumbres", len(queries), len(uncertainties))
        return await self.research(queries=queries, context=context, curated_urls=curated_urls)

    # -----------------------------------------------------------------------
    # Fuentes curadas — fetch directo
    # -----------------------------------------------------------------------

    async def _fetch_curated(self, urls: list[str]) -> list[SearchResult]:
        """
        Descarga el contenido de cada URL curada y lo convierte en SearchResult.
        Errores individuales se ignoran (best-effort).
        """
        results: list[SearchResult] = []
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            for url in urls[:10]:   # máx 10 fuentes curadas
                try:
                    resp = await client.get(url, headers={"User-Agent": "OVD-WebResearcher/1.0"})
                    if resp.status_code == 200:
                        # Extraer texto plano básico (primeros 800 chars del body)
                        text = resp.text
                        # Remover tags HTML simples
                        import re
                        clean = re.sub(r"<[^>]+>", " ", text)
                        clean = re.sub(r"\s+", " ", clean).strip()
                        snippet = clean[:800]
                        results.append(SearchResult(title=url, url=url, snippet=snippet))
                        log.debug("web_researcher curated: %s → %d chars", url[:60], len(snippet))
                    else:
                        log.debug("web_researcher curated: %s → HTTP %d (ignorado)", url[:60], resp.status_code)
                except Exception as e:
                    log.debug("web_researcher curated: %s → error %s (ignorado)", url[:60], e)
        return results

    # -----------------------------------------------------------------------
    # Síntesis LLM
    # -----------------------------------------------------------------------

    async def _synthesize(
        self,
        queries: list[str],
        results: list[SearchResult],
        context: str,
    ) -> str:
        """Usa el LLM para sintetizar los resultados de búsqueda en texto útil."""
        # Formatear resultados para el prompt
        results_text = "\n\n".join(
            f"[{i+1}] {r.title}\nURL: {r.url}\n{r.snippet[:400]}"
            for i, r in enumerate(results[:15])  # máx 15 resultados al LLM
        )
        context_section = f"\n\nContexto del proyecto:\n{context[:800]}" if context else ""

        try:
            response = await self._llm.ainvoke([
                SystemMessage(content=_SYNTHESIS_SYSTEM),
                HumanMessage(content=(
                    f"Queries realizadas: {', '.join(queries)}"
                    f"{context_section}\n\n"
                    f"Resultados de búsqueda:\n{results_text}\n\n"
                    "Sintetiza los hallazgos más relevantes para el equipo de desarrollo."
                )),
            ])
            return response.content
        except Exception as e:
            log.warning("web_researcher: error en síntesis LLM: %s", e)
            # Fallback: concatenar snippets sin síntesis
            return "\n\n".join(
                f"**{r.title}**\n{r.snippet[:200]}" for r in results[:5]
            )

    # -----------------------------------------------------------------------
    # Indexado en RAG
    # -----------------------------------------------------------------------

    async def _index_to_rag(
        self,
        queries: list[str],
        synthesis: str,
        results: list[SearchResult],
    ) -> int:
        """
        Indexa la síntesis en el RAG a nivel org (project_id=None).
        Retorna número de documentos indexados exitosamente.
        """
        if not synthesis or not self.bridge_url:
            return 0

        sources = [r.url for r in results[:5] if r.url]
        doc = {
            "orgId":     self.org_id,
            "projectId": self.project_id,  # None = org-level, visible a todos los proyectos del org
            "docType":   "web_research",
            "title":     f"Investigación web: {', '.join(queries[:2])} ({datetime.now(timezone.utc).strftime('%Y-%m-%d')})",
            "content":   synthesis,
            "metadata": {
                "queries":      queries,
                "sources":      sources,
                "provider":     self._provider.name,
                "indexed_at":   datetime.now(timezone.utc).isoformat(),
                "result_count": len(results),
            },
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    f"{self.bridge_url}/ovd/rag/index",
                    headers={
                        "Authorization": f"Bearer {self.jwt_token}",
                        "Content-Type": "application/json",
                    },
                    json=doc,
                )
                if resp.status_code in (200, 201):
                    log.info("web_researcher: síntesis indexada en RAG org-level (%d chars)", len(synthesis))
                    return 1
                else:
                    log.warning("web_researcher: RAG index falló con status %d", resp.status_code)
        except Exception as e:
            log.warning("web_researcher: error indexando en RAG: %s", e)

        return 0


# ---------------------------------------------------------------------------
# Helper para uso desde graph.py y api.py
# ---------------------------------------------------------------------------

async def run_web_research(
    queries: list[str],
    org_id: str,
    project_id: str | None,
    jwt_token: str,
    bridge_url: str,
    context: str = "",
    model: str | None = None,
    curated_urls: list[str] | None = None,
) -> ResearchFindings:
    """Shortcut para ejecutar WebResearcher sin instanciar la clase."""
    researcher = WebResearcher(
        bridge_url=bridge_url,
        jwt_token=jwt_token,
        org_id=org_id,
        project_id=project_id,
        model=model,
    )
    return await researcher.research(queries=queries, context=context, curated_urls=curated_urls)


async def run_web_research_uncertainties(
    uncertainties: list[dict],
    org_id: str,
    project_id: str | None,
    jwt_token: str,
    bridge_url: str,
    context: str = "",
    curated_urls: list[str] | None = None,
) -> ResearchFindings:
    """Shortcut para investigar incertidumbres (Modo B)."""
    researcher = WebResearcher(
        bridge_url=bridge_url,
        jwt_token=jwt_token,
        org_id=org_id,
        project_id=project_id,
    )
    return await researcher.research_uncertainties(
        uncertainties=uncertainties,
        context=context,
        curated_urls=curated_urls,
    )


async def load_curated_urls(org_id: str, project_id: str | None, db_url: str) -> list[str]:
    """
    Carga las URLs curadas activas para un proyecto desde la DB.
    Retorna lista vacía si no hay URLs o si falla la conexión.
    """
    try:
        import psycopg
        async with await psycopg.AsyncConnection.connect(db_url) as conn:
            rows = await conn.execute(
                """
                SELECT url FROM ovd_web_sources
                WHERE org_id = %s AND project_id = %s AND active = TRUE
                ORDER BY created_at
                """,
                (org_id, project_id),
            )
            records = await rows.fetchall()
        return [r[0] for r in records]
    except Exception as e:
        log.warning("load_curated_urls: error cargando fuentes curadas — %s", e)
        return []
