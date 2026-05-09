use crate::error::{AppError, AppResult};
use crate::state::AppState;
use serde::{Deserialize, Serialize};
use tauri::State;

const KEYRING_SERVICE: &str = "ovd-desktop";

// ── Tipos ───────────────────────────────────────────────────────────────────

#[derive(Debug, Serialize, Deserialize)]
pub struct LoginResult {
    pub access_token: String,
    pub org_id: String,
    pub user_id: String,
    pub email: String,
    pub role: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct UserProfile {
    pub user_id: String,
    pub org_id: String,
    pub role: String,
    pub email: String,
}

#[derive(Debug, Deserialize)]
struct LoginResponse {
    access_token: String,
    #[allow(dead_code)]
    expires_in: Option<u64>,
}

// ── Keyring helpers ─────────────────────────────────────────────────────────

pub fn init_keyring() {
    let _ = keyring::set_default_credential_builder(keyring::default::default_credential_builder());
}

pub fn shutdown_keyring() {
    // keyring v3 no requiere cleanup explícito en esta versión
}

fn save_refresh_token(email: &str, token: &str) -> AppResult<()> {
    let entry = keyring::Entry::new(KEYRING_SERVICE, email)?;
    entry.set_password(token)?;
    Ok(())
}

fn load_refresh_token(email: &str) -> AppResult<Option<String>> {
    let entry = keyring::Entry::new(KEYRING_SERVICE, email)?;
    match entry.get_password() {
        Ok(t) => Ok(Some(t)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(e) => Err(AppError::Keyring(e.to_string())),
    }
}

fn delete_refresh_token(email: &str) -> AppResult<()> {
    let entry = keyring::Entry::new(KEYRING_SERVICE, email)?;
    match entry.delete_credential() {
        Ok(_) => Ok(()),
        Err(keyring::Error::NoEntry) => Ok(()),
        Err(e) => Err(AppError::Keyring(e.to_string())),
    }
}

// ── Commands ─────────────────────────────────────────────────────────────────

#[tauri::command]
pub async fn auth_login(
    email: String,
    password: String,
    state: State<'_, AppState>,
) -> Result<LoginResult, String> {
    _auth_login(email, password, state).await.map_err(|e| e.to_string())
}

async fn _auth_login(
    email: String,
    password: String,
    state: State<'_, AppState>,
) -> AppResult<LoginResult> {
    let (engine_url, client) = {
        let s = state.0.lock().unwrap();
        (s.engine_url.clone(), s.http_client.clone())
    };

    let resp = client
        .post(format!("{engine_url}/auth/login"))
        .json(&serde_json::json!({ "email": email, "password": password }))
        .send()
        .await?;

    if resp.status() == 401 {
        return Err(AppError::Unauthorized);
    }
    if !resp.status().is_success() {
        return Err(AppError::Network(format!("login error {}", resp.status())));
    }

    // Extraer refresh token del header Set-Cookie
    let refresh_token = resp
        .headers()
        .get_all("set-cookie")
        .iter()
        .find_map(|v| {
            let s = v.to_str().ok()?;
            if s.contains("ovd_refresh_token=") {
                s.split(';').next()?.strip_prefix("ovd_refresh_token=").map(String::from)
            } else {
                None
            }
        });

    let body: LoginResponse = resp.json().await?;

    // Guardar refresh token en Keychain si lo recibimos
    if let Some(rt) = refresh_token {
        save_refresh_token(&email, &rt)?;
    }

    // Obtener datos del usuario
    let me_resp = client
        .get(format!("{engine_url}/auth/me"))
        .header("Authorization", format!("Bearer {}", body.access_token))
        .send()
        .await?;

    let me: UserProfile = me_resp.json().await?;

    // Guardar token en AppState (RAM)
    {
        let mut s = state.0.lock().unwrap();
        s.access_token = Some(body.access_token.clone());
        s.current_email = Some(email.clone());
    }

    Ok(LoginResult {
        access_token: body.access_token,
        org_id: me.org_id,
        user_id: me.user_id,
        email: me.email,
        role: me.role,
    })
}

#[tauri::command]
pub async fn auth_logout(state: State<'_, AppState>) -> Result<(), String> {
    _auth_logout(state).await.map_err(|e| e.to_string())
}

async fn _auth_logout(state: State<'_, AppState>) -> AppResult<()> {
    let (engine_url, client, email, token) = {
        let s = state.0.lock().unwrap();
        (
            s.engine_url.clone(),
            s.http_client.clone(),
            s.current_email.clone(),
            s.access_token.clone(),
        )
    };

    // Limpiar refresh token del Keychain
    if let Some(ref em) = email {
        if let Some(rt) = load_refresh_token(em)? {
            let _ = client
                .post(format!("{engine_url}/auth/logout"))
                .header("Cookie", format!("ovd_refresh_token={rt}"))
                .header("Authorization", format!("Bearer {}", token.unwrap_or_default()))
                .send()
                .await;
            delete_refresh_token(em)?;
        }
    }

    let mut s = state.0.lock().unwrap();
    s.access_token = None;
    s.current_email = None;
    Ok(())
}

#[tauri::command]
pub async fn auth_is_authenticated(state: State<'_, AppState>) -> Result<bool, String> {
    Ok(state.0.lock().unwrap().access_token.is_some())
}

#[tauri::command]
pub async fn auth_get_current_user(state: State<'_, AppState>) -> Result<UserProfile, String> {
    _auth_get_current_user(state).await.map_err(|e| e.to_string())
}

async fn _auth_get_current_user(state: State<'_, AppState>) -> AppResult<UserProfile> {
    let (engine_url, client, token) = {
        let s = state.0.lock().unwrap();
        let token = s.access_token.clone().ok_or(AppError::Unauthorized)?;
        (s.engine_url.clone(), s.http_client.clone(), token)
    };

    let resp = client
        .get(format!("{engine_url}/auth/me"))
        .header("Authorization", format!("Bearer {token}"))
        .send()
        .await?;

    if resp.status() == 401 {
        return Err(AppError::TokenExpired);
    }

    Ok(resp.json().await?)
}

#[tauri::command]
pub async fn auth_refresh_token(state: State<'_, AppState>) -> Result<String, String> {
    _auth_refresh_token(state).await.map_err(|e| e.to_string())
}

async fn _auth_refresh_token(state: State<'_, AppState>) -> AppResult<String> {
    let (engine_url, client, email) = {
        let s = state.0.lock().unwrap();
        let email = s.current_email.clone().ok_or(AppError::Unauthorized)?;
        (s.engine_url.clone(), s.http_client.clone(), email)
    };

    let refresh_token = load_refresh_token(&email)?.ok_or(AppError::TokenExpired)?;

    let resp = client
        .post(format!("{engine_url}/auth/refresh"))
        .header("Cookie", format!("ovd_refresh_token={refresh_token}"))
        .send()
        .await?;

    if !resp.status().is_success() {
        return Err(AppError::TokenExpired);
    }

    let body: LoginResponse = resp.json().await?;

    // Actualizar AppState con nuevo token
    {
        let mut s = state.0.lock().unwrap();
        s.access_token = Some(body.access_token.clone());
    }

    Ok(body.access_token)
}
