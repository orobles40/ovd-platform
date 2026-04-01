// OVD Platform — Pantalla de Login (S12.D)
//
// Layout:
//   ┌─────────────────────────────────┐
//   │       OVD Platform              │
//   │   Omar Robles               │
//   ├─────────────────────────────────┤
//   │  Email:    [___________________]│
//   │  Password: [___________________]│
//   │                                 │
//   │          [ Iniciar sesión ]     │
//   ├─────────────────────────────────┤
//   │  ⚠ Mensaje de error (si aplica) │
//   └─────────────────────────────────┘

use crossterm::event::{KeyCode, KeyEvent};
use ratatui::{
    Frame,
    layout::{Alignment, Constraint, Direction, Layout, Margin},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Clear, Paragraph},
};

/// Campo de input activo
#[derive(Debug, Clone, PartialEq)]
pub enum LoginField {
    Email,
    Password,
}

/// Estado de la pantalla de login
pub struct LoginScreen {
    pub email: String,
    pub password: String,
    pub active_field: LoginField,
    pub submitting: bool,
}

impl Default for LoginScreen {
    fn default() -> Self {
        Self {
            email: String::new(),
            password: String::new(),
            active_field: LoginField::Email,
            submitting: false,
        }
    }
}

impl LoginScreen {
    /// Maneja un KeyEvent. Retorna true si el usuario presionó Enter en el formulario.
    pub fn handle_key(&mut self, key: KeyEvent) -> LoginAction {
        match key.code {
            KeyCode::Tab | KeyCode::Down => {
                self.active_field = match self.active_field {
                    LoginField::Email => LoginField::Password,
                    LoginField::Password => LoginField::Email,
                };
                LoginAction::None
            }
            KeyCode::Up => {
                self.active_field = match self.active_field {
                    LoginField::Email => LoginField::Password,
                    LoginField::Password => LoginField::Email,
                };
                LoginAction::None
            }
            KeyCode::Enter => {
                if self.active_field == LoginField::Email {
                    self.active_field = LoginField::Password;
                    LoginAction::None
                } else if !self.email.is_empty() && !self.password.is_empty() {
                    self.submitting = true;
                    LoginAction::Submit {
                        email: self.email.clone(),
                        password: self.password.clone(),
                    }
                } else {
                    LoginAction::None
                }
            }
            KeyCode::Char(c) => {
                match self.active_field {
                    LoginField::Email => self.email.push(c),
                    LoginField::Password => self.password.push(c),
                }
                LoginAction::None
            }
            KeyCode::Backspace => {
                match self.active_field {
                    LoginField::Email => { self.email.pop(); }
                    LoginField::Password => { self.password.pop(); }
                }
                LoginAction::None
            }
            KeyCode::Esc => LoginAction::Quit,
            _ => LoginAction::None,
        }
    }

    /// Renderiza la pantalla de login en el frame de Ratatui.
    pub fn render(&self, frame: &mut Frame, error: Option<&str>) {
        let area = frame.area();

        // Centrar el formulario en la pantalla
        let vertical = Layout::vertical([
            Constraint::Fill(1),
            Constraint::Length(18), // 2 borders + 2 margin + 14 rows de contenido
            Constraint::Fill(1),
        ])
        .split(area);

        let horizontal = Layout::horizontal([
            Constraint::Fill(1),
            Constraint::Min(50),
            Constraint::Max(60),
            Constraint::Fill(1),
        ])
        .split(vertical[1]);

        let form_area = horizontal[2];

        // Limpiar área del formulario
        frame.render_widget(Clear, form_area);

        // Bloque contenedor
        let block = Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Color::Cyan))
            .title(Line::from(vec![
                Span::styled(" OVD ", Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD)),
                Span::styled("Platform ", Style::default().fg(Color::White)),
            ]));

        frame.render_widget(block, form_area);

        let inner = form_area.inner(Margin { horizontal: 2, vertical: 1 });

        let rows = Layout::vertical([
            Constraint::Length(1), // título "Omar Robles"
            Constraint::Length(1), // separador
            Constraint::Length(1), // label email
            Constraint::Length(2), // input email (1 texto + 1 borde inferior)
            Constraint::Length(1), // gap
            Constraint::Length(1), // label password
            Constraint::Length(2), // input password (1 texto + 1 borde inferior)
            Constraint::Length(1), // gap
            Constraint::Length(1), // botón
            Constraint::Length(1), // gap
            Constraint::Length(2), // error (2 filas por si es largo)
        ])
        .split(inner);

        // rows[0] — "Omar Robles"
        frame.render_widget(
            Paragraph::new("Omar Robles")
                .style(Style::default().fg(Color::DarkGray))
                .alignment(Alignment::Center),
            rows[0],
        );

        // rows[1] — separador
        frame.render_widget(
            Paragraph::new("─".repeat(inner.width as usize))
                .style(Style::default().fg(Color::DarkGray)),
            rows[1],
        );

        // rows[2] — label Email
        let email_label_style = if self.active_field == LoginField::Email {
            Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD)
        } else {
            Style::default().fg(Color::Gray)
        };
        frame.render_widget(
            Paragraph::new("Email:").style(email_label_style),
            rows[2],
        );

        // rows[3] — input Email (2 filas: texto arriba + borde abajo)
        let email_display = if self.active_field == LoginField::Email {
            format!("{}│", self.email)
        } else {
            self.email.clone()
        };
        let email_input = Paragraph::new(email_display)
            .style(Style::default().fg(Color::White))
            .block(
                Block::default()
                    .borders(Borders::BOTTOM)
                    .border_style(if self.active_field == LoginField::Email {
                        Style::default().fg(Color::Cyan)
                    } else {
                        Style::default().fg(Color::DarkGray)
                    }),
            );
        frame.render_widget(email_input, rows[3]);

        // rows[5] — label Password
        let pwd_label_style = if self.active_field == LoginField::Password {
            Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD)
        } else {
            Style::default().fg(Color::Gray)
        };
        frame.render_widget(
            Paragraph::new("Password:").style(pwd_label_style),
            rows[5],
        );

        // rows[6] — input Password (2 filas: texto arriba + borde abajo)
        let masked: String = if self.active_field == LoginField::Password {
            format!("{}│", "•".repeat(self.password.len()))
        } else {
            "•".repeat(self.password.len())
        };
        let pwd_input = Paragraph::new(masked)
            .style(Style::default().fg(Color::White))
            .block(
                Block::default()
                    .borders(Borders::BOTTOM)
                    .border_style(if self.active_field == LoginField::Password {
                        Style::default().fg(Color::Cyan)
                    } else {
                        Style::default().fg(Color::DarkGray)
                    }),
            );
        frame.render_widget(pwd_input, rows[6]);

        // rows[8] — botón / estado
        let btn = if self.submitting {
            Paragraph::new("  Autenticando...")
                .style(Style::default().fg(Color::Yellow))
                .alignment(Alignment::Center)
        } else {
            Paragraph::new("  [ Enter para iniciar sesión ]")
                .style(Style::default().fg(Color::Green))
                .alignment(Alignment::Center)
        };
        frame.render_widget(btn, rows[8]);

        // rows[10] — mensaje de error (2 filas)
        if let Some(err) = error {
            frame.render_widget(
                Paragraph::new(format!("⚠ {}", err))
                    .style(Style::default().fg(Color::Red))
                    .alignment(Alignment::Center),
                rows[10],
            );
        }
    }
}

/// Resultado de procesar un KeyEvent en la pantalla de login
#[derive(Debug)]
pub enum LoginAction {
    None,
    Submit { email: String, password: String },
    Quit,
}
