## Convenciones OVD — Rust Backend (S58-pre)

### Infraestructura obligatoria — ORDEN DE ESCRITURA

1. **`Cargo.toml`** — dependencias del workspace ← PRIMERO
2. **`src/lib.rs`** o **`src/main.rs`** — entry point ← SEGUNDO
3. **Módulos de tipos y structs** — antes de los que los usan ← TERCERO
4. **Tests inline** `#[cfg(test)]` en cada módulo ← OBLIGATORIO

**CHECKLIST:**
- [ ] `Cargo.toml` con todas las crates usadas
- [ ] `src/lib.rs` exporta los módulos públicos
- [ ] Cada módulo tiene su bloque `#[cfg(test)]`
- [ ] Sin `unwrap()` en código de producción — usa `?` y manejo de errores explícito

### Estructura válida

```
proyecto/
├── Cargo.toml
├── src/
│   ├── main.rs
│   ├── lib.rs
│   ├── models/
│   │   └── mod.rs
│   ├── routes/
│   │   └── mod.rs
│   └── services/
│       └── mod.rs
└── tests/
    └── integration_test.rs
```

### Manejo de errores — anyhow / thiserror

```rust
// Errores de dominio con thiserror:
use thiserror::Error;

#[derive(Error, Debug)]
pub enum AppError {
    #[error("Not found: {0}")]
    NotFound(String),
    #[error("Validation error: {0}")]
    Validation(String),
    #[error(transparent)]
    Database(#[from] sqlx::Error),
}

// En handlers (axum):
impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, message) = match &self {
            AppError::NotFound(_) => (StatusCode::NOT_FOUND, self.to_string()),
            AppError::Validation(_) => (StatusCode::UNPROCESSABLE_ENTITY, self.to_string()),
            AppError::Database(_) => (StatusCode::INTERNAL_SERVER_ERROR, "Internal error".to_string()),
        };
        (status, Json(json!({ "error": message }))).into_response()
    }
}
```

### Tests inline — Formato obligatorio

```rust
// En cada módulo:
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_happy_path() {
        let result = calculate(70.0, 1.75);
        assert!((result - 22.86).abs() < 0.01);  // float comparison con epsilon
    }

    #[test]
    fn test_invalid_input() {
        let result = calculate(-1.0, 1.75);
        assert!(result.is_err());
    }
}

// Tests de integración en tests/:
#[tokio::test]
async fn test_endpoint_integration() {
    // ...
}
```

**Regla para floats en Rust:** NUNCA uses `==` para comparar floats. Usa epsilon:
```rust
assert!((resultado - esperado).abs() < 0.01);
```
