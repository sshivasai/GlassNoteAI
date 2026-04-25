# GlassNote

Real-time technical meeting assistance. Invisible to screen share, taskbar, Alt+Tab, and Task Manager.

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Add API keys
Run the app → right-click tray icon → Settings → API Keys

- **Anthropic key** — for Claude (problem solving)
- **OpenAI key** — for Whisper transcription (meeting audio mode)
  - You only need OpenAI if you use `Ctrl+Shift+I` audio mode
  - If you only use screenshot modes, Anthropic key alone is enough

### 3. Enable WASAPI Loopback (for audio mode)
For `Ctrl+Shift+I` to capture the other person's voice from Zoom/Meet:

1. Right-click speaker icon → Sound settings → More sound settings
2. Recording tab → right-click empty area → Show Disabled Devices
3. Enable **Stereo Mix** (or "What U Hear")
4. Set as default recording device

If Stereo Mix is unavailable, the app falls back to your microphone.

---

## Run

```bash
python main.py
```

Or after building:
```bash
dist\GlassNote.exe
```

The app appears **only** as a tray icon in the bottom-right corner.
No taskbar entry. No Alt+Tab entry.

---

## Usage

### Starting a session
1. Right-click tray icon → **New Session**
2. Fill in: Company, Job Description, Resume (optional), Extra instructions
3. Select model and language → **Create Session**
4. Pill toolbar appears (invisible to screen share)

### During the meeting

| Hotkey | Action |
|---|---|
| `Ctrl+Shift+C` | Capture screenshot → add to queue |
| `Ctrl+Shift+S` | Solve all queued screenshots |
| `Ctrl+Shift+A` | Instant capture + solve (one shot) |
| `Ctrl+Shift+I` | Start / Stop audio recording → auto-answer |
| `Ctrl+Shift+H` | Toggle answer overlay visibility |
| `Ctrl+Shift+X` | Clear screenshot queue |
| `Ctrl+Shift+[` | Previous answer in history |
| `Ctrl+Shift+]` | Next answer in history |
| `Ctrl+Shift+↑↓←→` | Move overlay position |
| `Ctrl+Shift+Q` | End session |

### Typical workflow

**Coding problem (manual):**
```
1. Ctrl+Shift+C  — capture problem statement
2. Ctrl+Shift+C  — capture examples / constraints (optional)
3. Ctrl+Shift+S  — solve → answer streams into overlay
```

**Coding problem (instant):**
```
Ctrl+Shift+A  — single shot: capture + solve immediately
```

**Spoken meeting question:**
```
1. Ctrl+Shift+I  — start recording (other person speaks)
2. Ctrl+Shift+I  — stop → Whisper transcribes → LLM answers
```

---

## Build (standalone .exe)

```bash
pip install pyinstaller
python build.py
```

Output: `dist/GlassNote.exe`

The exe shows as **"Windows Audio Endpoint Builder"** in Task Manager.

---

## Invisibility

| Detection method | Status |
|---|---|
| Screen share (Zoom, Meet, Teams) | ✅ Invisible |
| OBS / screen recording | ✅ Invisible |
| Screenshots | ✅ Invisible |
| Taskbar | ✅ Hidden |
| Alt+Tab switcher | ✅ Hidden |
| Task Manager → Apps | ✅ Not listed |
| Task Manager → Details | ✅ Disguised as system service |

---

## Settings

Right-click tray → Settings:

- **API Keys** — Anthropic + OpenAI
- **Models** — Claude or GPT, model selection, max tokens
- **Overlay** — opacity (40–100%)
- **Audio** — source (system/mic/both), auto-answer toggle, silence threshold
- **Capture** — auto-capture toggle, interval (seconds)

---

## Project structure

```
glassnote/
├── main.py                    Entry point
├── app_controller.py          Central coordinator
├── requirements.txt
├── build.py                   Packaging script
├── glassnote.spec             PyInstaller spec
│
├── session/
│   ├── manager.py             Session state + system prompt builder
│   ├── setup_ui.py            2-step session creation UI
│   └── resume_parser.py       PDF/DOCX text extraction (local)
│
├── capture/
│   ├── screenshot.py          mss screen capture → base64
│   ├── queue.py               Thread-safe screenshot queue
│   ├── diff.py                Perceptual hash diff detection
│   └── auto_watcher.py        Auto-capture on screen change
│
├── audio/
│   ├── recorder.py            WASAPI loopback + microphone capture
│   ├── transcriber.py         OpenAI Whisper API transcription
│   └── pipeline.py            QThread: record → transcribe → LLM
│
├── llm/
│   ├── client.py              Unified Anthropic + OpenAI streaming client
│   ├── streamer.py            QThread streaming worker
│   └── prompts.py             System prompt templates
│
├── overlay/
│   ├── pill.py                Floating control bar
│   └── answer.py              Markdown answer overlay with history
│
├── hotkeys/
│   └── manager.py             Global hotkey registration
│
├── settings/
│   ├── config.py              JSON config load/save
│   └── ui.py                  Settings panel UI
│
└── utils/
    ├── window_hide.py         WDA_EXCLUDEFROMCAPTURE
    ├── process_hide.py        Task Manager disguise
    └── tray.py                System tray icon + menu
```