"""
OVD Platform — S17T: File Tools para agentes LangGraph
Copyright 2026 Omar Robles

Fábrica de herramientas LangChain que operan sobre un directorio base.
Cada agente recibe su propio set con `base_dir` ya vinculado, garantizando
que no pueden escribir fuera del directorio del proyecto (path traversal fix).

Herramientas:
  write_file(path, content)         — escribe o sobreescribe un archivo
  read_file(path)                   — lee el contenido de un archivo
  edit_file(path, old_str, new_str) — reemplaza una cadena en un archivo
  list_files(pattern="**/*")        — lista archivos con glob

Contexto de proyecto:
  read_project_context(base_dir, agent_name) — lee archivos relevantes
  existentes para inyectar en el prompt del agente (S17T.C).
"""
from __future__ import annotations

import glob
import os
import pathlib
from typing import List

from langchain_core.tools import tool


# ---------------------------------------------------------------------------
# Constantes de seguridad
# ---------------------------------------------------------------------------

_MAX_READ_BYTES    = 32_768   # 32 KB por archivo al leer
_MAX_LIST_RESULTS  = 50       # máximo de rutas en list_files
_MAX_CTX_FILES     = 3        # archivos para read_project_context
_MAX_CTX_CHARS     = 2_000    # caracteres por archivo en el contexto

# Patrones relevantes por tipo de agente para read_project_context
_AGENT_PATTERNS: dict[str, list[str]] = {
    "frontend":  ["*.tsx", "*.ts", "*.jsx", "*.js", "*.vue", "package.json"],
    "backend":   ["*.py", "requirements.txt", "*.toml", "*.cfg"],
    "database":  ["*.sql", "migrations/*.py", "models.py", "schema*.sql"],
    "devops":    ["Dockerfile*", "docker-compose*.yml", "*.yaml", "*.tf"],
}


# ---------------------------------------------------------------------------
# Validación de rutas (previene path traversal)
# ---------------------------------------------------------------------------

def _resolve_safe(base_dir: str, relative_path: str) -> str:
    """
    Resuelve `relative_path` relativo a `base_dir` y verifica que el
    resultado esté dentro de `base_dir`. Lanza ValueError si no lo está.
    """
    base = pathlib.Path(base_dir).resolve()
    target = (base / relative_path).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise ValueError(
            f"Ruta denegada: '{relative_path}' intenta salir de '{base_dir}'"
        )
    return str(target)


# ---------------------------------------------------------------------------
# Fábrica principal
# ---------------------------------------------------------------------------

def make_file_tools(base_dir: str) -> list:
    """
    Retorna una lista de herramientas LangChain ligadas a `base_dir`.

    Uso en agent_executor:
        tools = make_file_tools(state["directory"])
        bound_llm = llm.bind_tools(tools)
    """
    if not base_dir or not os.path.isdir(base_dir):
        return []

    # ----- write_file -------------------------------------------------------

    @tool
    def write_file(path: str, content: str) -> str:
        """
        Escribe `content` en el archivo `path` (relativo al directorio del proyecto).
        Crea directorios intermedios si no existen.
        Retorna la ruta absoluta donde se guardó el archivo.
        """
        abs_path = _resolve_safe(base_dir, path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return abs_path

    # ----- read_file --------------------------------------------------------

    @tool
    def read_file(path: str) -> str:
        """
        Lee el contenido de `path` (relativo al directorio del proyecto).
        Limita la salida a 32 KB para proteger la ventana de contexto.
        """
        abs_path = _resolve_safe(base_dir, path)
        if not os.path.isfile(abs_path):
            return f"ERROR: '{path}' no existe."
        with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(_MAX_READ_BYTES)

    # ----- edit_file --------------------------------------------------------

    @tool
    def edit_file(path: str, old_str: str, new_str: str) -> str:
        """
        Reemplaza la primera ocurrencia de `old_str` por `new_str` en el archivo `path`.
        El archivo debe existir. Retorna 'OK' o un mensaje de error.
        """
        abs_path = _resolve_safe(base_dir, path)
        if not os.path.isfile(abs_path):
            return f"ERROR: '{path}' no existe."
        with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
            original = fh.read()
        if old_str not in original:
            return f"ERROR: cadena no encontrada en '{path}'."
        updated = original.replace(old_str, new_str, 1)
        with open(abs_path, "w", encoding="utf-8") as fh:
            fh.write(updated)
        return "OK"

    # ----- list_files -------------------------------------------------------

    @tool
    def list_files(pattern: str = "**/*") -> str:
        """
        Lista archivos en el directorio del proyecto que coincidan con `pattern` (glob).
        Devuelve las rutas relativas, una por línea (máximo 50).
        """
        base = pathlib.Path(base_dir)
        matches = list(base.glob(pattern))
        files = [
            str(p.relative_to(base))
            for p in sorted(matches)
            if p.is_file()
        ][:_MAX_LIST_RESULTS]
        return "\n".join(files) if files else "(sin archivos)"

    return [write_file, read_file, edit_file, list_files]


# ---------------------------------------------------------------------------
# S17T.C — Contexto de proyecto existente
# ---------------------------------------------------------------------------

def read_project_context(base_dir: str, agent_name: str) -> str:
    """
    Lee archivos existentes relevantes para el agente dado y retorna
    un bloque de contexto para inyectar en el system prompt.

    Solo lee los primeros `_MAX_CTX_CHARS` chars de cada archivo y
    un máximo de `_MAX_CTX_FILES` archivos, para no inflar el contexto.
    """
    if not base_dir or not os.path.isdir(base_dir):
        return ""

    patterns = _AGENT_PATTERNS.get(agent_name, ["*.py", "*.ts", "*.js"])
    base = pathlib.Path(base_dir)

    collected: list[str] = []
    seen = 0

    for pattern in patterns:
        if seen >= _MAX_CTX_FILES:
            break
        for filepath in sorted(base.rglob(pattern)):
            if seen >= _MAX_CTX_FILES:
                break
            # Ignorar node_modules, .git, __pycache__, etc.
            rel = str(filepath.relative_to(base))
            if any(part.startswith(".") or part in ("node_modules", "__pycache__", "dist", "build")
                   for part in pathlib.Path(rel).parts):
                continue
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
                    snippet = fh.read(_MAX_CTX_CHARS)
                collected.append(f"// {rel}\n{snippet}")
                seen += 1
            except OSError:
                continue

    if not collected:
        return ""

    return (
        "=== Archivos existentes en el proyecto ===\n"
        + "\n---\n".join(collected)
        + "\n=== Fin del contexto existente ===\n"
    )
