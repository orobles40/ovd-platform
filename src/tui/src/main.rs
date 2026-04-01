// OVD Platform — TUI Principal (S12 + S13 + S14)
// Copyright 2026 Omar Robles
//
// Binario `ovd` — herramienta de línea de comandos para equipos de desarrollo.
// Consume la API FastAPI de OVD Engine.
//
// Flujo completo:
//   Onboarding → Login → WorkspaceSelect → Dashboard
//   Dashboard: [n] nueva FR, [h] historial, [u] quota, [q] cambiar ws, [Shift+L] logout
//   SessionForm → SessionStream → ApprovalPanel → SessionStream (done) → Dashboard

mod api;
mod config;
mod models;
mod ui;

use anyhow::Result;
use crossterm::{
    event::{self, Event, KeyCode, KeyModifiers},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{backend::CrosstermBackend, Terminal};
use std::io;
use std::time::Duration;

use crate::config::load_session;

use ui::{
    app::{AppState, Screen},
    delivery::{DeliveryAction, DeliveryScreen},
    history::{HistoryAction, HistoryScreen},
    login::{LoginAction, LoginScreen},
    onboarding::{OnboardingAction, OnboardingWizard},
    quota::QuotaScreen,
    session::{
        ReviewAction, SddReviewScreen, SessionFormAction, SessionFormScreen,
        SessionStreamAction, SessionStreamScreen,
    },
    workspace::{WorkspaceAction, WorkspaceScreen},
};

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("ovd_tui=info".parse()?),
        )
        .with_target(false)
        .init();

    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    let result = run_app(&mut terminal).await;

    disable_raw_mode()?;
    execute!(terminal.backend_mut(), LeaveAlternateScreen)?;
    terminal.show_cursor()?;

    if let Err(e) = result {
        eprintln!("Error: {e}");
        std::process::exit(1);
    }
    Ok(())
}

async fn run_app(terminal: &mut Terminal<CrosstermBackend<io::Stdout>>) -> Result<()> {
    let mut state = AppState::init()?;
    let mut onboarding = OnboardingWizard::default();
    let mut login_screen = LoginScreen::default();
    let mut workspace_screen = WorkspaceScreen::default();
    let mut history_screen = HistoryScreen::default();
    let mut session_form = SessionFormScreen::default();
    let mut session_stream = SessionStreamScreen::default();
    let mut sdd_review = SddReviewScreen::default();
    let mut delivery_screen = DeliveryScreen::default();

    // Si hay tokens válidos, cargar workspaces de inmediato
    if state.screen == Screen::WorkspaceSelect {
        state.maybe_refresh().await.unwrap_or(());
        match state.load_workspaces().await {
            Ok(_) => workspace_screen.loading = false,
            Err(e) => {
                state.set_error(format!("Error cargando workspaces: {e}"));
                state.screen = Screen::Login;
            }
        }
    }

    // UX-02: detectar sesión pendiente del arranque anterior
    // Si el estado es Dashboard o WorkspaceSelect y hay una sesión guardada, avisar al usuario
    let pending_session = if matches!(state.screen, Screen::Dashboard | Screen::WorkspaceSelect) {
        load_session()
    } else {
        None
    };
    if let Some(ref ps) = pending_session {
        state.set_error(format!(
            "Sesión pendiente detectada: \"{}\" [{}] — ve al Dashboard y usa [r] para retomar",
            &ps.feature_request.chars().take(40).collect::<String>(),
            &ps.thread_id.chars().take(12).collect::<String>(),
        ));
        state.thread_id = Some(ps.thread_id.clone());
    }

    loop {
        if state.should_quit {
            break;
        }

        // Drenar canal SSE cuando estamos en pantallas de sesión
        if matches!(state.screen, Screen::SessionStream | Screen::ApprovalPanel) {
            if let Some(rx) = &mut state.event_rx {
                while let Ok(ev) = rx.try_recv() {
                    session_stream.process_event(&ev);
                }
            }
        }

        // ── Renderizado ──────────────────────────────────────────────────────
        let error = state.error_message.as_deref();
        match state.screen.clone() {
            Screen::Onboarding => {
                terminal.draw(|f| onboarding.render(f))?;
            }
            Screen::Login => {
                terminal.draw(|f| login_screen.render(f, error))?;
            }
            Screen::WorkspaceSelect => {
                let workspaces = state.workspaces.clone();
                let org_id = state.config.active().org_id.clone();
                terminal.draw(|f| workspace_screen.render(f, &workspaces, &org_id))?;
            }
            Screen::Dashboard => {
                let ws_name = state
                    .selected_workspace
                    .as_ref()
                    .map(|w| w.name.as_str())
                    .unwrap_or("—");
                let has_pending = state.thread_id.is_some();
                terminal.draw(|f| render_dashboard(f, ws_name, error, has_pending))?;
            }
            Screen::SessionForm => {
                let ws_name = state
                    .selected_workspace
                    .as_ref()
                    .map(|w| w.name.as_str())
                    .unwrap_or("—");
                terminal.draw(|f| session_form.render(f, ws_name, error))?;
            }
            Screen::SessionStream => {
                let thread_id = state.thread_id.as_deref().unwrap_or("—");
                terminal.draw(|f| session_stream.render(f, thread_id))?;
            }
            Screen::ApprovalPanel => {
                let thread_id = state.thread_id.as_deref().unwrap_or("—");
                terminal.draw(|f| sdd_review.render(f, thread_id))?;
            }
            Screen::Delivery => {
                terminal.draw(|f| {
                    let area = f.area();
                    delivery_screen.render(f, area);
                })?;
            }
            Screen::History => {
                let cycles = state.cycles.clone();
                let ws_name = state
                    .selected_workspace
                    .as_ref()
                    .map(|w| w.name.as_str())
                    .unwrap_or("—");
                terminal.draw(|f| history_screen.render(f, &cycles, ws_name))?;
            }
            Screen::Quota => {
                let org_id = state.config.active().org_id.clone();
                let quota = state.quota.as_ref();
                let loading = state.quota_loading;
                terminal.draw(|f| QuotaScreen::render(f, quota, &org_id, loading))?;
            }
        }

        if !event::poll(Duration::from_millis(50))? {
            continue;
        }

        let evt = event::read()?;

        // Ctrl+C global → salir
        if let Event::Key(key) = &evt {
            if key.modifiers.contains(KeyModifiers::CONTROL) && key.code == KeyCode::Char('c') {
                break;
            }
        }

        // ── Manejo de eventos por pantalla ───────────────────────────────────
        match state.screen.clone() {
            Screen::Onboarding => {
                if let Event::Key(key) = evt {
                    match onboarding.handle_key(key) {
                        OnboardingAction::Complete { api_url, org_id } => {
                            match state.finish_onboarding(api_url, org_id) {
                                Ok(_)  => login_screen = LoginScreen::default(),
                                Err(e) => onboarding.error = Some(format!("{e}")),
                            }
                        }
                        OnboardingAction::None => {}
                    }
                }
            }

            Screen::Login => {
                if let Event::Key(key) = evt {
                    match login_screen.handle_key(key) {
                        LoginAction::Quit => break,
                        LoginAction::Submit { email, password } => {
                            match state.do_login(&email, &password).await {
                                Ok(_) => {
                                    login_screen = LoginScreen::default();
                                    workspace_screen = WorkspaceScreen::default();
                                    match state.load_workspaces().await {
                                        Ok(_) => workspace_screen.loading = false,
                                        Err(e) => state.set_error(format!("{e}")),
                                    }
                                }
                                Err(e) => {
                                    login_screen.submitting = false;
                                    state.set_error(format!("{e}"));
                                }
                            }
                        }
                        LoginAction::None => {}
                    }
                }
            }

            Screen::WorkspaceSelect => {
                if let Event::Key(key) = evt {
                    let total = state.workspaces.len();
                    match workspace_screen.handle_key(key, total) {
                        WorkspaceAction::Select(idx) => {
                            if let Some(ws) = state.workspaces.get(idx).cloned() {
                                state.select_workspace(ws)?;
                            }
                        }
                        WorkspaceAction::Logout => {
                            state.do_logout().await.unwrap_or(());
                            login_screen = LoginScreen::default();
                        }
                        WorkspaceAction::Quit => break,
                        WorkspaceAction::None => {}
                    }
                }
            }

            Screen::Dashboard => {
                if let Event::Key(key) = evt {
                    match key.code {
                        KeyCode::Char('n') => {
                            state.clear_error();
                            session_form = SessionFormScreen::default();
                            state.screen = Screen::SessionForm;
                        }
                        KeyCode::Char('h') => {
                            state.clear_error();
                            history_screen = HistoryScreen::default();
                            match state.load_history().await {
                                Ok(_)  => history_screen.loading = false,
                                Err(e) => state.set_error(format!("{e}")),
                            }
                            state.screen = Screen::History;
                        }
                        KeyCode::Char('u') => {
                            state.clear_error();
                            state.quota_loading = true;
                            state.screen = Screen::Quota;
                            match state.load_quota().await {
                                Ok(_)  => state.quota_loading = false,
                                Err(e) => {
                                    state.quota_loading = false;
                                    state.set_error(format!("{e}"));
                                }
                            }
                        }
                        // UX-02: retomar sesión pendiente detectada al arranque
                        KeyCode::Char('r') if state.thread_id.is_some() => {
                            state.clear_error();
                            session_stream = SessionStreamScreen::default();
                            state.resume_stream();
                            state.screen = Screen::SessionStream;
                        }
                        // UX-02: descartar sesión pendiente
                        KeyCode::Char('x') if state.thread_id.is_some() => {
                            state.finish_session();
                            state.clear_error();
                        }
                        KeyCode::Char('q') | KeyCode::Esc => {
                            state.screen = Screen::WorkspaceSelect;
                        }
                        KeyCode::Char('L') => {
                            state.do_logout().await.unwrap_or(());
                            login_screen = LoginScreen::default();
                        }
                        _ => {}
                    }
                }
            }

            Screen::SessionForm => {
                if let Event::Key(key) = evt {
                    match session_form.handle_key(key) {
                        SessionFormAction::Back => {
                            state.clear_error();
                            state.screen = Screen::Dashboard;
                        }
                        SessionFormAction::Submit { text, auto_approve } => {
                            state.clear_error();
                            session_stream = SessionStreamScreen::default();
                            match state.start_session(text, auto_approve).await {
                                Ok(_) => {
                                    session_form = SessionFormScreen::default();
                                }
                                Err(e) => {
                                    state.set_error(format!("{e}"));
                                }
                            }
                        }
                        SessionFormAction::None => {}
                    }
                }
            }

            Screen::SessionStream => {
                if let Event::Key(key) = evt {
                    match session_stream.handle_key(key) {
                        SessionStreamAction::OpenApproval => {
                            // Cargar SDD real desde el engine
                            sdd_review = SddReviewScreen::default();
                            state.screen = Screen::ApprovalPanel;
                            match state.load_sdd_state().await {
                                Ok(s) => {
                                    sdd_review.sdd = s.sdd;
                                    sdd_review.revision_count = s.revision_count;
                                    sdd_review.loading = false;
                                }
                                Err(e) => {
                                    sdd_review.loading = false;
                                    state.set_error(format!("Error cargando SDD: {e}"));
                                }
                            }
                        }
                        SessionStreamAction::OpenDelivery => {
                            delivery_screen = DeliveryScreen::default();
                            delivery_screen.loading = true;
                            let _ = crate::config::clear_session(); // UX-02: ciclo completado
                            state.screen = Screen::Delivery;
                            match state.load_delivery().await {
                                Ok(report) => {
                                    delivery_screen.report = Some(report);
                                    delivery_screen.loading = false;
                                }
                                Err(e) => {
                                    delivery_screen.loading = false;
                                    state.set_error(format!("Error cargando entrega: {e}"));
                                }
                            }
                        }
                        SessionStreamAction::Back => {
                            state.event_rx = None;
                            state.screen = Screen::Dashboard;
                        }
                        SessionStreamAction::None => {}
                    }
                }
            }

            Screen::Delivery => {
                if let Event::Key(key) = evt {
                    match delivery_screen.handle_key(key) {
                        DeliveryAction::Back => {
                            state.screen = Screen::SessionStream;
                        }
                        DeliveryAction::OpenDirectory => {
                            if let Some(report) = &delivery_screen.report {
                                if !report.directory.is_empty() {
                                    let dir = report.directory.clone();
                                    tokio::spawn(async move {
                                        let _ = tokio::process::Command::new("open")
                                            .arg(&dir)
                                            .spawn();
                                    });
                                }
                            }
                        }
                        DeliveryAction::ExportReport => {
                            // S16T.F: abrir el informe .md con la app por defecto del OS
                            if let Some(report) = &delivery_screen.report {
                                let report_path = report.deliverables.iter()
                                    .find(|d| d.kind == "report" && !d.path.is_empty())
                                    .map(|d| format!("{}/{}", report.directory.trim_end_matches('/'), d.path));
                                if let Some(path) = report_path {
                                    tokio::spawn(async move {
                                        let _ = tokio::process::Command::new("open")
                                            .arg(&path)
                                            .spawn();
                                    });
                                }
                            }
                        }
                        DeliveryAction::NewSession => {
                            // BUG-03: volver al dashboard para iniciar un nuevo ciclo
                            state.thread_id = None;
                            state.event_rx = None;
                            state.screen = Screen::Dashboard;
                        }
                        DeliveryAction::None => {}
                    }
                }
            }

            Screen::ApprovalPanel => {
                if let Event::Key(key) = evt {
                    match sdd_review.handle_key(key) {
                        ReviewAction::Approve => {
                            send_approval(&state, "approve", None).await;
                            session_stream.has_pending_approval = false;
                            state.resume_stream();
                            state.screen = Screen::SessionStream;
                        }
                        ReviewAction::RequestRevision { comment } => {
                            send_approval(&state, "revise", Some(comment)).await;
                            session_stream.has_pending_approval = false;
                            // Resetear stream screen para la nueva ronda
                            session_stream = SessionStreamScreen::default();
                            state.resume_stream();
                            state.screen = Screen::SessionStream;
                        }
                        ReviewAction::Reject => {
                            send_approval(&state, "reject", Some("Rechazado por el arquitecto".to_string())).await;
                            session_stream.has_pending_approval = false;
                            session_stream.is_done = true;
                            state.finish_session(); // UX-02: limpiar sesión persistida
                            state.screen = Screen::SessionStream;
                        }
                        ReviewAction::ExportSdd => {
                            // S15T.I: exportar SDD a ~/ovd-exports/{thread_id}-sdd.md
                            let content = sdd_review.format_sdd();
                            let thread_id = state.thread_id.clone().unwrap_or_else(|| "unknown".to_string());
                            tokio::spawn(async move {
                                let export_dir = dirs::home_dir()
                                    .unwrap_or_else(|| std::path::PathBuf::from("."))
                                    .join("ovd-exports");
                                let _ = tokio::fs::create_dir_all(&export_dir).await;
                                let path = export_dir.join(format!("{}-sdd.md", &thread_id));
                                if tokio::fs::write(&path, content).await.is_ok() {
                                    let _ = tokio::process::Command::new("open")
                                        .arg(&path)
                                        .spawn();
                                }
                            });
                        }
                        ReviewAction::Back => {
                            state.screen = Screen::SessionStream;
                        }
                        ReviewAction::None => {}
                    }
                }
            }

            Screen::History => {
                if let Event::Key(key) = evt {
                    let total = state.cycles.len();
                    match history_screen.handle_key(key, total) {
                        HistoryAction::Back => {
                            state.clear_error();
                            state.screen = Screen::Dashboard;
                        }
                        HistoryAction::None => {}
                    }
                }
            }

            Screen::Quota => {
                if let Event::Key(key) = evt {
                    match QuotaScreen::handle_key(key) {
                        ui::quota::QuotaAction::Back => {
                            state.clear_error();
                            state.screen = Screen::Dashboard;
                        }
                        ui::quota::QuotaAction::None => {}
                    }
                }
            }
        }
    }

    Ok(())
}

/// Envía la decisión de aprobación al backend.
/// action: "approve" | "reject" | "revise"
async fn send_approval(state: &AppState, action: &str, comment: Option<String>) {
    if let (Some(tid), Some(client)) = (&state.thread_id, &state.client) {
        let approved = action == "approve";
        if let Err(e) = client.approve_session(tid, approved, comment, action.to_string()).await {
            tracing::warn!("Error al enviar aprobación: {}", e);
        }
    }
}

/// Renderiza el Dashboard (S13 + S14 opciones).
fn render_dashboard(frame: &mut ratatui::Frame, ws_name: &str, error: Option<&str>, has_pending_session: bool) {
    use ratatui::{
        layout::{Constraint, Layout},
        style::{Color, Modifier, Style},
        text::{Line, Span},
        widgets::{Block, Borders, Paragraph},
    };

    let area = frame.area();
    let chunks = Layout::vertical([
        Constraint::Length(3),
        Constraint::Fill(1),
        Constraint::Length(2),
    ])
    .split(area);

    // Header
    let header = Paragraph::new(Line::from(vec![
        Span::styled("  workspace activo: ", Style::default().fg(Color::DarkGray)),
        Span::styled(
            ws_name,
            Style::default()
                .fg(Color::Cyan)
                .add_modifier(Modifier::BOLD),
        ),
    ]))
    .block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Color::Cyan))
            .title(Span::styled(
                " OVD Dashboard ",
                Style::default()
                    .fg(Color::White)
                    .add_modifier(Modifier::BOLD),
            )),
    );
    frame.render_widget(header, chunks[0]);

    // Cuerpo
    let mut body_lines = vec![
        Line::from(""),
        Line::from(vec![
            Span::styled(
                "  [n]",
                Style::default()
                    .fg(Color::Green)
                    .add_modifier(Modifier::BOLD),
            ),
            Span::styled(
                "  Nueva solicitud (Feature Request / Mantenimiento)",
                Style::default().fg(Color::White),
            ),
        ]),
        Line::from(""),
        Line::from(vec![
            Span::styled("  [h]", Style::default().fg(Color::Cyan)),
            Span::styled("  Historial de ciclos", Style::default().fg(Color::White)),
        ]),
        Line::from(""),
        Line::from(vec![
            Span::styled("  [u]", Style::default().fg(Color::Cyan)),
            Span::styled("  Quota y uso del período", Style::default().fg(Color::White)),
        ]),
        Line::from(""),
    ];

    // UX-02: opciones de recuperación si hay sesión pendiente
    if has_pending_session {
        body_lines.push(Line::from(vec![
            Span::styled("  [r]", Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)),
            Span::styled("  Retomar sesión pendiente", Style::default().fg(Color::Yellow)),
        ]));
        body_lines.push(Line::from(vec![
            Span::styled("  [x]", Style::default().fg(Color::DarkGray)),
            Span::styled("  Descartar sesión pendiente", Style::default().fg(Color::DarkGray)),
        ]));
        body_lines.push(Line::from(""));
    }

    if let Some(err) = error {
        body_lines.push(Line::from(vec![
            Span::styled("  ⚠ ", Style::default().fg(Color::Yellow)),
            Span::styled(err, Style::default().fg(Color::Yellow)),
        ]));
    }

    let body = Paragraph::new(body_lines).block(
        Block::default()
            .borders(Borders::LEFT | Borders::RIGHT | Borders::BOTTOM)
            .border_style(Style::default().fg(Color::Cyan)),
    );
    frame.render_widget(body, chunks[1]);

    // Footer
    let footer = Paragraph::new(Line::from(vec![
        Span::styled("  [n]", Style::default().fg(Color::Cyan)),
        Span::styled(" nueva  ", Style::default().fg(Color::DarkGray)),
        Span::styled("[h]", Style::default().fg(Color::Cyan)),
        Span::styled(" historial  ", Style::default().fg(Color::DarkGray)),
        Span::styled("[u]", Style::default().fg(Color::Cyan)),
        Span::styled(" quota  ", Style::default().fg(Color::DarkGray)),
        Span::styled("[Shift+L]", Style::default().fg(Color::Cyan)),
        Span::styled(" logout  ", Style::default().fg(Color::DarkGray)),
        Span::styled("[q]", Style::default().fg(Color::Cyan)),
        Span::styled(" cambiar workspace", Style::default().fg(Color::DarkGray)),
    ]));
    frame.render_widget(footer, chunks[2]);
}
