#[cfg(target_os = "windows")]
use anyhow::{Context, Result};
use parking_lot::RwLock;
use std::sync::Arc;
use tokio::sync::mpsc;
use tracing::{info, error};

use windows::Win32::Media::Audio::*;
use windows::Win32::System::Com::*;
use windows::Win32::Foundation::*;
use windows::core::*;

pub struct WindowsAudioRecorder {
    source: String,
    running: Arc<RwLock<bool>>,
}

impl WindowsAudioRecorder {
    pub fn new(source: &str) -> Result<Self> {
        Ok(Self {
            source: source.to_string(),
            running: Arc::new(RwLock::new(false)),
        })
    }

    pub fn start(&mut self, tx: mpsc::UnboundedSender<Vec<u8>>) -> Result<()> {
        *self.running.write() = true;
        let source = self.source.clone();
        let running = self.running.clone();

        std::thread::spawn(move || {
            if let Err(e) = Self::capture_loop(source, tx, running) {
                error!("Audio capture error: {}", e);
            }
        });

        info!("Windows audio recorder started");
        Ok(())
    }

    pub fn stop(&mut self) -> Result<()> {
        *self.running.write() = false;
        info!("Windows audio recorder stopped");
        Ok(())
    }

    pub fn is_running(&self) -> bool {
        *self.running.read()
    }

    fn capture_loop(
        source: String,
        tx: mpsc::UnboundedSender<Vec<u8>>,
        running: Arc<RwLock<bool>>,
    ) -> Result<()> {
        unsafe {
            // Initialize COM
            CoInitializeEx(None, COINIT_APARTMENTTHREADED)?;

            // Create device enumerator
            let enumerator: IMMDeviceEnumerator = CoCreateInstance(
                &MMDeviceEnumerator,
                None,
                CLSCTX_ALL,
            )?;

            // Get audio device
            let device = if source == "system" {
                enumerator.GetDefaultAudioEndpoint(eRender, eConsole)?
            } else {
                enumerator.GetDefaultAudioEndpoint(eCapture, eConsole)?
            };

            // Activate audio client
            let audio_client: IAudioClient = device.Activate(CLSCTX_ALL, None)?;

            // Get mix format
            let format = audio_client.GetMixFormat()?;

            // Initialize audio client
            audio_client.Initialize(
                AUDCLNT_SHAREMODE_SHARED,
                if source == "system" {
                    AUDCLNT_STREAMFLAGS_LOOPBACK
                } else {
                    AUDCLNT_STREAMFLAGS(0)
                },
                10_000_000, // 1 second buffer
                0,
                format,
                None,
            )?;

            // Get capture client
            let capture_client: IAudioCaptureClient = audio_client.GetService()?;

            // Start audio client
            audio_client.Start()?;

            info!("WASAPI capture started (source: {})", source);

            // Capture loop
            while *running.read() {
                std::thread::sleep(std::time::Duration::from_millis(10));

                let packet_length = capture_client.GetNextPacketSize()?;
                if packet_length == 0 {
                    continue;
                }

                let mut data_ptr = std::ptr::null_mut();
                let mut num_frames = 0u32;
                let mut flags = 0u32;

                capture_client.GetBuffer(
                    &mut data_ptr,
                    &mut num_frames,
                    &mut flags,
                    None,
                    None,
                )?;

                if num_frames > 0 && !data_ptr.is_null() {
                    let format_ref = &*format;
                    let bytes_per_frame = format_ref.nBlockAlign as usize;
                    let buffer_size = num_frames as usize * bytes_per_frame;

                    let audio_data = std::slice::from_raw_parts(
                        data_ptr as *const u8,
                        buffer_size,
                    );

                    // Send audio data
                    let _ = tx.send(audio_data.to_vec());
                }

                capture_client.ReleaseBuffer(num_frames)?;
            }

            // Stop audio client
            audio_client.Stop()?;
            CoUninitialize();

            info!("WASAPI capture stopped");
            Ok(())
        }
    }
}

impl crate::audio::recorder::AudioRecorderTrait for WindowsAudioRecorder {
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
