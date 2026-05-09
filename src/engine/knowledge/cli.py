"""
OVD Platform — Knowledge CLI (Sprint 8)
Copyright 2026 Omar Robles

Interfaz de línea de comandos para gestión de la base de conocimiento.

Comandos:
  bootstrap   Indexa documentos existentes de un proyecto en el RAG
  preview     Muestra los chunks generados sin indexar (dry-run)
  stats       Muestra estadísticas de documentos indexados por proyecto

Uso:
  # Indexar código fuente
  uv run python -m knowledge.cli bootstrap \\
    --org-id org_123 --project-id proj_abc \\
    --source /ruta/al/codigo --type codebase

  # Indexar DDL de Oracle
  uv run python -m knowledge.cli bootstrap \\
    --org-id org_123 --project-id proj_abc \\
    --source /ruta/al/ddl --type schema

  # Preview sin indexar
  uv run python -m knowledge.cli preview \\
    --source /ruta/al/codigo --type codebase --limit 5

  # Con Bridge y JWT explícitos
  uv run python -m knowledge.cli bootstrap \\
    --org-id org_123 --project-id proj_abc \\
    --source /docs --type doc \\
    --bridge http://localhost:3000 \\
    --token eyJhbGci...
"""
from __future__ import annotations

import asyncio
import json
import os
import pathlib
import sys

import argparse

from . import bootstrap as _bootstrap
from .chunkers import get_chunks, DOC_TYPE_CHUNKERS


def _get_env(name: str, fallback: str = "") -> str:
    return os.environ.get(name, fallback)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m knowledge.cli",
        description="OVD Knowledge Bootstrap — indexa documentos de proyectos en el RAG",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── bootstrap ──────────────────────────────────────────────────────────
    bs = sub.add_parser("bootstrap", help="Indexa documentos en el RAG del proyecto")
    bs.add_argument("--org-id",     required=True, help="ID de la organización")
    bs.add_argument("--project-id", required=True, help="ID del proyecto/workspace")
    bs.add_argument("--source",     required=True, help="Ruta al directorio o archivo")
    bs.add_argument(
        "--type", required=True,
        choices=list(DOC_TYPE_CHUNKERS.keys()),
        help="Tipo de documento",
    )
    bs.add_argument(
        "--bridge",
        default=_get_env("OVD_BRIDGE_URL", "http://localhost:3000"),
        help="URL del Bridge (default: $OVD_BRIDGE_URL o http://localhost:3000)",
    )
    bs.add_argument(
        "--token",
        default=_get_env("OVD_JWT_TOKEN", ""),
        help="JWT de autenticación (default: $OVD_JWT_TOKEN)",
    )
    bs.add_argument("--batch-size", type=int, default=10, help="Chunks en paralelo (default: 10)")
    bs.add_argument("--dry-run", action="store_true", help="Genera chunks sin enviar al Bridge")

    # ── preview ────────────────────────────────────────────────────────────
    pv = sub.add_parser("preview", help="Muestra chunks generados sin indexar")
    pv.add_argument("--source", required=True, help="Ruta al directorio o archivo")
    pv.add_argument(
        "--type", required=True,
        choices=list(DOC_TYPE_CHUNKERS.keys()),
        help="Tipo de documento",
    )
    pv.add_argument("--limit", type=int, default=10, help="Máximo de chunks a mostrar (default: 10)")
    pv.add_argument("--json", action="store_true", help="Salida en formato JSON")

    return parser


def cmd_bootstrap(args: argparse.Namespace) -> None:
    if not args.token and not args.dry_run:
        print("ERROR: --token requerido para indexar (o usar --dry-run)", file=sys.stderr)
        sys.exit(1)

    result = asyncio.run(_bootstrap.run(
        org_id=args.org_id,
        project_id=args.project_id,
        source_path=args.source,
        doc_type=args.type,
        bridge_url=args.bridge,
        jwt_token=args.token,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    ))
    print(result.summary())
    if result.errors:
        print(f"\nPrimeros {len(result.errors)} errores:")
        for err in result.errors:
            print(f"  - {err}")
    sys.exit(0 if result.failed == 0 else 1)


def cmd_preview(args: argparse.Namespace) -> None:
    source = pathlib.Path(args.source)
    if not source.exists():
        print(f"ERROR: ruta no encontrada: {source}", file=sys.stderr)
        sys.exit(1)

    count = 0
    for chunk in get_chunks(source, args.type):
        if count >= args.limit:
            break
        if args.json:
            print(json.dumps({
                "doc_type": chunk.doc_type,
                "source_file": chunk.source_file,
                "metadata": chunk.metadata,
                "content_preview": chunk.content[:200],
                "content_length": len(chunk.content),
            }, ensure_ascii=False))
        else:
            print(f"─── Chunk {count + 1} [{chunk.doc_type}] {chunk.source_file} ───")
            print(f"Metadata: {chunk.metadata}")
            print(f"Contenido ({len(chunk.content)} chars):")
            print(chunk.content[:300])
            print()
        count += 1

    # Contar total
    total = sum(1 for _ in get_chunks(source, args.type))
    print(f"Total de chunks: {total} (mostrando {min(args.limit, total)})")


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "bootstrap":
        cmd_bootstrap(args)
    elif args.command == "preview":
        cmd_preview(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
