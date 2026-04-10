# ADR-001 — RAG implementado directamente en el engine Python (sin Bridge TypeScript)

**Fecha:** 2026-04-08
**Estado:** Aceptado
**Autor:** Omar Robles

---

## Contexto

El diseño original de OVD Platform contemplaba un Bridge TypeScript (puerto 3000) como
intermediario entre el TUI/Dashboard y el engine Python. El Bridge debía gestionar los
endpoints RAG (`/ovd/rag/seed`, `/ovd/rag/search`) y generar embeddings llamando a un
servicio externo.

Al retomar el proyecto el 2026-04-08 se constató que:
- El Bridge TypeScript **no está implementado** en la estructura actual del repositorio
- Los archivos `src/ovd/bridge.ts`, `src/ovd/rag.ts` referenciados en el ROADMAP no existen
- `rag_seed.py` llamaba a endpoints del Bridge que devolvían "Connection refused"
- La variable `OVD_RAG_ENABLED=false` estaba hardcodeada para evitar errores en runtime

---

## Decisión

Implementar el RAG **directamente en el engine Python** usando:
- `langchain-postgres` (PGVector) para almacenamiento y búsqueda vectorial
- `langchain-ollama` (OllamaEmbeddings + `nomic-embed-text`) para generación de embeddings
- Nuevo módulo `src/engine/rag.py` como punto de entrada único

Se actualizaron para usar `rag.py` directamente:
- `src/engine/rag_seed.py` — `retrieve_context()`, `seed_project()`, `seed_from_file()`
- `src/knowledge/bootstrap.py` — `run()` reemplaza HTTP al Bridge por llamada directa

Los parámetros `bridge_url` y `jwt_token` de `bootstrap.run()` se mantienen por
compatibilidad de firma pero ya no se usan.

---

## Consecuencias

### Positivas
- El RAG funciona hoy sin implementar el Bridge
- Menos capas de indirección para el caso de uso local (un usuario, una instancia)
- `nomic-embed-text` corre nativamente en Ollama sobre Apple Silicon — sin costo de API
- Bootstrap inicial: 1617 chunks indexados (docs/ + src/engine/ + CLAUDE.md)
- Auto-indexación post-ciclo funciona vía `_index_delivery_report` en `graph.py`

### Negativas / trade-offs
- Si en el futuro se implementa el Bridge, el RAG deberá migrarse (refactor acotado)
- El engine Python ahora tiene doble responsabilidad: LangGraph + gestión de vectores
- `psycopg2-binary` fue agregado como dependencia adicional (requerido por `langchain-postgres`)

### Neutras
- La arquitectura multi-tenant por `project_id` se mantiene: cada proyecto tiene su propia
  colección en pgvector (`ovd_project_{project_id}`)
- Las tablas `langchain_pg_collection` y `langchain_pg_embedding` se crean automáticamente

---

## Alternativas consideradas

| Alternativa | Razón de descarte |
|---|---|
| Implementar el Bridge TypeScript primero | Semanas de trabajo antes de tener RAG funcional |
| Usar Anthropic API para embeddings | Costo por llamada, dependencia de internet |
| ChromaDB local | Requiere servicio adicional, pgvector ya está en la DB |

---

## Revisión futura

Cuando se implemente el Bridge TypeScript (FASE SC — SaaS), evaluar si:
1. El RAG migra al Bridge (mejor separación de responsabilidades)
2. O permanece en el engine (menos complejidad operacional)

Referencia: `docs/ROADMAP.md` — FASE SC
