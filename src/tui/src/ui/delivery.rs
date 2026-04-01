// OVD Platform — Pantalla de Entrega de Artefactos (S16T.D)
//
// Muestra el informe del ciclo completado:
//   Tab 1 — Resumen: scores, tokens, duración, directorio
//   Tab 2 — Archivos: lista de archivos escritos por agente
//
// Teclas:
//   [Tab]   — cambiar de tab
//   [q]/Esc — volver al stream
//   [o]     — abrir directorio en el explorador del OS

use crossterm::event::{KeyCode, KeyEvent};
use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, List, ListItem, Paragraph, Wrap},
    Frame,
};

use crate::models::session::{DeliveryReport, Deliverable, DeliveryScore, DeliveryQa};

#[derive(Debug, Clone, PartialEq)]
pub enum DeliveryTab {
    Summary,
    Files,
}

pub struct DeliveryScreen {
    pub report: Option<DeliveryReport>,
    pub tab: DeliveryTab,
    pub scroll: u16,
    pub loading: bool,
}

pub enum DeliveryAction {
    Back,
    OpenDirectory,
    ExportReport,
    NewSession,
    None,
}

impl Default for DeliveryScreen {
    fn default() -> Self {
        Self {
            report: None,
            tab: DeliveryTab::Summary,
            scroll: 0,
            loading: false,
        }
    }
}

impl DeliveryScreen {
    pub fn handle_key(&mut self, key: KeyEvent) -> DeliveryAction {
        match key.code {
            KeyCode::Tab => {
                self.tab = match self.tab {
                    DeliveryTab::Summary => DeliveryTab::Files,
                    DeliveryTab::Files   => DeliveryTab::Summary,
                };
                self.scroll = 0;
                DeliveryAction::None
            }
            KeyCode::Char('q') | KeyCode::Esc => DeliveryAction::Back,
            KeyCode::Char('o') | KeyCode::Char('O') => DeliveryAction::OpenDirectory,
            KeyCode::Char('e') | KeyCode::Char('E') => DeliveryAction::ExportReport,
            KeyCode::Char('n') | KeyCode::Char('N') => DeliveryAction::NewSession,
            KeyCode::Down | KeyCode::Char('j') => {
                self.scroll = self.scroll.saturating_add(1);
                DeliveryAction::None
            }
            KeyCode::Up | KeyCode::Char('k') => {
                self.scroll = self.scroll.saturating_sub(1);
                DeliveryAction::None
            }
            _ => DeliveryAction::None,
        }
    }

    pub fn render(&self, f: &mut Frame, area: Rect) {
        let chunks = Layout::default()
            .direction(Direction::Vertical)
            .constraints([
                Constraint::Length(3), // header
                Constraint::Min(1),    // contenido
                Constraint::Length(3), // footer
            ])
            .split(area);

        self.render_header(f, chunks[0]);

        if self.loading {
            let p = Paragraph::new("  Cargando entrega...")
                .style(Style::default().fg(Color::Yellow))
                .block(Block::default().borders(Borders::ALL));
            f.render_widget(p, chunks[1]);
        } else if let Some(report) = &self.report {
            match self.tab {
                DeliveryTab::Summary => self.render_summary(f, chunks[1], report),
                DeliveryTab::Files   => self.render_files(f, chunks[1], report),
            }
        } else {
            let p = Paragraph::new("  Sin datos de entrega disponibles.")
                .style(Style::default().fg(Color::DarkGray))
                .block(Block::default().borders(Borders::ALL));
            f.render_widget(p, chunks[1]);
        }

        self.render_footer(f, chunks[2]);
    }

    fn render_header(&self, f: &mut Frame, area: Rect) {
        let tab_summary = if self.tab == DeliveryTab::Summary {
            Span::styled(" Resumen ", Style::default().fg(Color::Black).bg(Color::Cyan).add_modifier(Modifier::BOLD))
        } else {
            Span::styled(" Resumen ", Style::default().fg(Color::DarkGray))
        };
        let tab_files = if self.tab == DeliveryTab::Files {
            Span::styled(" Archivos ", Style::default().fg(Color::Black).bg(Color::Green).add_modifier(Modifier::BOLD))
        } else {
            Span::styled(" Archivos ", Style::default().fg(Color::DarkGray))
        };

        let title = Line::from(vec![
            Span::raw(" "),
            tab_summary,
            Span::raw("  "),
            tab_files,
        ]);

        let header = Paragraph::new(title)
            .block(
                Block::default()
                    .title(" Entrega del Ciclo ")
                    .title_style(Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD))
                    .borders(Borders::ALL)
                    .border_style(Style::default().fg(Color::Cyan)),
            );
        f.render_widget(header, area);
    }

    fn render_summary(&self, f: &mut Frame, area: Rect, report: &DeliveryReport) {
        let sec_score = report.security.score.as_ref()
            .and_then(|v| v.as_f64())
            .map(|s| format!("{}/100", s))
            .unwrap_or_else(|| "?".to_string());
        let qa_score = report.qa.score.as_ref()
            .and_then(|v| v.as_f64())
            .map(|s| format!("{}/100", s))
            .unwrap_or_else(|| "?".to_string());

        let elapsed_min = (report.elapsed_secs / 60.0) as u64;
        let elapsed_sec = (report.elapsed_secs % 60.0) as u64;

        let total_files: usize = report.deliverables.iter()
            .filter(|d| d.kind == "implementation")
            .map(|d| d.artifacts.len())
            .sum();

        let dir_display = if report.directory.is_empty() {
            "_(no configurado)_".to_string()
        } else {
            report.directory.clone()
        };

        let lines = vec![
            Line::from(""),
            Line::from(vec![
                Span::styled("  Estado:        ", Style::default().fg(Color::DarkGray)),
                Span::styled(&report.status, Style::default().fg(Color::Green).add_modifier(Modifier::BOLD)),
            ]),
            Line::from(vec![
                Span::styled("  Directorio:    ", Style::default().fg(Color::DarkGray)),
                Span::styled(dir_display, Style::default().fg(Color::White)),
            ]),
            Line::from(""),
            Line::from(vec![
                Span::styled("  Security:      ", Style::default().fg(Color::DarkGray)),
                Span::styled(
                    format!("{} {}", sec_score, if report.security.passed { "✓ Passed" } else { "✗ Failed" }),
                    Style::default().fg(if report.security.passed { Color::Green } else { Color::Red }),
                ),
            ]),
            Line::from(vec![
                Span::styled("  QA Score:      ", Style::default().fg(Color::DarkGray)),
                Span::styled(
                    format!("{} {}", qa_score, if report.qa.passed { "✓ Passed" } else { "✗ Failed" }),
                    Style::default().fg(if report.qa.passed { Color::Green } else { Color::Red }),
                ),
            ]),
            Line::from(vec![
                Span::styled("  SDD Compliance:", Style::default().fg(Color::DarkGray)),
                Span::styled(
                    if report.qa.sdd_compliance { " ✓ True" } else { " ✗ False" },
                    Style::default().fg(if report.qa.sdd_compliance { Color::Green } else { Color::Red }),
                ),
            ]),
            Line::from(vec![
                Span::styled("  Issues QA:     ", Style::default().fg(Color::DarkGray)),
                Span::styled(format!(" {} issue(s)", report.qa.issues.len()), Style::default().fg(Color::White)),
            ]),
            Line::from(""),
            Line::from(vec![
                Span::styled("  Tokens:        ", Style::default().fg(Color::DarkGray)),
                Span::styled(
                    format!("{} entrada / {} salida", report.tokens_in, report.tokens_out),
                    Style::default().fg(Color::White),
                ),
            ]),
            Line::from(vec![
                Span::styled("  Duración:      ", Style::default().fg(Color::DarkGray)),
                Span::styled(format!(" {}m {}s", elapsed_min, elapsed_sec), Style::default().fg(Color::White)),
            ]),
            Line::from(""),
            if total_files == 0 {
                Line::from(vec![
                    Span::styled("  Archivos:      ", Style::default().fg(Color::DarkGray)),
                    Span::styled(
                        " Sin artefactos generados  →  [n] nueva sesión",
                        Style::default().fg(Color::Yellow),
                    ),
                ])
            } else {
                Line::from(vec![
                    Span::styled("  Archivos:      ", Style::default().fg(Color::DarkGray)),
                    Span::styled(
                        format!(" {} archivo(s) generado(s) → [Tab] para ver lista", total_files),
                        Style::default().fg(Color::Cyan),
                    ),
                ])
            },
        ];

        let p = Paragraph::new(lines)
            .wrap(Wrap { trim: false })
            .scroll((self.scroll, 0))
            .block(Block::default().borders(Borders::ALL).border_style(Style::default().fg(Color::DarkGray)));
        f.render_widget(p, area);
    }

    fn render_files(&self, f: &mut Frame, area: Rect, report: &DeliveryReport) {
        let mut items: Vec<ListItem> = Vec::new();

        for d in &report.deliverables {
            if d.kind == "implementation" {
                items.push(ListItem::new(Line::from(vec![
                    Span::styled(
                        format!("  [{}]", d.agent.to_uppercase()),
                        Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD),
                    ),
                ])));

                if d.artifacts.is_empty() {
                    items.push(ListItem::new(Line::from(
                        Span::styled("    (sin archivos detectados)", Style::default().fg(Color::DarkGray)),
                    )));
                } else {
                    for f_item in &d.artifacts {
                        let size_kb = if f_item.size > 1024 {
                            format!("{:.1} KB", f_item.size as f64 / 1024.0)
                        } else {
                            format!("{} B", f_item.size)
                        };
                        items.push(ListItem::new(Line::from(vec![
                            Span::styled("    ", Style::default()),
                            Span::styled(&f_item.path, Style::default().fg(Color::White)),
                            Span::styled(format!("  ({})", size_kb), Style::default().fg(Color::DarkGray)),
                        ])));
                    }
                }
                items.push(ListItem::new(Line::from("")));
            } else if d.kind == "report" && !d.path.is_empty() {
                items.push(ListItem::new(Line::from(vec![
                    Span::styled("  [INFORME] ", Style::default().fg(Color::Yellow).add_modifier(Modifier::BOLD)),
                    Span::styled(&d.path, Style::default().fg(Color::White)),
                ])));
                items.push(ListItem::new(Line::from("")));
            }
        }

        if items.is_empty() {
            items.push(ListItem::new(Line::from(
                Span::styled("  Sin artefactos registrados.", Style::default().fg(Color::DarkGray)),
            )));
            items.push(ListItem::new(Line::from("")));
            items.push(ListItem::new(Line::from(vec![
                Span::styled("  Posibles causas:", Style::default().fg(Color::Yellow)),
            ])));
            items.push(ListItem::new(Line::from(vec![
                Span::styled(
                    "    • Ningún agente de implementación fue asignado en el SDD.",
                    Style::default().fg(Color::DarkGray),
                ),
            ])));
            items.push(ListItem::new(Line::from(vec![
                Span::styled(
                    "    • Los agentes encontraron errores — revisa el log del stream.",
                    Style::default().fg(Color::DarkGray),
                ),
            ])));
            items.push(ListItem::new(Line::from("")));
            items.push(ListItem::new(Line::from(vec![
                Span::styled("  [n] ", Style::default().fg(Color::Green).add_modifier(Modifier::BOLD)),
                Span::styled("Iniciar nueva sesión", Style::default().fg(Color::White)),
            ])));
        }

        let list = List::new(items)
            .block(Block::default().borders(Borders::ALL).border_style(Style::default().fg(Color::DarkGray)));
        f.render_widget(list, area);
    }

    fn render_footer(&self, f: &mut Frame, area: Rect) {
        let footer = Paragraph::new(Line::from(vec![
            Span::styled(" [Tab] ", Style::default().fg(Color::Cyan)),
            Span::raw("cambiar tab  "),
            Span::styled("[o] ", Style::default().fg(Color::Green)),
            Span::raw("abrir dir  "),
            Span::styled("[e] ", Style::default().fg(Color::Green)),
            Span::raw("exportar informe  "),
            Span::styled("[n] ", Style::default().fg(Color::Green)),
            Span::raw("nueva sesión  "),
            Span::styled("[↑↓/jk] ", Style::default().fg(Color::DarkGray)),
            Span::raw("scroll  "),
            Span::styled("[q] ", Style::default().fg(Color::Yellow)),
            Span::raw("volver"),
        ]))
        .block(Block::default().borders(Borders::ALL).border_style(Style::default().fg(Color::DarkGray)));
        f.render_widget(footer, area);
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crossterm::event::{KeyCode, KeyEvent, KeyModifiers};

    fn make_key(code: KeyCode) -> KeyEvent {
        KeyEvent::new(code, KeyModifiers::NONE)
    }

    fn make_report() -> DeliveryReport {
        DeliveryReport {
            status: "done".to_string(),
            directory: "/tmp/workspace".to_string(),
            deliverables: vec![
                Deliverable {
                    kind: "report".to_string(),
                    agent: "ovd".to_string(),
                    path: "ovd-delivery-abc12345-1743000000.md".to_string(),
                    artifacts: vec![],
                },
                Deliverable {
                    kind: "implementation".to_string(),
                    agent: "backend".to_string(),
                    path: String::new(),
                    artifacts: vec![],
                },
            ],
            security: DeliveryScore { score: None, passed: true, severity: String::new() },
            qa: DeliveryQa { score: None, passed: true, sdd_compliance: true, issues: vec![] },
            tokens_in: 1000,
            tokens_out: 500,
            elapsed_secs: 120.0,
        }
    }

    #[test]
    fn tab_alterna_entre_summary_y_files() {
        let mut screen = DeliveryScreen::default();
        assert_eq!(screen.tab, DeliveryTab::Summary);
        screen.handle_key(make_key(KeyCode::Tab));
        assert_eq!(screen.tab, DeliveryTab::Files);
        screen.handle_key(make_key(KeyCode::Tab));
        assert_eq!(screen.tab, DeliveryTab::Summary);
    }

    #[test]
    fn tab_resetea_scroll() {
        let mut screen = DeliveryScreen::default();
        screen.scroll = 10;
        screen.handle_key(make_key(KeyCode::Tab));
        assert_eq!(screen.scroll, 0);
    }

    #[test]
    fn q_retorna_back() {
        let mut screen = DeliveryScreen::default();
        assert!(matches!(screen.handle_key(make_key(KeyCode::Char('q'))), DeliveryAction::Back));
        assert!(matches!(screen.handle_key(make_key(KeyCode::Esc)), DeliveryAction::Back));
    }

    #[test]
    fn o_retorna_open_directory() {
        let mut screen = DeliveryScreen::default();
        assert!(matches!(screen.handle_key(make_key(KeyCode::Char('o'))), DeliveryAction::OpenDirectory));
        assert!(matches!(screen.handle_key(make_key(KeyCode::Char('O'))), DeliveryAction::OpenDirectory));
    }

    #[test]
    fn e_retorna_export_report() {
        let mut screen = DeliveryScreen::default();
        assert!(matches!(screen.handle_key(make_key(KeyCode::Char('e'))), DeliveryAction::ExportReport));
        assert!(matches!(screen.handle_key(make_key(KeyCode::Char('E'))), DeliveryAction::ExportReport));
    }

    #[test]
    fn n_retorna_new_session() {
        let mut screen = DeliveryScreen::default();
        assert!(matches!(screen.handle_key(make_key(KeyCode::Char('n'))), DeliveryAction::NewSession));
        assert!(matches!(screen.handle_key(make_key(KeyCode::Char('N'))), DeliveryAction::NewSession));
    }

    #[test]
    fn scroll_down_incrementa() {
        let mut screen = DeliveryScreen::default();
        screen.handle_key(make_key(KeyCode::Down));
        assert_eq!(screen.scroll, 1);
        screen.handle_key(make_key(KeyCode::Char('j')));
        assert_eq!(screen.scroll, 2);
    }

    #[test]
    fn scroll_up_no_hace_underflow() {
        let mut screen = DeliveryScreen::default();
        screen.scroll = 0;
        screen.handle_key(make_key(KeyCode::Up));
        assert_eq!(screen.scroll, 0); // saturating_sub no va por debajo de 0
    }

    #[test]
    fn export_report_path_con_report_deliverable() {
        let report = make_report();
        // Verificar que existe un deliverable kind=report con path no vacío
        let report_deliv = report.deliverables.iter()
            .find(|d| d.kind == "report" && !d.path.is_empty());
        assert!(report_deliv.is_some());
        let path = format!("{}/{}", report.directory.trim_end_matches('/'), report_deliv.unwrap().path);
        assert_eq!(path, "/tmp/workspace/ovd-delivery-abc12345-1743000000.md");
    }

    #[test]
    fn export_report_sin_report_deliverable_no_falla() {
        let report = DeliveryReport {
            status: "done".to_string(),
            directory: "/tmp/ws".to_string(),
            deliverables: vec![],
            security: DeliveryScore { score: None, passed: true, severity: String::new() },
            qa: DeliveryQa { score: None, passed: true, sdd_compliance: true, issues: vec![] },
            tokens_in: 0, tokens_out: 0, elapsed_secs: 0.0,
        };
        // Simular la lógica del handler: find + map
        let path = report.deliverables.iter()
            .find(|d| d.kind == "report" && !d.path.is_empty())
            .map(|d| format!("{}/{}", report.directory.trim_end_matches('/'), d.path));
        assert!(path.is_none()); // Sin report deliverable, no se abre nada
    }
}
