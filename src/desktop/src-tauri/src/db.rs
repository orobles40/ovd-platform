use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

fn db_path() -> PathBuf {
    let base = dirs_next::data_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("ovd-desktop");
    std::fs::create_dir_all(&base).ok();
    base.join("config.db")
}

fn open_db() -> Result<Connection, String> {
    Connection::open(db_path()).map_err(|e| format!("sqlite: {e}"))
}

pub fn init_db() {
    if let Ok(conn) = open_db() {
        let _ = conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS cycle_history (
                thread_id         TEXT PRIMARY KEY,
                project_directory TEXT NOT NULL,
                fr_text           TEXT NOT NULL DEFAULT '',
                qa_score          INTEGER,
                security_score    INTEGER,
                tokens_in         INTEGER,
                tokens_out        INTEGER,
                elapsed_secs      REAL,
                files_written     INTEGER,
                output_dir        TEXT,
                status            TEXT NOT NULL DEFAULT 'completed',
                created_at        TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS error_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                level       TEXT NOT NULL,
                message     TEXT NOT NULL,
                context     TEXT NOT NULL DEFAULT '',
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );",
        );
    }
}

/// Escribe un error en error_log — sync, seguro de llamar desde el panic hook.
pub fn log_error(level: &str, message: &str, context: &str) {
    if let Ok(conn) = open_db() {
        let _ = conn.execute(
            "INSERT INTO error_log (level, message, context) VALUES (?1, ?2, ?3)",
            params![level, message, context],
        );
    }
}

// ── Tipos exportados al frontend ──────────────────────────────────────────────

#[derive(Debug, Serialize, Deserialize)]
pub struct CycleEntry {
    pub thread_id: String,
    pub project_directory: String,
    pub fr_text: String,
    pub qa_score: Option<i64>,
    pub security_score: Option<i64>,
    pub tokens_in: Option<i64>,
    pub tokens_out: Option<i64>,
    pub elapsed_secs: Option<f64>,
    pub files_written: Option<i64>,
    pub output_dir: Option<String>,
    pub status: String,
    pub created_at: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ErrorLogEntry {
    pub id: i64,
    pub level: String,
    pub message: String,
    pub context: String,
    pub created_at: String,
}

// ── Comandos Tauri ────────────────────────────────────────────────────────────

#[tauri::command]
pub async fn db_save_cycle(entry: CycleEntry) -> Result<(), String> {
    let conn = open_db()?;
    conn.execute(
        "INSERT INTO cycle_history
             (thread_id, project_directory, fr_text, qa_score, security_score,
              tokens_in, tokens_out, elapsed_secs, files_written, output_dir, status)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11)
         ON CONFLICT(thread_id) DO UPDATE SET
             qa_score       = excluded.qa_score,
             security_score = excluded.security_score,
             tokens_in      = excluded.tokens_in,
             tokens_out     = excluded.tokens_out,
             elapsed_secs   = excluded.elapsed_secs,
             files_written  = excluded.files_written,
             output_dir     = excluded.output_dir,
             status         = excluded.status",
        params![
            entry.thread_id,
            entry.project_directory,
            entry.fr_text,
            entry.qa_score,
            entry.security_score,
            entry.tokens_in,
            entry.tokens_out,
            entry.elapsed_secs,
            entry.files_written,
            entry.output_dir,
            entry.status,
        ],
    )
    .map_err(|e| format!("sqlite write cycle: {e}"))?;
    Ok(())
}

#[tauri::command]
pub async fn db_list_project_cycles(
    project_directory: String,
    limit: u32,
) -> Result<Vec<CycleEntry>, String> {
    let conn = open_db()?;
    let mut stmt = conn
        .prepare(
            "SELECT thread_id, project_directory, fr_text, qa_score, security_score,
                    tokens_in, tokens_out, elapsed_secs, files_written, output_dir, status, created_at
             FROM cycle_history
             WHERE project_directory = ?1
             ORDER BY created_at DESC
             LIMIT ?2",
        )
        .map_err(|e| format!("sqlite prepare: {e}"))?;

    let entries = stmt
        .query_map(params![project_directory, limit], |row| {
            Ok(CycleEntry {
                thread_id: row.get(0)?,
                project_directory: row.get(1)?,
                fr_text: row.get(2)?,
                qa_score: row.get(3)?,
                security_score: row.get(4)?,
                tokens_in: row.get(5)?,
                tokens_out: row.get(6)?,
                elapsed_secs: row.get(7)?,
                files_written: row.get(8)?,
                output_dir: row.get(9)?,
                status: row.get(10)?,
                created_at: row.get(11)?,
            })
        })
        .map_err(|e| format!("sqlite query: {e}"))?
        .filter_map(|r| r.ok())
        .collect();

    Ok(entries)
}

#[tauri::command]
pub async fn db_list_errors(limit: u32) -> Result<Vec<ErrorLogEntry>, String> {
    let conn = open_db()?;
    let mut stmt = conn
        .prepare(
            "SELECT id, level, message, context, created_at
             FROM error_log
             ORDER BY created_at DESC
             LIMIT ?1",
        )
        .map_err(|e| format!("sqlite prepare: {e}"))?;

    let entries = stmt
        .query_map(params![limit], |row| {
            Ok(ErrorLogEntry {
                id: row.get(0)?,
                level: row.get(1)?,
                message: row.get(2)?,
                context: row.get(3)?,
                created_at: row.get(4)?,
            })
        })
        .map_err(|e| format!("sqlite query: {e}"))?
        .filter_map(|r| r.ok())
        .collect();

    Ok(entries)
}
