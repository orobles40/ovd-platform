use crate::error::{AppError, AppResult};
use crate::state::AppState;
use serde::{Deserialize, Serialize};
use std::io::Read;
use std::path::Path;
use tauri::State;
use walkdir::WalkDir;

const MAX_CONTEXT_BYTES: usize = 50 * 1024; // 50 KB
const MAX_TEST_OUTPUT_BYTES: usize = 10 * 1024; // 10 KB

// Extensiones de código que se incluyen en el project_context
const CODE_EXTENSIONS: &[&str] = &[
    "py", "ts", "tsx", "js", "jsx", "sql", "md", "rs", "go", "java",
    "yaml", "yml", "toml", "json", "env.example",
];

// Directorios que se excluyen al leer el contexto
const EXCLUDED_DIRS: &[&str] = &[
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "target", "dist", "build", ".next", ".nuxt",
];

#[derive(Debug, Serialize, Deserialize)]
pub struct WriteResult {
    pub files_written: usize,
    pub paths: Vec<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct TestResult {
    pub passed: bool,
    pub exit_code: i32,
    pub summary: String,
    pub output: String,
}

// ── Commands ─────────────────────────────────────────────────────────────────

#[tauri::command]
pub async fn workspace_pick_folder(app: tauri::AppHandle) -> Result<Option<String>, String> {
    use tauri_plugin_dialog::DialogExt;
    let folder = app
        .dialog()
        .file()
        .set_title("Seleccionar carpeta del proyecto")
        .blocking_pick_folder();
    Ok(folder.map(|p| p.to_string()))
}

#[tauri::command]
pub async fn workspace_read_context(folder: String) -> Result<String, String> {
    _read_context(&folder).map_err(|e| e.to_string())
}

fn _read_context(folder: &str) -> AppResult<String> {
    let base = Path::new(folder);
    if !base.exists() {
        return Err(AppError::InvalidOperation(format!("carpeta no existe: {folder}")));
    }

    let mut result = String::new();
    let mut total_bytes = 0usize;

    for entry in WalkDir::new(base)
        .follow_links(false)
        .into_iter()
        .filter_entry(|e| {
            // Excluir directorios bloqueados
            if e.file_type().is_dir() {
                let name = e.file_name().to_string_lossy();
                return !EXCLUDED_DIRS.iter().any(|d| *d == name.as_ref());
            }
            true
        })
        .filter_map(|e| e.ok())
        .filter(|e| e.file_type().is_file())
    {
        let path = entry.path();
        let ext = path.extension().and_then(|s| s.to_str()).unwrap_or("");
        if !CODE_EXTENSIONS.contains(&ext) {
            continue;
        }

        if total_bytes >= MAX_CONTEXT_BYTES {
            break;
        }

        let rel_path = path.strip_prefix(base).unwrap_or(path);
        let content = match std::fs::read_to_string(path) {
            Ok(c) => c,
            Err(_) => continue,
        };

        let remaining = MAX_CONTEXT_BYTES - total_bytes;
        let chunk = if content.len() > remaining {
            &content[..remaining]
        } else {
            &content
        };

        result.push_str(&format!("--- {} ---\n{}\n\n", rel_path.display(), chunk));
        total_bytes += chunk.len();
    }

    Ok(result)
}

/// S125: abre la carpeta en el explorador del sistema operativo (Finder en macOS).
#[tauri::command]
pub async fn workspace_open_folder(folder: String) -> Result<(), String> {
    #[cfg(target_os = "macos")]
    let cmd = ("open", vec![folder.clone()]);
    #[cfg(target_os = "windows")]
    let cmd = ("explorer", vec![folder.clone()]);
    #[cfg(target_os = "linux")]
    let cmd = ("xdg-open", vec![folder.clone()]);

    std::process::Command::new(cmd.0)
        .args(&cmd.1)
        .spawn()
        .map_err(|e| format!("no se pudo abrir la carpeta: {e}"))?;
    Ok(())
}

#[tauri::command]
pub async fn workspace_write_artifacts(
    session_id: String,
    folder: String,
    state: State<'_, AppState>,
) -> Result<WriteResult, String> {
    _write_artifacts(session_id, folder, state)
        .await
        .map_err(|e| e.to_string())
}

async fn _write_artifacts(
    session_id: String,
    folder: String,
    state: State<'_, AppState>,
) -> AppResult<WriteResult> {
    let (engine_url, client, token) = {
        let s = state.0.lock().unwrap();
        let token = s.access_token.clone().ok_or(AppError::Unauthorized)?;
        (s.engine_url.clone(), s.http_client.clone(), token)
    };

    let url = format!("{engine_url}/session/{session_id}/artifacts/download");
    let resp = client
        .get(&url)
        .header("Authorization", format!("Bearer {token}"))
        .send()
        .await?;

    if !resp.status().is_success() {
        return Err(AppError::Network(format!(
            "download artifacts: {}",
            resp.status()
        )));
    }

    let bytes = resp.bytes().await.map_err(|e| AppError::Network(e.to_string()))?;

    let target = Path::new(&folder);
    std::fs::create_dir_all(target)?;

    let cursor = std::io::Cursor::new(bytes);
    let mut archive = zip::ZipArchive::new(cursor)?;
    let mut paths = Vec::new();

    for i in 0..archive.len() {
        let mut file = archive.by_index(i)?;
        if file.is_dir() {
            continue;
        }
        let name = file.name().to_owned();
        // Sanitizar ruta para evitar path traversal
        if name.contains("..") {
            continue;
        }
        let out_path = target.join(&name);
        if let Some(parent) = out_path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let mut buf = Vec::new();
        file.read_to_end(&mut buf)?;
        std::fs::write(&out_path, &buf)?;
        paths.push(name);
    }

    Ok(WriteResult {
        files_written: paths.len(),
        paths,
    })
}

#[tauri::command]
pub async fn workspace_run_tests(
    folder: String,
    command: String,
    timeout_secs: Option<u64>,
) -> Result<TestResult, String> {
    _run_tests(folder, command, timeout_secs.unwrap_or(120))
        .await
        .map_err(|e| e.to_string())
}

async fn _run_tests(
    folder: String,
    command: String,
    timeout_secs: u64,
) -> AppResult<TestResult> {
    let parts: Vec<&str> = command.split_whitespace().collect();
    let (cmd, args) = parts
        .split_first()
        .ok_or_else(|| AppError::InvalidOperation("comando de tests vacío".into()))?;

    let child = tokio::process::Command::new(cmd)
        .args(args)
        .current_dir(&folder)
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .map_err(|e| AppError::Io(format!("no se pudo ejecutar '{command}': {e}")))?;

    // wait_with_output consume child — capturamos id para poder matar en timeout
    let child_id = child.id();

    let result = tokio::time::timeout(
        tokio::time::Duration::from_secs(timeout_secs),
        child.wait_with_output(),
    )
    .await;

    match result {
        Ok(Ok(output)) => {
            let stdout = String::from_utf8_lossy(&output.stdout).to_string();
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            let combined = format!("{stdout}\n{stderr}");
            let passed = output.status.success();
            let summary = extract_test_summary(&combined, passed);
            let truncated: String = combined.chars().take(MAX_TEST_OUTPUT_BYTES).collect();
            Ok(TestResult {
                passed,
                exit_code: output.status.code().unwrap_or(-1),
                summary,
                output: truncated,
            })
        }
        Ok(Err(e)) => Err(AppError::Io(e.to_string())),
        Err(_) => {
            if let Some(pid) = child_id {
                let _ = tokio::process::Command::new("kill")
                    .arg(pid.to_string())
                    .spawn();
            }
            Err(AppError::Timeout(format!(
                "tests superaron el límite de {timeout_secs}s"
            )))
        }
    }
}

fn extract_test_summary(output: &str, passed: bool) -> String {
    // pytest: "5 passed, 1 failed in 2.3s"
    for line in output.lines().rev() {
        if line.contains("passed") || line.contains("failed") || line.contains("error") {
            let trimmed = line.trim();
            if trimmed.len() < 120 {
                return trimmed.to_string();
            }
        }
    }
    if passed {
        "Tests completados exitosamente".to_string()
    } else {
        "Tests fallaron — ver output para detalles".to_string()
    }
}
