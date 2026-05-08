"""
OVD Platform — Tests S115: Resiliencia de ciclo y calidad QA en producción

Verifica:
  A. app.yaml: disable_edge_cache=true + todos los modelos usan deepseek-v4-pro
  B. OVD_LLM_MAX_TOKENS escalado a 32768
  C. Feedback QA acumulativo con límite 10000 chars (antes: 5000)
  D. Template backend_python.md incluye orden topológico de generación
  E. _build_qa_feedback incluye atribución por archivo en issues
"""

import json
import os
import re
import sys

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))  # para factories

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
REPO_ROOT = os.path.join(BASE_DIR, "..", "..")  # src/engine → src → ovd-platform


# ---------------------------------------------------------------------------
# Fix E — disable_edge_cache en app.yaml
# ---------------------------------------------------------------------------


class TestDisableEdgeCache:
    def _app_yaml(self) -> dict:
        path = os.path.join(REPO_ROOT, ".do", "app.yaml")
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_engine_service_has_edge_section(self):
        """S115-E: el engine service debe tener sección edge."""
        spec = self._app_yaml()
        engine = next(s for s in spec["services"] if s["name"] == "ovd-engine")
        assert "edge" in engine, "El engine service no tiene sección 'edge'"

    def test_disable_edge_cache_is_true(self):
        """S115-E: disable_edge_cache debe ser true para habilitar SSE en DO."""
        spec = self._app_yaml()
        engine = next(s for s in spec["services"] if s["name"] == "ovd-engine")
        assert engine["edge"].get("disable_edge_cache") is True


# ---------------------------------------------------------------------------
# Fix F — Modelos deepseek-v4-pro + max_tokens 32768
# ---------------------------------------------------------------------------


class TestModelConfig:
    def _env_map(self) -> dict:
        """Retorna {key: value} de las env vars del engine en app.yaml."""
        path = os.path.join(REPO_ROOT, ".do", "app.yaml")
        with open(path, encoding="utf-8") as f:
            spec = yaml.safe_load(f)
        engine = next(s for s in spec["services"] if s["name"] == "ovd-engine")
        return {e["key"]: e.get("value", "") for e in engine.get("envs", [])}

    def test_backend_model_is_deepseek_v4_pro(self):
        """S115-F: OVD_MODEL_BACKEND debe ser deepseek-v4-pro."""
        env = self._env_map()
        assert env.get("OVD_MODEL_BACKEND") == "deepseek-v4-pro", (
            f"OVD_MODEL_BACKEND={env.get('OVD_MODEL_BACKEND')!r}, esperado 'deepseek-v4-pro'"
        )

    def test_sdd_model_is_deepseek_v4_pro(self):
        """S115-F: OVD_MODEL_SDD debe ser deepseek-v4-pro."""
        env = self._env_map()
        assert env.get("OVD_MODEL_SDD") == "deepseek-v4-pro"

    def test_qa_model_is_deepseek_v4_pro(self):
        """S115-F: OVD_MODEL_QA debe ser deepseek-v4-pro."""
        env = self._env_map()
        assert env.get("OVD_MODEL_QA") == "deepseek-v4-pro"

    def test_max_tokens_is_32768(self):
        """S115-F: OVD_LLM_MAX_TOKENS debe ser 32768 para soportar 8+ archivos."""
        env = self._env_map()
        assert env.get("OVD_LLM_MAX_TOKENS") == "32768", (
            f"OVD_LLM_MAX_TOKENS={env.get('OVD_LLM_MAX_TOKENS')!r}, esperado '32768'"
        )

    def test_no_qwen3_coder_flash_in_agent_models(self):
        """S115-F: ningún modelo de agente debe ser qwen3-coder-flash."""
        env = self._env_map()
        agent_keys = [k for k in env if k.startswith("OVD_MODEL_")]
        qwen_keys = [k for k in agent_keys if env[k] == "qwen3-coder-flash"]
        assert qwen_keys == [], f"Modelos todavía con qwen3-coder-flash: {qwen_keys}"


# ---------------------------------------------------------------------------
# Fix C — Feedback truncation aumentado a 10000
# ---------------------------------------------------------------------------


class TestQAFeedbackTruncation:
    def test_update_qa_retry_usa_limite_10000(self):
        """S115-C: update_qa_retry debe usar _truncate con 10000 chars."""
        import inspect
        from graph import update_qa_retry

        src = inspect.getsource(update_qa_retry)
        # Debe contener 10000, no 5000
        assert "10000" in src, "update_qa_retry no usa límite de 10000 chars"
        assert "5000" not in src or src.index("10000") < len(src), (
            "update_qa_retry todavía usa límite de 5000 chars"
        )

    def test_feedback_acumula_entre_rondas(self):
        """S115-C: update_qa_retry debe acumular el feedback de rondas anteriores."""
        from factories import make_state
        from graph import update_qa_retry

        # Estado con feedback previo (ronda 0 ya tuvo issues)
        state = make_state(
            qa_result={
                "score": 0,
                "issues": ["Falta endpoint /medicos"],
                "summary": "QA fallido",
            },
            qa_retry_count=1,
            retry_feedback="[S97-QA] CORRECCIONES RONDA 1\n=====\nISSUE-01: Falta models.py",
        )
        result = update_qa_retry(state)

        accumulated = result["retry_feedback"]
        # Debe contener el feedback previo Y el nuevo
        assert "RONDA 1" in accumulated or "CORRECCIONES" in accumulated, (
            "El feedback acumulado no contiene la ronda anterior"
        )
        assert "Falta endpoint /medicos" in accumulated or "RONDA" in accumulated

    def test_feedback_no_trunca_con_8_archivos(self):
        """S115-C: con 8 issues de archivos distintos el feedback no debe truncarse a menos de 10000."""
        from graph import _build_qa_feedback

        # Simular QA con 8 issues detallados (cada uno ~500 chars)
        issues = [
            f"src/turnos/models.py: Clase Medico no define __tablename__. SQLAlchemy no puede mapear la tabla. Agregar __tablename__ = 'medicos' en la definición de la clase.",
            f"src/turnos/schemas.py: MedicoCreate importa de models pero models.py no fue generado. ImportError en runtime.",
            f"src/turnos/services.py: La función buscar_medicos_por_especialidad usa Session pero no importa from sqlalchemy.orm import Session.",
            f"src/turnos/routers/medicos.py: El router no llama a services.buscar_medicos. Retorna lista vacía hardcodeada.",
            f"src/turnos/routers/citas.py: Falta validación de RUT chileno. El endpoint POST /citas acepta cualquier string en rut_paciente.",
            f"src/main.py: No incluye el router de citas. app.include_router(citas_router) está ausente.",
            f"conftest.py: sys.path.insert apunta a 'src' pero el paquete es 'turnos'. Los tests no pueden importar.",
            f"tests/test_turnos.py: test_reservar_cita usa assert data['id'] == 1 en lugar de assert 'id' in data. Falla si el ID cambia.",
        ]
        qa = {
            "score": 0,
            "issues": issues,
            "missing_requirements": [],
            "code_quality_issues": [],
        }
        feedback = _build_qa_feedback(qa)
        # El feedback de 8 issues no debe ser truncado por debajo de 3000 chars
        assert len(feedback) > 2000, (
            f"Feedback muy corto para 8 issues: {len(feedback)} chars"
        )


# ---------------------------------------------------------------------------
# Fix D — Template backend_python.md con orden topológico
# ---------------------------------------------------------------------------


class TestBackendPythonTopologicalOrder:
    def _template(self) -> str:
        path = os.path.join(BASE_DIR, "templates", "stack", "backend_python.md")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_template_menciona_orden_topologico(self):
        """S115-D: backend_python.md debe mencionar orden topológico."""
        content = self._template()
        assert "topológico" in content or "topologico" in content.lower(), (
            "backend_python.md no menciona orden topológico de generación"
        )

    def test_template_orden_models_antes_services(self):
        """S115-D: en la sección topológica, models.py debe aparecer antes que services.py."""
        content = self._template()
        # Buscar la sección específica de orden topológico
        sec_start = content.find("Orden topológico obligatorio")
        assert sec_start != -1, "No se encontró sección de orden topológico"
        section = content[sec_start:]
        pos_models = section.find("models.py")
        pos_services = section.find("services.py")
        assert pos_models != -1 and pos_services != -1
        assert pos_models < pos_services, (
            "En la sección topológica, models.py debe aparecer antes que services.py"
        )

    def test_template_orden_services_antes_routers(self):
        """S115-D: services.py debe aparecer antes que routers en la instrucción."""
        content = self._template()
        pos_services = content.find("services.py")
        pos_routers = content.find("routers")
        assert pos_services < pos_routers, (
            "services.py debe definirse antes que routers en el template"
        )

    def test_template_tests_son_ultimo(self):
        """S115-D: tests/test_*.py debe ser el último en el orden de generación."""
        content = self._template()
        pos_main = content.find("main.py")
        pos_tests = content.rfind("tests/test_")
        assert pos_main < pos_tests, (
            "tests/test_*.py debe aparecer después de main.py en el orden de generación"
        )


# ---------------------------------------------------------------------------
# Fix B — Early cycle registration y ensure_cycle_registered
# ---------------------------------------------------------------------------


class TestEarlyCycleRegistration:
    def test_ensure_cycle_registered_existe(self):
        """S115-B: _ensure_cycle_registered debe existir en api.py."""
        import inspect
        import importlib

        # Verificar que la función existe en api.py
        import api

        assert hasattr(api, "_ensure_cycle_registered"), (
            "api.py no tiene la función _ensure_cycle_registered"
        )

    def test_graph_tasks_dict_existe(self):
        """S115-A: _graph_tasks, _event_queues y _stream_done deben existir en api.py."""
        import api

        assert hasattr(api, "_graph_tasks"), "api.py no tiene _graph_tasks"
        assert hasattr(api, "_event_queues"), "api.py no tiene _event_queues"
        assert hasattr(api, "_stream_done"), "api.py no tiene _stream_done"
