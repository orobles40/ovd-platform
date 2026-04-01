"""
OVD Platform — Tests: Telemetría OTEL (Sprint 10)
No requiere OTEL Collector real.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from telemetry import setup_telemetry, get_tracer, get_trace_id, cycle_span, _get_parent_context


class TestSetupTelemetry:
    def test_setup_es_idempotente(self):
        setup_telemetry()
        setup_telemetry()  # segunda llamada no debe fallar
        tracer = get_tracer()
        assert tracer is not None

    def test_get_tracer_sin_setup_previo_no_falla(self):
        # Aunque no se haya llamado setup, get_tracer() inicializa solo
        tracer = get_tracer()
        assert tracer is not None


class TestGetTraceId:
    def test_cycle_span_genera_trace_id_valido(self):
        setup_telemetry()
        with cycle_span("thread-1", "org1", "proj1", "Feature request test") as span:
            tid = get_trace_id(span)
        # trace_id es string hex de 32 chars o vacío (si OTEL no está activo)
        assert isinstance(tid, str)
        if tid:
            assert len(tid) == 32
            assert all(c in "0123456789abcdef" for c in tid)

    def test_get_trace_id_con_span_invalido_devuelve_vacio(self):
        from opentelemetry.trace import NonRecordingSpan, INVALID_SPAN_CONTEXT
        span = NonRecordingSpan(INVALID_SPAN_CONTEXT)
        tid = get_trace_id(span)
        assert tid == ""


class TestGetParentContext:
    def test_trace_id_invalido_devuelve_none(self):
        assert _get_parent_context("") is None
        assert _get_parent_context("corto") is None
        assert _get_parent_context("gg" * 16) is None  # no hex

    def test_trace_id_valido_devuelve_contexto(self):
        valid_hex = "a" * 32
        ctx = _get_parent_context(valid_hex)
        assert ctx is not None


class TestRecordHelpers:
    def test_record_token_usage_no_falla(self):
        from telemetry import record_token_usage
        setup_telemetry()
        with cycle_span("t1", "org1", "p1", "fr") as span:
            record_token_usage(span, {"backend": {"input": 100, "output": 50}})

    def test_record_qa_result_no_falla(self):
        from telemetry import record_qa_result
        setup_telemetry()
        with cycle_span("t2", "org1", "p1", "fr") as span:
            record_qa_result(span, {"passed": True, "score": 90, "issues": []})

    def test_record_security_result_no_falla(self):
        from telemetry import record_security_result
        setup_telemetry()
        with cycle_span("t3", "org1", "p1", "fr") as span:
            record_security_result(span, {"passed": True, "score": 95, "severity": "none", "vulnerabilities": []})
