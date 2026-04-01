# VDO Platform — Arquitectura Multi-Tenant Jerárquica

> **Versión:** 1.0  
> **Fecha:** Marzo 2026  
> **Autor:** Omar Robles  
> **Contexto:** Análisis arquitectónico para evolución del Virtual Development Office (VDO) hacia modelo SaaS multi-tenant

---

## 1. Introducción

El Virtual Development Office (VDO) está diseñado inicialmente para uso interno en Omar Robles, operando con un cliente principal (Alemana) y un entorno de 5 usuarios. Sin embargo, la visión a futuro contempla convertir el VDO en un **producto SaaS** capaz de prestar servicios a múltiples empresas de TI, cada una con sus propios clientes finales y stacks tecnológicos heterogéneos.

Este documento establece el modelo arquitectónico correcto para soportar esa evolución desde el diseño inicial, evitando refactorizaciones costosas en el futuro.

---

## 2. Del Multi-Tenant Clásico al Modelo Jerárquico

### 2.1 Modelo clásico (video de referencia)

El modelo estándar multi-tenant — popularizado en frameworks como .NET con Entity Framework — asume la siguiente estructura:

| Concepto | Descripción |
|---|---|
| `DbContext` de tenants | Gestiona configuración de clientes (qué DB usar) |
| `DbContext` de negocio | Lógica de negocio, cambia dinámicamente por cliente |
| Resolución de tenant | Identificación via HTTP headers o JWT |
| Filtros globales | Queries automáticamente filtradas por `tenant_id` |
| Migraciones automáticas | Actualización de todas las DBs al iniciar la aplicación |

### 2.2 La complejidad específica del VDO

El caso del VDO es más complejo que el modelo estándar. Alemana no es un tenant con una sola base de datos — tiene un **sharding geográfico interno** con versiones de Oracle distintas:

```
Tenant Alemana
    │
    ├── CAS (Santiago)  → Oracle 12c  ← restricción crítica
    ├── CAT (Temuco)    → Oracle 19c
    └── CAV (Valdivia)  → Oracle 19c
```

Esto implica una capa adicional de resolución que el modelo estándar no contempla.

### 2.3 El modelo jerárquico para SaaS

Con la visión de producto SaaS, la estructura correcta es **multi-tier tenancy**:

```
VDO Platform (Omar Robles — Platform Provider)
│
├── Tenant L1: "Omar Robles" (uso interno)
│       └── Workspace: Alemana
│               ├── CAS → Oracle 12c / Java EE / Struts 1.3
│               ├── CAT → Oracle 19c / Python / NATS
│               └── CAV → Oracle 19c / Python / NATS
│
├── Tenant L1: "Empresa TI México"
│       ├── Workspace: Banco XYZ
│       │       └── Stack: PostgreSQL / Spring Boot / Kafka
│       └── Workspace: Retail ABC
│               └── Stack: MySQL / Node.js / RabbitMQ
│
└── Tenant L1: "Consultora Argentina"
        └── Workspace: Gobierno Provincial
                └── Stack: SQL Server / .NET / Azure
```

---

## 3. Los 3 Niveles del Modelo

| Nivel | Nombre | Actor | Responsabilidad |
|---|---|---|---|
| **L0** | Platform | Omar Robles (tú) | Plataforma VDO completa, billing global, SLAs |
| **L1** | Organization | Empresa de TI cliente de Omar Robles | Gestión de sus workspaces y usuarios |
| **L2** | Workspace | Cliente final de la organización | Sus sistemas, stack tecnológico, credenciales |

---

## 4. El Stack Registry: Corazón del Modelo

El componente central que habilita el soporte de stacks heterogéneos es el **Stack Registry** — un catálogo dinámico que describe el ecosistema tecnológico de cada Workspace.

### 4.1 Estructura del Stack Registry

```json
{
  "workspace_id": "alemana-cas",
  "org_id": "omar",
  "display_name": "Alemana CAS Santiago",
  "stack": {
    "databases": [
      {
        "id": "oracle-cas",
        "type": "oracle",
        "version": "12c",
        "host": "encrypted",
        "restrictions": [
          "no_json_functions",
          "no_lateral_join",
          "no_fetch_first"
        ]
      }
    ],
    "backend": [
      {
        "type": "java_ee",
        "framework": "struts",
        "version": "1.3",
        "runtime": "weblogic"
      }
    ],
    "messaging": [],
    "frontend": []
  },
  "agent_config": {
    "sql_developer": {
      "model": "claude-api",
      "oracle_compat": "12c"
    },
    "java_legacy_dev": {
      "model": "claude-api",
      "frameworks": ["struts-1.3", "ibatis", "spring-2.5"]
    }
  }
}
```

### 4.2 Capacidades que habilita el Stack Registry

**Agentes polimórficos**

El mismo agente genera comportamiento diferente según el stack del workspace:

| Workspace | Agente SQL Developer | Output |
|---|---|---|
| Alemana CAS | SQL Developer | Sintaxis Oracle 12c compatible |
| Banco XYZ | SQL Developer | Sintaxis PostgreSQL 15 |
| Gobierno AR | SQL Developer | Sintaxis SQL Server 2019 |

**Selección dinámica de modelo AI**

```
Stack simple / moderno    → Ollama local (costo cero)
Stack legacy complejo     → Claude API (máxima capacidad)
Stack desconocido         → Claude API + modo cauteloso
```

**Restricciones automáticas por stack**

Las restricciones del stack se inyectan automáticamente en el system prompt del agente correspondiente, eliminando la necesidad de configuración manual por instrucción.

---

## 5. Flujo de Resolución de Contexto

Ningún agente conoce el stack directamente. El contexto llega resuelto desde el **Context Resolver**:

```
Request del usuario
        │
        ▼
   JWT Token
   { org: "empresa-mexico", workspace: "banco-xyz" }
        │
        ▼
   Context Resolver (FastAPI Middleware)
        │
        ├── Carga Stack Registry del workspace
        ├── Resuelve conexiones disponibles
        ├── Determina qué agentes aplican
        └── Construye AgentContext
                │
                ▼
        Coordinator Agent (LangGraph)
        { stack: PostgreSQL/Kafka, restrictions: [], ... }
                │
                ├── SQL Developer    → recibe "postgresql 15, sin restricciones"
                ├── Backend Dev      → recibe "spring-boot, kotlin"
                └── DevOps Engineer  → recibe "kubernetes, azure"
```

**Principio fundamental:** los agentes son **stack-agnostic** en código, pero **stack-aware** en ejecución.

---

## 6. Modelo de Seguridad y Aislamiento

Con 3 niveles jerárquicos, la seguridad debe implementarse en capas:

```
┌─────────────────────────────────────────────────┐
│  Platform Layer (Omar Robles)                      │
│  • Billing, límites y SLAs por Organización      │
│  • Audit log global e inmutable                  │
│  • Control de versiones del VDO por tenant       │
├─────────────────────────────────────────────────┤
│  Organization Layer (empresa TI cliente)         │
│  • Gestión de sus Workspaces                     │
│  • Límites de agentes, tokens y requests         │
│  • Usuarios y roles propios                      │
├─────────────────────────────────────────────────┤
│  Workspace Layer (cliente final)                 │
│  • Credenciales encriptadas por workspace        │
│  • Stack config completamente aislada            │
│  • Logs propios sin visibilidad cruzada          │
└─────────────────────────────────────────────────┘
```

**Regla de oro:** ningún dato de un Workspace es visible desde otro Workspace, aunque pertenezcan a la misma Organización.

### 6.1 Errores comunes a evitar (extraídos del modelo clásico)

| Error | Descripción | Consecuencia |
|---|---|---|
| Sin filtros globales | Queries ejecutadas sin scope de tenant | Fuga de datos entre clientes |
| Lógica mezclada | Agentes resuelven sus propias conexiones | Acoplamiento, difícil de auditar |
| Onboarding incompleto | DB del cliente no se crea al registrarlo | Acceso antes de estar listo |
| Sin validación de tenant | Tenant vacío o inválido no rechazado | Acceso indeterminado |

---

## 7. Stack Tecnológico Recomendado

| Componente | Tecnología | Razón |
|---|---|---|
| **Tenant Registry** | PostgreSQL | Relacional, confiable, independiente de Oracle |
| **Stack Registry** | PostgreSQL + JSONB | Flexible para schemas distintos por cliente |
| **Secrets / Credenciales** | HashiCorp Vault o AWS Secrets Manager | Nunca almacenar en DB plana |
| **Auth / JWT** | Auth0 o Keycloak | Multi-tenant nativo, roles por organización |
| **Context Resolver** | FastAPI middleware | Nativo en el stack actual del VDO |
| **Orquestación de agentes** | LangGraph con contexto dinámico | Ya implementado en el VDO |
| **TUI (cliente)** | Rust + Ratatui | Binario distribuible, seguro, sin dependencias |

---

## 8. El TUI en el Modelo Multi-Tenant

El cliente TUI en Rust cobra especial relevancia en este modelo. Cada organización distribuye el binario a sus operadores, configurado por workspace:

```toml
# ~/.vdo/config.toml
[default]
org = "empresa-mexico"
workspace = "banco-xyz"
api_url = "https://vdo.omarrobles.dev"

[workspaces.retail]
workspace = "retail-abc"
```

```bash
# Flujo de trabajo del operador
vdo login --org empresa-mexico
vdo workspace use banco-xyz

vdo> /status
# Ve solo agentes y sistemas de banco-xyz

vdo workspace use retail-abc
vdo> /status
# Ve solo agentes y sistemas de retail-abc
```

La experiencia es similar a `kubectl` con múltiples clusters — cada contexto es completamente aislado desde el cliente.

---

## 9. Hoja de Ruta de Implementación

```
FASE ACTUAL — Uso interno Omar Robles
│   • 1 Organización (Omar Robles)
│   • 1 cliente (Alemana)
│   • 3 Workspaces (CAS, CAT, CAV)
│   • 5 usuarios internos
│
CORTO PLAZO — Fundamentos del modelo
│   • Stack Registry funcional
│   • Context Resolver en FastAPI middleware
│   • Aislamiento real entre workspaces
│   • Oracle version tag en cada conexión
│   (aunque sea 1 cliente, el modelo ya es correcto)
│
MEDIANO PLAZO — Multi-organización
│   • Organization Layer + Auth multi-org (Keycloak/Auth0)
│   • Onboarding self-service de workspaces
│   • TUI con soporte multi-workspace
│   • Secrets management centralizado (Vault)
│
LARGO PLAZO — SaaS público
│   • Billing por Organización
│   • Marketplace de stack connectors
│   • Certificación de stacks de terceros
│   • SLA garantizados por tier
```

---

## 10. Recomendación Principal

**Diseñar el Stack Registry desde ahora**, aunque hoy solo exista Alemana como cliente.

Construir asumiendo un stack único hace que la refactorización posterior para soportar stacks dinámicos sea costosa y riesgosa. Implementar el modelo correcto desde el inicio tiene un costo marginal bajo y entrega el diseño adecuado para escalar sin fricciones.

El Stack Registry, el Context Resolver y el modelo de 3 niveles son los tres componentes que convierten el VDO de una herramienta interna a un producto SaaS listo para múltiples organizaciones con stacks heterogéneos.

---

## Apéndice: Comparación de Modelos de Aislamiento

| Modelo | Aislamiento | Complejidad operacional | Caso de uso ideal |
|---|---|---|---|
| **1 DB por tenant** | Total | Alta | SaaS con clientes nuevos desde cero |
| **Schema por tenant** | Alto | Media | Sin posibilidad de crear DBs por cliente |
| **Row-level (tenant_id)** | Bajo | Baja | Datos no críticos, pocos tenants |
| **DB pre-existente por sede** | Total | Alta | Clientes con infraestructura propia (Alemana) |
| **Jerárquico (este modelo)** | Total por capa | Alta | SaaS con clientes que tienen sus propios clientes |

---

*Documento generado como parte del diseño arquitectónico del Virtual Development Office — Omar Robles, 2026.*
