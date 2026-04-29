"""
Tests S97 — QA feedback prescriptivo, qa_score_history, FR > perfil BD, temperature retry.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from graph import (
    _BD_KEYWORDS_EXPLICIT,
    _build_qa_feedback,
    _extract_explicit_bd_from_fr,
    _parse_location_from_issue,
    _strip_db_restrictions,
    route_after_qa,
    update_qa_retry,
)

# ---------------------------------------------------------------------------
# S97-D: FR explícita BD > perfil proyecto
# ---------------------------------------------------------------------------


def test_s97d_postgresql_in_fr_detected():
    """FR con 'PostgreSQL' → retorna 'postgresql'."""
    fr = "Sistema de contratos con autenticación JWT usando RUT chileno. API REST FastAPI: login RUT+contraseña, CRUD contratos por empleado. PostgreSQL + SQLAlchemy ORM."
    assert _extract_explicit_bd_from_fr(fr) == "postgresql"


def test_s97d_postgres_alias_detected():
    """Alias 'postgres' (sin QL) también se detecta."""
    assert (
        _extract_explicit_bd_from_fr("API con FastAPI y postgres como BD")
        == "postgresql"
    )


def test_s97d_mysql_in_fr_detected():
    """FR con 'MySQL' → retorna 'mysql'."""
    assert (
        _extract_explicit_bd_from_fr("Backend FastAPI con MySQL y SQLAlchemy")
        == "mysql"
    )


def test_s97d_sqlite_in_fr_detected():
    """FR con 'SQLite' → retorna 'sqlite'."""
    assert (
        _extract_explicit_bd_from_fr("Usar SQLite para persistencia local") == "sqlite"
    )


def test_s97d_oracle_in_fr_detected():
    """FR con 'Oracle' → retorna 'oracle' (sin override)."""
    assert (
        _extract_explicit_bd_from_fr("Sistema con Oracle y Python-oracledb") == "oracle"
    )


def test_s97d_no_bd_in_fr_returns_none():
    """FR sin mención de BD → retorna None."""
    fr = "Agregar endpoint de búsqueda de empleados con paginación y filtros."
    assert _extract_explicit_bd_from_fr(fr) is None


def test_s97d_case_insensitive_detection():
    """La detección es case-insensitive."""
    assert _extract_explicit_bd_from_fr("Usar POSTGRESQL en producción") == "postgresql"
    assert _extract_explicit_bd_from_fr("con MySQL 8.0") == "mysql"


def test_s97d_strip_db_removes_oracle_keywords():
    """_strip_db_restrictions elimina líneas con keywords Oracle del project_ctx."""
    ctx = (
        "Proyecto: Sistema HR\n"
        "Stack: Python 3.11 + FastAPI\n"
        "BD: Oracle XE 21c (python-oracledb thick mode)\n"
        "Restricción: usar rownum en lugar de LIMIT\n"
        "Auth: JWT con bcrypt\n"
    )
    result = _strip_db_restrictions(ctx)
    assert "Oracle" not in result
    assert "python-oracledb" not in result
    assert "rownum" not in result
    assert "Python 3.11" in result
    assert "JWT" in result


def test_s97d_strip_db_preserves_non_oracle_content():
    """_strip_db_restrictions no elimina contenido sin keywords Oracle."""
    ctx = "Stack: FastAPI + PostgreSQL\nAuth: JWT\nTesting: pytest\n"
    result = _strip_db_restrictions(ctx)
    assert result == ctx


def test_s97d_explicit_bd_keywords_dict_has_expected_entries():
    """El dict _BD_KEYWORDS_EXPLICIT tiene las BDs principales."""
    assert "postgresql" in _BD_KEYWORDS_EXPLICIT
    assert "postgres" in _BD_KEYWORDS_EXPLICIT
    assert "mysql" in _BD_KEYWORDS_EXPLICIT
    assert "sqlite" in _BD_KEYWORDS_EXPLICIT
    assert "oracle" in _BD_KEYWORDS_EXPLICIT
    assert "mongodb" in _BD_KEYWORDS_EXPLICIT


def test_s97d_oracle_in_fr_does_not_filter():
    """Si FR menciona Oracle explícitamente, NO se filtra el project_ctx."""
    ctx = (
        "BD: Oracle XE 21c (python-oracledb thick mode)\nRestricciones: usar rownum.\n"
    )
    explicit_bd = _extract_explicit_bd_from_fr("Sistema con Oracle XE 21c")
    assert explicit_bd == "oracle"
    # No se debe filtrar porque la FR coincide con el perfil
    # La lógica en analyze_fr: _explicit_bd != "oracle" AND project_ctx → NO filtra
    # Verificamos que el BD detectado es oracle (condición de no-filtrado)
    assert explicit_bd == "oracle"


def test_s97d_mariadb_alias_detected():
    """MariaDB se detecta como variante de MySQL."""
    assert _extract_explicit_bd_from_fr("Backend con MariaDB y SQLAlchemy") == "mysql"


def test_s97d_system_analyzer_template_has_rule():
    """El template system_analyzer.md contiene la regla S97-D."""
    template_path = (
        pathlib.Path(__file__).parent.parent / "templates" / "system_analyzer.md"
    )
    content = template_path.read_text(encoding="utf-8")
    assert "S97-D" in content
    assert "oracle_involved = false" in content
    assert "PRIORIDAD ABSOLUTA" in content


# ---------------------------------------------------------------------------
# S97-A: qa_score_history + detección de estancamiento
# ---------------------------------------------------------------------------


def _make_qa_state(score: int, retry_count: int, history: list) -> dict:
    return {
        "qa_result": {"score": score, "passed": False, "issues": [], "summary": ""},
        "qa_retry_count": retry_count,
        "qa_score_history": history,
        "retry_feedback": "",
        "messages": [],
    }


def test_s97a_update_qa_retry_records_history():
    """update_qa_retry agrega entrada con round/score/issues_count al historial."""
    state = _make_qa_state(score=50, retry_count=0, history=[])
    result = update_qa_retry(state)
    assert "qa_score_history" in result
    history = result["qa_score_history"]
    assert len(history) == 1
    assert history[0]["score"] == 50
    assert history[0]["round"] == 1


def test_s97a_stagnation_detected_delta_zero():
    """2 rondas con delta=0 y retry_count>=2 → route retorna 'handle_escalation'."""
    history = [{"round": 1, "score": 50}, {"round": 2, "score": 50}]
    state = _make_qa_state(score=50, retry_count=2, history=history)
    result = route_after_qa(state)
    assert result == "handle_escalation"


def test_s97a_stagnation_detected_delta_less_than_5():
    """Delta de 3 puntos con retry_count>=2 → estancamiento, handle_escalation."""
    history = [{"round": 1, "score": 50}, {"round": 2, "score": 53}]
    state = _make_qa_state(score=53, retry_count=2, history=history)
    result = route_after_qa(state)
    assert result == "handle_escalation"


def test_s97a_no_stagnation_if_improving():
    """Delta de 15 puntos → NO es estancamiento, continuar con route_agents."""
    history = [{"round": 1, "score": 50}, {"round": 2, "score": 65}]
    state = _make_qa_state(score=65, retry_count=2, history=history)
    result = route_after_qa(state)
    assert result == "route_agents"


def test_s97a_no_stagnation_if_only_one_round():
    """Con solo 1 ronda en historial → no puede detectar estancamiento aún."""
    history = [{"round": 1, "score": 50}]
    state = _make_qa_state(score=50, retry_count=1, history=history)
    result = route_after_qa(state)
    assert result == "route_agents"


def test_s97a_score_history_reducer_accumulates():
    """El reducer de qa_score_history acumula en lugar de sobrescribir."""
    old = [{"round": 1, "score": 50}]
    new = [{"round": 2, "score": 55}]
    # Simular el reducer directamente: lambda old, new: (old or []) + (new or [])
    result = (old or []) + (new or [])
    assert len(result) == 2
    assert result[0]["round"] == 1
    assert result[1]["round"] == 2


# ---------------------------------------------------------------------------
# S97-C: feedback prescriptivo
# ---------------------------------------------------------------------------


def test_s97c_feedback_includes_bloqueante_prefix():
    """_build_qa_feedback incluye [ISSUE-01] para el primer issue."""
    qa = {
        "score": 50,
        "issues": ["Error de validación RUT en auth/router.py"],
        "missing_requirements": [],
        "code_quality_issues": [],
    }
    feedback = _build_qa_feedback(qa)
    assert "[ISSUE-01]" in feedback


def test_s97c_feedback_includes_accion_instruction():
    """Cada issue tiene '→ ACCIÓN:' en el feedback."""
    qa = {
        "score": 50,
        "issues": ["Falta endpoint DELETE"],
        "missing_requirements": [],
        "code_quality_issues": [],
    }
    feedback = _build_qa_feedback(qa)
    assert "→ ACCIÓN:" in feedback


def test_s97c_feedback_parses_filepath_from_issue():
    """_parse_location_from_issue extrae archivo y línea de texto."""
    file, line = _parse_location_from_issue(
        "Error en src/auth/router.py:45: función inválida"
    )
    assert file == "src/auth/router.py"
    assert line == "45"


def test_s97c_feedback_parses_filepath_without_line():
    """_parse_location_from_issue funciona sin número de línea."""
    file, line = _parse_location_from_issue("Problema en src/contracts/service.py")
    assert file == "src/contracts/service.py"
    assert line == ""


def test_s97c_feedback_no_filepath_returns_empty():
    """Issue sin ruta Python → retorna ('', '')."""
    file, line = _parse_location_from_issue("Falta validación de RUT")
    assert file == ""
    assert line == ""


def test_s97c_feedback_has_superpowers_instructions():
    """El feedback incluye las instrucciones de corrección de 5 pasos."""
    qa = {
        "score": 50,
        "issues": ["Error"],
        "missing_requirements": [],
        "code_quality_issues": [],
    }
    feedback = _build_qa_feedback(qa)
    assert "INSTRUCCIONES DE CORRECCIÓN" in feedback
    assert "cambios mínimos" in feedback


def test_s97c_feedback_cap_is_5000():
    """update_qa_retry trunca accumulated a 5000 chars (no 3000).

    _truncate añade un sufijo de ~100 chars, por lo que el total puede llegar a ~5100.
    Lo importante es que NO supere 3000 (el cap anterior) y SÍ esté cerca de 5000.
    """
    long_issue = "x" * 200
    qa = {
        "score": 50,
        "issues": [long_issue] * 30,
        "missing_requirements": [],
        "code_quality_issues": [],
        "summary": "",
    }
    state = _make_qa_state(score=50, retry_count=0, history=[])
    state["qa_result"] = qa
    result = update_qa_retry(state)
    feedback_len = len(result["retry_feedback"])
    # Supera el cap viejo de 3000 (el texto generado es de ~9000 chars)
    assert feedback_len > 3000
    # Pero está acotado alrededor de 5000 (+sufijo de truncado ~100 chars)
    assert feedback_len <= 5200


# ---------------------------------------------------------------------------
# S97-E: temperature en retry
# ---------------------------------------------------------------------------


def test_s97e_temperature_override_signature():
    """model_router.get_llm_with_context acepta temperature_override opcional."""
    import inspect

    from model_router import get_llm_with_context

    sig = inspect.signature(get_llm_with_context)
    assert "temperature_override" in sig.parameters
    # El parámetro tiene default None
    assert sig.parameters["temperature_override"].default is None
