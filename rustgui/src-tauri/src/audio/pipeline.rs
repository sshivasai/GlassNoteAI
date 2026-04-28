use anyhow::Result;
use parking_lot::RwLock;
use std::sync::Arc;
use tokio::sync::mpsc;
use tracing::{info, error, debug};

use super::recorder::{AudioRecorder, VoiceActivityDetector};
use super::stt::{STTProvider, DeepgramSTT, OpenAIRealtimeSTT};

type TranscriptCallback = Arc<dyn Fn(String) + Send + Sync>;

pub struct AudioPipeline {
    running: Arc<RwLock<bool>>,
    recorder: Arc<RwLock<Option<AudioRecorder>>>,
    stt: Arc<RwLock<Option<Box<dyn STTProvider>>>>,
    callback: Arc<RwLock<Option<TranscriptCallback>>>,
    accumulated_transcript: Arc<RwLock<String>>,
    last_transcript_time: Arc<RwLock<std::time::Instant>>,
    config: Arc<RwLock<Option<crate::utils::Config>>>,
}

impl Default for AudioPipeline {
    fn default() -> Self {
        Self::new()
    }
}

impl AudioPipeline {
    pub fn new() -> Self {
        Self {
            running: Arc::new(RwLock::new(false)),
            recorder: Arc::new(RwLock::new(None)),
            stt: Arc::new(RwLock::new(None)),
            callback: Arc::new(RwLock::new(None)),
            accumulated_transcript: Arc::new(RwLock::new(String::new())),
            last_transcript_time: Arc::new(RwLock::new(std::time::Instant::now())),
            config: Arc::new(RwLock::new(None)),
        }
    }

    pub fn set_config(&self, config: crate::utils::Config) {
        *self.config.write() = Some(config);
    }

    pub async fn start<F>(&self, on_transcript: F) -> Result<()>
    where
        F: Fn(String) + Send + Sync + 'static,
    {
        info!("Starting audio pipeline");

        *self.running.write() = true;
        *self.callback.write() = Some(Arc::new(on_transcript));

        // Load config
        let config = if let Some(cfg) = self.config.read().as_ref() {
            cfg.clone()
        } else {
            crate::utils::Config::load()?
        };

        let audio_source = config.audio_source.as_deref().unwrap_or("system");
        let stt_provider = config.stt_provider.as_deref().unwrap_or("deepgram");

        // Create audio recorder
        let mut recorder = AudioRecorder::new(audio_source)?;

        // Create STT provider
        let mut stt: Box<dyn STTProvider> = match stt_provider {
            "deepgram" => {
                let api_key = config
                    .deepgram_api_key
                    .clone()
                    .unwrap_or_default();
                Box::new(DeepgramSTT::new(api_key)?)
            }
            "openai_realtime" => {
                let api_key = config
                    .openai_api_key
                    .clone()
                    .unwrap_or_default();
                Box::new(OpenAIRealtimeSTT::new(api_key)?)
            }
            _ => {
                anyhow::bail!("Unknown STT provider: {}", stt_provider);
            }
        };

        // Connect STT
        stt.connect()?;

        // Start audio capture
        let (audio_tx, mut audio_rx) = mpsc::unbounded_channel::<Vec<u8>>();
        recorder.start(audio_tx)?;

        *self.recorder.write() = Some(recorder);

        // Spawn audio processing task
        let stt_clone = Arc::new(RwLock::new(stt));
        let running = self.running.clone();
        let callback = self.callback.clone();
        let accumulated = self.accumulated_transcript.clone();
        let last_time = self.last_transcript_time.clone();

        tokio::spawn(async move {
            while let Some(audio_data) = audio_rx.recv().await {
                if !*running.read() {
                    break;
                }

                // Send audio to STT
                if let Some(stt_provider) = stt_clone.write().as_mut() {
                    if let Err(e) = stt_provider.send_audio(&audio_data) {
                        error!("Failed to send audio to STT: {}", e);
                    }

                    // Check for transcript
                    if let Ok(Some(transcript)) = stt_provider.get_transcript() {
                        debug!("Transcript: {}", transcript);

                        *accumulated.write() = transcript.clone();
                        *last_time.write() = std::time::Instant::now();

                        // Call callback
                        if let Some(cb) = callback.read().as_ref() {
                            cb(transcript);
                        }
                    }
                }
            }

            info!("Audio processing task ended");
        });

        *self.stt.write() = Some(*stt_clone.write().take().unwrap());

        Ok(())
    }

    pub async fn stop(&self) -> Result<()> {
        info!("Stopping audio pipeline");

        *self.running.write() = false;

        // Stop recorder
        if let Some(mut recorder) = self.recorder.write().take() {
            recorder.stop()?;
        }

        // Disconnect STT
        if let Some(stt) = self.stt.write().take() {
            stt.disconnect()?;
        }

        *self.callback.write() = None;
        *self.accumulated_transcript.write() = String::new();

        Ok(())
    }

    pub fn is_running(&self) -> bool {
        *self.running.read()
    }

    pub fn get_accumulated_transcript(&self) -> String {
        self.accumulated_transcript.read().clone()
    }

    pub fn get_last_transcript_age(&self) -> f32 {
        self.last_transcript_time.read().elapsed().as_secs_f32()
    }
}
