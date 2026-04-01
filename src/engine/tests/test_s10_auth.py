"""
OVD Platform — Tests: JWT auth + refresh tokens (Sprint 10)
No requiere BD — usa mocks para las operaciones de DB.
"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import AsyncMock, patch
from auth import (
    create_access_token, verify_access_token,
    _hash_token,
)

# JWT_SECRET mínimo para tests (32 chars)
_TEST_SECRET = "a" * 64


@pytest.fixture(autouse=True)
def set_jwt_secret(monkeypatch):
    import auth
    monkeypatch.setattr(auth, "_JWT_SECRET", _TEST_SECRET)


class TestAccessToken:
    def test_crear_y_verificar_token(self):
        token = create_access_token("user1", "org1", "dev")
        payload = verify_access_token(token)
        assert payload.sub == "user1"
        assert payload.org_id == "org1"
        assert payload.role == "dev"

    def test_token_invalido_lanza_error(self):
        with pytest.raises(ValueError):
            verify_access_token("token.invalido.xxx")

    def test_token_manipulado_lanza_error(self):
        token = create_access_token("user1", "org1", "dev")
        # Corromper la firma
        partes = token.split(".")
        partes[2] = "firmafalsa"
        with pytest.raises(ValueError):
            verify_access_token(".".join(partes))

    def test_token_incluye_exp(self):
        token = create_access_token("user1", "org1", "admin")
        payload = verify_access_token(token)
        assert payload.exp > time.time()

    def test_roles_distintos_generan_tokens_distintos(self):
        t1 = create_access_token("user1", "org1", "dev")
        t2 = create_access_token("user1", "org1", "admin")
        assert t1 != t2

    def test_orgs_distintas_generan_tokens_distintos(self):
        t1 = create_access_token("user1", "org1", "dev")
        t2 = create_access_token("user1", "org2", "dev")
        p1 = verify_access_token(t1)
        p2 = verify_access_token(t2)
        assert p1.org_id != p2.org_id


class TestHashToken:
    def test_hash_determinista(self):
        raw = "mi-token-secreto"
        assert _hash_token(raw) == _hash_token(raw)

    def test_hash_diferente_para_tokens_distintos(self):
        assert _hash_token("token1") != _hash_token("token2")

    def test_hash_es_hex_64_chars(self):
        h = _hash_token("cualquier-valor")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)
