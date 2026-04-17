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

// ---------------------------------------------------------------------------
// Tests — Block E
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    // ── LoginResponse deserialization ─────────────────────────────────────────

    #[test]
    fn login_response_deserializa_campos_requeridos() {
        let json = r#"{
            "access_token": "eyJ.abc.xyz",
            "refresh_token": "refresh-tok",
            "expires_in": 3600
        }"#;
        let r: LoginResponse = serde_json::from_str(json).unwrap();
        assert_eq!(r.access_token, "eyJ.abc.xyz");
        assert_eq!(r.refresh_token, "refresh-tok");
        assert_eq!(r.expires_in, 3600);
    }

    #[test]
    fn login_response_falla_sin_access_token() {
        let json = r#"{"refresh_token":"r","expires_in":3600}"#;
        assert!(serde_json::from_str::<LoginResponse>(json).is_err());
    }

    // ── StoredTokens — is_empty ───────────────────────────────────────────────

    #[test]
    fn stored_tokens_default_es_vacio() {
        let t = StoredTokens::default();
        assert!(t.is_empty());
    }

    #[test]
    fn stored_tokens_con_access_no_es_vacio() {
        let t = StoredTokens {
            access_token: "tok".into(),
            refresh_token: "ref".into(),
            expires_at: 9999999999,
        };
        assert!(!t.is_empty());
    }

    // ── StoredTokens — is_expired ─────────────────────────────────────────────

    #[test]
    fn expires_at_cero_nunca_expira() {
        let t = StoredTokens { expires_at: 0, ..Default::default() };
        assert!(!t.is_expired());
    }

    #[test]
    fn expires_at_en_pasado_esta_expirado() {
        // Unix epoch 1 = 1970-01-01 00:00:01 — siempre en el pasado
        let t = StoredTokens { access_token: "x".into(), expires_at: 1, ..Default::default() };
        assert!(t.is_expired());
    }

    #[test]
    fn expires_at_en_futuro_no_expira() {
        // año 2100 ≈ 4102444800
        let t = StoredTokens { access_token: "x".into(), expires_at: 4102444800, ..Default::default() };
        assert!(!t.is_expired());
    }

    // ── StoredTokens — TOML round-trip ───────────────────────────────────────

    #[test]
    fn stored_tokens_toml_roundtrip() {
        let original = StoredTokens {
            access_token: "acc".into(),
            refresh_token: "ref".into(),
            expires_at: 1_700_000_000,
        };
        let toml_str = toml::to_string_pretty(&original).unwrap();
        let recovered: StoredTokens = toml::from_str(&toml_str).unwrap();
        assert_eq!(recovered.access_token, original.access_token);
        assert_eq!(recovered.refresh_token, original.refresh_token);
        assert_eq!(recovered.expires_at, original.expires_at);
    }

    #[test]
    fn stored_tokens_toml_vacio_usa_defaults() {
        let toml_str = "";
        let t: StoredTokens = toml::from_str(toml_str).unwrap();
        assert!(t.is_empty());
        assert!(!t.is_expired());
    }
}
