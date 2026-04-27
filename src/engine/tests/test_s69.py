"""
Tests S69 — S69-A: _ensure_fastapi_main_task inyecta src/main.py cuando falta
            S69-B: template system_sdd.md tiene tabla verificación obligatoria al inicio
            S69-C: _validate_artifacts_imports auto-genera src/main.py si broken import es src.main
"""
import pathlib
import sys
import textwrap

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from graph import _ensure_fastapi_main_task, _validate_artifacts_imports


# ---------------------------------------------------------------------------
# S69-A: _ensure_fastapi_main_task
# ---------------------------------------------------------------------------

def _fr_fastapi() -> dict:
    return {"raw": "Sistema con autenticación JWT usando FastAPI. API REST endpoints.", "type": "feature"}


def _fr_no_fastapi() -> dict:
    return {"raw": "Script de análisis de datos con pandas y numpy.", "type": "feature"}


def _sdd_without_main() -> dict:
    return {
        "summary": "SDD de prueba",
        "requirements": [],
        "design": {},
        "constraints": [],
        "tasks": [
            {"id": "T1", "agent": "backend", "title": "Crear auth models", "file": "src/auth/models.py",
             "description": "Pydantic models para auth", "depends_on": [], "estimated_complexity": "low"},
        ],
    }


def _sdd_with_main() -> dict:
    return {
        "summary": "SDD con main",
        "requirements": [],
        "design": {},
        "constraints": [],
        "tasks": [
            {"id": "T0", "agent": "backend", "title": "Crear src/main.py", "file": "src/main.py",
             "description": "app FastAPI con routers", "depends_on": [], "estimated_complexity": "low"},
            {"id": "T1", "agent": "backend", "title": "Crear auth models", "file": "src/auth/models.py",
             "description": "Pydantic models", "depends_on": [], "estimated_complexity": "low"},
        ],
    }


def test_s69a_inyecta_main_cuando_falta():
    """S69-A: si FR menciona FastAPI y no hay tarea src/main.py, se inyecta."""
    sdd = _sdd_without_main()
    result = _ensure_fastapi_main_task(sdd, _fr_fastapi())
    files = [t["file"] for t in result["tasks"]]
    assert "src/main.py" in files


def test_s69a_main_es_primera_tarea():
    """S69-A: TASK-INFRA-MAIN se inserta como primera tarea."""
    sdd = _sdd_without_main()
    result = _ensure_fastapi_main_task(sdd, _fr_fastapi())
    assert result["tasks"][0]["id"] == "TASK-INFRA-MAIN"
    assert result["tasks"][0]["agent"] == "backend"


def test_s69a_no_duplica_si_ya_existe():
    """S69-A: si src/main.py ya está en tareas, no se agrega otro."""
    sdd = _sdd_with_main()
    original_count = len(sdd["tasks"])
    result = _ensure_fastapi_main_task(sdd, _fr_fastapi())
    assert len(result["tasks"]) == original_count
    main_tasks = [t for t in result["tasks"] if "main.py" in t.get("file", "")]
    assert len(main_tasks) == 1


def test_s69a_no_inyecta_sin_fastapi():
    """S69-A: FR sin FastAPI → no se inyecta src/main.py."""
    sdd = _sdd_without_main()
    result = _ensure_fastapi_main_task(sdd, _fr_no_fastapi())
    files = [t["file"] for t in result["tasks"]]
    assert "src/main.py" not in files


def test_s69a_detecta_keyword_api_rest():
    """S69-A: 'api rest' en FR también dispara la inyección."""
    fr = {"raw": "Crear API REST con endpoints CRUD.", "type": "feature"}
    sdd = _sdd_without_main()
    result = _ensure_fastapi_main_task(sdd, fr)
    files = [t["file"] for t in result["tasks"]]
    assert "src/main.py" in files


def test_s69a_detecta_keyword_endpoint():
    """S69-A: 'endpoint' en FR dispara la inyección."""
    fr = {"raw": "Implementar un endpoint REST para consultar beneficios.", "type": "feature"}
    sdd = _sdd_without_main()
    result = _ensure_fastapi_main_task(sdd, fr)
    files = [t["file"] for t in result["tasks"]]
    assert "src/main.py" in files


def test_s69a_descripcion_contiene_entry_point():
    """S69-A: la tarea inyectada crea src/main.py como entry point FastAPI.
    S70-B: cuando no hay router.py en el SDD, description no genera include_router.
    """
    sdd = _sdd_without_main()
    result = _ensure_fastapi_main_task(sdd, _fr_fastapi())
    main_task = next(t for t in result["tasks"] if t.get("id") == "TASK-INFRA-MAIN")
    desc = main_task["description"].lower()
    # La tarea debe generar src/main.py con app = FastAPI()
    assert "fastapi" in desc or "main.py" in main_task["file"]
    # Sin router.py en el SDD, no debe incluir routers fantasma (S70-B)
    assert "include_router" not in desc


# ---------------------------------------------------------------------------
# S69-B: system_sdd.md tabla de verificación al inicio
# ---------------------------------------------------------------------------

TEMPLATES_DIR = pathlib.Path(__file__).parent.parent / "templates"


def test_s69b_tabla_verificacion_al_inicio():
    """S69-B: system_sdd.md contiene tabla VERIFICACIÓN OBLIGATORIA antes de 'Eres un arquitecto'."""
    template = (TEMPLATES_DIR / "system_sdd.md").read_text(encoding="utf-8")
    idx_tabla = template.find("VERIFICACIÓN OBLIGATORIA")
    idx_arquitecto = template.find("Eres un arquitecto")
    assert idx_tabla != -1, "Tabla VERIFICACIÓN OBLIGATORIA no encontrada"
    assert idx_tabla < idx_arquitecto, "Tabla debe aparecer ANTES de 'Eres un arquitecto'"


def test_s69b_tabla_menciona_main_py():
    """S69-B: template menciona src/main.py como obligatorio."""
    template = (TEMPLATES_DIR / "system_sdd.md").read_text(encoding="utf-8")
    assert "src/main.py" in template[:2000], "src/main.py debe estar en los primeros 2000 chars del template"


def test_s69b_tabla_menciona_fastapi_condicion():
    """S69-B: tabla menciona FastAPI como condición para src/main.py."""
    template = (TEMPLATES_DIR / "system_sdd.md").read_text(encoding="utf-8")
    # Primeros 2000 chars deben tener FastAPI
    assert "FastAPI" in template[:2000]


# ---------------------------------------------------------------------------
# S69-C: auto-generación de src/main.py desde _validate_artifacts_imports
# ---------------------------------------------------------------------------

def test_s69c_autogenera_main_py(tmp_path):
    """S69-C: cuando import roto es src.main y archivo no existe, se genera src/main.py."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text("")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    test_file = tests_dir / "test_app.py"
    test_file.write_text("from src.main import app\nclient = app\n")

    agent_results = [{"artifacts": [{"path": "tests/test_app.py"}]}]
    ok, feedback = _validate_artifacts_imports(agent_results, str(tmp_path), ["tests/test_app.py"])

    main_py = tmp_path / "src" / "main.py"
    assert main_py.exists(), "S69-C debe haber generado src/main.py"
    content = main_py.read_text()
    assert "FastAPI" in content
    assert "app = FastAPI()" in content


def test_s69c_main_contiene_routers_detectados(tmp_path):
    """S69-C: si hay router.py en disco, main.py generado los incluye."""
    src = tmp_path / "src"
    (src / "auth").mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "auth" / "__init__.py").write_text("")
    (src / "auth" / "router.py").write_text("from fastapi import APIRouter\nrouter = APIRouter()\n")

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    test_file = tests_dir / "test_app.py"
    test_file.write_text("from src.main import app\n")

    agent_results = [{"artifacts": [{"path": "tests/test_app.py"}]}]
    _validate_artifacts_imports(agent_results, str(tmp_path), ["tests/test_app.py"])

    main_py = tmp_path / "src" / "main.py"
    assert main_py.exists()
    content = main_py.read_text()
    assert "router" in content.lower()


def test_s69c_no_regenera_si_main_existe(tmp_path):
    """S69-C: si src/main.py ya existe, no lo sobreescribe."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text("")
    original = "# existing main\napp = None\n"
    (src / "main.py").write_text(original)

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    test_file = tests_dir / "test_app.py"
    test_file.write_text("from src.main import app\n")

    agent_results = [{"artifacts": [{"path": "tests/test_app.py"}]}]
    _validate_artifacts_imports(agent_results, str(tmp_path), ["tests/test_app.py"])

    content = (src / "main.py").read_text()
    assert content == original, "S69-C NO debe sobreescribir src/main.py existente"
