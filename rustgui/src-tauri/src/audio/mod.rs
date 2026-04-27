mod pipeline;
mod recorder;
mod stt;

#[cfg(target_os = "windows")]
mod recorder_windows;

#[cfg(target_os = "macos")]
mod recorder_macos;

pub use pipeline::AudioPipeline;
pub use recorder::{AudioRecorder, VoiceActivityDetector};
pub use stt::{STTProvider, DeepgramSTT, OpenAIRealtimeSTT};
