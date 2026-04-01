// OVD Platform — Gestión de configuración local (~/.ovd/)
//
// Estructura de archivos:
//   ~/.ovd/config.toml   — perfiles de conexión (api_url, org_id, workspace activo)
//   ~/.ovd/tokens.toml   — tokens JWT (permisos 600, nunca en git)
//
// Similar a kubectl: múltiples perfiles, uno activo por defecto.

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

use crate::models::auth::StoredTokens;

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

pub fn ovd_dir() -> PathBuf {
    dirs::home_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join(".ovd")
}

pub fn config_path() -> PathBuf {
    ovd_dir().join("config.toml")
}

pub fn tokens_path() -> PathBuf {
    ovd_dir().join("tokens.toml")
}

fn ensure_ovd_dir() -> Result<()> {
    let dir = ovd_dir();
    if !dir.exists() {
        fs::create_dir_all(&dir)
            .with_context(|| format!("No se pudo crear directorio {}", dir.display()))?;
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Config de conexión
// ---------------------------------------------------------------------------

/// Perfil de conexión a una instancia OVD
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Profile {
    pub api_url: String,
    pub org_id: String,
    /// Workspace (proyecto) activo en este perfil
    pub workspace_id: Option<String>,
    pub workspace_name: Option<String>,
}

impl Default for Profile {
    fn default() -> Self {
        Self {
            api_url: "http://localhost:8000".into(),
            org_id: String::new(),
            workspace_id: None,
            workspace_name: None,
        }
    }
}

/// Archivo config.toml completo
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct AppConfig {
    /// Perfil activo (nombre de clave en `profiles`)
    pub active_profile: String,
    /// Perfiles disponibles
    #[serde(default)]
    pub profiles: std::collections::HashMap<String, Profile>,
}

impl AppConfig {
    pub fn load() -> Result<Self> {
        let path = config_path();
        if !path.exists() {
            return Ok(Self::default());
        }
        let content = fs::read_to_string(&path)
            .with_context(|| format!("No se pudo leer {}", path.display()))?;
        toml::from_str(&content).with_context(|| "config.toml tiene formato inválido")
    }

    pub fn save(&self) -> Result<()> {
        ensure_ovd_dir()?;
        let content = toml::to_string_pretty(self)?;
        fs::write(config_path(), content)?;
        Ok(())
    }

    /// Retorna el perfil activo, o el default si no hay ninguno configurado
    pub fn active(&self) -> Profile {
        self.profiles
            .get(&self.active_profile)
            .cloned()
            .unwrap_or_default()
    }

    /// Actualiza el workspace activo en el perfil activo
    pub fn set_workspace(&mut self, id: &str, name: &str) {
        let profile = self
            .profiles
            .entry(self.active_profile.clone())
            .or_default();
        profile.workspace_id = Some(id.to_string());
        profile.workspace_name = Some(name.to_string());
    }

    /// Inicializa con valores por defecto si no hay config
    pub fn init_default(api_url: &str, org_id: &str) -> Result<Self> {
        let mut cfg = Self::default();
        cfg.active_profile = "default".to_string();
        cfg.profiles.insert(
            "default".to_string(),
            Profile {
                api_url: api_url.to_string(),
                org_id: org_id.to_string(),
                workspace_id: None,
                workspace_name: None,
            },
        );
        cfg.save()?;
        Ok(cfg)
    }
}

// ---------------------------------------------------------------------------
// Tokens (almacenados separados de config por seguridad)
// ---------------------------------------------------------------------------

pub fn load_tokens() -> Result<StoredTokens> {
    let path = tokens_path();
    if !path.exists() {
        return Ok(StoredTokens::default());
    }
    let content = fs::read_to_string(&path)
        .with_context(|| format!("No se pudo leer {}", path.display()))?;
    toml::from_str(&content).with_context(|| "tokens.toml tiene formato inválido")
}

pub fn save_tokens(tokens: &StoredTokens) -> Result<()> {
    ensure_ovd_dir()?;
    let path = tokens_path();
    let content = toml::to_string_pretty(tokens)?;
    fs::write(&path, content)?;

    // Permisos 600 en Unix (propietario lectura/escritura únicamente)
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(&path, fs::Permissions::from_mode(0o600))?;
    }
    Ok(())
}

pub fn clear_tokens() -> Result<()> {
    let path = tokens_path();
    if path.exists() {
        fs::remove_file(path)?;
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Sesión activa (UX-02 — persistir thread_id entre reinicios)
// ---------------------------------------------------------------------------

pub fn session_path() -> PathBuf {
    ovd_dir().join("session.toml")
}

/// Sesión OVD en curso guardada en ~/.ovd/session.toml
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ActiveSession {
    pub thread_id: String,
    pub feature_request: String,
    /// Estado al momento de guardar: "streaming" | "pending_approval" | "done"
    pub status: String,
    /// Unix timestamp del inicio del ciclo
    pub started_at: u64,
}

pub fn save_session(session: &ActiveSession) -> Result<()> {
    ensure_ovd_dir()?;
    let content = toml::to_string_pretty(session)?;
    fs::write(session_path(), content)?;
    Ok(())
}

pub fn load_session() -> Option<ActiveSession> {
    let path = session_path();
    if !path.exists() {
        return None;
    }
    let content = fs::read_to_string(&path).ok()?;
    toml::from_str(&content).ok()
}

pub fn clear_session() -> Result<()> {
    let path = session_path();
    if path.exists() {
        fs::remove_file(path)?;
    }
    Ok(())
}
