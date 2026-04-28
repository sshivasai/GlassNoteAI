use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use tracing::{info, error};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionState {
    pub session_id: String,
    pub company: String,
    pub job_description: String,
    pub resume_text: String,
    pub timestamp: i64,
}

fn state_path() -> PathBuf {
    let home = std::env::var("USERPROFILE")
        .or_else(|_| std::env::var("HOME"))
        .unwrap_or_else(|_| ".".to_string());

    PathBuf::from(home)
        .join(".glassnote")
        .join("session_state.json")
}

pub fn save_session_state(state: &SessionState) -> Result<()> {
    let path = state_path();

    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }

    let json = serde_json::to_string_pretty(state)?;
    std::fs::write(&path, json)?;

    info!("Session state saved to {:?}", path);
    Ok(())
}

pub fn load_session_state() -> Result<Option<SessionState>> {
    let path = state_path();

    if !path.exists() {
        return Ok(None);
    }

    let content = std::fs::read_to_string(&path)?;
    let state: SessionState = serde_json::from_str(&content)?;

    // Check if state is recent (within last 24 hours)
    let now = chrono::Utc::now().timestamp();
    if now - state.timestamp > 86400 {
        info!("Session state too old, ignoring");
        clear_session_state()?;
        return Ok(None);
    }

    info!("Session state loaded from {:?}", path);
    Ok(Some(state))
}

pub fn clear_session_state() -> Result<()> {
    let path = state_path();

    if path.exists() {
        std::fs::remove_file(&path)?;
        info!("Session state cleared");
    }

    Ok(())
}
