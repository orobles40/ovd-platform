"""
OVD Platform — Tests unitarios: startup_check
Copyright 2026 Omar Robles

Verifica que assert_env() y check_env() fallen correctamente cuando
faltan variables críticas del Engine.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from startup_check import check_env


def valid_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-testkey")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/test")
    monkeypatch.setenv("NATS_URL", "nats://localhost:4222")


class TestCheckEnv:
    def test_pasa_con_variables_validas(self, monkeypatch):
        valid_env(monkeypatch)
        result = check_env()
        assert result.ok is True
        assert len(result.errors) == 0

    def test_falla_sin_anthropic_api_key(self, monkeypatch):
        valid_env(monkeypatch)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        result = check_env()
        assert result.ok is False
        assert any("ANTHROPIC_API_KEY" in e for e in result.errors)

    def test_falla_si_api_key_no_tiene_prefijo_correcto(self, monkeypatch):
        valid_env(monkeypatch)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "openai-sk-wrong")
        result = check_env()
        assert result.ok is False
        assert any("ANTHROPIC_API_KEY" in e for e in result.errors)

    def test_falla_sin_database_url(self, monkeypatch):
        valid_env(monkeypatch)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        result = check_env()
        assert result.ok is False
        assert any("DATABASE_URL" in e for e in result.errors)

    def test_falla_si_database_url_no_es_postgresql(self, monkeypatch):
        valid_env(monkeypatch)
        monkeypatch.setenv("DATABASE_URL", "mysql://user:pass@localhost/db")
        result = check_env()
        assert result.ok is False

    def test_nats_url_ausente_produce_advertencia_no_error(self, monkeypatch):
        """NATS_URL es opcional — su ausencia genera warning, no error."""
        valid_env(monkeypatch)
        monkeypatch.delenv("NATS_URL", raising=False)
        result = check_env()
        assert result.ok is True   # no error, sigue funcionando sin NATS
        assert any("NATS_URL" in w for w in result.warnings)

    def test_devuelve_multiples_errores(self, monkeypatch):
        """Sin DATABASE_URL y sin ningún provider LLM se generan ≥ 2 errores críticos."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("NATS_URL", raising=False)
        result = check_env()
        assert result.ok is False
        assert len(result.errors) >= 2

    def test_langsmith_sin_api_key_produce_advertencia(self, monkeypatch):
        valid_env(monkeypatch)
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
        result = check_env()
        assert any("LANGCHAIN_API_KEY" in w for w in result.warnings)

    def test_sin_provider_llm_produce_error(self, monkeypatch):
        """Sin ningún provider LLM configurado (Anthropic/Ollama/OpenAI) debe fallar."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/test")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        result = check_env()
        assert result.ok is False
        assert any("provider" in e.lower() or "LLM" in e for e in result.errors)
