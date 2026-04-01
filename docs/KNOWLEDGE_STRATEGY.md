# OVD Platform — Estrategia de Conocimiento
**Versión:** 1.0
**Fecha:** 2026-03-25
**Autor:** Omar Robles

---

## 1. Declaración estratégica

Un sistema multi-agente es tan bueno como el conocimiento que tiene disponible en el momento de actuar. El OVD tiene dos fuentes de conocimiento que deben gestionarse con estrategia explícita:

1. **Conocimiento del cliente** — todo lo que existe hoy en los proyectos: código, documentación, esquemas de base de datos, decisiones arquitectónicas, contratos de API.
2. **Conocimiento técnico externo** — mejores prácticas, documentación oficial, actualizaciones de frameworks, advisories de seguridad, patrones del dominio.

Sin una estrategia clara para alimentar ambas fuentes, el sistema opera con contexto incompleto, los agentes generan código genérico en lugar de código alineado con el stack real, y el modelo propio tarda meses en especializarse cuando podría hacerlo en semanas.

---

## 2. Problema actual

### Estado del RAG

El RAG actual solo indexa artefactos generados por el propio sistema:

```
doc_type permitidos:
  sdd        → especificaciones generadas en ciclos
  deliverable → código generado en ciclos
  message    → mensajes de agentes durante ciclos
```

**Lo que no está indexado:**
- Código existente del cliente (repositorios anteriores al OVD)
- Documentación técnica (PDFs, Word, HTML, Confluence)
- Esquemas de base de datos (DDL Oracle, SQL Server, scripts de migración)
- Contratos de API (Swagger/OpenAPI, WSDL de servicios Java EE)
- Tickets y decisiones previas (Jira, GitHub Issues, ADRs)
- Runbooks y documentación operacional

### Estado del pipeline de fine-tuning

`export_cycles.py` exporta ciclos completados pero no filtra por:
- `qa_score ≥ umbral` — ciclos de baja calidad contaminan el dataset
- Aprobación humana real — `auto_approve=true` no debe entrar al dataset de entrenamiento
- Completitud de artefactos — ciclos sin SDD completo no aportan valor

---

## 3. Estrategia 1 — Bootstrap de conocimiento existente

### 3.1 Problema que resuelve

Antes de que el equipo ejecute el primer ciclo OVD en un proyecto real, el sistema no sabe nada de ese proyecto. El primer ciclo opera sin contexto histórico. Con la estrategia de bootstrap, el sistema conoce el stack, los patrones de código, las restricciones de la DB y la arquitectura existente desde el día 1.

### 3.2 Pipeline de ingesta multi-formato

```
Fuente de conocimiento existente
            │
            ▼
    Knowledge Ingestion Pipeline
            │
    ┌───────┴────────┐
    │ Tipo de fuente │
    └───────┬────────┘
            │
    ┌───────┼────────────────────────────────┐
    │       │                                │
    ▼       ▼                                ▼
Código   Documentos                    Estructurado
.ts/.py  .pdf/.docx/.html              DDL / Swagger / WSDL
    │       │                                │
    ▼       ▼                                ▼
Chunking  Text extraction             Schema parser →
por       (PyMuPDF/python-docx)       descripción semántica
función   + limpieza                  + restricciones por versión
    │       │                                │
    └───────┴────────────────────────────────┘
                        │
                        ▼
               Embedding (Ollama nomic-embed-text)
                        │
                        ▼
              ovd_rag_documents (pgvector)
              doc_type: "codebase" | "doc" | "schema" | "contract"
```

### 3.3 Nuevos doc_type para el RAG

| doc_type | Fuente | Ejemplo de contenido indexado |
|---|---|---|
| `codebase` | Repositorios de código | Funciones, clases, patrones por archivo |
| `doc` | PDFs, Word, HTML, Confluence | Arquitectura, runbooks, decisiones |
| `schema` | DDL Oracle/PG/MySQL, migrations | Tablas, columnas, restricciones, relaciones |
| `contract` | Swagger/OpenAPI, WSDL | Endpoints, payloads, tipos de datos |
| `ticket` | Jira, GitHub Issues | Contexto de bugs y decisiones de diseño |
| `sdd` | Ciclos OVD | Especificaciones generadas (ya existe) |
| `deliverable` | Ciclos OVD | Código generado (ya existe) |

### 3.4 Herramienta CLI de bootstrap

```bash
# Indexar todo el codebase de un proyecto existente
ovd knowledge bootstrap \
  --project-id 01KMK17YZ5BKEMVAS4XZSTG9AW \
  --source /path/al/repositorio \
  --type codebase \
  --extensions ".ts,.py,.java,.sql"

# Indexar documentación existente
ovd knowledge bootstrap \
  --project-id 01KMK17YZ5BKEMVAS4XZSTG9AW \
  --source /path/a/documentacion \
  --type doc \
  --extensions ".pdf,.docx,.md,.html"

# Indexar esquemas Oracle
ovd knowledge bootstrap \
  --project-id 01KMK17YZ5BKEMVAS4XZSTG9AW \
  --source /path/a/ddl \
  --type schema \
  --db-type oracle \
  --db-version 12c

# Indexar contratos Swagger/WSDL
ovd knowledge bootstrap \
  --project-id 01KMK17YZ5BKEMVAS4XZSTG9AW \
  --source /path/a/swagger.json \
  --type contract
```

### 3.5 Chunking inteligente por tipo de fuente

El chunking genérico (cada N caracteres) destruye la coherencia semántica del código. Cada tipo de fuente tiene su estrategia:

| Tipo | Estrategia de chunking |
|---|---|
| Código `.ts`/`.py`/`.java` | Por función/clase (AST parsing). Un chunk = una función con su docstring |
| DDL SQL | Por tabla. Un chunk = CREATE TABLE + sus COMMENTs + restricciones relevantes |
| PDF/Word | Por sección (headings H1/H2). Respeta la estructura lógica del documento |
| Swagger/OpenAPI | Por endpoint. Un chunk = path + method + request/response schemas |
| WSDL Java EE | Por operación de servicio. Un chunk = operación + tipos de entrada/salida |

### 3.6 Prioridad de bootstrap por proyecto

Para Alemana, el orden recomendado:

```
1. DDL Oracle CAS/CAT/CAV     → los agentes evitan generar SQL incompatible
2. Contratos WSDL Java EE     → los agentes conocen las APIs existentes
3. Codebase Java/Python        → los agentes generan código en el mismo estilo
4. Documentación técnica       → runbooks, arquitectura, decisiones previas
5. Tickets históricos          → contexto de bugs y restricciones no documentadas
```

---

## 4. Estrategia 2 — Aceleración del modelo propio con datos sintéticos

### 4.1 El problema de la "arranque en frío"

Sin datos sintéticos, el primer fine-tuning significativo requiere ~200 ciclos reales aprobados. Con un ritmo inicial de 5–10 ciclos por semana, eso toma 3–6 meses.

Los datos sintéticos permiten llegar a M2 en **semanas**, no meses.

### 4.2 Generación de datos sintéticos

La estrategia usa Claude API para generar ejemplos de entrenamiento etiquetados sobre el stack real del cliente, antes de que el primer ciclo se ejecute.

```
Stack Registry (conocido)
        +
Patrones del codebase indexado (conocido)
        +
Claude API (generador)
        │
        ▼
Ejemplos sintéticos en formato instruction-tuning
        │
        ▼
Validación de calidad (validate_dataset.py)
        │
        ▼
Mezclado con ciclos reales (ratio: 30% sintético, 70% real)
        │
        ▼
Fine-tuning LoRA más efectivo y más rápido
```

### 4.3 Tipos de ejemplos sintéticos a generar

| Tipo | Descripción | Volumen inicial |
|---|---|---|
| FR → análisis estructurado | Feature requests variados del dominio del cliente → FRAnalysisOutput correcto | 100 ejemplos |
| FR → SDD completo | Features del stack del cliente → especificación requirements/design/constraints/tasks | 50 ejemplos |
| DDL Oracle 12c → consulta correcta | Consultas que NO usen funciones inexistentes en 12c | 80 ejemplos |
| DDL Oracle 12c → error a corregir | El modelo aprende a identificar SQL incompatible | 40 ejemplos |
| Código Java EE → refactor moderno | Patrones Struts 1.3/EJB → Spring Boot equivalente | 30 ejemplos |
| QA review → score estructurado | Código generado → evaluación QA con score, issues, owasp | 50 ejemplos |

**Total estimado: 350 ejemplos sintéticos.** Con 200 ciclos reales, el dataset de M2 tiene ~550 ejemplos, suficiente para un fine-tuning sólido.

### 4.4 Control de calidad de los datos sintéticos

Los datos sintéticos de baja calidad son peores que no tener datos — degeneran el modelo.

Criterios de inclusión:
- Generado por Claude Opus o Sonnet (no Haiku — la calidad importa aquí)
- Revisado por un humano en muestra aleatoria del 10%
- Validado por `validate_dataset.py` antes de incluir en el dataset final
- Marcado con `"source": "synthetic"` en el metadata del JSONL para auditoría futura
- Ratio máximo de sintéticos en cualquier batch de fine-tuning: 40%

### 4.5 Proceso de generación (script)

```bash
# Generar dataset sintético para el stack del proyecto
python src/finetune/generate_synthetic.py \
  --project-id 01KMK17YZ5BKEMVAS4XZSTG9AW \
  --stack-profile /path/to/profile.json \
  --count 350 \
  --output data/synthetic_alemana_v1.jsonl \
  --generator-model claude-opus-4-6

# Validar antes de usar
python src/finetune/validate_dataset.py \
  --input data/synthetic_alemana_v1.jsonl \
  --report

# Mezclar con ciclos reales
python src/finetune/merge_datasets.py \
  --real data/real_cycles.jsonl \
  --synthetic data/synthetic_alemana_v1.jsonl \
  --max-synthetic-ratio 0.40 \
  --output data/training_v1.jsonl
```

---

## 5. Estrategia 3 — Investigación web continua con fuentes fiables

### 5.1 Principio: calidad sobre cantidad

El RAG contaminado con información incorrecta o desactualizada es peor que un RAG vacío. La investigación web debe filtrar activamente para incluir solo fuentes confiables.

### 5.2 Fuentes confiables por categoría

**Documentación oficial (máxima prioridad):**
| Categoría | Fuente | Tipo de información |
|---|---|---|
| Oracle | docs.oracle.com | SQL compatibility por versión, PL/SQL, tuning |
| Java EE / Jakarta EE | jakarta.ee, javaee.github.io | Especificaciones EJB, JAX-RS, JPA |
| TypeScript | typescriptlang.org/docs | Language spec, release notes |
| Bun | bun.sh/docs | Runtime APIs, performance, compatibility |
| Hono | hono.dev/docs | Middleware, routing, deployment |
| PostgreSQL | postgresql.org/docs | Query optimization, extensions, pgvector |
| LangGraph | langchain-ai.github.io/langgraph | Graph patterns, interrupts, checkpointing |

**Seguridad (alta prioridad):**
| Fuente | Información |
|---|---|
| nvd.nist.gov | CVEs relevantes a los stacks utilizados |
| owasp.org | OWASP Top 10 actualizados |
| cve.mitre.org | Vulnerabilidades por paquete |

**Técnicas curadas (media prioridad):**
| Fuente | Criterio de calidad |
|---|---|
| Stack Overflow | Solo respuestas con score ≥ 50 y aceptadas |
| GitHub | Solo READMEs de repos con ≥ 1000 stars en tecnologías del stack |
| Martin Fowler's blog | Artículos de arquitectura y patrones |
| The Pragmatic Engineer | Newsletter técnico de calidad |

**Fuentes excluidas:**
- Blogs personales sin reputación verificable
- Medium/Dev.to sin autor reconocido
- Documentación de versiones obsoletas (Oracle 9i, Java 1.4, etc.)
- Contenido generado por AI sin revisión humana verificable

### 5.3 Integración con el Web Researcher Agent (Sprint 11)

El Web Researcher tiene dos modos de operación:

```
MODO REACTIVO (durante ciclos)
  Cuando el agente encuentra incertidumbre durante un FR
  → busca en las fuentes configuradas
  → indexa el resultado en el RAG del proyecto
  → el agente continúa con contexto actualizado

MODO PROACTIVO (programado, sin FR activo)
  Nightly job: monitorea fuentes oficiales para el stack del workspace
  → detecta nuevas releases, deprecaciones, CVEs
  → indexa automáticamente en el RAG de la org (doc_type: "tech_update")
  → si detecta CVE relevante: genera alerta via NATS → webhook → notificación
```

### 5.4 Priorización del contenido indexado por relevancia al stack

No todo el contenido de una fuente confiable es relevante. El indexado filtra por relevancia al Stack Registry:

```
Workspace con Oracle 12c + Java EE:
  ✅ Indexar: Oracle 12c SQL reference, EJB 3.0 spec, Struts 1.3 migration guide
  ❌ Ignorar: PostgreSQL docs, React tutorials, Kubernetes guides

Workspace con TypeScript + Bun + Hono:
  ✅ Indexar: Bun runtime docs, Hono middleware guide, TypeScript 5.x release notes
  ❌ Ignorar: Oracle docs, Java EE specs
```

La relevancia la determina el Stack Registry del workspace — otra razón por la que el Stack Registry estructurado (Sprint 8) es un prerequisito de esta estrategia.

---

## 6. Corrección de export_cycles.py (prerequisito M1)

El filtro actual de `export_cycles.py` no garantiza calidad del dataset. Debe actualizarse:

```python
# Filtros requeridos para incluir un ciclo en el dataset de fine-tuning:

QUALITY_FILTERS = {
    "min_qa_score": 0.80,          # QA score mínimo
    "require_human_approval": True, # auto_approve=True excluye el ciclo
    "require_complete_sdd": True,   # SDD con requirements + design + tasks
    "max_retry_count": 2,           # ciclos con > 2 reintentos de QA son ruidosos
    "status": "done",               # solo ciclos completados
    "exclude_auto_approve": True,   # auto_approve es solo para CI/CD, no para entrenamiento
}
```

**Impacto:** sin este filtro, ciclos de baja calidad o generados automáticamente contaminan el modelo. Con el filtro, cada ejemplo que entra al dataset es una decisión humana validada.

---

## 7. Resumen de gaps vs. estado actual

| Componente | Estado actual | Gap | Sprint |
|---|---|---|---|
| RAG indexa solo ciclos OVD | Parcial | No indexa código, docs, DDL, Swagger existentes | S8 (nuevos doc_type) |
| CLI de bootstrap de conocimiento | No existe | Herramienta para onboardear proyectos existentes | S8.F |
| Chunking por tipo de fuente | No existe | Chunking genérico (por caracteres) | S8.F |
| Datos sintéticos para fine-tuning | No existe | Script `generate_synthetic.py` + merge | SM1 (nuevo) |
| export_cycles.py con filtros de calidad | Incompleto | Sin filtro por qa_score ni human_approval | SM1 |
| Web Researcher reactivo | Planificado | Sprint 11 | S11 |
| Web Researcher proactivo (nightly) | No existe | Monitoreo de fuentes oficiales programado | S11.G (nuevo) |
| Fuentes curadas configuradas por org | No existe | Lista de fuentes por stack en Stack Registry | S11 |

---

## 8. Impacto esperado en el modelo propio

Con las tres estrategias combinadas:

```
SIN estrategia de conocimiento:
  Tiempo a M2 (primer modelo activo): 6–9 meses
  Calidad del dataset: ciclos reales sin filtrar
  Contexto en ciclos: solo artefactos generados por OVD

CON estrategia de conocimiento:
  Tiempo a M2: 4–8 semanas
    - 350 ejemplos sintéticos de alta calidad desde el día 1
    - RAG enriquecido con codebase + schemas + docs existentes
    - Ciclos reales con contexto histórico → mejor calidad → mejor dataset
  Calidad del dataset: filtrado por qa_score + aprobación humana + completitud
  Contexto en ciclos: codebase completo + documentación + patrones históricos + web
```

---

*Documento vivo — actualizar al completar cada sprint de ingesta de conocimiento.*
