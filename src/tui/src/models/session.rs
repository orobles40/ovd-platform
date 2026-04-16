use serde::{Deserialize, Serialize};
use serde_json::Value;

// ─── Eventos SSE ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SseEvent {
    #[serde(rename = "type")]
    pub event_type: String,
    #[serde(default)]
    pub data: Value,
}

// ─── Inicio de sesión / ciclo ─────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StartSessionRequest {
    pub session_id: String,
    pub org_id: String,
    pub project_id: String,
    #[serde(default)]
    pub directory: String,
    pub feature_request: String,
    pub language: String,
    pub auto_approve: bool,
    #[serde(default)]
    pub project_context: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StartSessionResponse {
    pub thread_id: String,
}

// ─── Aprobación ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApproveRequest {
    pub approved: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub comment: Option<String>,
    pub action: String,
}

// ─── Estado de sesión / SDD ───────────────────────────────────────────────────

/// Contenido estructurado del SDD, tal como lo devuelve el engine.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct SddContent {
    #[serde(default)]
    pub summary: String,
    #[serde(default)]
    pub requirements: Vec<Value>,
    #[serde(default)]
    pub tasks: Vec<Value>,
    #[serde(default)]
    pub constraints: Vec<Value>,
    #[serde(default)]
    pub design: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionState {
    pub sdd: SddContent,
    #[serde(default)]
    pub revision_count: u32,
}

// ─── Historial de ciclos ──────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CycleRecord {
    pub feature_request: String,
    #[serde(default)]
    pub fr_type: Option<String>,
    #[serde(default)]
    pub qa_score: Option<f64>,
    #[serde(default)]
    pub created_at: Option<String>,
}

// ─── Entrega de artefactos ────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Artifact {
    pub path: String,
    #[serde(default)]
    pub size: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Deliverable {
    pub kind: String,
    #[serde(default)]
    pub agent: String,
    #[serde(default)]
    pub path: String,
    #[serde(default)]
    pub artifacts: Vec<Artifact>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeliveryScore {
    pub score: Option<Value>,
    pub passed: bool,
    #[serde(default)]
    pub severity: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeliveryQa {
    pub score: Option<Value>,
    pub passed: bool,
    pub sdd_compliance: bool,
    #[serde(default)]
    pub issues: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeliveryReport {
    pub status: String,
    #[serde(default)]
    pub directory: String,
    #[serde(default)]
    pub deliverables: Vec<Deliverable>,
    pub security: DeliveryScore,
    pub qa: DeliveryQa,
    #[serde(default)]
    pub tokens_in: u64,
    #[serde(default)]
    pub tokens_out: u64,
    #[serde(default)]
    pub elapsed_secs: f64,
}
