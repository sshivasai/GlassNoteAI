use anyhow::Result;
use global_hotkey::{
    hotkey::{Code, HotKey, Modifiers},
    GlobalHotKeyEvent, GlobalHotKeyManager,
};
use parking_lot::RwLock;
use std::collections::HashMap;
use std::sync::Arc;
use tauri::{AppHandle, Manager};
use tracing::{info, error};

pub struct HotkeyManager {
    manager: Arc<RwLock<Option<GlobalHotKeyManager>>>,
    registered: Arc<RwLock<HashMap<String, HotKey>>>,
    app: Arc<RwLock<Option<AppHandle>>>,
}

impl Default for HotkeyManager {
    fn default() -> Self {
        Self::new()
    }
}

impl HotkeyManager {
    pub fn new() -> Self {
        Self {
            manager: Arc::new(RwLock::new(None)),
            registered: Arc::new(RwLock::new(HashMap::new())),
            app: Arc::new(RwLock::new(None)),
        }
    }

    pub fn init(&self, app: AppHandle) -> Result<()> {
        let manager = GlobalHotKeyManager::new()
            .map_err(|e| anyhow::anyhow!("Failed to create hotkey manager: {}", e))?;

        *self.manager.write() = Some(manager);
        *self.app.write() = Some(app);

        self.register_default_hotkeys()?;
        self.start_event_listener();

        info!("Hotkey manager initialized");
        Ok(())
    }

    fn register_default_hotkeys(&self) -> Result<()> {
        // Ctrl+Shift+C - Capture
        self.register(
            "capture",
            Modifiers::CONTROL | Modifiers::SHIFT,
            Code::KeyC,
        )?;

        // Ctrl+Shift+S - Solve
        self.register(
            "solve",
            Modifiers::CONTROL | Modifiers::SHIFT,
            Code::KeyS,
        )?;

        // Ctrl+Shift+A - Analyze
        self.register(
            "analyze",
            Modifiers::CONTROL | Modifiers::SHIFT,
            Code::KeyA,
        )?;

        // Ctrl+Shift+I - Interview
        self.register(
            "interview",
            Modifiers::CONTROL | Modifiers::SHIFT,
            Code::KeyI,
        )?;

        // Ctrl+Shift+O - Toggle Overlay
        self.register(
            "toggle_overlay",
            Modifiers::CONTROL | Modifiers::SHIFT,
            Code::KeyO,
        )?;

        // Ctrl+Shift+E - End Session
        self.register(
            "end_session",
            Modifiers::CONTROL | Modifiers::SHIFT,
            Code::KeyE,
        )?;

        info!("Default hotkeys registered");
        Ok(())
    }

    fn register(&self, name: &str, modifiers: Modifiers, code: Code) -> Result<()> {
        let hotkey = HotKey::new(Some(modifiers), code);

        if let Some(manager) = self.manager.read().as_ref() {
            manager
                .register(hotkey)
                .map_err(|e| anyhow::anyhow!("Failed to register hotkey {}: {}", name, e))?;

            self.registered.write().insert(name.to_string(), hotkey);

            info!("Registered hotkey: {} ({:?}+{:?})", name, modifiers, code);
        }

        Ok(())
    }

    fn start_event_listener(&self) {
        let registered = self.registered.clone();
        let app = self.app.clone();

        std::thread::spawn(move || {
            let receiver = GlobalHotKeyEvent::receiver();

            loop {
                if let Ok(event) = receiver.recv() {
                    let reg = registered.read();
                    let hotkey = event.id();

                    // Find which hotkey was triggered
                    for (name, hk) in reg.iter() {
                        if hk.id() == hotkey {
                            info!("Hotkey triggered: {}", name);

                            // Emit event to frontend
                            if let Some(app_handle) = app.read().as_ref() {
                                let event_name = format!("hotkey-{}", name);
                                if let Err(e) = app_handle.emit(&event_name, ()) {
                                    error!("Failed to emit hotkey event: {}", e);
                                }
                            }
                            break;
                        }
                    }
                }
            }
        });
    }

    pub fn unregister_all(&self) {
        if let Some(manager) = self.manager.write().as_ref() {
            let registered = self.registered.read();
            for (name, hotkey) in registered.iter() {
                if let Err(e) = manager.unregister(*hotkey) {
                    error!("Failed to unregister hotkey {}: {}", name, e);
                }
            }
        }

        self.registered.write().clear();
        info!("All hotkeys unregistered");
    }
}
