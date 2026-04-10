"""
OVD Platform — Knowledge Bootstrap (Sprint 8)
Copyright 2026 Omar Robles

Orquesta la ingesta de conocimiento existente de un proyecto de cliente
en el RAG de OVD. Soporta los 5 tipos de documentos definidos en
KNOWLEDGE_STRATEGY.md: codebase, doc, schema, contract, ticket.

Flujo:
  1. Chunk source_path según doc_type
  2. Para cada chunk, llamar al endpoint de indexación del Bridge (RAG seed)
  3. Reportar progreso y estadísticas

El Bridge gestiona la embeddings y el almacenamiento en pgvector.
El Bootstrap solo genera los chunks y los envía al Bridge.
"""
from __future__ import annotations

import asyncio
import logging
import pathlib
from dataclasses import dataclass
from typing import AsyncIterator

import httpx

from .chunkers import get_chunks, Chunk

log = logging.getLogger(__name__)

# Número de chunks a enviar en paralelo al Bridge
_BATCH_SIZE = int(10)
# Timeout por request al Bridge
_REQUEST_TIMEOUT = 30.0


@dataclass
class BootstrapResult:
    doc_type: str
    source: str
    total_chunks: int
    indexed: int
    failed: int
    errors: list[str]

    def summary(self) -> str:
        return (
            f"Bootstrap {self.doc_type} ({self.source}): "
            f"{self.indexed}/{self.total_chunks} chunks indexados, "
            f"{self.failed} fallidos"
        )


async def run(
    org_id: str,
    project_id: str,
    source_path: str | pathlib.Path,
    doc_type: str,
    bridge_url: str = "",
    jwt_token: str = "",
    batch_size: int = _BATCH_SIZE,
    dry_run: bool = False,
) -> BootstrapResult:
    """
    Ejecuta el bootstrap de conocimiento para un proyecto.

    Indexa directamente en pgvector via rag.py (sin Bridge TypeScript).
    Los parámetros bridge_url y jwt_token se mantienen por compatibilidad
    pero ya no se usan.

    Args:
        org_id:      ID de la organización
        project_id:  ID del proyecto/workspace
        source_path: Ruta al directorio o archivo a indexar
        doc_type:    Tipo de documento (codebase|doc|schema|contract|ticket|delivery)
        bridge_url:  Ignorado — mantenido por compatibilidad
        jwt_token:   Ignorado — mantenido por compatibilidad
        batch_size:  Chunks enviados en paralelo
        dry_run:     Si True, genera chunks pero no los indexa

    Returns:
        BootstrapResult con estadísticas de la operación
    """
    import sys
    import os
    # Agregar el directorio del engine al path para importar rag.py
    engine_dir = pathlib.Path(__file__).parent.parent / "engine"
    if str(engine_dir) not in sys.path:
        sys.path.insert(0, str(engine_dir))

    source_path = pathlib.Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Ruta no encontrada: {source_path}")

    log.info(
        "knowledge.bootstrap: iniciando — org=%s project=%s type=%s source=%s dry_run=%s",
        org_id, project_id, doc_type, source_path, dry_run,
    )

    chunks = list(get_chunks(source_path, doc_type))
    log.info("knowledge.bootstrap: %d chunks generados", len(chunks))

    if dry_run:
        log.info("knowledge.bootstrap: dry_run=True — no se indexará nada")
        return BootstrapResult(
            doc_type=doc_type,
            source=str(source_path),
            total_chunks=len(chunks),
            indexed=0,
            failed=0,
            errors=[],
        )

    indexed = 0
    failed = 0
    errors: list[str] = []

    # Indexar en lotes directamente via rag.py (sin Bridge)
    import rag as _rag
    for batch_start in range(0, len(chunks), batch_size):
        batch = chunks[batch_start: batch_start + batch_size]
        batch_dicts = [
            {
                "content": c.content,
                "doc_type": c.doc_type,
                "source_file": c.source_file,
                "metadata": c.metadata,
            }
            for c in batch
        ]
        try:
            n = await _rag.index_chunks_async(batch_dicts, project_id, org_id)
            indexed += n
        except Exception as e:
            failed += len(batch)
            errors.append(str(e))
            log.warning("knowledge.bootstrap: error indexando lote — %s", e)

        log.info(
            "knowledge.bootstrap: progreso %d/%d chunks (%d fallidos)",
            batch_start + len(batch), len(chunks), failed,
        )

    result = BootstrapResult(
        doc_type=doc_type,
        source=str(source_path),
        total_chunks=len(chunks),
        indexed=indexed,
        failed=failed,
        errors=errors[:20],  # máximo 20 errores en el reporte
    )
    log.info("knowledge.bootstrap: %s", result.summary())
    return result


async def _index_chunk(
    client: httpx.AsyncClient,
    chunk: Chunk,
    org_id: str,
    project_id: str,
    bridge_url: str,
    jwt_token: str,
) -> None:
    """Envía un chunk al endpoint de indexación del Bridge."""
    url = f"{bridge_url}/ovd/rag/seed"
    payload = {
        "org_id": org_id,
        "project_id": project_id,
        "content": chunk.content,
        "doc_type": chunk.doc_type,
        "source_file": chunk.source_file,
        "metadata": chunk.metadata,
    }
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
    }
    response = await client.post(url, json=payload, headers=headers)
    response.raise_for_status()


async def stream_chunks(
    source_path: str | pathlib.Path,
    doc_type: str,
) -> AsyncIterator[Chunk]:
    """
    Generador asíncrono de chunks para preview o procesamiento externo.
    Útil para estimar el volumen antes de ejecutar el bootstrap completo.
    """
    source_path = pathlib.Path(source_path)
    for chunk in get_chunks(source_path, doc_type):
        yield chunk
        await asyncio.sleep(0)  # ceder el event loop entre chunks grandes
