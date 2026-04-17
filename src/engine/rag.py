"""
OVD Platform — RAG directo sobre pgvector (sin Bridge)
Copyright 2026 Omar Robles

Implementa indexación y búsqueda semántica usando:
  - OllamaEmbeddings (nomic-embed-text) o OpenAIEmbeddings (text-embedding-3-small)
  - PGVector (langchain-postgres) para almacenar y buscar en PostgreSQL

Reemplaza la dependencia del Bridge TypeScript para operaciones RAG.
Uso interno del engine: graph.py, rag_seed.py, knowledge/bootstrap.py

Tablas creadas automáticamente en el primer uso:
  langchain_pg_collection  — colecciones por proyecto (una por project_id)
  langchain_pg_embedding   — vectores + metadata + contenido

Variables de entorno:
  DATABASE_URL                  — conexión PostgreSQL (requerida)
  OVD_RAG_EMBEDDING_PROVIDER    — "ollama" (default) o "openai"
  OLLAMA_BASE_URL               — URL Ollama (default: http://localhost:11434)
  OVD_EMBED_MODEL               — modelo de embeddings
                                  ollama: nomic-embed-text (default)
                                  openai: text-embedding-3-small (default)
  OPENAI_API_KEY                — requerida cuando provider=openai
  OVD_RAG_TOP_K                 — top-K resultados en búsqueda (default: 5)
  OVD_RAG_MIN_SCORE             — score mínimo de similitud 0.0-1.0 (default: 0.65)
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("ovd.rag")

_DATABASE_URL      = os.environ.get("DATABASE_URL", "")
_EMBED_PROVIDER    = os.environ.get("OVD_RAG_EMBEDDING_PROVIDER", "ollama").lower()
_OLLAMA_URL        = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
_EMBED_MODEL       = os.environ.get("OVD_EMBED_MODEL", "")
_TOP_K             = int(os.environ.get("OVD_RAG_TOP_K", "5"))
_MIN_SCORE         = float(os.environ.get("OVD_RAG_MIN_SCORE", "0.65"))

# Modelos default por provider
_DEFAULT_MODEL = {
    "ollama": "nomic-embed-text",
    "openai": "text-embedding-3-small",
}

# Prefijo de colección por proyecto — aislamiento multi-proyecto
_COLLECTION_PREFIX = "ovd_project_"


# ---------------------------------------------------------------------------
# OB-01 — Filtros estructurados de metadatos
# ---------------------------------------------------------------------------

@dataclass
class RagFilters:
    """
    Filtros combinables para búsqueda semántica con metadatos.

    doc_types:    lista de tipos permitidos — ["delivery", "doc", "codebase", ...]
    min_qa_score: incluir solo chunks con qa_score >= N (0-100)
    after_date:   incluir solo chunks con created_at >= "YYYY-MM-DD"
    before_date:  incluir solo chunks con created_at <= "YYYY-MM-DD"
    """
    doc_types:     list[str] = field(default_factory=list)
    min_qa_score:  int | None = None
    after_date:    str | None = None   # "YYYY-MM-DD"
    before_date:   str | None = None   # "YYYY-MM-DD"

    def to_pgvector_filter(self) -> dict | None:
        """
        Convierte doc_types a filtro PGVector ($in operator).
        Los filtros numéricos y de fecha se aplican en Python post-búsqueda.
        """
        if not self.doc_types:
            return None
        if len(self.doc_types) == 1:
            return {"doc_type": self.doc_types[0]}
        return {"doc_type": {"$in": self.doc_types}}

    def passes(self, metadata: dict) -> bool:
        """Evalúa si un chunk con estos metadatos pasa los filtros de rango."""
        if self.min_qa_score is not None:
            score = metadata.get("qa_score")
            if score is not None and isinstance(score, (int, float)):
                if score < self.min_qa_score:
                    return False
        if self.after_date and "created_at" in metadata:
            if str(metadata["created_at"]) < self.after_date:
                return False
        if self.before_date and "created_at" in metadata:
            if str(metadata["created_at"]) > self.before_date:
                return False
        return True


def _get_connection_string() -> str:
    """Convierte DATABASE_URL al formato requerido por SQLAlchemy + psycopg2."""
    url = _DATABASE_URL
    # SQLAlchemy requiere postgresql+psycopg2:// para usar psycopg2
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    return url


def _get_embeddings():
    """
    Instancia el modelo de embeddings según OVD_RAG_EMBEDDING_PROVIDER.

    Soporta:
      "ollama"  — OllamaEmbeddings (nomic-embed-text). Requiere Ollama corriendo.
      "openai"  — OpenAIEmbeddings (text-embedding-3-small). Requiere OPENAI_API_KEY.
    """
    model = _EMBED_MODEL or _DEFAULT_MODEL.get(_EMBED_PROVIDER, "nomic-embed-text")

    if _EMBED_PROVIDER == "openai":
        from langchain_openai import OpenAIEmbeddings
        log.debug("rag: usando OpenAIEmbeddings (model=%s)", model)
        return OpenAIEmbeddings(model=model)

    # Default: Ollama
    from langchain_ollama import OllamaEmbeddings
    log.debug("rag: usando OllamaEmbeddings (model=%s, url=%s)", model, _OLLAMA_URL)
    return OllamaEmbeddings(model=model, base_url=_OLLAMA_URL)


def _get_store(project_id: str):
    """Retorna un PGVector store para el proyecto dado. Crea la colección si no existe."""
    from langchain_postgres.vectorstores import PGVector

    collection = f"{_COLLECTION_PREFIX}{project_id}"
    store = PGVector(
        embeddings=_get_embeddings(),
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
    rag_filters: "RagFilters | None" = None,
) -> str:
    """
    Busca chunks relevantes para la query en el proyecto dado.
    Retorna un bloque de texto formateado para inyectar en prompts.
    Retorna string vacío si no hay resultados o RAG no está disponible.

    OB-01: rag_filters permite filtrar por doc_type, qa_score mínimo y fechas.
    Cuando se especifica rag_filters, se recupera un buffer (top_k * 4) y se
    post-filtra en Python para aplicar filtros de rango que JSONB no soporta.
    """
    if not _DATABASE_URL:
        return ""

    try:
        store = _get_store(project_id)

        # Construir filtro PGVector: combinación de dict legacy + RagFilters
        filter_dict: dict[str, Any] = {}
        if filters:
            filter_dict.update(filters)
        if rag_filters:
            pf = rag_filters.to_pgvector_filter()
            if pf:
                filter_dict.update(pf)

        # Si hay filtros de rango (qa_score, fechas), ampliar el fetch para compensar
        fetch_k = top_k * 4 if rag_filters and (
            rag_filters.min_qa_score is not None
            or rag_filters.after_date
            or rag_filters.before_date
        ) else top_k

        results = store.similarity_search_with_relevance_scores(
            query,
            k=fetch_k,
            filter=filter_dict if filter_dict else None,
        )

        # Filtrar por score mínimo de similitud
        relevant = [(doc, score) for doc, score in results if score >= min_score]

        # OB-01: post-filtro de metadatos (qa_score, created_at)
        if rag_filters:
            relevant = [(doc, score) for doc, score in relevant if rag_filters.passes(doc.metadata)]

        # Tomar los top_k finales
        relevant = relevant[:top_k]

        if not relevant:
            return ""

        lines = [f"Contexto RAG — {len(relevant)} documento(s) relevante(s) del proyecto:"]
        for i, (doc, score) in enumerate(relevant, 1):
            meta     = doc.metadata
            doc_type = meta.get("doc_type", "doc")
            source   = meta.get("source_file", "")
            qa       = meta.get("qa_score")
            title    = source if source else f"doc-{i}"
            qa_label = f", QA={qa}" if qa is not None else ""
            lines.append(f"\n### [{i}] {title} (tipo: {doc_type}{qa_label}, similitud: {score:.2f})")
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
    rag_filters: "RagFilters | None" = None,
) -> str:
    """Versión async de search para uso en nodos LangGraph."""
    import asyncio
    return await asyncio.to_thread(search, query, project_id, top_k, min_score, filters, rag_filters)
