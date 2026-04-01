"""
OVD Platform — GitHub Helper (Sprint 6)
Copyright 2026 Omar Robles

Utilidades para integración con repositorios GitHub via PAT:
  - Clonar / actualizar repo antes del ciclo
  - Leer archivos relevantes del repo para contexto de agentes
  - Crear branch + commit + PR automático al entregar

Nota de arquitectura: MVP con PAT. Migrar a GitHub App en v1.0.

Variables de entorno (configurables desde Dashboard por proyecto):
  github_token  — viene del Project Profile via Bridge (no env var directa)
  github_repo   — URL del repo, ej: https://github.com/org/repo
  github_branch — branch base (default: main)
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Extensiones de archivos relevantes por tipo de agente
_AGENT_EXTENSIONS: dict[str, list[str]] = {
    "backend":  [".py", ".ts", ".js", ".go", ".java", ".rb", ".php"],
    "frontend": [".tsx", ".ts", ".jsx", ".js", ".vue", ".svelte", ".html", ".css"],
    "database": [".sql", ".prisma", ".graphql"],
    "devops":   ["Dockerfile", ".yml", ".yaml", ".sh", ".tf", ".hcl"],
    "default":  [".py", ".ts", ".js", ".go", ".java", ".sql", ".yml"],
}

_MAX_FILES_PER_AGENT  = 6     # máximo de archivos a incluir como contexto
_MAX_CHARS_PER_FILE   = 2_000 # truncar archivos largos
_MAX_TOTAL_CHARS      = 8_000 # límite total de contexto de repo


# ---------------------------------------------------------------------------
# G1.B — Clonar / actualizar repo
# ---------------------------------------------------------------------------

def _inject_token_in_url(url: str, token: str) -> str:
    """Inserta el PAT en la URL de GitHub para autenticación HTTPS."""
    # https://github.com/org/repo → https://{token}@github.com/org/repo
    return re.sub(r"https://", f"https://{token}@", url, count=1)


def clone_or_pull(github_repo: str, github_token: str, github_branch: str = "main") -> str:
    """
    Clona el repo si no existe localmente, o hace git pull si ya está clonado.
    Retorna la ruta local del directorio clonado.

    El repo se clona en /tmp/ovd-repos/{org}/{repo_name} para reutilizarlo
    entre ciclos del mismo proyecto.
    """
    # Derivar nombre de org/repo desde la URL
    match = re.search(r"github\.com[:/](.+?)(?:\.git)?$", github_repo)
    if not match:
        raise ValueError(f"URL de GitHub inválida: {github_repo}")

    repo_path_str = match.group(1)  # ej: "omar/my-service"
    local_dir = Path("/tmp/ovd-repos") / repo_path_str

    # Solo inyectar token si está presente (repos públicos no lo requieren)
    auth_url = _inject_token_in_url(github_repo, github_token) if github_token else github_repo

    if local_dir.exists():
        log.info("github_helper: repo ya clonado en %s — haciendo pull", local_dir)
        result = subprocess.run(
            ["git", "pull", "origin", github_branch],
            cwd=local_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            log.warning("github_helper: git pull falló: %s", result.stderr[:200])
    else:
        log.info("github_helper: clonando %s en %s", github_repo, local_dir)
        local_dir.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "clone", "--depth=1", "--branch", github_branch, auth_url, str(local_dir)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            import re as _re
            # SEC HIGH-02: redactar PAT embebido en la URL antes de loguear/lanzar
            safe_err = _re.sub(r"https?://[^:@\s]+:[^@\s]+@", "https://***:***@", result.stderr[:300])
            raise RuntimeError(f"git clone falló: {safe_err}")

    return str(local_dir)


# ---------------------------------------------------------------------------
# G1.C — Leer archivos del repo para contexto de agentes
# ---------------------------------------------------------------------------

def read_repo_context(directory: str, agent_name: str = "default") -> str:
    """
    Lee los archivos más relevantes del repo para el agente dado.
    Retorna un bloque de texto Markdown listo para inyectar en el prompt.

    Límites: máx _MAX_FILES_PER_AGENT archivos, _MAX_CHARS_PER_FILE por archivo,
    _MAX_TOTAL_CHARS en total.
    """
    base = Path(directory)
    if not base.exists():
        return ""

    extensions = _AGENT_EXTENSIONS.get(agent_name, _AGENT_EXTENSIONS["default"])
    candidates: list[Path] = []

    for ext in extensions:
        if ext.startswith("."):
            candidates.extend(base.rglob(f"*{ext}"))
        else:
            # Para archivos sin extensión como "Dockerfile"
            candidates.extend(base.rglob(ext))

    # Filtrar: excluir node_modules, .venv, __pycache__, .git, dist, build
    _EXCLUDE = {".git", "node_modules", ".venv", "__pycache__", "dist", "build", ".next"}
    candidates = [
        p for p in candidates
        if not any(part in _EXCLUDE for part in p.parts)
        and p.is_file()
    ]

    # Ordenar por tamaño ascendente (preferir archivos pequeños/manejables)
    candidates.sort(key=lambda p: p.stat().st_size)
    candidates = candidates[:_MAX_FILES_PER_AGENT]

    if not candidates:
        return ""

    blocks: list[str] = ["### Archivos del repositorio (contexto)\n"]
    total_chars = 0

    for path in candidates:
        if total_chars >= _MAX_TOTAL_CHARS:
            break
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            if len(content) > _MAX_CHARS_PER_FILE:
                content = content[:_MAX_CHARS_PER_FILE] + "\n... [truncado]"

            rel_path = path.relative_to(base)
            ext = path.suffix.lstrip(".") or "text"
            block = f"\n**`{rel_path}`**\n```{ext}\n{content}\n```\n"
            blocks.append(block)
            total_chars += len(block)
        except Exception as e:
            log.debug("github_helper: no se pudo leer %s: %s", path, e)

    return "".join(blocks) if len(blocks) > 1 else ""


# ---------------------------------------------------------------------------
# G1.D — Crear branch, commit y PR automático
# ---------------------------------------------------------------------------

def _write_agent_artifacts(directory: str, agent_results: list[dict]) -> list[str]:
    """
    Escribe los artefactos de los agentes en el directorio del repo.
    Retorna la lista de rutas de archivos creados.
    """
    base = Path(directory)
    created: list[str] = []

    for result in agent_results:
        agent  = result.get("agent", "agent")
        output = result.get("output", "")
        if not output:
            continue

        # Extraer bloques de código del output Markdown
        code_blocks = re.findall(r"```(?:\w+)?\n(.*?)```", output, re.DOTALL)

        if code_blocks:
            for i, code in enumerate(code_blocks):
                suffix = _infer_extension(agent, code)
                fname  = f"ovd_{agent}_{i + 1}{suffix}"
                fpath  = base / "ovd_output" / fname
                fpath.parent.mkdir(parents=True, exist_ok=True)
                fpath.write_text(code, encoding="utf-8")
                created.append(str(fpath.relative_to(base)))
        else:
            # Sin bloques de código: guardar el output completo como .md
            fname = f"ovd_{agent}_output.md"
            fpath = base / "ovd_output" / fname
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text(output, encoding="utf-8")
            created.append(str(fpath.relative_to(base)))

    return created


def _infer_extension(agent: str, code: str) -> str:
    """Infiere la extensión del archivo según el agente y el contenido."""
    if agent == "database" or code.strip().upper().startswith(("SELECT", "CREATE", "INSERT", "ALTER")):
        return ".sql"
    if agent == "devops":
        if "FROM " in code and "RUN " in code:
            return ""  # Dockerfile sin extensión
        return ".yml"
    if agent == "frontend":
        if "import React" in code or "jsx" in code.lower():
            return ".tsx"
        return ".ts"
    # backend y default
    if "def " in code or "import " in code and "class " in code:
        return ".py"
    return ".ts"


async def create_pr(
    directory: str,
    github_token: str,
    github_repo: str,
    github_branch: str,
    session_id: str,
    agent_results: list[dict],
    sdd_summary: str,
    qa_score: int,
    security_score: int,
) -> dict[str, Any]:
    """
    G1.D: Crea una branch ovd/{session_id}, hace commit de los artefactos
    generados y abre un PR automático en GitHub.

    Retorna dict con pr_url, branch y archivos commiteados.
    """
    if not github_token or not github_repo:
        return {"ok": False, "reason": "github_token o github_repo no configurados"}

    new_branch = f"ovd/{session_id[:8]}"

    try:
        # 1. Crear branch desde la base
        subprocess.run(
            ["git", "checkout", "-b", new_branch],
            cwd=directory, capture_output=True, text=True, timeout=30, check=True,
        )

        # 2. Escribir artefactos al disco
        files_created = _write_agent_artifacts(directory, agent_results)
        if not files_created:
            return {"ok": False, "reason": "No hay artefactos para commitear"}

        # 3. Git add + commit
        subprocess.run(
            ["git", "add", "ovd_output/"],
            cwd=directory, capture_output=True, text=True, timeout=30, check=True,
        )
        commit_msg = f"feat(ovd): implementación automática — sesión {session_id[:8]}\n\nQA: {qa_score}/100 | Security: {security_score}/100"
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=directory, capture_output=True, text=True, timeout=30, check=True,
        )

        # 4. Push de la branch
        auth_url = _inject_token_in_url(github_repo, github_token)
        subprocess.run(
            ["git", "push", auth_url, new_branch],
            cwd=directory, capture_output=True, text=True, timeout=60, check=True,
        )

        # 5. Crear PR via GitHub REST API
        match = re.search(r"github\.com[:/](.+?)(?:\.git)?$", github_repo)
        repo_path = match.group(1) if match else ""

        pr_body = (
            f"## OVD — Entrega automática\n\n"
            f"**Sesión:** `{session_id}`\n\n"
            f"### Resumen del SDD\n{sdd_summary}\n\n"
            f"### Resultados de calidad\n"
            f"- Security score: **{security_score}/100**\n"
            f"- QA score: **{qa_score}/100**\n\n"
            f"### Archivos generados\n"
            + "\n".join(f"- `{f}`" for f in files_created)
            + "\n\n> Generado automáticamente por OVD Engine"
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"https://api.github.com/repos/{repo_path}/pulls",
                headers={
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                json={
                    "title": f"feat(ovd): implementación automática [{session_id[:8]}]",
                    "body": pr_body,
                    "head": new_branch,
                    "base": github_branch,
                },
            )

        if resp.status_code in (200, 201):
            pr_data = resp.json()
            pr_url  = pr_data.get("html_url", "")
            pr_number = pr_data.get("number", 0)
            log.info("github_helper: PR creado — %s", pr_url)
            return {
                "ok": True,
                "pr_url": pr_url,
                "pr_number": pr_number,
                "branch": new_branch,
                "files": files_created,
            }
        else:
            log.warning("github_helper: error creando PR — %s %s", resp.status_code, resp.text[:200])
            return {"ok": False, "reason": f"GitHub API error {resp.status_code}", "branch": new_branch, "files": files_created}

    except subprocess.CalledProcessError as e:
        log.error("github_helper: error git — %s", e.stderr[:200] if e.stderr else str(e))
        return {"ok": False, "reason": str(e)}
    except Exception as e:
        log.error("github_helper: error inesperado — %s", e)
        return {"ok": False, "reason": str(e)}
