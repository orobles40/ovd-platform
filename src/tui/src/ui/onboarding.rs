// OVD Platform — Wizard de onboarding (S14.C)
//
// Se muestra la primera vez que se ejecuta el binario `ovd`
// (cuando ~/.ovd/config.toml no existe o el org_id está vacío).
//
// Pasos:
//   1. URL del OVD Engine (ej: https://ovd.omarrobles.dev)
//   2. Org ID  (ej: omarrobles)
//   3. Confirmación y guardado

use crossterm::event::{KeyCode, KeyEvent};
use ratatui::{
    Frame,
    layout::{Alignment, Constraint, Layout, Margin},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Clear, Paragraph},
};

#[derive(Debug, Clone, PartialEq)]
pub enum OnboardingStep {
    ApiUrl,
    OrgId,
    Confirm,
}

pub struct OnboardingWizard {
    pub step: OnboardingStep,
    pub api_url: String,
    pub org_id: String,
    pub error: Option<String>,
}

impl Default for OnboardingWizard {
    fn default() -> Self {
        Self {
            step: OnboardingStep::ApiUrl,
            api_url: "http://localhost:8000".to_string(),
            org_id: String::new(),
            error: None,
        }
    }
}

#[derive(Debug)]
pub enum OnboardingAction {
    None,
    /// Configuración lista: (api_url, org_id)
    Complete { api_url: String, org_id: String },
}

impl OnboardingWizard {
    pub fn handle_key(&mut self, key: KeyEvent) -> OnboardingAction {
        match key.code {
            KeyCode::Backspace => {
                match self.step {
                    OnboardingStep::ApiUrl  => { self.api_url.pop(); }
                    OnboardingStep::OrgId   => { self.org_id.pop(); }
                    OnboardingStep::Confirm => {}
                }
                self.error = None;
                OnboardingAction::None
            }
            KeyCode::Char(c) => {
                match self.step {
                    OnboardingStep::ApiUrl  => self.api_url.push(c),
                    OnboardingStep::OrgId   => self.org_id.push(c),
                    OnboardingStep::Confirm => {}
                }
                self.error = None;
                OnboardingAction::None
            }
            KeyCode::Enter | KeyCode::Tab => {
                match self.step {
                    OnboardingStep::ApiUrl => {
                        let url = self.api_url.trim().to_string();
                        if url.is_empty() || (!url.starts_with("http://") && !url.starts_with("https://")) {
                            self.error = Some("Ingresa una URL válida (http:// o https://)".to_string());
                        } else {
                            self.api_url = url;
                            self.step = OnboardingStep::OrgId;
                            self.error = None;
                        }
                    }
                    OnboardingStep::OrgId => {
                        let id = self.org_id.trim().to_string();
                        if id.is_empty() {
                            self.error = Some("El Org ID no puede estar vacío".to_string());
                        } else {
                            self.org_id = id;
                            self.step = OnboardingStep::Confirm;
                            self.error = None;
                        }
                    }
                    OnboardingStep::Confirm => {
                        return OnboardingAction::Complete {
                            api_url: self.api_url.clone(),
                            org_id: self.org_id.clone(),
                        };
                    }
                }
                OnboardingAction::None
            }
            KeyCode::Esc => {
                // Retroceder un paso
                match self.step {
                    OnboardingStep::ApiUrl  => {}
                    OnboardingStep::OrgId   => { self.step = OnboardingStep::ApiUrl; }
                    OnboardingStep::Confirm => { self.step = OnboardingStep::OrgId; }
                }
                self.error = None;
                OnboardingAction::None
            }
            _ => OnboardingAction::None,
        }
    }

    pub fn render(&self, frame: &mut Frame) {
        let area = frame.area();

        // Centrar el wizard
        let vert = Layout::vertical([
            Constraint::Fill(1),
            Constraint::Length(16),
            Constraint::Fill(1),
        ])
        .split(area);

        let horiz = Layout::horizontal([
            Constraint::Fill(1),
            Constraint::Min(52),
            Constraint::Max(64),
            Constraint::Fill(1),
        ])
        .split(vert[1]);

        let form_area = horiz[2];
        frame.render_widget(Clear, form_area);

        // Contenedor
        let step_label = match self.step {
            OnboardingStep::ApiUrl  => "1/3 — URL del servidor",
            OnboardingStep::OrgId   => "2/3 — Identificador de organización",
            OnboardingStep::Confirm => "3/3 — Confirmar configuración",
        };
        let block = Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Color::Cyan))
            .title(Line::from(vec![
                Span::styled(" OVD ", Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD)),
                Span::styled("Setup ", Style::default().fg(Color::White)),
                Span::styled(step_label, Style::default().fg(Color::DarkGray)),
                Span::raw(" "),
            ]));
        frame.render_widget(block, form_area);

        let inner = form_area.inner(Margin { horizontal: 2, vertical: 1 });

        let rows = Layout::vertical([
            Constraint::Length(1), // subtítulo
            Constraint::Length(1), // sep
            Constraint::Length(1), // label 1
            Constraint::Length(1), // input 1
            Constraint::Length(1), // gap
            Constraint::Length(1), // label 2
            Constraint::Length(1), // input 2
            Constraint::Length(1), // gap
            Constraint::Length(1), // confirm / botón
            Constraint::Length(1), // error
            Constraint::Length(1), // ayuda
        ])
        .split(inner);

        frame.render_widget(
            Paragraph::new("Configura tu primera conexión a OVD Engine")
                .style(Style::default().fg(Color::DarkGray))
                .alignment(Alignment::Center),
            rows[0],
        );
        frame.render_widget(
            Paragraph::new("─".repeat(inner.width as usize))
                .style(Style::default().fg(Color::DarkGray)),
            rows[1],
        );

        // Campo API URL
        let url_active = self.step == OnboardingStep::ApiUrl;
        let url_label_style = if url_active {
            Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD)
        } else {
            Style::default().fg(Color::Gray)
        };
        frame.render_widget(
            Paragraph::new("API URL:").style(url_label_style),
            rows[2],
        );
        let url_display = if url_active {
            format!("{}_", self.api_url)
        } else {
            self.api_url.clone()
        };
        frame.render_widget(
            Paragraph::new(url_display)
                .style(Style::default().fg(Color::White))
                .block(
                    Block::default()
                        .borders(Borders::BOTTOM)
                        .border_style(if url_active {
                            Style::default().fg(Color::Cyan)
                        } else {
                            Style::default().fg(Color::DarkGray)
                        }),
                ),
            rows[3],
        );

        // Campo Org ID
        let org_active = self.step == OnboardingStep::OrgId;
        let org_label_style = if org_active {
            Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD)
        } else {
            Style::default().fg(Color::Gray)
        };
        frame.render_widget(
            Paragraph::new("Org ID:").style(org_label_style),
            rows[5],
        );
        let org_display = if org_active {
            format!("{}_", self.org_id)
        } else if self.org_id.is_empty() {
            "—".to_string()
        } else {
            self.org_id.clone()
        };
        frame.render_widget(
            Paragraph::new(org_display)
                .style(Style::default().fg(Color::White))
                .block(
                    Block::default()
                        .borders(Borders::BOTTOM)
                        .border_style(if org_active {
                            Style::default().fg(Color::Cyan)
                        } else {
                            Style::default().fg(Color::DarkGray)
                        }),
                ),
            rows[6],
        );

        // Botón de acción
        let btn = match self.step {
            OnboardingStep::Confirm => Paragraph::new("  [ Enter — Guardar y continuar ]")
                .style(Style::default().fg(Color::Green).add_modifier(Modifier::BOLD))
                .alignment(Alignment::Center),
            _ => Paragraph::new("  [ Enter — Siguiente ]")
                .style(Style::default().fg(Color::Cyan))
                .alignment(Alignment::Center),
        };
        frame.render_widget(btn, rows[8]);

        // Error
        if let Some(err) = &self.error {
            frame.render_widget(
                Paragraph::new(format!("⚠ {}", err))
                    .style(Style::default().fg(Color::Red))
                    .alignment(Alignment::Center),
                rows[9],
            );
        }

        // Ayuda
        frame.render_widget(
            Paragraph::new("[Esc] volver  [Tab/Enter] siguiente")
                .style(Style::default().fg(Color::DarkGray))
                .alignment(Alignment::Center),
            rows[10],
        );
    }
}
