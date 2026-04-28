use anyhow::{Context, Result};
use reqwest::{Client, header};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::RwLock;
use tracing::{info, error, debug};
use futures::StreamExt;

use super::proxy::ProxyClient;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub role: String,
    pub content: String,
}

#[derive(Clone)]
pub struct LLMClient {
    client: Arc<Client>,
    config: Arc<RwLock<crate::utils::Config>>,
    proxy: Arc<RwLock<Option<ProxyClient>>>,
}

impl Default for LLMClient {
    fn default() -> Self {
        Self::new()
    }
}

impl LLMClient {
    pub fn new() -> Self {
        // HTTP/2 connection pool with keepalive
        let client = Client::builder()
            .http2_prior_knowledge()
            .pool_idle_timeout(Duration::from_secs(90))
            .pool_max_idle_per_host(10)
            .tcp_keepalive(Duration::from_secs(60))
            .timeout(Duration::from_secs(120))
            .build()
            .expect("Failed to create HTTP client");

        let config = crate::utils::Config::load().unwrap_or_default();
        let proxy = Self::init_proxy(&config, Arc::new(client.clone()));

        Self {
            client: Arc::new(client),
            config: Arc::new(RwLock::new(config)),
            proxy: Arc::new(RwLock::new(proxy)),
        }
    }

    fn init_proxy(config: &crate::utils::Config, client: Arc<Client>) -> Option<ProxyClient> {
        let api_url = config.glassnote_api_url.as_ref()?.clone();
        let api_token = config.glassnote_api_token.as_ref()?.clone();

        if api_url.is_empty() || api_token.is_empty() {
            return None;
        }

        info!("Proxy mode enabled: {}", api_url);
        Some(ProxyClient::new(api_url, api_token, client))
    }

    pub async fn reload_config(&self) -> Result<()> {
        let config = crate::utils::Config::load()?;
        let proxy = Self::init_proxy(&config, self.client.clone());

        *self.config.write().await = config;
        *self.proxy.write().await = proxy;

        Ok(())
    }

    /// Pre-warm TCP+TLS connections to LLM provider
    pub async fn warm_connections(&self) -> Result<()> {
        let config = self.config.read().await;
        let provider = config.selected_provider.as_deref().unwrap_or("anthropic");

        let endpoint = if provider == "anthropic" {
            "https://api.anthropic.com/v1/messages"
        } else {
            "https://api.openai.com/v1/chat/completions"
        };

        info!("Pre-warming connection to {}", endpoint);

        // Fire a lightweight HEAD request to establish TCP+TLS
        match self.client.head(endpoint).send().await {
            Ok(_) => {
                info!("✓ Connection pre-warmed successfully");
                Ok(())
            }
            Err(e) => {
                error!("Connection pre-warm failed (non-fatal): {}", e);
                Err(e.into())
            }
        }
    }

    pub async fn stream_solve<F>(
        &self,
        system_prompt: String,
        screenshots: Vec<String>,
        mut on_token: F,
    ) -> Result<String>
    where
        F: FnMut(&str) + Send + 'static,
    {
        let config = self.config.read().await;
        let provider = config.selected_provider.as_deref().unwrap_or("anthropic");

        let start = std::time::Instant::now();

        let full_response = if provider == "anthropic" {
            self.stream_anthropic(
                system_prompt,
                screenshots,
                "solve",
                &mut on_token,
            )
            .await?
        } else {
            self.stream_openai(
                system_prompt,
                screenshots,
                "solve",
                &mut on_token,
            )
            .await?
        };

        let elapsed = start.elapsed();
        info!("LLM response complete in {:?}", elapsed);

        Ok(full_response)
    }

    pub async fn stream_interview<F>(
        &self,
        system_prompt: String,
        transcript: String,
        mut on_token: F,
    ) -> Result<String>
    where
        F: FnMut(&str) + Send + 'static,
    {
        let config = self.config.read().await;
        let provider = config.selected_provider.as_deref().unwrap_or("anthropic");

        let start = std::time::Instant::now();

        let full_response = if provider == "anthropic" {
            self.stream_anthropic_text(
                system_prompt,
                transcript,
                &mut on_token,
            )
            .await?
        } else {
            self.stream_openai_text(
                system_prompt,
                transcript,
                &mut on_token,
            )
            .await?
        };

        let elapsed = start.elapsed();
        debug!("Interview response in {:?}", elapsed);

        Ok(full_response)
    }

    async fn stream_anthropic<F>(
        &self,
        system_prompt: String,
        screenshots: Vec<String>,
        _mode: &str,
        on_token: &mut F,
    ) -> Result<String>
    where
        F: FnMut(&str),
    {
        let config = self.config.read().await;
        let api_key = config
            .anthropic_api_key
            .as_ref()
            .context("Anthropic API key not configured")?;
        let model = config
            .anthropic_model
            .as_deref()
            .unwrap_or("claude-sonnet-4-20250514");

        // Build content array with images
        let mut content_parts: Vec<serde_json::Value> = vec![];

        for screenshot in screenshots {
            content_parts.push(json!({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": screenshot
                }
            }));
        }

        content_parts.push(json!({
            "type": "text",
            "text": "Please analyze the provided screenshot(s) and solve the problem."
        }));

        let payload = json!({
            "model": model,
            "max_tokens": 4096,
            "temperature": 0.7,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": content_parts
                }
            ],
            "stream": true
        });

        debug!("Sending Anthropic request to model: {}", model);

        let mut response = self
            .client
            .post("https://api.anthropic.com/v1/messages")
            .header(header::CONTENT_TYPE, "application/json")
            .header("x-api-key", api_key)
            .header("anthropic-version", "2023-06-01")
            .json(&payload)
            .send()
            .await?;

        let mut full_text = String::new();
        let mut first_token = true;

        while let Some(chunk) = response.chunk().await? {
            let text = String::from_utf8_lossy(&chunk);

            for line in text.lines() {
                if line.starts_with("data: ") {
                    let data = &line[6..];
                    if data == "[DONE]" {
                        break;
                    }

                    if let Ok(json) = serde_json::from_str::<serde_json::Value>(data) {
                        if json["type"] == "content_block_delta" {
                            if let Some(delta_text) = json["delta"]["text"].as_str() {
                                if first_token {
                                    let ttft = std::time::Instant::now();
                                    debug!("TTFT: {:?}", ttft);
                                    first_token = false;
                                }

                                full_text.push_str(delta_text);
                                on_token(delta_text);
                            }
                        }
                    }
                }
            }
        }

        Ok(full_text)
    }

    async fn stream_anthropic_text<F>(
        &self,
        system_prompt: String,
        user_text: String,
        on_token: &mut F,
    ) -> Result<String>
    where
        F: FnMut(&str),
    {
        let config = self.config.read().await;
        let api_key = config
            .anthropic_api_key
            .as_ref()
            .context("Anthropic API key not configured")?;
        let model = config
            .anthropic_model
            .as_deref()
            .unwrap_or("claude-haiku-4-20250514");

        let payload = json!({
            "model": model,
            "max_tokens": 2048,
            "temperature": 0.7,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": user_text
                }
            ],
            "stream": true
        });

        let mut response = self
            .client
            .post("https://api.anthropic.com/v1/messages")
            .header(header::CONTENT_TYPE, "application/json")
            .header("x-api-key", api_key)
            .header("anthropic-version", "2023-06-01")
            .json(&payload)
            .send()
            .await?;

        let mut full_text = String::new();

        while let Some(chunk) = response.chunk().await? {
            let text = String::from_utf8_lossy(&chunk);

            for line in text.lines() {
                if line.starts_with("data: ") {
                    let data = &line[6..];
                    if data == "[DONE]" {
                        break;
                    }

                    if let Ok(json) = serde_json::from_str::<serde_json::Value>(data) {
                        if json["type"] == "content_block_delta" {
                            if let Some(delta_text) = json["delta"]["text"].as_str() {
                                full_text.push_str(delta_text);
                                on_token(delta_text);
                            }
                        }
                    }
                }
            }
        }

        Ok(full_text)
    }

    async fn stream_openai<F>(
        &self,
        system_prompt: String,
        screenshots: Vec<String>,
        _mode: &str,
        on_token: &mut F,
    ) -> Result<String>
    where
        F: FnMut(&str),
    {
        let config = self.config.read().await;
        let api_key = config
            .openai_api_key
            .as_ref()
            .context("OpenAI API key not configured")?;
        let model = config
            .openai_model
            .as_deref()
            .unwrap_or("gpt-4o");

        let mut content_parts: Vec<serde_json::Value> = vec![];

        for screenshot in screenshots {
            content_parts.push(json!({
                "type": "image_url",
                "image_url": {
                    "url": format!("data:image/png;base64,{}", screenshot)
                }
            }));
        }

        content_parts.push(json!({
            "type": "text",
            "text": "Please analyze the provided screenshot(s) and solve the problem."
        }));

        let payload = json!({
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": content_parts
                }
            ],
            "stream": true,
            "temperature": 0.7
        });

        let mut response = self
            .client
            .post("https://api.openai.com/v1/chat/completions")
            .header(header::AUTHORIZATION, format!("Bearer {}", api_key))
            .header(header::CONTENT_TYPE, "application/json")
            .json(&payload)
            .send()
            .await?;

        let mut full_text = String::new();

        while let Some(chunk) = response.chunk().await? {
            let text = String::from_utf8_lossy(&chunk);

            for line in text.lines() {
                if line.starts_with("data: ") {
                    let data = &line[6..];
                    if data == "[DONE]" {
                        break;
                    }

                    if let Ok(json) = serde_json::from_str::<serde_json::Value>(data) {
                        if let Some(choices) = json["choices"].as_array() {
                            if let Some(choice) = choices.first() {
                                if let Some(delta_text) = choice["delta"]["content"].as_str() {
                                    full_text.push_str(delta_text);
                                    on_token(delta_text);
                                }
                            }
                        }
                    }
                }
            }
        }

        Ok(full_text)
    }

    async fn stream_openai_text<F>(
        &self,
        system_prompt: String,
        user_text: String,
        on_token: &mut F,
    ) -> Result<String>
    where
        F: FnMut(&str),
    {
        let config = self.config.read().await;
        let api_key = config
            .openai_api_key
            .as_ref()
            .context("OpenAI API key not configured")?;
        let model = config
            .openai_model
            .as_deref()
            .unwrap_or("gpt-4o-mini");

        let payload = json!({
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_text
                }
            ],
            "stream": true,
            "temperature": 0.7
        });

        let mut response = self
            .client
            .post("https://api.openai.com/v1/chat/completions")
            .header(header::AUTHORIZATION, format!("Bearer {}", api_key))
            .header(header::CONTENT_TYPE, "application/json")
            .json(&payload)
            .send()
            .await?;

        let mut full_text = String::new();

        while let Some(chunk) = response.chunk().await? {
            let text = String::from_utf8_lossy(&chunk);

            for line in text.lines() {
                if line.starts_with("data: ") {
                    let data = &line[6..];
                    if data == "[DONE]" {
                        break;
                    }

                    if let Ok(json) = serde_json::from_str::<serde_json::Value>(data) {
                        if let Some(choices) = json["choices"].as_array() {
                            if let Some(choice) = choices.first() {
                                if let Some(delta_text) = choice["delta"]["content"].as_str() {
                                    full_text.push_str(delta_text);
                                    on_token(delta_text);
                                }
                            }
                        }
                    }
                }
            }
        }

        Ok(full_text)
    }
}
