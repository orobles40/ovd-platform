# ADR-006 — OVD Desktop: Modo escritura directa (enfoque "directo")

**Estado:** Propuesta — sprint futuro  
**Fecha:** 2026-05-08  
**Contexto:** OVD Desktop F0 completado, flujo ZIP validado

---

## Problema

El flujo actual de entrega de artefactos usa ZIP como transporte:

```
Engine genera código → guarda en memoria → ZIP → HTTP download → Tauri extrae en disco
```

Esto es correcto para producción (engine en servidor remoto), pero para uso local agrega una indirección innecesaria. Herramientas como Claude Code, Goose y opencode escriben directamente al filesystem sin ZIP porque el agente corre en la misma máquina.

---

## Análisis: cómo lo resuelven otros

| Herramienta | Agente corre en | Escribe archivos | Mecanismo |
|---|---|---|---|
| Claude Code | Local (CLI) | Directo | Write tool del proceso local |
| Goose | Local (CLI) | Directo | Tool calling local |
| opencode | Local (CLI/TUI) | Directo | Tool calling local |
| OpenHands | Docker container | Directo | Volumen montado `-v ~/proyecto:/workspace` |
| LangFlow Cloud | Servidor remoto | ZIP / API | Descarga manual |
| OVD Desktop (actual) | Servidor HTTP | ZIP | `workspace_write_artifacts` |

---

## Hallazgos técnicos clave

**El engine YA escribe a disco durante el ciclo.**

El nodo `deliver` en `graph.py` ya llama `_write_artifacts(directory, ...)` que escribe los archivos al `directory` recibido en el request. El endpoint `/artifacts/download` después ZIPA ese mismo directorio para devolverlo. Es decir: los archivos ya están escritos en el directorio cuando el desktop hace el ZIP download.

Implicación: si el engine corre localmente y recibe el path real del proyecto, los archivos ya están escritos antes de que el desktop descargue el ZIP.

---

## Opciones para el modo directo

### Opción A — Sidecar mode (recomendada para sprint futuro)

Tauri lanza el engine Python como proceso hijo usando la API de sidecar de Tauri 2:

```
[Tauri Desktop]
    ├── UI (React/Vite)
    └── sidecar: engine Python (PyInstaller bundle)
              ├── escribe directo al directory
              └── SSE via localhost:8001 (o stdout pipe)
```

**Ventajas:**
- App completamente offline — no depende de servidor externo
- Escribe directo al disco (no ZIP necesario)
- Distribución como `.dmg`/`.exe` con todo incluido
- Usa la misma arquitectura del engine actual sin reescribir

**Trabajo requerido:**
- Empaquetar engine con PyInstaller (o Nuitka) como binario portable
- Agregar `externalBin` en `tauri.conf.json` para registrar el sidecar
- Agregar `tauri::command` en Rust para iniciar/detener el sidecar
- Agregar modo `local_write: true` en engine que confirme sin retornar ZIP
- Tiempo estimado: 3-4 días de sprint

**Referencia Tauri:** https://tauri.app/develop/sidecar/

---

### Opción B — Flag `local_mode` en engine existente

Agregar campo `local_write: bool` al request. Si es `true`, el engine omite el ZIP y retorna solo confirmación. El desktop no llama `workspaceWriteArtifacts` — los archivos ya están en disco.

```typescript
// startCycle en FrLauncher.tsx
body: JSON.stringify({
  ...
  local_write: true,   // nuevo flag
  directory: project.directory,
})

// handleDeliver: si local_write, skip download
const skip_zip = autoApprove && isLocalEngine;
if (!skip_zip) {
  await workspaceWriteArtifacts(sid, project.directory);
}
```

**Ventajas:** cambio mínimo, funciona ya con el engine local actual  
**Desventajas:** no funciona en modo remoto, requiere que `directory` sea accesible desde el engine

**Trabajo requerido:** 1 día (engine + frontend)

---

### Opción C — Reescritura del grafo en Rust

Portar LangGraph a una implementación Rust dentro de Tauri. El agente correría nativo como parte del proceso Tauri.

**Pros:** app completamente nativa, sin dependencia Python  
**Contras:** meses de trabajo, LangGraph no tiene equivalente maduro en Rust  
**Veredicto:** descartado hasta que el ecosistema Rust AI madure

---

## Recomendación

| Plazo | Opción | Esfuerzo | Valor |
|---|---|---|---|
| Sprint próximo (corto plazo) | B — flag local_write | 1 día | Validar concepto |
| Sprint medio plazo | A — sidecar PyInstaller | 4 días | App completamente offline |
| Largo plazo | A + release en App Store | 2 semanas | Distribución comercial |

**Prioridad sugerida:** Opción B primero para validar (no requiere rediseño), luego Opción A para la release de distribución.

---

## Impacto en arquitectura actual

- El flujo ZIP actual sigue siendo necesario para el engine en DO (producción remota)
- El modo directo es opt-in según si el engine corre local o remoto
- `configGet()` puede detectar si `engine_url` es localhost → activar modo directo automáticamente

```typescript
const isLocalEngine = engineUrl.includes("localhost") || engineUrl.includes("127.0.0.1");
```

---

## Referencias

- Tauri Sidecar API: `tauri.conf.json` → `bundle.externalBin`
- Goose source: `crates/goose/src/agents/` — tool calling directo en Rust
- OpenHands workspace: `openhands/runtime/docker/` — volumen mount approach
- engine/graph.py `_write_artifacts()` — ya escribe al `directory` recibido
- engine/api.py `/artifacts/download` — ZIP del directorio post-escritura
