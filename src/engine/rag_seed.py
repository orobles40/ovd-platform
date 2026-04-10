"""
OVD Platform — RAG Seed por Proyecto (GAP-006)
Copyright 2026 Omar Robles

Indexa conocimiento de base para un proyecto en pgvector ANTES del primer ciclo.
El seed transforma el Project Profile y documentos adicionales en documentos RAG
que los agentes pueden recuperar durante generate_sdd.

Flujo:
  1. rag_seed.seed_project(org_id, project_id, jwt_token)
     → GET /ovd/project/{id}/profile desde el Bridge
     → POST /ovd/rag/index con los documentos del perfil
  2. rag_seed.retrieve_context(feature_request, org_id, project_id, jwt_token)
     → GET /ovd/rag/search?query=...
     → retorna string con contexto RAG para inyectar en system_sdd

También puede recibir documentos adicionales (markdown, PDF texto plano) para
indexar conocimiento específico del proyecto: arquitectura, guías de estilo,
decisiones técnicas, glosario de dominio, etc.

Uso como script:
  python rag_seed.py --org-id ORG --project-id PROJ --token JWT
  python rag_seed.py --org-id ORG --project-id PROJ --token JWT --file docs/arch.md
  python rag_seed.py --org-id ORG --project-id PROJ --token JWT --retrieve "autenticacion"

Variables de entorno:
  OVD_BRIDGE_URL   — URL del Bridge TypeScript (default: http://localhost:3000)
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BRIDGE_URL = os.environ.get("OVD_BRIDGE_URL", "http://localhost:3000")
RAG_ENABLED = os.environ.get("OVD_RAG_ENABLED", "true").lower() == "true"

# Top-K documentos recuperados del RAG para el contexto
RAG_TOP_K = int(os.environ.get("OVD_RAG_TOP_K", "5"))

# Score mínimo de similaridad para incluir un documento (0.0 - 1.0)
RAG_MIN_SCORE = float(os.environ.get("OVD_RAG_MIN_SCORE", "0.65"))


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _http(method: str, path: str, token: str, payload: dict | None = None) -> dict:
    """Helper HTTP minimo sin dependencias externas."""
    url = f"{BRIDGE_URL}{path}"
    data = json.dumps(payload).encode() if payload else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            return json.loads(res.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} {method} {path}: {body}") from e


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------

async def seed_project(
    org_id: str,
    project_id: str,
    jwt_token: str,
    extra_docs: list[dict] | None = None,
) -> int:
    """
    Semilla el RAG con documentos adicionales del proyecto.
    Indexa directamente en pgvector via rag.py (sin Bridge).

    Retorna el número de documentos indexados.
    Si el RAG no está habilitado, retorna 0 sin hacer nada.
    """
    if not RAG_ENABLED:
        return 0

    if not extra_docs:
        return 0

    try:
        import rag as _rag
        n = await _rag.index_chunks_async(extra_docs, project_id, org_id)
        return n
    except Exception as e:
        print(f"[rag_seed] Warning: seed fallido para {project_id}: {e}", file=sys.stderr)
        return 0


def retrieve_context(
    query: str,
    org_id: str,
    project_id: str,
    jwt_token: str = "",
) -> str:
    """
    Recupera contexto relevante del RAG para el feature request dado.
    Retorna un bloque de texto formateado para inyectar en system_sdd.
    Si no hay resultados o el RAG no está habilitado, retorna string vacio.
    Busca directamente en pgvector via rag.py (sin Bridge).
    """
    if not RAG_ENABLED:
        return ""

    try:
        import rag as _rag
        return _rag.search(query, project_id)
    except Exception as e:
        print(f"[rag_seed] Warning: RAG search fallido: {e}", file=sys.stderr)
        return ""


def seed_from_file(
    file_path: str,
    org_id: str,
    project_id: str,
    jwt_token: str = "",
    doc_type: str = "doc",
) -> bool:
    """
    Indexa un archivo de texto (markdown, txt) como documento RAG del proyecto.
    Útil para: guías de arquitectura, guías de estilo, glosarios de dominio, etc.
    """
    p = Path(file_path)
    if not p.exists():
        print(f"[rag_seed] Error: archivo no encontrado: {file_path}", file=sys.stderr)
        return False

    try:
        import sys as _sys
        import rag as _rag
        from knowledge.chunkers import chunk_doc, chunk_codebase
        chunker = chunk_codebase if doc_type == "codebase" else chunk_doc
        chunks = list(chunker(p))
        chunk_dicts = [
            {"content": c.content, "doc_type": c.doc_type,
             "source_file": c.source_file, "metadata": c.metadata}
            for c in chunks
        ]
        n = _rag.index_chunks(chunk_dicts, project_id, org_id)
        print(f"[rag_seed] Indexado: {p.name} ({n} chunks)")
        return n > 0
    except Exception as e:
        print(f"[rag_seed] Error indexando {file_path}: {e}", file=sys.stderr)
        return False


import urllib.parse  # noqa: E402


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:
    global BRIDGE_URL
    parser = argparse.ArgumentParser(
        description="OVD RAG Seed — Indexa conocimiento de base por proyecto"
    )
    parser.add_argument("--org-id",     required=True,  help="ID de la organización")
    parser.add_argument("--project-id", required=True,  help="ID del proyecto")
    parser.add_argument("--token",      required=True,  help="JWT del Bridge")
    parser.add_argument("--file",       help="Archivo .md/.txt adicional a indexar")
    parser.add_argument("--retrieve",   help="Buscar en el RAG y mostrar el resultado")
    parser.add_argument(
        "--bridge-url",
        default=BRIDGE_URL,
        help=f"URL del Bridge (default: {BRIDGE_URL})",
    )

    args = parser.parse_args()

    BRIDGE_URL = args.bridge_url

    if args.retrieve:
        print(f"\nBuscando en RAG: '{args.retrieve}'")
        ctx = retrieve_context(args.retrieve, args.org_id, args.project_id, args.token)
        if ctx:
            print(f"\n{ctx}\n")
        else:
            print("Sin resultados relevantes.\n")
        return

    if args.file:
        print(f"\nIndexando archivo: {args.file}")
        ok = seed_from_file(args.file, args.org_id, args.project_id, args.token)
        sys.exit(0 if ok else 1)

    # Seed completo del perfil del proyecto
    print(f"\nSeeding RAG para proyecto {args.project_id}...")
    import asyncio
    indexed = asyncio.run(seed_project(args.org_id, args.project_id, args.token))
    print(f"Documentos indexados: {indexed}\n")


if __name__ == "__main__":
    _cli()
