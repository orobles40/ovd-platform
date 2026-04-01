"""
OVD Platform — Tests: Search Providers (Sprint 11)
No requiere conexión real a internet.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, AsyncMock
from search_providers import (
    DuckDuckGoProvider, TavilyProvider, SearXNGProvider,
    SearchResult, get_provider, reset_provider,
)


class TestSearchResult:
    def test_campos_minimos(self):
        r = SearchResult(title="Título", url="https://example.com", snippet="Descripción")
        assert r.title == "Título"
        assert r.score == 0.0
        assert r.published_date == ""


class TestDuckDuckGoProvider:
    def test_name(self):
        assert DuckDuckGoProvider().name == "duckduckgo"

    def test_is_available_siempre_true(self):
        assert DuckDuckGoProvider().is_available() is True

    @pytest.mark.asyncio
    async def test_search_retorna_lista_vacia_si_ddg_no_instalado(self):
        provider = DuckDuckGoProvider()
        with patch.dict("sys.modules", {"duckduckgo_search": None}):
            results = await provider.search("test query")
            assert isinstance(results, list)


class TestTavilyProvider:
    def test_name(self):
        assert TavilyProvider().name == "tavily"

    def test_no_disponible_sin_api_key(self, monkeypatch):
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        provider = TavilyProvider()
        assert provider.is_available() is False

    def test_disponible_con_api_key(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "tvly-test123")
        provider = TavilyProvider()
        assert provider.is_available() is True

    @pytest.mark.asyncio
    async def test_search_sin_api_key_devuelve_vacio(self, monkeypatch):
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        provider = TavilyProvider()
        results = await provider.search("test")
        assert results == []


class TestSearXNGProvider:
    def test_name(self):
        assert SearXNGProvider().name == "searxng"

    def test_no_disponible_sin_url(self, monkeypatch):
        monkeypatch.delenv("OVD_SEARXNG_URL", raising=False)
        assert SearXNGProvider().is_available() is False

    def test_disponible_con_url(self, monkeypatch):
        monkeypatch.setenv("OVD_SEARXNG_URL", "http://searxng:8080")
        assert SearXNGProvider().is_available() is True


class TestGetProvider:
    def setup_method(self):
        reset_provider()

    def teardown_method(self):
        reset_provider()

    def test_default_es_duckduckgo(self, monkeypatch):
        monkeypatch.delenv("OVD_WEB_SEARCH_PROVIDER", raising=False)
        provider = get_provider()
        assert provider.name == "duckduckgo"

    def test_tavily_sin_key_hace_fallback_a_duckduckgo(self, monkeypatch):
        monkeypatch.setenv("OVD_WEB_SEARCH_PROVIDER", "tavily")
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        provider = get_provider()
        assert provider.name == "duckduckgo"

    def test_searxng_sin_url_hace_fallback_a_duckduckgo(self, monkeypatch):
        monkeypatch.setenv("OVD_WEB_SEARCH_PROVIDER", "searxng")
        monkeypatch.delenv("OVD_SEARXNG_URL", raising=False)
        provider = get_provider()
        assert provider.name == "duckduckgo"

    def test_singleton_devuelve_misma_instancia(self, monkeypatch):
        monkeypatch.delenv("OVD_WEB_SEARCH_PROVIDER", raising=False)
        p1 = get_provider()
        p2 = get_provider()
        assert p1 is p2
