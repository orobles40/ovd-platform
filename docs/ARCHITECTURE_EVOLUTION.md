# OVD Platform — Evolución Arquitectónica hacia SaaS
**Última actualización:** 2026-03-26
**Autor:** Omar Robles / Omar Robles
**Estado actual:** FASE A completa — iniciando FASE B (TUI Rust)

---

## 1. Contexto

Este documento registra el alineamiento entre el modelo arquitectónico objetivo (SaaS multi-tenant jerárquico) y la implementación real en cada hito del proyecto.

**Principios de diseño no negociables (en orden de prioridad):**
1. Seguridad — ninguna brecha es aceptable, ni en uso interno
2. Escalabilidad — el modelo de datos y aislamiento soporta crecimiento sin refactorización
3. Extensibilidad — nuevas funcionalidades se agregan sin romper lo existente
4. Calidad del flujo — el sistema mejora con el tiempo gracias a datos bien estructurados

---

## 2. Estado de alineamiento — FASE A completa (2026-03-26)

### Componentes correctamente implementados

| Componente | Descripción | Estado |
|---|---|---|
| Modelo L1/L2 | `ovd_orgs` (L1) + `ovd_projects` (L2) con JWT por org | ✅ |
| Isolation por `org_id` | Todos los queries filtran por org, FastAPI inyecta contexto | ✅ |
| **RLS activo** | 13 tablas con Row-Level Security. Sin `app.current_org_id` → 0 filas visibles | ✅ S10 |
| NATS por org | Subjects `ovd.{org_id}.session.*` — namespace implícito por tenant | ✅ |
| Quota enforcement | `OVDQuota.check()` antes de crear sesión | ✅ |
| LangGraph stack-agnostic | Engine recibe `AgentContext` tipado, no tiene stack hardcodeado | ✅ S8 |
| **Stack Registry estructurado** | `db_version`, `db_restrictions[]`, `model_routing` en `ovd_stack_profiles` | ✅ S8 |
| **Context Resolver** | `ContextResolver.resolve_async()` construye `AgentContext` tipado antes del grafo | ✅ S8 |
| **Secrets Manager** | `InfisicalAdapter` + `EnvAdapter` fallback. `secret_ref` por proyecto | ✅ S9 |
| **JWT + refresh tokens** | Access token 1h + refresh token 7d rotativo en `ovd_refresh_tokens` | ✅ S10 |
| **Audit logging** | `AuditLogger` con métodos por evento. Fire-and-forget async | ✅ S10 |
| **OTEL tracing** | Spans por ciclo y nodo LangGraph. `trace_id` en `OVDState` | ✅ S10 |
| Webhooks por org | `ovd_webhook_subscriptions` — integración CI/CD | ✅ |
| API pública REST | Auth + 9 endpoints bajo `/api/v1/orgs/{id}/` | ✅ S12w |
| Dashboard web v1 | React + Vite + Tailwind. Login, métricas, ciclos, proyectos | ✅ S12w |

### GAPs resueltos en FASE A

| GAP | Descripción | Solución | Sprint |
|---|---|---|---|
| GAP-A1 | Stack Registry truncado (texto libre) | Schema estructurado `ovd_stack_profiles` | S8 ✅ |
| GAP-A2 | RLS no activado | `infra/postgres/rls.sql` aplicado, 13 tablas | S10 ✅ |
| GAP-A3 | Context Resolver embebido en route handler | `context_resolver.py` middleware independiente | S8 ✅ |
| GAP-A4 | Secrets en `.env.local` | Infisical self-hosted + `secrets_adapter.py` | S9 ✅ |
| GAP-A5 | JWT sin refresh tokens | Access 1h + refresh 7d en `ovd_refresh_tokens` | S10 ✅ |
| GAP-A6 | Telemetría sin instrumentación end-to-end | `telemetry.py` con spans OTEL por ciclo/nodo | S10 ✅ |

### GAPs pendientes

| GAP | Descripción | Plan |
|---|---|---|
| GAP-B1 | Naming "Project" vs "Workspace" (semántico) | Alias `/workspace` en S15 — no urgente |
| GAP-C1 | L0 Platform Layer (admin global Omar Robles) | Solo relevante en Fase C |

---

## 3. Mapa de evolución

```
ESTADO SPRINT 7 (referencia histórica)
───────────────────────────────────────
Omar Robles (org L1) — JWT HS256 — row-level isolation (sin RLS activo)
    └── OVD Platform (project L2)
            ├── Stack Profile: texto libre
            ├── Context: string en route handler
            ├── Credentials: .env.local
            └── Engine: Ollama (todos los agentes, sin routing)

ESTADO ACTUAL — FASE A completa (2026-03-26) ✅
────────────────────────────────────────────────
Omar Robles (org L1) — JWT HS256 + refresh tokens — RLS activo — Audit logging
    └── OVD Platform (project L2)
            ├── Stack Registry: db_version, db_restrictions[], model_routing
            ├── Context Resolver: AgentContext tipado (stack + secrets + RAG)
            ├── Credentials: Infisical self-hosted (secret_ref por proyecto)
            ├── Engine: routing automático (Ollama/Claude según stack)
            ├── OTEL: spans por ciclo y nodo, trace_id propagado
            ├── API REST pública: auth + proyectos + ciclos + stats
            └── Dashboard web v1: React operativo en :5173

FASE B — En progreso (SIGUIENTE: TUI Rust S12)
───────────────────────────────────────────────
Omar Robles (org L1)
    ├── Alemana CAS (workspace L2) — Oracle 12c — restrictions[4] — Claude API
    ├── Alemana CAT (workspace L2) — Oracle 19c — Ollama
    └── Alemana CAV (workspace L2) — Oracle 19c + Python/NATS — Ollama
TUI Rust: login, workspace switch, FR launcher, SSE streaming, aprobación, historial

FASE C — SaaS Producto (largo plazo)
──────────────────────────────────────
L0: Omar Robles Platform (admin global, billing, SLAs)
    ├── L1: Empresa TI México — Workspaces: Banco XYZ, Retail ABC
    ├── L1: Consultora Argentina — Workspaces: Gobierno, Retail
    └── L1: Omar Robles (uso interno) — Workspaces: Alemana CAS/CAT/CAV
```

---

## 4. Decisiones de stack (definitivas al 2026-03-25)

| Componente | Stack | Notas |
|---|---|---|
| Backend API | Python — FastAPI | Consolida Bridge TypeScript (no extender más el Bridge) |
| Agentes | Python — LangGraph | |
| Fine-tuning | Python — Unsloth / LlamaFactory | |
| MCP Servers | Python | oracle, nats |
| Deps Python | uv + pyproject.toml | `uv.lock` se commitea |
| TUI | **Rust + Ratatui** | Binario standalone distribuible (Mac/Linux/Windows) |
| Web App | React + Vite + shadcn/ui + Tailwind | v1 operativa, completa en S15–S17 |
| Observabilidad | OTEL → panel en Web App (S17.C) | Grafana descartado (decisión 2026-03-26) |
| Base de conocimiento | opencode | Patrones y diseño de referencia — no código a mantener |

**Sobre el Bridge TypeScript:** el Bridge (Hono/Bun, Sprints 1–7) queda como referencia histórica. No se extiende. Toda la lógica migra a FastAPI en S15.A.

**Sobre opencode:** el fork fue la estrategia inicial. Decisión definitiva: base de conocimiento para estudiar patrones de sesiones, SSE y aprobaciones. El código OVD vive 100% en `src/`.

**Sobre gestión de dependencias Python:** `pip` queda descartado en todo el proyecto. El gestor oficial es **`uv`** (ya en uso en `src/engine/.venv`). Toda documentación, scripts y planes que referencien `pip install` deben usar `uv` en su lugar. Esto aplica a entornos de fine-tuning, MLX, MCP servers y cualquier componente Python nuevo. Decisión registrada 2026-03-31.

---

## 5. Decisiones de diseño

### Auth: JWT HS256
**Decisión:** mantener JWT HS256 para Fase A y B. Migrar a Keycloak/Auth0 si se requiere SSO/SAML para un cliente corporativo o segundo tenant real.

### Aislamiento de datos: Row-level con RLS
**Decisión:** row-level isolation (por `org_id`) con RLS activo para Fase A y B. Schema-per-tenant solo si un cliente enterprise lo requiere contractualmente (Fase C).

### Model routing automático
**Regla:** stack legacy (Oracle, Java EE, Struts) → Claude API. Stack moderno (Python, TypeScript, Go) → Ollama local. Sin perfil → Claude en modo cauteloso. Operador puede sobreescribir con `model_routing: "claude"` en Stack Registry.

### Observabilidad
**Decisión 2026-03-26:** no se usa Grafana ni herramienta externa. La visualización de métricas OTEL se integra directamente en la Web App (S17.C) como parte del producto — escalable a SaaS sin operación de herramientas por cliente. Infraestructura OTEL lista y recibiendo spans.

---

## 6. Pilar estratégico: modelo de IA propio

Cada ciclo OVD aprobado es una unidad de entrenamiento. El circuito:

```
Ciclo aprobado (QA ≥ 0.80 + aprobación humana)
        ↓
JSONL export filtrado (export_cycles.py)
        ↓
Fine-tuning LoRA sobre Qwen-Coder (Unsloth)
        ↓
Evaluación benchmark → si supera al base: activar vía Ollama
        ↓
El agente usa el modelo mejorado en los próximos ciclos
        ↓
Próximos ciclos generan mejores datos → el ciclo continúa
```

**Estado:** M0 activo (qwen2.5-coder:7b en producción local). SM1 pausado — faltan créditos API para generar ~238 ejemplos sintéticos adicionales (batch1.jsonl = 112 ejemplos guardados).

**Ver estrategia completa:** `docs/MODEL_STRATEGY.md`

---

## 7. Lo que no cambia

- **Modelo L1/L2 con JWT** — correcto para todos los estados de evolución
- **NATS por org** — aislamiento de mensajería correcto
- **Quota enforcement pre-sesión** — lugar correcto en el pipeline
- **LangGraph stack-agnostic** — el engine recibe contexto desde fuera, no conoce stacks
- **Webhooks por org** — integración CI/CD correctamente modelada
- **`ovd_cycle_logs` + fine-tuning pipeline** — el circuito de aprendizaje continuo

---

*Actualizar al completar cada sprint o tomar una decisión arquitectónica relevante.*
