use crate::error::{AppError, AppResult};
use crate::state::AppState;
use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use tauri::State;

const DEFAULT_ENGINE_URL: &str = "https://ovd-platform.codigonet.cloud";

/// Carga la URL guardada en SQLite y la sincroniza en AppState al arrancar.
pub fn init_from_db(state: &AppState) {
    if let Ok(conn) = open_db() {
        let engine_url: String = conn
            .query_row(
                "SELECT value FROM config WHERE key = 'engine_url'",
                [],
                |row| row.get(0),
            )
            .unwrap_or_else(|_| DEFAULT_ENGINE_URL.to_string());
        let mut s = state.0.lock().unwrap();
        s.engine_url = engine_url;
    }
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Config {
    pub engine_url: String,
}

fn db_path() -> PathBuf {
    let base = dirs_next::data_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("ovd-desktop");
    std::fs::create_dir_all(&base).ok();
    base.join("config.db")
}

fn open_db() -> AppResult<Connection> {
    let conn = Connection::open(db_path())
        .map_err(|e| AppError::InvalidOperation(format!("sqlite: {e}")))?;
    conn.execute_batch(
        "CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT NOT NULL);",
    )
    .map_err(|e| AppError::InvalidOperation(format!("sqlite init: {e}")))?;
    Ok(conn)
}

#[tauri::command]
pub async fn config_get(state: State<'_, AppState>) -> Result<Config, String> {
    _config_get(state).await.map_err(|e| e.to_string())
}

async fn _config_get(state: State<'_, AppState>) -> AppResult<Config> {
    let conn = open_db()?;
    let engine_url: String = conn
        .query_row(
            "SELECT value FROM config WHERE key = 'engine_url'",
            [],
            |row| row.get(0),
        )
        .unwrap_or_else(|_| DEFAULT_ENGINE_URL.to_string());

    // Sincronizar AppState con la URL guardada
    {
        let mut s = state.0.lock().unwrap();
        s.engine_url = engine_url.clone();
    }

    Ok(Config { engine_url })
}

#[tauri::command]
pub async fn config_save(
    engine_url: String,
    state: State<'_, AppState>,
) -> Result<(), String> {
    _config_save(engine_url, state).await.map_err(|e| e.to_string())
}

async fn _config_save(engine_url: String, state: State<'_, AppState>) -> AppResult<()> {
    let conn = open_db()?;
    conn.execute(
        "INSERT INTO config (key, value) VALUES ('engine_url', ?1)
         ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        params![engine_url],
    )
    .map_err(|e| AppError::InvalidOperation(format!("sqlite write: {e}")))?;

    // Actualizar AppState
    {
        let mut s = state.0.lock().unwrap();
        s.engine_url = engine_url;
    }

    Ok(())
}
