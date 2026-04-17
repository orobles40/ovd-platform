use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct Stack {
    #[serde(default)]
    pub language: Option<String>,
    #[serde(default)]
    pub framework: Option<String>,
    #[serde(default)]
    pub db_engine: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Workspace {
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub active: bool,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub directory: String,
    #[serde(default)]
    pub stack: Stack,
}

// ---------------------------------------------------------------------------
// Tests — Block E
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    // ── Stack deserialization ─────────────────────────────────────────────────

    #[test]
    fn stack_todos_los_campos_presentes() {
        let json = r#"{"language":"Python","framework":"FastAPI","db_engine":"PostgreSQL"}"#;
        let s: Stack = serde_json::from_str(json).unwrap();
        assert_eq!(s.language.as_deref(), Some("Python"));
        assert_eq!(s.framework.as_deref(), Some("FastAPI"));
        assert_eq!(s.db_engine.as_deref(), Some("PostgreSQL"));
    }

    #[test]
    fn stack_campos_faltantes_son_none() {
        let json = r#"{}"#;
        let s: Stack = serde_json::from_str(json).unwrap();
        assert!(s.language.is_none());
        assert!(s.framework.is_none());
        assert!(s.db_engine.is_none());
    }

    #[test]
    fn stack_algunos_campos_presentes() {
        let json = r#"{"language":"Rust"}"#;
        let s: Stack = serde_json::from_str(json).unwrap();
        assert_eq!(s.language.as_deref(), Some("Rust"));
        assert!(s.framework.is_none());
        assert!(s.db_engine.is_none());
    }

    #[test]
    fn stack_campos_null_son_none() {
        let json = r#"{"language":null,"framework":null,"db_engine":null}"#;
        let s: Stack = serde_json::from_str(json).unwrap();
        assert!(s.language.is_none());
        assert!(s.framework.is_none());
        assert!(s.db_engine.is_none());
    }

    #[test]
    fn stack_default_todos_none() {
        let s = Stack::default();
        assert!(s.language.is_none());
        assert!(s.framework.is_none());
        assert!(s.db_engine.is_none());
    }

    // ── Workspace deserialization ─────────────────────────────────────────────

    #[test]
    fn workspace_minimo_valido() {
        let json = r#"{"id":"WS1","name":"Mi proyecto"}"#;
        let w: Workspace = serde_json::from_str(json).unwrap();
        assert_eq!(w.id, "WS1");
        assert_eq!(w.name, "Mi proyecto");
        assert!(!w.active);
        assert!(w.description.is_none());
        assert_eq!(w.directory, "");
        assert!(w.stack.language.is_none());
    }

    #[test]
    fn workspace_completo() {
        let json = r#"{
            "id": "WS2",
            "name": "HHMM",
            "active": true,
            "description": "Honorarios Médicos",
            "directory": "/opt/hhmm",
            "stack": {"language":"Java","framework":"Spring","db_engine":"Oracle"}
        }"#;
        let w: Workspace = serde_json::from_str(json).unwrap();
        assert!(w.active);
        assert_eq!(w.description.as_deref(), Some("Honorarios Médicos"));
        assert_eq!(w.stack.language.as_deref(), Some("Java"));
        assert_eq!(w.stack.db_engine.as_deref(), Some("Oracle"));
    }

    #[test]
    fn workspace_stack_vacio_no_falla() {
        let json = r#"{"id":"WS3","name":"Test","stack":{}}"#;
        let w: Workspace = serde_json::from_str(json).unwrap();
        assert!(w.stack.language.is_none());
    }

    #[test]
    fn workspace_sin_stack_usa_default() {
        let json = r#"{"id":"WS4","name":"NoStack"}"#;
        let w: Workspace = serde_json::from_str(json).unwrap();
        assert!(w.stack.language.is_none());
        assert!(w.stack.framework.is_none());
    }

    #[test]
    fn workspace_lista_deserializa_ok() {
        let json = r#"[
            {"id":"A","name":"Alpha"},
            {"id":"B","name":"Beta","active":true,"stack":{"language":"TypeScript"}}
        ]"#;
        let ws: Vec<Workspace> = serde_json::from_str(json).unwrap();
        assert_eq!(ws.len(), 2);
        assert_eq!(ws[1].stack.language.as_deref(), Some("TypeScript"));
    }
}
