// OVD Platform — Historial de ciclos (S14.A)
//
// Lista los ciclos pasados del workspace activo.
// Layout:
//   ┌─────────────────────────────────────────────────────┐
//   │  Historial — workspace: Alemana CAS                  │
//   ├──────────────────────────────────────────────────────┤
//   │  > 2026-03-15  Agregar OAuth2 con Google    ✓ 0.92  │
//   │    2026-03-10  Refactor módulo reportes      ✓ 0.88  │
//   │    2026-03-01  Fix: timeout en validaciones  ✗ —     │
//   ├──────────────────────────────────────────────────────┤
//   │  [↑↓/jk] navegar  [q] volver                        │
//   └──────────────────────────────────────────────────────┘

use crossterm::event::{KeyCode, KeyEvent};
use ratatui::{
    Frame,
    layout::Constraint,
    layout::Layout,
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, List, ListItem, ListState, Paragraph},
};

use crate::models::session::CycleRecord;

pub struct HistoryScreen {
    pub list_state: ListState,
    pub loading: bool,
}

impl Default for HistoryScreen {
    fn default() -> Self {
        let mut list_state = ListState::default();
        list_state.select(Some(0));
        Self {
            list_state,
            loading: true,
        }
    }
}

#[derive(Debug)]
pub enum HistoryAction {
    None,
    Back,
}

impl HistoryScreen {
    pub fn handle_key(&mut self, key: KeyEvent, total: usize) -> HistoryAction {
        match key.code {
            KeyCode::Char('q') | KeyCode::Esc => HistoryAction::Back,
            KeyCode::Down | KeyCode::Char('j') if total > 0 => {
                let i = self.list_state.selected().unwrap_or(0);
                self.list_state.select(Some((i + 1).min(total - 1)));
                HistoryAction::None
            }
            KeyCode::Up | KeyCode::Char('k') if total > 0 => {
                let i = self.list_state.selected().unwrap_or(0);
                self.list_state.select(Some(i.saturating_sub(1)));
                HistoryAction::None
            }
            _ => HistoryAction::None,
        }
    }

    pub fn render(&mut self, frame: &mut Frame, cycles: &[CycleRecord], ws_name: &str) {
        let area = frame.area();

        let chunks = Layout::vertical([
            Constraint::Length(3), // header
            Constraint::Fill(1),   // lista
            Constraint::Length(2), // footer
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
                    " Historial de Ciclos ",
                    Style::default()
                        .fg(Color::White)
                        .add_modifier(Modifier::BOLD),
                )),
        );
        frame.render_widget(header, chunks[0]);

        // Lista
        let items: Vec<ListItem> = if self.loading {
            vec![ListItem::new("  Cargando historial...").style(Style::default().fg(Color::Yellow))]
        } else if cycles.is_empty() {
            vec![ListItem::new("  Sin ciclos previos en este workspace")
                .style(Style::default().fg(Color::DarkGray))]
        } else {
            cycles
                .iter()
                .map(|c| {
                    // fr_type como indicador de tipo (el engine no expone status del thread)
                    let fr_type = c.fr_type.as_deref().unwrap_or("cycle");
                    let (type_icon, type_style) = match fr_type {
                        "feature"     => ("✦", Style::default().fg(Color::Cyan)),
                        "maintenance" => ("⚙", Style::default().fg(Color::Blue)),
                        "bugfix"      => ("✗", Style::default().fg(Color::Red)),
                        _             => ("○", Style::default().fg(Color::DarkGray)),
                    };
                    // qa_score viene 0-100 desde el engine
                    let qa = c
                        .qa_score
                        .map(|s| if s > 1.0 { format!("{:.0}", s) } else { format!("{:.2}", s) })
                        .unwrap_or_else(|| "—".to_string());
                    // Truncar FR a 42 caracteres
                    let fr = if c.feature_request.len() > 42 {
                        format!("{}…", &c.feature_request[..41])
                    } else {
                        c.feature_request.clone()
                    };
                    let created = c.created_at.as_deref().unwrap_or("—");
                    // Usar solo los primeros 10 chars de la fecha (YYYY-MM-DD)
                    let date = if created.len() >= 10 { &created[..10] } else { created };

                    ListItem::new(Line::from(vec![
                        Span::styled(
                            format!("  {:<12}", date),
                            Style::default().fg(Color::DarkGray),
                        ),
                        Span::styled(
                            format!("{:<44}", fr),
                            Style::default().fg(Color::White),
                        ),
                        Span::styled(format!(" {} ", type_icon), type_style),
                        Span::styled(qa, Style::default().fg(Color::Cyan)),
                    ]))
                })
                .collect()
        };

        let list = List::new(items)
            .block(
                Block::default()
                    .borders(Borders::LEFT | Borders::RIGHT | Borders::BOTTOM)
                    .border_style(Style::default().fg(Color::Cyan)),
            )
            .highlight_style(Style::default().bg(Color::DarkGray).add_modifier(Modifier::BOLD))
            .highlight_symbol("> ");

        frame.render_stateful_widget(list, chunks[1], &mut self.list_state);

        // Footer
        let footer = Paragraph::new(Line::from(vec![
            Span::styled("  [↑↓/jk]", Style::default().fg(Color::Cyan)),
            Span::styled(" navegar  ", Style::default().fg(Color::DarkGray)),
            Span::styled("[q]", Style::default().fg(Color::Cyan)),
            Span::styled(" volver al dashboard", Style::default().fg(Color::DarkGray)),
        ]));
        frame.render_widget(footer, chunks[2]);
    }
}
