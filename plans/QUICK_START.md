# GlassNote - Quick Start Guide

Fast setup guide to get GlassNote running on your local machine.

---

## ⚡ Prerequisites Check

Before starting, verify you have:

- [ ] **Python 3.12+** installed
- [ ] **Node.js 20+** installed  
- [ ] **Docker Desktop** installed and running
- [ ] **Anthropic API Key** (get from https://console.anthropic.com/)

---

## 🚀 5-Minute Setup

### 1. Verify Python

```bash
python --version
```

Should show Python 3.12.x or higher.

### 2. Install Node.js (if needed)

Download from: https://nodejs.org/ (choose LTS version 20+)

### 3. Start Docker Desktop

Make sure Docker Desktop is running (whale icon in system tray).

### 4. Backend Setup

```bash
# Navigate to backend
cd backend

# Start PostgreSQL database
docker compose up -d

# Install dependencies
pip install -r requirements.txt

# Create environment file (you'll need to edit this)
copy .env.example .env

# Run database migrations
alembic upgrade head

# Start backend server
uvicorn app.main:app --reload --port 8000
```

**Important:** Edit `backend/.env` and add your `ANTHROPIC_API_KEY` before starting the server.

### 5. GUI Setup (New Terminal)

```bash
# Navigate to GUI
cd GUI

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

The app will appear as a tray icon in the bottom-right corner.

### 6. Website Setup (New Terminal)

```bash
# Navigate to website
cd website

# Install dependencies
npm install

# Start development server
npm run dev
```

Open http://localhost:3000 in your browser.

---

## 🎯 What's Running

After setup, you should have:

| Component | URL | Status |
|-----------|-----|--------|
| Backend API | http://localhost:8000 | ✓ |
| API Docs | http://localhost:8000/docs | ✓ |
| GUI App | System Tray Icon | ✓ |
| Website | http://localhost:3000 | ✓ |
| PostgreSQL | localhost:5432 | ✓ |

---

## 🔑 Configure API Keys

### Backend API Keys

Edit `backend/.env`:

```env
ANTHROPIC_API_KEY=sk-ant-your-key-here
OPENAI_API_KEY=sk-your-key-here
```

Restart the backend server after editing.

### GUI API Keys

**Option 1: Via GUI**
1. Right-click tray icon
2. Settings → API Keys
3. Enter your keys
4. Click Save

**Option 2: Via Config File**

Create `GUI/config.json`:
```json
{
  "api_keys": {
    "anthropic": "sk-ant-your-key-here",
    "openai": "sk-your-key-here"
  }
}
```

---

## 🧪 Test Your Setup

### Test Backend

```bash
# In your browser or using curl
curl http://localhost:8000/health
```

Should return: `{"status":"ok"}`

### Test GUI

1. Right-click tray icon
2. Click "New Session"
3. Fill in session details
4. If no errors, setup is working!

### Test Website

Open http://localhost:3000 - you should see the GlassNote landing page.

---

## 🛑 Stopping Services

**Stop Backend:** Press `Ctrl+C` in backend terminal

**Stop GUI:** Right-click tray icon → Exit

**Stop Website:** Press `Ctrl+C` in website terminal

**Stop Database:**
```bash
cd backend
docker compose down
```

---

## 🐛 Quick Troubleshooting

### "Database connection failed"

```bash
cd backend
docker compose ps  # Check if running
docker compose up -d  # Start if needed
```

### "Port already in use"

**Backend (port 8000):**
```bash
# Use different port
uvicorn app.main:app --reload --port 8001
```

**Website (port 3000):**
```bash
npm run dev -- -p 3001
```

### "Module not found"

**Backend:**
```bash
cd backend
pip install -r requirements.txt
```

**GUI:**
```bash
cd GUI
pip install -r requirements.txt
```

**Website:**
```bash
cd website
npm install
```

---

## 📚 Next Steps

- Read the full [SETUP.md](../SETUP.md) for detailed documentation
- Check [SETUP_PLAN.md](SETUP_PLAN.md) for architecture details
- Configure optional services (Stripe, SendGrid, etc.)
- Set up your development workflow

---

## 💡 Daily Development Workflow

1. **Start Docker Desktop** (if not running)

2. **Start Backend:**
   ```bash
   cd backend
   docker compose up -d
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

---

**Need help?** Check the full [SETUP.md](../SETUP.md) guide or the troubleshooting section.
