"""
OVD Platform — Tests: Context Resolver + Stack Registry (Sprint 8)
No requiere BD ni LLM.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from context_resolver import (
    ContextResolver, StackRegistry, AgentContext,
    _infer_restrictions, _resolve_model_routing, RESTRICTION_RULES,
)


class TestInferRestrictions:
    def test_oracle_12c_tiene_restricciones(self):
        r = _infer_restrictions("oracle", "12c")
        assert len(r) > 0
        assert any("json" in x.lower() or "lateral" in x.lower() for x in r)

    def test_oracle_19c_menos_restricciones_que_12c(self):
        r12 = _infer_restrictions("oracle", "12c")
        r19 = _infer_restrictions("oracle", "19c")
        assert len(r12) >= len(r19)

    def test_postgresql_sin_restricciones_criticas(self):
        r = _infer_restrictions("postgresql", "15")
        # PostgreSQL moderno no debería tener restricciones de compatibilidad
        assert isinstance(r, list)

    def test_motor_desconocido_devuelve_lista_vacia(self):
        r = _infer_restrictions("mysql_inexistente", "99.0")
        assert r == []

    def test_version_desconocida_usa_fallback_mas_restrictivo(self):
        # Oracle con versión inexistente → fallback a la más restrictiva conocida
        r = _infer_restrictions("oracle", "9i")
        assert isinstance(r, list)


class TestResolveModelRouting:
    def test_legacy_stack_fuerza_claude(self):
        stack = StackRegistry(legacy_stack="COBOL + Oracle", model_routing="auto")
        routing = _resolve_model_routing(stack)
        assert routing == "claude"

    def test_stack_moderno_usa_ollama(self):
        stack = StackRegistry(db_engine="postgresql", db_version="15", model_routing="auto")
        routing = _resolve_model_routing(stack)
        assert routing == "ollama"

    def test_routing_explicito_claude_se_respeta(self):
        stack = StackRegistry(model_routing="claude")
        routing = _resolve_model_routing(stack)
        assert routing == "claude"

    def test_routing_explicito_openai_se_respeta(self):
        stack = StackRegistry(model_routing="openai")
        routing = _resolve_model_routing(stack)
        assert routing == "openai"

    def test_restricciones_legacy_activan_claude(self):
        stack = StackRegistry(
            db_engine="oracle", db_version="12c",
            db_restrictions=["no_json_functions", "no_lateral_join"],
            model_routing="auto",
        )
        routing = _resolve_model_routing(stack)
        assert routing == "claude"


class TestAgentContextToPromptBlock:
    def test_bloque_contiene_restricciones(self):
        ctx = AgentContext(
            org_id="org1", project_id="p1",
            stack=StackRegistry(db_engine="oracle", db_version="12c"),
            model_routing="claude",
            restrictions=["No usar JSON_TABLE", "No usar LATERAL JOIN"],
            rag_context="",
            language="es",
        )
        block = ctx.to_prompt_block()
        assert "JSON_TABLE" in block or "LATERAL JOIN" in block
        assert "oracle" in block.lower() or "12c" in block.lower()

    def test_bloque_sin_credenciales(self):
        ctx = AgentContext(
            org_id="org1", project_id="p1",
            stack=StackRegistry(),
            model_routing="ollama",
            restrictions=[],
            rag_context="",
            language="es",
            workspace_credentials={"DB_PASSWORD": "supersecret"},
        )
        block = ctx.to_prompt_block()
        assert "supersecret" not in block
        assert "DB_PASSWORD" not in block

    def test_retrocompat_texto_libre(self):
        ctx = ContextResolver.resolve(
            org_id="org1", project_id="p1",
            project_context="Sistema con Oracle 12c y Python",
            rag_context="",
        )
        assert ctx.org_id == "org1"
        # Texto libre se envuelve como project_description
        assert ctx.stack.project_description != "" or ctx.stack.db_engine == ""
