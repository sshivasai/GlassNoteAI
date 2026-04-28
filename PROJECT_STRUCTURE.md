# GlassNote Project Structure

Clean, organized codebase with no duplicate files.

## Directory Tree

```
Proj_AI/
├── .git/                      # Git repository
├── .gitignore                 # Git ignore rules
├── README.md                  # Main documentation
├── SETUP.md                   # Setup instructions
├── pytest.ini                 # Pytest configuration
│
├── rustgui/                   # Rust + Tauri GUI (NEW - 6x faster)
│   ├── src/                   # React frontend
│   │   ├── App.tsx           # Main app
│   │   ├── main.tsx          # Entry point
│   │   ├── index.css         # Styles
│   │   └── components/       # UI components
│   │       ├── Pill.tsx
│   │       ├── AnswerOverlay.tsx
│   │       ├── SessionSetup.tsx
│   │       └── SettingsWindow.tsx
│   ├── src-tauri/            # Rust backend
│   │   ├── src/
│   │   │   ├── main.rs       # Entry + commands
│   │   │   ├── llm/          # LLM client + proxy
│   │   │   ├── capture/      # Screen capture
│   │   │   ├── audio/        # Audio pipeline + STT
│   │   │   ├── hotkeys/      # Global hotkeys
│   │   │   ├── tray/         # System tray
│   │   │   ├── session/      # Session management
│   │   │   └── utils/        # Config, logging, crash recovery
│   │   ├── Cargo.toml        # Rust dependencies
│   │   └── tauri.conf.json   # Tauri config
│   ├── package.json          # Node dependencies
│   ├── README.md             # Rust GUI docs
│   └── FEATURES.md           # Feature list
│
├── GUI/                       # Python PyQt6 GUI (original)
│   ├── main.py               # Entry point
│   ├── app_controller.py     # Main controller
│   ├── build.py              # PyInstaller build script
│   ├── requirements.txt      # Python dependencies
│   ├── api/                  # Backend API clients
│   ├── audio/                # Audio recording + STT
│   ├── capture/              # Screen capture
│   ├── hotkeys/              # Global hotkeys
│   ├── llm/                  # LLM client
│   ├── overlay/              # UI overlays (pill + answer)
│   ├── session/              # Session management
│   ├── settings/             # Settings UI
│   ├── utils/                # Utilities
│   └── tests/                # Unit tests
│
├── backend/                   # FastAPI backend + PostgreSQL
│   ├── app/
│   │   ├── main.py           # FastAPI app
│   │   ├── config.py         # Configuration
│   │   ├── models/           # SQLAlchemy models
│   │   ├── routers/          # API routes
│   │   │   ├── auth.py       # Authentication
│   │   │   ├── sessions.py   # Session management
│   │   │   ├── usage.py      # Usage tracking
│   │   │   ├── billing.py    # Stripe billing
│   │   │   ├── proxy.py      # LLM/STT proxy
│   │   │   └── notifications.py
│   │   └── services/         # Business logic
│   ├── alembic/              # Database migrations
│   ├── tests/                # Backend tests
│   └── requirements.txt      # Python dependencies
│
└── website/                   # Next.js 15 landing page
    ├── src/
    │   ├── app/              # App router
    │   └── components/       # React components
    ├── public/               # Static assets
    ├── package.json          # Node dependencies
    └── README.md             # Website docs
```

## File Count

| Directory | Type | Count |
|-----------|------|-------|
| `rustgui/src-tauri/src/` | Rust | 22 files |
| `rustgui/src/` | React/TS | 5 files |
| `GUI/` | Python | 80+ files |
| `backend/` | Python | 30+ files |
| `website/` | Next.js | 20+ files |

## Key Files

### Root
- `README.md` - Main project documentation
- `SETUP.md` - Quick setup guide
- `PROJECT_STRUCTURE.md` - This file

### Rust GUI
- `rustgui/README.md` - Rust GUI overview
- `rustgui/FEATURES.md` - Complete feature list
- `rustgui/src-tauri/src/main.rs` - Rust entry point (330 lines)
- `rustgui/src/App.tsx` - React app (180 lines)

### Python GUI
- `GUI/README.md` - Python GUI docs
- `GUI/main.py` - Entry point (100 lines)
- `GUI/app_controller.py` - Main controller (1280 lines)

### Backend
- `backend/README.md` - Backend docs
- `backend/app/main.py` - FastAPI app (200 lines)

### Website
- `website/README.md` - Website docs
- `website/src/app/page.tsx` - Landing page

## Cleaned Up

### Deleted Files
- ❌ `BEFORE_AFTER_COMPARISON.md`
- ❌ `FINAL_IMPLEMENTATION_SUMMARY.md`
- ❌ `IMPLEMENTATION_COMPLETE.md`
- ❌ `PRODUCTION_READINESS_REPORT.md`
- ❌ `QUICK_START_PRODUCTION.md`
- ❌ `README_PRODUCTION_UPGRADE.md`
- ❌ `CHANGES_SUMMARY.txt`
- ❌ `plans/` directory (all planning docs)

### Cleaned
- ✅ Removed all `__pycache__/` directories
- ✅ Removed all `*.pyc` files
- ✅ Consolidated documentation

## Configuration Files

- `.gitignore` - Comprehensive ignore rules
- `pytest.ini` - Python test configuration
- `rustgui/package.json` - Node dependencies
- `rustgui/src-tauri/Cargo.toml` - Rust dependencies
- `rustgui/tsconfig.json` - TypeScript config
- `rustgui/vite.config.ts` - Vite bundler
- `rustgui/tailwind.config.js` - Tailwind CSS

## No Duplicates

All code is unique:
- Rust GUI: Complete rewrite in Rust
- Python GUI: Original implementation
- No backup/old/temp files
- No redundant documentation

## Total Size

- **Rust GUI:** ~4,500 LOC
- **Python GUI:** ~8,000 LOC
- **Backend:** ~3,000 LOC
- **Website:** ~2,000 LOC
- **Total:** ~17,500 LOC

---

**Last Updated:** April 27, 2026  
**Status:** ✅ Clean & Organized
