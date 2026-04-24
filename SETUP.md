# GlassNote - Local Development Setup Guide

Complete guide to set up GlassNote on your Windows development machine.

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Detailed Setup](#detailed-setup)
4. [Configuration](#configuration)
5. [Running the Application](#running-the-application)
6. [Troubleshooting](#troubleshooting)
7. [Development Workflow](#development-workflow)

---

## 🔧 Prerequisites

### Required Software

| Software | Version | Purpose | Download Link |
|----------|---------|---------|---------------|
| **Python** | 3.12+ | Backend & GUI | [python.org](https://www.python.org/downloads/) |
| **Node.js** | 20+ | Website | [nodejs.org](https://nodejs.org/) |
| **Docker Desktop** | Latest | PostgreSQL database | [docker.com](https://www.docker.com/products/docker-desktop/) |
| **Git** | Latest | Version control | [git-scm.com](https://git-scm.com/) |

### API Keys (Optional for initial setup)

- **Anthropic API Key** - For Claude LLM (required for GUI functionality)
- **OpenAI API Key** - For Whisper STT and GPT models (optional)
- **Deepgram API Key** - For alternative STT (optional)
- **Stripe Keys** - For billing features (optional)
- **SendGrid API Key** - For email notifications (optional)

---

## 🚀 Quick Start

```bash
# 1. Verify Python version
python --version  # Should be 3.12 or higher

# 2. Install Node.js (if not installed)
# Download from: https://nodejs.org/

# 3. Start Docker Desktop
# Make sure Docker Desktop is running

# 4. Set up backend
cd backend
copy .env.example .env  # Edit this file with your configuration
docker compose up -d    # Start PostgreSQL
pip install -r requirements.txt
alembic upgrade head    # Run database migrations
uvicorn app.main:app --reload --port 8000

# 5. Set up GUI (in a new terminal)
cd GUI
pip install -r requirements.txt
python main.py

# 6. Set up website (in a new terminal)
cd website
npm install
npm run dev
```

---

## 📖 Detailed Setup

### Step 1: Verify Python Installation

```bash
python --version
```

**Expected output:** `Python 3.12.x` or higher

If Python is not installed or version is too old:
1. Download Python 3.12+ from [python.org](https://www.python.org/downloads/)
2. During installation, check "Add Python to PATH"
3. Restart your terminal after installation

### Step 2: Install Node.js

```bash
node --version
npm --version
```

**Expected output:** Node v20.x.x or higher

If Node.js is not installed:
1. Download Node.js 20 LTS from [nodejs.org](https://nodejs.org/)
2. Run the installer with default settings
3. Restart your terminal after installation

### Step 3: Verify Docker Desktop

1. Open Docker Desktop application
2. Ensure it's running (whale icon in system tray)
3. Verify installation:

```bash
docker --version
docker compose version
```

### Step 4: Backend Setup

#### 4.1 Create Environment File

Navigate to the backend directory and create a `.env` file:

```bash
cd backend
```

Create [`backend/.env`](backend/.env) with the following content (see [Configuration](#configuration) section for details):

```env
# ── App ────────────────────────────────────────────────────
APP_NAME=GlassNote API
DEBUG=true

# ── Database ───────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://glassnote:glassnote@localhost:5432/glassnote

# ── Auth ───────────────────────────────────────────────────
JWT_SECRET=your-secret-key-change-this-in-production-use-openssl-rand-hex-32
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=43200

# ── Provider API Keys ──────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-your-key-here
OPENAI_API_KEY=sk-your-key-here
DEEPGRAM_API_KEY=your-key-here

# ── Stripe (Optional) ──────────────────────────────────────
STRIPE_SECRET_KEY=sk_test_your-key-here
STRIPE_WEBHOOK_SECRET=whsec_your-key-here

# ── Email (Optional) ───────────────────────────────────────
SENDGRID_API_KEY=SG.your-key-here
FROM_EMAIL=noreply@yourdomain.com
REPLY_EMAIL=support@yourdomain.com

# ── Google OAuth (Optional) ────────────────────────────────
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret

# ── Admin ──────────────────────────────────────────────────
ADMIN_SECRET=your-admin-secret-for-admin-endpoints

# ── CORS ───────────────────────────────────────────────────
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# ── Rate Limiting ──────────────────────────────────────────
RATE_LIMIT_PER_MINUTE=60
```

#### 4.2 Start PostgreSQL Database

```bash
docker compose up -d
```

This will:
- Pull PostgreSQL 16 Alpine image
- Create a database named `glassnote`
- Expose it on `localhost:5432`
- Create a persistent volume for data

**Verify database is running:**

```bash
docker compose ps
```

You should see the `db` service with status "Up".

#### 4.3 Install Python Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- FastAPI & Uvicorn (web framework)
- SQLAlchemy & asyncpg (database)
- Alembic (migrations)
- Stripe, SendGrid (billing & email)
- And more...

#### 4.4 Run Database Migrations

```bash
alembic upgrade head
```

This creates all necessary database tables:
- `users` - User accounts
- `sessions` - Interview sessions
- `api_calls` - API usage tracking
- `usage_quotas` - Monthly limits
- `email_otps` - Email verification
- `system_notifications` - Admin broadcasts

#### 4.5 Test Backend Server

```bash
uvicorn app.main:app --reload --port 8000
```

**Expected output:**
```
[glassnote] Starting GlassNote API
[glassnote] Debug mode: True
[glassnote] Anthropic key: ✓
[glassnote] OpenAI key:    ✓
[glassnote] Initializing database...
[glassnote] Pre-warming provider connection pools (TTFT-OPT)...
[glassnote]   anthropic: ok (120ms)
[glassnote]   openai: ok (95ms)
[glassnote] ✓ Ready — accepting requests
INFO:     Uvicorn running on http://127.0.0.1:8000
```

**Test the API:**
- Open browser: http://localhost:8000
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### Step 5: GUI Setup

Open a **new terminal** window:

```bash
cd GUI
pip install -r requirements.txt
```

This installs:
- PyQt6 (UI framework)
- mss & Pillow (screen capture)
- anthropic & openai (LLM clients)
- sounddevice & numpy (audio recording)
- deepgram-sdk (STT)
- keyboard (hotkeys)
- PyMuPDF & python-docx (resume parsing)
- pywin32 (Windows APIs)

**Configure API Keys:**

On first run, the app will prompt you to enter API keys. Alternatively, you can configure them later:

1. Run the app: `python main.py`
2. Right-click the tray icon (bottom-right corner)
3. Settings → API Keys
4. Enter your Anthropic and OpenAI keys

**Test GUI:**

```bash
python main.py
```

The app runs as a system tray icon only (no window). Look for the icon in the bottom-right corner of your taskbar.

### Step 6: Website Setup

Open a **new terminal** window:

```bash
cd website
npm install
```

This installs:
- Next.js 15 (React framework)
- Tailwind CSS (styling)
- TypeScript (type safety)
- Lucide React (icons)

**Start development server:**

```bash
npm run dev
```

**Expected output:**
```
  ▲ Next.js 15.5.15
  - Local:        http://localhost:3000
  - Ready in 2.3s
```

**Test website:**
- Open browser: http://localhost:3000
- You should see the GlassNote landing page

---

## ⚙️ Configuration

### Backend Environment Variables

#### Required for Basic Functionality

```env
DATABASE_URL=postgresql+asyncpg://glassnote:glassnote@localhost:5432/glassnote
JWT_SECRET=your-secret-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

#### Optional Features

| Variable | Purpose | Required For |
|----------|---------|--------------|
| `OPENAI_API_KEY` | OpenAI API access | GPT models, Whisper STT |
| `DEEPGRAM_API_KEY` | Deepgram STT | Alternative STT provider |
| `STRIPE_SECRET_KEY` | Payment processing | Billing features |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhooks | Subscription management |
| `SENDGRID_API_KEY` | Email sending | Email verification, notifications |
| `GOOGLE_CLIENT_ID` | Google OAuth | Social login |
| `GOOGLE_CLIENT_SECRET` | Google OAuth | Social login |
| `ADMIN_SECRET` | Admin endpoints | Admin operations |

### GUI Configuration

The GUI stores configuration in a local JSON file. To manually configure:

**Location:** `GUI/config.json` (created on first run)

**Example:**
```json
{
  "api_keys": {
    "anthropic": "sk-ant-your-key-here",
    "openai": "sk-your-key-here"
  },
  "backend_url": "http://localhost:8000",
  "models": {
    "default_provider": "anthropic",
    "default_model": "claude-sonnet-4-20250514"
  },
  "overlay": {
    "opacity": 0.85
  }
}
```

### Database Configuration

The default Docker Compose setup creates a PostgreSQL database with:
- **Host:** localhost
- **Port:** 5432
- **Database:** glassnote
- **User:** glassnote
- **Password:** glassnote

**To use a different database:**

1. Update `DATABASE_URL` in [`backend/.env`](backend/.env)
2. Ensure the database exists
3. Run migrations: `alembic upgrade head`

---

## 🎯 Running the Application

### Development Mode (All Components)

You need **3 terminal windows**:

**Terminal 1 - Backend:**
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 - GUI:**
```bash
cd GUI
python main.py
```

**Terminal 3 - Website:**
```bash
cd website
npm run dev
```

### Running Individual Components

**Backend only:**
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

**GUI only (requires backend running):**
```bash
cd GUI
python main.py
```

**Website only:**
```bash
cd website
npm run dev
```

### Stopping Services

**Stop backend:** Press `Ctrl+C` in the backend terminal

**Stop GUI:** Right-click tray icon → Exit

**Stop website:** Press `Ctrl+C` in the website terminal

**Stop database:**
```bash
cd backend
docker compose down
```

**Stop database and remove data:**
```bash
cd backend
docker compose down -v
```

---

## 🐛 Troubleshooting

### Backend Issues

#### "Database connection failed"

**Cause:** PostgreSQL is not running or connection string is wrong

**Solution:**
```bash
cd backend
docker compose ps  # Check if db is running
docker compose up -d  # Start if not running
```

#### "Module not found" errors

**Cause:** Dependencies not installed

**Solution:**
```bash
cd backend
pip install -r requirements.txt
```

#### "Port 8000 already in use"

**Cause:** Another process is using port 8000

**Solution:**
```bash
# Find and kill the process
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Or use a different port
uvicorn app.main:app --reload --port 8001
```

### GUI Issues

#### "No module named 'PyQt6'"

**Cause:** GUI dependencies not installed

**Solution:**
```bash
cd GUI
pip install -r requirements.txt
```

#### "API key not configured"

**Cause:** Anthropic API key not set

**Solution:**
1. Right-click tray icon → Settings → API Keys
2. Enter your Anthropic API key
3. Click Save

#### Tray icon not visible

**Cause:** Windows system tray settings

**Solution:**
1. Click the up arrow (^) in the system tray
2. Drag the GlassNote icon to the main tray area
3. Or: Settings → Personalization → Taskbar → Select which icons appear

### Website Issues

#### "Cannot find module 'next'"

**Cause:** Node modules not installed

**Solution:**
```bash
cd website
npm install
```

#### "Port 3000 already in use"

**Cause:** Another process is using port 3000

**Solution:**
```bash
# Use a different port
npm run dev -- -p 3001
```

### Database Issues

#### "Docker daemon not running"

**Cause:** Docker Desktop is not started

**Solution:**
1. Open Docker Desktop application
2. Wait for it to fully start (whale icon in tray)
3. Try again: `docker compose up -d`

#### "Database tables not found"

**Cause:** Migrations not run

**Solution:**
```bash
cd backend
alembic upgrade head
```

#### Reset database completely

```bash
cd backend
docker compose down -v  # Remove database and volumes
docker compose up -d    # Recreate database
alembic upgrade head    # Recreate tables
```

---

## 💻 Development Workflow

### Daily Development Routine

1. **Start Docker Desktop** (if not already running)

2. **Start Backend:**
   ```bash
   cd backend
   docker compose up -d  # Start database
   uvicorn app.main:app --reload --port 8000
   ```

3. **Start GUI (optional):**
   ```bash
   cd GUI
   python main.py
   ```

4. **Start Website (optional):**
   ```bash
   cd website
   npm run dev
   ```

### Making Changes

#### Backend Changes

- Edit files in [`backend/app/`](backend/app/)
- Server auto-reloads on file changes (with `--reload` flag)
- Test changes at http://localhost:8000/docs

#### GUI Changes

- Edit files in [`GUI/`](GUI/)
- Restart the app to see changes: Right-click tray → Exit, then `python main.py`

#### Website Changes

- Edit files in [`website/src/`](website/src/)
- Browser auto-refreshes on file changes
- View at http://localhost:3000

### Database Migrations

When you modify database models:

```bash
cd backend
alembic revision --autogenerate -m "Description of changes"
alembic upgrade head
```

### Running Tests

**Backend tests:**
```bash
cd backend
pytest
```

**With coverage:**
```bash
cd backend
pytest --cov=app --cov-report=html
```

### Building for Production

**GUI executable:**
```bash
cd GUI
python build.py
# Output: dist/GlassNote.exe
```

**Website:**
```bash
cd website
npm run build
npm start  # Production server
```

**Backend Docker image:**
```bash
cd backend
docker build -t glassnote-api .
docker run -p 8000:8000 --env-file .env glassnote-api
```

---

## 📚 Additional Resources

### Documentation

- **Backend API Docs:** http://localhost:8000/docs (when running)
- **FastAPI:** https://fastapi.tiangolo.com/
- **SQLAlchemy:** https://docs.sqlalchemy.org/
- **Alembic:** https://alembic.sqlalchemy.org/

### GUI Documentation

- **PyQt6:** https://www.riverbankcomputing.com/static/Docs/PyQt6/
- **Anthropic API:** https://docs.anthropic.com/
- **OpenAI API:** https://platform.openai.com/docs/

### Website Documentation

- **Next.js:** https://nextjs.org/docs
- **Tailwind CSS:** https://tailwindcss.com/docs
- **React:** https://react.dev/

---

## 🔐 Security Notes

### Development vs Production

The default configuration is for **local development only**. For production:

1. **Change JWT_SECRET** to a strong random value:
   ```bash
   openssl rand -hex 32
   ```

2. **Use environment variables** instead of `.env` files

3. **Enable SSL/TLS** for all connections

4. **Set DEBUG=false** in production

5. **Use proper secrets management** (AWS Secrets Manager, Azure Key Vault, etc.)

### API Keys

- **Never commit API keys** to version control
- The `.gitignore` file excludes `.env` files
- Store production keys in secure secret management systems

---

## 📞 Support

If you encounter issues not covered in this guide:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review error messages carefully
3. Check Docker Desktop is running
4. Verify all dependencies are installed
5. Ensure API keys are configured correctly

---

**Happy coding! 🚀**
