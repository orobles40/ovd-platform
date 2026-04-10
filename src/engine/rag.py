"""
OVD Platform — RAG directo sobre pgvector (sin Bridge)
Copyright 2026 Omar Robles

Implementa indexación y búsqueda semántica usando:
  - OllamaEmbeddings (nomic-embed-text) para generar vectores
  - PGVector (langchain-postgres) para almacenar y buscar en PostgreSQL

Reemplaza la dependencia del Bridge TypeScript para operaciones RAG.
Uso interno del engine: graph.py, rag_seed.py, knowledge/bootstrap.py

Tablas creadas automáticamente en el primer uso:
  langchain_pg_collection  — colecciones por proyecto (una por project_id)
  langchain_pg_embedding   — vectores + metadata + contenido

Variables de entorno:
  DATABASE_URL       — conexión PostgreSQL (requerida)
  OLLAMA_BASE_URL    — URL Ollama (default: http://localhost:11434)
  OVD_EMBED_MODEL    — modelo de embeddings (default: nomic-embed-text)
  OVD_RAG_TOP_K      — top-K resultados en búsqueda (default: 5)
  OVD_RAG_MIN_SCORE  — score mínimo de similitud 0.0-1.0 (default: 0.65)
"""
from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger("ovd.rag")

_DATABASE_URL   = os.environ.get("DATABASE_URL", "")
_OLLAMA_URL     = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
_EMBED_MODEL    = os.environ.get("OVD_EMBED_MODEL", "nomic-embed-text")
_TOP_K          = int(os.environ.get("OVD_RAG_TOP_K", "5"))
_MIN_SCORE      = float(os.environ.get("OVD_RAG_MIN_SCORE", "0.65"))

# Prefijo de colección por proyecto — aislamiento multi-proyecto
_COLLECTION_PREFIX = "ovd_project_"


def _get_connection_string() -> str:
    """Convierte DATABASE_URL al formato requerido por SQLAlchemy + psycopg2."""
    url = _DATABASE_URL
    # SQLAlchemy requiere postgresql+psycopg2:// para usar psycopg2
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    return url


def _get_store(project_id: str):
    """Retorna un PGVector store para el proyecto dado. Crea la colección si no existe."""
    from langchain_postgres.vectorstores import PGVector
    from langchain_ollama import OllamaEmbeddings

    embeddings = OllamaEmbeddings(
        model=_EMBED_MODEL,
        base_url=_OLLAMA_URL,
    )
    collection = f"{_COLLECTION_PREFIX}{project_id}"

    store = PGVector(
        embeddings=embeddings,
        collection_name=collection,
        connection=_get_connection_string(),
        use_jsonb=True,
    )
    return store


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def index_chunks(
    chunks: list[dict],
    project_id: str,
    org_id: str,
) -> int:
    """
    Indexa una lista de chunks en pgvector para el proyecto dado.

    Cada chunk debe tener:
      - content: str
      - doc_type: str
      - source_file: str
      - metadata: dict (opcional)

    Retorna el número de chunks indexados.
    """
    if not chunks:
        return 0
    if not _DATABASE_URL:
        log.warning("rag.index_chunks: DATABASE_URL no definida — saltando indexación")
        return 0

    try:
        from langchain_core.documents import Document

        store = _get_store(project_id)

        docs = []
        for chunk in chunks:
            meta = chunk.get("metadata", {}) or {}
            meta.update({
                "org_id": org_id,
                "project_id": project_id,
                "doc_type": chunk.get("doc_type", "doc"),
                "source_file": chunk.get("source_file", ""),
            })
            docs.append(Document(
                page_content=chunk["content"],
                metadata=meta,
            ))

        store.add_documents(docs)
        log.info("rag.index_chunks: %d chunks indexados en proyecto %s", len(docs), project_id)
        return len(docs)

    except Exception as e:
        log.error("rag.index_chunks: error — %s", e)
        return 0


def search(
    query: str,
    project_id: str,
    top_k: int = _TOP_K,
    min_score: float = _MIN_SCORE,
    filters: dict | None = None,
) -> str:
    """
    Busca chunks relevantes para la query en el proyecto dado.
    Retorna un bloque de texto formateado para inyectar en prompts.
    Retorna string vacío si no hay resultados o RAG no está disponible.
    """
    if not _DATABASE_URL:
        return ""

    try:
        store = _get_store(project_id)

        filter_dict: dict[str, Any] = {}
        if filters:
            filter_dict.update(filters)

        results = store.similarity_search_with_relevance_scores(
            query,
            k=top_k,
            filter=filter_dict if filter_dict else None,
        )

        relevant = [(doc, score) for doc, score in results if score >= min_score]
        if not relevant:
            return ""

        lines = [f"Contexto RAG — {len(relevant)} documento(s) relevante(s) del proyecto:"]
        for i, (doc, score) in enumerate(relevant, 1):
            meta     = doc.metadata
            doc_type = meta.get("doc_type", "doc")
            source   = meta.get("source_file", "")
            title    = f"{source}" if source else f"doc-{i}"
            lines.append(f"\n### [{i}] {title} (tipo: {doc_type}, similitud: {score:.2f})")
            lines.append(doc.page_content[:800])

        return "\n".join(lines)

    except Exception as e:
        log.warning("rag.search: error — %s", e)
        return ""


async def index_chunks_async(
    chunks: list[dict],
    project_id: str,
    org_id: str,
) -> int:
    """Versión async de index_chunks para uso en nodos LangGraph."""
    import asyncio
    return await asyncio.to_thread(index_chunks, chunks, project_id, org_id)


async def search_async(
    query: str,
    project_id: str,
    top_k: int = _TOP_K,
    min_score: float = _MIN_SCORE,
    filters: dict | None = None,
) -> str:
    """Versión async de search para uso en nodos LangGraph."""
    import asyncio
    return await asyncio.to_thread(search, query, project_id, top_k, min_score, filters)
