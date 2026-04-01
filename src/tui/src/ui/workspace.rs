// OVD Platform — Selector de Workspace (S12.E)
//
// Layout:
//   ┌──────────────────────────────────────────────┐
//   │  Seleccionar Workspace                       │
//   │  org: Omar Robles                        │
//   ├──────────────────────────────────────────────┤
//   │  > Alemana CAS    Oracle 12c   /srv/cas      │
//   │    Alemana CAT    Oracle 19c   /srv/cat      │
//   │    Cliente XYZ    Python/PG    /srv/xyz      │
//   ├──────────────────────────────────────────────┤
//   │  [↑↓] Navegar  [Enter] Seleccionar  [q] Salir│
//   └──────────────────────────────────────────────┘

use crossterm::event::{KeyCode, KeyEvent};
use ratatui::{
    Frame,
    layout::{Constraint, Direction, Layout},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, List, ListItem, ListState, Paragraph},
};

use crate::models::workspace::Workspace;

pub struct WorkspaceScreen {
    pub list_state: ListState,
    pub loading: bool,
}

impl Default for WorkspaceScreen {
    fn default() -> Self {
        let mut list_state = ListState::default();
        list_state.select(Some(0));
        Self {
            list_state,
            loading: true,
        }
    }
}

/// Acción resultante de un KeyEvent en el selector
#[derive(Debug)]
pub enum WorkspaceAction {
    None,
    Select(usize),
    Quit,
    Logout,
}

impl WorkspaceScreen {
    pub fn handle_key(&mut self, key: KeyEvent, total: usize) -> WorkspaceAction {
        if total == 0 {
            return match key.code {
                KeyCode::Char('q') | KeyCode::Esc => WorkspaceAction::Quit,
                _ => WorkspaceAction::None,
            };
        }

        match key.code {
            KeyCode::Down | KeyCode::Char('j') => {
                let i = self.list_state.selected().unwrap_or(0);
                self.list_state.select(Some((i + 1).min(total - 1)));
                WorkspaceAction::None
            }
            KeyCode::Up | KeyCode::Char('k') => {
                let i = self.list_state.selected().unwrap_or(0);
                self.list_state.select(Some(i.saturating_sub(1)));
                WorkspaceAction::None
            }
            KeyCode::Enter => {
                let i = self.list_state.selected().unwrap_or(0);
                WorkspaceAction::Select(i)
            }
            KeyCode::Char('q') | KeyCode::Esc => WorkspaceAction::Quit,
            KeyCode::Char('L') => WorkspaceAction::Logout, // Shift+L → logout
            _ => WorkspaceAction::None,
        }
    }

    pub fn render(&mut self, frame: &mut Frame, workspaces: &[Workspace], org_id: &str) {
        let area = frame.area();

        let chunks = Layout::vertical([
            Constraint::Length(3), // header
            Constraint::Fill(1),   // lista
            Constraint::Length(2), // footer con atajos
        ])
        .split(area);

        // Header
        let header = Paragraph::new(Line::from(vec![
            Span::styled("  org: ", Style::default().fg(Color::DarkGray)),
            Span::styled(org_id, Style::default().fg(Color::Cyan)),
        ]))
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(Style::default().fg(Color::Cyan))
                .title(Span::styled(
                    " Seleccionar Workspace ",
                    Style::default()
                        .fg(Color::White)
                        .add_modifier(Modifier::BOLD),
                )),
        );
        frame.render_widget(header, chunks[0]);

        // Lista de workspaces
        let items: Vec<ListItem> = if self.loading {
            vec![ListItem::new("  Cargando workspaces...").style(Style::default().fg(Color::Yellow))]
        } else if workspaces.is_empty() {
            vec![ListItem::new("  Sin workspaces activos en esta org").style(Style::default().fg(Color::DarkGray))]
        } else {
            workspaces
                .iter()
                .map(|w| {
                    let desc = w.description.as_deref().unwrap_or("-");
                    let line = Line::from(vec![
                        Span::styled(
                            format!("  {:<25}", w.name),
                            Style::default().fg(Color::White).add_modifier(Modifier::BOLD),
                        ),
                        Span::styled(
                            format!("{:<20}", desc),
                            Style::default().fg(Color::DarkGray),
                        ),
                        Span::styled(
                            // Mostrar solo los últimos 30 chars del path para evitar overflow
                            if w.directory.len() > 30 {
                                format!("…{}", &w.directory[w.directory.len()-29..])
                            } else {
                                w.directory.clone()
                            },
                            Style::default().fg(Color::Blue),
                        ),
                    ]);
                    ListItem::new(line)
                })
                .collect()
        };

        let list = List::new(items)
            .block(
                Block::default()
                    .borders(Borders::LEFT | Borders::RIGHT | Borders::BOTTOM)
                    .border_style(Style::default().fg(Color::Cyan)),
            )
            .highlight_style(
                Style::default()
                    .fg(Color::Black)
                    .bg(Color::Cyan)
                    .add_modifier(Modifier::BOLD),
            )
            .highlight_symbol("> ");

        frame.render_stateful_widget(list, chunks[1], &mut self.list_state);

        // Footer con atajos de teclado
        let footer = Paragraph::new(Line::from(vec![
            Span::styled("  [↑↓/jk]", Style::default().fg(Color::Cyan)),
            Span::styled(" navegar  ", Style::default().fg(Color::DarkGray)),
            Span::styled("[Enter]", Style::default().fg(Color::Cyan)),
            Span::styled(" seleccionar  ", Style::default().fg(Color::DarkGray)),
            Span::styled("[Shift+L]", Style::default().fg(Color::Cyan)),
            Span::styled(" logout  ", Style::default().fg(Color::DarkGray)),
            Span::styled("[q]", Style::default().fg(Color::Cyan)),
            Span::styled(" salir", Style::default().fg(Color::DarkGray)),
        ]));
        frame.render_widget(footer, chunks[2]);
    }
}
