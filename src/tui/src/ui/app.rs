// OVD Platform — Estado global de la aplicación TUI (S12 + S13 + S14)
//
// AppState coordina entre pantallas y mantiene el contexto activo.

use tokio::sync::mpsc;

use crate::api::OvdClient;
use crate::config::{AppConfig, ActiveSession, clear_session, clear_tokens, load_tokens, save_session, save_tokens};
use crate::models::auth::StoredTokens;
use crate::models::quota::QuotaInfo;
use crate::models::session::{CycleRecord, DeliveryReport, StartSessionRequest, SseEvent};
use crate::models::workspace::Workspace;
use anyhow::Result;

/// Pantalla activa en el TUI
#[derive(Debug, Clone, PartialEq)]
pub enum Screen {
    Onboarding,     // S14.C — wizard primera ejecución
    Login,
    WorkspaceSelect,
    Dashboard,
    SessionForm,    // S13.A — formulario Feature Request
    SessionStream,  // S13.B — streaming SSE del ciclo OVD
    ApprovalPanel,  // S13.C — revisión SDD + decisión
    Delivery,       // S16T.D — entrega de artefactos post-ciclo
    History,        // S14.A — historial de ciclos
    Quota,          // S14.B — quota y uso del período
}

/// Estado global compartido entre todos los componentes de UI
pub struct AppState {
    pub screen: Screen,
    pub config: AppConfig,
    pub tokens: StoredTokens,
    pub client: Option<OvdClient>,
    pub workspaces: Vec<Workspace>,
    pub selected_workspace: Option<Workspace>,
    pub error_message: Option<String>,
    pub status_message: Option<String>,
    pub should_quit: bool,

    // S13 — sesión activa
    pub thread_id: Option<String>,
    pub event_rx: Option<mpsc::UnboundedReceiver<SseEvent>>,

    // S14 — historial y quota
    pub cycles: Vec<CycleRecord>,
    pub quota: Option<QuotaInfo>,
    pub quota_loading: bool,
}

impl AppState {
    /// Inicializa el estado leyendo config y tokens locales.
    /// Si no hay config (org_id vacío) → Onboarding.
    /// Si hay tokens válidos → WorkspaceSelect.
    /// Si no → Login.
    pub fn init() -> Result<Self> {
        let config = AppConfig::load()?;
        let tokens = load_tokens()?;

        // AUTH-01: si hay refresh_token, intentar auto-refresh al inicio aunque el
        // access_token esté expirado — maybe_refresh() se ejecuta antes de cargar workspaces.
        let has_session = !tokens.is_empty()
            && (!tokens.is_expired() || !tokens.refresh_token.is_empty());

        let screen = if config.active().org_id.is_empty() {
            Screen::Onboarding
        } else if has_session {
            Screen::WorkspaceSelect
        } else {
            Screen::Login
        };

        let client = if !tokens.is_empty() && !tokens.access_token.is_empty() && !config.active().org_id.is_empty() {
            let profile = config.active();
            OvdClient::new(&profile.api_url, &profile.org_id, &tokens.access_token).ok()
        } else {
            None
        };

        Ok(Self {
            screen,
            config,
            tokens,
            client,
            workspaces: Vec::new(),
            selected_workspace: None,
            error_message: None,
            status_message: None,
            should_quit: false,
            thread_id: None,
            event_rx: None,
            cycles: Vec::new(),
            quota: None,
            quota_loading: false,
        })
    }

    /// Termina el onboarding guardando la configuración inicial.
    pub fn finish_onboarding(&mut self, api_url: String, org_id: String) -> Result<()> {
        self.config = AppConfig::init_default(&api_url, &org_id)?;
        self.screen = Screen::Login;
        Ok(())
    }

    /// Ejecuta login: llama API, guarda tokens, crea cliente.
    pub async fn do_login(&mut self, email: &str, password: &str) -> Result<()> {
        let profile = self.config.active();
        let tokens = OvdClient::login(&profile.api_url, email, password).await?;
        save_tokens(&tokens)?;

        self.client = Some(OvdClient::new(
            &profile.api_url,
            &profile.org_id,
            &tokens.access_token,
        )?);
        self.tokens = tokens;
        self.screen = Screen::WorkspaceSelect;
        self.error_message = None;
        Ok(())
    }

    /// Refresca el access token si está próximo a expirar.
    pub async fn maybe_refresh(&mut self) -> Result<()> {
        if self.tokens.is_expired() && !self.tokens.refresh_token.is_empty() {
            let profile = self.config.active();
            let new_tokens =
                OvdClient::refresh(&profile.api_url, &self.tokens.refresh_token).await?;
            save_tokens(&new_tokens)?;
            self.client = Some(OvdClient::new(
                &profile.api_url,
                &profile.org_id,
                &new_tokens.access_token,
            )?);
            self.tokens = new_tokens;
        }
        Ok(())
    }

    /// Cierra sesión: revoca token en API y limpia archivos locales.
    pub async fn do_logout(&mut self) -> Result<()> {
        if let Some(client) = &self.client {
            let _ = client.logout(&self.tokens.refresh_token).await;
        }
        clear_tokens()?;
        self.tokens = StoredTokens::default();
        self.client = None;
        self.thread_id = None;
        self.event_rx = None;
        self.screen = Screen::Login;
        Ok(())
    }

    /// Carga la lista de workspaces desde la API.
    pub async fn load_workspaces(&mut self) -> Result<()> {
        if let Some(client) = &self.client {
            self.workspaces = client.list_workspaces().await?;
        }
        Ok(())
    }

    /// Selecciona un workspace y persiste en config.
    pub fn select_workspace(&mut self, workspace: Workspace) -> Result<()> {
        self.config.set_workspace(&workspace.id, &workspace.name);
        self.config.save()?;
        self.selected_workspace = Some(workspace);
        self.screen = Screen::Dashboard;
        Ok(())
    }

    /// Inicia un ciclo OVD y abre el canal SSE para recibir eventos.
    pub async fn start_session(
        &mut self,
        feature_request: String,
        auto_approve: bool,
    ) -> Result<String> {
        let ws = self
            .selected_workspace
            .as_ref()
            .ok_or_else(|| anyhow::anyhow!("No hay workspace seleccionado"))?;
        let client = self
            .client
            .as_ref()
            .ok_or_else(|| anyhow::anyhow!("Sin cliente HTTP — vuelve a hacer login"))?
            .clone();

        // SEC-01: agregar entropía al session_id para evitar enumeración.
        // RandomState::new() usa seed aleatorio del OS por proceso (no predecible).
        let rnd = {
            use std::collections::hash_map::RandomState;
            use std::hash::{BuildHasher, Hasher};
            let mut h = RandomState::new().build_hasher();
            format!("{:016x}", {
                use std::hash::Hash;
                std::time::SystemTime::now().hash(&mut h);
                h.finish()
            })
        };
        let session_id = format!(
            "tui-{}-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_millis(),
            &rnd[..8],
        );

        // Serializar stack del workspace como JSON para el ContextResolver del engine
        let project_context = serde_json::json!({
            "language": ws.stack.language,
            "framework": ws.stack.framework,
            "db_engine": ws.stack.db_engine,
        })
        .to_string();

        let req = StartSessionRequest {
            session_id,
            org_id: self.config.active().org_id.clone(),
            project_id: ws.id.clone(),
            directory: ws.directory.clone(),
            feature_request,
            language: "es".to_string(),
            auto_approve,
            project_context,
        };

        let resp = client.start_session(&req).await?;
        let thread_id = resp.thread_id.clone();

        let (tx, rx) = mpsc::unbounded_channel();
        self.event_rx = Some(rx);
        self.thread_id = Some(thread_id.clone());

        // UX-02: persistir sesión activa para recuperarla si el TUI se cierra
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        let _ = save_session(&ActiveSession {
            thread_id: thread_id.clone(),
            feature_request: req.feature_request.clone(),
            status: "streaming".to_string(),
            started_at: now,
        });

        let tid = thread_id.clone();
        tokio::spawn(async move {
            if let Err(e) = client.stream_session(&tid, tx).await {
                tracing::warn!("stream_session terminó con error: {}", e);
            }
        });

        self.screen = Screen::SessionStream;
        Ok(thread_id)
    }

    /// Carga los entregables del ciclo desde el engine (S16T.C).
    pub async fn load_delivery(&self) -> Result<DeliveryReport> {
        let tid = self
            .thread_id
            .as_deref()
            .ok_or_else(|| anyhow::anyhow!("Sin thread activo"))?;
        let client = self
            .client
            .as_ref()
            .ok_or_else(|| anyhow::anyhow!("Sin cliente HTTP"))?;
        client.get_delivery(tid).await
    }

    /// Obtiene el SDD completo del engine para la revisión iterativa.
    pub async fn load_sdd_state(&self) -> Result<crate::models::session::SessionState> {
        let tid = self
            .thread_id
            .as_deref()
            .ok_or_else(|| anyhow::anyhow!("Sin thread activo"))?;
        let client = self
            .client
            .as_ref()
            .ok_or_else(|| anyhow::anyhow!("Sin cliente HTTP"))?;
        client.get_session_state(tid).await
    }

    /// Relanza el stream SSE para el thread activo (llamar tras enviar aprobación).
    pub fn resume_stream(&mut self) {
        let (Some(thread_id), Some(client)) = (self.thread_id.clone(), self.client.clone()) else {
            return;
        };
        let (tx, rx) = mpsc::unbounded_channel();
        self.event_rx = Some(rx);
        tokio::spawn(async move {
            if let Err(e) = client.stream_session(&thread_id, tx).await {
                tracing::warn!("resume stream_session terminó con error: {}", e);
            }
        });
    }

    /// Carga el historial de ciclos del workspace activo.
    pub async fn load_history(&mut self) -> Result<()> {
        let project_id = self
            .selected_workspace
            .as_ref()
            .map(|w| w.id.clone())
            .unwrap_or_default();
        if let Some(client) = &self.client {
            self.cycles = client.list_cycles(&project_id).await?;
        }
        Ok(())
    }

    /// Carga la información de quota de la organización.
    pub async fn load_quota(&mut self) -> Result<()> {
        if let Some(client) = &self.client {
            self.quota = Some(client.get_quota().await?);
        }
        Ok(())
    }

    /// UX-02: limpia la sesión persistida cuando el ciclo finaliza o se rechaza.
    pub fn finish_session(&mut self) {
        let _ = clear_session();
        self.thread_id = None;
        self.event_rx = None;
    }

    pub fn set_error(&mut self, msg: impl Into<String>) {
        self.error_message = Some(msg.into());
    }

    pub fn clear_error(&mut self) {
        self.error_message = None;
    }
}
