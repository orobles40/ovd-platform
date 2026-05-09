# OVD Desktop — Plan de implementación v2

**Estado:** Planificado — pendiente inicio  
**Ubicación en repo:** `src/desktop/`  
**Fecha de diseño:** 2026-05-08  
**Revisión:** 2026-05-08 (post-research)

---

## Correcciones al plan v1 (hallazgos de investigación)

| Item | Plan v1 | Plan v2 (correcto) |
|---|---|---|
| React version | React 18 | **React 19** — consistente con dashboard existente |
| reqwest version | 0.12 | **0.13** — versión actual, feature `cookies` requerida |
| zip crate | `zip = "2"` | **`zip2 = "2"`** — el fork activo (crate original abandonado) |
| keyring API | `Entry::new()` simple | `use_native_store()` + `release_store()` requeridos en v3 |
| Tauri CLI | asumido instalado | **No instalado** — F0 debe instalarlo primero |
| Timeout run_tests | No mencionado | **Requerido** — sin timeout bloquea indefinidamente |
| Dominio DO | genérico | **`ovd-platform.codigonet.cloud`** / `ovd-platform-qjk25.ondigitalocean.app` |
| Deployment DO | VPS Docker Compose | **DO App Platform** con `app.yaml` |

---

## Decisiones de distribución confirmadas (2026-05-08)

| Pregunta | Decisión | Impacto |
|---|---|---|
| Distribución | **Uso interno** | Sin App Store, sin notarization |
| Apple Developer Program | **No** — no requerido para uso interno | Sin firma de código macOS en v0.1 |
| Auto-updater | **MVP** — incluir desde v0.1 | Keypair Ed25519 generado antes de F0 |
| Ícono | **Después** — placeholder Tauri en v0.1 | Sin `cargo tauri icon` en F0 |

### Comportamiento de instalación por plataforma

**macOS:** App sin firma. Primera vez: clic derecho → "Abrir" (o `xattr -d com.apple.quarantine "OVD Platform.app"`). Estándar para herramientas internas.

**Windows:** Sin certificado. SmartScreen advierte en primer run → "Más información → Ejecutar de todas formas". Normal para distribución interna.

**Linux:** `.deb` y `.appimage` no requieren firma.

### Paso pre-F0 — Generar keypair del updater (una sola vez)

```bash
# 1. Instalar Tauri CLI (si no está)
cargo install tauri-cli --version "^2"

# 2. Generar keypair Ed25519 para firmar updates
cargo tauri signer generate -w ~/.tauri/ovd-desktop.key
# → genera ~/.tauri/ovd-desktop.key (privada — guardar en password manager)
# → muestra la clave pública — copiar a tauri.conf.json → plugins.updater.pubkey

# 3. Agregar secreto en GitHub
# Settings → Secrets → Actions → New repository secret
# Name: TAURI_SIGNING_PRIVATE_KEY
# Value: contenido de ~/.tauri/ovd-desktop.key
```

### CI/CD simplificado (sin Apple)

`release-desktop.yml` usa solo:
- `TAURI_SIGNING_PRIVATE_KEY` + `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` (updater)
- Sin `APPLE_CERTIFICATE`, `APPLE_ID`, `APPLE_PASSWORD`, `APPLE_TEAM_ID`

Endpoint de updates (GitHub Releases):
```
https://github.com/omarrobles/ovd-platform/releases/latest/download/latest.json
```

---

## Contexto

OVD Desktop es un cliente nativo de escritorio (Tauri 2) para OVD Platform. El
desarrollador selecciona una carpeta de proyecto local, lanza Feature Requests, el
engine en DO genera código usando los modelos configurados, y el desktop escribe
los archivos directamente en la carpeta. Los tests se ejecutan en el ambiente real
del desarrollador.

**Lo que corre en DO:** análisis FR, agentes LLM, LangGraph, QA, tests internos (loop retry).  
**Lo que corre local:** app desktop, lectura/escritura de carpeta, tests locales reales.

---

## Requisitos confirmados

| # | Requisito |
|---|---|
| R1 | Conectarse al engine en DO y usar modelos ya configurados |
| R2 | No afectar implementación existente (engine, dashboard, TUI) |
| R3 | Trabajar directamente con carpeta de proyecto local |
| R3.1 | Crear proyecto nuevo con carpeta vacía |
| R3.2 | Proyecto existente — leer código como contexto para el engine |
| R4 | Pantallas: Login, Workspace (con gestión de proyectos + Stack Profile), FrLauncher |
| R5 | Aprobación de SDD requerida — igual que la app web |
| R6 | Tests ejecutados localmente después de escribir artefactos |
| R7 | Cross-platform: macOS (aarch64 + x86_64), Windows, Linux |
| R8 | Engine configurable: local (`localhost:8001`) o DO (producción) |

---

## Stack definitivo

| Capa | Tecnología | Versión |
|---|---|---|
| Framework desktop | Tauri 2 | 2.x |
| Frontend | React **19** + TypeScript + Vite + Tailwind CSS 4 | React 19.x |
| Icons | Lucide React | misma que dashboard |
| Backend nativo | Rust stable | 1.94.1 ✓ |
| HTTP client | reqwest (rustls-tls + cookies) | 0.13 |
| Keychain | keyring v3 (apple-native / windows-native / secret-service) | 3.x |
| Config local | rusqlite (bundled) | 0.32 |
| ZIP extracción | zip2 | 2.x |
| Runtime async | tokio (full) | 1.x |
| Serialización | serde + serde_json | 1.x |
| Errores | thiserror + anyhow | 1.x |
| CI/CD | GitHub Actions + tauri-action | v0 |
| Targets | dmg (macOS aarch64+x86_64), msi+nsis (Windows), deb+appimage (Linux) | — |

**Entorno local verificado:**
```
Rust/Cargo: 1.94.1 ✓
Node: 22.17.1 ✓
bun: 1.3.11 ✓
Tauri CLI: NO INSTALADO — instalar en F0
```

---

## Arquitectura de componentes

```
src/desktop/
├── frontend/                         ← React 19 + TypeScript + Vite + Tailwind 4
│   ├── index.html
│   ├── package.json                  ← React 19, @tauri-apps/api, lucide-react, react-router-dom
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── src/
│       ├── main.tsx
│       ├── App.tsx                   ← Router: /login → /workspace → /launch
│       ├── context/
│       │   └── AuthContext.tsx       ← ADAPTADO: invoke() en vez de axios/localStorage
│       ├── pages/
│       │   ├── Login.tsx             ← REUTILIZADO del dashboard (copia directa)
│       │   ├── Workspace.tsx         ← NUEVO: lista proyectos + crear + stack profile
│       │   └── FrLauncher.tsx        ← ADAPTADO: URLs dinámicas + write_artifacts + tests locales
│       ├── lib/
│       │   └── tauri.ts              ← Bridge tipado: invoke() wrappers con tipos
│       └── api/
│           └── client.ts             ← ADAPTADO: baseURL dinámica + refresh via invoke
└── src-tauri/
    ├── build.rs
    ├── Cargo.toml
    ├── tauri.conf.json
    ├── capabilities/
    │   └── default.json              ← Permisos: dialog:allow-open, shell:allow-open, etc.
    └── src/
        ├── lib.rs                    ← Entry point, plugins, generate_handler![]
        ├── auth.rs                   ← Login email+password, refresh, logout, me
        ├── keyring_store.rs          ← Keychain nativo (existente, ajustar API v3)
        ├── state.rs                  ← AppState: Mutex<Inner> {token, engine_url, client}
        ├── config.rs                 ← SQLite: engine_url preferida
        ├── workspace.rs              ← pick_folder, read_context, write_artifacts, run_tests
        └── error.rs                  ← AppError serializable al frontend
```

---

## Cargo.toml definitivo

```toml
[package]
name = "ovd-desktop"
version = "0.1.0"
description = "OVD Platform Desktop Client"
authors = ["Codigonet Cloud"]
edition = "2021"

[lib]
name = "ovd_desktop_lib"
crate-type = ["staticlib", "cdylib", "rlib"]

[build-dependencies]
tauri-build = { version = "2", features = [] }

[dependencies]
# Tauri core
tauri                         = { version = "2", features = ["protocol-asset"] }
tauri-plugin-shell            = "2"
tauri-plugin-dialog           = "2"
tauri-plugin-os               = "2"
tauri-plugin-updater          = "2"
tauri-plugin-single-instance  = "2"

# Serialización
serde       = { version = "1", features = ["derive"] }
serde_json  = "1"

# HTTP — rustls (sin OpenSSL), cookies para manejar Set-Cookie del engine
reqwest = { version = "0.13", default-features = false, features = [
    "json", "rustls-tls", "gzip", "stream", "cookies"
] }
tokio = { version = "1", features = ["full"] }

# Keychain nativo del SO (v3 — requiere use_native_store + release_store)
keyring = { version = "3", features = [
    "apple-native", "windows-native", "sync-secret-service"
] }

# Config local (engine URL preferida)
rusqlite = { version = "0.32", features = ["bundled"] }

# ZIP extracción en memoria (zip2 = fork activo de zip)
zip2 = "2"

# Errores y logging
thiserror = "1"
anyhow    = "1"
tracing   = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }

[features]
default = ["custom-protocol"]
custom-protocol = ["tauri/custom-protocol"]
```

---

## Pantallas en detalle

### Login

**Origen:** copia directa de `src/dashboard/src/pages/Login.tsx` — sin cambios visuales.

**Adaptación en AuthContext.tsx:**
```typescript
// ANTES (dashboard)
const data = await authApi.login(email, password)
localStorage.setItem('ovd_access_token', data.access_token)

// DESPUÉS (desktop)
const data = await invoke<LoginResult>('auth_login', { email, password })
// access_token va a React state (no localStorage — Rust lo maneja en AppState)
// refresh_token lo guarda Rust en Keychain automáticamente
```

**Flujo Rust (`auth.rs`):**
```
POST {engine_url}/auth/login
  body: {email, password}
  → response.headers().get_all(SET_COOKIE) → parsear ovd_refresh_token
  → keyring::Entry::new("ovd-desktop", email)?.set_password(refresh_token)?
  → AppState.token = access_token (RAM)
  → retorna LoginResult {access_token, org_id, user_id, email, role}
```

### Workspace

**Origen:** nuevo componente, combina lógica de `Projects.tsx` del dashboard adaptada.

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│ OVD Platform                         [omar@...]  [↩] │
├─────────────────────────────────────────────────────┤
│ Engine                                              │
│  ○ Local   http://localhost:8001                    │
│  ● DO      https://ovd-platform.codigonet.cloud     │
├─────────────────────────────────────────────────────┤
│ Proyectos                              [+ Nuevo]    │
│  ┌──────────────────────────────────────────────┐   │
│  │ ▶ Sistema RRHH    /Users/omar/rrhh           │   │
│  │   API Pagos       /Users/omar/pagos     [→]  │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│ [Proyecto seleccionado: Sistema RRHH]               │
│  Stack Profile ──────────────────────────────────   │
│  Lenguaje: python     Framework: fastapi            │
│  DB: postgresql       Runtime: python 3.12          │
│  Herramientas QA: pytest    ← define comando tests  │
│  [Guardar perfil]                                   │
│                                                     │
│  [ Lanzar FR → ]                                    │
└─────────────────────────────────────────────────────┘
```

**Modal "Nuevo proyecto"** (reutiliza UI de `Projects.tsx`):
- Nombre
- Directorio → `invoke('workspace_pick_folder')` → selector nativo
- Descripción (opcional)
- `POST /api/v1/orgs/{org_id}/projects` con `{name, directory, description}`

**Stack Profile** (reutiliza `Projects.tsx`):
- `PUT /api/v1/orgs/{org_id}/projects/{id}/profile`
- El campo "Herramientas QA" define el comando para tests locales

### FrLauncher

**Origen:** adaptación de `src/dashboard/src/pages/FrLauncher.tsx`.

**Barra de contexto (siempre visible — formulario + streaming + done):**

```
┌─────────────────────────────────────────────────────────┐
│  Cliente: Codigonet Cloud          omar@omarrobles.dev  │
│  Proyecto: Sistema RRHH   /Users/omar/rrhh              │
└─────────────────────────────────────────────────────────┘
```

Implementación:
```typescript
// Componente fijo en la parte superior del FrLauncher
function ContextBar({ project, user, orgName }: ContextBarProps) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg px-4 py-2.5 mb-4 font-mono text-xs">
      <div className="flex justify-between text-gray-300">
        <span><span className="text-gray-500">Cliente:</span> {orgName}</span>
        <span className="text-gray-400">{user.email}</span>
      </div>
      <div className="flex justify-between mt-0.5 text-gray-400">
        <span><span className="text-gray-500">Proyecto:</span> {project.name}</span>
        <span className="text-gray-600 truncate ml-4">{project.directory}</span>
      </div>
    </div>
  )
}
```

`orgName` se obtiene al cargar el Workspace: `GET /api/v1/orgs/{org_id}` → `{name, ...}`.
Si el endpoint no devuelve nombre, se usa `org_id` como fallback hasta que se mejore.

**4 cambios de código mínimos:**

```typescript
// 1. EventSource — URL absoluta
const es = new EventSource(
  `${engineUrl}/session/${sid}/stream?token=${encodeURIComponent(token)}`
)

// 2. POST /session — URL absoluta
const res = await fetch(`${engineUrl}/session`, {
  method: 'POST',
  headers: { Authorization: `Bearer ${getToken()}`, ... },
  body: JSON.stringify({ ..., project_context: await readProjectContext() }),
})

// 3. POST approve — URL absoluta
await fetch(`${engineUrl}/session/${sessionId}/approve`, { ... })

// 4. evento 'done' — guardar en carpeta + tests locales (reemplaza handleDownloadArtifacts)
async function handleSaveToFolder() {
  const result = await invoke<WriteResult>('workspace_write_artifacts', {
    sessionId, folder: currentProject.directory
  })
  pushLog(`✓ ${result.files_written} archivos escritos en ${currentProject.directory}`)

  // Tests locales
  if (currentProject.qa_tools) {
    const tests = await invoke<TestResult>('workspace_run_tests', {
      folder: currentProject.directory,
      command: currentProject.qa_tools,
      timeoutSecs: 120
    })
    pushLog(tests.passed ? `✓ Tests: ${tests.summary}` : `✗ Tests: ${tests.summary}`)
  }
}
```

**Mejoras UI incorporadas** (patrones de AutoGen + Langflow):

```typescript
// NodeStatus enum con ring animation en nodo activo
type NodeStatus = 'idle' | 'running' | 'done' | 'error'

// Nodo activo: ring-2 ring-violet-400 animate-pulse
// Nodo done: CheckCircle (verde)
// Nodo error: AlertTriangle (rojo)
// Nodo idle: círculo outline gris

// Streaming log: cursor parpadeante en último mensaje activo
// Badge por nodo completado: duración + timestamp
// Modal expandible para tokens/detalles del agente
```

**Reconnect con Last-Event-ID** (patrón Goose):
```typescript
// Al reconectar, enviar el último event ID para replay
const es = new EventSource(
  `${engineUrl}/session/${sid}/stream?token=${token}&last_event_id=${lastEventId}`
)
```

---

## Commands Rust definitivos

| Command | Input | Output | Descripción |
|---|---|---|---|
| `auth_login` | `{email, password}` | `LoginResult` | POST /auth/login → Keychain + AppState |
| `auth_logout` | — | `()` | POST /auth/logout → limpiar Keychain |
| `auth_is_authenticated` | — | `bool` | Verifica token en AppState (sin red) |
| `auth_get_current_user` | — | `UserProfile` | GET /auth/me |
| `auth_refresh_token` | — | `String` (token) | Keychain → POST /auth/refresh |
| `workspace_pick_folder` | — | `Option<String>` | Dialog nativo del SO |
| `workspace_read_context` | `{folder}` | `String` (≤50 KB) | Lee .py/.ts/.sql/.md para project_context |
| `workspace_write_artifacts` | `{session_id, folder}` | `WriteResult` | Descarga ZIP → extrae → escribe archivos |
| `workspace_run_tests` | `{folder, command, timeout_secs}` | `TestResult` | Subprocess local + stream output + kill en timeout |
| `config_get` | — | `Config` | Lee engine_url de SQLite |
| `config_save` | `{engine_url}` | `()` | Guarda preferencia |

**Structs de retorno:**
```rust
#[derive(Serialize)]
pub struct WriteResult {
    pub files_written: usize,
    pub paths: Vec<String>,
}

#[derive(Serialize)]
pub struct TestResult {
    pub passed: bool,
    pub exit_code: i32,
    pub summary: String,     // "5 passed, 1 failed" etc.
    pub output: String,      // stdout completo (máx 10KB)
}

#[derive(Serialize)]
pub struct Config {
    pub engine_url: String,  // default: "https://ovd-platform.codigonet.cloud"
}
```

---

## Implementación Rust clave

### state.rs
```rust
use std::sync::Mutex;
use reqwest::Client;

pub struct AppStateInner {
    pub access_token: Option<String>,
    pub engine_url: String,
    pub http_client: Client,
}

pub struct AppState(pub Mutex<AppStateInner>);

impl AppState {
    pub fn new() -> Self {
        let client = Client::builder()
            .https_only(false)   // false para permitir localhost en dev
            .cookie_store(true)  // manejar cookies automáticamente
            .build()
            .expect("http client");
        AppState(Mutex::new(AppStateInner {
            access_token: None,
            engine_url: "https://ovd-platform.codigonet.cloud".to_string(),
            http_client: client,
        }))
    }
}
```

### auth.rs — patrón keyring v3
```rust
use keyring::{use_native_store, release_store};

pub fn init_keyring() {
    // Llamar una vez al arrancar la app en lib.rs::setup()
    let _ = use_native_store(false); // false = default nativo del SO
}

pub fn shutdown_keyring() {
    release_store(); // Llamar al cerrar la app
}

pub fn save_refresh_token(email: &str, token: &str) -> AppResult<()> {
    let entry = keyring::Entry::new("ovd-desktop", email)?;
    entry.set_password(token)?;
    Ok(())
}
```

### workspace.rs — write_artifacts
```rust
use std::io::Cursor;
use zip2::ZipArchive;

pub async fn write_artifacts_impl(
    bytes: Vec<u8>,
    target_folder: &Path,
) -> AppResult<WriteResult> {
    let cursor = Cursor::new(bytes);
    let mut archive = ZipArchive::new(cursor)?;
    let mut paths = Vec::new();

    for i in 0..archive.len() {
        let mut file = archive.by_index(i)?;
        if file.is_dir() { continue; }
        let out_path = target_folder.join(file.name());
        if let Some(parent) = out_path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let mut buf = Vec::new();
        std::io::Read::read_to_end(&mut file, &mut buf)?;
        std::fs::write(&out_path, &buf)?;
        paths.push(file.name().to_string());
    }

    Ok(WriteResult { files_written: paths.len(), paths })
}
```

### workspace.rs — run_tests con timeout y kill
```rust
use tokio::process::Command;
use tokio::time::{timeout, Duration};

pub async fn run_tests_impl(
    folder: &Path,
    command: &str,
    timeout_secs: u64,
) -> AppResult<TestResult> {
    let parts: Vec<&str> = command.split_whitespace().collect();
    let (cmd, args) = parts.split_first()
        .ok_or_else(|| AppError::InvalidOperation("comando vacío".into()))?;

    let mut child = Command::new(cmd)
        .args(args)
        .current_dir(folder)
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()?;

    let result = timeout(Duration::from_secs(timeout_secs), child.wait_with_output()).await;

    match result {
        Ok(Ok(output)) => {
            let stdout = String::from_utf8_lossy(&output.stdout).to_string();
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            let combined = format!("{}\n{}", stdout, stderr);
            let passed = output.status.success();
            // Extraer resumen (e.g., "5 passed, 1 failed")
            let summary = extract_test_summary(&combined);
            Ok(TestResult {
                passed,
                exit_code: output.status.code().unwrap_or(-1),
                summary,
                output: combined.chars().take(10000).collect(),
            })
        }
        Ok(Err(e)) => Err(AppError::Io(e)),
        Err(_) => {
            let _ = child.kill().await;
            Err(AppError::Timeout(format!("tests superaron {}s", timeout_secs)))
        }
    }
}
```

---

## Cambios a OVD Platform (engine) — solo configuración

**`.env` local:**
```bash
OVD_CORS_ORIGINS=http://localhost:5173,tauri://localhost,http://localhost:1420
```

**Panel DO App Platform** → Variables de entorno → `OVD_CORS_ORIGINS`:
```
agregar: ,tauri://localhost
```

Ningún cambio de código Python. El CORSMiddleware de FastAPI ya acepta la lista dinámica.

---

## Diseño visual (DESIGN.md)

Inspirado en patrones de VoltAgent/awesome-design-md + AutoGen Studio:

| Token | Valor |
|---|---|
| Background principal | `gray-950` (`#0a0a0a`) |
| Surface cards | `gray-900` (`#111111`) |
| Bordes | `gray-800` |
| Acento primario | `violet-500/600` |
| Acento secundario | `emerald-500` |
| Texto primario | `white` |
| Texto secundario | `gray-400` |
| Error | `red-400` |
| Éxito | `green-400` |
| Warning | `yellow-400` |
| Nodo activo | `ring-2 ring-violet-400` |
| Nodo completado | `CheckCircle` verde |
| Nodo error | `AlertTriangle` rojo |
| Nodo en espera | `circle` outline `gray-600` |
| Log streaming cursor | `animate-pulse` en último char |
| Font | Inter (system-ui fallback) |

---

## Fases de implementación — detalle

### F0 — Prerrequisitos + estructura (0.5 días)

**Bloqueante:** instalar Tauri CLI (no está en el entorno):
```bash
cargo install tauri-cli --version "^2"
```

**Tareas:**
1. Crear `src/desktop/` en el repo ovd-platform
2. `cd src/desktop && cargo tauri init` — genera estructura base
3. Reemplazar `Cargo.toml` generado con el definitivo de este plan
4. Crear `frontend/package.json` con deps: `react@19`, `@tauri-apps/api`, `react-router-dom`, `lucide-react`, `tailwindcss@4`
5. Configurar `tauri.conf.json` (CSP, bundle targets, updater stub)
6. Configurar `capabilities/default.json` con permisos mínimos
7. Crear módulos Rust vacíos: `auth.rs`, `state.rs`, `config.rs`, `workspace.rs`, `error.rs`
8. Verificar `npm run tauri dev` arranca (aunque sin funcionalidad)

**Criterio de aceptación:** `cargo tauri dev` abre una ventana vacía sin errores de compilación.

---

### F1 — Rust core: error + state + auth + config (1.5 días)

**Tareas:**

**error.rs:**
```rust
#[derive(Debug, thiserror::Error, Serialize)]
pub enum AppError {
    #[error("error de red: {0}")] Network(String),
    #[error("no autenticado")]     Unauthorized,
    #[error("token expirado")]     TokenExpired,
    #[error("keyring: {0}")]       Keyring(String),
    #[error("io: {0}")]            Io(String),
    #[error("timeout: {0}")]       Timeout(String),
    #[error("{0}")]                InvalidOperation(String),
}
// impl From<reqwest::Error>, From<std::io::Error>, From<keyring::Error>
// impl serde::Serialize para que tauri lo serialice al frontend como { error: "..." }
```

**state.rs:** AppState con Mutex<Inner> (ver sección anterior)

**auth.rs:** 5 commands:
- `auth_login`: POST /auth/login, parsear Set-Cookie, guardar en Keychain, retornar access_token
- `auth_logout`: POST /auth/logout con Cookie header, limpiar Keychain
- `auth_is_authenticated`: verificar AppState.token sin llamar al engine
- `auth_get_current_user`: GET /auth/me con Bearer token
- `auth_refresh_token`: leer Keychain → POST /auth/refresh con Cookie header → nuevo token

**config.rs:**
- SQLite en `$APPDATA/ovd-desktop/config.db` (via `dirs` crate o `tauri::path::app_data_dir`)
- Tabla: `config(key TEXT, value TEXT)`
- Solo key: `engine_url`, default: `https://ovd-platform.codigonet.cloud`
- Commands: `config_get`, `config_save`

**lib.rs:** registrar todos los commands con `generate_handler![]` + llamar `init_keyring()` en setup

**Criterio de aceptación:** `cargo build` sin errores + test manual login desde un script Rust.

---

### F2 — workspace.rs: pick_folder + read_context + write_artifacts + run_tests (1 día)

**workspace_pick_folder:**
```rust
use tauri_plugin_dialog::DialogExt;
// Abrir picker de directorio con texto descriptivo
```

**workspace_read_context:**
- `walkdir` o `std::fs::read_dir` recursivo (agregar `walkdir = "2"` a Cargo.toml)
- Filtrar extensiones: `.py`, `.ts`, `.tsx`, `.js`, `.sql`, `.md`, `.rs`, `.go`, `.java`, `.yaml`, `.yml`, `.toml`
- Excluir: `.git/`, `node_modules/`, `__pycache__/`, `.venv/`, `target/`, `dist/`
- Cap: 50 KB total — truncar los archivos más grandes si excede
- Retorna String con formato: `--- archivo.py ---\n{content}\n`

**workspace_write_artifacts:** (ver implementación en sección anterior)
- Descargar ZIP desde `GET {engine_url}/session/{id}/artifacts/download`
- Authorization: Bearer token desde AppState
- Extraer en memoria con zip2
- Escribir archivos respetando la estructura de directorios

**workspace_run_tests:** (ver implementación con timeout en sección anterior)

**Agregar a Cargo.toml:**
```toml
walkdir = "2"
```

**Criterio de aceptación:** test unitario que extrae un ZIP de prueba y verifica archivos escritos en `/tmp/test_workspace`.

---

### F3 — Frontend bridge + AuthContext + api/client (0.5 días)

**lib/tauri.ts** — wrappers tipados:
```typescript
import { invoke } from '@tauri-apps/api/core'

export interface LoginResult {
  access_token: string; org_id: string; user_id: string; email: string; role: string
}
export interface WriteResult { files_written: number; paths: string[] }
export interface TestResult { passed: boolean; exit_code: number; summary: string; output: string }
export interface Config { engine_url: string }

export const tauriAuth = {
  login:            (email: string, password: string) =>
                      invoke<LoginResult>('auth_login', { email, password }),
  logout:           () => invoke<void>('auth_logout'),
  isAuthenticated:  () => invoke<boolean>('auth_is_authenticated'),
  getCurrentUser:   () => invoke<UserProfile>('auth_get_current_user'),
  refreshToken:     () => invoke<string>('auth_refresh_token'),
}

export const tauriWorkspace = {
  pickFolder:      () => invoke<string | null>('workspace_pick_folder'),
  readContext:     (folder: string) => invoke<string>('workspace_read_context', { folder }),
  writeArtifacts:  (sessionId: string, folder: string) =>
                     invoke<WriteResult>('workspace_write_artifacts', { sessionId, folder }),
  runTests:        (folder: string, command: string, timeoutSecs = 120) =>
                     invoke<TestResult>('workspace_run_tests', { folder, command, timeoutSecs }),
}

export const tauriConfig = {
  get:  () => invoke<Config>('config_get'),
  save: (engineUrl: string) => invoke('config_save', { engineUrl }),
}
```

**AuthContext.tsx adaptado:**
- Reemplaza axios + localStorage por `tauriAuth.*`
- `getToken()` lee del state React (no localStorage)
- Auto-refresh: on 401, llama `tauriAuth.refreshToken()`, actualiza state, reintenta

**api/client.ts adaptado:**
- Elimina axios + baseURL fija
- `getEngineUrl()` retorna la URL configurada (cargada al arrancar desde `tauriConfig.get()`)
- Función `apiFetch(path, options)` que añade Authorization + maneja 401 → refresh

**Criterio de aceptación:** Login funcional en ventana Tauri, token visible en AppState Rust.

---

### F4 — Pantallas: Login + Workspace + App routing (2 días)

**Login.tsx:**
- Copia directa de `src/dashboard/src/pages/Login.tsx`
- Conecta a `AuthContext` adaptado — sin cambios visuales
- Navega a `/workspace` tras login exitoso

**App.tsx:**
```typescript
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'

export default function App() {
  const { user, loading } = useAuth()
  if (loading) return <SplashScreen />
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={!user ? <Login /> : <Navigate to="/workspace" />} />
        <Route path="/workspace" element={user ? <Workspace /> : <Navigate to="/login" />} />
        <Route path="/launch" element={user ? <FrLauncher /> : <Navigate to="/login" />} />
        <Route path="*" element={<Navigate to={user ? "/workspace" : "/login"} />} />
      </Routes>
    </BrowserRouter>
  )
}
```

**Workspace.tsx (pantalla más compleja — 1.5 días):**

Secciones:
1. **Header engine toggle:** ○ Local / ● DO → `tauriConfig.save(url)`
2. **Lista de proyectos:** `GET /api/v1/orgs/{org_id}/projects` → cards con nombre + directory
3. **Modal crear proyecto:**
   - Input nombre, description
   - Selector carpeta: `tauriWorkspace.pickFolder()` → muestra path
   - Submit: `POST /api/v1/orgs/{org_id}/projects`
4. **Stack Profile inline** (proyecto seleccionado):
   - Campos: lenguaje, framework, db, runtime, qa_tools, restricciones, integraciones, stack_legado
   - Submit: `PUT /api/v1/orgs/{org_id}/projects/{id}/profile`
5. **Botón "Lanzar FR"** → navega a `/launch` con `project` en state

**Criterio de aceptación:** crear proyecto con carpeta local, guardar stack profile, ver en lista.

---

### F5 — FrLauncher adaptado (1 día)

**Base:** copia de `src/dashboard/src/pages/FrLauncher.tsx`

**Cambios:**
1. URLs: `/session/...` → `${getEngineUrl()}/session/...` (3 ocurrencias)
2. Token: `localStorage.getItem('ovd_access_token')` → `getToken()` del contexto
3. `project_context`: antes del submit, si proyecto existente:
   ```typescript
   const projectContext = await tauriWorkspace.readContext(currentProject.directory)
   // inyectar en el body del POST /session
   ```
4. Reemplazar `handleDownloadArtifacts` con `handleSaveToFolder` (ver sección pantallas)
5. Botón: "Descargar código" → "Guardar en carpeta"
6. Sección post-done: mostrar resultado write + resultado tests locales

**Mejoras UI (de investigación):**
- `NodeStatus` enum con colores Tailwind + ring-2 en nodo activo
- `CheckCircle` / `AlertTriangle` / `Loader2 animate-spin` para estados
- Badge con duración por nodo completado (timestamp `node_end` - `node_start`)
- Cursor `animate-pulse` en la última línea del log activo
- Sección "Tests locales" plegable con output completo expandible

**Criterio de aceptación:** ciclo completo Login → Workspace → FR → escritura en carpeta → tests locales.

---

### F6 — Configuración final: CSP + CORS + capabilities (0.5 días)

**tauri.conf.json — CSP definitivo:**
```json
"csp": "default-src 'self' ipc: http://ipc.localhost; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: asset: http://asset.localhost; connect-src 'self' ipc: http://ipc.localhost http://localhost:* https://*.codigonet.cloud https://*.ondigitalocean.app; font-src 'self' data:"
```

**capabilities/default.json — permisos finales:**
```json
{
  "permissions": [
    "core:default",
    "core:window:allow-close",
    "core:window:allow-minimize",
    "core:window:allow-maximize",
    "core:window:allow-unmaximize",
    "core:window:allow-start-dragging",
    "shell:allow-open",
    "dialog:allow-open",
    "os:default",
    "updater:default"
  ]
}
```

**Engine `.env` local:**
```bash
OVD_CORS_ORIGINS=http://localhost:5173,tauri://localhost,http://localhost:1420
```

**Panel DO App Platform → Environment Variables:**
```
OVD_CORS_ORIGINS: [valor_actual],tauri://localhost
```

**Criterio de aceptación:** app conecta a engine local Y a DO sin errores CORS.

---

### F7 — Build + smoke test + release workflow (0.5 días)

1. `npm run tauri build` en macOS Apple Silicon → genera `.dmg`
2. Smoke test completo: Login → Workspace → crear proyecto → lanzar FR → verificar archivos en carpeta → tests locales
3. Crear `.github/workflows/release-desktop.yml` (adaptar `release.yml` existente en los files de referencia)
4. Tag `desktop-v0.1.0` → trigger CI → verificar artifacts en GitHub Releases

**Criterio de aceptación:** `.dmg` instala y corre en macOS ARM sin errores de firma (sin notarization en v0.1).

---

## Resumen de fases

| Fase | Contenido | Días |
|---|---|---|
| **F0** | Prerrequisitos + estructura base | 0.5 |
| **F1** | Rust: error + state + auth + config | 1.5 |
| **F2** | Rust: workspace (pick/read/write/tests) | 1 |
| **F3** | Frontend: lib/tauri.ts + AuthContext + client | 0.5 |
| **F4** | Pantallas: Login + Workspace + routing | 2 |
| **F5** | FrLauncher adaptado + mejoras UI | 1 |
| **F6** | CSP + CORS + capabilities | 0.5 |
| **F7** | Build + smoke test + CI release | 0.5 |
| **Total** | | **7.5 días** |

---

## Release CI/CD

Archivo: `.github/workflows/release-desktop.yml`

- Trigger: `push tags: ["desktop-v*"]`
- Matrix: macOS aarch64, macOS x86_64, Ubuntu 22.04, Windows
- Secrets necesarios: `TAURI_SIGNING_PRIVATE_KEY`, `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`
- macOS sin notarization en v0.1 — agregar en v1.0 si se distribuye públicamente
- Artifacts: `.dmg`, `.msi`, `.nsis`, `.deb`, `.appimage`

---

## Iteraciones post-MVP

| Versión | Funcionalidad |
|---|---|
| v0.2 | Historial de ciclos (Cycles.tsx adaptado) |
| v0.2 | Reconexión automática con Last-Event-ID replay buffer |
| v0.3 | Telemetría (Telemetry.tsx adaptado) |
| v0.3 | Detección automática de stack desde la carpeta |
| v0.4 | Notificaciones nativas del SO al completar ciclo |
| v0.4 | Múltiples workspaces simultáneos |
| v0.5 | Cliente API generado desde OpenAPI schema del engine (`@hey-api/openapi-ts`) |
| v1.0 | macOS notarization + Apple Developer Program |
| v1.0 | Auto-update firmado con Ed25519 |
| v1.0 | DESIGN.md del proyecto para contexto del agente frontend |

---

## Preguntas abiertas

- [x] ¿Distribución pública o uso interno? → **Uso interno**
- [x] ¿Apple Developer Program disponible? → **No — no requerido para uso interno**
- [x] ¿El updater automático es requerido desde v0.1? → **Sí, es MVP**
- [ ] ¿Logo/icono específico? → **Pendiente — placeholder Tauri en v0.1**
