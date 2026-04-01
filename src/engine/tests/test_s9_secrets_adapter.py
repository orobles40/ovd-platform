"""
OVD Platform — Tests: Secrets Adapter (Sprint 9)
No requiere Infisical real — usa EnvAdapter.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
import pytest
from secrets_adapter import EnvAdapter, get_adapter, reset_adapter


def _run(coro):
    """Helper para ejecutar coroutines en tests síncronos."""
    return asyncio.run(coro)


class TestEnvAdapter:
    def setup_method(self):
        reset_adapter()

    def test_is_available_siempre_true(self):
        adapter = EnvAdapter()
        assert adapter.is_available() is True

    def test_get_secrets_devuelve_vars_del_entorno(self, monkeypatch):
        monkeypatch.setenv("OVD_SECRET_MYWORKSPACE_DB_PASSWORD", "secret123")
        monkeypatch.setenv("OVD_SECRET_MYWORKSPACE_API_KEY", "key456")
        adapter = EnvAdapter()
        secrets = _run(adapter.get_secrets("myworkspace"))
        assert secrets.get("DB_PASSWORD") == "secret123"
        assert secrets.get("API_KEY") == "key456"

    def test_get_secrets_workspace_sin_vars_devuelve_dict_vacio(self):
        adapter = EnvAdapter()
        secrets = _run(adapter.get_secrets("workspace_inexistente_xyz"))
        assert secrets == {}

    def test_prefijo_case_insensitive_normalizado(self, monkeypatch):
        monkeypatch.setenv("OVD_SECRET_PROD_MY_KEY", "valor")
        adapter = EnvAdapter()
        secrets = _run(adapter.get_secrets("PROD"))
        assert "MY_KEY" in secrets

    def test_no_incluye_vars_de_otro_workspace(self, monkeypatch):
        monkeypatch.setenv("OVD_SECRET_WS1_KEY", "ws1_value")
        monkeypatch.setenv("OVD_SECRET_WS2_KEY", "ws2_value")
        adapter = EnvAdapter()
        secrets_ws1 = _run(adapter.get_secrets("WS1"))
        assert "KEY" in secrets_ws1
        assert "ws2_value" not in secrets_ws1.values()


class TestGetAdapter:
    def setup_method(self):
        reset_adapter()

    def test_sin_infisical_devuelve_env_adapter(self, monkeypatch):
        monkeypatch.delenv("INFISICAL_URL", raising=False)
        monkeypatch.delenv("INFISICAL_TOKEN", raising=False)
        adapter = get_adapter()
        assert isinstance(adapter, EnvAdapter)

    def test_singleton_devuelve_misma_instancia(self, monkeypatch):
        monkeypatch.delenv("INFISICAL_URL", raising=False)
        a1 = get_adapter()
        a2 = get_adapter()
        assert a1 is a2
