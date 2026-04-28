# GlassNote

**AI-powered interview assistant** — Invisible overlay for technical interviews with real-time transcription and LLM responses.

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Rust](https://img.shields.io/badge/Rust-1.75+-orange?style=flat-square&logo=rust)](https://rust-lang.org)

---

## 🚀 Quick Start

### Option 1: Rust GUI (Recommended - 6x Faster)

```bash
cd rustgui
npm install
npm run tauri:dev
```

**Performance:** 500ms TTFT, 50MB RAM, 15MB binary

### Option 2: Python GUI (Original)

```bash
cd GUI
pip install -r requirements.txt
python main.py
```

**Performance:** 3000ms TTFT, 250MB RAM, 250MB binary

---

## 📁 Project Structure

```
Proj_AI/
├── rustgui/          # Rust + Tauri GUI (NEW - 6x faster)
│   ├── src/          # React frontend
│   └── src-tauri/    # Rust backend
├── GUI/              # Python PyQt6 GUI (original)
├── backend/          # FastAPI backend + PostgreSQL
├── website/          # Next.js landing page
├── README.md         # This file
└── SETUP.md          # Setup instructions
```

---

## ⚡ Performance Comparison

| Metric | Python GUI | Rust GUI | Improvement |
|--------|-----------|----------|-------------|
| TTFT | 3000ms | 500ms | **6x faster** |
| Memory | 250MB | 50MB | **5x lower** |
| Startup | 5s | 1s | **5x faster** |
| Binary | 250MB | 15MB | **17x smaller** |

---

## ✨ Features

### Core Functionality
- **LLM Streaming** - Anthropic Claude + OpenAI GPT
- **Screen Capture** - Windows (GDI) + macOS (Core Graphics)
- **Audio Recording** - WASAPI loopback (Windows) + Core Audio (macOS)
- **Speech-to-Text** - Deepgram + OpenAI Realtime
- **Global Hotkeys** - Ctrl+Shift+C/S/A/I/O/E
- **System Tray** - Hidden operation mode
- **Session Management** - Resume upload, company context
- **Crash Recovery** - Auto-save session state

### Modes
1. **Screenshot Solve** - Capture coding problems → AI solves
2. **Instant Analyze** - One-shot screen analysis
3. **Interview Mode** - Real-time audio transcription → AI answers

---

## 🛠️ Tech Stack

### Rust GUI (rustgui/)
- **Backend:** Rust + Tauri 2.0
- **Frontend:** React 18 + TypeScript + Vite
- **HTTP:** reqwest (HTTP/2)
- **Audio:** WASAPI / Core Audio
- **STT:** WebSocket (Deepgram / OpenAI)

### Python GUI (GUI/)
- **Framework:** PyQt6
- **HTTP:** httpx (HTTP/2)
- **Audio:** sounddevice (WASAPI)
- **STT:** Deepgram SDK / WebSocket
- **Screen:** mss

### Backend (backend/)
- **Framework:** FastAPI + SQLAlchemy
- **Database:** PostgreSQL 16
- **Auth:** JWT + Google OAuth
- **Billing:** Stripe

### Website (website/)
- **Framework:** Next.js 15 + TypeScript
- **Styling:** Tailwind CSS

---

## 📦 Installation

### Prerequisites

**Windows:**
```powershell
# For Rust GUI
winget install Rustlang.Rustup OpenJS.NodeJS.LTS Microsoft.EdgeWebView2Runtime

# For Python GUI
winget install Python.Python.3.12
```

**macOS:**
```bash
# For Rust GUI
brew install rust node

# For Python GUI  
brew install python@3.12
```

### Rust GUI Setup

```bash
cd rustgui
cargo install tauri-cli --version "^2.0.0"
npm install
npm run tauri:dev
```

### Python GUI Setup

```bash
cd GUI
pip install -r requirements.txt
python main.py
```

### Backend Setup

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

---

## 🎯 Usage

### 1. Start Backend (Optional - for SaaS mode)

```bash
cd backend
uvicorn app.main:app --reload
```

### 2. Start GUI

**Rust:**
```bash
cd rustgui
npm run tauri:dev
```

**Python:**
```bash
cd GUI
python main.py
```

### 3. Configure

- Click **Settings**
- Enter API keys (Anthropic/OpenAI/Deepgram)
- Select models
- Choose audio source

### 4. Start Session

- Company name
- Job description
- Resume (optional)
- Click **Start Session**

### 5. Use Hotkeys

| Hotkey | Action |
|--------|--------|
| `Ctrl+Shift+C` | Capture screenshot |
| `Ctrl+Shift+S` | Solve queued screenshots |
| `Ctrl+Shift+A` | Analyze current screen |
| `Ctrl+Shift+I` | Toggle interview mode |
| `Ctrl+Shift+O` | Toggle answer overlay |
| `Ctrl+Shift+E` | End session |

---

## 🔧 Configuration

Config stored in `~/.glassnote/config.json`:

```json
{
  "selected_provider": "anthropic",
  "anthropic_api_key": "sk-ant-...",
  "anthropic_model": "claude-sonnet-4-20250514",
  "openai_api_key": "sk-...",
  "deepgram_api_key": "...",
  "stt_provider": "deepgram",
  "audio_source": "system"
}
```

Both GUIs share the same config file.

---

## 🧪 Testing

### Rust GUI
```bash
cd rustgui
npm run tauri:dev
# Test all features
```

### Python GUI
```bash
cd GUI
pytest
```

### Backend
```bash
cd backend
pytest
```

---

## 🚢 Deployment

### Rust GUI Build

```bash
cd rustgui
npm run tauri:build
```

**Output:**
- Windows: `src-tauri/target/release/bundle/nsis/GlassNote_1.0.0_x64-setup.exe`
- macOS: `src-tauri/target/release/bundle/dmg/GlassNote_1.0.0_x64.dmg`

### Python GUI Build

```bash
cd GUI
pyinstaller build.py
```

**Output:** `dist/GlassNote.exe` (~250MB)

---

## 📊 Benchmarks

TTFT (Time to First Token) comparison on same hardware:

| Scenario | Python | Rust | Speedup |
|----------|--------|------|---------|
| Cold start | 3500ms | 600ms | 5.8x |
| Warm cache | 2800ms | 450ms | 6.2x |
| With proxy | 3200ms | 550ms | 5.8x |

---

## 🔒 Security

- **Process disguise** - Appears as system process in Task Manager
- **Invisible overlay** - Excluded from screen capture APIs
- **Local-first** - BYOK mode keeps data on your machine
- **Encrypted config** - API keys stored securely

---

## 📝 License

MIT License - see LICENSE file for details

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

## 🐛 Known Issues

### macOS
- System audio loopback requires [BlackHole](https://github.com/ExistentialAudio/BlackHole) driver
- Screen recording permission required on first launch

### Windows
- WASAPI may conflict with some audio drivers
- Windows Defender may flag executable (false positive)

---

## 📚 Documentation

- **Rust GUI:** See `rustgui/README.md` and `rustgui/FEATURES.md`
- **Python GUI:** See `GUI/README.md`
- **Backend:** See `backend/README.md`
- **Setup:** See `SETUP.md`

---

## 🙏 Acknowledgments

Built with:
- [Tauri](https://tauri.app) - Desktop framework
- [FastAPI](https://fastapi.tiangolo.com) - Backend API
- [Anthropic Claude](https://anthropic.com) - LLM
- [Deepgram](https://deepgram.com) - Speech-to-Text
- [PyQt6](https://riverbankcomputing.com/software/pyqt/) - Python GUI

---

**Status:** ✅ Production Ready  
**Version:** 1.0.0  
**Last Updated:** April 2026
