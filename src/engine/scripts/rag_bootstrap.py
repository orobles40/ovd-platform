"""
OVD Platform — S96-H: CLI de re-bootstrap y re-indexación RAG

Uso:
  # Re-bootstrap completo (borra chunks previos y re-indexa todo)
  python scripts/rag_bootstrap.py --org-id ORG --project-id PROJ --clear

  # Re-indexar un archivo o directorio específico (sin borrar)
  python scripts/rag_bootstrap.py --org-id ORG --project-id PROJ \
      --path /abs/path/to/file.py --doc-type codebase

  # Dry run (genera chunks pero no los indexa)
  python scripts/rag_bootstrap.py --org-id ORG --project-id PROJ --clear --dry-run

Variables de entorno requeridas:
  DATABASE_URL                  — PostgreSQL connection string
  OVD_RAG_EMBEDDING_PROVIDER   — "ollama" (default) o "openai"
  OLLAMA_BASE_URL               — URL Ollama (default: http://localhost:11434)

Corre desde src/engine/:
  cd src/engine && .venv/bin/python scripts/rag_bootstrap.py ...
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import pathlib
import sys

# Asegurar que src/engine/ esté en el path para importar rag y settings
_engine_dir = pathlib.Path(__file__).parent.parent
if str(_engine_dir) not in sys.path:
    sys.path.insert(0, str(_engine_dir))

# Asegurar que src/knowledge/ esté en el path para importar bootstrap
_knowledge_dir = _engine_dir.parent / "knowledge"
if str(_knowledge_dir.parent) not in sys.path:
    sys.path.insert(0, str(_knowledge_dir.parent))

# Cargar .env antes de importar rag/settings para que DATABASE_URL esté disponible
try:
    from dotenv import load_dotenv

    _env_file = _engine_dir / ".env"
    if _env_file.exists():
        load_dotenv(_env_file, override=False)
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ovd.rag_bootstrap")

# Rutas predeterminadas para re-bootstrap completo del proyecto OVD
_DEFAULT_SOURCES = [
    ("codebase", _engine_dir),
    ("doc", _engine_dir.parent.parent / "docs"),
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="S96-H: Re-bootstrap y re-indexación RAG para OVD Platform",
    )
    parser.add_argument("--org-id", required=True, help="ID de la organización")
    parser.add_argument("--project-id", required=True, help="ID del proyecto")
    parser.add_argument(
        "--path",
        help="Archivo o directorio a indexar (omitir para bootstrap completo)",
    )
    parser.add_argument(
        "--doc-type",
        default="codebase",
        choices=["codebase", "doc", "schema", "contract", "ticket", "delivery"],
        help="Tipo de documento (default: codebase)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Borrar todos los chunks previos del proyecto antes de indexar",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generar chunks pero no indexar (solo reportar volumen)",
    )
    return parser.parse_args()


async def main() -> int:
    args = _parse_args()

    from knowledge.bootstrap import run as bootstrap_run

    import rag as _rag

    # H1 — Borrar chunks previos si se solicitó
    if args.clear:
        if args.dry_run:
            log.info("dry-run: saltando clear_project_chunks")
        else:
            log.info("Borrando chunks previos del proyecto %s ...", args.project_id)
            deleted = _rag.clear_project_chunks(args.project_id)
            log.info("Chunks eliminados: %d", deleted)

    # Determinar fuentes a indexar
    if args.path:
        sources = [(args.doc_type, pathlib.Path(args.path))]
    else:
        sources = [(dt, p) for dt, p in _DEFAULT_SOURCES if p.exists()]
        if not sources:
            log.error("No se encontraron fuentes predeterminadas. Use --path.")
            return 1

    total_indexed = 0
    total_failed = 0

    for doc_type, source_path in sources:
        log.info("Indexando %s (tipo=%s) ...", source_path, doc_type)
        try:
            result = await bootstrap_run(
                org_id=args.org_id,
                project_id=args.project_id,
                source_path=source_path,
                doc_type=doc_type,
                dry_run=args.dry_run,
            )
            log.info(result.summary())
            if result.errors:
                for err in result.errors[:5]:
                    log.warning("  error: %s", err)
            total_indexed += result.indexed
            total_failed += result.failed
        except FileNotFoundError as e:
            log.error("Ruta no encontrada: %s", e)
            total_failed += 1

    print(
        f"\nRe-bootstrap completado: {total_indexed} chunks indexados, "
        f"{total_failed} fallidos"
    )
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
