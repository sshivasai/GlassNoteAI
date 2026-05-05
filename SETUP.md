# GlassNote Setup Guide

This guide covers installation and configuration for all three GlassNote components: **Backend**, **Website**, and **GUI Client**.

---

## 📋 Table of Contents

- [System Requirements](#system-requirements)
- [Backend Setup](#backend-setup)
- [Website Setup](#website-setup)
- [GUI Client Setup](#gui-client-setup)
- [API Keys Configuration](#api-keys-configuration)
- [Docker Deployment](#docker-deployment)
- [Troubleshooting](#troubleshooting)

---

## 🖥️ System Requirements

### Backend
- **OS**: Linux, macOS, or Windows
- **Python**: 3.11 or higher
- **PostgreSQL**: 15 or higher
- **RAM**: 512MB minimum (2GB recommended)
- **Disk**: 1GB free space

### Website
- **OS**: Linux, macOS, or Windows
- **Node.js**: 18 or higher
- **RAM**: 512MB minimum
- **Disk**: 500MB free space

### GUI Client
- **OS**: Windows 10/11 (64-bit)
- **Python**: 3.11 or higher
- **RAM**: 2GB minimum
- **Screen**: 1920x1080 or higher recommended
- **Audio**: Microphone or system audio routing (Stereo Mix / VoiceMeeter)

---

## 🔧 Backend Setup

The backend is a FastAPI application that handles authentication, API proxying, billing, and usage tracking.

### 1. Clone the Repository

```bash
git clone https://github.com/sshivasai/GlassNoteAI.git
cd GlassNoteAI/backend
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure PostgreSQL

**Install PostgreSQL** (if not already installed):
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install postgresql postgresql-contrib

# macOS (Homebrew)
brew install postgresql@15
brew services start postgresql@15

# Windows
# Download from: https://www.postgresql.org/download/windows/
```

**Create Database**:
```bash
# Connect to PostgreSQL
psql -U postgres

# In psql prompt
CREATE DATABASE glassnote;
CREATE USER glassnote_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE glassnote TO glassnote_user;
\q
```

### 5. Configure Environment Variables

Create a `.env` file in the `backend` directory:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```bash
# ── Database ───────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://glassnote_user:your_secure_password@localhost/glassnote

# ── Application ────────────────────────────────────────────
SECRET_KEY=your-secret-key-here-use-python-secrets-token-urlsafe-32
ENVIRONMENT=development

# ── Auth ───────────────────────────────────────────────────
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# ── Google OAuth (optional) ────────────────────────────────
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# ── Stripe (for billing) ───────────────────────────────────
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID_BASE=price_...
STRIPE_PRICE_ID_UNLIMITED=price_...

# ── SendGrid (for emails) ──────────────────────────────────
SENDGRID_API_KEY=SG...
SENDGRID_FROM_EMAIL=noreply@glassnote.ai

# ── CORS ───────────────────────────────────────────────────
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# ── Frontend URL ───────────────────────────────────────────
FRONTEND_URL=http://localhost:3000
```

**Generate Secret Keys**:
```python
import secrets
print(secrets.token_urlsafe(32))  # Run this twice for SECRET_KEY and JWT_SECRET_KEY
```

### 6. Run Database Migrations

```bash
# Initialize Alembic (first time only)
alembic upgrade head
```

### 7. Start the Backend

```bash
# Development mode (with hot reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

The backend will be available at: `http://localhost:8000`

API documentation: `http://localhost:8000/docs` (Swagger UI)

---

## 🌐 Website Setup

The website is a Next.js 15 application with the App Router.

### 1. Navigate to Website Directory

```bash
cd website
```

### 2. Install Dependencies

```bash
npm install
# or
yarn install
# or
pnpm install
```

### 3. Configure Environment Variables

Create a `.env.local` file:

```bash
# ── Backend API ────────────────────────────────────────────
NEXT_PUBLIC_API_URL=http://localhost:8000

# ── Google OAuth (must match backend) ──────────────────────
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your-google-client-id

# ── Stripe (public key) ────────────────────────────────────
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_...

# ── Environment ────────────────────────────────────────────
NEXT_PUBLIC_ENV=development
```

### 4. Start the Development Server

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
```

The website will be available at: `http://localhost:3000`

### 5. Build for Production

```bash
npm run build
npm run start
```

---

## 🖥️ GUI Client Setup

The GUI client is a PyQt6 desktop application for Windows.

### 1. Navigate to GUI Directory

```bash
cd GUI
```

### 2. Create Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Settings

Edit `GUI/settings/config.py` or use the GUI settings dialog:

```python
{
    "glassnote_api_url": "http://localhost:8000",
    "process_disguise_name": "Windows Audio Endpoint Builder",
    "hotkey_trigger": "ctrl+space",
    "theme": "dark",
    "byok_mode": true,
    "api_keys": {
        "anthropic": "",
        "openai": "",
        "deepgram": ""
    }
}
```

### 5. Audio Setup (Important!)

**Windows requires special audio routing to capture system audio:**

#### Option 1: Enable Stereo Mix (Easiest)
1. Right-click the sound icon in the system tray
2. Select "Sounds" → "Recording" tab
3. Right-click in the empty area → "Show Disabled Devices"
4. Right-click "Stereo Mix" → Enable
5. Set as default recording device

#### Option 2: VoiceMeeter (Recommended for Advanced Users)
1. Download VoiceMeeter: https://vb-audio.com/Voicemeeter/
2. Install and configure virtual audio routing
3. Set VoiceMeeter Output as the recording device in GlassNote

#### Test Audio Capture
```bash
python audio/stereo_mix_checker.py
```

### 6. Run the GUI Client

```bash
python main.py
```

The application will start in the system tray. Right-click the tray icon to start a session.

### 7. Build Executable (Optional)

To create a standalone `.exe`:

```bash
python build.py
```

The executable will be in `dist/GlassNote.exe` (~50MB).

---

## 🔑 API Keys Configuration

GlassNote supports two modes:

### 1. BYOK (Bring Your Own Keys) — Free Forever

Use your own API keys for unlimited access at zero platform cost.

**Required API Keys**:

#### Anthropic (Claude)
1. Sign up at: https://console.anthropic.com
2. Create an API key
3. Add to GUI settings: `api_keys.anthropic`

#### OpenAI (GPT)
1. Sign up at: https://platform.openai.com
2. Create an API key
3. Add to GUI settings: `api_keys.openai`

#### Deepgram (STT)
1. Sign up at: https://console.deepgram.com
2. Create an API key
3. Add to GUI settings: `api_keys.deepgram`

**Typical Costs (BYOK)**:
- Claude Sonnet: ~$3 per 1M input tokens
- GPT-4o: ~$2.50 per 1M input tokens
- Deepgram STT: ~$0.0043 per minute

**Example Session Cost**:
- 60-minute meeting
- ~10 AI queries
- Total cost: ~$0.50 - $2.00

### 2. GlassNote Cloud — Managed Keys

Use our managed API keys with simple per-session pricing.

**Plans**:
- **Free**: 5 lifetime sessions (30 min each)
- **Base**: $29/month — 15 sessions (60 min each) [Coming Soon]
- **Unlimited**: $49/month — Unlimited sessions [Coming Soon]

---

## 🐳 Docker Deployment

### Backend + Database (Docker Compose)

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: glassnote
      POSTGRES_USER: glassnote_user
      POSTGRES_PASSWORD: your_secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql+asyncpg://glassnote_user:your_secure_password@db/glassnote
      SECRET_KEY: your-secret-key
      ENVIRONMENT: production
    depends_on:
      - db
    ports:
      - "8000:8000"
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000

volumes:
  postgres_data:
```

Start services:
```bash
docker-compose up -d
```

### Website (Docker)

```dockerfile
# Dockerfile
FROM node:18-alpine

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]
```

Build and run:
```bash
docker build -t glassnote-website .
docker run -p 3000:3000 glassnote-website
```

---

## 🐛 Troubleshooting

### Backend Issues

#### "Database connection failed"
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql  # Linux
brew services list  # macOS

# Verify connection
psql -U glassnote_user -d glassnote -h localhost
```

#### "Alembic migration error"
```bash
# Reset migrations (CAUTION: deletes all data)
alembic downgrade base
alembic upgrade head
```

### Website Issues

#### "API connection failed"
- Verify backend is running: `curl http://localhost:8000/health`
- Check `NEXT_PUBLIC_API_URL` in `.env.local`
- Check CORS settings in backend `.env`

#### "Build fails with type errors"
```bash
# Clear Next.js cache
rm -rf .next
npm run build
```

### GUI Client Issues

#### "No audio input detected"
- Run `python audio/stereo_mix_checker.py` to diagnose
- Enable Stereo Mix or install VoiceMeeter
- Check that the audio device is set to "Default" in Windows sound settings

#### "Overlay not visible"
- Run as Administrator (some overlays require elevated permissions)
- Disable Windows Game Bar (may interfere with overlay)
- Check that "process_disguise_name" is set in config

#### "API key errors"
- Verify keys are valid: test at https://platform.openai.com/playground
- Check that `byok_mode: true` in settings
- Ensure keys have sufficient credits

#### "PyQt6 import errors"
```bash
# Reinstall PyQt6
pip uninstall PyQt6 PyQt6-Qt6 PyQt6-sip
pip install PyQt6
```

---

## 📚 Next Steps

1. **Configure API Keys**: Set up your [API keys](#api-keys-configuration)
2. **Test a Session**: Start the GUI and run a test meeting
3. **Deploy to Production**: Use [Docker](#docker-deployment) for easy deployment
4. **Customize Settings**: Explore `config.py` and `.env` options
5. **Join the Community**: [GitHub Discussions](https://github.com/sshivasai/GlassNoteAI/discussions)

---

## 🆘 Getting Help

- **Documentation**: [README.md](README.md)
- **Support Email**: [support@glassnote.ai](mailto:support@glassnote.ai)
- **GitHub Issues**: [Report a bug](https://github.com/sshivasai/GlassNoteAI/issues)
- **Discord**: [Join our community](#) (Coming soon)

---

<div align="center">

**Happy Meeting! 🎉**

[Back to README](README.md)

</div>
