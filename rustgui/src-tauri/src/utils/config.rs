use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct Config {
    pub selected_provider: Option<String>,
    pub anthropic_api_key: Option<String>,
    pub anthropic_model: Option<String>,
    pub openai_api_key: Option<String>,
    pub openai_model: Option<String>,
    pub deepgram_api_key: Option<String>,
    pub stt_provider: Option<String>,
    pub audio_source: Option<String>,
    pub glassnote_api_url: Option<String>,
    pub glassnote_api_token: Option<String>,
    pub glassnote_user_plan: Option<String>,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            selected_provider: Some("anthropic".to_string()),
            anthropic_api_key: None,
            anthropic_model: Some("claude-sonnet-4-20250514".to_string()),
            openai_api_key: None,
            openai_model: Some("gpt-4o".to_string()),
            deepgram_api_key: None,
            stt_provider: Some("deepgram".to_string()),
            audio_source: Some("system".to_string()),
            glassnote_api_url: None,
            glassnote_api_token: None,
            glassnote_user_plan: Some("free".to_string()),
        }
    }
}

impl Config {
    fn config_path() -> PathBuf {
        let home = std::env::var("USERPROFILE").unwrap_or_else(|_| ".".to_string());
        PathBuf::from(home)
            .join(".glassnote")
            .join("config.json")
    }

    pub fn load() -> Result<Self> {
        let path = Self::config_path();
        if !path.exists() {
            return Ok(Self::default());
        }

        let content = std::fs::read_to_string(path)?;
        let config: Self = serde_json::from_str(&content)?;
        Ok(config)
    }

    pub fn save(&self) -> Result<()> {
        let path = Self::config_path();
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }

        let content = serde_json::to_string_pretty(self)?;
        std::fs::write(path, content)?;
        Ok(())
    }
}
