use anyhow::{Context, Result};
use parking_lot::RwLock;
use std::sync::Arc;
use tokio_tungstenite::{connect_async, tungstenite::Message};
use futures::{SinkExt, StreamExt};
use tracing::{info, error, debug};

pub trait STTProvider: Send + Sync {
    fn connect(&mut self) -> Result<()>;
    fn send_audio(&mut self, data: &[u8]) -> Result<()>;
    fn get_transcript(&mut self) -> Result<Option<String>>;
    fn disconnect(&self) -> Result<()>;
}

// Deepgram STT Implementation
pub struct DeepgramSTT {
    api_key: String,
    ws_tx: Arc<RwLock<Option<futures::stream::SplitSink<
        tokio_tungstenite::WebSocketStream<tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>>,
        Message,
    >>>>,
    transcript_queue: Arc<RwLock<Vec<String>>>,
    running: Arc<RwLock<bool>>,
}

impl DeepgramSTT {
    pub fn new(api_key: String) -> Result<Self> {
        Ok(Self {
            api_key,
            ws_tx: Arc::new(RwLock::new(None)),
            transcript_queue: Arc::new(RwLock::new(Vec::new())),
            running: Arc::new(RwLock::new(false)),
        })
    }
}

impl STTProvider for DeepgramSTT {
    fn connect(&mut self) -> Result<()> {
        if self.api_key.is_empty() {
            anyhow::bail!("Deepgram API key not configured");
        }

        *self.running.write() = true;

        let api_key = self.api_key.clone();
        let ws_tx = self.ws_tx.clone();
        let queue = self.transcript_queue.clone();
        let running = self.running.clone();

        tokio::spawn(async move {
            let url = format!(
                "wss://api.deepgram.com/v1/listen?encoding=linear16&sample_rate=16000&channels=1&interim_results=true",
            );

            match connect_async(&url).await {
                Ok((ws_stream, _)) => {
                    info!("Deepgram WebSocket connected");

                    let (mut write, mut read) = ws_stream.split();

                    // Send API key as first message
                    if let Err(e) = write
                        .send(Message::Text(
                            serde_json::json!({
                                "type": "Authenticate",
                                "token": api_key
                            })
                            .to_string(),
                        ))
                        .await
                    {
                        error!("Failed to authenticate with Deepgram: {}", e);
                        return;
                    }

                    *ws_tx.write() = Some(write);

                    // Read messages
                    while *running.read() {
                        match read.next().await {
                            Some(Ok(Message::Text(text))) => {
                                if let Ok(json) = serde_json::from_str::<serde_json::Value>(&text) {
                                    if let Some(channel) = json.get("channel") {
                                        if let Some(alternatives) = channel
                                            .get("alternatives")
                                            .and_then(|a| a.as_array())
                                        {
                                            if let Some(first) = alternatives.first() {
                                                if let Some(transcript) = first
                                                    .get("transcript")
                                                    .and_then(|t| t.as_str())
                                                {
                                                    if !transcript.is_empty() {
                                                        debug!("Deepgram transcript: {}", transcript);
                                                        queue.write().push(transcript.to_string());
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            Some(Ok(Message::Close(_))) => {
                                info!("Deepgram WebSocket closed");
                                break;
                            }
                            Some(Err(e)) => {
                                error!("Deepgram WebSocket error: {}", e);
                                break;
                            }
                            None => break,
                            _ => {}
                        }
                    }

                    info!("Deepgram WebSocket disconnected");
                }
                Err(e) => {
                    error!("Failed to connect to Deepgram: {}", e);
                }
            }
        });

        Ok(())
    }

    fn send_audio(&mut self, data: &[u8]) -> Result<()> {
        let ws_tx = self.ws_tx.clone();
        let data = data.to_vec();

        tokio::spawn(async move {
            if let Some(tx) = ws_tx.write().as_mut() {
                if let Err(e) = tx.send(Message::Binary(data)).await {
                    error!("Failed to send audio to Deepgram: {}", e);
                }
            }
        });

        Ok(())
    }

    fn get_transcript(&mut self) -> Result<Option<String>> {
        let mut queue = self.transcript_queue.write();
        if !queue.is_empty() {
            Ok(Some(queue.remove(0)))
        } else {
            Ok(None)
        }
    }

    fn disconnect(&self) -> Result<()> {
        *self.running.write() = false;
        Ok(())
    }
}

// OpenAI Realtime STT Implementation
pub struct OpenAIRealtimeSTT {
    api_key: String,
    ws_tx: Arc<RwLock<Option<futures::stream::SplitSink<
        tokio_tungstenite::WebSocketStream<tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>>,
        Message,
    >>>>,
    transcript_queue: Arc<RwLock<Vec<String>>>,
    running: Arc<RwLock<bool>>,
}

impl OpenAIRealtimeSTT {
    pub fn new(api_key: String) -> Result<Self> {
        Ok(Self {
            api_key,
            ws_tx: Arc::new(RwLock::new(None)),
            transcript_queue: Arc::new(RwLock::new(Vec::new())),
            running: Arc::new(RwLock::new(false)),
        })
    }
}

impl STTProvider for OpenAIRealtimeSTT {
    fn connect(&mut self) -> Result<()> {
        if self.api_key.is_empty() {
            anyhow::bail!("OpenAI API key not configured");
        }

        *self.running.write() = true;

        let api_key = self.api_key.clone();
        let ws_tx = self.ws_tx.clone();
        let queue = self.transcript_queue.clone();
        let running = self.running.clone();

        tokio::spawn(async move {
            let url = "wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview-2024-12-17";

            let request = match tokio_tungstenite::tungstenite::client::IntoClientRequest::into_client_request(url) {
                Ok(mut req) => {
                    req.headers_mut().insert(
                        "Authorization",
                        format!("Bearer {}", api_key).parse().unwrap(),
                    );
                    req.headers_mut().insert(
                        "OpenAI-Beta",
                        "realtime=v1".parse().unwrap(),
                    );
                    req
                }
                Err(e) => {
                    error!("Failed to create OpenAI request: {}", e);
                    return;
                }
            };

            match connect_async(request).await {
                Ok((ws_stream, _)) => {
                    info!("OpenAI Realtime WebSocket connected");

                    let (mut write, mut read) = ws_stream.split();

                    // Send session configuration
                    let config = serde_json::json!({
                        "type": "session.update",
                        "session": {
                            "modalities": ["text", "audio"],
                            "instructions": "Transcribe the audio accurately.",
                            "input_audio_format": "pcm16",
                            "output_audio_format": "pcm16",
                            "input_audio_transcription": {
                                "model": "whisper-1"
                            }
                        }
                    });

                    if let Err(e) = write.send(Message::Text(config.to_string())).await {
                        error!("Failed to configure OpenAI session: {}", e);
                        return;
                    }

                    *ws_tx.write() = Some(write);

                    // Read messages
                    while *running.read() {
                        match read.next().await {
                            Some(Ok(Message::Text(text))) => {
                                if let Ok(json) = serde_json::from_str::<serde_json::Value>(&text) {
                                    if json["type"] == "conversation.item.input_audio_transcription.completed" {
                                        if let Some(transcript) = json["transcript"].as_str() {
                                            if !transcript.is_empty() {
                                                debug!("OpenAI transcript: {}", transcript);
                                                queue.write().push(transcript.to_string());
                                            }
                                        }
                                    }
                                }
                            }
                            Some(Ok(Message::Close(_))) => {
                                info!("OpenAI WebSocket closed");
                                break;
                            }
                            Some(Err(e)) => {
                                error!("OpenAI WebSocket error: {}", e);
                                break;
                            }
                            None => break,
                            _ => {}
                        }
                    }

                    info!("OpenAI Realtime WebSocket disconnected");
                }
                Err(e) => {
                    error!("Failed to connect to OpenAI: {}", e);
                }
            }
        });

        Ok(())
    }

    fn send_audio(&mut self, data: &[u8]) -> Result<()> {
        let ws_tx = self.ws_tx.clone();
        let data = data.to_vec();

        tokio::spawn(async move {
            if let Some(tx) = ws_tx.write().as_mut() {
                // Encode audio as base64
                let b64 = base64::Engine::encode(&base64::engine::general_purpose::STANDARD, &data);

                let message = serde_json::json!({
                    "type": "input_audio_buffer.append",
                    "audio": b64
                });

                if let Err(e) = tx.send(Message::Text(message.to_string())).await {
                    error!("Failed to send audio to OpenAI: {}", e);
                }
            }
        });

        Ok(())
    }

    fn get_transcript(&mut self) -> Result<Option<String>> {
        let mut queue = self.transcript_queue.write();
        if !queue.is_empty() {
            Ok(Some(queue.remove(0)))
        } else {
            Ok(None)
        }
    }

    fn disconnect(&self) -> Result<()> {
        *self.running.write() = false;
        Ok(())
    }
}
