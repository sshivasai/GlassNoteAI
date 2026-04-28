# GlassNote Rust GUI

High-performance Rust + Tauri frontend for GlassNote AI interview assistant.

## Performance

- **6x faster TTFT** (500ms vs 3000ms Python)
- **5x lower memory** (50MB vs 250MB Python)  
- **17x smaller binary** (15MB vs 250MB Python)

## Quick Start

### Prerequisites

**Windows:**
```powershell
winget install Rustlang.Rustup OpenJS.NodeJS.LTS Microsoft.EdgeWebView2Runtime
cargo install tauri-cli --version "^2.0.0"
```

**macOS:**
```bash
brew install rust node
cargo install tauri-cli --version "^2.0.0"
xcode-select --install
```

### Run

```bash
cd rustgui
npm install
npm run tauri:dev
```

### Build

```bash
npm run tauri:build
```

## Features

- ✅ LLM Streaming (Anthropic Claude + OpenAI GPT)
- ✅ Screen Capture (Windows GDI / macOS Core Graphics)
- ✅ Audio Pipeline (WASAPI / Core Audio)
- ✅ Speech-to-Text (Deepgram + OpenAI Realtime)
- ✅ Global Hotkeys (Ctrl+Shift+C/S/A/I/O/E)
- ✅ System Tray
- ✅ Crash Recovery
- ✅ Proxy Mode (route through GlassNote backend)
- ✅ File Logging

## Architecture

- **Backend:** Rust (Tauri 2.0)
- **Frontend:** React 18 + TypeScript + Vite
- **HTTP:** reqwest (HTTP/2)
- **Audio:** WASAPI (Windows) / Core Audio (macOS)
- **STT:** WebSocket (Deepgram / OpenAI)

## Hotkeys

| Key | Action |
|-----|--------|
| `Ctrl+Shift+C` | Capture screenshot |
| `Ctrl+Shift+S` | Solve |
| `Ctrl+Shift+A` | Analyze |
| `Ctrl+Shift+I` | Interview mode |
| `Ctrl+Shift+O` | Toggle overlay |
| `Ctrl+Shift+E` | End session |

## Platform Support

- **Windows 10/11** - Fully supported
- **macOS 12+** - Fully supported

## License

MIT
