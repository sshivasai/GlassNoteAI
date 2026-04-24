# GlassNote

> **The invisible AI assistant for technical interviews and meetings — completely hidden from screen sharing.**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-15-000000?style=flat-square&logo=next.js&logoColor=white)](https://nextjs.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=flat-square&logo=windows&logoColor=white)](https://microsoft.com/windows)

---

GlassNote is a real-time AI assistant that runs as a **hidden system-tray application** on Windows. It listens to meeting audio, captures screen content, and delivers AI-generated answers through a transparent overlay that is **completely invisible to Zoom, Teams, Google Meet, and OBS**. The process disguises itself as `"Windows Audio Endpoint Builder"` in Task Manager — no one will know it's running.

> ⚠️ **Windows only.** GlassNote uses Windows-exclusive APIs (`WASAPI` loopback, `WDA_EXCLUDEFROMCAPTURE`) that are not available on macOS or Linux.

---

## ✨ Features

### 🧠 AI Capabilities

- **Screenshot Solve** — Queue one or more screenshots of a coding problem, then dispatch to an LLM for a full structured solution (problem type, approach, code, complexity, edge cases)
- **Instant Analyze** — One-shot screen capture + immediate LLM analysis
- **Meeting Mode** — Continuous real-time audio transcription; auto-dispatches to LLM when silence is detected or end-of-turn is signaled
- **Smart Answering** — Uses STT provider's end-of-turn signal to dispatch immediately, reducing latency by 100–400 ms
- **Answer History** — Browse previous Q&A pairs within a session using hotkeys
- **Conversation Context** — Last 3 Q&A pairs passed as message history for contextual continuity

### 🖥️ Screen Capture

- Full-screen capture via `mss`
- **Region capture** — Define a specific screen region to monitor
- **Auto-capture watcher** — Automatically captures when screen content changes beyond a configurable diff threshold
- Smart format selection: PNG for text-heavy screens, JPEG for diagrams (~40% smaller payload)
- Images resized to 768 px max width (fits single OpenAI vision tile, ~2 s faster TTFT)

### 🎙️ Audio Pipeline

- **Dual-stream architecture**: Stream A captures meeting audio (system loopback or mic); Stream B is a separate mic-only voice activity gate
- **WASAPI loopback** — Captures system audio to hear the other person on Zoom/Meet
- **STT Providers**: Deepgram (nova-3, nova-2) and OpenAI Realtime (gpt-4o-mini-transcribe, gpt-4o-transcribe)
- Configurable silence threshold (default 0.8 s)
- Partial transcript streaming to the pill ticker UI in real time

### ⚡ LLM Integration

- **Providers**: Anthropic (Claude Haiku 4.5, Sonnet 4.5, Opus 4.5) and OpenAI (GPT-4o, GPT-4o Mini, GPT-4.1, GPT-4.1 Mini, GPT-4 Turbo, o1, o1-mini, GPT-5.4 family)
- **Cerebras** support via proxy (ultra-fast inference)
- **Auto model routing** — Automatically selects fast/balanced/best model based on question complexity
- **Proxy mode (SaaS)** — Routes LLM/STT calls through `api.glassnote.ai`; no provider API keys needed
- **BYOK mode** — Direct calls to Anthropic/OpenAI using your own API keys; data never touches GlassNote servers
- **Anthropic prompt caching** — Reduces costs on repeated system prompts
- **Response cache** — In-memory LRU cache (50 entries, 30-min TTL) for identical queries
- **HTTP/2 connection pooling** — Persistent pools with keepalive heartbeat to all LLM providers
- **Speculative connection pre-warming** — TCP+TLS handshakes initiated on session start before first query
- Streaming token-by-token response delivery to overlay

### 🗂️ Session Management

- **Session setup wizard** — Enter company name, job description, resume (PDF/DOCX upload), extra instructions, model/language selection
- **Resume parsing** — Local PDF (PyMuPDF) and DOCX (python-docx) text extraction; never sent to external servers
- **Personalized system prompt** — Custom LLM system prompt incorporating resume, company, JD, and custom instructions
- **Crash recovery** — Session state persisted to `~/.glassnote/session_state.json`; recovered on next launch if crash detected
- **Usage reporting** — Session stats reported to backend on session end (async, non-blocking)

---

## 🏗️ Architecture

GlassNote is a three-component system:

```
┌─────────────────────────────────────────────────────────────────┐
│                        GlassNote System                         │
│                                                                 │
│  ┌──────────────────┐    ┌──────────────────┐    ┌───────────┐  │
│  │   GUI Client     │    │  Backend API     │    │  Website  │  │
│  │                  │    │                  │    │           │  │
│  │  Python 3.12     │───▶│  FastAPI         │    │  Next.js  │  │
│  │  PyQt6           │    │  PostgreSQL 16   │    │  15       │  │
│  │  Windows Only    │◀───│  Docker/Railway  │    │  Tailwind │  │
│  │                  │    │                  │    │  CSS      │  │
│  │  • Overlay UI    │    │  • LLM Proxy     │    │           │  │
│  │  • Audio capture │    │  • STT Proxy     │    │  • Landing│  │
│  │  • Screen capture│    │  • Auth/JWT      │    │  • Pricing│  │
│  │  • Hotkeys       │    │  • Billing       │    │  • Dash-  │  │
│  │  • Stealth mode  │    │  • Sessions      │    │    board  │  │
│  └──────────────────┘    └──────────────────┘    └───────────┘  │
│                                                                 │
│         ┌──────────────────────────────────────┐               │
│         │           External AI APIs           │               │
│         │  Anthropic • OpenAI • Deepgram        │               │
│         │  Cerebras (via proxy)                 │               │
│         └──────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

### Backend API Endpoints

| Route | Description |
|---|---|
| `POST /v1/proxy/anthropic` | Zero-copy SSE proxy → Anthropic |
| `POST /v1/proxy/openai` | Zero-copy SSE proxy → OpenAI |
| `POST /v1/proxy/cerebras` | Zero-copy SSE proxy → Cerebras |
| `GET /v1/proxy/stt-credentials` | STT key distribution |
| `POST /api/auth/*` | JWT auth, Google OAuth |
| `POST /api/sessions/*` | Session start/end, quota check |
| `GET /api/usage/*` | Usage metering |
| `POST /api/billing/*` | Stripe checkout + webhooks |
| `POST /api/notifications/*` | Admin broadcast notifications |
| `GET /api/public/*` | Pricing, testimonials (public) |

---

## 🛠️ Tech Stack

### GUI Client

| Category | Technology |
|---|---|
| Language / Framework | Python 3.12, PyQt6 6.6+ |
| Screen Capture | `mss`, `Pillow` |
| HTTP Client | `httpx[http2]` |
| LLM SDKs | `anthropic`, `openai` |
| Audio | `sounddevice` (WASAPI loopback + mic) |
| Audio Processing | `numpy`, `scipy` (resampling) |
| STT | `deepgram-sdk`, `websockets` |
| Hotkeys | `keyboard` |
| Document Parsing | `PyMuPDF` (PDF), `python-docx` (DOCX) |
| Windows APIs | `pywin32` |
| Build | `pyinstaller` → `.exe` |

### Backend

| Category | Technology |
|---|---|
| Language / Framework | Python 3.12, FastAPI 0.110+ |
| Database | PostgreSQL 16, SQLAlchemy 2.0 (async), asyncpg, Alembic |
| Auth | JWT, Google OAuth, bcrypt/passlib |
| Billing | Stripe 8.0+ |
| Email | SendGrid |
| HTTP Client | `httpx[http2]` (zero-copy SSE proxy) |
| Deployment | Docker, Railway |

### Website

| Category | Technology |
|---|---|
| Language / Framework | TypeScript, Next.js 15 (App Router) |
| Styling | Tailwind CSS, Lucide React |
| Components | shadcn/ui-style component library |

### AI APIs

| Provider | Models / Usage |
|---|---|
| **Anthropic** | Claude Haiku 4.5, Sonnet 4.5, Opus 4.5 |
| **OpenAI** | GPT-4o, GPT-4.1, GPT-4 Turbo, o1, o1-mini, GPT-5.4 family; Realtime API for STT |
| **Deepgram** | nova-3, nova-2 (STT) |
| **Cerebras** | Ultra-fast inference via proxy |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker Desktop (for PostgreSQL)
- Git

---

### Backend Setup

```bash
cd backend

# 1. Configure environment
copy .env.example .env
# Edit .env and fill in required values (see below)

# 2. Start PostgreSQL
docker compose up -d

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run migrations
alembic upgrade head

# 5. Start the API server
uvicorn app.main:app --reload --port 8000
```

**Required environment variables:**

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `JWT_SECRET` | Secret key for JWT signing |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `DEEPGRAM_API_KEY` | Deepgram API key |

**Optional environment variables:**

`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `SENDGRID_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `ADMIN_SECRET`

---

### GUI Client Setup

```bash
cd GUI

# Install dependencies
pip install -r requirements.txt

# Launch the app
python main.py
```

The app will appear as a system tray icon. Right-click → **Settings → API Keys** to enter your keys (BYOK mode) or log in to use the proxy (SaaS mode).

**Audio Setup (for Meeting Mode):**

1. Right-click the speaker icon → **Sound settings → More sound settings**
2. Go to the **Recording** tab → right-click → **Show Disabled Devices**
3. Enable **Stereo Mix** → Set as default recording device

---

### Website Setup

```bash
cd website

npm install
npm run dev
# Open http://localhost:3000
```

---

### Build Standalone `.exe`

```bash
cd GUI

python build.py
# Output: dist/GlassNote.exe
```

The resulting executable is self-contained and disguises itself as `"Windows Audio Endpoint Builder"` in Task Manager.

---

## ⌨️ Hotkeys

| Hotkey | Action |
|---|---|
| `Ctrl+Shift+C` | Capture screenshot → add to queue |
| `Ctrl+Shift+S` | Solve all queued screenshots |
| `Ctrl+Shift+A` | Instant capture + analyze |
| `Ctrl+Shift+I` | Toggle meeting mode (start/stop audio) |
| `Ctrl+Shift+H` | Toggle answer overlay visibility |
| `Ctrl+Shift+X` | Clear screenshot queue |
| `Ctrl+Shift+[` | Previous answer in history |
| `Ctrl+Shift+]` | Next answer in history |
| `Ctrl+Shift+↑/↓/←/→` | Move overlay position |
| `Ctrl+Shift+Q` | End session |

---

## 🕵️ Stealth & Privacy

### Invisibility

GlassNote uses the `WDA_EXCLUDEFROMCAPTURE` Windows API flag on all overlay windows. This is the same mechanism Windows uses to protect DRM content — it causes the overlay to render as a **black/transparent rectangle** in any screen capture API, including those used by Zoom, Teams, Google Meet, and OBS.

| Detection Method | Status |
|---|---|
| Screen share (Zoom, Meet, Teams) | ✅ Invisible |
| OBS / screen recording | ✅ Invisible |
| Screenshots (PrintScreen, Snipping Tool) | ✅ Invisible |
| Taskbar | ✅ Hidden |
| Alt+Tab switcher | ✅ Hidden |
| Task Manager → Apps | ✅ Not listed |
| Task Manager → Details | ✅ Disguised as "Windows Audio Endpoint Builder" |

### Privacy (BYOK Mode)

In **BYOK (Bring Your Own Keys)** mode:

- All LLM and STT calls go **directly** from your machine to Anthropic/OpenAI/Deepgram
- Your resume, job description, and conversation data **never touch GlassNote servers**
- Resume parsing (PDF/DOCX) is performed **100% locally** using PyMuPDF and python-docx
- Only anonymous session metadata (start time, duration, model used) is reported to the backend

---

## 💳 Pricing

| Plan | Price | Sessions | Duration | Models | STT |
|---|---|---|---|---|---|
| **Free** | $0 | 5 lifetime | 30 min/session | Basic (Haiku, GPT-4o Mini) | Deepgram only |
| **Base** | $29/mo | 15/month | 60 min/session | Standard (Sonnet, GPT-4o, GPT-4.1) | Deepgram only |
| **Unlimited** | $49/mo | Unlimited | No limit | All models (+ Opus, o1, GPT-5.4) | Deepgram + OpenAI Realtime |
| **BYOK** | $99 one-time | Unlimited | No limit | All models | Deepgram + OpenAI Realtime |

> **BYOK** = Bring Your Own Keys. Pay once, use forever. Your API keys, your data.

---

## 📁 Project Structure

<details>
<summary>Click to expand full project structure</summary>

```
Proj_AI/
│
├── README.md
├── SETUP.md
├── .gitignore
│
├── GUI/                          # Python desktop client (Windows)
│   ├── main.py                   # Entry point
│   ├── app_controller.py         # Central application controller
│   ├── build.py                  # PyInstaller build script
│   ├── requirements.txt
│   ├── pricing_config.py
│   │
│   ├── api/                      # Backend API clients
│   │   ├── auth_client.py
│   │   ├── login_ui.py
│   │   ├── notifications_client.py
│   │   ├── pricing_client.py
│   │   └── usage_reporter.py
│   │
│   ├── audio/                    # Audio capture & STT
│   │   ├── pipeline.py           # Dual-stream audio pipeline
│   │   ├── recorder.py           # WASAPI loopback recorder
│   │   ├── resample_utils.py
│   │   ├── stt_deepgram.py       # Deepgram STT provider
│   │   ├── stt_openai_realtime.py# OpenAI Realtime STT provider
│   │   └── voice_gate.py         # Mic voice activity detection
│   │
│   ├── capture/                  # Screen capture
│   │   ├── auto_watcher.py       # Auto-capture on screen change
│   │   ├── diff.py               # Screen diff detection
│   │   ├── queue.py              # Screenshot queue
│   │   ├── region_selector.py    # Region selection UI
│   │   └── screenshot.py         # mss-based capture
│   │
│   ├── hotkeys/                  # Global hotkey manager
│   │   └── manager.py
│   │
│   ├── llm/                      # LLM integration
│   │   ├── client.py             # HTTP/2 LLM client with caching
│   │   ├── prompts.py            # System & user prompt templates
│   │   └── streamer.py           # Token streaming handler
│   │
│   ├── overlay/                  # Transparent overlay UI
│   │   ├── answer.py             # Answer display overlay
│   │   ├── pill.py               # Pill/ticker overlay
│   │   └── ticker.py             # Partial transcript ticker
│   │
│   ├── session/                  # Session management
│   │   ├── manager.py            # Session state & crash recovery
│   │   ├── resume_parser.py      # Local PDF/DOCX parser
│   │   └── setup_ui.py           # Session setup wizard UI
│   │
│   ├── settings/                 # App settings
│   │   ├── config.py             # Config persistence
│   │   └── ui.py                 # Settings dialog UI
│   │
│   └── utils/                    # Utilities
│       ├── models.py             # Model definitions & routing
│       ├── perf.py               # Performance helpers
│       ├── process_hide.py       # Task Manager disguise
│       ├── theme.py              # UI theme
│       ├── tray.py               # System tray icon
│       └── window_hide.py        # WDA_EXCLUDEFROMCAPTURE
│
├── backend/                      # FastAPI backend
│   ├── requirements.txt
│   ├── docker-compose.yml
│   ├── Dockerfile
│   ├── railway.toml
│   │
│   ├── app/
│   │   ├── main.py               # FastAPI app entry point
│   │   ├── config.py             # Environment config
│   │   ├── pricing_config.py     # Plan definitions
│   │   │
│   │   ├── models/
│   │   │   └── database.py       # SQLAlchemy models
│   │   │
│   │   ├── routers/              # API route handlers
│   │   │   ├── auth.py
│   │   │   ├── billing.py
│   │   │   ├── notifications.py
│   │   │   ├── proxy.py          # Zero-copy SSE proxy
│   │   │   ├── public.py
│   │   │   ├── sessions.py
│   │   │   └── usage.py
│   │   │
│   │   └── services/
│   │       ├── auth.py
│   │       └── database.py
│   │
│   └── alembic/                  # Database migrations
│       └── versions/
│
└── website/                      # Next.js marketing site
    ├── package.json
    ├── next.config.ts
    ├── tailwind.config (via postcss)
    │
    └── src/
        ├── app/                  # Next.js App Router pages
        │   ├── page.tsx          # Landing page
        │   ├── layout.tsx
        │   ├── login/
        │   ├── signup/
        │   └── dashboard/        # User dashboard
        │       ├── page.tsx
        │       ├── billing/
        │       ├── settings/
        │       └── usage/
        │
        └── components/           # React components
            ├── hero.tsx
            ├── features.tsx
            ├── pricing.tsx
            ├── how-it-works.tsx
            ├── testimonials.tsx
            ├── cta.tsx
            ├── header.tsx
            ├── footer.tsx
            └── auth/
```

</details>

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Commit your changes: `git commit -m 'feat: add some feature'`
4. Push to the branch: `git push origin feature/your-feature-name`
5. Open a Pull Request

Please ensure your code follows the existing style and that any new features are covered by tests where applicable.

---

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---

<div align="center">

**GlassNote** — *Stay focused. Stay invisible. Stay ahead.*

</div>
