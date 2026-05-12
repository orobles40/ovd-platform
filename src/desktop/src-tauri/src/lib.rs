mod auth;
mod config;
pub mod db;
mod error;
mod state;
mod workspace;

use state::AppState;
use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info,ovd_desktop_lib=debug")),
        )
        .init();

    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.set_focus();
                let _ = window.unminimize();
            }
        }))
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_os::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(AppState::new())
        .invoke_handler(tauri::generate_handler![
            // Auth
            auth::auth_login,
            auth::auth_logout,
            auth::auth_is_authenticated,
            auth::auth_get_current_user,
            auth::auth_refresh_token,
            // Workspace
            workspace::workspace_pick_folder,
            workspace::workspace_read_context,
            workspace::workspace_write_artifacts,
            workspace::workspace_run_tests,
            workspace::workspace_open_folder,
            // Config
            config::config_get,
            config::config_save,
            // DB — historial SQLite (T3) + errores (T6)
            db::db_save_cycle,
            db::db_list_project_cycles,
            db::db_list_errors,
        ])
        .setup(|app| {
            auth::init_keyring();
            db::init_db();
            // Cargar engine_url guardada en SQLite al arrancar
            let state = app.state::<AppState>();
            config::init_from_db(&state);
            tracing::info!("OVD Platform Desktop iniciado");
            Ok(())
        })
        .on_window_event(|_window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                auth::shutdown_keyring();
            }
        })
        .run(tauri::generate_context!())
        .expect("error al iniciar OVD Platform Desktop");
}
