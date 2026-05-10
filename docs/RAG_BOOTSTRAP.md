# RAG Bootstrap — Guía Operativa

Documento el proceso completo para indexar conocimiento en el RAG de OVD Platform,
tanto en entorno local como en producción (DigitalOcean App Platform).

---

## Arquitectura del RAG

```
Fuente (archivos .py / .md)
        ↓
knowledge/bootstrap.py  → chunking por tipo de documento
        ↓
rag.py → genera embeddings vía proveedor configurado
        ↓
pgvector (langchain_pg_embedding) → almacena vector + texto + metadatos
```

### Metadatos por chunk

| Campo | Descripción | Ejemplo |
|---|---|---|
| `org_id` | ULID del organización | `01KMK160F1TJ807Z0BDSJD504D` |
| `project_id` | Slug del proyecto | `ovd-platform` |
| `doc_type` | Tipo de documento | `codebase`, `doc`, `delivery`, `lesson_backend` |
| `source` | Ruta del archivo fuente | `/app/api.py` |

---

## Entornos

### Local (desarrollo)

| Variable | Valor |
|---|---|
| Modelo de embeddings | `nomic-embed-text` vía Ollama |
| Dimensiones | 768 |
| Base de datos | `postgresql://ovd_dev:changeme@localhost:5432/ovd_dev` |
| Contenedor PostgreSQL | `postgres_db` (Docker) |

### Producción (DigitalOcean)

| Variable | Valor |
|---|---|
| Modelo de embeddings | `bge-m3` vía DO GenAI Serverless Inference |
| Dimensiones | 1024 |
| Endpoint | `https://inference.do-ai.run/v1` |
| Base de datos | DO Managed PostgreSQL (`ovd-postgres-prod`, cluster NYC3) |
| Puerto | 25060 (SSL requerido) |

> **Nota importante:** Local y producción usan modelos distintos con dimensiones
> diferentes. Los vectores NO son compatibles entre entornos — no se pueden copiar
> directamente. Para migrar, hay que re-embeber el texto original.

---

## Autenticación DO GenAI (lección aprendida)

DO GenAI tiene tres tipos de tokens con propósitos distintos:

| Tipo | Prefijo | Sirve para |
|---|---|---|
| Personal Access Token | `dop_v1_*` | Serverless Inference API ✓ |
| Model Access Key | `doo_v1_*` | Agent Inference (NO intercambiable) |
| OAuth App Token | `doo_v1_*` | Solo aplicaciones OAuth |

**El token correcto para `inference.do-ai.run/v1/embeddings` es el Personal Access Token (`dop_v1_*`).**

Los Model Access Keys creados en "INFERENCE → Manage" retornan `403 Forbidden`
en el endpoint de embeddings aunque el modelo esté seleccionado. El error
`"You are not authorized to perform this operation"` es la señal de que se
está usando el tipo de token incorrecto.

Para verificar que un token funciona:

```bash
curl -X POST https://inference.do-ai.run/v1/embeddings \
  -H "Authorization: Bearer dop_v1_TU_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "bge-m3", "input": ["texto de prueba"]}'
# Respuesta esperada: {"data": [{"embedding": [...1024 floats...]}]}
```

---

## Bootstrap de codebase (producción)

```bash
cd src/engine && \
  OPENAI_API_KEY=dop_v1_TU_TOKEN \
  OPENAI_BASE_URL=https://inference.do-ai.run/v1 \
  OVD_RAG_EMBEDDING_PROVIDER=openai \
  OVD_EMBED_MODEL=bge-m3 \
  DATABASE_URL="postgresql://doadmin:PASSWORD@ovd-postgres-prod-do-user-246170-0.h.db.ondigitalocean.com:25060/defaultdb?sslmode=require" \
  .venv/bin/python scripts/rag_bootstrap.py \
    --org-id 01KMK160F1TJ807Z0BDSJD504D \
    --project-id ovd-platform \
    --path /ruta/a/src/engine \
    --doc-type codebase \
    --clear
```

> `--clear` borra chunks previos del mismo `project_id` antes de indexar.
> Omitir `--clear` para agregar sin borrar (ej. al indexar docs después del codebase).

## Bootstrap de documentación (producción)

```bash
cd src/engine && \
  OPENAI_API_KEY=dop_v1_TU_TOKEN \
  OPENAI_BASE_URL=https://inference.do-ai.run/v1 \
  OVD_RAG_EMBEDDING_PROVIDER=openai \
  OVD_EMBED_MODEL=bge-m3 \
  DATABASE_URL="postgresql://doadmin:PASSWORD@ovd-postgres-prod-do-user-246170-0.h.db.ondigitalocean.com:25060/defaultdb?sslmode=require" \
  .venv/bin/python scripts/rag_bootstrap.py \
    --org-id 01KMK160F1TJ807Z0BDSJD504D \
    --project-id ovd-platform \
    --path /ruta/a/docs \
    --doc-type doc
```

## Bootstrap desde el contenedor DO (alternativa)

Si se necesita correr desde dentro del App Platform (no recomendado — preferir desde Mac):

```bash
# Abrir consola del contenedor
doctl apps console APP_ID ovd-engine

# Dentro del contenedor — PYTHONPATH requerido
PYTHONPATH=/app python scripts/rag_bootstrap.py \
  --org-id 01KMK160F1TJ807Z0BDSJD504D \
  --project-id ovd-platform \
  --path /app \
  --doc-type codebase \
  --clear
```

> **Nota:** El módulo `knowledge/` debe estar incluido en la imagen Docker.
> Se encuentra en `src/engine/knowledge/` (copiado desde `src/knowledge/`).
> Si no está en la imagen, el script falla con `ModuleNotFoundError: No module named 'knowledge'`.

---

## Bootstrap local

```bash
cd src/engine && \
  OVD_RAG_EMBEDDING_PROVIDER=ollama \
  OVD_EMBED_MODEL=nomic-embed-text \
  DATABASE_URL="postgresql://ovd_dev:changeme@localhost:5432/ovd_dev" \
  .venv/bin/python scripts/rag_bootstrap.py \
    --org-id 01KMK160F1TJ807Z0BDSJD504D \
    --project-id ovd-platform \
    --path src/engine \
    --doc-type codebase \
    --clear
```

---

## Estado del RAG local (2026-05-09)

| org_id | project_id | doc_type | chunks |
|---|---|---|---|
| `01KMK160F1TJ807Z0BDSJD504D` | `ovd-platform` | codebase | 5.946 |
| `01KMK160F1TJ807Z0BDSJD504D` | `ovd-platform` | doc | 3.611 |
| `01KMK160F1TJ807Z0BDSJD504D` | `ovd-platform` | delivery + lessons | 9 |
| `01KMK160F1TJ807Z0BDSJD504D` | `contratos-beneficios` | lessons | 3 |
| `01KMK160F1TJ807Z0BDSJD504D` | `turnos-medicos-s111*` | delivery + lessons | 21 |
| `ORG_OMAR_ROBLES` | `PROJ_CONTRATOS_BENEFICIOS` | delivery + lessons | 465 |
| `ORG_OMAR_ROBLES` | `PROJ_TURNOS_MEDICOS` | delivery + lessons | 14 |
| `ORG_OMAR_ROBLES` | otros proyectos | delivery + lessons | 69 |

**Total local: ~10.161 chunks**

> Los chunks `delivery` y `lesson_*` son generados automáticamente por el engine
> durante los ciclos. No se pueden re-generar con bootstrap — solo volviendo a
> ejecutar los ciclos. Valor alto: representan aprendizaje acumulado de proyectos reales.

---

## Tipos de documentos soportados

| `doc_type` | Fuente | Quién lo genera |
|---|---|---|
| `codebase` | Archivos `.py`, `.ts`, `.tsx`, `.rs`, `.java`, `.sql` | Bootstrap manual |
| `doc` | Archivos `.md` de `docs/` | Bootstrap manual |
| `schema` | DDL SQL, modelos ORM | Bootstrap manual |
| `contract` | OpenAPI specs, contratos | Bootstrap manual |
| `ticket` | Issues, especificaciones | Bootstrap manual |
| `delivery` | Informes de entrega de ciclos | Auto — `_index_delivery_report()` en `graph.py` |
| `lesson_*` | Postmortems y QA findings | Auto — al final de cada ciclo |

---

## Roadmap de mejoras pendientes

### Iteración 3 — Consolidar org_ids (pendiente)
Hay 4 org_ids distintos para el mismo usuario en el RAG local.
El canónico es `01KMK160F1TJ807Z0BDSJD504D`.
Los chunks bajo `ORG_OMAR_ROBLES`, `omar`, `test` deben re-indexarse.

### Iteración 3 — Fix colisión multi-tenant (pendiente)
El `collection_name` actual es `ovd_project_{project_id}`.
Si dos orgs distintas tienen el mismo `project_id`, colisionan.
Fix propuesto: `ovd_{org_id[:8]}_{project_id}`.

### Iteración 4 — Bootstrap por proyecto con configuración declarativa (futuro)
Script `scripts/bootstrap_project.py` con mapa de proyectos y fuentes,
para indexar múltiples proyectos de clientes desde un solo comando.

### Migración local → producción (pendiente)
Los 465 chunks de `PROJ_CONTRATOS_BENEFICIOS` (deliveries + lessons) no tienen
archivo fuente para re-bootstrapear. Plan de migración:
1. Exportar texto original de `langchain_pg_embedding.document`
2. Re-embeber con `bge-m3` via DO GenAI
3. Insertar en producción con los mismos metadatos
