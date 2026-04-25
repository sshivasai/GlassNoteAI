# GlassNote - Local Development Setup Plan

**System:** Windows 11  
**Status:** Python ✓ | Docker ✓ | Node.js ✗  
**Goal:** Set up all three components (Backend + GUI + Website) for local development

---

## 📊 Project Architecture Overview

```mermaid
graph TB
    subgraph "Frontend Layer"
        GUI[GUI Desktop App<br/>PyQt6 + Python]
        WEB[Website<br/>Next.js 15 + React]
    end
    
    subgraph "Backend Layer"
        API[FastAPI Backend<br/>Python 3.12+]
    end
    
    subgraph "Data Layer"
        DB[(PostgreSQL 16<br/>Docker)]
    end
    
    subgraph "External Services"
        ANTHROPIC[Anthropic API<br/>Claude Models]
        OPENAI[OpenAI API<br/>Whisper STT]
        STRIPE[Stripe<br/>Payments]
    end
    
    GUI -->|HTTP/REST| API
    WEB -->|HTTP/REST| API
    API -->|asyncpg| DB
    API -->|Proxy| ANTHROPIC
    API -->|Proxy| OPENAI
    API -->|Webhooks| STRIPE
    
    style GUI fill:#e1f5ff
    style WEB fill:#e1f5ff
    style API fill:#fff3e0
    style DB fill:#f3e5f5
    style ANTHROPIC fill:#e8f5e9
    style OPENAI fill:#e8f5e9
    style STRIPE fill:#e8f5e9
```

---

## 🎯 Setup Strategy

### Phase 1: Prerequisites & Environment
1. Verify existing installations (Python, Docker)
2. Install Node.js 20 LTS
3. Verify all tools are accessible from command line

### Phase 2: Backend Infrastructure
1. Create environment configuration
2. Start PostgreSQL database
3. Install Python dependencies
4. Run database migrations
5. Test backend server

### Phase 3: GUI Application
1. Install GUI dependencies
2. Configure basic settings
3. Test application launch

### Phase 4: Website
1. Install Node.js dependencies
2. Start development server
3. Verify website loads

### Phase 5: Integration & Documentation
1. Test all components together
2. Document API key setup for later
3. Create daily workflow guide

---

## 📋 Detailed Setup Steps

### Step 1: Verify Python Installation

**Action:**
```cmd
python --version
```

**Expected Output:**
```
Python 3.12.x
```

**If version is too old or not found:**
- Download Python 3.12+ from https://www.python.org/downloads/
- During installation: ✓ Check "Add Python to PATH"
- Restart terminal after installation

---

### Step 2: Verify Docker Desktop

**Action:**
1. Open Docker Desktop application
2. Wait for it to fully start (whale icon in system tray)
3. Verify installation:

```cmd
docker --version
docker compose version
```

**Expected Output:**
```
Docker version 24.x.x
Docker Compose version v2.x.x
```

**If Docker is not running:**
- Start Docker Desktop from Start Menu
- Wait for "Docker Desktop is running" notification
- Try commands again

---

### Step 3: Install Node.js

**Action:**
1. Download Node.js 20 LTS from: https://nodejs.org/
2. Run the installer
3. Use default settings (includes npm)
4. Restart your terminal
5. Verify installation:

```cmd
node --version
npm --version
```

**Expected Output:**
```
v20.x.x
10.x.x
```

**Why Node.js 20?**
- Next.js 15 requires Node.js 18.18 or higher
- Version 20 LTS provides long-term stability
- Includes npm package manager

---

### Step 4: Create Backend Environment File

**Action:**
Navigate to backend directory and create `.env` file:

```cmd
cd backend
```

Create a new file named `.env` with the following content:

```env
# ── App ────────────────────────────────────────────────────
APP_NAME=GlassNote API
DEBUG=true

# ── Database ───────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://glassnote:glassnote@localhost:5432/glassnote

# ── Auth ───────────────────────────────────────────────────
JWT_SECRET=dev-secret-change-in-production-use-openssl-rand-hex-32
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=43200

# ── Provider API Keys ──────────────────────────────────────
# TODO: Add your API keys later
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
DEEPGRAM_API_KEY=

# ── Stripe (Optional) ──────────────────────────────────────
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=

# ── Email (Optional) ───────────────────────────────────────
SENDGRID_API_KEY=
FROM_EMAIL=noreply@localhost
REPLY_EMAIL=support@localhost

# ── Google OAuth (Optional) ────────────────────────────────
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# ── Admin ──────────────────────────────────────────────────
ADMIN_SECRET=dev-admin-secret

# ── CORS ───────────────────────────────────────────────────
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# ── Rate Limiting ──────────────────────────────────────────
RATE_LIMIT_PER_MINUTE=60
```

**Important Notes:**
- API keys are left empty for now - you'll add them later
- `DEBUG=true` enables verbose logging for development
- `JWT_SECRET` should be changed for production
- Database credentials match the Docker Compose configuration

**Windows Command to Create File:**
```cmd
echo # GlassNote Backend Environment Configuration > .env
notepad .env
```
Then paste the content above and save.

---

### Step 5: Start PostgreSQL Database

**Action:**
```cmd
cd backend
docker compose up -d
```

**What This Does:**
- Downloads PostgreSQL 16 Alpine image (if not cached)
- Creates a container named `glassnote-db`
- Exposes database on `localhost:5432`
- Creates persistent volume for data storage
- Runs health checks to ensure database is ready

**Verify Database is Running:**
```cmd
docker compose ps
```

**Expected Output:**
```
NAME           IMAGE                COMMAND                  SERVICE   STATUS
glassnote-db   postgres:16-alpine   "docker-entrypoint.s…"   db        Up (healthy)
```

**View Database Logs (if needed):**
```cmd
docker compose logs db
```

**Troubleshooting:**
- If port 5432 is already in use, stop other PostgreSQL instances
- If Docker daemon error: Ensure Docker Desktop is running
- To reset database: `docker compose down -v` then `docker compose up -d`

---

### Step 6: Install Backend Dependencies

**Action:**
```cmd
cd backend
pip install -r requirements.txt
```

**What Gets Installed:**
- **FastAPI** - Modern web framework
- **Uvicorn** - ASGI server
- **SQLAlchemy** - ORM for database operations
- **asyncpg** - Async PostgreSQL driver
- **Alembic** - Database migration tool
- **python-jose** - JWT token handling
- **Stripe** - Payment processing
- **SendGrid** - Email service
- **httpx** - HTTP client for API proxying

**Installation Time:** ~2-3 minutes

**Verify Installation:**
```cmd
python -c "import fastapi; print(fastapi.__version__)"
```

Should print FastAPI version (e.g., `0.110.0`)

---

### Step 7: Run Database Migrations

**Action:**
```cmd
cd backend
alembic upgrade head
```

**What This Does:**
Creates all necessary database tables:
- `users` - User accounts and authentication
- `sessions` - Interview session data
- `api_calls` - API usage tracking
- `usage_quotas` - Monthly usage limits
- `email_otps` - Email verification codes
- `system_notifications` - Admin broadcasts

**Expected Output:**
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> abc123, initial schema
INFO  [alembic.runtime.migration] Running upgrade abc123 -> def456, add plan expires
```

**Verify Tables Created:**
```cmd
docker compose exec db psql -U glassnote -d glassnote -c "\dt"
```

Should list all tables.

---

### Step 8: Test Backend Server

**Action:**
```cmd
cd backend
uvicorn app.main:app --reload --port 8000
```

**Expected Output:**
```
[glassnote] Starting GlassNote API
[glassnote] Debug mode: True
[glassnote] Anthropic key: ✗ (not configured)
[glassnote] OpenAI key:    ✗ (not configured)
[glassnote] Initializing database...
[glassnote] Database connection: ✓
[glassnote] ✓ Ready — accepting requests
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

**Test Endpoints:**

1. **Health Check:**
   - Open browser: http://localhost:8000/health
   - Should return: `{"status":"ok"}`

2. **API Documentation:**
   - Open browser: http://localhost:8000/docs
   - Interactive Swagger UI with all endpoints

3. **Root Endpoint:**
   - Open browser: http://localhost:8000
   - Should return API info

**Keep This Terminal Running** - Backend server needs to stay active

**Troubleshooting:**
- **Port 8000 in use:** Use `--port 8001` instead
- **Database connection failed:** Check Docker container is running
- **Module not found:** Re-run `pip install -r requirements.txt`

---

### Step 9: Install GUI Dependencies

**Open a NEW terminal window** (keep backend running)

**Action:**
```cmd
cd GUI
pip install -r requirements.txt
```

**What Gets Installed:**
- **PyQt6** - Cross-platform GUI framework
- **mss** - Fast screen capture
- **Pillow** - Image processing
- **anthropic** - Anthropic API client
- **openai** - OpenAI API client
- **sounddevice** - Audio recording
- **numpy/scipy** - Audio processing
- **deepgram-sdk** - Speech-to-text
- **keyboard** - Global hotkey support
- **PyMuPDF** - PDF parsing (resume upload)
- **python-docx** - Word document parsing
- **pywin32** - Windows API integration
- **pyinstaller** - Executable builder

**Installation Time:** ~3-5 minutes (PyQt6 is large)

**Verify Installation:**
```cmd
python -c "from PyQt6.QtWidgets import QApplication; print('PyQt6 OK')"
```

---

### Step 10: Test GUI Application

**Action:**
```cmd
cd GUI
python main.py
```

**What to Expect:**
- No window appears (this is normal!)
- App runs as a **system tray icon** only
- Look in the bottom-right corner of your taskbar
- You should see a small icon (may be hidden in the overflow area)

**Accessing the GUI:**
1. Click the up arrow (^) in system tray
2. Find the GlassNote icon
3. Right-click the icon to see menu:
   - New Session
   - Settings
   - About
   - Exit

**First Run Configuration:**
- The app will create a `config.json` file
- API keys can be configured later via Settings menu
- Backend URL defaults to `http://localhost:8000`

**Testing Without API Keys:**
- You can launch the app and explore the UI
- Session functionality requires API keys (add later)
- Settings and configuration work without keys

**To Stop GUI:**
- Right-click tray icon → Exit

---

### Step 11: Install Website Dependencies

**Open a NEW terminal window** (keep backend and GUI running if desired)

**Action:**
```cmd
cd website
npm install
```

**What Gets Installed:**
- **Next.js 15** - React framework with SSR
- **React 19** - UI library
- **Tailwind CSS 4** - Utility-first CSS
- **TypeScript** - Type safety
- **Lucide React** - Icon library
- **ESLint** - Code linting

**Installation Time:** ~2-4 minutes

**Expected Output:**
```
added 234 packages, and audited 235 packages in 2m

found 0 vulnerabilities
```

---

### Step 12: Test Website Development Server

**Action:**
```cmd
cd website
npm run dev
```

**Expected Output:**
```
  ▲ Next.js 15.5.15
  - Local:        http://localhost:3000
  - Environments: .env

 ✓ Starting...
 ✓ Ready in 2.3s
```

**Test Website:**
1. Open browser: http://localhost:3000
2. You should see the GlassNote landing page
3. Navigation should work (Home, Features, Pricing, etc.)
4. Responsive design (try resizing browser)

**Hot Reload:**
- Edit any file in `website/src/`
- Browser automatically refreshes with changes
- Great for rapid development

**To Stop Website:**
- Press `Ctrl+C` in terminal

---

## 🎯 Current Status Summary

After completing all steps, you should have:

| Component | Status | URL/Location |
|-----------|--------|--------------|
| PostgreSQL Database | ✓ Running | localhost:5432 |
| Backend API | ✓ Running | http://localhost:8000 |
| API Documentation | ✓ Available | http://localhost:8000/docs |
| GUI Application | ✓ Installed | System Tray Icon |
| Website | ✓ Running | http://localhost:3000 |

---

## 🔑 Next Steps: API Key Configuration

Your infrastructure is now set up! To enable full functionality:

### 1. Obtain API Keys

**Required:**
- **Anthropic API Key** - Get from https://console.anthropic.com/
  - Sign up for account
  - Navigate to API Keys
  - Create new key (starts with `sk-ant-`)

**Recommended:**
- **OpenAI API Key** - Get from https://platform.openai.com/api-keys
  - Needed for audio/voice features
  - Create new key (starts with `sk-`)

### 2. Configure Backend

Edit `backend/.env`:
```env
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
OPENAI_API_KEY=sk-your-actual-key-here
```

Restart backend server:
```cmd
# Press Ctrl+C in backend terminal
# Then restart:
uvicorn app.main:app --reload --port 8000
```

### 3. Configure GUI

**Option A: Via GUI Settings**
1. Right-click tray icon
2. Settings → API Keys
3. Enter your keys
4. Click Save

**Option B: Via Config File**
Edit or create `GUI/config.json`:
```json
{
  "api_keys": {
    "anthropic": "sk-ant-your-actual-key-here",
    "openai": "sk-your-actual-key-here"
  },
  "backend_url": "http://localhost:8000"
}
```

### 4. Test Full Functionality

1. **Create Account:**
   - Open GUI → New Session
   - Or use backend API at http://localhost:8000/docs

2. **Start Interview Session:**
   - Configure session details
   - Select problem type
   - Test screen capture
   - Test audio recording (if OpenAI key configured)

3. **Check Usage Tracking:**
   - Backend tracks API calls
   - View in database or via API endpoints

---

## 💻 Daily Development Workflow

### Starting Your Development Environment

**Terminal 1 - Database & Backend:**
```cmd
cd backend
docker compose up -d
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 - GUI (optional):**
```cmd
cd GUI
python main.py
```

**Terminal 3 - Website (optional):**
```cmd
cd website
npm run dev
```

### Stopping Services

**Stop Backend:** `Ctrl+C` in terminal 1

**Stop GUI:** Right-click tray icon → Exit

**Stop Website:** `Ctrl+C` in terminal 3

**Stop Database:**
```cmd
cd backend
docker compose down
```

**Stop Database & Remove Data:**
```cmd
cd backend
docker compose down -v
```

---

## 🔧 Development Tips

### Backend Development

**Auto-reload is enabled** - Changes to Python files automatically restart server

**View Logs:**
```cmd
# Backend logs appear in terminal
# Database logs:
docker compose logs -f db
```

**Database Migrations:**
When you modify models in `backend/app/models/`:
```cmd
cd backend
alembic revision --autogenerate -m "Description of changes"
alembic upgrade head
```

**Run Tests:**
```cmd
cd backend
pytest
```

### GUI Development

**No auto-reload** - Must restart app to see changes:
```cmd
# Right-click tray → Exit
# Then: python main.py
```

**Debug Mode:**
Edit `GUI/main.py` and add at top:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Build Executable:**
```cmd
cd GUI
python build.py
# Output: dist/GlassNote.exe
```

### Website Development

**Auto-reload enabled** - Changes automatically refresh browser

**View Build Output:**
```cmd
cd website
npm run build
```

**Production Mode:**
```cmd
cd website
npm run build
npm start
```

**Linting:**
```cmd
cd website
npm run lint
```

---

## 🐛 Common Issues & Solutions

### Backend Issues

**"Database connection failed"**
```cmd
# Check if database is running
cd backend
docker compose ps

# Restart if needed
docker compose restart db
```

**"Port 8000 already in use"**
```cmd
# Find process using port
netstat -ano | findstr :8000

# Kill process (replace PID)
taskkill /PID <PID> /F

# Or use different port
uvicorn app.main:app --reload --port 8001
```

**"Module not found"**
```cmd
cd backend
pip install -r requirements.txt
```

### GUI Issues

**"No module named 'PyQt6'"**
```cmd
cd GUI
pip install -r requirements.txt
```

**Tray icon not visible**
- Click up arrow (^) in system tray
- Drag icon to main tray area
- Or: Settings → Personalization → Taskbar

**"API key not configured" error**
- Add keys via Settings menu
- Or edit `GUI/config.json`
- Restart GUI app

### Website Issues

**"Cannot find module 'next'"**
```cmd
cd website
npm install
```

**"Port 3000 already in use"**
```cmd
# Use different port
npm run dev -- -p 3001
```

**Build errors**
```cmd
# Clear cache and reinstall
cd website
rmdir /s /q node_modules
rmdir /s /q .next
npm install
npm run dev
```

### Database Issues

**"Docker daemon not running"**
- Open Docker Desktop
- Wait for it to fully start
- Try command again

**Reset database completely**
```cmd
cd backend
docker compose down -v
docker compose up -d
alembic upgrade head
```

---

## 📊 System Architecture Details

### Backend Architecture

```mermaid
graph TB
    subgraph "FastAPI Application"
        MAIN[main.py<br/>App Entry Point]
        
        subgraph "Routers"
            AUTH[auth.py<br/>Authentication]
            SESSIONS[sessions.py<br/>Interview Sessions]
            PROXY[proxy.py<br/>LLM Proxy]
            BILLING[billing.py<br/>Stripe Integration]
            USAGE[usage.py<br/>Usage Tracking]
            NOTIF[notifications.py<br/>System Alerts]
        end
        
        subgraph "Services"
            AUTHSVC[auth.py<br/>Auth Logic]
            DBSVC[database.py<br/>DB Operations]
        end
        
        subgraph "Models"
            DBMODELS[database.py<br/>SQLAlchemy Models]
        end
        
        CONFIG[config.py<br/>Settings]
    end
    
    MAIN --> AUTH
    MAIN --> SESSIONS
    MAIN --> PROXY
    MAIN --> BILLING
    MAIN --> USAGE
    MAIN --> NOTIF
    
    AUTH --> AUTHSVC
    SESSIONS --> DBSVC
    PROXY --> DBSVC
    
    AUTHSVC --> DBMODELS
    DBSVC --> DBMODELS
    
    CONFIG --> MAIN
    
    style MAIN fill:#ff9800
    style CONFIG fill:#2196f3
```

### GUI Architecture

```mermaid
graph TB
    subgraph "GUI Application"
        MAIN[main.py<br/>Entry Point]
        CTRL[app_controller.py<br/>Main Controller]
        
        subgraph "API Layer"
            AUTHCLI[auth_client.py<br/>Backend Auth]
            PRICECLI[pricing_client.py<br/>Pricing Info]
            NOTIFCLI[notifications_client.py<br/>Notifications]
            USAGEREP[usage_reporter.py<br/>Usage Tracking]
            LOGINUI[login_ui.py<br/>Login Dialog]
        end
        
        subgraph "Audio Pipeline"
            RECORDER[recorder.py<br/>Audio Capture]
            VOICEGATE[voice_gate.py<br/>Voice Detection]
            STTDG[stt_deepgram.py<br/>Deepgram STT]
            STTOAI[stt_openai_realtime.py<br/>OpenAI STT]
            PIPELINE[pipeline.py<br/>Audio Pipeline]
        end
        
        subgraph "Screen Capture"
            SCREENSHOT[screenshot.py<br/>Screen Capture]
            AUTOWATCHER[auto_watcher.py<br/>Auto Capture]
            DIFF[diff.py<br/>Change Detection]
            REGIONSEL[region_selector.py<br/>Region Selection]
        end
        
        subgraph "LLM Integration"
            CLIENT[client.py<br/>LLM Client]
            STREAMER[streamer.py<br/>Response Streaming]
            PROMPTS[prompts.py<br/>Prompt Templates]
        end
        
        subgraph "UI Overlay"
            ANSWER[answer.py<br/>Answer Display]
            PILL[pill.py<br/>Status Pill]
            TICKER[ticker.py<br/>Usage Ticker]
        end
        
        subgraph "Session Management"
            SESSMGR[manager.py<br/>Session Manager]
            RESUMEPARSE[resume_parser.py<br/>Resume Parser]
            SETUPUI[setup_ui.py<br/>Setup Dialog]
        end
        
        subgraph "Settings"
            SETTINGSUI[ui.py<br/>Settings Dialog]
            SETTINGSCONF[config.py<br/>Config Manager]
        end
        
        subgraph "Hotkeys"
            HOTKEYMGR[manager.py<br/>Hotkey Manager]
        end
        
        subgraph "Utils"
            TRAY[tray.py<br/>System Tray]
            THEME[theme.py<br/>UI Theme]
            MODELS[models.py<br/>Data Models]
        end
    end
    
    MAIN --> CTRL
    CTRL --> AUTHCLI
    CTRL --> SESSMGR
    CTRL --> PIPELINE
    CTRL --> SCREENSHOT
    CTRL --> CLIENT
    CTRL --> ANSWER
    CTRL --> HOTKEYMGR
    CTRL --> TRAY
    
    style MAIN fill:#ff9800
    style CTRL fill:#f44336
```

### Data Flow

```mermaid
sequenceDiagram
    participant User
    participant GUI
    participant Backend
    participant Database
    participant Anthropic
    
    User->>GUI: Start Interview Session
    GUI->>Backend: POST /api/sessions/create
    Backend->>Database: Create session record
    Database-->>Backend: Session ID
    Backend-->>GUI: Session created
    
    User->>GUI: Capture screen
    GUI->>GUI: Take screenshot
    GUI->>Backend: POST /api/proxy/anthropic
    Backend->>Anthropic: Forward request
    Anthropic-->>Backend: Stream response
    Backend-->>GUI: Stream response
    GUI->>User: Display answer overlay
    
    GUI->>Backend: POST /api/usage/track
    Backend->>Database: Record API call
    Database-->>Backend: Usage updated
    Backend-->>GUI: Usage stats
```

---

## 📚 Additional Resources

### Documentation Links

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

### Project Documentation

- **Full Setup Guide:** [`SETUP.md`](../SETUP.md)
- **Quick Start:** [`plans/QUICK_START.md`](QUICK_START.md)
- **API Keys Guide:** [`plans/API_KEYS_GUIDE.md`](API_KEYS_GUIDE.md)

---

## ✅ Setup Checklist

Use this checklist to track your progress:

### Prerequisites
- [ ] Python 3.12+ installed and verified
- [ ] Docker Desktop installed and running
- [ ] Node.js 20+ installed and verified

### Backend Setup
- [ ] Created `backend/.env` file
- [ ] Started PostgreSQL with Docker
- [ ] Installed Python dependencies
- [ ] Ran database migrations
- [ ] Backend server running on port 8000
- [ ] Tested health endpoint

### GUI Setup
- [ ] Installed GUI dependencies
- [ ] Launched GUI application
- [ ] Found tray icon in system tray
- [ ] Explored settings menu

### Website Setup
- [ ] Installed Node.js dependencies
- [ ] Started development server
- [ ] Website loads at localhost:3000
- [ ] Navigation works correctly

### API Keys (Optional - Do Later)
- [ ] Obtained Anthropic API key
- [ ] Obtained OpenAI API key
- [ ] Configured backend `.env`
- [ ] Configured GUI settings
- [ ] Tested full functionality

---

## 🎉 Success Criteria

Your setup is complete when:

1. ✅ Backend API responds at http://localhost:8000/health
2. ✅ API documentation loads at http://localhost:8000/docs
3. ✅ GUI app appears in system tray
4. ✅ Website loads at http://localhost:3000
5. ✅ Database is running and accessible
6. ✅ No error messages in any terminal

---

## 🚀 You're Ready to Develop!

With infrastructure set up, you can:

- **Explore the codebase** - Understand how components work
- **Make changes** - Edit code and see results
- **Add features** - Extend functionality
- **Test locally** - Full development environment
- **Add API keys later** - When ready for full functionality

**Next:** Follow the API Keys Guide to enable LLM features!

---

**Questions or issues?** Check the troubleshooting section or review the full [`SETUP.md`](../SETUP.md) guide.
