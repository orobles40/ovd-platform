# MCP Validation Report — OVD-TUI Fork
**Version:** 1.0
**Fecha:** 2026-03-23
**Proyecto:** OVD-TUI (Fork OpenCode para Oficina Virtual de Desarrollo)

---

## 1. Estado Actual

### 1.1 MCPs instalados en Claude Code (sesion actual)

| MCP | Estado | Herramientas disponibles | Relevancia al proyecto |
|-----|--------|--------------------------|------------------------|
| `gdrive` | ACTIVO | `gdrive_search`, `gdrive_read_file`, `gsheets_read`, `gsheets_update_cell` | ALTA — archivos de diseño Alemana en Google Drive |
| `gmail` | ACTIVO | `gmail_search_messages`, `gmail_read_message`, `gmail_read_thread`, `gmail_list_drafts`, `gmail_create_draft`, `gmail_list_labels`, `gmail_get_profile` | MEDIA — comunicacion con equipo |
| `context7` | ACTIVO | `resolve-library-id`, `query-docs` | MUY ALTA — documentacion actualizada de Bun, Hono, Effect.ts, Drizzle ORM |
| `memory` | ACTIVO | `read_graph`, `search_nodes`, `create_entities`, `create_relations`, `add_observations`, `delete_entities`, `delete_observations`, `delete_relations`, `open_nodes` | ALTA — estado del proyecto entre sesiones |

### 1.2 MCPs en el fork OpenCode (.opencode/opencode.jsonc)

```jsonc
// Estado actual — completamente vacio
"mcp": {}
```

**Herramientas deshabilitadas en el fork:**
```jsonc
"tools": {
  "github-triage": false,
  "github-pr-search": false
}
```

Estas fueron deshabilitadas en el upstream para reducir ruido — se pueden rehabilitar si se configura el MCP de GitHub.

---

## 2. Analisis de Cobertura

### 2.1 Gaps criticos identificados

| Necesidad del proyecto | MCP disponible | Estado |
|------------------------|----------------|--------|
| Consultar Oracle multi-sede (CAS/CAT/CAV) | Oracle MCP (custom) | FALTANTE — disenar desde cero |
| Publicar mensajes en NATS JetStream | NATS MCP (custom) | FALTANTE — disenar desde cero |
| Buscar documentacion interna en Confluence | Confluence MCP | FALTANTE |
| Gestionar PRs y issues del fork | GitHub MCP | FALTANTE |
| Ejecutar queries en PostgreSQL (base del fork) | PostgreSQL MCP | FALTANTE |
| Control de contenedores Docker del entorno dev | Docker MCP | FALTANTE |
| Leer logs de OpenTelemetry collector | OTEL MCP | FALTANTE |

---

## 3. MCPs Instalados — Evaluacion de Uso

### 3.1 context7 — USO INMEDIATO

Resolver las bibliotecas criticas del fork antes de comenzar TASK-FORK:

```bash
# Ejemplos de uso en sesiones de desarrollo
mcp context7: resolve-library-id "bun"
mcp context7: resolve-library-id "hono"
mcp context7: resolve-library-id "drizzle-orm"
mcp context7: resolve-library-id "effect"
mcp context7: resolve-library-id "ai sdk vercel"
mcp context7: resolve-library-id "zod"
```

Critico para: TASK-API (Hono middleware), TASK-FT (Drizzle ORM), TASK-EXT (MCP SDK).

### 3.2 gdrive — USO EN PHASE 0

Documentacion de Alemana disponible en Drive:
- Arquitectura Oracle multi-sede (esquemas de conexion)
- Flujos de aprobacion Java EE legacy
- ERD de las bases de datos por sede

Usar para informar el diseno del Oracle MCP Server antes de TASK-EXT.

### 3.3 memory — USO CONTINUO

El grafo de memoria debe mantener:
- Estado del fork (commits pendientes, PRs abiertos)
- Decisiones de arquitectura tomadas (no revertir sin justificacion)
- Configuracion Oracle por sede (credenciales NO, topologia SI)
- Agentes activos y sus modelos asignados

### 3.4 gmail — USO SECUNDARIO

Util para:
- Notificaciones de CI/CD por correo
- Comunicacion con Alemana sobre requisitos Oracle
- Coordinacion del equipo de desarrollo

---

## 4. MCPs Propuestos

### 4.1 MCP GitHub — PRIORIDAD ALTA

**Proposito:** Gestionar el ciclo de vida del fork: PRs, issues, branch protection, code review.

**Instalacion:**
```bash
# Via npx (recomendado para desarrollo)
npx @modelcontextprotocol/server-github

# Configuracion en opencode.jsonc del fork
"mcp": {
  "github": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-github"],
    "env": {
      "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
    }
  }
}
```

**Herramientas clave:** `create_pull_request`, `search_repositories`, `create_issue`, `list_commits`, `get_file_contents`, `push_files`

**Fase:** Phase 0 (Semana 1 — TASK-FORK)

---

### 4.2 MCP PostgreSQL — PRIORIDAD ALTA

**Proposito:** Acceso directo a la base de datos del fork (sessions, messages, fine-tuning samples, tenants).

**Instalacion:**
```bash
npx @modelcontextprotocol/server-postgres

# Configuracion
"mcp": {
  "postgres": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-postgres",
             "postgresql://ovd_dev:password@localhost:5432/ovd_dev"]
  }
}
```

**Herramientas clave:** `query`, `describe_table`, `list_tables`

**Casos de uso:**
- Inspeccionar schema de multi-tenancy durante TASK-API
- Verificar RLS policies en tiempo real
- Debug de sesiones y fine-tuning samples

**Fase:** Phase 0 (Semana 2 — junto con TASK-API)

---

### 4.3 MCP Oracle Multi-Sede (custom) — PRIORIDAD CRITICA

**Proposito:** Unico punto de acceso a Oracle CAS (12c), CAT (19c), CAV (19c) con routing automatico y validacion de compatibilidad.

**Diseno del servidor (Python/oracledb):**

```
src/mcp/oracle/
├── server.py          # MCP stdio server
├── connections.py     # Pool manager por sede
├── compat.py          # Validador 12c vs 19c syntax
├── wallet/            # Oracle Wallet credentials (gitignored)
│   ├── CAS/
│   ├── CAT/
│   └── CAV/
└── requirements.txt   # oracledb, mcp, python-dotenv
```

**Tools expuestas:**
```python
@mcp.tool()
async def query_oracle(
    sql: str,
    sede: Literal["CAS", "CAT", "CAV"],
    max_rows: int = 100
) -> dict:
    """Ejecuta SQL en la sede Oracle especificada."""

@mcp.tool()
async def validate_sql_compat(
    sql: str,
    target_sede: Literal["CAS", "CAT", "CAV"]
) -> dict:
    """Valida compatibilidad SQL entre versiones Oracle.
    CAS = Oracle 12c, CAT/CAV = Oracle 19c"""

@mcp.tool()
async def describe_schema(
    table_pattern: str,
    sede: Literal["CAS", "CAT", "CAV"]
) -> list[dict]:
    """Lista tablas/columnas que coincidan con el patron."""
```

**Configuracion en fork:**
```jsonc
"mcp": {
  "oracle-ovd": {
    "command": "python3",
    "args": ["/path/to/mcp-servers/oracle/server.py"],
    "env": {
      "ORACLE_WALLET_DIR": "${ORACLE_WALLET_DIR}",
      "CAS_DSN": "${ORACLE_CAS_DSN}",
      "CAT_DSN": "${ORACLE_CAT_DSN}",
      "CAV_DSN": "${ORACLE_CAV_DSN}"
    }
  }
}
```

**Fase:** Phase 1 (TASK-EXT, semana 5-6)

---

### 4.4 MCP NATS (custom) — PRIORIDAD MEDIA

**Proposito:** Publicar eventos del OVD-Bridge a NATS JetStream para integracion con el sistema de colas de Alemana.

**Diseno:**
```
src/mcp/nats/
├── server.py
└── requirements.txt   # nats-py, mcp
```

**Tools expuestas:**
```python
@mcp.tool()
async def publish_event(subject: str, payload: dict) -> dict:
    """Publica evento en NATS JetStream."""

@mcp.tool()
async def consume_events(subject: str, limit: int = 10) -> list[dict]:
    """Lee ultimos N eventos del subject."""

@mcp.tool()
async def list_subjects(pattern: str = ">") -> list[str]:
    """Lista subjects activos en el servidor NATS."""
```

**Fase:** Phase 2 (TASK-BRIDGE, semana 9-10)

---

### 4.5 MCP Confluence — PRIORIDAD MEDIA

**Proposito:** Buscar documentacion interna de Alemana: especificaciones de requisitos, arquitectura legacy, workflows aprobados.

**Opcion recomendada:** `@modelcontextprotocol/server-confluence` (oficial Atlassian)

```jsonc
"mcp": {
  "confluence": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-confluence"],
    "env": {
      "CONFLUENCE_URL": "${CONFLUENCE_URL}",
      "CONFLUENCE_USERNAME": "${CONFLUENCE_USER}",
      "CONFLUENCE_API_TOKEN": "${CONFLUENCE_TOKEN}"
    }
  }
}
```

**Herramientas clave:** `search_pages`, `get_page`, `list_spaces`

**Fase:** Phase 1 (TASK-EXT, habilitar junto con Skills de legacy-java)

---

### 4.6 MCP Docker — PRIORIDAD BAJA

**Proposito:** Control del entorno Docker durante desarrollo — inspeccionar contenedores, logs, restart de servicios.

```jsonc
"mcp": {
  "docker": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-docker"]
  }
}
```

**Casos de uso:** Debug del stack Docker Compose (PostgreSQL, NATS, Oracle, Redis), restart de servicios durante CI.

**Fase:** Phase 0 (Semana 3 — TASK-INFRA)

---

## 5. Configuracion MCP Consolidada para el Fork

Una vez completada Phase 0, el archivo `.opencode/opencode.jsonc` del fork deberia quedar:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    // Disponibles desde Phase 0
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}" }
    },
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres",
               "${DATABASE_URL}"]
    },
    "docker": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-docker"]
    },
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"]
    },
    // Disponibles desde Phase 1
    "oracle-ovd": {
      "command": "python3",
      "args": ["${OVD_ROOT}/src/mcp/oracle/server.py"],
      "env": {
        "ORACLE_WALLET_DIR": "${ORACLE_WALLET_DIR}",
        "CAS_DSN": "${ORACLE_CAS_DSN}",
        "CAT_DSN": "${ORACLE_CAT_DSN}",
        "CAV_DSN": "${ORACLE_CAV_DSN}"
      }
    },
    "confluence": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-confluence"],
      "env": {
        "CONFLUENCE_URL": "${CONFLUENCE_URL}",
        "CONFLUENCE_USERNAME": "${CONFLUENCE_USER}",
        "CONFLUENCE_API_TOKEN": "${CONFLUENCE_TOKEN}"
      }
    },
    // Disponibles desde Phase 2
    "nats-ovd": {
      "command": "python3",
      "args": ["${OVD_ROOT}/src/mcp/nats/server.py"],
      "env": { "NATS_URL": "${NATS_URL}" }
    }
  },
  "tools": {
    "github-triage": false,
    "github-pr-search": false
  }
}
```

---

## 6. Roadmap de Instalacion

```
Phase 0 (Semanas 1-4)
  Semana 1: GitHub MCP          → TASK-FORK
  Semana 2: PostgreSQL MCP      → TASK-API (schema multi-tenancy)
  Semana 3: Docker MCP          → TASK-INFRA (Docker Compose)
  Semana 4: context7 en fork    → disponible para todo el equipo

Phase 1 (Semanas 5-8)
  Semana 5: Oracle MCP (dev)    → TASK-EXT (solo datos de prueba)
  Semana 6: Confluence MCP      → TASK-EXT (Skills legacy-java)
  Semana 8: Oracle MCP (prod)   → validacion con DBA Alemana

Phase 2 (Semanas 9-12)
  Semana 9: NATS MCP            → TASK-BRIDGE
```

---

## 7. Notas de Seguridad

- Credenciales Oracle NUNCA en opencode.jsonc — solo variables de entorno via `.env.local` (gitignored)
- Oracle Wallet files fuera del repositorio — path absoluto configurable
- MCP PostgreSQL usa rol de solo lectura en produccion (`ovd_readonly`)
- GitHub MCP token con scope minimo: `repo`, `read:org` (no `admin:*`)
- Todos los MCP custom deben loggear a OTEL collector (ver TASK-TEL)
