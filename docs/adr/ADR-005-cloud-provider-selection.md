# ADR-005 — Selección de proveedor cloud: DigitalOcean vs alternativas

**Estado:** Decisión tomada
**Fecha:** 2026-05-05
**Contexto:** Sprint S112 — primer despliegue en producción para demo 2026-05-18

---

## Problema

OVD Platform necesita infraestructura cloud para:
1. Ejecutar el engine (FastAPI + LangGraph) en forma continua y accesible públicamente
2. Persistir datos en PostgreSQL con extensión pgvector (RAG)
3. Proveer inferencia LLM para los agentes (modelo de producción)
4. Servir el dashboard React estáticamente

La plataforma fue desarrollada íntegramente en local (Ollama + Docker). El primer despliegue en producción debe estar operativo antes del 2026-05-18.

---

## Opciones evaluadas

| Opción | Infraestructura | Costo estimado/mes | Complejidad |
|--------|-----------------|-------------------|-------------|
| **DigitalOcean App Platform + GenAI** | PaaS managed | ~$85 | Baja |
| AWS ECS + RDS + Bedrock | PaaS semi-managed | ~$120-180 | Alta |
| GCP Cloud Run + Cloud SQL + Vertex | PaaS managed | ~$100-150 | Media |
| Fly.io + Neon | PaaS | ~$40-70 | Media |
| Railway | PaaS | ~$60-90 | Baja |
| VPS (Hetzner / DO Droplet) | IaaS self-managed | ~$30-50 | Alta (ops manual) |

Análisis completo en `docs/CLOUD_ALTERNATIVES.md`.

---

## Decisión: DigitalOcean App Platform + Managed PostgreSQL + GenAI Platform

### Razones principales

1. **GenAI Platform integrado**: DO ofrece serverless inference con 70+ modelos (Claude, Llama, DeepSeek, Mistral) en el mismo ecosistema. API compatible con SDKs oficiales de Anthropic y OpenAI — zero cambios de código, solo variables de entorno.

2. **pgvector nativo**: Managed PostgreSQL 16 en DO incluye pgvector sin configuración adicional. OVD depende de pgvector para el RAG — en AWS/GCP requiere extensiones manuales o instancias especializadas.

3. **Deploy desde Dockerfile**: App Platform usa el `Dockerfile` existente del proyecto sin wrapper adicional (ECS requiere task definitions, Cloud Run requiere Cloud Build).

4. **Dominio propio sin configuración adicional**: DO emite TLS automáticamente al registrar el dominio. El CNAME en Route 53 (AWS) apunta a la URL `*.ondigitalocean.app`.

5. **Costo predecible**: ~$85/mes fijo (engine $50 + postgres $30 + NATS worker ~$5). GenAI Platform es por token, estimado $10-30/mes con la carga de demo.

6. **Tiempo de setup**: App Platform → primer deploy en ~30 min desde CLI (`doctl`). Alternativas como ECS + RDS pueden tomar días de configuración.

### Trade-offs aceptados

- **Vendor lock-in moderado**: `app.yaml` es específico de DO App Platform. Migración a otro PaaS requiere reescribir el spec de deployment (no el código de la app).
- **Región limitada**: NYC como región principal — latencia aceptable desde Chile (~200ms), no óptima.
- **DO GenAI en preview**: Algunos modelos y funcionalidades (guardrails, ADK) están en preview. Para la demo se usan solo modelos GA.

---

## Arquitectura resultante

```
ovd-platform (App Platform, NYC)
├── ovd-engine        — FastAPI + LangGraph (professional-xs, 2vCPU/4GB, $50/mes)
├── ovd-nats          — NATS 2.10 JetStream worker (basic-xxs, 512MB, ~$5/mes)
├── ovd-dashboard     — React estático via nginx (static site, $0)
└── db                — Managed PostgreSQL 16 + pgvector ($30/mes)

Dominio: ovd-platform.codigonet.cloud (CNAME → *.ondigitalocean.app)
DNS: AWS Route 53 (zona codigonet.cloud)
TLS: Let's Encrypt automático via DO

LLM producción: DO GenAI Platform (inference.do-ai.run)
  - Provider: claude (Anthropic-compatible endpoint)
  - Modelo default: claude-sonnet-4-6
  - Configurable por rol via OVD_MODEL_ANALYZER, OVD_MODEL_SDD, etc.
```

---

## Referencias

- `docs/CLOUD_ALTERNATIVES.md` — análisis completo de opciones
- `.do/app.yaml` — spec de deployment
- `ADR-004` — decisión de modelo LLM (Opción D — Claude API/DO GenAI)
- `docs/sprints/CURRENT.md` — gaps C6, C7 (dominio y provider configurable)
