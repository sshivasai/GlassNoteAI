use std::path::PathBuf;
use tracing_subscriber::{fmt, prelude::*, EnvFilter};

pub fn init_logger() {
    let log_dir = get_log_dir();

    if let Err(e) = std::fs::create_dir_all(&log_dir) {
        eprintln!("Failed to create log directory: {}", e);
        return;
    }

    let log_file = log_dir.join("glassnote.log");

    let file_appender = match std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_file)
    {
        Ok(file) => file,
        Err(e) => {
            eprintln!("Failed to open log file: {}", e);
            return;
        }
    };

    let file_layer = fmt::layer()
        .with_writer(std::sync::Arc::new(std::sync::Mutex::new(file_appender)))
        .with_ansi(false)
        .with_target(false);

    let stdout_layer = fmt::layer()
        .with_writer(std::io::stdout)
        .with_target(false);

    let env_filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new("info"));

    tracing_subscriber::registry()
        .with(env_filter)
        .with(file_layer)
        .with(stdout_layer)
        .init();

    tracing::info!("Logger initialized - logs at {:?}", log_file);
}

fn get_log_dir() -> PathBuf {
    #[cfg(target_os = "windows")]
    {
        let appdata = std::env::var("APPDATA").unwrap_or_else(|_| ".".to_string());
        PathBuf::from(appdata).join("GlassNote").join("logs")
    }

    #[cfg(target_os = "macos")]
    {
        let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
        PathBuf::from(home).join("Library").join("Logs").join("GlassNote")
    }

    #[cfg(not(any(target_os = "windows", target_os = "macos")))]
    {
        PathBuf::from(".logs")
    }
}
