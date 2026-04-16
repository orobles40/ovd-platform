# OVD Platform — Alternativas de Despliegue Cloud

**Fecha:** 2026-04-16
**Relacionado con:** ROADMAP.md FASE 5 — GAP-CLOUD-01 a GAP-CLOUD-09

Este documento analiza las alternativas para desplegar OVD Platform en cloud, con costos aproximados en USD/mes y recomendación según el perfil de uso actual (equipo interno de Omar Robles, sin SaaS todavía).

---

## 1. Requisitos mínimos del sistema

| Componente | Requisito mínimo | Notas |
|-----------|-----------------|-------|
| Engine FastAPI | 2 vCPU, 4 GB RAM | LangGraph + asyncio. Con Ollama: 8 GB RAM |
| PostgreSQL 16 + pgvector | 1 GB RAM, 20 GB SSD | Checkpoints LangGraph + embeddings RAG |
| NATS JetStream | 256 MB RAM | Bus de eventos entre Engine y RAG |
| Dashboard nginx | 128 MB RAM | Sirve archivos estáticos del build Vite |
| Ollama (si en cloud) | 8 GB RAM + GPU opcional | `nomic-embed-text` ~274 MB, `qwen2.5-coder:7b` ~4 GB |

**Sin Ollama en cloud (embeddings vía OpenAI API):** un VPS de 4 GB RAM es suficiente.
**Con Ollama en cloud:** mínimo 8 GB RAM. GPU no obligatoria para embeddings.

---

## 2. Alternativas de VPS

### Opción A — DigitalOcean (Recomendada para empezar)

| Plan | vCPU | RAM | SSD | Precio/mes | Aplica para OVD |
|------|------|-----|-----|-----------|-----------------|
| Basic 4 GB | 2 | 4 GB | 80 GB | $24 | Sin Ollama en cloud |
| Basic 8 GB | 2 | 8 GB | 160 GB | $48 | Con Ollama embeddings |
| CPU-Opt 8 GB | 4 | 8 GB | 100 GB | $68 | Con Ollama + LLM |

**Pros:**
- Panel simple, documentación excelente
- Snapshots automáticos ($1/GB/mes para backup)
- Managed PostgreSQL disponible si se quiere separar la BD ($15/mes adicional)
- Datacenter en São Paulo (latencia baja desde Chile)
- Firewall incluido sin costo adicional

**Contras:**
- Precio/rendimiento ligeramente inferior a Hetzner en Europa

**Costo estimado OVD (sin Ollama cloud):** ~$24-28/mes (droplet + snapshot)

---

### Opción B — Hetzner Cloud (Mejor precio/rendimiento global)

| Plan | vCPU | RAM | SSD | Precio/mes | Aplica para OVD |
|------|------|-----|-----|-----------|-----------------|
| CX22 | 2 | 4 GB | 40 GB | €4.5 (~$5) | Sin Ollama en cloud |
| CX32 | 4 | 8 GB | 80 GB | €8.5 (~$9) | Con Ollama embeddings |
| CX42 | 8 | 16 GB | 160 GB | €16 (~$17) | Con Ollama + LLM pequeño |

**Pros:**
- El mejor precio/rendimiento del mercado europeo
- Incluye 20 TB de tráfico saliente
- Snapshots a €0.012/GB
- Datacenter en Virginia (US) o Falkenstein/Nuremberg (EU)

**Contras:**
- Sin datacenter en Latinoamérica (latencia ~180ms desde Chile vs ~100ms DigitalOcean SP)
- Soporte menos reactivo que DO para incidencias críticas

**Costo estimado OVD (sin Ollama cloud):** ~$6-8/mes (CX22 + snapshot)

---

### Opción C — AWS EC2 (Mayor madurez, más complejo)

| Instancia | vCPU | RAM | Precio/mes (on-demand) | Precio/mes (reserved 1yr) |
|-----------|------|-----|----------------------|--------------------------|
| t3.medium | 2 | 4 GB | ~$30 | ~$19 |
| t3.large | 2 | 8 GB | ~$60 | ~$38 |
| t3a.xlarge | 4 | 16 GB | ~$108 | ~$69 |

**Pros:**
- Ecosistema completo: RDS, S3, CloudWatch, ECS
- RDS PostgreSQL Managed con backup automático (~$15-25/mes adicional)
- S3 para backups de BD ($0.023/GB/mes)
- Alta disponibilidad nativa (Multi-AZ, Auto Scaling)

**Contras:**
- Precio significativamente más alto que DO o Hetzner
- Complejidad operacional alta para un equipo pequeño
- Costo real aumenta con egress, snapshots, IPs públicas, etc.

**Costo estimado OVD:** ~$45-80/mes (EC2 + EBS + S3 backups + IP)

---

### Opción D — Fly.io (Orientado a containers, fácil deploy)

| Plan | vCPU | RAM | Precio/mes |
|------|------|-----|-----------|
| shared-cpu-2x | 2 (shared) | 4 GB | ~$18 |
| performance-2x | 2 | 4 GB | ~$45 |

**Pros:**
- `fly deploy` — un comando para desplegar desde Docker
- Certificados TLS automáticos incluidos
- Múltiples regiones disponibles (GRU São Paulo)
- Postgres managed con backup incluido ($0.15/GB/mes)

**Contras:**
- Shared CPU throttleado — no adecuado para LangGraph con ciclos largos
- PostgreSQL managed de Fly.io no soporta extensión `pgvector` nativa todavía
- Logs y observabilidad más limitada

**Costo estimado OVD:** ~$30-50/mes — no recomendado por limitación pgvector

---

### Opción E — Railway (Más simple aún, para prototipos)

| Componente | Costo |
|-----------|-------|
| Engine container | $5/mes base + $0.000463/vCPU·s |
| PostgreSQL plugin | $5/mes base + $0.000231/GB·s |
| Total estimado | $15-25/mes (uso moderado) |

**Pros:**
- Deploy desde GitHub en minutos sin configuración de servidor
- PostgreSQL con pgvector disponible como plugin
- Dominios con TLS automático

**Contras:**
- Pricing variable — puede subir con uso intensivo de CPU (LangGraph consume bastante en ciclos complejos)
- Sin control directo del servidor
- No adecuado si se procesan datos sensibles de clientes (Alemana)

---

## 3. Comparativa de opciones

| Criterio | DO $24 | Hetzner $9 | AWS t3.medium | Fly.io | Railway |
|----------|--------|-----------|--------------|--------|---------|
| Precio/mes | $24 | $9 | $45 | $30 | $20* |
| Latencia Chile | ~100ms | ~180ms | ~120ms | ~110ms | ~120ms |
| pgvector | manual | manual | RDS no incluye | ⚠️ | ✅ plugin |
| TLS automático | nginx+certbot | nginx+certbot | nginx+certbot | ✅ | ✅ |
| Backup BD | snapshot $1/GB | snapshot €0.01/GB | RDS +$15/mes | incluido | incluido |
| Ollama posible | ✅ (8GB plan) | ✅ (CX32 $9) | ✅ (t3.large) | ❌ shared | ❌ |
| Datos sensibles | ✅ VPS dedicado | ✅ VPS dedicado | ✅ | ⚠️ | ⚠️ |
| Complejidad setup | Media | Media | Alta | Baja | Muy baja |

*Railway: precio variable según CPU usage

---

## 4. Decisión sobre Ollama en cloud

### Opción A — Ollama en el mismo VPS

**Ventaja:** sin cambios en el código. `OVD_EMBEDDING_MODEL=nomic-embed-text` sigue igual.

**Desventaja:** requiere VPS de 8 GB RAM mínimo. Con `qwen2.5-coder:7b` necesita 8+ GB adicionales para LLM.

**Costo adicional:** diferencia entre plan 4 GB ($24) y 8 GB ($48) en DO = **+$24/mes**.

### Opción B — Embeddings vía OpenAI API (Recomendada)

Migrar `nomic-embed-text` a `text-embedding-3-small` de OpenAI:

| Métrica | Ollama local | OpenAI text-embedding-3-small |
|---------|-------------|-------------------------------|
| Costo | $0 (hardware local) | $0.02/1M tokens |
| Latencia | ~50ms | ~200ms |
| Disponibilidad | Depende del Mac | 99.9% SLA |
| Cambio de código | Ninguno | `langchain-openai`, 1 env var |

**Estimado de costo:** con 1617 chunks (~800 tokens c/u promedio) = 1.3M tokens/bootstrap completo = **$0.026 por bootstrap**. Consultas RAG durante ciclos: ~100 queries/ciclo × ~500 tokens = 50K tokens/ciclo = **$0.001/ciclo**. Prácticamente cero costo.

**Recomendación: Opción B** — VPS 4 GB + OpenAI embeddings. Ahorra $24/mes y elimina la complejidad de Ollama en server.

---

## 5. Stack recomendado (MVP cloud)

```
VPS: Hetzner CX22 (~$9/mes) o DigitalOcean 4GB (~$24/mes)
OS: Ubuntu 22.04 LTS
Docker + Docker Compose (sin Swarm, sin Kubernetes)

Servicios:
  ovd-engine     → FastAPI + LangGraph (puerto interno 8001)
  ovd-postgres   → pgvector/pgvector:pg16 (puerto interno 5432)
  ovd-nats       → nats:2.10-alpine (puerto interno 4222)
  ovd-dashboard  → nginx sirviendo el build React (puerto interno 80)
  nginx-proxy    → reverse proxy público con TLS Let's Encrypt

Embeddings: OpenAI text-embedding-3-small (en lugar de Ollama)
LLMs agentes:  Claude Sonnet / Haiku (API Anthropic) + OpenAI GPT-4o-mini
Backup BD:     pg_dump diario → Backblaze B2 (~$0.006/GB/mes)
```

**Costo mensual estimado:**

| Concepto | Costo |
|---------|-------|
| VPS Hetzner CX22 | $9 |
| Dominio `.dev` (anual / 12) | $1.5 |
| Backblaze B2 backup (5 GB) | $0.03 |
| OpenAI embeddings | $0.05 |
| Claude API (ciclos del equipo) | variable |
| **Total infraestructura fija** | **~$11/mes** |

---

## 6. Modelos potentes en cloud — DeepSeek + Qwen

> Escenario: agente principal con razonamiento profundo (arquitectura/SDD) + agentes especializados de código de mayor calidad que el `qwen2.5-coder:7b` actual.

### 6.1 Aclaración importante sobre DeepSeek-V3

**DeepSeek-V3 (671B MoE) no es desplegable en un VPS.** En Q4 ocupa ~200 GB de RAM. Requiere un clúster de GPUs A100/H100.

Lo que sí es viable en cloud son las **versiones destiladas de DeepSeek-R1**, que mantienen buena capacidad de razonamiento:

| Modelo | Parámetros | RAM requerida (Q4_K_M) | Velocidad CPU (8 vCPU) | Velocidad GPU (RTX 4090) |
|--------|-----------|----------------------|----------------------|-------------------------|
| deepseek-r1:7b | 7B | ~5 GB | ~20 tok/s | ~120 tok/s |
| deepseek-r1:14b | 14B | ~9 GB | ~12 tok/s | ~80 tok/s |
| deepseek-r1:32b | 32B | ~20 GB | ~5 tok/s | ~40 tok/s |
| deepseek-r1:70b | 70B | ~42 GB | ~2 tok/s | inviable 24GB VRAM |

---

### 6.2 Modelos candidatos por rol en OVD

#### Agente principal — Razonamiento y arquitectura (analyze_fr + generate_sdd)

| Modelo | RAM Q4 | Fortaleza | Debilidad |
|--------|--------|-----------|-----------|
| **deepseek-r1:14b** ⭐ | ~9 GB | Razonamiento cadena de pensamiento, arquitectura de software | Lento en CPU (12 tok/s) |
| deepseek-r1:32b | ~20 GB | Mejor calidad SDD, más contexto | Necesita 32+ GB RAM total |
| qwen2.5:14b | ~9 GB | Buena comprensión, multilingüe | Menor razonamiento que R1 |
| mistral-small3.1:22b | ~13 GB | Balance razonamiento + velocidad | Menos especializado en código |

**Recomendado: `deepseek-r1:14b`** — el mejor balance calidad/RAM. Razonamiento explícito (chain-of-thought visible), ideal para `analyze_fr` y `generate_sdd`.

#### Agentes especializados — Implementación de código (backend / frontend / database / devops)

| Modelo | RAM Q4 | Fortaleza | Debilidad |
|--------|--------|-----------|-----------|
| **qwen2.5-coder:14b** ⭐ | ~9 GB | Salto de calidad sobre 7B, mismo modelo base | Doble de RAM que 7B |
| qwen2.5-coder:7b | ~5 GB | Actual en uso, rápido | Calidad limitada en Oracle/Java |
| qwen2.5-coder:32b | ~20 GB | Mejor calidad de código | Necesita 32+ GB RAM total |
| deepseek-coder-v2:16b | ~10 GB | Fuerte en Python/TypeScript | Menos maduro en Oracle/Java |
| codestral:22b | ~13 GB | Modelo Mistral especializado en código | No disponible en Ollama aún |

**Recomendado: `qwen2.5-coder:14b`** — mejora concreta sobre el 7B actual (mejor razonamiento en contextos Java/Oracle), sin triplicar la RAM.

#### Embeddings RAG

| Modelo | RAM | Calidad | Costo |
|--------|-----|---------|-------|
| nomic-embed-text (actual) | ~274 MB | Buena | $0 |
| mxbai-embed-large | ~670 MB | Mejor en código | $0 |
| OpenAI text-embedding-3-small | 0 (API) | Comparable | $0.02/1M tokens |

**En cloud con RAM ajustada:** preferir OpenAI embeddings (0 RAM local).

---

### 6.3 Configuraciones recomendadas en DigitalOcean

#### Configuración A — CPU pura, equilibrio (recomendada para empezar)

```
Droplet: General Purpose g-8vcpu-32gb
  vCPU: 8 dedicados | RAM: 32 GB | SSD: 100 GB | Precio: ~$252/mes

Modelos Ollama:
  Agente principal:    deepseek-r1:14b     Q4_K_M  ~9 GB
  Agentes código:      qwen2.5-coder:14b   Q4_K_M  ~9 GB
  Embeddings:          nomic-embed-text            ~274 MB

Memoria estimada en uso:
  OS + Docker:         ~2 GB
  Engine + Postgres + NATS + Dashboard:  ~3 GB
  Ollama (1 modelo en memoria a la vez): ~9 GB
  Buffer:              ~9 GB
  Total:               ~23 GB de 32 GB  ← viable
```

**Consideración clave:** Ollama mantiene 1 modelo cargado en RAM a la vez por defecto. Al cambiar de modelo (de R1 a Coder), hay un swap de ~5-10 segundos. Configurable con `OLLAMA_MAX_LOADED_MODELS=2` si la RAM lo permite.

**Velocidad de ciclo estimada (CPU, sin GPU):**
- analyze_fr (R1:14b, ~300 tokens): ~25 segundos
- generate_sdd (R1:14b, ~800 tokens): ~67 segundos
- 4 agentes código (Coder:14b, ~600 tokens c/u): ~200 segundos
- **Total estimado por ciclo: ~5-7 minutos** (vs 2-3 min actual con Claude API)

---

#### Configuración B — CPU con modelos más potentes (mayor calidad, más costo)

```
Droplet: Memory-Optimized m-8vcpu-64gb
  vCPU: 8 dedicados | RAM: 64 GB | SSD: 50 GB | Precio: ~$420/mes

Modelos Ollama:
  Agente principal:    deepseek-r1:32b     Q4_K_M  ~20 GB
  Agentes código:      qwen2.5-coder:32b   Q4_K_M  ~20 GB
  Embeddings:          nomic-embed-text            ~274 MB

Memoria estimada en uso:
  OS + servicios:      ~5 GB
  Ollama (2 modelos simultáneos): ~40 GB
  Buffer:              ~19 GB
  Total:               ~45 GB de 64 GB  ← viable con OLLAMA_MAX_LOADED_MODELS=2
```

**Velocidad de ciclo estimada:**
- analyze_fr (R1:32b): ~3 tok/s → 100 tokens = ~33 segundos
- generate_sdd (R1:32b): 800 tokens = ~267 segundos
- **Total estimado por ciclo: ~12-15 minutos** — lento para uso intensivo

---

#### Configuración C — Híbrida (infraestructura barata + API de inferencia) ⭐ RECOMENDADA

La mejor relación costo/calidad/velocidad para uso intermitente de equipo:

```
Droplet: Basic 4 GB / $24 mes (o Hetzner CX22 / $9 mes)
  Solo servicios: Engine + Postgres + NATS + Dashboard

Agente principal (razonamiento) → Groq Cloud API:
  Modelo:   deepseek-r1-distill-llama-70b
  Velocidad: ~300 tok/s (30x más rápido que CPU local)
  Costo:     $0.75/M tokens entrada + $0.99/M tokens salida

Agentes código → Together.ai API:
  Modelo:   Qwen2.5-Coder-32B-Instruct
  Velocidad: ~100 tok/s
  Costo:     $0.80/M tokens entrada + $0.80/M tokens salida

Embeddings → OpenAI:
  Modelo:   text-embedding-3-small
  Costo:    $0.02/1M tokens
```

**Costo de API por ciclo OVD (estimado):**
- analyze_fr + generate_sdd (R1, ~3K tokens): ~$0.004
- 4 agentes código (Coder32B, ~8K tokens total): ~$0.013
- **Costo por ciclo: ~$0.017 (menos de 2 centavos)**
- 100 ciclos/mes: ~$1.70 en APIs de modelos

**Velocidad de ciclo:** 1-3 minutos (vs 5-7 min CPU o 12-15 min CPU 32B)

---

### 6.4 Comparativa de configuraciones

| | Config A (CPU 32GB) | Config B (CPU 64GB) | Config C Híbrida ⭐ |
|--|--------------------|--------------------|-------------------|
| VPS/mes | $252 | $420 | $24 |
| API modelos/mes (100 ciclos) | $0 | $0 | ~$2 |
| **Total/mes** | **$252** | **$420** | **~$26** |
| Calidad razonamiento | R1:14b (buena) | R1:32b (excelente) | R1:70B via Groq (excelente) |
| Calidad código | Coder:14b (buena) | Coder:32b (excelente) | Coder:32B via Together (excelente) |
| Velocidad por ciclo | ~6 min | ~13 min | ~2 min |
| Sin dependencia API | ✅ | ✅ | ❌ (requiere Groq + Together) |
| Datos en cloud propio | ✅ | ✅ | Prompts van a terceros |
| Confidencialidad prompts | ✅ | ✅ | ⚠️ revisar TOS Groq/Together |

---

### 6.5 Consideraciones de privacidad para clientes (ej: Alemana)

Si los prompts incluyen código o contexto de sistemas de Clínica Alemana:
- **Config A y B:** todo el procesamiento ocurre en tu VPS. Cero exposición a terceros.
- **Config C:** los prompts se envían a Groq (US) y Together.ai (US). Revisar acuerdos de confidencialidad con el cliente antes de usar.

**Recomendación para proyectos de clientes con datos sensibles:** Config A con `deepseek-r1:14b` + `qwen2.5-coder:14b`. El costo de $252/mes es justificable si se factura a 2+ clientes.

---

### 6.6 Cambios de código necesarios para modelos nuevos

Solo cambiar variables de entorno en `.env.prod`:

```bash
# Agente principal con razonamiento
OVD_ARCHITECT_MODEL=deepseek-r1:14b
OVD_ARCHITECT_PROVIDER=ollama

# Agentes de código (backend, frontend, database, devops)
OVD_AGENT_MODEL=qwen2.5-coder:14b
OVD_AGENT_PROVIDER=ollama

# O para Config C híbrida:
OVD_ARCHITECT_MODEL=deepseek-r1-distill-llama-70b
OVD_ARCHITECT_PROVIDER=groq
OVD_AGENT_MODEL=Qwen2.5-Coder-32B-Instruct
OVD_AGENT_PROVIDER=together

# Embeddings
OVD_EMBEDDING_PROVIDER=ollama   # Config A/B
OVD_EMBEDDING_PROVIDER=openai   # Config C
```

El `model_router.py` ya maneja múltiples providers. Solo requiere agregar Groq y Together como providers en el router (2-3 horas de trabajo).

---

## 7. Alternativa Kubernetes (Largo plazo — FASE C)

Para cuando OVD sea multi-cliente (FASE C), considerar:

| Opción | Precio base | Aplica cuando |
|--------|------------|---------------|
| DigitalOcean DOKS | $12/mes (2 nodos × $6) | > 3 orgs cliente |
| Hetzner K3s self-managed | $9-18/mes | > 5 orgs cliente, equipo con experiencia K8s |
| AWS EKS | $73/mes base + nodos | > 10 orgs cliente con SLA exigente |

No se recomienda Kubernetes para la FASE 5 actual. Docker Compose es suficiente y mucho más simple de operar para un equipo pequeño.

---

## 7. Próximos pasos (una vez seleccionado el proveedor)

1. Crear VPS y configurar SSH key
2. Instalar Docker + Docker Compose
3. Configurar DNS y obtener certificado TLS con certbot
4. Actualizar `docker-compose.prod.yml` con variables de entorno de producción
5. Agregar Node.js al Dockerfile del engine (GAP-CLOUD-03)
6. Crear Dockerfile del dashboard (GAP-CLOUD-04)
7. Configurar `VITE_API_URL` y `OVD_EMBEDDING_PROVIDER=openai`
8. Ejecutar migraciones iniciales
9. Crear usuario admin + org + workspace en BD de producción
10. Actualizar `~/.ovd/config.toml` del equipo con la URL cloud
