"""
OVD Platform — Tests unitarios: reducers de LangGraph
Copyright 2026 Omar Robles

Verifica los reducers puros del grafo: _list_reset_or_add y _merge_token_usage.
No requiere base de datos ni LLM.
"""
import sys
import os

# Agregar src/engine al path para importar el módulo
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from graph import _list_reset_or_add, _merge_token_usage, _extract_uncertainties


class TestListResetOrAdd:
    """Reducer para agent_results (fan-out GAP-002)."""

    def test_none_resetea_lista_existente(self):
        existing = [{"agent": "backend", "output": "code"}]
        result = _list_reset_or_add(existing, None)
        assert result == []

    def test_lista_vacia_sobre_lista_existente_acumula_vacio(self):
        existing = [{"agent": "backend"}]
        result = _list_reset_or_add(existing, [])
        assert result == [{"agent": "backend"}]

    def test_acumula_nuevo_resultado(self):
        existing = [{"agent": "backend", "output": "code1"}]
        new_result = [{"agent": "frontend", "output": "code2"}]
        result = _list_reset_or_add(existing, new_result)
        assert len(result) == 2
        assert result[0]["agent"] == "backend"
        assert result[1]["agent"] == "frontend"

    def test_acumula_multiples_resultados_paralelos(self):
        """Simula tres agent_executors corriendo en paralelo."""
        base = []
        after_backend = _list_reset_or_add(base, [{"agent": "backend"}])
        after_frontend = _list_reset_or_add(after_backend, [{"agent": "frontend"}])
        after_database = _list_reset_or_add(after_frontend, [{"agent": "database"}])
        assert len(after_database) == 3

    def test_none_limpia_lista_con_multiples_elementos(self):
        existing = [{"agent": "a"}, {"agent": "b"}, {"agent": "c"}]
        result = _list_reset_or_add(existing, None)
        assert result == []


class TestMergeTokenUsage:
    """Reducer para token_usage (acumulación en fan-out paralelo)."""

    def test_update_none_devuelve_existente(self):
        existing = {"backend": {"input": 100, "output": 50}}
        result = _merge_token_usage(existing, None)
        assert result == existing

    def test_update_vacio_devuelve_existente(self):
        existing = {"backend": {"input": 100, "output": 50}}
        result = _merge_token_usage(existing, {})
        assert result == existing

    def test_agente_nuevo_se_agrega(self):
        existing = {"backend": {"input": 100, "output": 50}}
        update = {"frontend": {"input": 200, "output": 80}}
        result = _merge_token_usage(existing, update)
        assert "backend" in result
        assert "frontend" in result
        assert result["frontend"]["input"] == 200

    def test_agente_existente_suma_tokens(self):
        """Simula un agente que ejecutó dos veces (reintentos)."""
        existing = {"backend": {"input": 100, "output": 50}}
        update = {"backend": {"input": 200, "output": 100}}
        result = _merge_token_usage(existing, update)
        assert result["backend"]["input"] == 300
        assert result["backend"]["output"] == 150

    def test_acumulacion_fan_out_paralelo(self):
        """Simula 3 agentes corriendo en paralelo, cada uno emite token_usage."""
        base = {}
        after_backend = _merge_token_usage(base, {"backend": {"input": 1000, "output": 500}})
        after_frontend = _merge_token_usage(after_backend, {"frontend": {"input": 800, "output": 400}})
        after_database = _merge_token_usage(after_frontend, {"database": {"input": 600, "output": 300}})

        total_input = sum(v["input"] for v in after_database.values())
        total_output = sum(v["output"] for v in after_database.values())
        assert total_input == 2400
        assert total_output == 1200

    def test_no_muta_el_dict_existente(self):
        """El reducer no debe mutar el estado existente."""
        existing = {"backend": {"input": 100, "output": 50}}
        original_existing = dict(existing)
        _merge_token_usage(existing, {"frontend": {"input": 200, "output": 80}})
        assert existing == original_existing


class TestExtractUncertainties:
    """Parser de incertidumbres en el output de los agentes (GAP-004)."""

    def test_detecta_uncertainty_en_comentario(self):
        output = "const x = 1;\n// UNCERTAINTY: no sé qué índice usar\nconst y = 2;"
        result = _extract_uncertainties(output, "backend")
        assert len(result) == 1
        assert result[0]["agent"] == "backend"
        assert "índice" in result[0]["item"]

    def test_severity_alta_para_palabras_criticas(self):
        output = "// UNCERTAINTY: critical security issue with auth token"
        result = _extract_uncertainties(output, "backend")
        assert result[0]["severity"] == "high"

    def test_severity_media_por_defecto(self):
        output = "// UNCERTAINTY: podría ser necesario revisar el naming"
        result = _extract_uncertainties(output, "frontend")
        assert result[0]["severity"] == "medium"

    def test_sin_uncertainties_devuelve_lista_vacia(self):
        output = "const x = authMiddleware();\nconst y = db.query();"
        result = _extract_uncertainties(output, "backend")
        assert result == []

    def test_multiples_uncertainties(self):
        output = (
            "// UNCERTAINTY: primer punto desconocido\n"
            "const x = 1;\n"
            "// UNCERTAINTY: segundo punto desconocido\n"
        )
        result = _extract_uncertainties(output, "database")
        assert len(result) == 2
        assert all(r["agent"] == "database" for r in result)
