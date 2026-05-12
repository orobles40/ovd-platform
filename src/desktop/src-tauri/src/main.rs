// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    // T6: captura panics y los persiste en SQLite antes de que el proceso muera
    std::panic::set_hook(Box::new(|info| {
        let msg = info.to_string();
        let location = info
            .location()
            .map(|l| format!("{}:{}:{}", l.file(), l.line(), l.column()))
            .unwrap_or_default();
        ovd_desktop_lib::db::log_error("panic", &msg, &location);
    }));

    ovd_desktop_lib::run();
}
