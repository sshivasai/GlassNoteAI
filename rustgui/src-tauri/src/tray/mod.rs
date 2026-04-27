use tauri::{
    AppHandle, Manager,
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
};
use tracing::{info, error};

pub fn setup(app: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    info!("Setting up system tray");

    // Create menu items
    let new_session = MenuItem::with_id(app, "new_session", "New Session", true, None::<&str>)?;
    let settings = MenuItem::with_id(app, "settings", "Settings", true, None::<&str>)?;
    let separator = MenuItem::with_id(app, "separator", "---", false, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;

    // Create menu
    let menu = Menu::with_items(
        app,
        &[
            &new_session,
            &settings,
            &separator,
            &quit,
        ],
    )?;

    // Build tray icon
    let _tray = TrayIconBuilder::new()
        .tooltip("GlassNote - AI Interview Assistant")
        .icon(app.default_window_icon().unwrap().clone())
        .menu(&menu)
        .menu_on_left_click(false)
        .on_menu_event(move |app, event| match event.id().as_ref() {
            "new_session" => {
                info!("Tray: New Session clicked");
                if let Err(e) = app.emit("tray-new-session", ()) {
                    error!("Failed to emit tray event: {}", e);
                }
            }
            "settings" => {
                info!("Tray: Settings clicked");
                if let Err(e) = app.emit("tray-settings", ()) {
                    error!("Failed to emit tray event: {}", e);
                }
            }
            "quit" => {
                info!("Tray: Quit clicked");
                app.exit(0);
            }
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            match event {
                TrayIconEvent::Click {
                    button: MouseButton::Left,
                    button_state: MouseButtonState::Up,
                    ..
                } => {
                    info!("Tray icon clicked");
                    let app = tray.app_handle();
                    if let Err(e) = app.emit("tray-clicked", ()) {
                        error!("Failed to emit tray click event: {}", e);
                    }
                }
                TrayIconEvent::DoubleClick {
                    button: MouseButton::Left,
                    ..
                } => {
                    info!("Tray icon double-clicked");
                    let app = tray.app_handle();
                    if let Err(e) = app.emit("tray-double-clicked", ()) {
                        error!("Failed to emit tray double-click event: {}", e);
                    }
                }
                _ => {}
            }
        })
        .build(app)?;

    info!("System tray setup complete");
    Ok(())
}
