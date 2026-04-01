// OVD Platform — Dashboard de quota y uso (S14.B)
//
// Muestra el consumo de ciclos y tokens del período actual.
// Layout:
//   ┌──────────────────────────────────────────┐
//   │  Quota — org: omarrobles             │
//   ├──────────────────────────────────────────┤
//   │  Ciclos     [████████░░░░░░░] 8 / 20      │
//   │  Tokens     [████░░░░░░░░░░░] 45k / 200k  │
//   │                                            │
//   │  Período: 2026-03-01 → 2026-03-31         │
//   └──────────────────────────────────────────┘

use crossterm::event::{KeyCode, KeyEvent};
use ratatui::{
    Frame,
    layout::{Constraint, Layout, Margin},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Gauge, Paragraph},
};

use crate::models::quota::QuotaInfo;

pub struct QuotaScreen;

#[derive(Debug)]
pub enum QuotaAction {
    None,
    Back,
}

impl QuotaScreen {
    pub fn handle_key(key: KeyEvent) -> QuotaAction {
        match key.code {
            KeyCode::Char('q') | KeyCode::Esc => QuotaAction::Back,
            _ => QuotaAction::None,
        }
    }

    pub fn render(frame: &mut Frame, quota: Option<&QuotaInfo>, org_id: &str, loading: bool) {
        let area = frame.area();

        let chunks = Layout::vertical([
            Constraint::Length(3), // header
            Constraint::Fill(1),   // contenido
            Constraint::Length(2), // footer
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
                    " Quota y Uso ",
                    Style::default()
                        .fg(Color::White)
                        .add_modifier(Modifier::BOLD),
                )),
        );
        frame.render_widget(header, chunks[0]);

        // Contenido
        let body_block = Block::default()
            .borders(Borders::LEFT | Borders::RIGHT | Borders::BOTTOM)
            .border_style(Style::default().fg(Color::Cyan));
        frame.render_widget(body_block, chunks[1]);

        let inner = chunks[1].inner(Margin { horizontal: 2, vertical: 1 });

        if loading {
            frame.render_widget(
                Paragraph::new("  Cargando información de quota...")
                    .style(Style::default().fg(Color::Yellow)),
                inner,
            );
        } else if let Some(q) = quota {
            let rows = Layout::vertical([
                Constraint::Length(1), // label ciclos
                Constraint::Length(2), // barra ciclos
                Constraint::Length(1), // gap
                Constraint::Length(1), // label tokens
                Constraint::Length(2), // barra tokens
                Constraint::Length(1), // gap
                Constraint::Length(1), // período
            ])
            .split(inner);

            // Ciclos
            let cycles_color = if q.cycles_percent() >= 90.0 {
                Color::Red
            } else if q.cycles_percent() >= 70.0 {
                Color::Yellow
            } else {
                Color::Green
            };
            frame.render_widget(
                Paragraph::new(Line::from(vec![
                    Span::styled("Ciclos  ", Style::default().fg(Color::White).add_modifier(Modifier::BOLD)),
                    Span::styled(
                        format!("{} / {}", q.cycles_used, q.cycles_limit),
                        Style::default().fg(cycles_color),
                    ),
                ])),
                rows[0],
            );
            let cycles_gauge = Gauge::default()
                .block(Block::default())
                .gauge_style(Style::default().fg(cycles_color).bg(Color::DarkGray))
                .percent(q.cycles_percent() as u16)
                .label(format!("{:.0}%", q.cycles_percent()));
            frame.render_widget(cycles_gauge, rows[1]);

            // Tokens
            let tokens_color = if q.tokens_percent() >= 90.0 {
                Color::Red
            } else if q.tokens_percent() >= 70.0 {
                Color::Yellow
            } else {
                Color::Cyan
            };
            let fmt_tokens = |n: u64| -> String {
                if n >= 1_000_000 {
                    format!("{:.1}M", n as f64 / 1_000_000.0)
                } else if n >= 1_000 {
                    format!("{:.0}k", n as f64 / 1_000.0)
                } else {
                    n.to_string()
                }
            };
            frame.render_widget(
                Paragraph::new(Line::from(vec![
                    Span::styled("Tokens  ", Style::default().fg(Color::White).add_modifier(Modifier::BOLD)),
                    Span::styled(
                        format!("{} / {}", fmt_tokens(q.tokens_used), fmt_tokens(q.tokens_limit)),
                        Style::default().fg(tokens_color),
                    ),
                ])),
                rows[3],
            );
            let tokens_gauge = Gauge::default()
                .block(Block::default())
                .gauge_style(Style::default().fg(tokens_color).bg(Color::DarkGray))
                .percent(q.tokens_percent() as u16)
                .label(format!("{:.0}%", q.tokens_percent()));
            frame.render_widget(tokens_gauge, rows[4]);

            // Período
            let period = if !q.period_start.is_empty() && !q.period_end.is_empty() {
                let start = if q.period_start.len() >= 10 { &q.period_start[..10] } else { &q.period_start };
                let end   = if q.period_end.len()   >= 10 { &q.period_end[..10]   } else { &q.period_end   };
                format!("Período: {} → {}", start, end)
            } else {
                "Período: —".to_string()
            };
            frame.render_widget(
                Paragraph::new(period).style(Style::default().fg(Color::DarkGray)),
                rows[6],
            );
        } else {
            frame.render_widget(
                Paragraph::new("  No se pudo obtener información de quota.")
                    .style(Style::default().fg(Color::DarkGray)),
                inner,
            );
        }

        // Footer
        frame.render_widget(
            Paragraph::new(Line::from(vec![
                Span::styled("  [q]", Style::default().fg(Color::Cyan)),
                Span::styled(" volver al dashboard", Style::default().fg(Color::DarkGray)),
            ])),
            chunks[2],
        );
    }
}
