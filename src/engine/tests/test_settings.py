"""
Tests para settings.py — Fase 3-A plan de mantenibilidad.
Copyright 2026 Omar Robles
"""

import os

import pytest

from settings import OVDSettings, get_settings

_VARS_TO_CLEAR = [
    "DATABASE_URL", "JWT_SECRET", "PORT", "LOG_LEVEL", "OVD_ENGINE_SECRET",
    "OVD_NODE_TIMEOUT_SECS", "OVD_SSE_STREAM_TIMEOUT_SECS", "OVD_LLM_TIMEOUT_SECS",
    "OVD_RAG_ENABLED", "OVD_RAG_TOP_K", "OVD_RAG_MIN_SCORE",
    "OVD_MAX_RETRIES", "OVD_QA_MIN_SCORE", "OVD_SECURITY_MIN_SCORE",
    "OVD_SECURITY_SCAN_ENABLED", "OLLAMA_BASE_URL", "OVD_BRIDGE_URL",
]


def _clean_env(monkeypatch):
    for var in _VARS_TO_CLEAR:
        monkeypatch.delenv(var, raising=False)


class TestOVDSettingsDefaults:
    def test_defaults_database_url(self, monkeypatch):
        _clean_env(monkeypatch)
        s = OVDSettings(_env_file=None)
        assert s.database_url == ""

    def test_defaults_jwt_secret(self, monkeypatch):
        _clean_env(monkeypatch)
        s = OVDSettings(_env_file=None)
        assert s.jwt_secret == ""

    def test_defaults_port(self, monkeypatch):
        _clean_env(monkeypatch)
        s = OVDSettings(_env_file=None)
        assert s.port == 8001

    def test_defaults_log_level(self, monkeypatch):
        _clean_env(monkeypatch)
        s = OVDSettings(_env_file=None)
        assert s.log_level == "info"

    def test_defaults_timeouts(self, monkeypatch):
        _clean_env(monkeypatch)
        s = OVDSettings(_env_file=None)
        assert s.ovd_node_timeout_secs == 120.0
        assert s.ovd_sse_stream_timeout_secs == 900.0
        assert s.ovd_llm_timeout_secs == 300.0

    def test_defaults_rag(self, monkeypatch):
        _clean_env(monkeypatch)
        s = OVDSettings(_env_file=None)
        assert s.ovd_rag_enabled is True
        assert s.ovd_rag_top_k == 5
        assert s.ovd_rag_min_score == 0.65

    def test_defaults_quality(self, monkeypatch):
        _clean_env(monkeypatch)
        s = OVDSettings(_env_file=None)
        assert s.ovd_max_retries == 3
        assert s.ovd_qa_min_score == 70
        assert s.ovd_security_min_score == 0
        assert s.ovd_security_scan_enabled is False

    def test_defaults_ollama(self, monkeypatch):
        _clean_env(monkeypatch)
        s = OVDSettings(_env_file=None)
        assert s.ollama_base_url == "http://localhost:11434"

    def test_defaults_bridge(self, monkeypatch):
        _clean_env(monkeypatch)
        s = OVDSettings(_env_file=None)
        assert s.ovd_bridge_url == "http://localhost:3000"


class TestOVDSettingsEnvOverride:
    def test_env_override_database_url(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")
        s = OVDSettings(_env_file=None)
        assert s.database_url == "postgresql://user:pass@host:5432/db"

    def test_env_override_jwt_secret(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET", "supersecretkey1234567890abcdef12")
        s = OVDSettings(_env_file=None)
        assert s.jwt_secret == "supersecretkey1234567890abcdef12"

    def test_env_override_port(self, monkeypatch):
        monkeypatch.setenv("PORT", "9001")
        s = OVDSettings(_env_file=None)
        assert s.port == 9001

    def test_env_override_bool_rag_enabled_false(self, monkeypatch):
        monkeypatch.setenv("OVD_RAG_ENABLED", "false")
        s = OVDSettings(_env_file=None)
        assert s.ovd_rag_enabled is False

    def test_env_override_bool_rag_enabled_true(self, monkeypatch):
        monkeypatch.setenv("OVD_RAG_ENABLED", "true")
        s = OVDSettings(_env_file=None)
        assert s.ovd_rag_enabled is True

    def test_env_override_float_timeout(self, monkeypatch):
        monkeypatch.setenv("OVD_NODE_TIMEOUT_SECS", "60.5")
        s = OVDSettings(_env_file=None)
        assert s.ovd_node_timeout_secs == 60.5

    def test_env_override_ovd_engine_secret(self, monkeypatch):
        monkeypatch.setenv("OVD_ENGINE_SECRET", "my-secret")
        s = OVDSettings(_env_file=None)
        assert s.ovd_engine_secret == "my-secret"

    def test_env_override_node_env_development(self, monkeypatch):
        monkeypatch.setenv("NODE_ENV", "development")
        s = OVDSettings(_env_file=None)
        assert s.node_env == "development"


class TestGetSettingsSingleton:
    def test_get_settings_returns_instance(self):
        get_settings.cache_clear()
        s = get_settings()
        assert isinstance(s, OVDSettings)

    def test_get_settings_is_singleton(self):
        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_cache_clear_reloads(self, monkeypatch):
        get_settings.cache_clear()
        monkeypatch.setenv("PORT", "7777")
        s1 = OVDSettings(_env_file=None)
        get_settings.cache_clear()
        s2 = OVDSettings(_env_file=None)
        assert s1.port == s2.port
