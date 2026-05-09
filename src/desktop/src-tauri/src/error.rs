use serde::Serialize;

#[derive(Debug, thiserror::Error, Serialize)]
#[serde(tag = "kind", content = "message")]
pub enum AppError {
    #[error("error de red: {0}")]
    Network(String),
    #[error("no autenticado")]
    Unauthorized,
    #[error("token expirado")]
    TokenExpired,
    #[error("keyring: {0}")]
    Keyring(String),
    #[error("io: {0}")]
    Io(String),
    #[error("timeout: {0}")]
    Timeout(String),
    #[error("{0}")]
    InvalidOperation(String),
}

pub type AppResult<T> = Result<T, AppError>;

impl From<reqwest::Error> for AppError {
    fn from(e: reqwest::Error) -> Self {
        if e.status().map(|s| s.as_u16()) == Some(401) {
            AppError::TokenExpired
        } else {
            AppError::Network(e.to_string())
        }
    }
}

impl From<std::io::Error> for AppError {
    fn from(e: std::io::Error) -> Self {
        AppError::Io(e.to_string())
    }
}

impl From<keyring::Error> for AppError {
    fn from(e: keyring::Error) -> Self {
        AppError::Keyring(e.to_string())
    }
}

impl From<zip::result::ZipError> for AppError {
    fn from(e: zip::result::ZipError) -> Self {
        AppError::InvalidOperation(format!("zip: {e}"))
    }
}

// Tauri requiere que los errores de commands sean serializable con Display
impl From<AppError> for String {
    fn from(e: AppError) -> Self {
        e.to_string()
    }
}
