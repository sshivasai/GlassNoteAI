#[cfg(target_os = "macos")]
use anyhow::{Context, Result};
use parking_lot::RwLock;
use std::sync::Arc;
use tokio::sync::mpsc;
use tracing::{info, error};
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};

pub struct MacOSAudioRecorder {
    source: String,
    running: Arc<RwLock<bool>>,
    stream: Option<cpal::Stream>,
}

impl MacOSAudioRecorder {
    pub fn new(source: &str) -> Result<Self> {
        Ok(Self {
            source: source.to_string(),
            running: Arc::new(RwLock::new(false)),
            stream: None,
        })
    }

    pub fn start(&mut self, tx: mpsc::UnboundedSender<Vec<u8>>) -> Result<()> {
        *self.running.write() = true;

        let host = cpal::default_host();

        let device = if self.source == "system" {
            // macOS doesn't have native loopback, use default input
            // Users need to use tools like BlackHole for system audio capture
            host.default_input_device()
                .context("No input device available")?
        } else {
            host.default_input_device()
                .context("No input device available")?
        };

        let config = device.default_input_config()
            .context("Failed to get default input config")?;

        info!("macOS audio config: {:?}", config);

        let running = self.running.clone();

        let stream = match config.sample_format() {
            cpal::SampleFormat::F32 => {
                Self::build_stream::<f32>(&device, &config.into(), tx, running)?
            }
            cpal::SampleFormat::I16 => {
                Self::build_stream::<i16>(&device, &config.into(), tx, running)?
            }
            cpal::SampleFormat::U16 => {
                Self::build_stream::<u16>(&device, &config.into(), tx, running)?
            }
            _ => anyhow::bail!("Unsupported sample format"),
        };

        stream.play()?;
        self.stream = Some(stream);

        info!("macOS audio recorder started");
        Ok(())
    }

    pub fn stop(&mut self) -> Result<()> {
        *self.running.write() = false;

        if let Some(stream) = self.stream.take() {
            drop(stream);
        }

        info!("macOS audio recorder stopped");
        Ok(())
    }

    pub fn is_running(&self) -> bool {
        *self.running.read()
    }

    fn build_stream<T>(
        device: &cpal::Device,
        config: &cpal::StreamConfig,
        tx: mpsc::UnboundedSender<Vec<u8>>,
        running: Arc<RwLock<bool>>,
    ) -> Result<cpal::Stream>
    where
        T: cpal::Sample + cpal::SizedSample,
    {
        let err_fn = |err| error!("Audio stream error: {}", err);

        let stream = device.build_input_stream(
            config,
            move |data: &[T], _: &cpal::InputCallbackInfo| {
                if !*running.read() {
                    return;
                }

                // Convert samples to bytes
                let bytes = unsafe {
                    std::slice::from_raw_parts(
                        data.as_ptr() as *const u8,
                        data.len() * std::mem::size_of::<T>(),
                    )
                };

                let _ = tx.send(bytes.to_vec());
            },
            err_fn,
            None,
        )?;

        Ok(stream)
    }
}

impl crate::audio::recorder::AudioRecorderTrait for MacOSAudioRecorder {
    fn start(&mut self, tx: mpsc::UnboundedSender<Vec<u8>>) -> Result<()> {
        self.start(tx)
    }

    fn stop(&mut self) -> Result<()> {
        self.stop()
    }

    fn is_running(&self) -> bool {
        self.is_running()
    }
}
