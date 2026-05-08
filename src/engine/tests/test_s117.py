"""
OVD Platform — Tests S117: QA stale fix + timeout escalado + templates async

Verifica:
  A. Migración failed_at_node existe en versions/
  B. OVDState tiene qa_result_current (sin Annotated reducer)
  C. qa_review escribe qa_result_current en todas sus salidas
  D. update_qa_retry lee qa_result_current primero
  E. _get_task_timeout escala 1.0 / 1.5 / 2.0 por ronda
  F. _agent_executor_impl usa _task_timeout (no _AGENTS_TIMEOUT directo)
  G. backend_python.md contiene patrón SQLAlchemy async D4
  H. system_sdd.md contiene regla S117-E concurrencia
"""

import ast
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
MIGRATIONS_DIR = os.path.join(BASE_DIR, "migrations", "versions")
GRAPH_PY = os.path.join(BASE_DIR, "graph.py")


# ---------------------------------------------------------------------------
# A — Migración failed_at_node
# ---------------------------------------------------------------------------


def test_migration_failed_at_node_exists():
    files = os.listdir(MIGRATIONS_DIR)
    matching = [f for f in files if "failed_at_node" in f]
    assert matching, "Migración failed_at_node no encontrada en migrations/versions/"


def test_migration_failed_at_node_revision():
    files = [
        f
        for f in os.listdir(MIGRATIONS_DIR)
        if "failed_at_node" in f and f.endswith(".py")
    ]
    assert files, "Archivo de migración failed_at_node no existe"
    path = os.path.join(MIGRATIONS_DIR, files[0])
    content = open(path).read()
    assert "failed_at_node" in content
    assert "ALTER TABLE ovd_cycles" in content
    assert "ADD COLUMN" in content


# ---------------------------------------------------------------------------
# B — OVDState.qa_result_current sin Annotated
# ---------------------------------------------------------------------------


def _graph_source() -> str:
    return open(GRAPH_PY, encoding="utf-8").read()


def test_ovdstate_has_qa_result_current():
    src = _graph_source()
    assert "qa_result_current: dict" in src, (
        "OVDState debe tener campo qa_result_current: dict (sin Annotated)"
    )


def test_qa_result_current_is_not_annotated():
    src = _graph_source()
    # Asegurarse que qa_result_current NO tenga Annotated (es last-write-wins)
    lines = src.splitlines()
    for i, line in enumerate(lines):
        if "qa_result_current" in line and "Annotated" in line:
            pytest.fail(
                f"qa_result_current no debe usar Annotated (línea {i + 1}): {line.strip()}"
            )


# ---------------------------------------------------------------------------
# C — qa_review escribe qa_result_current en todas sus salidas
# ---------------------------------------------------------------------------


def test_qa_review_returns_qa_result_current():
    src = _graph_source()
    # Extraer solo el cuerpo de qa_review
    match = re.search(
        r"async def qa_review.*?(?=\nasync def |\ndef [a-z]|\nclass |\Z)",
        src,
        re.DOTALL,
    )
    assert match, "Función qa_review no encontrada"
    qa_body = match.group(0)
    # Buscar returns que tengan qa_result pero NO qa_result_current
    returns_with_qa = re.findall(
        r"return\s*\{[^}]*\"qa_result\"\s*:[^}]+\}", qa_body, re.DOTALL
    )
    for ret in returns_with_qa:
        if '"qa_result_current"' not in ret:
            pytest.fail(
                f"return en qa_review con qa_result sin qa_result_current:\n{ret[:300]}"
            )


# ---------------------------------------------------------------------------
# D — update_qa_retry lee qa_result_current primero
# ---------------------------------------------------------------------------


def test_update_qa_retry_reads_qa_result_current():
    src = _graph_source()
    # La línea de asignación de qa en update_qa_retry debe mencionar qa_result_current
    assert "qa_result_current" in src
    # Específicamente en el contexto de update_qa_retry
    match = re.search(
        r"(?:async )?def update_qa_retry.*?(?=\nasync def |\ndef [a-z]|\nclass |\Z)",
        src,
        re.DOTALL,
    )
    assert match, "Función update_qa_retry no encontrada"
    fn_body = match.group(0)
    assert "qa_result_current" in fn_body, (
        "update_qa_retry debe leer qa_result_current para evitar scores stale"
    )


# ---------------------------------------------------------------------------
# E — _get_task_timeout escala correctamente
# ---------------------------------------------------------------------------


def test_get_task_timeout_defined():
    src = _graph_source()
    assert "def _get_task_timeout(" in src, "_get_task_timeout no está definida"


def test_get_task_timeout_ronda_0():
    # Importar directamente la función
    import importlib.util

    spec = importlib.util.spec_from_file_location("graph", GRAPH_PY)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    except Exception:
        pytest.skip("graph.py requiere dependencias de entorno — test de source")

    fn = getattr(mod, "_get_task_timeout", None)
    base = getattr(mod, "_AGENTS_TIMEOUT", 120.0)
    if fn is None:
        pytest.skip("no se pudo importar _get_task_timeout")
    assert fn(0) == base * 1.0
    assert fn(1) == base * 1.5
    assert fn(2) == base * 2.0
    assert fn(99) == base * 2.0  # clamped al máximo


def test_get_task_timeout_source_scale_factors():
    src = _graph_source()
    # Verificar que los factores 1.0, 1.5, 2.0 están en la función
    match = re.search(
        r"def _get_task_timeout.*?(?=\ndef |\nasync def |\nclass |\Z)",
        src,
        re.DOTALL,
    )
    assert match, "_get_task_timeout no encontrada"
    fn_src = match.group(0)
    assert "1.5" in fn_src, "Factor 1.5 para retry #1 no encontrado"
    assert "2.0" in fn_src, "Factor 2.0 para retry #2+ no encontrado"


# ---------------------------------------------------------------------------
# F — _agent_executor_impl usa _task_timeout (no _AGENTS_TIMEOUT directo en wait_for)
# ---------------------------------------------------------------------------


def test_agent_executor_impl_no_direct_agents_timeout_in_wait_for():
    src = _graph_source()
    # Extraer cuerpo de _agent_executor_impl
    match = re.search(
        r"async def _agent_executor_impl.*?(?=\nasync def |\nclass |\Z)",
        src,
        re.DOTALL,
    )
    assert match, "_agent_executor_impl no encontrada"
    impl_body = match.group(0)

    # Buscar wait_for con timeout=_AGENTS_TIMEOUT directo (debe ser 0)
    direct_uses = re.findall(
        r"asyncio\.wait_for\([^)]*timeout=_AGENTS_TIMEOUT", impl_body
    )
    assert not direct_uses, (
        f"_agent_executor_impl aún usa timeout=_AGENTS_TIMEOUT directamente "
        f"({len(direct_uses)} ocurrencia(s)) — debe usar _task_timeout"
    )


def test_agent_executor_impl_computes_retry_round():
    src = _graph_source()
    match = re.search(
        r"async def _agent_executor_impl.*?(?=\nasync def |\nclass |\Z)",
        src,
        re.DOTALL,
    )
    assert match, "_agent_executor_impl no encontrada"
    impl_body = match.group(0)
    assert "_retry_round" in impl_body, (
        "_agent_executor_impl debe calcular _retry_round desde qa_retry_count + security_retry_count"
    )
    assert "_task_timeout" in impl_body, (
        "_agent_executor_impl debe usar _task_timeout calculado via _get_task_timeout"
    )


# ---------------------------------------------------------------------------
# G — backend_python.md contiene patrón SQLAlchemy async D4
# ---------------------------------------------------------------------------


def test_backend_python_has_async_sqlalchemy_pattern():
    path = os.path.join(TEMPLATES_DIR, "stack", "backend_python.md")
    content = open(path, encoding="utf-8").read()
    assert "async with db.begin()" in content, (
        "backend_python.md debe contener patrón async with db.begin() (S117-E D4)"
    )
    assert "with_for_update()" in content, (
        "backend_python.md debe contener .with_for_update() para SELECT FOR UPDATE"
    )
    assert "async_sessionmaker" in content, (
        "backend_python.md debe contener async_sessionmaker (SQLAlchemy 2.x async)"
    )


def test_backend_python_d4_section_exists():
    path = os.path.join(TEMPLATES_DIR, "stack", "backend_python.md")
    content = open(path, encoding="utf-8").read()
    assert "D4" in content and "SQLAlchemy" in content, (
        "backend_python.md debe tener sección D4 SQLAlchemy async"
    )
    assert "race condition" in content.lower() or "PROHIBIDO" in content, (
        "backend_python.md D4 debe advertir contra race conditions"
    )


# ---------------------------------------------------------------------------
# H — system_sdd.md contiene regla S117-E concurrencia
# ---------------------------------------------------------------------------


def test_system_sdd_has_concurrency_rule():
    path = os.path.join(TEMPLATES_DIR, "system_sdd.md")
    content = open(path, encoding="utf-8").read()
    assert "S117-E" in content, (
        "system_sdd.md debe contener regla de concurrencia S117-E"
    )
    assert "with_for_update" in content or "SELECT FOR UPDATE" in content, (
        "system_sdd.md S117-E debe mencionar with_for_update o SELECT FOR UPDATE"
    )


def test_system_sdd_concurrency_signals():
    path = os.path.join(TEMPLATES_DIR, "system_sdd.md")
    content = open(path, encoding="utf-8").read()
    # Verificar que menciona casos de uso típicos que activan la regla
    assert "reservar turno" in content or "reservas" in content, (
        "system_sdd.md debe mencionar casos de uso que activan la regla de concurrencia"
    )
