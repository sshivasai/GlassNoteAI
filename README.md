# GlassNote AI


<div align="center">
www.glassnoteai.com
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org/)

**Speak confidently in every meeting with real-time AI assistance**

[Features](#features) • [Architecture](#architecture) • [Setup](SETUP.md) • [Contributing](#contributing) • [License](#license)

</div>

---

## 🚀 What is GlassNote?

GlassNote is an **open-source AI meeting assistant** that provides real-time answers through an invisible transparent overlay. It helps you communicate clearly and confidently in meetings by:

- 🎤 **Real-time transcription** of meeting audio (Deepgram, OpenAI Whisper, GPT-4o Realtime)
- 🖥️ **Intelligent screen capture** that detects and analyzes content automatically
- 🤖 **AI-powered responses** from Claude (Opus, Sonnet, Haiku) or GPT models (4o, o1, o3)
- 👻 **Completely invisible** to screen sharing tools (Zoom, Teams, Meet, etc.)
- ⚡ **187ms first token** with Cerebras models and optimized streaming architecture
- 🔐 **100% privacy** with BYOK (Bring Your Own Keys) mode

### Not a Bot, Just Confidence

GlassNote doesn't sit in your meeting as a bot. It's a personal assistant that only you can see, helping you speak more confidently and clearly without anyone knowing.

---

## ✨ Features

### Core Capabilities

- **Multi-model Support**: Choose between Claude Opus, Sonnet, Haiku, GPT-4o, GPT-4, o1, o3, and more
- **Auto Model Routing**: Intelligent model selection based on query complexity
- **Blazing Fast**: 187ms TTFT (Time To First Token) with Cerebras models
- **Screen Intelligence**: Automatically captures and analyzes screen content for context
- **Voice Gate**: Only processes audio when someone is speaking (reduces API costs)
- **Stealth Mode**: Hardware overlay bypass makes it invisible to all screen capture tools
- **Session Management**: Save, resume, and export meeting sessions
- **Hotkey Support**: Trigger responses instantly with customizable keyboard shortcuts
- **BYOK Mode**: Use your own API keys for unlimited access at zero platform cost

### Privacy & Security

- **Open Source**: Full transparency — audit every line of code
- **Self-Hostable**: Run the entire backend on your own infrastructure
- **BYOK Mode**: Your data never touches our servers when using your own API keys
- **Local Audio Processing**: All transcription happens locally or directly with your STT provider
- **No Meeting Bot**: GlassNote doesn't join meetings — it's invisible to other participants

---

## 🏗️ Architecture

GlassNote consists of three main components:

```
┌─────────────────────────────────────────────────────────────┐
│                      GlassNote Stack                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────┐ │
│  │   GUI Client     │  │  Backend API     │  │ Website  │ │
│  │   (PyQt6)        │  │  (FastAPI)       │  │ (Next.js)│ │
│  │                  │  │                  │  │          │ │
│  │  • Overlay       │  │  • Auth          │  │  • Docs  │ │
│  │  • Audio Pipeline│  │  • Proxy         │  │  • Dash  │ │
│  │  • Screen Capture│  │  • Billing       │  │  • Admin │ │
│  │  • Hotkeys       │  │  • Analytics     │  │          │ │
│  │  • Session Mgmt  │  │  • Rate Limiting │  │          │ │
│  └──────────────────┘  └──────────────────┘  └──────────┘ │
│           │                      │                    │     │
│           └──────────────────────┴────────────────────┘     │
│                              │                              │
└──────────────────────────────┼──────────────────────────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
         ┌──────▼──────┐            ┌────────▼────────┐
         │  STT APIs   │            │   LLM APIs      │
         │  • Deepgram │            │   • Claude      │
         │  • OpenAI   │            │   • GPT         │
         │  • Whisper  │            │   • Cerebras    │
         └─────────────┘            └─────────────────┘
```

### Component Breakdown

#### 1. **GUI Client** (`/GUI`)
- **Framework**: PyQt6
- **Key Features**:
  - Transparent overlay window with custom rendering
  - Real-time audio capture and transcription pipeline
  - Automatic screen content detection and capture
  - Hotkey management and session control
  - Crash recovery and error handling
  - System tray integration

#### 2. **Backend API** (`/backend`)
- **Framework**: FastAPI + PostgreSQL + SQLAlchemy
- **Key Features**:
  - User authentication (JWT, Google OAuth)
  - API proxy for LLM providers (with HTTP/2 connection pooling)
  - Usage tracking and billing (Stripe integration)
  - Rate limiting (slowapi)
  - Pricing configuration management
  - Email notifications (SendGrid)

#### 3. **Website** (`/website`)
- **Framework**: Next.js 15 + React + TailwindCSS
- **Key Features**:
  - Landing page with live pricing data
  - User dashboard and billing portal
  - Authentication flow (login/signup)
  - Usage analytics and session history

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for website)
- **PostgreSQL 15+** (for backend)
- **Windows 10/11** (for GUI client)

### Installation

See [SETUP.md](SETUP.md) for detailed installation instructions for each component.

**TLDR**:
```bash
# 1. Backend
cd backend
pip install -r requirements.txt
cp .env.example .env  # Configure your environment
alembic upgrade head
uvicorn app.main:app --reload

# 2. Website
cd website
npm install
npm run dev

# 3. GUI Client
cd GUI
pip install -r requirements.txt
python main.py
```

---

## 📊 Performance

GlassNote is optimized for **ultra-low latency** to provide instant responses:

| Metric | Value | Details |
|--------|-------|---------|
| **TTFT (First Token)** | 187ms | Cerebras models with HTTP/2 pooling |
| **Audio Latency** | ~42ms | System audio capture + VAD |
| **Screen Capture** | ~100ms | Screenshot + diff detection |
| **Overlay FPS** | 60fps | Hardware-accelerated rendering |
| **Memory Usage** | ~124MB | Lightweight PyQt6 client |

### Optimization Techniques

1. **HTTP/2 Connection Pooling**: Reuses connections to LLM providers
2. **Speculative Pre-warming**: Keeps connections warm during meetings
3. **Zero-copy Streaming**: Direct byte streaming from API to overlay
4. **Voice Activity Detection**: Only processes audio when speech is detected
5. **Diff-based Screen Capture**: Only captures changed regions
6. **Prompt Caching**: Caches repeated context (Claude, GPT-4o)

---

## 🔐 Privacy & BYOK Mode

GlassNote prioritizes your privacy:

### BYOK (Bring Your Own Keys)
When you use your own API keys:
- ✅ Your data goes **directly** to your STT/LLM provider (Deepgram, OpenAI, Anthropic)
- ✅ **No logs** are stored on GlassNote servers
- ✅ **No usage tracking** (unless you opt in for analytics)
- ✅ **Zero platform fees** — pay only your provider's API costs

### GlassNote Cloud
If you use GlassNote Cloud (managed keys):
- Session metadata (duration, model used) is stored for billing
- Audio/transcripts are **never** stored
- Screen captures are **never** uploaded
- All data is encrypted in transit and at rest

---

## 🛠️ Configuration

### GUI Settings (`GUI/settings/config.py`)
```python
{
    "glassnote_api_url": "http://localhost:8000",
    "process_disguise_name": "Windows Audio Endpoint Builder",
    "hotkey_trigger": "ctrl+space",
    "theme": "dark",
    "byok_mode": true,
    "api_keys": {
        "anthropic": "sk-ant-...",
        "openai": "sk-...",
        "deepgram": "..."
    }
}
```

### Backend Environment (`.env`)
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/glassnote
SECRET_KEY=your-secret-key-here
STRIPE_SECRET_KEY=sk_test_...
SENDGRID_API_KEY=SG...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
```

---

## 🤝 Contributing

We welcome contributions! Here's how you can help:

1. **Report Bugs**: Open an issue with detailed reproduction steps
2. **Suggest Features**: Describe your use case and proposed solution
3. **Submit PRs**: Fork, create a branch, and submit a pull request
4. **Improve Docs**: Help us make the documentation clearer

### Development Setup

See [SETUP.md](SETUP.md) for detailed development environment setup.

---

## 📝 License

GlassNote is open source under the [MIT License](LICENSE).

---

## 🙏 Acknowledgments

GlassNote is built with amazing open-source technologies:

- **AI Models**: [Anthropic Claude](https://anthropic.com), [OpenAI GPT](https://openai.com), [Cerebras](https://cerebras.ai)
- **STT**: [Deepgram](https://deepgram.com), [OpenAI Whisper](https://openai.com/research/whisper)
- **Frameworks**: [FastAPI](https://fastapi.tiangolo.com), [Next.js](https://nextjs.org), [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
- **Infrastructure**: [PostgreSQL](https://postgresql.org), [Stripe](https://stripe.com), [SendGrid](https://sendgrid.com)

---

## 📧 Support

- **Email**: [support@glassnote.ai](mailto:support@glassnote.ai)
- **GitHub Issues**: [Report a bug](https://github.com/sshivasai/GlassNoteAI/issues)
- **Discussions**: [Join the conversation](https://github.com/sshivasai/GlassNoteAI/discussions)

---

<div align="center">

**Made with ❤️ by the GlassNote**

[Website](https://glassnoteai.com) • [GitHub](https://github.com/sshivasai/GlassNoteAI) • [Documentation](https://api.glassnoteai.com/docs)

</div>
