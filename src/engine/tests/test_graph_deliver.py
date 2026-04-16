"""
OVD Platform — Tests para el nodo deliver
Sprint: S6+
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))  # para factories

import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from factories import make_state, make_sdd, make_agent_result, make_security_result, make_qa_result
from graph import deliver
from model_router import ResolvedConfig

# deliver llama nats_client.publish_done y AuditLogger.cycle_completed
pytestmark = pytest.mark.usefixtures("mock_nats", "mock_audit_logger")


# ---------------------------------------------------------------------------
# Fixture: ResolvedConfig por defecto (Ollama — sin costo)
# ---------------------------------------------------------------------------

_DEFAULT_RESOLVED = ResolvedConfig(
    provider="ollama",
    model="qwen2.5-coder:7b",
    base_url=None,
    api_key_env=None,
    extra_instructions=None,
    constraints=None,
    code_style=None,
    resolved_from="default",
    temperature=0.0,
)


def _make_deliver_state(**overrides):
    """State mínimo válido para ejecutar deliver."""
    defaults = dict(
        sdd=make_sdd(),
        agent_results=[make_agent_result("backend")],
        security_result=make_security_result(),
        qa_result=make_qa_result(),
        token_usage={"backend": {"input": 100, "output": 200}},
        cycle_start_ts=time.time() - 10.0,
        messages=[],
    )
    defaults.update(overrides)
    return make_state(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deliver_incluye_sdd_como_artefacto():
    """El deliverable de tipo 'sdd' está presente cuando hay sdd en el state."""
    with patch("model_router.resolve", new=AsyncMock(return_value=_DEFAULT_RESOLVED)):
        state = _make_deliver_state()
        result = await deliver(state)

    types = [d["type"] for d in result["deliverables"]]
    assert "sdd" in types, f"Se esperaba 'sdd' en deliverables. Tipos: {types}"
    sdd_artifact = next(d for d in result["deliverables"] if d["type"] == "sdd")
    assert sdd_artifact["agent"] == "architect"


@pytest.mark.asyncio
async def test_deliver_incluye_resultados_agentes():
    """Los resultados de cada agente se incluyen como deliverables de tipo 'implementation'."""
    with patch("model_router.resolve", new=AsyncMock(return_value=_DEFAULT_RESOLVED)):
        state = _make_deliver_state(
            agent_results=[make_agent_result("backend"), make_agent_result("frontend")]
        )
        result = await deliver(state)

    impl_deliverables = [d for d in result["deliverables"] if d["type"] == "implementation"]
    assert len(impl_deliverables) == 2
    agents_in_deliverables = {d["agent"] for d in impl_deliverables}
    assert "backend" in agents_in_deliverables
    assert "frontend" in agents_in_deliverables


@pytest.mark.asyncio
async def test_deliver_retorna_status_done():
    """El nodo finaliza el ciclo con status='done'."""
    with patch("model_router.resolve", new=AsyncMock(return_value=_DEFAULT_RESOLVED)):
        state = _make_deliver_state()
        result = await deliver(state)

    assert result["status"] == "done"


@pytest.mark.asyncio
async def test_deliver_sin_github_pr_vacio():
    """Sin github_token configurado, github_pr permanece vacío (no se modifica en deliver)."""
    with patch("model_router.resolve", new=AsyncMock(return_value=_DEFAULT_RESOLVED)):
        state = _make_deliver_state(github_token="", github_repo="", github_pr={})
        result = await deliver(state)

    # deliver no establece github_pr — eso lo hace create_pr
    # Verificar que deliver no crea un PR donde no debería
    assert "github_pr" not in result or result.get("github_pr") == {}


@pytest.mark.asyncio
async def test_deliver_agrega_mensaje_final():
    """El nodo agrega al menos un mensaje que menciona 'Ciclo completado' o entrega."""
    with patch("model_router.resolve", new=AsyncMock(return_value=_DEFAULT_RESOLVED)):
        state = _make_deliver_state(messages=[])
        result = await deliver(state)

    msgs = result["messages"]
    assert len(msgs) >= 1
    combined = " ".join(m.get("content", "") for m in msgs)
    # El mensaje de deliver menciona "Entrega completada" o variantes
    entrega_keywords = ["Entrega completada", "artefacto", "Ciclo completado"]
    found = any(kw in combined for kw in entrega_keywords)
    assert found, f"El mensaje debería mencionar la entrega. Contenido: {combined[:200]}"


# ---------------------------------------------------------------------------
# OB-02 — YAML frontmatter en informe de entrega
# ---------------------------------------------------------------------------

class TestOB02Frontmatter:
    """OB-02: el informe de entrega incluye YAML frontmatter con metadatos del ciclo."""

    def _call_generate(self, **state_overrides):
        """Llama _generate_delivery_report con un state mínimo y retorna el contenido."""
        import tempfile, os
        from graph import _generate_delivery_report
        from factories import make_state, make_sdd, make_agent_result, make_security_result, make_qa_result

        with tempfile.TemporaryDirectory() as tmpdir:
            state = make_state(
                directory=tmpdir,
                session_id="tui-abc12345-deadbeef",
                feature_request="Implementar login JWT",
                sdd=make_sdd(),
                agent_results=[make_agent_result("backend")],
                security_result=make_security_result(score=85, passed=True),
                qa_result=make_qa_result(score=90, passed=True),
                **state_overrides,
            )
            name = _generate_delivery_report(state, [], 0.01, "1m 30s", 1000, 500, "anthropic")
            if not name:
                return ""
            path = os.path.join(tmpdir, name)
            with open(path) as f:
                return f.read()

    def test_frontmatter_presente(self):
        """El informe empieza con '---' (YAML frontmatter)."""
        content = self._call_generate()
        assert content.startswith("---\n"), f"Falta frontmatter. Inicio: {content[:80]!r}"

    def test_frontmatter_tiene_session_id(self):
        content = self._call_generate()
        assert 'session_id: "tui-abc12345-deadbeef"' in content

    def test_frontmatter_tiene_feature_request(self):
        content = self._call_generate()
        assert "feature_request:" in content
        assert "Implementar login JWT" in content

    def test_frontmatter_tiene_scores(self):
        content = self._call_generate()
        assert "security_score: 85" in content
        assert "qa_score: 90" in content
        assert "security_passed: true" in content
        assert "qa_passed: true" in content

    def test_frontmatter_tiene_provider(self):
        content = self._call_generate()
        assert 'provider: "anthropic"' in content

    def test_frontmatter_cierra_con_separador(self):
        """El frontmatter debe cerrarse con '---' antes del cuerpo del informe."""
        content = self._call_generate()
        lines = content.split("\n")
        # La primera línea es '---', debe haber otra '---' antes del heading '#'
        closing_idx = next((i for i, l in enumerate(lines[1:], 1) if l.strip() == "---"), None)
        assert closing_idx is not None, "Frontmatter no cerrado con '---'"
        heading_idx = next((i for i, l in enumerate(lines) if l.startswith("# ")), None)
        assert heading_idx is not None and heading_idx > closing_idx, "El heading debe ir después del frontmatter"

    def test_cuerpo_intacto_tras_frontmatter(self):
        """El cuerpo del informe (heading '# Informe de Entrega') sigue presente."""
        content = self._call_generate()
        assert "# Informe de Entrega OVD" in content


# ---------------------------------------------------------------------------
# PP-01 — Budget enforcement por ciclo
# ---------------------------------------------------------------------------

class TestPP01Budget:
    """PP-01: agent_executor omite agentes cuando se supera el presupuesto de tokens."""

    @pytest.mark.asyncio
    async def test_sin_budget_agente_no_se_omite(self, monkeypatch):
        """Con OVD_CYCLE_TOKEN_BUDGET=0 (default) nunca se omite ningún agente."""
        import graph as _graph
        monkeypatch.setattr(_graph, "_CYCLE_BUDGET_TOKENS", 0)

        state = make_state(
            current_agent="backend",
            token_usage={"frontend": {"input": 99999, "output": 99999}},
        )
        # No debe retornar skipped — comprobamos que el flag no está en el resultado
        # (el LLM fallará pero no por budget)
        from unittest.mock import AsyncMock, patch
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(
            content="```python:src/app.py\npass\n```",
            response_metadata={},
            usage_metadata={},
        ))
        with patch("model_router.get_llm_with_context", new=AsyncMock(return_value=mock_llm)):
            result = await _graph.agent_executor(state)

        agent_res = result["agent_results"][0]
        assert not agent_res.get("skipped", False), "Sin budget no debe omitirse el agente"

    @pytest.mark.asyncio
    async def test_con_budget_superado_agente_se_omite(self, monkeypatch):
        """Con presupuesto superado, agent_executor retorna resultado 'skipped'."""
        import graph as _graph
        monkeypatch.setattr(_graph, "_CYCLE_BUDGET_TOKENS", 1000)

        state = make_state(
            current_agent="backend",
            # Tokens ya usados superan el budget
            token_usage={"frontend": {"input": 600, "output": 500}},
        )
        result = await _graph.agent_executor(state)

        agent_res = result["agent_results"][0]
        assert agent_res.get("skipped") is True
        assert agent_res["agent"] == "backend"
        assert "presupuesto" in agent_res["output"].lower()

    @pytest.mark.asyncio
    async def test_con_budget_no_superado_agente_se_ejecuta(self, monkeypatch):
        """Con tokens < budget, el agente sí se ejecuta (no se omite)."""
        import graph as _graph
        monkeypatch.setattr(_graph, "_CYCLE_BUDGET_TOKENS", 10000)

        state = make_state(
            current_agent="backend",
            token_usage={"frontend": {"input": 100, "output": 200}},
        )
        from unittest.mock import AsyncMock, patch
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(
            content="```python:src/app.py\npass\n```",
            response_metadata={},
            usage_metadata={},
        ))
        with patch("model_router.get_llm_with_context", new=AsyncMock(return_value=mock_llm)):
            result = await _graph.agent_executor(state)

        agent_res = result["agent_results"][0]
        assert not agent_res.get("skipped", False)

    def test_budget_exactamente_en_limite_se_omite(self, monkeypatch):
        """Cuando tokens_so_far == budget, el agente se omite (límite inclusivo)."""
        import graph as _graph
        monkeypatch.setattr(_graph, "_CYCLE_BUDGET_TOKENS", 500)
        # 300 + 200 = 500 == budget → debe omitirse
        import asyncio
        state = make_state(
            current_agent="database",
            token_usage={"backend": {"input": 300, "output": 200}},
        )
        result = asyncio.get_event_loop().run_until_complete(_graph.agent_executor(state))
        assert result["agent_results"][0].get("skipped") is True
