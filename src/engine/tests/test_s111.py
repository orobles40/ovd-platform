"""
S111: tests para scaffolding frontend, CORS injection y back_populates orphan fix.

S111-A: ensure_frontend_scaffold — crea archivos Vite React TS si faltan
S111-B: _inject_cors_middleware — inyecta CORSMiddleware en main.py
S111-C: _fix_back_populates_orphan — elimina back_populates sin relación inversa
S111-D: template system_backend_python.md contiene instrucción anti-stubs
"""

import pathlib

import pytest

from code_postprocessor import (
    _fix_back_populates_orphan,
    _inject_cors_middleware,
    ensure_frontend_scaffold,
)

# ---------------------------------------------------------------------------
# S111-B: _inject_cors_middleware
# ---------------------------------------------------------------------------


def test_inject_cors_middleware_adds_import_and_middleware():
    content = (
        "from fastapi import FastAPI\n"
        "from src.auth.router import router as auth_router\n\n"
        "app = FastAPI(title='Test')\n"
        "app.include_router(auth_router, prefix='/auth')\n"
    )
    result = _inject_cors_middleware(content, "src/main.py")
    assert "CORSMiddleware" in result
    assert "from fastapi.middleware.cors import CORSMiddleware" in result
    assert "app.add_middleware(" in result
    assert "allow_origins" in result


def test_inject_cors_middleware_skips_if_already_present():
    content = (
        "from fastapi import FastAPI\n"
        "from fastapi.middleware.cors import CORSMiddleware\n\n"
        "app = FastAPI()\n"
        "app.add_middleware(CORSMiddleware, allow_origins=['*'])\n"
    )
    result = _inject_cors_middleware(content, "src/main.py")
    assert result == content


def test_inject_cors_middleware_skips_non_main_files():
    content = "from fastapi import FastAPI\napp = FastAPI()\n"
    result = _inject_cors_middleware(content, "src/auth/router.py")
    assert result == content


def test_inject_cors_middleware_skips_non_fastapi_files():
    content = "x = 1\ny = 2\n"
    result = _inject_cors_middleware(content, "src/main.py")
    assert result == content


def test_inject_cors_middleware_placed_after_fastapi_init():
    content = "from fastapi import FastAPI\napp = FastAPI()\napp.include_router(r)\n"
    result = _inject_cors_middleware(content, "src/main.py")
    cors_pos = result.find("add_middleware")
    router_pos = result.find("include_router")
    assert cors_pos < router_pos, "CORSMiddleware debe estar antes de include_router"


# ---------------------------------------------------------------------------
# S111-C: _fix_back_populates_orphan
# ---------------------------------------------------------------------------


def test_fix_back_populates_orphan_removes_missing_inverse(tmp_path):
    """Si el atributo inverso no existe en ningún model, strip back_populates."""
    models_py = tmp_path / "src" / "turnos" / "models.py"
    models_py.parent.mkdir(parents=True)
    models_py.write_text(
        "class TurnoORM(Base):\n"
        "    id = Column(Integer, primary_key=True)\n"
        "    paciente = relationship('PacienteORM', back_populates='turnos')\n"
        "    medico = relationship('MedicoORM', back_populates='turnos')\n",
        encoding="utf-8",
    )
    content = models_py.read_text(encoding="utf-8")
    result = _fix_back_populates_orphan(content, "src/turnos/models.py", str(tmp_path))
    assert "back_populates" not in result


def test_fix_back_populates_orphan_preserves_valid_inverse(tmp_path):
    """Si el atributo inverso SÍ existe, no tocar."""
    # Crear PacienteORM con attr 'turnos'
    paciente_models = tmp_path / "src" / "pacientes" / "models.py"
    paciente_models.parent.mkdir(parents=True)
    paciente_models.write_text(
        "class PacienteORM(Base):\n"
        "    id = Column(Integer, primary_key=True)\n"
        "    turnos = relationship('TurnoORM', back_populates='paciente')\n",
        encoding="utf-8",
    )
    turno_models = tmp_path / "src" / "turnos" / "models.py"
    turno_models.parent.mkdir(parents=True)
    turno_content = (
        "class TurnoORM(Base):\n"
        "    id = Column(Integer, primary_key=True)\n"
        "    paciente = relationship('PacienteORM', back_populates='turnos')\n"
    )
    turno_models.write_text(turno_content, encoding="utf-8")

    result = _fix_back_populates_orphan(
        turno_content, "src/turnos/models.py", str(tmp_path)
    )
    assert "back_populates='turnos'" in result


def test_fix_back_populates_orphan_skips_non_model_files(tmp_path):
    content = "x = relationship('A', back_populates='items')\n"
    result = _fix_back_populates_orphan(content, "src/services.py", str(tmp_path))
    assert result == content


def test_fix_back_populates_orphan_no_work_dir():
    content = "paciente = relationship('PacienteORM', back_populates='turnos')\n"
    result = _fix_back_populates_orphan(content, "models.py", "")
    assert result == content


# ---------------------------------------------------------------------------
# S111-A: ensure_frontend_scaffold
# ---------------------------------------------------------------------------


def test_ensure_frontend_scaffold_creates_package_json(tmp_path):
    frontend = tmp_path / "frontend" / "src" / "components"
    frontend.mkdir(parents=True)
    (frontend / "App.tsx").write_text(
        "export default function App() { return null }", encoding="utf-8"
    )

    created = ensure_frontend_scaffold(str(tmp_path))
    assert any("package.json" in p for p in created)
    assert (tmp_path / "frontend" / "package.json").exists()


def test_ensure_frontend_scaffold_creates_vite_config(tmp_path):
    frontend = tmp_path / "frontend" / "src"
    frontend.mkdir(parents=True)
    (frontend / "App.tsx").write_text(
        "export default function App() {}", encoding="utf-8"
    )

    ensure_frontend_scaffold(str(tmp_path))
    vite_config = tmp_path / "frontend" / "vite.config.ts"
    assert vite_config.exists()
    assert "@tailwindcss/vite" in vite_config.read_text()


def test_ensure_frontend_scaffold_creates_index_html(tmp_path):
    frontend = tmp_path / "frontend" / "src"
    frontend.mkdir(parents=True)
    (frontend / "Dashboard.tsx").write_text(
        "export default function Dashboard() {}", encoding="utf-8"
    )

    ensure_frontend_scaffold(str(tmp_path))
    index = tmp_path / "frontend" / "index.html"
    assert index.exists()
    assert '<div id="root">' in index.read_text()


def test_ensure_frontend_scaffold_creates_main_tsx_if_missing(tmp_path):
    frontend = tmp_path / "frontend" / "src"
    frontend.mkdir(parents=True)
    (frontend / "App.tsx").write_text(
        "export default function App() {}", encoding="utf-8"
    )

    ensure_frontend_scaffold(str(tmp_path))
    main_tsx = tmp_path / "frontend" / "src" / "main.tsx"
    assert main_tsx.exists()
    assert "createRoot" in main_tsx.read_text()


def test_ensure_frontend_scaffold_skips_if_package_json_exists(tmp_path):
    frontend = tmp_path / "frontend"
    frontend.mkdir(parents=True)
    (frontend / "package.json").write_text('{"name":"existing"}', encoding="utf-8")
    (tmp_path / "frontend" / "src").mkdir()
    (tmp_path / "frontend" / "src" / "App.tsx").write_text("", encoding="utf-8")

    created = ensure_frontend_scaffold(str(tmp_path))
    assert created == []


def test_ensure_frontend_scaffold_no_tsx_files(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("", encoding="utf-8")

    created = ensure_frontend_scaffold(str(tmp_path))
    assert created == []


def test_ensure_frontend_scaffold_does_not_overwrite_existing_app_tsx(tmp_path):
    frontend_src = tmp_path / "frontend" / "src"
    frontend_src.mkdir(parents=True)
    original_app = "export default function MyCustomApp() { return <div>Custom</div> }"
    (frontend_src / "App.tsx").write_text(original_app, encoding="utf-8")

    ensure_frontend_scaffold(str(tmp_path))
    assert (frontend_src / "App.tsx").read_text() == original_app


def test_ensure_frontend_scaffold_fixes_tailwind_v3_to_v4(tmp_path):
    frontend_src = tmp_path / "frontend" / "src"
    frontend_src.mkdir(parents=True)
    (frontend_src / "App.tsx").write_text(
        "export default function App() {}", encoding="utf-8"
    )
    (frontend_src / "index.css").write_text(
        "@tailwind base;\n@tailwind components;\n@tailwind utilities;\n",
        encoding="utf-8",
    )

    ensure_frontend_scaffold(str(tmp_path))
    css = (frontend_src / "index.css").read_text()
    assert '@import "tailwindcss"' in css
    assert "@tailwind base" not in css


def test_ensure_frontend_scaffold_index_css_uses_tailwind_v4(tmp_path):
    frontend_src = tmp_path / "frontend" / "src"
    frontend_src.mkdir(parents=True)
    (frontend_src / "Component.tsx").write_text(
        "export function C() {}", encoding="utf-8"
    )

    ensure_frontend_scaffold(str(tmp_path))
    css_path = frontend_src / "index.css"
    assert css_path.exists()
    assert '@import "tailwindcss"' in css_path.read_text()


def test_ensure_frontend_scaffold_vite_config_uses_tailwind_v4_plugin(tmp_path):
    frontend_src = tmp_path / "frontend" / "src"
    frontend_src.mkdir(parents=True)
    (frontend_src / "App.tsx").write_text(
        "export default function App() {}", encoding="utf-8"
    )

    ensure_frontend_scaffold(str(tmp_path))
    vite_config = tmp_path / "frontend" / "vite.config.ts"
    content = vite_config.read_text()
    assert "tailwindcss" in content
    assert "@tailwindcss/vite" in content


# ---------------------------------------------------------------------------
# S111-D: template contiene instrucción anti-stubs
# ---------------------------------------------------------------------------


def test_backend_template_prohibits_stubs():
    import os

    template_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "templates",
        "system_backend_python.md",
    )
    content = open(template_path, encoding="utf-8").read()
    assert "S111-D" in content or "stub" in content.lower()
    assert "PROHIBIDO" in content


def test_backend_template_includes_cors():
    import os

    template_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "templates",
        "system_backend_python.md",
    )
    content = open(template_path, encoding="utf-8").read()
    assert "CORSMiddleware" in content
    assert "S111-B" in content


def test_frontend_template_includes_scaffold_section():
    import os

    template_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "templates",
        "system_frontend_react.md",
    )
    content = open(template_path, encoding="utf-8").read()
    assert "package.json" in content
    assert "vite.config.ts" in content
    assert "src/main.tsx" in content
    assert "S111-A" in content


def test_frontend_template_uses_tailwind_v4_syntax():
    import os

    template_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "templates",
        "system_frontend_react.md",
    )
    content = open(template_path, encoding="utf-8").read()
    assert '@import "tailwindcss"' in content
    assert "@tailwindcss/vite" in content


def test_frontend_template_requires_hooks():
    import os

    template_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "templates",
        "system_frontend_react.md",
    )
    content = open(template_path, encoding="utf-8").read()
    assert "hooks" in content.lower()
    assert "use[Entidad]" in content or "use" in content


# ---------------------------------------------------------------------------
# S111-B (ruta tool-calling): postprocessor aplicado a archivo ya en disco
# ---------------------------------------------------------------------------


def test_inject_cors_applied_to_disk_file(tmp_path):
    """Simula la ruta tool-calling: main.py ya en disco sin CORS → debe quedar con CORS."""
    main_py = tmp_path / "src" / "main.py"
    main_py.parent.mkdir(parents=True)
    original = (
        "from fastapi import FastAPI\n"
        "from src.auth.router import router as auth_router\n\n"
        "app = FastAPI(title='Turnos')\n"
        "app.include_router(auth_router, prefix='/auth')\n"
    )
    main_py.write_text(original, encoding="utf-8")

    # Simular lo que el nuevo bloque en _run_agent_with_tools hace
    from code_postprocessor import postprocess_python_file

    processed = postprocess_python_file(original, "src/main.py", work_dir=str(tmp_path))
    main_py.write_text(processed, encoding="utf-8")

    result = main_py.read_text(encoding="utf-8")
    assert "CORSMiddleware" in result
    assert "from fastapi.middleware.cors import CORSMiddleware" in result


# ---------------------------------------------------------------------------
# S111-A (ruta tool-calling): ensure_frontend_scaffold sin guard "frontend" agent
# ---------------------------------------------------------------------------


def test_ensure_frontend_scaffold_runs_with_src_components_tsx(tmp_path):
    """tsx en src/components/ — sin package.json — scaffold debe crearse en raíz."""
    components = tmp_path / "src" / "components"
    components.mkdir(parents=True)
    (components / "LoginForm.tsx").write_text(
        "export default function LoginForm() { return null }", encoding="utf-8"
    )
    pages = tmp_path / "src" / "pages"
    pages.mkdir(parents=True)
    (pages / "Dashboard.tsx").write_text(
        "export default function Dashboard() { return null }", encoding="utf-8"
    )

    created = ensure_frontend_scaffold(str(tmp_path))
    assert any("package.json" in p for p in created)
    assert (tmp_path / "package.json").exists()
    assert (tmp_path / "vite.config.ts").exists()
    assert (tmp_path / "index.html").exists()
    assert (tmp_path / "src" / "main.tsx").exists()
