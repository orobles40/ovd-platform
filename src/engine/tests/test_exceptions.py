"""
Tests para exceptions.py — Fase 3-C plan de mantenibilidad.
Copyright 2026 Omar Robles
"""

import pytest

from exceptions import (
    OVDAgentError,
    OVDCircuitOpenError,
    OVDConfigError,
    OVDCycleError,
    OVDError,
    OVDNotFoundError,
    OVDTokenError,
    OVDValidationError,
)


class TestJerarquia:
    def test_todas_heredan_de_ovd_error(self):
        assert issubclass(OVDConfigError, OVDError)
        assert issubclass(OVDCycleError, OVDError)
        assert issubclass(OVDAgentError, OVDError)
        assert issubclass(OVDValidationError, OVDError)
        assert issubclass(OVDTokenError, OVDError)
        assert issubclass(OVDNotFoundError, OVDError)
        assert issubclass(OVDCircuitOpenError, OVDError)

    def test_agent_error_hereda_de_cycle_error(self):
        assert issubclass(OVDAgentError, OVDCycleError)

    def test_ovd_error_hereda_de_exception(self):
        assert issubclass(OVDError, Exception)

    def test_catch_generico_con_ovd_error(self):
        with pytest.raises(OVDError):
            raise OVDConfigError("DATABASE_URL no configurada")

    def test_catch_generico_captura_subclases(self):
        instancias = [
            OVDConfigError("test"),
            OVDCycleError("test"),
            OVDAgentError("nodo", "test"),
            OVDValidationError("test"),
            OVDTokenError("test"),
            OVDNotFoundError("test"),
            OVDCircuitOpenError("test"),
        ]
        capturadas = []
        for exc in instancias:
            try:
                raise exc
            except OVDError:
                capturadas.append(type(exc).__name__)
        assert len(capturadas) == 7


class TestOVDConfigError:
    def test_mensaje(self):
        exc = OVDConfigError("JWT_SECRET muy corto")
        assert "JWT_SECRET" in str(exc)

    def test_es_catcheable_como_ovd_error(self):
        with pytest.raises(OVDError):
            raise OVDConfigError("falta DATABASE_URL")


class TestOVDTokenError:
    def test_mensaje_token_expirado(self):
        exc = OVDTokenError("Token expirado")
        assert "expirado" in str(exc)

    def test_no_es_value_error(self):
        assert not issubclass(OVDTokenError, ValueError)

    def test_catch_especifico(self):
        with pytest.raises(OVDTokenError):
            raise OVDTokenError("Refresh token revocado")


class TestOVDAgentError:
    def test_formato_mensaje_incluye_agente(self):
        exc = OVDAgentError("generate_sdd", "timeout después de 600s")
        assert "generate_sdd" in str(exc)
        assert "timeout" in str(exc)

    def test_atributo_agent_name(self):
        exc = OVDAgentError("qa_review", "score insuficiente")
        assert exc.agent_name == "qa_review"

    def test_es_catcheable_como_cycle_error(self):
        with pytest.raises(OVDCycleError):
            raise OVDAgentError("security_audit", "fallo crítico")


class TestOVDCircuitOpenError:
    def test_alias_en_model_router(self):
        from model_router import CircuitOpenError

        assert CircuitOpenError is OVDCircuitOpenError

    def test_catch_como_ovd_error(self):
        with pytest.raises(OVDError):
            raise OVDCircuitOpenError("ollama circuit abierto")
