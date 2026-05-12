"""Tests S127 Fase 1 — Git branch awareness en OVD Desktop.

S127-A: workspace.rs exporta workspace_git_status y workspace_git_checkout_branch.
S127-B: workspace_git_status retorna struct GitStatus con branch, dirty, ahead.
S127-C: workspace_git_checkout_branch acepta parámetro create para -b.
S127-D: lib.rs registra ambos comandos git en invoke_handler.
S127-E: tauri.ts exporta workspaceGitStatus, workspaceGitCheckoutBranch, GitStatus.
S127-F: vitest.setup.ts mockea workspaceGitStatus y workspaceGitCheckoutBranch.
S127-G: Workspace.tsx importa workspaceGitStatus y muestra badge de rama.
S127-H: FrLauncher.tsx importa workspaceGitStatus, workspaceGitCheckoutBranch, GitStatus.
S127-I: FrLauncher.tsx tiene helper toSlug.
S127-J: FrLauncher.tsx tiene estados git: gitStatus, branchMode, newBranchName, gitError.
S127-K: FrLauncher.tsx llama workspaceGitStatus en useEffect al montar.
S127-L: FrLauncher.tsx llama workspaceGitCheckoutBranch en startCycle cuando branchMode new.
S127-M: FrLauncher.tsx renderiza selector de rama cuando gitStatus && phase idle.
"""

import pathlib
import re

import pytest

# ── Rutas ──────────────────────────────────────────────────────────────────────

_ENGINE_DIR = pathlib.Path(".")
_DESKTOP_DIR = _ENGINE_DIR / ".." / "desktop"

_WORKSPACE_RS = (_DESKTOP_DIR / "src-tauri" / "src" / "workspace.rs").read_text(
    encoding="utf-8"
)
_LIB_RS = (_DESKTOP_DIR / "src-tauri" / "src" / "lib.rs").read_text(encoding="utf-8")
_TAURI_TS = (_DESKTOP_DIR / "frontend" / "src" / "lib" / "tauri.ts").read_text(
    encoding="utf-8"
)
_SETUP_TS = (_DESKTOP_DIR / "frontend" / "vitest.setup.ts").read_text(encoding="utf-8")
_WORKSPACE_TSX = (
    _DESKTOP_DIR / "frontend" / "src" / "pages" / "Workspace.tsx"
).read_text(encoding="utf-8")
_FRLAUNCHER_TSX = (
    _DESKTOP_DIR / "frontend" / "src" / "pages" / "FrLauncher.tsx"
).read_text(encoding="utf-8")


# ── S127-A: workspace.rs exporta los dos comandos ─────────────────────────────


def test_s127a_workspace_git_status_fn():
    assert "pub async fn workspace_git_status" in _WORKSPACE_RS


def test_s127a_workspace_git_checkout_branch_fn():
    assert "pub async fn workspace_git_checkout_branch" in _WORKSPACE_RS


# ── S127-B: struct GitStatus con los tres campos ──────────────────────────────


def test_s127b_git_status_struct():
    assert "struct GitStatus" in _WORKSPACE_RS


def test_s127b_git_status_branch_field():
    assert "branch:" in _WORKSPACE_RS


def test_s127b_git_status_dirty_field():
    assert "dirty:" in _WORKSPACE_RS


def test_s127b_git_status_ahead_field():
    assert "ahead:" in _WORKSPACE_RS


# ── S127-C: workspace_git_checkout_branch acepta create y usa -b ──────────────


def test_s127c_checkout_uses_create_flag():
    assert (
        '"-b"' in _WORKSPACE_RS
        or '"-b", &branch' in _WORKSPACE_RS
        or "create" in _WORKSPACE_RS
    )


def test_s127c_checkout_create_param():
    assert "create: bool" in _WORKSPACE_RS


# ── S127-D: lib.rs registra ambos comandos en invoke_handler ─────────────────


def test_s127d_lib_registers_git_status():
    assert "workspace::workspace_git_status" in _LIB_RS


def test_s127d_lib_registers_git_checkout():
    assert "workspace::workspace_git_checkout_branch" in _LIB_RS


# ── S127-E: tauri.ts exporta tipos y funciones git ────────────────────────────


def test_s127e_git_status_interface():
    assert "interface GitStatus" in _TAURI_TS


def test_s127e_workspace_git_status_export():
    assert "workspaceGitStatus" in _TAURI_TS


def test_s127e_workspace_git_checkout_export():
    assert "workspaceGitCheckoutBranch" in _TAURI_TS


# ── S127-F: vitest.setup.ts mockea ambas funciones ───────────────────────────


def test_s127f_mock_git_status():
    assert "workspaceGitStatus" in _SETUP_TS


def test_s127f_mock_git_checkout():
    assert "workspaceGitCheckoutBranch" in _SETUP_TS


# ── S127-G: Workspace.tsx muestra badge de rama ───────────────────────────────


def test_s127g_workspace_imports_git_status():
    assert "workspaceGitStatus" in _WORKSPACE_TSX


def test_s127g_workspace_git_branches_state():
    assert "gitBranches" in _WORKSPACE_TSX


def test_s127g_workspace_shows_branch_badge():
    assert "GitBranch" in _WORKSPACE_TSX


# ── S127-H: FrLauncher importa las funciones git ─────────────────────────────


def test_s127h_frlauncher_imports_git_status():
    assert "workspaceGitStatus" in _FRLAUNCHER_TSX


def test_s127h_frlauncher_imports_git_checkout():
    assert "workspaceGitCheckoutBranch" in _FRLAUNCHER_TSX


def test_s127h_frlauncher_imports_git_status_type():
    assert "GitStatus" in _FRLAUNCHER_TSX


# ── S127-I: FrLauncher tiene helper toSlug ────────────────────────────────────


def test_s127i_to_slug_function():
    assert "function toSlug" in _FRLAUNCHER_TSX


def test_s127i_to_slug_normalize():
    assert "normalize" in _FRLAUNCHER_TSX


def test_s127i_to_slug_slice():
    assert ".slice(0, 40)" in _FRLAUNCHER_TSX


# ── S127-J: FrLauncher tiene los cuatro estados git ──────────────────────────


def test_s127j_git_status_state():
    assert "gitStatus" in _FRLAUNCHER_TSX and "setGitStatus" in _FRLAUNCHER_TSX


def test_s127j_branch_mode_state():
    assert "branchMode" in _FRLAUNCHER_TSX and "setBranchMode" in _FRLAUNCHER_TSX


def test_s127j_new_branch_name_state():
    assert "newBranchName" in _FRLAUNCHER_TSX and "setNewBranchName" in _FRLAUNCHER_TSX


def test_s127j_git_error_state():
    assert "gitError" in _FRLAUNCHER_TSX and "setGitError" in _FRLAUNCHER_TSX


# ── S127-K: FrLauncher carga git status en useEffect ─────────────────────────


def test_s127k_loads_git_status_on_mount():
    assert re.search(
        r"workspaceGitStatus\(project\.directory\)\s*\n?\s*\.then\(setGitStatus\)",
        _FRLAUNCHER_TSX,
    ), "FrLauncher debe llamar workspaceGitStatus en useEffect al montar"


# ── S127-L: startCycle llama workspaceGitCheckoutBranch si branchMode=new ─────


def test_s127l_start_cycle_calls_checkout():
    assert 'branchMode === "new"' in _FRLAUNCHER_TSX
    assert "workspaceGitCheckoutBranch" in _FRLAUNCHER_TSX


def test_s127l_checkout_uses_create_true():
    assert (
        "workspaceGitCheckoutBranch(project.directory, newBranchName, true)"
        in _FRLAUNCHER_TSX
    )


# ── S127-M: FrLauncher renderiza el selector de rama ─────────────────────────


def test_s127m_branch_selector_renders_git_branch_icon():
    # El selector usa el icono GitBranch de lucide
    assert "<GitBranch" in _FRLAUNCHER_TSX


def test_s127m_branch_selector_radio_current():
    assert 'branchMode === "current"' in _FRLAUNCHER_TSX


def test_s127m_branch_selector_radio_new():
    # Hay al menos dos referencias a branchMode === "new" (radio + conditional input)
    matches = re.findall(r'branchMode === "new"', _FRLAUNCHER_TSX)
    assert len(matches) >= 2


def test_s127m_branch_name_input_placeholder():
    assert 'placeholder="feature/..."' in _FRLAUNCHER_TSX
