"""Tests S125 — OVD Desktop: extracción de artefactos a outputDirectory + cleanup endpoint.

S125-A: endpoint DELETE /session/{thread_id} existe en api.py.
S125-B: el endpoint solo elimina directorios bajo tmpdir del sistema.
S125-C: el endpoint preserva directorios de proyecto (no tmpdir).
S125-D: workspaceOpenFolder existe en tauri.ts.
S125-E: workspace_open_folder está registrado en lib.rs.
S125-F: FrLauncher usa outputDirectory cuando está disponible.
S125-G: Workspace.tsx exporta Project con campo outputDirectory.
S125-H: handleDeliver usa outputDirectory ?? directory.
"""

import pathlib
import re

_API_SRC = (pathlib.Path(".") / "api.py").read_text(encoding="utf-8")

_TAURI_TS = (
    pathlib.Path(".") / ".." / "desktop" / "frontend" / "src" / "lib" / "tauri.ts"
).read_text(encoding="utf-8")

_LIB_RS = (
    pathlib.Path(".") / ".." / "desktop" / "src-tauri" / "src" / "lib.rs"
).read_text(encoding="utf-8")

_LAUNCHER_TSX = (
    pathlib.Path(".")
    / ".."
    / "desktop"
    / "frontend"
    / "src"
    / "pages"
    / "FrLauncher.tsx"
).read_text(encoding="utf-8")

_WORKSPACE_TSX = (
    pathlib.Path(".")
    / ".."
    / "desktop"
    / "frontend"
    / "src"
    / "pages"
    / "Workspace.tsx"
).read_text(encoding="utf-8")

_WORKSPACE_RS = (
    pathlib.Path(".") / ".." / "desktop" / "src-tauri" / "src" / "workspace.rs"
).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# S125-A — endpoint cleanup existe
# ---------------------------------------------------------------------------


def test_s125a_cleanup_endpoint_exists():
    """api.py debe tener el endpoint DELETE /session/{thread_id}."""
    assert "@app.delete" in _API_SRC, "S125-A: falta decorador @app.delete en api.py"
    assert "cleanup_session" in _API_SRC, (
        "S125-A: falta función cleanup_session en api.py"
    )


def test_s125a_cleanup_endpoint_path():
    """El endpoint debe estar en /session/{thread_id}."""
    assert (
        '"/session/{thread_id}"' in _API_SRC or "'/session/{thread_id}'" in _API_SRC
    ), "S125-A: el endpoint de cleanup debe estar en /session/{thread_id}"


def test_s125a_cleanup_uses_verify_secret():
    """El endpoint de cleanup debe requerir verify_secret."""
    cleanup_idx = _API_SRC.find("cleanup_session")
    snippet = _API_SRC[cleanup_idx - 50 : cleanup_idx + 300]
    assert "verify_secret" in snippet, (
        "S125-A: cleanup_session debe protegerse con verify_secret"
    )


# ---------------------------------------------------------------------------
# S125-B — cleanup solo elimina tmpdirs
# ---------------------------------------------------------------------------


def test_s125b_cleanup_checks_tmpdir():
    """El cleanup debe verificar que el directorio está bajo el tmpdir del sistema."""
    assert "gettempdir" in _API_SRC or "tmp_root" in _API_SRC, (
        "S125-B: cleanup debe verificar que el directorio es un tmpdir"
    )


def test_s125b_cleanup_preserves_project_dirs():
    """El cleanup debe retornar sin eliminar si el directorio no es tmpdir."""
    assert "no es tmpdir" in _API_SRC or "se preserva" in _API_SRC, (
        "S125-B: cleanup debe indicar explícitamente que preserva directorios de proyecto"
    )


def test_s125b_cleanup_uses_rmtree():
    """El cleanup debe usar shutil.rmtree para eliminar el tmpdir."""
    assert "rmtree" in _API_SRC, "S125-B: cleanup debe usar shutil.rmtree"


# ---------------------------------------------------------------------------
# S125-C — cleanup retorna estructura JSON
# ---------------------------------------------------------------------------


def test_s125c_cleanup_returns_ok_field():
    """cleanup_session debe retornar un dict con campo 'ok'."""
    assert '"ok": True' in _API_SRC or '"ok": True' in _API_SRC, (
        "S125-C: cleanup_session debe retornar {ok: True/False}"
    )


# ---------------------------------------------------------------------------
# S125-D — workspaceOpenFolder en tauri.ts
# ---------------------------------------------------------------------------


def test_s125d_workspace_open_folder_in_tauri_ts():
    """tauri.ts debe exportar workspaceOpenFolder."""
    assert "workspaceOpenFolder" in _TAURI_TS, (
        "S125-D: tauri.ts debe exportar workspaceOpenFolder"
    )


def test_s125d_workspace_open_folder_invokes_rust():
    """workspaceOpenFolder debe invocar el comando Rust workspace_open_folder."""
    assert "workspace_open_folder" in _TAURI_TS, (
        "S125-D: workspaceOpenFolder debe invocar 'workspace_open_folder' en Rust"
    )


# ---------------------------------------------------------------------------
# S125-E — workspace_open_folder en lib.rs
# ---------------------------------------------------------------------------


def test_s125e_open_folder_registered_in_lib():
    """lib.rs debe registrar workspace_open_folder en el invoke_handler."""
    assert "workspace_open_folder" in _LIB_RS, (
        "S125-E: workspace_open_folder debe estar registrado en lib.rs"
    )


# ---------------------------------------------------------------------------
# S125-F — workspace_open_folder en workspace.rs
# ---------------------------------------------------------------------------


def test_s125f_open_folder_command_exists():
    """workspace.rs debe tener el comando workspace_open_folder."""
    assert "workspace_open_folder" in _WORKSPACE_RS, (
        "S125-F: workspace.rs debe definir fn workspace_open_folder"
    )


def test_s125f_open_folder_uses_open_on_macos():
    """workspace.rs debe usar 'open' como comando en macOS."""
    assert '"open"' in _WORKSPACE_RS, (
        "S125-F: workspace_open_folder debe usar 'open' en macOS"
    )


# ---------------------------------------------------------------------------
# S125-G — Workspace.tsx exporta Project con outputDirectory
# ---------------------------------------------------------------------------


def test_s125g_project_interface_exported():
    """Workspace.tsx debe exportar la interfaz Project."""
    assert "export interface Project" in _WORKSPACE_TSX, (
        "S125-G: Workspace.tsx debe exportar 'export interface Project'"
    )


def test_s125g_project_has_output_directory():
    """La interfaz Project debe tener el campo outputDirectory opcional."""
    assert "outputDirectory?" in _WORKSPACE_TSX, (
        "S125-G: Project debe tener campo 'outputDirectory?: string'"
    )


# ---------------------------------------------------------------------------
# S125-H — FrLauncher usa outputDirectory
# ---------------------------------------------------------------------------


def test_s125h_frlauncher_imports_project_type():
    """FrLauncher.tsx debe importar Project desde Workspace."""
    assert (
        'from "./Workspace"' in _LAUNCHER_TSX or "from './Workspace'" in _LAUNCHER_TSX
    ), "S125-H: FrLauncher.tsx debe importar Project de './Workspace'"


def test_s125h_frlauncher_uses_output_directory():
    """handleDeliver debe usar outputDirectory del proyecto."""
    assert "outputDirectory" in _LAUNCHER_TSX, (
        "S125-H: FrLauncher.tsx debe referenciar project.outputDirectory"
    )


def test_s125h_frlauncher_fallback_to_directory():
    """FrLauncher debe usar directory como fallback cuando outputDirectory no está."""
    assert (
        "outputDirectory ?? project.directory" in _LAUNCHER_TSX
        or "outputDirectory ?? directory" in _LAUNCHER_TSX
        or ("outputDirectory" in _LAUNCHER_TSX and "project.directory" in _LAUNCHER_TSX)
    ), "S125-H: debe referenciar outputDirectory y project.directory como fallback"


def test_s125h_frlauncher_shows_written_files():
    """FrLauncher debe mostrar los artefactos escritos (writtenFiles state)."""
    assert "writtenFiles" in _LAUNCHER_TSX, (
        "S125-H: FrLauncher debe tener estado writtenFiles para mostrar archivos escritos"
    )


def test_s125h_frlauncher_has_open_button():
    """FrLauncher debe tener botón para abrir la carpeta de salida."""
    assert "workspaceOpenFolder" in _LAUNCHER_TSX, (
        "S125-H: FrLauncher debe llamar a workspaceOpenFolder para abrir la carpeta"
    )


def test_s125h_frlauncher_calls_cleanup_after_deliver():
    """FrLauncher debe llamar al endpoint de cleanup tras extraer los artefactos."""
    assert "/cleanup" in _LAUNCHER_TSX or "cleanup" in _LAUNCHER_TSX, (
        "S125-H: FrLauncher debe llamar al endpoint DELETE /session/{id} tras la entrega"
    )
