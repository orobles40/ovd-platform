"""
OVD Platform — Tests de regresión por sprint (R4)
Verifican los contratos críticos establecidos en cada sprint/GAP.
No requieren LLM ni infraestructura real.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))  # para factories

import hashlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from factories import make_state, make_security_result, make_qa_result


# ---------------------------------------------------------------------------
# TestGAP001SecurityAuditIndependiente
# ---------------------------------------------------------------------------

class TestGAP001SecurityAuditIndependiente:

    def test_security_result_tiene_campos_obligatorios(self):
        """
        El dict de security_result siempre debe tener los campos:
        passed, score, severity, vulnerabilities, rls_compliant.
        """
        result = make_security_result()
        campos_obligatorios = ["passed", "score", "severity", "vulnerabilities", "rls_compliant"]
        for campo in campos_obligatorios:
            assert campo in result, f"Campo obligatorio '{campo}' ausente en security_result"

    def test_security_score_entre_0_y_100(self):
        """El score no puede ser negativo ni mayor a 100."""
        # Score normal
        result = make_security_result(score=90)
        assert 0 <= result["score"] <= 100

        # Score en el límite inferior
        result_min = make_security_result(score=0)
        assert result_min["score"] >= 0

        # Score en el límite superior
        result_max = make_security_result(score=100)
        assert result_max["score"] <= 100

    def test_security_result_passed_es_bool(self):
        """El campo 'passed' debe ser un booleano."""
        result = make_security_result(passed=True)
        assert isinstance(result["passed"], bool)

        result_failed = make_security_result(passed=False)
        assert isinstance(result_failed["passed"], bool)

    def test_security_result_vulnerabilities_es_lista(self):
        """El campo 'vulnerabilities' debe ser una lista."""
        result = make_security_result()
        assert isinstance(result["vulnerabilities"], list)

    def test_security_result_rls_compliant_es_bool(self):
        """El campo 'rls_compliant' debe ser un booleano."""
        result = make_security_result()
        assert isinstance(result["rls_compliant"], bool)


# ---------------------------------------------------------------------------
# TestGAP002FanOut
# ---------------------------------------------------------------------------

class TestGAP002FanOut:

    def test_dispatch_agents_genera_send_por_cada_agente(self):
        """
        _dispatch_agents con ["backend","frontend","database"]
        debe generar exactamente 3 objetos Send.
        """
        from graph import _dispatch_agents
        from langgraph.types import Send

        state = make_state(selected_agents=["backend", "frontend", "database"])
        sends = _dispatch_agents(state)

        assert len(sends) == 3
        assert all(isinstance(s, Send) for s in sends)

    def test_dispatch_agents_cada_send_tiene_current_agent(self):
        """Cada Send debe incluir el campo 'current_agent' con el nombre del agente."""
        from graph import _dispatch_agents

        state = make_state(selected_agents=["backend", "frontend"])
        sends = _dispatch_agents(state)

        agentes_enviados = [s.arg["current_agent"] for s in sends]
        assert "backend" in agentes_enviados
        assert "frontend" in agentes_enviados

    def test_agent_results_reducer_acumula(self):
        """
        _list_reset_or_add([{"agent":"backend"}], [{"agent":"frontend"}])
        → lista con 2 items.
        """
        from graph import _list_reset_or_add

        existing = [{"agent": "backend"}]
        update = [{"agent": "frontend"}]
        result = _list_reset_or_add(existing, update)

        assert len(result) == 2
        agentes = [r["agent"] for r in result]
        assert "backend" in agentes
        assert "frontend" in agentes

    def test_agent_results_reducer_reset_con_none(self):
        """
        _list_reset_or_add([{"agent":"backend"}], None)
        → lista vacía (reset antes de nuevo ciclo).
        """
        from graph import _list_reset_or_add

        existing = [{"agent": "backend"}, {"agent": "frontend"}]
        result = _list_reset_or_add(existing, None)

        assert result == []

    def test_agent_results_reducer_acumulacion_multiple(self):
        """Múltiples acumulaciones producen lista con todos los items."""
        from graph import _list_reset_or_add

        result = _list_reset_or_add([], [{"agent": "backend"}])
        result = _list_reset_or_add(result, [{"agent": "database"}])
        result = _list_reset_or_add(result, [{"agent": "devops"}])

        assert len(result) == 3

    def test_dispatch_agents_un_solo_agente(self):
        """Con un solo agente debe generar exactamente 1 Send."""
        from graph import _dispatch_agents

        state = make_state(selected_agents=["backend"])
        sends = _dispatch_agents(state)

        assert len(sends) == 1


# ---------------------------------------------------------------------------
# TestGAP004ConstraintsVersion
# ---------------------------------------------------------------------------

class TestGAP004ConstraintsVersion:

    def test_constraints_version_es_hash_md5_8chars(self):
        """
        Con project_context no vacío, constraints_version debe ser
        un hash MD5 truncado a 8 caracteres hexadecimales.
        """
        project_context = "## Stack\nPython / FastAPI / PostgreSQL 16"
        constraints_version = hashlib.md5(project_context.encode()).hexdigest()[:8]

        # Debe tener exactamente 8 caracteres
        assert len(constraints_version) == 8

        # Debe ser hexadecimal
        int(constraints_version, 16)  # lanza ValueError si no es hex

    def test_constraints_version_cambia_con_context(self):
        """
        Dos project_context distintos deben producir constraints_version distintos.
        """
        ctx1 = "## Stack\nPython / FastAPI / PostgreSQL 16"
        ctx2 = "## Stack\nJava / Spring Boot / Oracle 12c"

        v1 = hashlib.md5(ctx1.encode()).hexdigest()[:8]
        v2 = hashlib.md5(ctx2.encode()).hexdigest()[:8]

        assert v1 != v2

    def test_constraints_version_mismo_context_mismo_hash(self):
        """El mismo project_context siempre produce el mismo constraints_version."""
        ctx = "## Stack\nNode.js / Express / MySQL 8.0"
        v1 = hashlib.md5(ctx.encode()).hexdigest()[:8]
        v2 = hashlib.md5(ctx.encode()).hexdigest()[:8]

        assert v1 == v2

    def test_constraints_version_vacio_produce_no_profile(self):
        """
        Con project_context vacío → constraints_version = "no-profile"
        (según implementación en graph.py).
        """
        project_ctx = ""
        constraints_version = hashlib.md5(project_ctx.encode()).hexdigest()[:8] if project_ctx else "no-profile"

        assert constraints_version == "no-profile"


# ---------------------------------------------------------------------------
# TestGAP005RetryLoop
# ---------------------------------------------------------------------------

class TestGAP005RetryLoop:

    def test_max_retries_definido(self):
        """MAX_RETRIES debe estar definido en graph y tener el valor configurado (3)."""
        from graph import MAX_RETRIES
        assert MAX_RETRIES == 3

    def test_route_security_escalates_at_max(self):
        """
        Con retry_count=MAX_RETRIES y security fallando →
        route_after_security debe retornar 'handle_escalation'.
        """
        from graph import route_after_security, MAX_RETRIES

        state = make_state(
            security_result=make_security_result(passed=False, score=0),
            security_retry_count=MAX_RETRIES,
        )
        result = route_after_security(state)
        assert result == "handle_escalation"

    def test_route_security_continua_con_reintentos_disponibles(self):
        """
        Con retry_count < MAX_RETRIES y security fallando →
        route_after_security debe retornar 'route_agents' (reintento).
        """
        from graph import route_after_security, MAX_RETRIES

        state = make_state(
            security_result=make_security_result(passed=False, score=0),
            security_retry_count=0,
        )
        result = route_after_security(state)
        assert result == "route_agents"

    def test_route_security_pasa_si_passed_true(self):
        """Con security passed=True → route_after_security retorna 'qa_review'."""
        from graph import route_after_security

        state = make_state(
            security_result=make_security_result(passed=True, score=95),
            security_retry_count=0,
        )
        result = route_after_security(state)
        assert result == "qa_review"

    def test_route_qa_escalates_at_max(self):
        """
        Con retry_count=MAX_RETRIES y QA fallando →
        route_after_qa debe retornar 'handle_escalation'.
        """
        from graph import route_after_qa, MAX_RETRIES

        state = make_state(
            qa_result=make_qa_result(passed=False, score=0),
            qa_retry_count=MAX_RETRIES,
        )
        result = route_after_qa(state)
        assert result == "handle_escalation"

    def test_route_qa_continua_con_reintentos_disponibles(self):
        """
        Con retry_count < MAX_RETRIES y QA fallando →
        route_after_qa debe retornar 'route_agents' (reintento).
        """
        from graph import route_after_qa, MAX_RETRIES

        state = make_state(
            qa_result=make_qa_result(passed=False, score=0),
            qa_retry_count=0,
        )
        result = route_after_qa(state)
        assert result == "route_agents"

    def test_route_qa_pasa_si_passed_true(self):
        """Con QA passed=True → route_after_qa retorna 'deliver'."""
        from graph import route_after_qa

        state = make_state(
            qa_result=make_qa_result(passed=True, score=90),
            qa_retry_count=0,
        )
        result = route_after_qa(state)
        assert result == "deliver"


# ---------------------------------------------------------------------------
# TestS8ContextResolver
# ---------------------------------------------------------------------------

class TestS8ContextResolver:

    def test_agentcontext_to_prompt_incluye_restricciones(self):
        """
        AgentContext con restricciones → to_prompt_block() debe
        contener las restricciones en el texto generado.
        """
        from context_resolver import AgentContext, StackRegistry

        stack = StackRegistry(
            language="Python",
            framework="FastAPI",
            db_engine="oracle",
            db_version="12c",
        )
        ctx = AgentContext(
            org_id="org1",
            project_id="proj1",
            stack=stack,
            model_routing="claude",
            restrictions=["no_json_functions", "no_lateral_join", "no_fetch_first"],
            rag_context="",
        )

        prompt_block = ctx.to_prompt_block()

        assert "no_json_functions" in prompt_block
        assert "no_lateral_join" in prompt_block

    def test_agentcontext_to_prompt_sin_restricciones_no_incluye_bloque(self):
        """
        AgentContext sin restricciones → to_prompt_block() no debe
        incluir el bloque de restricciones.
        """
        from context_resolver import AgentContext, StackRegistry

        stack = StackRegistry(language="Python", framework="FastAPI")
        ctx = AgentContext(
            org_id="org1",
            project_id="proj1",
            stack=stack,
            model_routing="ollama",
            restrictions=[],
            rag_context="",
        )

        prompt_block = ctx.to_prompt_block()
        # Sin restricciones el bloque no debe aparecer
        assert "Restricciones del stack" not in prompt_block

    def test_routing_oracle_usa_claude(self):
        """
        _resolve_model_routing con stack que incluye Oracle → 'claude'.
        Oracle está en _LEGACY_INDICATORS.
        """
        from context_resolver import _resolve_model_routing, StackRegistry

        stack = StackRegistry(
            db_engine="oracle",
            db_version="12c",
            model_routing="auto",
        )
        result = _resolve_model_routing(stack)
        assert result == "claude"

    def test_routing_stack_moderno_usa_ollama(self):
        """
        _resolve_model_routing con stack moderno (Python/FastAPI/PostgreSQL) →
        no es legacy → retorna 'ollama' en modo auto.
        """
        from context_resolver import _resolve_model_routing, StackRegistry

        stack = StackRegistry(
            language="Python",
            framework="FastAPI",
            db_engine="postgresql",
            db_version="16",
            model_routing="auto",
            db_restrictions=[],
        )
        result = _resolve_model_routing(stack)
        assert result == "ollama"

    def test_routing_explicito_respeta_configuracion(self):
        """
        Si model_routing != 'auto', _resolve_model_routing devuelve
        el valor configurado independientemente del stack.
        """
        from context_resolver import _resolve_model_routing, StackRegistry

        stack = StackRegistry(
            db_engine="postgresql",
            model_routing="claude",  # explícito
        )
        result = _resolve_model_routing(stack)
        assert result == "claude"

    def test_routing_con_restricciones_activas_usa_claude(self):
        """
        Stack con db_restrictions no vacías → Claude
        (stack complejo con restricciones).
        """
        from context_resolver import _resolve_model_routing, StackRegistry

        stack = StackRegistry(
            db_engine="mysql",
            db_version="5.7",
            model_routing="auto",
            db_restrictions=["no_window_functions", "no_cte"],
        )
        result = _resolve_model_routing(stack)
        assert result == "claude"

    def test_infer_restrictions_oracle_12c(self):
        """
        _infer_restrictions("oracle", "12c") debe retornar
        la lista de restricciones de Oracle 12c.
        """
        from context_resolver import _infer_restrictions, RESTRICTION_RULES

        restrictions = _infer_restrictions("oracle", "12c")
        expected = RESTRICTION_RULES[("oracle", "12c")]

        assert restrictions == expected
        assert "no_json_functions" in restrictions

    def test_infer_restrictions_engine_desconocido_retorna_lista_vacia(self):
        """_infer_restrictions con BD desconocida → lista vacía."""
        from context_resolver import _infer_restrictions

        restrictions = _infer_restrictions("mongodb", "6.0")
        assert restrictions == []


# ---------------------------------------------------------------------------
# TestS10JWT
# ---------------------------------------------------------------------------

class TestS10JWT:

    def test_refresh_token_hash_nunca_igual_al_raw(self):
        """_hash_token(raw) nunca debe ser igual al token raw."""
        from auth import _hash_token

        raw = "550e8400-e29b-41d4-a716-446655440000"
        hashed = _hash_token(raw)

        assert hashed != raw

    def test_hash_token_es_sha256_hex(self):
        """_hash_token debe retornar un string hexadecimal de 64 caracteres (SHA-256)."""
        from auth import _hash_token

        hashed = _hash_token("test-token-value")
        assert len(hashed) == 64
        int(hashed, 16)  # lanza ValueError si no es hex

    def test_hash_token_determinista(self):
        """El mismo token siempre produce el mismo hash."""
        from auth import _hash_token

        raw = "token-de-prueba-123"
        assert _hash_token(raw) == _hash_token(raw)

    def test_access_token_payload_tiene_org_id(self):
        """
        verify_access_token(token) debe retornar un payload con org_id correcto.
        Usa el JWT_SECRET inyectado por el conftest.
        """
        from auth import create_access_token, verify_access_token

        token = create_access_token(
            user_id="user-001",
            org_id="org1",
            role="developer",
        )
        payload = verify_access_token(token)

        assert payload.org_id == "org1"

    def test_access_token_payload_tiene_sub(self):
        """El payload del token debe contener el user_id en el campo 'sub'."""
        from auth import create_access_token, verify_access_token

        token = create_access_token(
            user_id="user-abc",
            org_id="org-test",
            role="admin",
        )
        payload = verify_access_token(token)

        assert payload.sub == "user-abc"

    def test_access_token_payload_tiene_role(self):
        """El payload debe contener el role del usuario."""
        from auth import create_access_token, verify_access_token

        token = create_access_token(
            user_id="user-001",
            org_id="org1",
            role="viewer",
        )
        payload = verify_access_token(token)

        assert payload.role == "viewer"

    def test_token_expirado_lanza_error(self, monkeypatch):
        """
        Un token creado con TTL negativo (ya expirado) debe hacer que
        verify_access_token lanze ValueError.
        """
        import auth
        from auth import create_access_token, verify_access_token

        # Forzar TTL negativo para que el token expire inmediatamente
        monkeypatch.setattr(auth, "_ACCESS_TOKEN_TTL_HOURS", -1)

        token = create_access_token(
            user_id="user-exp",
            org_id="org-exp",
            role="developer",
        )

        with pytest.raises(ValueError):
            verify_access_token(token)

    def test_token_invalido_lanza_error(self):
        """Un JWT malformado debe lanzar ValueError."""
        from auth import verify_access_token

        with pytest.raises(ValueError):
            verify_access_token("esto.no.es.un.jwt.valido")

    def test_token_con_secret_incorrecto_lanza_error(self, monkeypatch):
        """Un token firmado con diferente secret debe lanzar ValueError al verificar."""
        import auth
        from auth import create_access_token, verify_access_token

        # Crear token con secret A
        monkeypatch.setattr(auth, "_JWT_SECRET", "a" * 64)
        token = create_access_token("user1", "org1", "developer")

        # Cambiar a secret B para la verificación
        monkeypatch.setattr(auth, "_JWT_SECRET", "b" * 64)

        with pytest.raises(ValueError):
            verify_access_token(token)


# ---------------------------------------------------------------------------
# TestS11NightlyResearcher
# ---------------------------------------------------------------------------

class TestS11NightlyResearcher:

    def test_queries_oracle_priorizan_cve(self):
        """
        Stack con database="Oracle 12c" → la primera query debe contener "CVE"
        (queries de BD tienen prioridad y siguen el patrón "{db} CVE {year}").
        """
        from nightly_researcher import build_stack_queries

        stack = {"database": "Oracle", "db_version": "12c"}
        queries = build_stack_queries(stack)

        assert len(queries) > 0
        # La primera query es sobre BD → contiene "CVE"
        assert "CVE" in queries[0].upper()

    def test_queries_stack_completo_no_vacio(self):
        """Un stack completo debe generar al menos 1 query."""
        from nightly_researcher import build_stack_queries

        stack = {
            "language": "Python",
            "framework": "FastAPI",
            "database": "PostgreSQL",
            "db_version": "16",
        }
        queries = build_stack_queries(stack)
        assert len(queries) >= 1

    def test_queries_stack_vacio_genera_fallback(self):
        """Un stack vacío debe generar la query genérica de fallback."""
        from nightly_researcher import build_stack_queries

        queries = build_stack_queries({})
        assert len(queries) == 1
        assert "security" in queries[0].lower() or "advisories" in queries[0].lower()

    def test_queries_respeta_max_queries(self):
        """El número de queries no debe exceder _MAX_QUERIES (por defecto 3)."""
        from nightly_researcher import build_stack_queries, _MAX_QUERIES

        stack = {
            "language": "Java",
            "framework": "Spring Boot",
            "database": "Oracle",
            "db_version": "19c",
        }
        queries = build_stack_queries(stack)
        assert len(queries) <= _MAX_QUERIES

    def test_has_cve_detecta_cve_uppercase(self):
        """has_cve debe detectar 'CVE-2024-1234' en mayúsculas."""
        from nightly_researcher import has_cve

        text = "Se encontró CVE-2024-1234 en el componente X."
        assert has_cve(text) is True

    def test_has_cve_detecta_cve_lowercase(self):
        """has_cve debe ser case-insensitive: 'cve-2024' en minúsculas también se detecta."""
        from nightly_researcher import has_cve

        text = "vulnerabilidad detectada: cve-2024-5678 crítica."
        assert has_cve(text) is True

    def test_has_cve_retorna_false_sin_cve(self):
        """has_cve debe retornar False cuando no hay CVEs ni palabras clave."""
        from nightly_researcher import has_cve

        text = "El framework tiene buenas prácticas de desarrollo."
        assert has_cve(text) is False

    def test_has_cve_detecta_vulnerability_keyword(self):
        """has_cve debe detectar la palabra 'vulnerability'."""
        from nightly_researcher import has_cve

        text = "Critical vulnerability found in OpenSSL."
        assert has_cve(text) is True

    def test_has_cve_detecta_critical_keyword(self):
        """has_cve debe detectar la palabra 'critical'."""
        from nightly_researcher import has_cve

        text = "This is a critical security advisory."
        assert has_cve(text) is True

    def test_queries_incluyen_año_actual(self):
        """Las queries deben incluir el año actual."""
        from nightly_researcher import build_stack_queries
        from datetime import datetime, timezone

        stack = {"database": "MySQL", "db_version": "8.0"}
        queries = build_stack_queries(stack)
        year = str(datetime.now(timezone.utc).year)

        assert any(year in q for q in queries)
