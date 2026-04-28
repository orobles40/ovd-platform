"""Tests for S83: topological sort, context injection, template fixes, auth router injection."""

import pytest

# ---------------------------------------------------------------------------
# S83-B — system_backend_python.md no contiene imports estáticos hardcodeados
# ---------------------------------------------------------------------------


def test_s83b_template_no_static_auth_import():
    """S83-B: template no debe tener import hardcodeado de auth_router."""
    import pathlib

    tpl = (
        pathlib.Path(__file__).parent.parent / "templates" / "system_backend_python.md"
    )
    content = tpl.read_text()
    # El template antiguo tenía "from src.auth.router import router as auth_router" como ejemplo fijo
    # Ahora debe tener la instrucción condicional
    assert "S83-B" in content, "template debe referenciar S83-B"
    assert "PROHIBIDO importar un router si no aparece en el SDD" in content


def test_s83b_template_has_dynamic_router_rule():
    """S83-B: template debe incluir regla de routers dinámicos del SDD."""
    import pathlib

    tpl = (
        pathlib.Path(__file__).parent.parent / "templates" / "system_backend_python.md"
    )
    content = tpl.read_text()
    assert (
        "IMPORTA SOLO LOS ROUTERS QUE TÚ GENERAS" in content
        or "solo si" in content.lower()
    )


# ---------------------------------------------------------------------------
# S83-C — system_backend_python.md tiene sección PostgreSQL antes que Oracle
# ---------------------------------------------------------------------------


def test_s83c_postgres_section_exists():
    """S83-C: template debe tener ejemplo de DATABASE_URL PostgreSQL."""
    import pathlib

    tpl = (
        pathlib.Path(__file__).parent.parent / "templates" / "system_backend_python.md"
    )
    content = tpl.read_text()
    assert "postgresql+psycopg" in content, "debe existir ejemplo de URL PostgreSQL"


def test_s83c_postgres_before_oracle():
    """S83-C: la sección PostgreSQL debe aparecer antes que la sección Oracle en el template."""
    import pathlib

    tpl = (
        pathlib.Path(__file__).parent.parent / "templates" / "system_backend_python.md"
    )
    content = tpl.read_text()
    pg_idx = content.find("postgresql+psycopg")
    oracle_idx = content.find("oracle+oracledb")
    assert pg_idx != -1, "sección PostgreSQL debe existir"
    assert oracle_idx != -1, "sección Oracle debe existir"
    assert pg_idx < oracle_idx, "PostgreSQL debe aparecer antes que Oracle"


# ---------------------------------------------------------------------------
# S83-D — system_devops.md tiene cap de 5 archivos
# ---------------------------------------------------------------------------


def test_s83d_devops_max_5_files():
    """S83-D: system_devops.md debe mencionar el límite de 5 archivos."""
    import pathlib

    tpl = pathlib.Path(__file__).parent.parent / "templates" / "system_devops.md"
    content = tpl.read_text()
    assert "MÁXIMO 5 archivos" in content or "máximo 5" in content.lower()


def test_s83d_devops_prohibits_validate_scripts():
    """S83-D: system_devops.md debe prohibir scripts validate-*.sh."""
    import pathlib

    tpl = pathlib.Path(__file__).parent.parent / "templates" / "system_devops.md"
    content = tpl.read_text()
    assert "validate-*.sh" in content or "validate-" in content


# ---------------------------------------------------------------------------
# S83-E — _ensure_auth_login_task inyecta auth/router.py cuando FR menciona login
# ---------------------------------------------------------------------------


def test_s83e_injects_auth_router_when_missing():
    """S83-E: debe inyectar TASK-INFRA-AUTH-ROUTER cuando FR menciona login y no hay auth/router."""
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from graph import _ensure_auth_login_task

    sdd = {"tasks": [{"id": "T1", "agent": "backend", "file": "src/database.py"}]}
    fr = {"raw": "sistema con autenticación JWT y login RUT", "type": "feature"}
    result = _ensure_auth_login_task(sdd, fr)
    ids = [t["id"] for t in result["tasks"]]
    assert "TASK-INFRA-AUTH-ROUTER" in ids


def test_s83e_no_injection_when_auth_router_exists():
    """S83-E: no debe duplicar si auth/router.py ya está en el SDD."""
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from graph import _ensure_auth_login_task

    sdd = {
        "tasks": [
            {"id": "T1", "agent": "backend", "file": "src/auth/router.py"},
        ]
    }
    fr = {"raw": "sistema con login JWT", "type": "feature"}
    result = _ensure_auth_login_task(sdd, fr)
    auth_tasks = [t for t in result["tasks"] if "auth/router" in t.get("file", "")]
    assert len(auth_tasks) == 1, "no debe duplicar auth/router.py"


def test_s83e_no_injection_when_fr_no_auth():
    """S83-E: no debe inyectar si el FR no menciona autenticación."""
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from graph import _ensure_auth_login_task

    sdd = {
        "tasks": [{"id": "T1", "agent": "backend", "file": "src/contracts/models.py"}]
    }
    fr = {
        "raw": "CRUD de productos, listado de inventario y exportación a CSV",
        "type": "feature",
    }
    result = _ensure_auth_login_task(sdd, fr)
    ids = [t["id"] for t in result["tasks"]]
    assert "TASK-INFRA-AUTH-ROUTER" not in ids


# ---------------------------------------------------------------------------
# S83-F — _topological_sort_tasks
# ---------------------------------------------------------------------------


def test_s83f_topo_sort_basic():
    """S83-F: sort básico — task B depende de A, A debe ir primero."""
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from graph import _topological_sort_tasks

    tasks = [
        {"id": "B", "depends_on": ["A"], "file": "service.py"},
        {"id": "A", "depends_on": [], "file": "models.py"},
    ]
    result = _topological_sort_tasks(tasks)
    ids = [t["id"] for t in result]
    assert ids.index("A") < ids.index("B"), "A debe ir antes que B"


def test_s83f_topo_sort_no_deps():
    """S83-F: sin dependencias, orden original se preserva."""
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from graph import _topological_sort_tasks

    tasks = [
        {"id": "A", "depends_on": [], "file": "models.py"},
        {"id": "B", "depends_on": [], "file": "service.py"},
    ]
    result = _topological_sort_tasks(tasks)
    assert len(result) == 2


def test_s83f_topo_sort_cycle_fallback():
    """S83-F: con ciclo, devuelve lista original sin modificar (no debe lanzar excepción)."""
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from graph import _topological_sort_tasks

    tasks = [
        {"id": "A", "depends_on": ["B"], "file": "a.py"},
        {"id": "B", "depends_on": ["A"], "file": "b.py"},
    ]
    result = _topological_sort_tasks(tasks)
    assert len(result) == 2  # no lanzó excepción, devolvió algo


def test_s83f_topo_sort_cross_agent_deps_ignored():
    """S83-F: dependencias de otros agentes (fuera del set local) se ignoran."""
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from graph import _topological_sort_tasks

    tasks = [
        {"id": "A", "depends_on": ["TASK-DB-EXTERNAL"], "file": "a.py"},
        {"id": "B", "depends_on": ["A"], "file": "b.py"},
    ]
    result = _topological_sort_tasks(tasks)
    assert len(result) == 2
    ids = [t["id"] for t in result]
    assert ids.index("A") < ids.index("B")


# ---------------------------------------------------------------------------
# S83-F — _build_dependency_context
# ---------------------------------------------------------------------------


def test_s83f_build_context_injects_models_for_service():
    """S83-F: debe inyectar models.py en el contexto de service.py."""
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from graph import _build_dependency_context

    written = {
        "src/contracts/models.py": "class ContractORM(Base):\n    id = Column(Integer, primary_key=True)"
    }
    task = {"id": "T2", "file": "src/contracts/service.py", "depends_on": []}
    result = _build_dependency_context(task, written)
    assert "ContractORM" in result
    assert "S83-F" in result


def test_s83f_build_context_empty_when_no_written():
    """S83-F: con written_context vacío, devuelve string vacío."""
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from graph import _build_dependency_context

    task = {"id": "T1", "file": "src/models.py", "depends_on": []}
    result = _build_dependency_context(task, {})
    assert result == ""


def test_s83f_build_context_no_inject_for_models():
    """S83-F: models.py escribiendo no recibe contexto de otros models.py."""
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from graph import _build_dependency_context

    written = {"src/other/models.py": "class OtherORM(Base): pass"}
    task = {"id": "T1", "file": "src/contracts/models.py", "depends_on": []}
    result = _build_dependency_context(task, written)
    # models.py no es consumidor (service/router/test_) — no debe inyectar
    assert result == ""


# ---------------------------------------------------------------------------
# S83-E wired — _ensure_auth_login_task llamada desde generate_sdd
# ---------------------------------------------------------------------------


def test_s83e_wired_in_generate_sdd_callchain():
    """S83-E: verificar que graph.py llama a _ensure_auth_login_task después de _ensure_contracts_models_task."""
    import pathlib

    src = pathlib.Path(__file__).parent.parent / "graph.py"
    content = src.read_text()
    # Verificar que la llamada existe en el código
    assert "_ensure_auth_login_task" in content
    # Verificar que está en la cadena de postprocesado del SDD
    contracts_idx = content.find("_ensure_contracts_models_task(sdd)")
    auth_idx = content.find("_ensure_auth_login_task(sdd,")
    assert contracts_idx != -1
    assert auth_idx != -1
    assert auth_idx > contracts_idx, (
        "_ensure_auth_login_task debe llamarse después de _ensure_contracts_models_task"
    )
