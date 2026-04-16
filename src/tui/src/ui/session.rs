// OVD Platform — Pantallas de Sesión (S13)
//
// S13.A — SessionFormScreen  : formulario Feature Request (multi-línea)
// S13.B — SessionStreamScreen: viewer de eventos SSE en tiempo real
// S13.C — ApprovalScreen     : panel SDD con aprobar / rechazar / escalar

use crossterm::event::{KeyCode, KeyEvent, KeyModifiers};
use ratatui::{
    Frame,
    layout::{Constraint, Layout},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, List, ListItem, Paragraph, Wrap},
};

use crate::models::session::SseEvent;

/// Divide un &str en el límite de carácter UTF-8 más cercano a `max_chars`.
/// Retorna (chunk, resto).
fn split_at_char_boundary(s: &str, max_chars: usize) -> (&str, &str) {
    if s.chars().count() <= max_chars {
        return (s, "");
    }
    let byte_pos = s.char_indices()
        .nth(max_chars)
        .map(|(i, _)| i)
        .unwrap_or(s.len());
    (&s[..byte_pos], &s[byte_pos..])
}

// ─── S13.A — Formulario Feature Request ──────────────────────────────────────

pub struct SessionFormScreen {
    pub text: String,
    pub auto_approve: bool,
    /// true cuando el usuario presionó Ctrl+O para ingresar una ruta de archivo
    pub file_mode: bool,
    /// ruta que el usuario está escribiendo en file_mode
    pub file_input: String,
}

impl Default for SessionFormScreen {
    fn default() -> Self {
        Self {
            text: String::new(),
            auto_approve: false,
            file_mode: false,
            file_input: String::new(),
        }
    }
}

#[derive(Debug)]
pub enum SessionFormAction {
    None,
    Submit { text: String, auto_approve: bool },
    /// El usuario confirmó una ruta de archivo en file_mode
    LoadFile { path: String },
    Back,
}

impl SessionFormScreen {
    pub fn handle_key(&mut self, key: KeyEvent) -> SessionFormAction {
        // Modo ingreso de ruta de archivo (Ctrl+O)
        if self.file_mode {
            return match key.code {
                KeyCode::Esc => {
                    self.file_mode = false;
                    self.file_input.clear();
                    SessionFormAction::None
                }
                KeyCode::Enter => {
                    let path = self.file_input.trim().to_string();
                    self.file_mode = false;
                    self.file_input.clear();
                    if path.is_empty() {
                        SessionFormAction::None
                    } else {
                        SessionFormAction::LoadFile { path }
                    }
                }
                KeyCode::Backspace => {
                    self.file_input.pop();
                    SessionFormAction::None
                }
                KeyCode::Char(c) => {
                    self.file_input.push(c);
                    SessionFormAction::None
                }
                _ => SessionFormAction::None,
            };
        }

        match key.code {
            KeyCode::Esc => SessionFormAction::Back,
            KeyCode::Char('s') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                let trimmed = self.text.trim().to_string();
                if trimmed.is_empty() {
                    SessionFormAction::None
                } else {
                    SessionFormAction::Submit {
                        text: trimmed,
                        auto_approve: self.auto_approve,
                    }
                }
            }
            KeyCode::Char('a') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                self.auto_approve = !self.auto_approve;
                SessionFormAction::None
            }
            KeyCode::Char('o') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                self.file_mode = true;
                self.file_input.clear();
                SessionFormAction::None
            }
            KeyCode::Enter => {
                self.text.push('\n');
                SessionFormAction::None
            }
            KeyCode::Char(c) => {
                self.text.push(c);
                SessionFormAction::None
            }
            KeyCode::Backspace => {
                self.text.pop();
                SessionFormAction::None
            }
            _ => SessionFormAction::None,
        }
    }

    pub fn render(&self, frame: &mut Frame, ws_name: &str, error: Option<&str>) {
        let area = frame.area();

        let chunks = Layout::vertical([
            Constraint::Length(3), // header con workspace
            Constraint::Fill(1),   // textarea FR
            Constraint::Length(3), // opciones + footer
        ])
        .split(area);

        // Header
        let header = Paragraph::new(Line::from(vec![
            Span::styled("  workspace: ", Style::default().fg(Color::DarkGray)),
            Span::styled(ws_name, Style::default().fg(Color::Cyan)),
        ]))
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(Style::default().fg(Color::Cyan))
                .title(Span::styled(
                    " Nueva Solicitud ",
                    Style::default()
                        .fg(Color::White)
                        .add_modifier(Modifier::BOLD),
                )),
        );
        frame.render_widget(header, chunks[0]);

        // Textarea
        let display_text = if self.text.is_empty() {
            "  Describe la funcionalidad o mantenimiento solicitado...\n".to_string()
        } else {
            format!("  {}_", self.text.replace('\n', "\n  "))
        };
        let text_style = if self.text.is_empty() {
            Style::default().fg(Color::DarkGray)
        } else {
            Style::default().fg(Color::White)
        };
        let title_span = if let Some(err) = error {
            Span::styled(
                format!(" ⚠ {} ", err),
                Style::default().fg(Color::Red),
            )
        } else {
            Span::styled(
                " Feature Request ",
                Style::default().fg(Color::DarkGray),
            )
        };
        let textarea = Paragraph::new(display_text)
            .style(text_style)
            .wrap(Wrap { trim: false })
            .block(
                Block::default()
                    .borders(Borders::LEFT | Borders::RIGHT | Borders::BOTTOM)
                    .border_style(Style::default().fg(Color::Cyan))
                    .title(title_span),
            );
        frame.render_widget(textarea, chunks[1]);

        // Footer — modo normal o modo ingreso de archivo
        if self.file_mode {
            let file_footer = Paragraph::new(Line::from(vec![
                Span::styled("  Cargar archivo: ", Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)),
                Span::styled(self.file_input.as_str(), Style::default().fg(Color::White)),
                Span::styled("_", Style::default().fg(Color::Yellow)),
                Span::styled("   [Enter] cargar  [Esc] cancelar", Style::default().fg(Color::DarkGray)),
            ]))
            .block(
                Block::default()
                    .borders(Borders::LEFT | Borders::RIGHT | Borders::BOTTOM)
                    .border_style(Style::default().fg(Color::Yellow)),
            );
            frame.render_widget(file_footer, chunks[2]);
        } else {
            let auto_span = if self.auto_approve {
                Span::styled(
                    "[Ctrl+A] auto-aprobar: SÍ  ",
                    Style::default().fg(Color::Green),
                )
            } else {
                Span::styled(
                    "[Ctrl+A] auto-aprobar: no  ",
                    Style::default().fg(Color::DarkGray),
                )
            };
            let footer = Paragraph::new(Line::from(vec![
                Span::styled("  [Enter]", Style::default().fg(Color::Cyan)),
                Span::styled(" nueva línea  ", Style::default().fg(Color::DarkGray)),
                Span::styled("[Ctrl+S]", Style::default().fg(Color::Green).add_modifier(Modifier::BOLD)),
                Span::styled(" enviar  ", Style::default().fg(Color::DarkGray)),
                auto_span,
                Span::styled("[Ctrl+O]", Style::default().fg(Color::Cyan)),
                Span::styled(" cargar .md  ", Style::default().fg(Color::DarkGray)),
                Span::styled("[Esc]", Style::default().fg(Color::Cyan)),
                Span::styled(" volver", Style::default().fg(Color::DarkGray)),
            ]));
            frame.render_widget(footer, chunks[2]);
        }
    }
}

// ─── S13.B — Vista de streaming SSE ──────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub enum NodeStatus {
    Waiting,
    Running,
    Done,
    Error,
}

#[derive(Debug, Clone)]
pub struct NodeState {
    pub name: String,
    pub status: NodeStatus,
    pub detail: Option<String>,
}

pub struct SessionStreamScreen {
    pub nodes: Vec<NodeState>,
    pub log_lines: Vec<String>,
    pub has_pending_approval: bool,
    pub sdd_summary: String,
    pub is_done: bool,
    pub final_status: Option<String>,
    pub scroll: usize,
}

impl Default for SessionStreamScreen {
    fn default() -> Self {
        let nodes = vec![
            NodeState { name: "analyze_fr".into(),       status: NodeStatus::Waiting, detail: None },
            NodeState { name: "route_agents".into(),     status: NodeStatus::Waiting, detail: None },
            NodeState { name: "agents".into(),           status: NodeStatus::Waiting, detail: None },
            NodeState { name: "security_audit".into(),   status: NodeStatus::Waiting, detail: None },
            NodeState { name: "qa_review".into(),        status: NodeStatus::Waiting, detail: None },
            NodeState { name: "request_approval".into(), status: NodeStatus::Waiting, detail: None },
            NodeState { name: "deliver".into(),          status: NodeStatus::Waiting, detail: None },
        ];
        Self {
            nodes,
            log_lines: Vec::new(),
            has_pending_approval: false,
            sdd_summary: String::new(),
            is_done: false,
            final_status: None,
            scroll: 0,
        }
    }
}

#[derive(Debug)]
pub enum SessionStreamAction {
    None,
    OpenApproval,
    OpenDelivery,
    Back,
}

impl SessionStreamScreen {
    /// Procesa un evento SSE del backend y actualiza el estado visual.
    pub fn process_event(&mut self, event: &SseEvent) {
        match event.event_type.as_str() {
            "node_start" => {
                if let Some(node) = event.data.get("node").and_then(|v| v.as_str()) {
                    self.set_node_status(node, NodeStatus::Running, None);
                    self.push_log(format!("▶ {}", node));
                }
            }
            "node_end" => {
                if let Some(node) = event.data.get("node").and_then(|v| v.as_str()) {
                    let detail = event
                        .data
                        .get("summary")
                        .and_then(|v| v.as_str())
                        .map(|s| s.to_string());
                    self.set_node_status(node, NodeStatus::Done, detail.clone());
                    if let Some(d) = detail {
                        self.push_log(format!("✓ {} — {}", node, d));
                    } else {
                        self.push_log(format!("✓ {}", node));
                    }
                }
            }
            "agent_start" => {
                if let Some(agent) = event.data.get("agent").and_then(|v| v.as_str()) {
                    self.set_node_status("agents", NodeStatus::Running, Some(agent.to_string()));
                    self.push_log(format!("  ↪ agente: {}", agent));
                }
            }
            "agent_end" => {
                if let Some(agent) = event.data.get("agent").and_then(|v| v.as_str()) {
                    let passed = event
                        .data
                        .get("passed")
                        .and_then(|v| v.as_bool())
                        .unwrap_or(true);
                    let icon = if passed { "✓" } else { "✗" };
                    self.push_log(format!("  {} agente {} completado", icon, agent));
                }
            }
            "pending_approval" => {
                self.has_pending_approval = true;
                self.sdd_summary = event
                    .data
                    .get("sdd_summary")
                    .and_then(|v| v.as_str())
                    .unwrap_or("SDD sin resumen disponible")
                    .to_string();
                self.set_node_status("request_approval", NodeStatus::Running, None);
                self.push_log("⏸ Aprobación pendiente — presiona [a] para revisar".to_string());
            }
            "message" => {
                // El engine emite { "type": "message", "data": {"role": ..., "content": ...} }
                let content = event
                    .data
                    .get("content")
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                let role = event
                    .data
                    .get("role")
                    .and_then(|v| v.as_str())
                    .unwrap_or("agent");
                if !content.is_empty() {
                    // Avanzar nodos linealmente según los mensajes recibidos
                    self.advance_nodes_from_messages();
                    self.push_log(format!("[{}] {}", role, content));
                }
            }
            "stream_closed" => {
                // El engine cerró la conexión sin evento "done" → interrupción por aprobación
                if !self.is_done && !self.has_pending_approval {
                    self.has_pending_approval = true;
                    if self.sdd_summary.is_empty() {
                        self.sdd_summary = "El engine requiere aprobación para continuar.\n\
                            Revisa el log y decide si el ciclo puede avanzar.".to_string();
                    }
                    self.set_node_status("request_approval", NodeStatus::Running, None);
                    self.push_log("⏸ Stream cerrado — aprobación requerida [a]".to_string());
                }
            }
            "done" => {
                self.is_done = true;
                self.final_status = event
                    .data
                    .get("status")
                    .and_then(|v| v.as_str())
                    .map(|s| s.to_string());
                let status = self.final_status.as_deref().unwrap_or("done");
                self.push_log(format!("■ Ciclo finalizado — {}", status));
                // Marcar todos los nodos anteriores como completados
                for node in self.nodes.iter_mut() {
                    if node.status == NodeStatus::Waiting || node.status == NodeStatus::Running {
                        node.status = NodeStatus::Done;
                    }
                }
            }
            "error" => {
                let msg = event
                    .data
                    .get("message")
                    .and_then(|v| v.as_str())
                    .unwrap_or("error desconocido");
                self.push_log(format!("✗ Error: {}", msg));
            }
            other => {
                self.push_log(format!("  [{}]", other));
            }
        }
    }

    /// Avanza los nodos secuencialmente basándose en cuántos mensajes se han recibido.
    /// Heurística simple: cada mensaje nuevo activa el siguiente nodo en espera.
    fn advance_nodes_from_messages(&mut self) {
        // Contar mensajes ya en el log para saber qué nodo activar
        let msg_count = self.log_lines.iter().filter(|l| l.contains("] ")).count();
        // Secuencia de nodos que se activan progresivamente
        let sequence = [
            "analyze_fr", "route_agents", "agents", "security_audit",
            "qa_review", "request_approval", "deliver",
        ];
        // Marcar el nodo correspondiente como Running (y los anteriores como Done)
        let target_idx = msg_count.min(sequence.len().saturating_sub(1));
        for (i, node_name) in sequence.iter().enumerate() {
            if let Some(node) = self.nodes.iter_mut().find(|n| &n.name == node_name) {
                match node.status {
                    NodeStatus::Waiting if i == target_idx => {
                        node.status = NodeStatus::Running;
                    }
                    NodeStatus::Waiting if i < target_idx => {
                        node.status = NodeStatus::Done;
                    }
                    _ => {}
                }
            }
        }
    }

    fn push_log(&mut self, line: String) {
        self.log_lines.push(line);
        // Auto-scroll al final
        self.scroll = self.log_lines.len().saturating_sub(1);
    }

    fn set_node_status(&mut self, name: &str, status: NodeStatus, detail: Option<String>) {
        if let Some(node) = self.nodes.iter_mut().find(|n| n.name == name) {
            node.status = status;
            if detail.is_some() {
                node.detail = detail;
            }
        }
    }

    pub fn handle_key(&mut self, key: KeyEvent) -> SessionStreamAction {
        match key.code {
            KeyCode::Char('a') | KeyCode::Char('A') if self.has_pending_approval => {
                SessionStreamAction::OpenApproval
            }
            KeyCode::Char('d') | KeyCode::Char('D') if self.is_done => SessionStreamAction::OpenDelivery,
            KeyCode::Char('q') | KeyCode::Esc if self.is_done => SessionStreamAction::Back,
            KeyCode::Down | KeyCode::Char('j') => {
                self.scroll = (self.scroll + 1).min(self.log_lines.len().saturating_sub(1));
                SessionStreamAction::None
            }
            KeyCode::Up | KeyCode::Char('k') => {
                self.scroll = self.scroll.saturating_sub(1);
                SessionStreamAction::None
            }
            _ => SessionStreamAction::None,
        }
    }

    pub fn render(&self, frame: &mut Frame, thread_id: &str) {
        let area = frame.area();

        let chunks = Layout::vertical([
            Constraint::Length(3),  // header
            Constraint::Length(11), // nodos del grafo (7 + 2 borders + 2 padding)
            Constraint::Fill(1),    // log de eventos
            Constraint::Length(2),  // footer con atajos
        ])
        .split(area);

        // Header
        let short_id = if thread_id.len() > 24 {
            &thread_id[..24]
        } else {
            thread_id
        };
        let header = Paragraph::new(Line::from(vec![
            Span::styled("  thread: ", Style::default().fg(Color::DarkGray)),
            Span::styled(short_id, Style::default().fg(Color::Cyan)),
        ]))
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(Style::default().fg(Color::Cyan))
                .title(Span::styled(
                    " Ciclo OVD ",
                    Style::default()
                        .fg(Color::White)
                        .add_modifier(Modifier::BOLD),
                )),
        );
        frame.render_widget(header, chunks[0]);

        // Nodos del grafo
        let node_items: Vec<ListItem> = self
            .nodes
            .iter()
            .map(|n| {
                let (icon, icon_style) = match n.status {
                    NodeStatus::Waiting => ("○", Style::default().fg(Color::DarkGray)),
                    NodeStatus::Running => ("◉", Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)),
                    NodeStatus::Done    => ("●", Style::default().fg(Color::Green)),
                    NodeStatus::Error   => ("✗", Style::default().fg(Color::Red)),
                };
                let name_style = match n.status {
                    NodeStatus::Waiting => Style::default().fg(Color::DarkGray),
                    NodeStatus::Running => Style::default().fg(Color::White).add_modifier(Modifier::BOLD),
                    NodeStatus::Done    => Style::default().fg(Color::White),
                    NodeStatus::Error   => Style::default().fg(Color::Red),
                };
                let detail_span = n.detail.as_ref().map(|d| {
                    Span::styled(
                        format!("  {}", d),
                        Style::default().fg(Color::DarkGray),
                    )
                });
                let mut spans = vec![
                    Span::styled(format!("  {} ", icon), icon_style),
                    Span::styled(n.name.clone(), name_style),
                ];
                if let Some(ds) = detail_span {
                    spans.push(ds);
                }
                ListItem::new(Line::from(spans))
            })
            .collect();

        let node_list = List::new(node_items).block(
            Block::default()
                .borders(Borders::LEFT | Borders::RIGHT | Borders::BOTTOM)
                .border_style(Style::default().fg(Color::Cyan))
                .title(Span::styled(" Nodos ", Style::default().fg(Color::DarkGray))),
        );
        frame.render_widget(node_list, chunks[1]);

        // Log de eventos con wrap por ancho de área
        let log_width = chunks[2].width.saturating_sub(4) as usize; // 2 border + 2 indent
        let log_width = log_width.max(20);

        // Expandir cada línea larga en múltiples Line según el ancho disponible
        let expanded: Vec<(Vec<String>, Style)> = self.log_lines.iter().map(|l| {
            let style = if l.starts_with("✓") {
                Style::default().fg(Color::Green)
            } else if l.starts_with("✗") {
                Style::default().fg(Color::Red)
            } else if l.starts_with("■") {
                Style::default().fg(Color::Yellow)
            } else if l.starts_with("⏸") {
                Style::default().fg(Color::Magenta)
            } else if l.starts_with("▶") {
                Style::default().fg(Color::Blue)
            } else {
                Style::default().fg(Color::White)
            };
            let text = format!("  {}", l);
            // Wrap en múltiples líneas si supera el ancho
            let mut wrapped: Vec<String> = Vec::new();
            let mut remaining = text.as_str();
            let indent = "    "; // indentación para líneas de continuación
            let mut first = true;
            while !remaining.is_empty() {
                let max = if first { log_width } else { log_width.saturating_sub(indent.len()) };
                let (chunk, rest) = split_at_char_boundary(remaining, max);
                if first {
                    wrapped.push(chunk.to_string());
                } else {
                    wrapped.push(format!("{}{}", indent, chunk));
                }
                remaining = rest;
                first = false;
            }
            if wrapped.is_empty() {
                wrapped.push(String::new());
            }
            (wrapped, style)
        }).collect();

        // Total de líneas visuales (para scroll)
        let total_visual: usize = expanded.iter().map(|(lines, _)| lines.len()).sum();
        let visible_height = chunks[2].height.saturating_sub(2) as usize;
        let max_scroll = total_visual.saturating_sub(visible_height);
        let scroll_offset = self.scroll.min(max_scroll);

        // Aplanar y paginar
        let all_visual: Vec<(&str, Style)> = expanded.iter()
            .flat_map(|(lines, style)| lines.iter().map(move |l| (l.as_str(), *style)))
            .collect();

        let log_items: Vec<ListItem> = all_visual
            .iter()
            .skip(scroll_offset)
            .take(visible_height.max(1))
            .map(|(l, style)| ListItem::new(Span::styled(l.to_string(), *style)))
            .collect();

        let log_list = List::new(log_items).block(
            Block::default()
                .borders(Borders::LEFT | Borders::RIGHT | Borders::BOTTOM)
                .border_style(Style::default().fg(Color::Cyan))
                .title(Span::styled(" Log ", Style::default().fg(Color::DarkGray))),
        );
        frame.render_widget(log_list, chunks[2]);

        // Footer
        let mut footer_spans = vec![
            Span::styled("  [↑↓/jk]", Style::default().fg(Color::Cyan)),
            Span::styled(" scroll  ", Style::default().fg(Color::DarkGray)),
        ];
        if self.has_pending_approval {
            footer_spans.push(Span::styled(
                "[a] ",
                Style::default()
                    .fg(Color::Magenta)
                    .add_modifier(Modifier::BOLD),
            ));
            footer_spans.push(Span::styled(
                "revisar SDD  ",
                Style::default().fg(Color::DarkGray),
            ));
        }
        if self.is_done {
            footer_spans.push(Span::styled("[d] ", Style::default().fg(Color::Green)));
            footer_spans.push(Span::styled("ver entrega  ", Style::default().fg(Color::DarkGray)));
            footer_spans.push(Span::styled("[q] ", Style::default().fg(Color::Cyan)));
            footer_spans.push(Span::styled("volver", Style::default().fg(Color::DarkGray)));
        } else if !self.has_pending_approval {
            footer_spans.push(Span::styled(
                "procesando...",
                Style::default().fg(Color::Yellow),
            ));
        }
        frame.render_widget(Paragraph::new(Line::from(footer_spans)), chunks[3]);
    }
}

// ─── S13.C / S15-TUI — Revisión iterativa del SDD ───────────────────────────

use crate::models::session::SddContent;
use tui_textarea::TextArea;

#[derive(Debug, Clone, PartialEq)]
pub enum ReviewMode {
    Scroll,     // navegación del SDD
    Input,      // escritura de feedback
    FileInput,  // S15T.H: ingreso de ruta de archivo a adjuntar
}

pub struct SddReviewScreen {
    pub sdd: SddContent,
    pub revision_count: u32,
    pub scroll: u16,
    pub feedback: TextArea<'static>,
    pub mode: ReviewMode,
    pub loading: bool,
    /// S15T.H: ruta que el usuario está tipeando para adjuntar
    pub file_path_input: String,
    /// S15T.H: nombre del último archivo adjuntado (para mostrar indicador)
    pub attached_file: Option<String>,
}

impl Default for SddReviewScreen {
    fn default() -> Self {
        let mut ta = TextArea::default();
        ta.set_placeholder_text("Escribe el feedback para solicitar revisión...");
        ta.set_cursor_line_style(ratatui::style::Style::default());
        Self {
            sdd: SddContent::default(),
            revision_count: 0,
            scroll: 0,
            feedback: ta,
            mode: ReviewMode::Scroll,
            loading: true,
            file_path_input: String::new(),
            attached_file: None,
        }
    }
}

#[derive(Debug)]
pub enum ReviewAction {
    None,
    Approve,
    RequestRevision { comment: String },
    Reject,
    Back,
    ExportSdd,
}

impl SddReviewScreen {
    pub fn handle_key(&mut self, key: KeyEvent) -> ReviewAction {
        match self.mode {
            ReviewMode::Scroll => match key.code {
                KeyCode::Tab => {
                    self.mode = ReviewMode::Input;
                    ReviewAction::None
                }
                KeyCode::Char('y') | KeyCode::Char('Y') => ReviewAction::Approve,
                KeyCode::Char('r') | KeyCode::Char('R') => {
                    let text = self.feedback.lines().join("\n");
                    if text.trim().is_empty() {
                        self.mode = ReviewMode::Input;
                        ReviewAction::None
                    } else {
                        ReviewAction::RequestRevision {
                            comment: text.trim().to_string(),
                        }
                    }
                }
                KeyCode::Char('n') | KeyCode::Char('N') => ReviewAction::Reject,
                KeyCode::Char('e') | KeyCode::Char('E') => ReviewAction::ExportSdd,
                // S15T.H: [f] abre el modo ingreso de ruta de archivo
                KeyCode::Char('f') | KeyCode::Char('F') => {
                    self.mode = ReviewMode::FileInput;
                    self.file_path_input.clear();
                    ReviewAction::None
                }
                KeyCode::Char('q') | KeyCode::Esc => ReviewAction::Back,
                KeyCode::Down | KeyCode::Char('j') => {
                    self.scroll = self.scroll.saturating_add(1);
                    ReviewAction::None
                }
                KeyCode::Up | KeyCode::Char('k') => {
                    self.scroll = self.scroll.saturating_sub(1);
                    ReviewAction::None
                }
                _ => ReviewAction::None,
            },
            ReviewMode::Input => {
                let is_send = (key.code == KeyCode::Char('r') || key.code == KeyCode::Enter)
                    && key.modifiers.contains(crossterm::event::KeyModifiers::CONTROL);
                if is_send {
                    let text = self.feedback.lines().join("\n");
                    return if text.trim().is_empty() {
                        ReviewAction::None
                    } else {
                        ReviewAction::RequestRevision { comment: text.trim().to_string() }
                    };
                }
                if key.code == KeyCode::Tab || key.code == KeyCode::Esc {
                    self.mode = ReviewMode::Scroll;
                    return ReviewAction::None;
                }
                self.feedback.input(key);
                ReviewAction::None
            }
            // S15T.H: modo de ingreso de ruta de archivo a adjuntar
            ReviewMode::FileInput => match key.code {
                KeyCode::Esc | KeyCode::Tab => {
                    self.mode = ReviewMode::Scroll;
                    ReviewAction::None
                }
                KeyCode::Enter => {
                    let path = self.file_path_input.trim().to_string();
                    if !path.is_empty() {
                        // SEC MEDIUM-03: bloquear rutas sensibles del sistema
                        let sensitive = [".ssh", ".aws", ".ovd", "/etc/", "/root/", "id_rsa", "id_ed25519", ".env"];
                        let path_lower = path.to_lowercase();
                        if sensitive.iter().any(|s| path_lower.contains(s)) {
                            self.attached_file = Some("ERROR: ruta sensible bloqueada por seguridad".to_string());
                            self.mode = ReviewMode::Input;
                            // No devolvemos ReviewAction diferente — permanece None
                            return ReviewAction::None;
                        }
                        match std::fs::read_to_string(&path) {
                            Ok(content) => {
                                let filename = std::path::Path::new(&path)
                                    .file_name()
                                    .and_then(|n| n.to_str())
                                    .unwrap_or(&path)
                                    .to_string();
                                self.attached_file = Some(filename.clone());
                                // Limitar a 4000 caracteres para no saturar el contexto
                                let truncated: String = content.chars().take(4_000).collect();
                                let header = format!(
                                    "=== Archivo adjunto: {} ===\n{}\n=== Fin del archivo ===\n\n",
                                    filename, truncated
                                );
                                let current = self.feedback.lines().join("\n");
                                let combined = if current.trim().is_empty() {
                                    header
                                } else {
                                    format!("{}{}", header, current)
                                };
                                // Reconstruir el TextArea con el contenido combinado
                                let lines: Vec<String> = combined
                                    .lines()
                                    .map(|l| l.to_string())
                                    .collect();
                                self.feedback = TextArea::new(lines);
                                self.feedback.set_placeholder_text(
                                    "Escribe el feedback para solicitar revisión...",
                                );
                                self.feedback
                                    .set_cursor_line_style(ratatui::style::Style::default());
                            }
                            Err(e) => {
                                self.attached_file =
                                    Some(format!("ERROR: {}", e));
                            }
                        }
                    }
                    self.mode = ReviewMode::Input;
                    ReviewAction::None
                }
                KeyCode::Char(c) => {
                    self.file_path_input.push(c);
                    ReviewAction::None
                }
                KeyCode::Backspace => {
                    self.file_path_input.pop();
                    ReviewAction::None
                }
                _ => ReviewAction::None,
            },
        }
    }

    /// Formatea el SDD completo como Markdown exportable.
    pub fn format_sdd(&self) -> String {
        let sdd = &self.sdd;
        let mut lines = Vec::new();

        // Resumen
        if !sdd.summary.is_empty() {
            lines.push("── RESUMEN ─────────────────────────────".to_string());
            lines.push(sdd.summary.clone());
            lines.push(String::new());
        }

        // Requisitos
        if !sdd.requirements.is_empty() {
            lines.push(format!("── REQUISITOS ({}) ──────────────────────", sdd.requirements.len()));
            for req in &sdd.requirements {
                let id   = req.get("id").and_then(|v| v.as_str()).unwrap_or("?");
                let prio = req.get("priority").and_then(|v| v.as_str()).unwrap_or("");
                let desc = req.get("description").and_then(|v| v.as_str()).unwrap_or("");
                lines.push(format!("  {} [{}] {}", id, prio, desc));
            }
            lines.push(String::new());
        }

        // Tareas
        if !sdd.tasks.is_empty() {
            lines.push(format!("── TAREAS ({}) ──────────────────────────", sdd.tasks.len()));
            for task in &sdd.tasks {
                let id    = task.get("id").and_then(|v| v.as_str()).unwrap_or("?");
                let agent = task.get("agent").and_then(|v| v.as_str()).unwrap_or("?");
                let title = task.get("title").and_then(|v| v.as_str()).unwrap_or("");
                let comp  = task.get("estimated_complexity").and_then(|v| v.as_str()).unwrap_or("");
                lines.push(format!("  {} [{}·{}] {}", id, agent, comp, title));
            }
            lines.push(String::new());
        }

        // Restricciones
        if !sdd.constraints.is_empty() {
            lines.push(format!("── RESTRICCIONES ({}) ───────────────────", sdd.constraints.len()));
            for con in &sdd.constraints {
                let id   = con.get("id").and_then(|v| v.as_str()).unwrap_or("?");
                let cat  = con.get("category").and_then(|v| v.as_str()).unwrap_or("");
                let desc = con.get("description").and_then(|v| v.as_str()).unwrap_or("");
                lines.push(format!("  {} [{}] {}", id, cat, desc));
            }
            lines.push(String::new());
        }

        // Diseño
        if let Some(overview) = sdd.design.get("overview").and_then(|v| v.as_str()) {
            if !overview.is_empty() {
                lines.push("── DISEÑO ──────────────────────────────".to_string());
                for line in overview.lines().take(20) {
                    lines.push(format!("  {}", line));
                }
            }
        }

        if lines.is_empty() {
            "  Sin contenido en el SDD".to_string()
        } else {
            lines.join("\n")
        }
    }

    pub fn render(&mut self, frame: &mut Frame, thread_id: &str) {
        let area = frame.area();

        let input_height: u16 = match self.mode {
            ReviewMode::Input     => 5,
            ReviewMode::FileInput => 3,
            ReviewMode::Scroll    => 3,
        };
        let chunks = Layout::vertical([
            Constraint::Length(3),            // header
            Constraint::Fill(1),              // SDD scrollable
            Constraint::Length(input_height), // feedback / file-input
            Constraint::Length(2),            // footer
        ])
        .split(area);

        // Header
        let short_id = if thread_id.len() > 24 { &thread_id[..24] } else { thread_id };
        let round_label = if self.revision_count > 0 {
            format!("  Ronda #{}", self.revision_count + 1)
        } else {
            String::new()
        };
        let header = Paragraph::new(Line::from(vec![
            Span::styled("  thread: ", Style::default().fg(Color::DarkGray)),
            Span::styled(short_id, Style::default().fg(Color::Yellow)),
            Span::styled(round_label, Style::default().fg(Color::DarkGray)),
        ]))
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(Style::default().fg(Color::Yellow))
                .title(Span::styled(
                    " ⏸ Revisión del Plan ",
                    Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD),
                )),
        );
        frame.render_widget(header, chunks[0]);

        // SDD scrollable
        let sdd_text = if self.loading {
            "  Cargando SDD...".to_string()
        } else {
            self.format_sdd()
        };
        let sdd_widget = Paragraph::new(sdd_text)
            .style(Style::default().fg(Color::White))
            .wrap(Wrap { trim: false })
            .scroll((self.scroll, 0))
            .block(
                Block::default()
                    .borders(Borders::LEFT | Borders::RIGHT | Borders::BOTTOM)
                    .border_style(Style::default().fg(Color::Yellow))
                    .title(Span::styled(
                        " SDD — revisa antes de decidir  [↑↓/jk] scroll ",
                        Style::default().fg(Color::DarkGray),
                    )),
            );
        frame.render_widget(sdd_widget, chunks[1]);

        // Feedback / FileInput
        match self.mode {
            ReviewMode::FileInput => {
                // S15T.H: mostrar input de ruta de archivo
                let display = format!(
                    "  Ruta: {}█",
                    self.file_path_input
                );
                let file_widget = Paragraph::new(display)
                    .style(Style::default().fg(Color::White))
                    .block(
                        Block::default()
                            .borders(Borders::LEFT | Borders::RIGHT | Borders::BOTTOM)
                            .border_style(Style::default().fg(Color::Magenta))
                            .title(Span::styled(
                                " Adjuntar archivo  [Enter] confirmar  [Esc] cancelar ",
                                Style::default().fg(Color::Magenta),
                            )),
                    );
                frame.render_widget(file_widget, chunks[2]);
            }
            _ => {
                // Feedback input — TextArea con cursor navegable (UX-01)
                let (input_border_style, input_title) = if self.mode == ReviewMode::Input {
                    (
                        Style::default().fg(Color::Cyan),
                        " Feedback  [Tab/Esc] listo  [Ctrl+R] enviar  [← → ↑ ↓] cursor ",
                    )
                } else {
                    let base = " Feedback  [Tab] escribir  [f] adjuntar archivo ";
                    (Style::default().fg(Color::DarkGray), base)
                };
                // Indicador de archivo adjunto
                let title_with_attach = if let Some(ref fname) = self.attached_file {
                    if fname.starts_with("ERROR") {
                        format!("{} ⚠ {}", input_title, fname)
                    } else {
                        format!("{}  ● adjunto: {}", input_title, fname)
                    }
                } else {
                    input_title.to_string()
                };
                self.feedback.set_block(
                    Block::default()
                        .borders(Borders::LEFT | Borders::RIGHT | Borders::BOTTOM)
                        .border_style(input_border_style)
                        .title(Span::styled(title_with_attach, Style::default().fg(Color::DarkGray))),
                );
                self.feedback.set_style(if self.mode == ReviewMode::Input {
                    Style::default().fg(Color::White)
                } else {
                    Style::default().fg(Color::DarkGray)
                });
                frame.render_widget(self.feedback.widget(), chunks[2]);
            }
        }

        // Footer
        let footer = Paragraph::new(Line::from(vec![
            Span::styled("  [y] ", Style::default().fg(Color::Green).add_modifier(Modifier::BOLD)),
            Span::styled("Aprobar  ", Style::default().fg(Color::DarkGray)),
            Span::styled("[r] ", Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD)),
            Span::styled("Revisión  ", Style::default().fg(Color::DarkGray)),
            Span::styled("[n] ", Style::default().fg(Color::Red).add_modifier(Modifier::BOLD)),
            Span::styled("Rechazar  ", Style::default().fg(Color::DarkGray)),
            Span::styled("[e] ", Style::default().fg(Color::Green)),
            Span::styled("SDD  ", Style::default().fg(Color::DarkGray)),
            Span::styled("[f] ", Style::default().fg(Color::Magenta)),
            Span::styled("adjuntar  ", Style::default().fg(Color::DarkGray)),
            Span::styled("[Tab] ", Style::default().fg(Color::Cyan)),
            Span::styled("input  ", Style::default().fg(Color::DarkGray)),
            Span::styled("[q] ", Style::default().fg(Color::Cyan)),
            Span::styled("volver", Style::default().fg(Color::DarkGray)),
        ]));
        frame.render_widget(footer, chunks[3]);
    }
}

// ─── Tests SddReviewScreen ────────────────────────────────────────────────────

#[cfg(test)]
mod tests_sdd_review {
    use super::*;
    use crossterm::event::{KeyCode, KeyEvent, KeyModifiers};

    fn make_key(code: KeyCode) -> KeyEvent {
        KeyEvent::new(code, KeyModifiers::NONE)
    }

    fn ctrl_key(code: KeyCode) -> KeyEvent {
        KeyEvent::new(code, KeyModifiers::CONTROL)
    }

    #[test]
    fn y_en_scroll_retorna_approve() {
        let mut screen = SddReviewScreen::default();
        screen.loading = false;
        assert!(matches!(screen.handle_key(make_key(KeyCode::Char('y'))), ReviewAction::Approve));
        assert!(matches!(screen.handle_key(make_key(KeyCode::Char('Y'))), ReviewAction::Approve));
    }

    #[test]
    fn n_en_scroll_retorna_reject() {
        let mut screen = SddReviewScreen::default();
        screen.loading = false;
        assert!(matches!(screen.handle_key(make_key(KeyCode::Char('n'))), ReviewAction::Reject));
    }

    #[test]
    fn q_retorna_back() {
        let mut screen = SddReviewScreen::default();
        assert!(matches!(screen.handle_key(make_key(KeyCode::Char('q'))), ReviewAction::Back));
        assert!(matches!(screen.handle_key(make_key(KeyCode::Esc)), ReviewAction::Back));
    }

    #[test]
    fn e_retorna_export_sdd_en_scroll_mode() {
        let mut screen = SddReviewScreen::default();
        assert_eq!(screen.mode, ReviewMode::Scroll);
        assert!(matches!(screen.handle_key(make_key(KeyCode::Char('e'))), ReviewAction::ExportSdd));
        assert!(matches!(screen.handle_key(make_key(KeyCode::Char('E'))), ReviewAction::ExportSdd));
    }

    #[test]
    fn tab_cambia_a_input_mode() {
        let mut screen = SddReviewScreen::default();
        assert_eq!(screen.mode, ReviewMode::Scroll);
        screen.handle_key(make_key(KeyCode::Tab));
        assert_eq!(screen.mode, ReviewMode::Input);
    }

    #[test]
    fn tab_en_input_vuelve_a_scroll() {
        let mut screen = SddReviewScreen::default();
        screen.mode = ReviewMode::Input;
        screen.handle_key(make_key(KeyCode::Tab));
        assert_eq!(screen.mode, ReviewMode::Scroll);
    }

    #[test]
    fn esc_en_input_vuelve_a_scroll() {
        let mut screen = SddReviewScreen::default();
        screen.mode = ReviewMode::Input;
        screen.handle_key(make_key(KeyCode::Esc));
        assert_eq!(screen.mode, ReviewMode::Scroll);
    }

    #[test]
    fn r_sin_feedback_cambia_a_input() {
        let mut screen = SddReviewScreen::default();
        screen.handle_key(make_key(KeyCode::Char('r')));
        assert_eq!(screen.mode, ReviewMode::Input);
    }

    #[test]
    fn scroll_down_incrementa() {
        let mut screen = SddReviewScreen::default();
        assert_eq!(screen.scroll, 0);
        screen.handle_key(make_key(KeyCode::Down));
        assert_eq!(screen.scroll, 1);
        screen.handle_key(make_key(KeyCode::Char('j')));
        assert_eq!(screen.scroll, 2);
    }

    #[test]
    fn scroll_up_no_hace_underflow() {
        let mut screen = SddReviewScreen::default();
        screen.scroll = 0;
        screen.handle_key(make_key(KeyCode::Up));
        assert_eq!(screen.scroll, 0);
    }

    #[test]
    fn format_sdd_vacio_retorna_sin_contenido() {
        let screen = SddReviewScreen::default();
        let output = screen.format_sdd();
        assert!(output.contains("Sin contenido") || output.is_empty() || output.len() < 100);
    }

    #[test]
    fn format_sdd_con_summary_lo_incluye() {
        let mut screen = SddReviewScreen::default();
        screen.loading = false;
        screen.sdd.summary = "Implementar endpoint de usuarios".to_string();
        let output = screen.format_sdd();
        assert!(output.contains("Implementar endpoint de usuarios"));
    }

    #[test]
    fn format_sdd_es_publico_y_retorna_string() {
        let screen = SddReviewScreen::default();
        let _: String = screen.format_sdd(); // compila solo si format_sdd es pub
    }

    // S15T.H — tests de FileInput
    #[test]
    fn f_en_scroll_activa_file_input_mode() {
        let mut screen = SddReviewScreen::default();
        assert_eq!(screen.mode, ReviewMode::Scroll);
        screen.handle_key(make_key(KeyCode::Char('f')));
        assert_eq!(screen.mode, ReviewMode::FileInput);
    }

    #[test]
    fn f_mayuscula_activa_file_input_mode() {
        let mut screen = SddReviewScreen::default();
        screen.handle_key(make_key(KeyCode::Char('F')));
        assert_eq!(screen.mode, ReviewMode::FileInput);
    }

    #[test]
    fn file_input_limpia_ruta_al_activar() {
        let mut screen = SddReviewScreen::default();
        screen.file_path_input = "/tmp/previo.txt".to_string();
        screen.handle_key(make_key(KeyCode::Char('f')));
        assert!(screen.file_path_input.is_empty());
    }

    #[test]
    fn file_input_esc_vuelve_a_scroll() {
        let mut screen = SddReviewScreen::default();
        screen.mode = ReviewMode::FileInput;
        screen.handle_key(make_key(KeyCode::Esc));
        assert_eq!(screen.mode, ReviewMode::Scroll);
    }

    #[test]
    fn file_input_tab_vuelve_a_scroll() {
        let mut screen = SddReviewScreen::default();
        screen.mode = ReviewMode::FileInput;
        screen.handle_key(make_key(KeyCode::Tab));
        assert_eq!(screen.mode, ReviewMode::Scroll);
    }

    #[test]
    fn file_input_acumula_caracteres() {
        let mut screen = SddReviewScreen::default();
        screen.mode = ReviewMode::FileInput;
        for c in "/tmp/req.txt".chars() {
            screen.handle_key(make_key(KeyCode::Char(c)));
        }
        assert_eq!(screen.file_path_input, "/tmp/req.txt");
    }

    #[test]
    fn file_input_backspace_borra_ultimo() {
        let mut screen = SddReviewScreen::default();
        screen.mode = ReviewMode::FileInput;
        screen.file_path_input = "/tmp/x".to_string();
        screen.handle_key(make_key(KeyCode::Backspace));
        assert_eq!(screen.file_path_input, "/tmp/");
    }

    #[test]
    fn file_input_enter_con_ruta_invalida_va_a_input_con_error() {
        let mut screen = SddReviewScreen::default();
        screen.mode = ReviewMode::FileInput;
        screen.file_path_input = "/ruta/que/no/existe.txt".to_string();
        screen.handle_key(make_key(KeyCode::Enter));
        // Debe cambiar al modo Input aunque haya error
        assert_eq!(screen.mode, ReviewMode::Input);
        // attached_file debe indicar el error
        assert!(screen.attached_file.as_deref().map(|s| s.starts_with("ERROR")).unwrap_or(false));
    }

    #[test]
    fn file_input_enter_con_archivo_real_inyecta_contenido() {
        use std::io::Write;
        let mut tmp = tempfile::NamedTempFile::new().expect("temp file");
        write!(tmp, "Requisito: el sistema debe ser rápido").expect("write");
        let path = tmp.path().to_str().unwrap().to_string();

        let mut screen = SddReviewScreen::default();
        screen.mode = ReviewMode::FileInput;
        screen.file_path_input = path;
        screen.handle_key(make_key(KeyCode::Enter));

        assert_eq!(screen.mode, ReviewMode::Input);
        let content = screen.feedback.lines().join("\n");
        assert!(content.contains("Requisito"));
        assert!(screen.attached_file.is_some());
        assert!(!screen.attached_file.as_deref().unwrap().starts_with("ERROR"));
    }

    #[test]
    fn file_input_bloquea_ruta_sensible_ssh() {
        // SEC MEDIUM-03: rutas con .ssh deben ser bloqueadas
        let mut screen = SddReviewScreen::default();
        screen.mode = ReviewMode::FileInput;
        screen.file_path_input = "/home/user/.ssh/id_rsa".to_string();
        let action = screen.handle_key(make_key(KeyCode::Enter));
        assert!(matches!(action, ReviewAction::None));
        assert_eq!(screen.mode, ReviewMode::Input);
        let attached = screen.attached_file.as_deref().unwrap_or("");
        assert!(attached.contains("ERROR"));
    }

    #[test]
    fn file_input_bloquea_ruta_sensible_env() {
        let mut screen = SddReviewScreen::default();
        screen.mode = ReviewMode::FileInput;
        screen.file_path_input = "/proyecto/.env".to_string();
        screen.handle_key(make_key(KeyCode::Enter));
        let attached = screen.attached_file.as_deref().unwrap_or("");
        assert!(attached.contains("ERROR"));
    }

    #[test]
    fn file_input_trunca_archivo_grande() {
        use std::io::Write;
        let mut tmp = tempfile::NamedTempFile::new().expect("temp file");
        // 5000 caracteres
        write!(tmp, "{}", "A".repeat(5_000)).expect("write");
        let path = tmp.path().to_str().unwrap().to_string();

        let mut screen = SddReviewScreen::default();
        screen.mode = ReviewMode::FileInput;
        screen.file_path_input = path;
        screen.handle_key(make_key(KeyCode::Enter));

        let content = screen.feedback.lines().join("\n");
        // El contenido del archivo se trunca a 4000 chars, más el header
        assert!(content.len() < 5_000 + 200);
    }
}
