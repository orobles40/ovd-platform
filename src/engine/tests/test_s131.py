"""Tests S131 — Retry overwrite semántics + deduplicate modules + alias map ES/EN.

S131-A: _write_artifacts solo protege output VACÍO (eliminada protección <50%).
S131-B: preamble de retry incluye lista de archivos objetivo (ARCHIVOS A SOBRESCRIBIR).
S131-C: deduplicate_module_files elimina copias en rutas no canónicas.
S131-D: _build_service_alias_map cubre patrones español→inglés e inglés→español.
S131-E: _run_agent_with_tools genera debug_frontend_*.txt cuando frontend entrega 0 artefactos.
"""

import pathlib
import sys
import tempfile

import pytest

_ENGINE_DIR = pathlib.Path(".")
sys.path.insert(0, str(_ENGINE_DIR))

_GRAPH_SRC = (_ENGINE_DIR / "graph.py").read_text(encoding="utf-8")
_POSTPROCESSOR_SRC = (_ENGINE_DIR / "code_postprocessor.py").read_text(encoding="utf-8")


# ── S131-A: _write_artifacts — eliminar protección <50% ─────────────────────


def test_s131a_write_artifacts_no_50_percent_guard():
    """graph.py no debe contener la rama de protección <50% original de S55-B."""
    assert "new_size < existing_size // 2" not in _GRAPH_SRC


def test_s131a_write_artifacts_protects_empty_output():
    """_write_artifacts sigue protegiendo el caso de output VACÍO (new_size == 0)."""
    assert "new_size == 0" in _GRAPH_SRC


def test_s131a_write_artifacts_overwrites_smaller_file():
    """Verificar que preserve_nonempty permite sobreescribir si new_size > 0."""
    from graph import _write_artifacts

    with tempfile.TemporaryDirectory() as tmpdir:
        target = pathlib.Path(tmpdir) / "src" / "services.py"
        target.parent.mkdir(parents=True)
        original_content = "x" * 500
        target.write_text(original_content, encoding="utf-8")

        # Contenido válido pero más pequeño (40% del original — antes bloqueado por S55-B)
        smaller_content = "x" * 200
        code_block = f"```python:src/services.py\n{smaller_content}\n```"

        result = _write_artifacts(
            code_block,
            tmpdir,
            "backend",
            preserve_nonempty=True,  # simula retry round
        )
        assert any("services.py" in a.get("path", "") for a in result), (
            "El archivo debería sobreescribirse incluso siendo <50% del original"
        )
        assert target.read_text(encoding="utf-8").strip() == smaller_content


def test_s131a_write_artifacts_preserves_when_empty():
    """_write_artifacts preserva el archivo existente cuando el nuevo contenido es vacío."""
    from graph import _write_artifacts

    with tempfile.TemporaryDirectory() as tmpdir:
        target = pathlib.Path(tmpdir) / "src" / "models.py"
        target.parent.mkdir(parents=True)
        target.write_text("class TurnoORM: pass", encoding="utf-8")

        code_block = "```python:src/models.py\n\n```"  # vacío

        result = _write_artifacts(
            code_block,
            tmpdir,
            "backend",
            preserve_nonempty=True,
        )
        # El archivo original debe mantenerse
        assert "class TurnoORM: pass" in target.read_text(encoding="utf-8")


# ── S131-B: preamble retry con ARCHIVOS A SOBRESCRIBIR ──────────────────────


def test_s131b_retry_preamble_injects_file_targets():
    """graph.py debe tener la lógica S131-B de ARCHIVOS A SOBRESCRIBIR en el preamble."""
    assert "ARCHIVOS A SOBRESCRIBIR" in _GRAPH_SRC


def test_s131b_retry_preamble_uses_agent_tasks_files():
    """El bloque de archivos objetivo se construye a partir de agent_tasks."""
    assert "_agent_file_targets" in _GRAPH_SRC


def test_s131b_retry_preamble_only_in_retry_rounds():
    """El preamble S131-B solo se activa cuando _qa_retry_round > 0."""
    # Verificar que la condición de retry round está antes de la inyección
    idx_condition = _GRAPH_SRC.find("_qa_retry_round > 0 and retry_feedback")
    idx_files_block = _GRAPH_SRC.find("ARCHIVOS A SOBRESCRIBIR")
    assert idx_condition < idx_files_block, (
        "La condición de retry debe preceder al bloque de archivos"
    )


# ── S131-C: deduplicate_module_files ─────────────────────────────────────────


def test_s131c_deduplicate_removes_stray_copy():
    """deduplicate_module_files elimina copia en ruta no canónica cuando la canónica existe."""
    from code_postprocessor import deduplicate_module_files

    with tempfile.TemporaryDirectory() as tmpdir:
        base = pathlib.Path(tmpdir)
        # Canónico según SDD: src/turnos/services.py
        canonical = base / "src" / "turnos" / "services.py"
        canonical.parent.mkdir(parents=True)
        canonical.write_text("def crear_turno(): pass\n", encoding="utf-8")
        # Copia en ruta incorrecta
        stray = base / "src" / "services.py"
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_text("def crear_turno(): pass\n", encoding="utf-8")

        sdd_tasks = [{"file": "src/turnos/services.py", "agent": "backend"}]
        removed = deduplicate_module_files(tmpdir, sdd_tasks)

        assert not stray.exists(), "La copia en src/services.py debería eliminarse"
        assert canonical.exists(), "El archivo canónico debe preservarse"
        assert len(removed) == 1


def test_s131c_deduplicate_preserves_when_no_canonical():
    """deduplicate_module_files no elimina nada si ningún archivo coincide con el SDD."""
    from code_postprocessor import deduplicate_module_files

    with tempfile.TemporaryDirectory() as tmpdir:
        base = pathlib.Path(tmpdir)
        only_file = base / "src" / "services.py"
        only_file.parent.mkdir(parents=True)
        only_file.write_text("def fn(): pass\n", encoding="utf-8")

        sdd_tasks = [{"file": "src/turnos/services.py", "agent": "backend"}]
        removed = deduplicate_module_files(tmpdir, sdd_tasks)

        assert only_file.exists(), "No debe eliminarse si la canónica no existe"
        assert removed == []


def test_s131c_deduplicate_ignores_test_files():
    """deduplicate_module_files no toca archivos con 'test' en el nombre."""
    from code_postprocessor import deduplicate_module_files

    with tempfile.TemporaryDirectory() as tmpdir:
        base = pathlib.Path(tmpdir)
        canonical = base / "src" / "turnos" / "services.py"
        canonical.parent.mkdir(parents=True)
        canonical.write_text("def fn(): pass\n", encoding="utf-8")
        # test_services.py no debe tocarse
        test_file = base / "src" / "test_services.py"
        test_file.write_text("def test_fn(): pass\n", encoding="utf-8")

        sdd_tasks = [{"file": "src/turnos/services.py", "agent": "backend"}]
        deduplicate_module_files(tmpdir, sdd_tasks)

        assert test_file.exists(), "Los archivos de test no deben eliminarse"


# ── S131-D: _build_service_alias_map con patrones ES/EN ──────────────────────


def test_s131d_spanish_verb_patterns_defined():
    """code_postprocessor.py debe definir _ES_EN_VERB_PATTERNS con patrones españoles."""
    assert "_ES_EN_VERB_PATTERNS" in _POSTPROCESSOR_SRC
    assert '"crear_"' in _POSTPROCESSOR_SRC
    assert '"obtener_"' in _POSTPROCESSOR_SRC
    assert '"eliminar_"' in _POSTPROCESSOR_SRC


def test_s131d_alias_map_crear_to_create():
    """Si services.py define crear_turno, el mapa debe mapear create_turno → crear_turno."""
    from code_postprocessor import _build_service_alias_map

    defined = {"crear_turno", "obtener_turno", "eliminar_turno"}
    alias_map = _build_service_alias_map(defined)

    assert alias_map.get("create_turno") == "crear_turno"
    assert alias_map.get("get_turno") == "obtener_turno"
    assert alias_map.get("delete_turno") == "eliminar_turno"


def test_s131d_alias_map_listar_to_list():
    """Si services.py define listar_turnos, el mapa debe mapear list_turnos → listar_turnos."""
    from code_postprocessor import _build_service_alias_map

    defined = {"listar_turnos", "buscar_turno", "actualizar_turno"}
    alias_map = _build_service_alias_map(defined)

    assert alias_map.get("list_turnos") == "listar_turnos"
    assert alias_map.get("search_turno") == "buscar_turno"
    assert alias_map.get("update_turno") == "actualizar_turno"


def test_s131d_alias_map_does_not_alias_itself():
    """El mapa no debe mapear una función a sí misma."""
    from code_postprocessor import _build_service_alias_map

    defined = {"create_turno"}
    alias_map = _build_service_alias_map(defined)

    assert alias_map.get("create_turno") != "create_turno", (
        "No debe crear alias circular create_turno → create_turno"
    )


# ── S131-E: diagnóstico frontend 0 artefactos ───────────────────────────────


def test_s131e_frontend_diagnostic_in_graph_source():
    """graph.py debe tener lógica S131-E para escribir debug_frontend_*.txt."""
    assert "S131-E" in _GRAPH_SRC
    assert "debug_frontend_" in _GRAPH_SRC


def test_s131e_frontend_diagnostic_only_for_frontend_agent():
    """El diagnóstico S131-E solo aplica cuando agent_name == 'frontend'."""
    idx = _GRAPH_SRC.find("S131-E")
    # Debe haber una condición agent_name == "frontend" cerca del bloque S131-E
    surrounding = _GRAPH_SRC[max(0, idx - 200) : idx + 200]
    assert 'agent_name == "frontend"' in surrounding
