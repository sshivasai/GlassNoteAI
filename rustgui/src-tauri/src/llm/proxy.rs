use anyhow::{Context, Result};
use reqwest::Client;
use serde_json::json;
use std::sync::Arc;
use tracing::{info, error, debug};

/// Proxy client for routing LLM requests through GlassNote backend
pub struct ProxyClient {
    client: Arc<Client>,
    api_url: String,
    api_token: String,
}

impl ProxyClient {
    pub fn new(api_url: String, api_token: String, client: Arc<Client>) -> Self {
        Self {
            client,
            api_url: api_url.trim_end_matches('/').to_string(),
            api_token,
        }
    }

    /// Stream LLM response through GlassNote proxy
    pub async fn stream_proxy<F>(
        &self,
        provider: &str,
        system_prompt: String,
        messages: Vec<serde_json::Value>,
        model: &str,
        on_token: F,
    ) -> Result<String>
    where
        F: Fn(&str),
    {
        let endpoint = match provider {
            "anthropic" => format!("{}/v1/proxy/anthropic", self.api_url),
            "openai" => format!("{}/v1/proxy/openai", self.api_url),
            _ => anyhow::bail!("Unknown provider: {}", provider),
        };

        info!("Proxying {} request through {}", provider, endpoint);

        let payload = if provider == "anthropic" {
            json!({
                "model": model,
                "max_tokens": 4096,
                "system": system_prompt,
                "messages": messages,
                "stream": true
            })
        } else {
            // OpenAI
            let mut msgs = vec![
                json!({
                    "role": "system",
                    "content": system_prompt
                })
            ];
            msgs.extend(messages);

            json!({
                "model": model,
                "messages": msgs,
                "stream": true,
                "temperature": 0.7
            })
        };

        let mut response = self
            .client
            .post(&endpoint)
            .header("Authorization", format!("Bearer {}", self.api_token))
            .header("Content-Type", "application/json")
            .json(&payload)
            .send()
            .await
            .context("Failed to send proxy request")?;

        if !response.status().is_success() {
            let status = response.status();
            let text = response.text().await.unwrap_or_default();
            anyhow::bail!("Proxy error ({}): {}", status, text);
        }

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
                        let token = if provider == "anthropic" {
                            json["delta"]["text"].as_str()
                        } else {
                            json["choices"][0]["delta"]["content"].as_str()
                        };

                        if let Some(t) = token {
                            if first_token {
                                debug!("First token received via proxy");
                                first_token = false;
                            }
                            full_text.push_str(t);
                            on_token(t);
                        }
                    }
                }
            }
        }

        Ok(full_text)
    }

    /// Get STT credentials from proxy
    pub async fn get_stt_credentials(&self) -> Result<SttCredentials> {
        let url = format!("{}/v1/proxy/stt-credentials", self.api_url);

        info!("Fetching STT credentials from proxy");

        let response = self
            .client
            .get(&url)
            .header("Authorization", format!("Bearer {}", self.api_token))
            .send()
            .await
            .context("Failed to fetch STT credentials")?;

        if !response.status().is_success() {
            anyhow::bail!("Failed to get STT credentials: {}", response.status());
        }

        let creds: SttCredentials = response.json().await?;
        info!("STT credentials fetched successfully");

        Ok(creds)
    }

    /// Report session usage to backend
    pub async fn report_usage(&self, usage: SessionUsage) -> Result<()> {
        let url = format!("{}/api/usage/report", self.api_url);

        debug!("Reporting session usage to backend");

        let response = self
            .client
            .post(&url)
            .header("Authorization", format!("Bearer {}", self.api_token))
            .header("Content-Type", "application/json")
            .json(&usage)
            .send()
            .await
            .context("Failed to report usage")?;

        if !response.status().is_success() {
            error!("Failed to report usage: {}", response.status());
        } else {
            info!("Usage reported successfully");
        }

        Ok(())
    }
}

#[derive(Debug, serde::Deserialize)]
pub struct SttCredentials {
    pub deepgram_key: Option<String>,
    pub openai_key: Option<String>,
}

#[derive(Debug, serde::Serialize)]
pub struct SessionUsage {
    pub session_id: String,
    pub duration_seconds: u64,
    pub llm_calls: usize,
    pub stt_calls: usize,
    pub screenshots: usize,
    pub total_tokens: usize,
}
