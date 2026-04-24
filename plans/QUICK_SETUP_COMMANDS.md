# GlassNote - Quick Setup Commands

**Copy-paste ready commands for Windows setup**

---

## 📋 Prerequisites Check

```cmd
python --version
docker --version
docker compose version
node --version
npm --version
```

---

## 🚀 Backend Setup

```cmd
cd backend
docker compose up -d
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

**Keep this terminal running!**

---

## 🖥️ GUI Setup (New Terminal)

```cmd
cd GUI
pip install -r requirements.txt
python main.py
```

Look for the system tray icon in the bottom-right corner!

---

## 🌐 Website Setup (New Terminal)

```cmd
cd website
npm install
npm run dev
```

Open http://localhost:3000 in your browser!

---

## 🔑 Backend Environment File

Create `backend/.env` with this content:

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

---

## 🛑 Stop Services

**Stop Backend:** `Ctrl+C` in backend terminal

**Stop GUI:** Right-click tray icon → Exit

**Stop Website:** `Ctrl+C` in website terminal

**Stop Database:**
```cmd
cd backend
docker compose down
```

---

## 🔄 Restart Everything

```cmd
cd backend
docker compose up -d
uvicorn app.main:app --reload --port 8000
```

Then in separate terminals:
```cmd
cd GUI && python main.py
```

```cmd
cd website && npm run dev
```

---

## 🧪 Test URLs

- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- Website: http://localhost:3000

---

## 🐛 Quick Fixes

**Database not running:**
```cmd
cd backend
docker compose up -d
```

**Port already in use:**
```cmd
# Backend - use different port
uvicorn app.main:app --reload --port 8001

# Website - use different port
npm run dev -- -p 3001
```

**Module not found:**
```cmd
# Backend
cd backend
pip install -r requirements.txt

# GUI
cd GUI
pip install -r requirements.txt

# Website
cd website
npm install
```

**Reset database:**
```cmd
cd backend
docker compose down -v
docker compose up -d
alembic upgrade head
```

---

## 📦 Install Node.js

If Node.js is not installed:

1. Download from: https://nodejs.org/
2. Choose "20.x LTS" version
3. Run installer with default settings
4. Restart terminal
5. Verify: `node --version`

---

## 🔑 Add API Keys Later

**Backend:** Edit `backend/.env`
```env
ANTHROPIC_API_KEY=sk-ant-your-key-here
OPENAI_API_KEY=sk-your-key-here
```

**GUI:** Right-click tray icon → Settings → API Keys

Or create `GUI/config.json`:
```json
{
  "api_keys": {
    "anthropic": "sk-ant-your-key-here",
    "openai": "sk-your-key-here"
  }
}
```

Get keys from:
- Anthropic: https://console.anthropic.com/
- OpenAI: https://platform.openai.com/api-keys

---

**That's it! You're ready to develop! 🎉**
