use anyhow::{Context, Result};
use std::sync::Arc;
use tokio::sync::mpsc;
use tracing::{info, error, debug};

#[cfg(target_os = "windows")]
use crate::audio::recorder_windows::WindowsAudioRecorder;

#[cfg(target_os = "macos")]
use crate::audio::recorder_macos::MacOSAudioRecorder;

pub trait AudioRecorderTrait: Send + Sync {
    fn start(&mut self, tx: mpsc::UnboundedSender<Vec<u8>>) -> Result<()>;
    fn stop(&mut self) -> Result<()>;
    fn is_running(&self) -> bool;
}

pub struct AudioRecorder {
    #[cfg(target_os = "windows")]
    inner: WindowsAudioRecorder,

    #[cfg(target_os = "macos")]
    inner: MacOSAudioRecorder,
}

impl AudioRecorder {
    pub fn new(source: &str) -> Result<Self> {
        info!("Creating audio recorder for source: {}", source);

        #[cfg(target_os = "windows")]
        let inner = WindowsAudioRecorder::new(source)?;

        #[cfg(target_os = "macos")]
        let inner = MacOSAudioRecorder::new(source)?;

        Ok(Self { inner })
    }

    pub fn start(&mut self, tx: mpsc::UnboundedSender<Vec<u8>>) -> Result<()> {
        self.inner.start(tx)
    }

    pub fn stop(&mut self) -> Result<()> {
        self.inner.stop()
    }

    pub fn is_running(&self) -> bool {
        self.inner.is_running()
    }
}

// Voice Activity Detection
pub struct VoiceActivityDetector {
    threshold: f32,
    last_speech_time: std::time::Instant,
}

impl VoiceActivityDetector {
    pub fn new(threshold: f32) -> Self {
        Self {
            threshold,
            last_speech_time: std::time::Instant::now(),
        }
    }

    pub fn is_speech(&mut self, audio_data: &[i16]) -> bool {
        // Calculate RMS (Root Mean Square) energy
        let rms = Self::calculate_rms(audio_data);

        if rms > self.threshold {
            self.last_speech_time = std::time::Instant::now();
            true
        } else {
            false
        }
    }

    pub fn seconds_since_speech(&self) -> f32 {
        self.last_speech_time.elapsed().as_secs_f32()
    }

    fn calculate_rms(samples: &[i16]) -> f32 {
        if samples.is_empty() {
            return 0.0;
        }

        let sum: f64 = samples
            .iter()
            .map(|&s| {
                let normalized = s as f64 / i16::MAX as f64;
                normalized * normalized
            })
            .sum();

        (sum / samples.len() as f64).sqrt() as f32
    }
}
