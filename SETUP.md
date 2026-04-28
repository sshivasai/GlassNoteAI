# GlassNote Setup Guide

## Quick Setup (5 minutes)

### 1. Choose Your GUI

**Rust GUI (Recommended - 6x faster)**
```bash
cd rustgui
npm install
npm run tauri:dev
```

**Python GUI (Original)**
```bash
cd GUI
pip install -r requirements.txt
python main.py
```

### 2. Get API Keys

**Required:**
- Anthropic: https://console.anthropic.com/
- OR OpenAI: https://platform.openai.com/

**Optional (audio):**
- Deepgram: https://console.deepgram.com/

### 3. Configure

Settings → Enter API keys → Save

---

## Platform Prerequisites

### Windows
```powershell
winget install Rustlang.Rustup OpenJS.NodeJS.LTS Microsoft.EdgeWebView2Runtime
cargo install tauri-cli --version "^2.0.0"
```

### macOS
```bash
brew install rust node
cargo install tauri-cli --version "^2.0.0"
xcode-select --install
```

---

## Troubleshooting

**Rust: linker not found** → Install Visual Studio Build Tools  
**macOS: Screen capture fails** → Grant screen recording permission  
**Audio not working** → Check microphone permissions

See README.md for detailed documentation.
