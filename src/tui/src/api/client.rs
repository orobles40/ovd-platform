// OVD Platform — Cliente HTTP (S12.B / S13.B)
//
// Cubre todos los endpoints que necesita el TUI:
//   POST /auth/login            — autenticación
//   POST /auth/refresh          — rotar token
//   POST /auth/logout           — revocar sesión
//   GET  /api/v1/orgs/{id}/projects  — listar workspaces
//   POST /session               — crear ciclo OVD
//   GET  /session/{id}/stream   — SSE streaming de eventos
//   POST /session/{id}/approve  — aprobar/rechazar SDD

use anyhow::{bail, Context, Result};
use eventsource_stream::Eventsource;
use futures_util::StreamExt;
use reqwest::Client;
use serde_json::Value;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::sync::mpsc;

use crate::models::auth::{LoginResponse, StoredTokens};
use crate::models::quota::QuotaInfo;
use crate::models::session::{
    ApproveRequest, CycleRecord, DeliveryReport, SessionState, StartSessionRequest,
    StartSessionResponse, SseEvent,
};
use crate::models::workspace::Workspace;

/// Cliente principal del TUI. Un solo cliente reutilizado durante la sesión.
#[derive(Clone)]
pub struct OvdClient {
    pub api_url: String,
    pub org_id: String,
    http: Client,
    access_token: String,
}

impl OvdClient {
    pub fn new(api_url: &str, org_id: &str, access_token: &str) -> Result<Self> {
        let http = Client::builder()
            .timeout(Duration::from_secs(30))
            .build()
            .context("No se pudo construir el cliente HTTP")?;
        Ok(Self {
            api_url: api_url.trim_end_matches('/').to_string(),
            org_id: org_id.to_string(),
            http,
            access_token: access_token.to_string(),
        })
    }

    fn auth_header(&self) -> String {
        format!("Bearer {}", self.access_token)
    }

    // ── Auth ────────────────────────────────────────────────────────────────

    /// POST /auth/login → access_token + refresh_token
    pub async fn login(api_url: &str, email: &str, password: &str) -> Result<StoredTokens> {
        let http = Client::builder()
            .timeout(Duration::from_secs(15))
            .build()?;

        let url = format!("{}/auth/login", api_url.trim_end_matches('/'));
        let body = serde_json::json!({ "email": email, "password": password });

        let resp = http
            .post(&url)
            .json(&body)
            .send()
            .await
            .context("No se pudo conectar al servidor OVD")?;

        if !resp.status().is_success() {
            let status = resp.status();
            let text = resp.text().await.unwrap_or_default();
            bail!("Login fallido ({}): {}", status, text);
        }

        let login: LoginResponse = resp.json().await.context("Respuesta de login inválida")?;

        let expires_at = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs()
            + login.expires_in;

        Ok(StoredTokens {
            access_token: login.access_token,
            refresh_token: login.refresh_token,
            expires_at,
        })
    }

    /// POST /auth/refresh → nuevos tokens
    pub async fn refresh(api_url: &str, refresh_token: &str) -> Result<StoredTokens> {
        let http = Client::builder()
            .timeout(Duration::from_secs(15))
            .build()?;

        let url = format!("{}/auth/refresh", api_url.trim_end_matches('/'));
        let body = serde_json::json!({ "refresh_token": refresh_token });

        let resp = http
            .post(&url)
            .json(&body)
            .send()
            .await
            .context("Error al refrescar token")?;

        if !resp.status().is_success() {
            bail!("Refresh token inválido o expirado — por favor vuelve a hacer login");
        }

        let login: LoginResponse = resp.json().await?;
        let expires_at = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs()
            + login.expires_in;

        Ok(StoredTokens {
            access_token: login.access_token,
            refresh_token: login.refresh_token,
            expires_at,
        })
    }

    /// POST /auth/logout — revoca el refresh token
    pub async fn logout(&self, refresh_token: &str) -> Result<()> {
        let url = format!("{}/auth/logout", self.api_url);
        let body = serde_json::json!({ "refresh_token": refresh_token });
        self.http
            .post(&url)
            .header("Authorization", self.auth_header())
            .json(&body)
            .send()
            .await
            .context("Error al cerrar sesión")?;
        Ok(())
    }

    // ── Workspaces ──────────────────────────────────────────────────────────

    /// GET /api/v1/orgs/{org_id}/projects → lista de workspaces activos
    pub async fn list_workspaces(&self) -> Result<Vec<Workspace>> {
        let url = format!("{}/api/v1/orgs/{}/projects", self.api_url, self.org_id);
        let resp = self
            .http
            .get(&url)
            .header("Authorization", self.auth_header())
            .send()
            .await
            .context("Error al obtener workspaces")?;

        if !resp.status().is_success() {
            bail!("No se pudieron obtener los workspaces ({})", resp.status());
        }

        let data: Value = resp.json().await?;
        let items = data
            .as_array()
            .or_else(|| data.get("projects").and_then(|v| v.as_array()))
            .cloned()
            .unwrap_or_default();

        let workspaces: Vec<Workspace> = items
            .iter()
            .filter_map(|v| serde_json::from_value(v.clone()).ok())
            .filter(|w: &Workspace| w.active)
            .collect();

        Ok(workspaces)
    }

    // ── Historial y Quota (S14) ─────────────────────────────────────────────

    /// GET /api/v1/orgs/{org_id}/cycles?project_id={id} → historial de ciclos
    pub async fn list_cycles(&self, project_id: &str) -> Result<Vec<CycleRecord>> {
        let url = format!(
            "{}/api/v1/orgs/{}/cycles?project_id={}",
            self.api_url, self.org_id, project_id
        );
        let resp = self
            .http
            .get(&url)
            .header("Authorization", self.auth_header())
            .send()
            .await
            .context("Error al obtener historial de ciclos")?;

        if !resp.status().is_success() {
            bail!("No se pudo obtener el historial ({})", resp.status());
        }

        let data: Value = resp.json().await?;
        // El engine retorna { total, limit, offset, items: [...] }
        let items = data
            .get("items")
            .and_then(|v| v.as_array())
            .or_else(|| data.as_array())
            .or_else(|| data.get("cycles").and_then(|v| v.as_array()))
            .cloned()
            .unwrap_or_default();

        Ok(items
            .iter()
            .filter_map(|v| serde_json::from_value(v.clone()).ok())
            .collect())
    }

    /// GET /api/v1/orgs/{org_id}/stats → mapea a QuotaInfo para el dashboard
    pub async fn get_quota(&self) -> Result<QuotaInfo> {
        let url = format!("{}/api/v1/orgs/{}/stats", self.api_url, self.org_id);
        let resp = self
            .http
            .get(&url)
            .header("Authorization", self.auth_header())
            .send()
            .await
            .context("Error al obtener estadísticas de uso")?;

        if !resp.status().is_success() {
            bail!("No se pudieron obtener las estadísticas ({})", resp.status());
        }

        let data: Value = resp.json().await?;
        // Mapear stats del engine → QuotaInfo del TUI
        let cycles_used = data.get("total_cycles").and_then(|v| v.as_u64()).unwrap_or(0) as u32;
        let tokens_used = data.get("total_tokens").and_then(|v| v.as_u64()).unwrap_or(0);
        let period_days = data.get("period_days").and_then(|v| v.as_u64()).unwrap_or(30);

        // Calcular fechas del período desde hoy hacia atrás
        let now_secs = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        let start_secs = now_secs.saturating_sub(period_days * 86400);
        let fmt_date = |secs: u64| -> String {
            // Formato YYYY-MM-DD simple sin dependencias de fecha
            let days_since_epoch = secs / 86400;
            let y = 1970 + days_since_epoch / 365;
            let m = (days_since_epoch % 365) / 30 + 1;
            let d = (days_since_epoch % 30) + 1;
            format!("{:04}-{:02}-{:02}", y, m.min(12), d.min(31))
        };

        Ok(QuotaInfo {
            cycles_used,
            cycles_limit: 50,      // límite por defecto — se leerá de ovd_org_quotas en el futuro
            tokens_used,
            tokens_limit: 500_000,
            period_start: fmt_date(start_secs),
            period_end: fmt_date(now_secs),
        })
    }

    // ── Sesiones / Ciclos OVD ──────────────────────────────────────────────

    /// POST /session → inicia un ciclo OVD
    pub async fn start_session(&self, req: &StartSessionRequest) -> Result<StartSessionResponse> {
        let url = format!("{}/session", self.api_url);
        let resp = self
            .http
            .post(&url)
            .header("Authorization", self.auth_header())
            .json(req)
            .send()
            .await
            .context("Error al iniciar sesión OVD")?;

        if !resp.status().is_success() {
            let status = resp.status();
            let text = resp.text().await.unwrap_or_default();
            bail!("Error al crear sesión ({}): {}", status, text);
        }

        resp.json().await.context("Respuesta de sesión inválida")
    }

    /// GET /session/{thread_id}/state → SDD completo para revisión iterativa
    pub async fn get_session_state(&self, thread_id: &str) -> Result<SessionState> {
        let url = format!("{}/session/{}/state", self.api_url, thread_id);
        let resp = self
            .http
            .get(&url)
            .header("Authorization", self.auth_header())
            .send()
            .await
            .context("Error al obtener estado del ciclo")?;

        if !resp.status().is_success() {
            bail!("No se pudo obtener el estado del ciclo ({})", resp.status());
        }

        resp.json().await.context("Respuesta de estado inválida")
    }

    /// GET /session/{thread_id}/delivery → entregables completos del ciclo
    pub async fn get_delivery(&self, thread_id: &str) -> Result<DeliveryReport> {
        let url = format!("{}/session/{}/delivery?org_id={}", self.api_url, thread_id, self.org_id);
        let resp = self
            .http
            .get(&url)
            .header("Authorization", self.auth_header())
            .send()
            .await
            .context("Error al obtener entrega del ciclo")?;

        if !resp.status().is_success() {
            bail!("No se pudo obtener la entrega ({})", resp.status());
        }

        resp.json().await.context("Respuesta de entrega inválida")
    }

    /// POST /session/{thread_id}/approve
    pub async fn approve_session(
        &self,
        thread_id: &str,
        approved: bool,
        comment: Option<String>,
        action: String,
    ) -> Result<()> {
        let url = format!("{}/session/{}/approve", self.api_url, thread_id);
        let body = ApproveRequest { approved, comment, action };
        let resp = self
            .http
            .post(&url)
            .header("Authorization", self.auth_header())
            .json(&body)
            .send()
            .await
            .context("Error al enviar decisión de aprobación")?;

        if !resp.status().is_success() {
            bail!("Error al aprobar/rechazar ({})", resp.status());
        }
        Ok(())
    }

    /// GET /session/{thread_id}/stream → devuelve la URL para SSE
    pub fn stream_url(&self, thread_id: &str) -> String {
        format!("{}/session/{}/stream", self.api_url, thread_id)
    }

    /// Parsea un evento SSE crudo (data: {...}) en SseEvent
    pub fn parse_sse_event(raw_data: &str) -> Option<SseEvent> {
        serde_json::from_str(raw_data).ok()
    }

    /// GET /session/{thread_id}/stream — consume SSE y envía eventos al canal.
    /// Termina cuando el servidor cierra la conexión o llega evento "done".
    /// Llamar con `tokio::spawn(client.stream_session(tid, tx))`.
    pub async fn stream_session(
        &self,
        thread_id: &str,
        tx: mpsc::UnboundedSender<SseEvent>,
    ) -> Result<()> {
        // Sin timeout global — el stream puede durar minutos
        let http = Client::builder().build()?;
        let url = self.stream_url(thread_id);
        let response = http
            .get(&url)
            .header("Authorization", self.auth_header())
            .send()
            .await
            .context("No se pudo conectar al stream SSE")?;

        if !response.status().is_success() {
            bail!("Stream SSE error ({})", response.status());
        }

        let mut stream = response.bytes_stream().eventsource();
        let mut received_done = false;

        while let Some(item) = stream.next().await {
            match item {
                Ok(ev) => {
                    // Ignorar pings y eventos vacíos
                    if ev.event == "ping" || ev.data.is_empty() || ev.data == "\"\"" {
                        continue;
                    }
                    if let Some(sse) = Self::parse_sse_event(&ev.data) {
                        let is_done = sse.event_type == "done";
                        if is_done {
                            received_done = true;
                        }
                        // Si el canal ya no tiene receptores (pantalla cerrada), salir
                        if tx.send(sse).is_err() {
                            break;
                        }
                        if is_done {
                            break;
                        }
                    }
                }
                Err(e) => {
                    tracing::warn!("SSE stream error: {}", e);
                    break;
                }
            }
        }

        // Si el stream se cerró sin "done", el engine interrumpió (LangGraph interrupt())
        // Emitir evento sintético para que la UI muestre el panel de aprobación
        if !received_done {
            let closed_event = SseEvent {
                event_type: "stream_closed".to_string(),
                data: serde_json::Value::Object(serde_json::Map::new()),
            };
            let _ = tx.send(closed_event); // ignorar error si canal ya cerrado
        }

        Ok(())
    }
}
