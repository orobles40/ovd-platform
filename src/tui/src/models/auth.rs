use serde::{Deserialize, Serialize};

/// Respuesta del endpoint POST /auth/login
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LoginResponse {
    pub access_token: String,
    pub refresh_token: String,
    pub expires_in: u64,
}

/// Tokens guardados localmente en ~/.ovd/tokens.toml
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct StoredTokens {
    #[serde(default)]
    pub access_token: String,
    #[serde(default)]
    pub refresh_token: String,
    /// Unix timestamp de expiración del access_token
    #[serde(default)]
    pub expires_at: u64,
}

impl StoredTokens {
    pub fn is_empty(&self) -> bool {
        self.access_token.is_empty()
    }

    pub fn is_expired(&self) -> bool {
        if self.expires_at == 0 {
            return false;
        }
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        now >= self.expires_at
    }
}
