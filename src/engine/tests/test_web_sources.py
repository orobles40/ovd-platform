"""
S11.H — Tests para fuentes curadas configurables en WebResearcher.

Tests:
  - research() con curated_urls vacío no llama _fetch_curated
  - research() con curated_urls llama _fetch_curated y antepone resultados
  - _fetch_curated retorna SearchResult con url y snippet
  - _fetch_curated ignora URLs con error HTTP
  - _fetch_curated ignora errores de red silenciosamente
  - run_web_research propaga curated_urls al researcher
  - load_curated_urls retorna [] si la DB falla
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from search_providers import SearchResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_researcher(bridge_url="http://bridge", jwt_token="tok", org_id="org1"):
    from web_researcher import WebResearcher
    r = WebResearcher(bridge_url=bridge_url, jwt_token=jwt_token, org_id=org_id)
    return r


# ---------------------------------------------------------------------------
# research() con curated_urls=None no invoca _fetch_curated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_research_no_curated_skips_fetch():
    researcher = _make_researcher()

    fake_results = [SearchResult(title="T", url="https://example.com", snippet="snippet")]
    provider_mock = AsyncMock(return_value=fake_results)
    researcher._provider = MagicMock(search=provider_mock, name="mock")

    with patch.object(researcher, "_fetch_curated", new_callable=AsyncMock) as fetch_mock, \
         patch.object(researcher, "_synthesize", new_callable=AsyncMock, return_value="sintesis"), \
         patch.object(researcher, "_index_to_rag", new_callable=AsyncMock, return_value=1):

        await researcher.research(queries=["query1"], context="ctx", curated_urls=None)

        fetch_mock.assert_not_called()


# ---------------------------------------------------------------------------
# research() con curated_urls llama _fetch_curated y antepone resultados
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_research_with_curated_calls_fetch_and_prepends():
    researcher = _make_researcher()

    curated_result = SearchResult(title="https://docs.oracle.com", url="https://docs.oracle.com", snippet="oracle docs")
    search_result  = SearchResult(title="Search", url="https://search.com", snippet="search result")

    researcher._provider = MagicMock(
        search=AsyncMock(return_value=[search_result]),
        name="mock",
    )

    with patch.object(researcher, "_fetch_curated", new_callable=AsyncMock, return_value=[curated_result]) as fetch_mock, \
         patch.object(researcher, "_synthesize", new_callable=AsyncMock, return_value="sintesis") as synth_mock, \
         patch.object(researcher, "_index_to_rag", new_callable=AsyncMock, return_value=1):

        findings = await researcher.research(
            queries=["oracle vulnerability"],
            context="ctx",
            curated_urls=["https://docs.oracle.com"],
        )

        fetch_mock.assert_called_once_with(["https://docs.oracle.com"])
        # curated va primero en la lista de resultados
        assert findings.results[0].url == "https://docs.oracle.com"
        assert findings.results[1].url == "https://search.com"
        # synthesize recibe todos los resultados combinados
        all_results = synth_mock.call_args[0][1]
        assert len(all_results) == 2


# ---------------------------------------------------------------------------
# _fetch_curated — URL válida retorna SearchResult con snippet
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_curated_returns_search_result():
    researcher = _make_researcher()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html><body><p>Oracle 19c documentation content here</p></body></html>"

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("web_researcher.httpx.AsyncClient", return_value=mock_client):
        results = await researcher._fetch_curated(["https://docs.oracle.com/en/database/oracle/oracle-database/19/"])

    assert len(results) == 1
    assert results[0].url == "https://docs.oracle.com/en/database/oracle/oracle-database/19/"
    assert "Oracle 19c" in results[0].snippet


# ---------------------------------------------------------------------------
# _fetch_curated — HTTP 404 se ignora (retorna lista vacía)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_curated_ignores_http_errors():
    researcher = _make_researcher()

    mock_resp = MagicMock()
    mock_resp.status_code = 404

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("web_researcher.httpx.AsyncClient", return_value=mock_client):
        results = await researcher._fetch_curated(["https://example.com/notfound"])

    assert results == []


# ---------------------------------------------------------------------------
# _fetch_curated — excepción de red se ignora silenciosamente
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_curated_ignores_network_exception():
    researcher = _make_researcher()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=Exception("connection timeout"))

    with patch("web_researcher.httpx.AsyncClient", return_value=mock_client):
        results = await researcher._fetch_curated(["https://unreachable.example.com"])

    assert results == []


# ---------------------------------------------------------------------------
# run_web_research — propaga curated_urls al researcher
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_web_research_passes_curated_urls():
    from web_researcher import run_web_research, ResearchFindings

    fake_findings = ResearchFindings(queries=["q"], results=[], synthesis="ok", indexed=0)

    with patch("web_researcher.WebResearcher.research", new_callable=AsyncMock, return_value=fake_findings) as research_mock:
        await run_web_research(
            queries=["q"],
            org_id="org1",
            project_id="proj1",
            jwt_token="tok",
            bridge_url="http://bridge",
            curated_urls=["https://curated.example.com"],
        )
        _, kwargs = research_mock.call_args
        assert kwargs.get("curated_urls") == ["https://curated.example.com"]


# ---------------------------------------------------------------------------
# load_curated_urls — retorna [] si la DB falla
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_load_curated_urls_returns_empty_on_db_error():
    from web_researcher import load_curated_urls
    import psycopg

    with patch.object(psycopg.AsyncConnection, "connect", side_effect=Exception("db down")):
        result = await load_curated_urls("org1", "proj1", "postgresql://bad-url")

    assert result == []
