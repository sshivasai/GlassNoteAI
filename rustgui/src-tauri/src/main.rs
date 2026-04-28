// Prevents additional console window on Windows in release builds
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod audio;
mod capture;
mod hotkeys;
mod llm;
mod session;
mod tray;
mod utils;

use std::sync::Arc;
use parking_lot::RwLock;
use tauri::{Manager, State, Window};
use tracing::{info, error};

#[derive(Default)]
struct AppState {
    session: Arc<RwLock<Option<session::Session>>>,
    llm_client: Arc<llm::LLMClient>,
    audio_pipeline: Arc<audio::AudioPipeline>,
    capture_queue: Arc<capture::CaptureQueue>,
    hotkey_manager: Arc<hotkeys::HotkeyManager>,
}

#[tauri::command]
async fn check_crash_recovery() -> Result<Option<utils::crash_recovery::SessionState>, String> {
    info!("Checking for crash recovery state");

    match utils::load_session_state() {
        Ok(state) => {
            if state.is_some() {
                info!("Crash recovery state found");
            }
            Ok(state)
        }
        Err(e) => {
            error!("Failed to load crash recovery state: {}", e);
            Ok(None)
        }
    }
}

#[tauri::command]
async fn start_session(
    session_data: session::SessionData,
    state: State<'_, AppState>,
) -> Result<String, String> {
    info!("Starting session: {}", session_data.company);

    let session = session::Session::new(session_data.clone());
    let session_id = session.id.clone();

    // Save crash recovery state
    let crash_state = utils::crash_recovery::SessionState {
        session_id: session_id.clone(),
        company: session_data.company,
        job_description: session_data.job_description,
        resume_text: session_data.resume_text,
        timestamp: chrono::Utc::now().timestamp(),
    };

    if let Err(e) = utils::save_session_state(&crash_state) {
        error!("Failed to save crash recovery state: {}", e);
    }

    *state.session.write() = Some(session);

    // Pre-warm connections
    if let Err(e) = state.llm_client.warm_connections().await {
        error!("Connection warm-up failed (non-fatal): {}", e);
    }

    Ok(session_id)
}

#[tauri::command]
async fn end_session(state: State<'_, AppState>) -> Result<(), String> {
    info!("Ending session");

    state.audio_pipeline.stop().await.map_err(|e| e.to_string())?;
    state.hotkey_manager.unregister_all();
    state.capture_queue.clear();

    *state.session.write() = None;

    // Clear crash recovery state
    if let Err(e) = utils::clear_session_state() {
        error!("Failed to clear crash recovery state: {}", e);
    }

    Ok(())
}

#[tauri::command]
async fn capture_screen(state: State<'_, AppState>) -> Result<String, String> {
    let screenshot = capture::capture_fullscreen()
        .await
        .map_err(|e| e.to_string())?;

    state.capture_queue.add(screenshot.clone());

    Ok(screenshot)
}

#[tauri::command]
async fn solve(
    state: State<'_, AppState>,
    window: Window,
) -> Result<(), String> {
    let screenshots = state.capture_queue.pop_all();
    if screenshots.is_empty() {
        return Err("No screenshots queued".to_string());
    }

    let session_guard = state.session.read();
    let session = session_guard
        .as_ref()
        .ok_or("No active session")?;

    let system_prompt = session.build_system_prompt();

    info!("Dispatching solve with {} screenshots", screenshots.len());

    let llm_client = state.llm_client.clone();

    tauri::async_runtime::spawn(async move {
        match llm_client
            .stream_solve(
                system_prompt,
                screenshots,
                |token| {
                    let _ = window.emit("llm-token", token);
                },
            )
            .await
        {
            Ok(full_response) => {
                let _ = window.emit("llm-done", full_response);
            }
            Err(e) => {
                error!("LLM error: {}", e);
                let _ = window.emit("llm-error", e.to_string());
            }
        }
    });

    Ok(())
}

#[tauri::command]
async fn analyze(
    state: State<'_, AppState>,
    window: Window,
) -> Result<(), String> {
    let screenshot = capture::capture_fullscreen()
        .await
        .map_err(|e| e.to_string())?;

    let session_guard = state.session.read();
    let session = session_guard
        .as_ref()
        .ok_or("No active session")?;

    let system_prompt = session.build_analyze_prompt();

    info!("Dispatching analyze");

    let llm_client = state.llm_client.clone();

    tauri::async_runtime::spawn(async move {
        match llm_client
            .stream_solve(
                system_prompt,
                vec![screenshot],
                |token| {
                    let _ = window.emit("llm-token", token);
                },
            )
            .await
        {
            Ok(full_response) => {
                let _ = window.emit("llm-done", full_response);
            }
            Err(e) => {
                error!("LLM error: {}", e);
                let _ = window.emit("llm-error", e.to_string());
            }
        }
    });

    Ok(())
}

#[tauri::command]
async fn start_interview(
    state: State<'_, AppState>,
    window: Window,
) -> Result<(), String> {
    info!("Starting interview mode");

    let audio_pipeline = state.audio_pipeline.clone();
    let llm_client = state.llm_client.clone();
    let session = state.session.clone();

    audio_pipeline
        .start(move |transcript| {
            let window_clone = window.clone();
            let llm_client_clone = llm_client.clone();
            let session_clone = session.clone();

            tauri::async_runtime::spawn(async move {
                let _ = window_clone.emit("transcript", &transcript);

                let session_guard = session_clone.read();
                if let Some(sess) = session_guard.as_ref() {
                    let system_prompt = sess.build_interview_prompt();

                    match llm_client_clone
                        .stream_interview(
                            system_prompt,
                            transcript,
                            |token| {
                                let _ = window_clone.emit("llm-token", token);
                            },
                        )
                        .await
                    {
                        Ok(full_response) => {
                            let _ = window_clone.emit("llm-done", full_response);
                        }
                        Err(e) => {
                            error!("LLM error: {}", e);
                            let _ = window_clone.emit("llm-error", e.to_string());
                        }
                    }
                }
            });
        })
        .await
        .map_err(|e| e.to_string())?;

    Ok(())
}

#[tauri::command]
async fn stop_interview(state: State<'_, AppState>) -> Result<(), String> {
    info!("Stopping interview mode");
    state.audio_pipeline.stop().await.map_err(|e| e.to_string())
}

#[tauri::command]
async fn load_config() -> Result<utils::Config, String> {
    utils::Config::load().map_err(|e| e.to_string())
}

#[tauri::command]
async fn save_config(config: utils::Config) -> Result<(), String> {
    config.save().map_err(|e| e.to_string())
}

#[tauri::command]
async fn get_queue_count(state: State<'_, AppState>) -> Result<usize, String> {
    Ok(state.capture_queue.len())
}

fn main() {
    // Initialize logger first
    utils::init_logger();

    info!("=== Starting GlassNote Rust GUI ===");
    info!("Version: {}", env!("CARGO_PKG_VERSION"));
    info!("Platform: {}", std::env::consts::OS);

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_notification::init())
        .setup(|app| {
            let state = AppState::default();

            // Initialize hotkey manager
            if let Err(e) = state.hotkey_manager.init(app.handle().clone()) {
                error!("Failed to initialize hotkey manager: {}", e);
            }

            app.manage(state);

            // Setup system tray
            if let Err(e) = tray::setup(app.handle()) {
                error!("Failed to setup system tray: {}", e);
            }

            // Setup event listeners for hotkeys
            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                setup_hotkey_listeners(app_handle);
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            check_crash_recovery,
            start_session,
            end_session,
            capture_screen,
            solve,
            analyze,
            start_interview,
            stop_interview,
            load_config,
            save_config,
            get_queue_count,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

fn setup_hotkey_listeners(app: AppHandle) {
    let window = app.get_webview_window("main");

    if let Some(win) = window {
        // Listen for hotkey events and forward to frontend
        let win_capture = win.clone();
        app.listen("hotkey-capture", move |_| {
            let _ = win_capture.emit("hotkey-triggered", "capture");
        });

        let win_solve = win.clone();
        app.listen("hotkey-solve", move |_| {
            let _ = win_solve.emit("hotkey-triggered", "solve");
        });

        let win_analyze = win.clone();
        app.listen("hotkey-analyze", move |_| {
            let _ = win_analyze.emit("hotkey-triggered", "analyze");
        });

        let win_interview = win.clone();
        app.listen("hotkey-interview", move |_| {
            let _ = win_interview.emit("hotkey-triggered", "interview");
        });

        let win_overlay = win.clone();
        app.listen("hotkey-toggle_overlay", move |_| {
            let _ = win_overlay.emit("hotkey-triggered", "toggle_overlay");
        });

        let win_end = win.clone();
        app.listen("hotkey-end_session", move |_| {
            let _ = win_end.emit("hotkey-triggered", "end_session");
        });
    }
}
