"""
OVD Platform — Proveedores de búsqueda web (Sprint 11 — S11.A)
Copyright 2026 Omar Robles

Abstracción sobre motores de búsqueda web para el Web Researcher Agent.

Proveedores disponibles:
  - DuckDuckGo (default): gratis, sin API key, usando duckduckgo-search
  - Tavily: mejor calidad, requiere TAVILY_API_KEY
  - SearXNG: self-hosted, requiere OVD_SEARXNG_URL

Configuración:
  OVD_WEB_SEARCH_PROVIDER=duckduckgo|tavily|searxng  (default: duckduckgo)
  TAVILY_API_KEY=tvly-...                              (solo para Tavily)
  OVD_SEARXNG_URL=http://searxng:8080                 (solo para SearXNG)
"""
from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

log = logging.getLogger("ovd.search")


# ---------------------------------------------------------------------------
# Resultado de búsqueda normalizado
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    score: float = 0.0          # relevancia 0.0–1.0 (si el provider lo devuelve)
    published_date: str = ""    # ISO date si está disponible


# ---------------------------------------------------------------------------
# Interfaz abstracta
# ---------------------------------------------------------------------------

class SearchProvider(ABC):
    """Interfaz base para proveedores de búsqueda web."""

    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        """Busca y devuelve resultados normalizados."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre del proveedor para logging."""

    def is_available(self) -> bool:
        """True si el proveedor está configurado y disponible."""
        return True


# ---------------------------------------------------------------------------
# DuckDuckGo (default — gratis, sin API key)
# ---------------------------------------------------------------------------

class DuckDuckGoProvider(SearchProvider):
    """
    Proveedor DuckDuckGo usando duckduckgo-search (ya en pyproject.toml).
    Sin límites conocidos para uso moderado. Sin API key requerida.
    """

    @property
    def name(self) -> str:
        return "duckduckgo"

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        try:
            from duckduckgo_search import AsyncDDGS
        except ImportError:
            log.error("duckduckgo-search no instalado. Ejecutar: uv add duckduckgo-search")
            return []

        results: list[SearchResult] = []
        try:
            async with AsyncDDGS() as ddgs:
                async for r in ddgs.atext(query, max_results=max_results):
                    results.append(SearchResult(
                        title=r.get("title", ""),
                        url=r.get("href", ""),
                        snippet=r.get("body", ""),
                    ))
        except Exception as e:
            log.warning("DuckDuckGo search error para '%s': %s", query[:60], e)
        return results


# ---------------------------------------------------------------------------
# Tavily (alta calidad, requiere API key)
# ---------------------------------------------------------------------------

class TavilyProvider(SearchProvider):
    """
    Proveedor Tavily — mejor relevancia que DuckDuckGo, diseñado para LLMs.
    Requiere TAVILY_API_KEY.
    """

    def __init__(self) -> None:
        self._api_key = os.environ.get("TAVILY_API_KEY", "")

    @property
    def name(self) -> str:
        return "tavily"

    def is_available(self) -> bool:
        return bool(self._api_key)

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        if not self._api_key:
            log.error("TAVILY_API_KEY no configurada")
            return []

        import httpx
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self._api_key,
                        "query": query,
                        "max_results": max_results,
                        "search_depth": "basic",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            log.warning("Tavily search error para '%s': %s", query[:60], e)
            return []

        results = []
        for r in data.get("results", []):
            results.append(SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("content", ""),
                score=r.get("score", 0.0),
                published_date=r.get("published_date", ""),
            ))
        return results


# ---------------------------------------------------------------------------
# SearXNG (self-hosted, sin límites)
# ---------------------------------------------------------------------------

class SearXNGProvider(SearchProvider):
    """
    Proveedor SearXNG self-hosted.
    Requiere OVD_SEARXNG_URL (ej: http://searxng:8080).
    """

    def __init__(self) -> None:
        self._base_url = os.environ.get("OVD_SEARXNG_URL", "").rstrip("/")

    @property
    def name(self) -> str:
        return "searxng"

    def is_available(self) -> bool:
        return bool(self._base_url)

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        if not self._base_url:
            log.error("OVD_SEARXNG_URL no configurada")
            return []

        import httpx
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self._base_url}/search",
                    params={"q": query, "format": "json", "pageno": 1},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            log.warning("SearXNG search error para '%s': %s", query[:60], e)
            return []

        results = []
        for r in data.get("results", [])[:max_results]:
            results.append(SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("content", ""),
                score=r.get("score", 0.0),
                published_date=r.get("publishedDate", ""),
            ))
        return results


# ---------------------------------------------------------------------------
# Factory singleton
# ---------------------------------------------------------------------------

_provider_instance: SearchProvider | None = None


def get_provider() -> SearchProvider:
    """
    Devuelve el proveedor configurado según OVD_WEB_SEARCH_PROVIDER.
    Singleton — reutilizado entre llamadas.

    Orden de fallback si el proveedor configurado no está disponible:
      tavily → duckduckgo (si TAVILY_API_KEY no existe)
      searxng → duckduckgo (si OVD_SEARXNG_URL no existe)
    """
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    provider_name = os.environ.get("OVD_WEB_SEARCH_PROVIDER", "duckduckgo").lower()

    candidates: list[SearchProvider] = []
    if provider_name == "tavily":
        candidates = [TavilyProvider(), DuckDuckGoProvider()]
    elif provider_name == "searxng":
        candidates = [SearXNGProvider(), DuckDuckGoProvider()]
    else:
        candidates = [DuckDuckGoProvider()]

    for candidate in candidates:
        if candidate.is_available():
            _provider_instance = candidate
            log.info("search_providers: usando %s", candidate.name)
            return _provider_instance

    # Fallback final
    _provider_instance = DuckDuckGoProvider()
    return _provider_instance


def reset_provider() -> None:
    """Resetea el singleton (para tests)."""
    global _provider_instance
    _provider_instance = None
