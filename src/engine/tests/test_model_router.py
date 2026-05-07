"""
OVD Platform — Tests para model_router.py
Unit tests: sin LLM real, sin API del Bridge real.

Cubre:
  - S98-B: _ROLE_MODEL_OVERRIDES — override de modelo por rol específico
  - ResolvedConfig dataclass
  - _apply_stack_routing: lógica de override según stack_routing
  - _cache_key / invalidate_cache
  - _resolve_temperature por role y provider
  - _warn_if_small_model
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch

import pytest

from model_router import (
    _ROLE_MODEL_OVERRIDES,
    ResolvedConfig,
    _apply_stack_routing,
    _cache,
    _cache_key,
    _resolve_temperature,
    _warn_if_small_model,
    invalidate_cache,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_config(
    provider="ollama",
    model="qwen2.5-coder:7b",
    resolved_from="default",
    temperature=0.0,
    constraints=None,
) -> ResolvedConfig:
    return ResolvedConfig(
        provider=provider,
        model=model,
        base_url=None,
        api_key_env=None,
        extra_instructions=None,
        constraints=constraints,
        code_style=None,
        resolved_from=resolved_from,
        temperature=temperature,
    )


# ---------------------------------------------------------------------------
# TestResolvedConfig
# ---------------------------------------------------------------------------


class TestResolvedConfig:
    def test_config_defaults(self):
        """ResolvedConfig con valores mínimos: resolved_from=default, temperature=0.0."""
        cfg = ResolvedConfig(
            provider="ollama",
            model="qwen2.5-coder:7b",
            base_url=None,
            api_key_env=None,
            extra_instructions=None,
            constraints=None,
            code_style=None,
            resolved_from="default",
        )
        assert cfg.resolved_from == "default"
        assert cfg.temperature == 0.0
        assert cfg.provider == "ollama"
        assert cfg.model == "qwen2.5-coder:7b"

    def test_config_campos_opcionales_son_none(self):
        """Los campos opcionales deben poder ser None sin error."""
        cfg = make_config()
        assert cfg.base_url is None
        assert cfg.api_key_env is None
        assert cfg.extra_instructions is None
        assert cfg.constraints is None
        assert cfg.code_style is None


# ---------------------------------------------------------------------------
# TestApplyStackRouting
# ---------------------------------------------------------------------------


class TestApplyStackRouting:
    def test_auto_retorna_config_sin_cambios(self):
        """stack_routing='auto' → la función retorna la misma config sin modificar."""
        cfg = make_config(provider="ollama")
        result = _apply_stack_routing(cfg, "auto")
        assert result.provider == "ollama"
        assert result.resolved_from == "default"

    def test_claude_explicito_cambia_provider(self):
        """stack_routing='claude' → provider cambia a 'claude'."""
        cfg = make_config(provider="ollama", resolved_from="default")
        result = _apply_stack_routing(cfg, "claude")
        assert result.provider == "claude"

    def test_claude_explicito_resolved_from_stack_registry(self):
        """stack_routing='claude' → resolved_from contiene 'stack_registry'."""
        cfg = make_config(provider="ollama", resolved_from="default")
        result = _apply_stack_routing(cfg, "claude")
        assert "stack_registry" in result.resolved_from

    def test_ollama_explicito_mantiene_ollama(self):
        """stack_routing='ollama' → provider permanece 'ollama'."""
        cfg = make_config(provider="claude", resolved_from="default")
        result = _apply_stack_routing(cfg, "ollama")
        assert result.provider == "ollama"

    def test_openai_explicito_cambia_provider(self):
        """stack_routing='openai' → provider cambia a 'openai'."""
        cfg = make_config(provider="ollama", resolved_from="default")
        result = _apply_stack_routing(cfg, "openai")
        assert result.provider == "openai"

    def test_provider_ya_configurado_por_bridge_no_se_sobrescribe(self):
        """
        Si el Bridge ya configuró el mismo provider y resolved_from != 'default',
        _apply_stack_routing respeta la config del Bridge (no-op).
        """
        cfg = make_config(provider="claude", resolved_from="project")
        result = _apply_stack_routing(cfg, "claude")
        # Debe devolver la misma config (no sobrescribir model/base_url del Bridge)
        assert result.provider == "claude"
        assert result.resolved_from == "project"

    def test_stack_routing_desconocido_retorna_config_sin_cambios(self):
        """Un stack_routing no reconocido debe retornar la config original."""
        cfg = make_config(provider="ollama")
        result = _apply_stack_routing(cfg, "unknown_routing")
        assert result.provider == "ollama"

    def test_retorna_resolved_config(self):
        """_apply_stack_routing siempre retorna una instancia de ResolvedConfig."""
        cfg = make_config(provider="ollama", resolved_from="default")
        result = _apply_stack_routing(cfg, "claude")
        assert isinstance(result, ResolvedConfig)

    def test_auto_con_provider_ollama_no_cambia(self):
        """
        stack_routing='auto' con provider='ollama':
        el provider no debe cambiar (auto = sin override).
        """
        cfg = make_config(provider="ollama")
        result = _apply_stack_routing(cfg, "auto")
        assert result.provider == "ollama"


# ---------------------------------------------------------------------------
# TestCache
# ---------------------------------------------------------------------------


class TestCache:
    def setup_method(self):
        """Limpiar el cache antes de cada test."""
        _cache.clear()

    def teardown_method(self):
        """Limpiar el cache después de cada test."""
        _cache.clear()

    def test_cache_key_formato(self):
        """_cache_key genera la clave en formato org_id:project_id:agent_role."""
        key = _cache_key("org1", "proj1", "backend")
        assert key == "org1:proj1:backend"

    def test_cache_key_separador_dos_puntos(self):
        """El separador del cache key debe ser ':'."""
        key = _cache_key("mi-org", "mi-proyecto", "qa")
        assert key == "mi-org:mi-proyecto:qa"

    def test_invalidate_cache_por_org(self):
        """
        Poblar cache con 2 keys de org1 y 1 de org2.
        Invalidar org1 → solo quedan keys de org2.
        """
        cfg = make_config()
        _cache["org1:proj1:backend"] = cfg
        _cache["org1:proj1:frontend"] = cfg
        _cache["org2:proj1:backend"] = cfg

        invalidate_cache("org1")

        remaining = list(_cache.keys())
        assert "org1:proj1:backend" not in remaining
        assert "org1:proj1:frontend" not in remaining
        assert "org2:proj1:backend" in remaining

    def test_invalidate_cache_total(self):
        """invalidate_cache() sin org_id limpia todo el cache."""
        cfg = make_config()
        _cache["org1:proj1:backend"] = cfg
        _cache["org2:proj1:backend"] = cfg
        _cache["org3:proj1:qa"] = cfg

        invalidate_cache()

        assert len(_cache) == 0

    def test_invalidate_cache_org_inexistente_no_falla(self):
        """Invalidar un org_id que no tiene keys en cache no debe lanzar excepción."""
        _cache["org1:proj1:backend"] = make_config()
        # No debe lanzar excepción
        invalidate_cache("org_que_no_existe")
        assert "org1:proj1:backend" in _cache

    def test_invalidate_cache_vacio_no_falla(self):
        """invalidate_cache() con cache vacío no debe lanzar excepción."""
        assert len(_cache) == 0
        invalidate_cache()  # sin org_id
        invalidate_cache("org1")  # con org_id inexistente
        assert len(_cache) == 0


# ---------------------------------------------------------------------------
# TestResolveTemperature
# ---------------------------------------------------------------------------


class TestResolveTemperature:
    def test_qa_ollama_tiene_temperature_cero(self):
        """role='qa' con provider='ollama' → temperature=0.0 (structured role)."""
        temp = _resolve_temperature("qa", "ollama")
        assert temp == 0.0

    def test_qa_claude_tiene_temperature_structured(self):
        """role='qa' con provider='claude' → temperature=ovd_llm_temperature_structured (S115: configurable)."""
        from settings import get_settings

        temp = _resolve_temperature("qa", "claude")
        assert temp == get_settings().ovd_llm_temperature_structured

    def test_backend_ollama_tiene_temperature_cero(self):
        """role='backend' con provider='ollama' → temperature=0.0 (S104-A: structured role)."""
        temp = _resolve_temperature("backend", "ollama")
        assert temp == 0.0

    def test_backend_claude_tiene_temperatura_structured(self):
        """role='backend' con provider='claude' → temperature=ovd_llm_temperature_structured (S115: configurable)."""
        from settings import get_settings

        temp = _resolve_temperature("backend", "claude")
        assert temp == get_settings().ovd_llm_temperature_structured

    def test_analyzer_es_structured_role(self):
        """role='analyzer' → temperatura structured (igual a backend, ambos son structured desde S104-A)."""
        temp_structured = _resolve_temperature("analyzer", "ollama")
        temp_backend = _resolve_temperature("backend", "ollama")
        assert temp_structured == temp_backend == 0.0

    def test_security_es_structured_role(self):
        """role='security' → temperatura structured."""
        temp = _resolve_temperature("security", "ollama")
        assert temp == 0.0

    def test_sdd_es_structured_role(self):
        """role='sdd' → temperatura structured."""
        temp = _resolve_temperature("sdd", "ollama")
        assert temp == 0.0

    def test_provider_openai_igual_a_ollama(self):
        """provider='openai' sigue la misma lógica que 'ollama' (no Claude)."""
        temp_openai = _resolve_temperature("qa", "openai")
        temp_ollama = _resolve_temperature("qa", "ollama")
        assert temp_openai == temp_ollama


# ---------------------------------------------------------------------------
# TestWarnIfSmallModel
# ---------------------------------------------------------------------------


class TestWarnIfSmallModel:
    def test_modelo_grande_no_emite_warning(self, caplog):
        """Un modelo 7b+ no debe emitir warning."""
        import logging

        with caplog.at_level(logging.WARNING):
            _warn_if_small_model("qwen2.5-coder:7b", "backend")
        # No debe haber warnings de small model en este caso
        small_warnings = [
            r
            for r in caplog.records
            if "pequeño" in r.message.lower()
            or "7b" in r.message.lower()
            or "menos de" in r.message.lower()
        ]
        assert len(small_warnings) == 0

    def test_modelo_3b_emite_warning(self, caplog):
        """Un modelo 3b debe emitir warning."""
        import logging

        with caplog.at_level(logging.WARNING):
            _warn_if_small_model("llama:3b", "qa")
        assert len(caplog.records) > 0


# ---------------------------------------------------------------------------
# TestRoleModelOverrides — S98-B
# ---------------------------------------------------------------------------


class TestRoleModelOverrides:
    """
    Verifica el dict _ROLE_MODEL_OVERRIDES que permite asignar modelos distintos
    por rol (OVD_MODEL_DEVOPS, OVD_MODEL_BACKEND, etc.) sin afectar otros roles.
    """

    def test_role_overrides_dict_exists(self):
        """_ROLE_MODEL_OVERRIDES debe existir y ser un dict."""
        assert isinstance(_ROLE_MODEL_OVERRIDES, dict)

    def test_role_overrides_only_contains_known_roles(self):
        """El dict solo puede contener roles del fan-out de agentes."""
        valid_roles = {"backend", "database", "devops", "frontend"}
        for role in _ROLE_MODEL_OVERRIDES:
            assert role in valid_roles, (
                f"Rol inesperado en _ROLE_MODEL_OVERRIDES: {role}"
            )

    def test_role_overrides_values_are_non_empty_strings(self):
        """Los valores del dict deben ser strings no vacíos (los vacíos se excluyen al construir)."""
        for role, model in _ROLE_MODEL_OVERRIDES.items():
            assert isinstance(model, str), f"Modelo para {role} debe ser str"
            assert model.strip(), f"Modelo para {role} no debe ser vacío"

    def test_override_logic_uses_role_model_when_set(self):
        """
        Simula la lógica de resolve(): si hay override para el rol, se usa ese modelo;
        si no hay, se usa _AGENT_MODEL.
        """
        import model_router as mr

        # Parchear _ROLE_MODEL_OVERRIDES con un valor de prueba
        original = mr._ROLE_MODEL_OVERRIDES.copy()
        try:
            mr._ROLE_MODEL_OVERRIDES["devops"] = "qwen2.5-coder:7b"
            # Replicar la lógica de resolve() para agent_role en _AGENT_ROLES
            agent_role = "devops"
            model = mr._ROLE_MODEL_OVERRIDES.get(agent_role) or mr._AGENT_MODEL
            assert model == "qwen2.5-coder:7b"
        finally:
            mr._ROLE_MODEL_OVERRIDES.clear()
            mr._ROLE_MODEL_OVERRIDES.update(original)

    def test_override_logic_falls_back_to_agent_model_when_not_set(self):
        """Si no hay override para el rol, se usa _AGENT_MODEL."""
        import model_router as mr

        original = mr._ROLE_MODEL_OVERRIDES.copy()
        try:
            mr._ROLE_MODEL_OVERRIDES.pop("devops", None)
            agent_role = "devops"
            model = mr._ROLE_MODEL_OVERRIDES.get(agent_role) or mr._AGENT_MODEL
            assert model == mr._AGENT_MODEL
        finally:
            mr._ROLE_MODEL_OVERRIDES.clear()
            mr._ROLE_MODEL_OVERRIDES.update(original)

    def test_override_for_devops_does_not_affect_backend(self):
        """Override de devops no debe afectar al rol backend."""
        import model_router as mr

        original = mr._ROLE_MODEL_OVERRIDES.copy()
        try:
            mr._ROLE_MODEL_OVERRIDES["devops"] = "qwen2.5-coder:7b"
            mr._ROLE_MODEL_OVERRIDES.pop("backend", None)

            devops_model = mr._ROLE_MODEL_OVERRIDES.get("devops") or mr._AGENT_MODEL
            backend_model = mr._ROLE_MODEL_OVERRIDES.get("backend") or mr._AGENT_MODEL

            assert devops_model == "qwen2.5-coder:7b"
            assert backend_model == mr._AGENT_MODEL
            assert (
                devops_model != backend_model or mr._AGENT_MODEL == "qwen2.5-coder:7b"
            )
        finally:
            mr._ROLE_MODEL_OVERRIDES.clear()
            mr._ROLE_MODEL_OVERRIDES.update(original)

    def test_settings_fields_exist_for_all_overrideable_roles(self):
        """OVDSettings debe tener campos para los 4 roles overrideables."""
        from settings import OVDSettings

        s = OVDSettings()
        assert hasattr(s, "ovd_model_backend")
        assert hasattr(s, "ovd_model_database")
        assert hasattr(s, "ovd_model_devops")
        assert hasattr(s, "ovd_model_frontend")
